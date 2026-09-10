# 005: 프롬프트 조립 + 응답 추출 (`t2s/prompt.py`)

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "LLM 계층" 앞부분. LLM 구간에서 **네트워크가 필요 없는 순수 함수 부분**만 먼저 굳힌다. 실제 호출은 006 `llm.py` 다.
- 선행 스펙: `001-bootstrap`, `002-guard`, `003-db`, `004-schema` (전부 커밋 완료, 112 passed)
- 예상 분량: 파일 2개(신규 2 / 수정 0), 약 240줄

## 목표

`render_schema()` 가 만든 스키마 텍스트와 사용자 질문으로 ollama 메시지를 조립하고, 모델의 원시 응답에서 SQL 한 문장을 뽑아내는 순수 함수 두 개를 만든다.
DB·네트워크 없이 도는 결정적 테스트만으로 LLM 구간의 위험 부분 전부를 검증한다.

## 배경 (이 스펙의 근거)

`glm-5.3-flash:cloud` 로 스파이크를 두 차례 돌렸다. 실패한 사례는 **전부 응답 파싱**이었고 SQL 생성 능력은 문제가 없었다.

| 관측 | 내용 |
|---|---|
| 모델이 감싸는 형태가 매번 다르다 | ` ```sql ` 펜스 / ` ```json ` 펜스 / `</think>` 뒤 / 아무 표시 없이 추론 뒤 |
| `think=False` 가 안 먹는다 | `message.thinking` 은 항상 0자, 추론이 `content` 안에 섞여 온다 |
| `format=<JSON 스키마>` 가 강제되지 않는다 | 8/8 전부 마크다운 펜스로 감싸서 나와 JSON 파싱이 전멸했다. **구조화 출력에 의존하지 마라** |
| 출력 형식을 프롬프트 맨 위로 올리면 안정된다 | 아래 `SYSTEM_PROMPT` 로 한국어 질문 9종 × 2회 = **18/18 성공** (추출 실패 0, guard 오탐 0, DB 에러 0, 정답 일치 8/8, 거부 4/4) |

아래 계약의 추출 규칙은 스크래치패드에서 **실측 응답 14종에 대해 14/14 통과**를 확인한 것이다. 수용 기준의 입력 문자열은 전부 실제로 모델에게서 받아낸 원문이거나 그 최소 변형이다.

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| `t2s/prompt.py` | `SYSTEM_PROMPT`, `Extraction`, `build_messages()`, `extract_sql()` |
| `tests/test_prompt.py` | 수용 기준 전부. DB·네트워크 불필요 |

**수정**
| 파일 | 무엇을 |
|---|---|
| 없음 | — |

**건드리지 말 것**
- **`t2s/guard.py` — 한 글자도 고치지 마라.** `prompt.py` 는 SQL 을 실행하지 않으므로 guard 와 무관하다.
- `t2s/config.py`, `t2s/db.py`, `t2s/schema.py`, 그리고 그에 대응하는 기존 테스트 4개 — 001~004 검수 통과분이다.
- `t2s/__init__.py` — 0 바이트 유지.
- `docker/`, `.env`, `.env.example`, `.gitignore`, `requirements.txt`, `docs/`, `readme.md`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `t2s/db.py` `QueryResult` / `ColumnInfo` | frozen dataclass 스타일의 참고 대상. `Extraction` 도 같은 형태로 만든다. **import 하지는 마라** — `prompt.py` 는 `t2s` 내부 모듈에 의존하지 않는다. |
| `t2s/schema.py` `render_schema()` | `build_messages` 의 `schema_text` 인자에 들어갈 값을 만드는 함수. **호출하지 마라.** 이미 만들어진 문자열을 인자로 받는다. |
| `t2s/guard.py` `MAX_ROWS = 200` | `SYSTEM_PROMPT` 안의 "at most 200" 이 이 값과 같다. **import 해서 f-string 으로 조립하지 마라** — `SYSTEM_PROMPT` 는 리터럴 상수다 (설계결정 3). |

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **`prompt.py` 는 아무것도 호출하지 않는다.** 네트워크·DB·파일·환경변수 접근 금지. `ollama` 를 import 하지 마라. `t2s.config`, `t2s.db`, `t2s.schema`, `t2s.guard` 도 import 하지 마라. 허용 import 는 `dataclasses`, `json`, `re` 셋뿐이다.
2. **추출 결과는 3-way 다.** 모델이 명시적으로 거부한 것(`unsupported`)과 응답을 해석하지 못한 것(`unparsable`)은 다른 상황이고, CLI 가 다른 메시지를 내야 한다. `str` 이나 `str | None` 을 반환하지 마라.
3. **`SYSTEM_PROMPT` 는 리터럴 문자열 상수다.** f-string·`.format()`·문자열 덧셈으로 조립하지 마라. 스파이크에서 18/18 을 낸 문자열을 **글자 그대로** 옮긴다. 문구를 개선하지 마라 — 개선의 효과를 잴 방법이 아직 없다 (평가는 007).
4. **few-shot 예시를 넣지 마라.** 현재 zero-shot 으로 18/18 이다. 예시 추가는 007 골든셋으로 효과를 측정한 뒤에 판단한다.
5. **펜스 안과 펜스 밖의 규칙이 다르다.** 이 스펙에서 가장 중요한 부분이다.
   - 펜스 본문과 JSON 의 `sql` 필드는 **이미 SQL 만 들어있는 영역**이다. 통째로 쓴다. 그 안에서 `SELECT` 를 다시 찾지 마라 — `WITH t AS (SELECT ...) SELECT ...` 의 CTE 가 잘린다.
   - 펜스가 없는 본문은 산문과 SQL 이 섞여 있다. **마지막** `SELECT`/`WITH` 부터 끝까지 자른다. 첫 번째를 잡으면 추론 중에 예시로 쓴 SQL(세미콜론 포함)을 집어서 guard 가 `multiple statements are not allowed` 로 막는다. 스파이크에서 실제로 그렇게 실패했다.
6. **거부 센티널은 `SELECT`/`WITH` 가 하나도 없을 때만 본다.** `UNSUPPORTED` 를 무조건 부분문자열로 찾으면 `SELECT 'UNSUPPORTED' AS note` 같은 정상 SQL 을 거부로 오탐한다.
7. **`extract_sql` 은 예외를 던지지 않는다.** 어떤 문자열이 와도 `Extraction` 을 반환한다. 빈 문자열이 들어와도 `unparsable` 을 돌려준다.
8. **`extract_sql` 은 SQL 이 안전한지 검사하지 않는다.** 그건 `guard.ensure_safe_sql()` 의 일이다. `DROP TABLE film` 이 펜스 안에 있으면 `kind="unparsable"` 이 된다 (규칙 5의 `SELECT`/`WITH` 시작 조건 때문이지 안전성 판단 때문이 아니다). 금지 키워드 목록을 `prompt.py` 에 복사하지 마라.

## 파일별 계약

### `t2s/prompt.py`

```python
import json
import re
from dataclasses import dataclass


SYSTEM_PROMPT: str = """You are a MySQL 8.4 query writer for the `sakila` database.

Output format (strict):
- Reply with ONE fenced code block and nothing else:
```sql
<the query>
```
- No prose before or after the block. No trailing semicolon.
- If the request cannot be answered with a SELECT over the given schema, reply with exactly:
```sql
UNSUPPORTED
```

Query rules:
- Only SELECT (or WITH ... SELECT). Never INSERT/UPDATE/DELETE/DROP/ALTER/GRANT.
- Use only tables and columns present in the schema. Never invent names.
- Never reference information_schema, mysql, performance_schema or sys.
- Add LIMIT (at most 200) unless the query returns a single aggregate row.
- Use explicit JOIN ... ON, never comma joins."""

THINK_END: str = "</think>"
UNSUPPORTED: str = "UNSUPPORTED"
EXTRACTION_KINDS: tuple[str, ...] = ("sql", "unsupported", "unparsable")

FENCE = re.compile(r"```[ \t]*([A-Za-z]*)[ \t]*\r?\n(.*?)```", re.DOTALL)
SQL_START = re.compile(r"\b(?:SELECT|WITH)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Extraction:
    sql: str
    kind: str


def build_messages(schema_text: str, question: str) -> list[dict[str, str]]:
    ...


def _from_sql_text(body: str, *, whole: bool) -> Extraction | None:
    ...


def extract_sql(text: str) -> Extraction:
    ...
```

`SYSTEM_PROMPT` 는 위 삼중따옴표 문자열을 **글자 그대로** 옮긴다. 안쪽의 ` ```sql ` 세 줄도 프롬프트의 일부이므로 지우지 마라. 줄바꿈·하이픈·대소문자를 바꾸지 마라.

`FENCE` 와 `SQL_START` 의 정규식도 위 패턴을 글자 그대로 쓴다. `SQL_START` 가 캡처하지 않는 그룹 `(?:...)` 인 점에 주의하라.

---

#### `build_messages(schema_text: str, question: str) -> list[dict[str, str]]`

동작 규칙 (번호대로, 순서대로):

1. 길이 2의 `list` 를 반환한다. 원소는 각각 키가 `"role"` 과 `"content"` 인 `dict` 다.
2. 0번 원소는 `{"role": "system", "content": SYSTEM_PROMPT}` 다. `SYSTEM_PROMPT` 를 **가공하지 마라** (`.strip()` 도 하지 마라).
3. 1번 원소는 `{"role": "user", "content": f"{schema_text}\n\nQuestion: {question}"}` 다. 구분자는 빈 줄 하나(`\n\n`)이고, 접두사는 `"Question: "` (콜론 + 공백 한 칸)이다.
4. `schema_text` 와 `question` 을 `.strip()` 하지 마라. 인자를 그대로 쓴다.
5. `question` 이 빈 문자열이어도 예외를 던지지 마라. `"...\n\nQuestion: "` 가 그대로 만들어진다.
6. 인자 검증을 하지 마라. 예외를 던지지 마라.

발생 예외: 없음.

---

#### `_from_sql_text(body: str, *, whole: bool) -> Extraction | None`

비공개 헬퍼다. `whole` 은 **키워드 전용 인자**다 (`*` 를 시그니처에 그대로 둔다).

동작 규칙 (번호대로, 순서대로):

1. `body = body.strip()`. 결과가 빈 문자열이면 `None` 을 반환한다.
2. `starts = [m.start() for m in SQL_START.finditer(body)]` 로 `SELECT`/`WITH` 의 등장 위치를 전부 모은다.
3. `starts` 가 비어 있으면:
   1. `UNSUPPORTED in body.upper()` 이면 `Extraction(sql="", kind="unsupported")` 를 반환한다.
   2. 아니면 `None` 을 반환한다.
   - **이 순서가 설계결정 6이다.** `SELECT` 가 하나라도 있으면 센티널 검사를 하지 않는다.
4. `whole` 이 `True` 이면 `sql = body` 로 둔다 (자르지 않는다).
5. `whole` 이 `False` 이면:
   1. `sql = body[starts[-1]:].strip()` — **마지막** 등장 위치부터 끝까지.
   2. `sql = sql.split("\n\n")[0].strip()` — 빈 줄 뒤에 붙은 산문을 버린다.
6. `sql = sql.rstrip(";").strip()` 으로 후행 세미콜론을 제거한다. 세미콜론이 여러 개여도 전부 지운다 (`rstrip` 의 기본 동작).
7. `sql` 이 빈 문자열이거나 `SQL_START.match(sql)` 이 `None` 이면 `None` 을 반환한다. (`.match` 는 **문자열 처음**에서만 맞춘다. `.search` 를 쓰지 마라.)
8. `Extraction(sql=sql, kind="sql")` 을 반환한다.

발생 예외: 없음.

---

#### `extract_sql(text: str) -> Extraction`

동작 규칙 (번호대로, 순서대로). **이 순서가 곧 우회 경로의 우선순위다.**

1. `THINK_END` 가 `text` 에 있으면 `text = text.split(THINK_END)[-1]` 로 **마지막 조각만** 남긴다. 없으면 그대로 둔다.
2. `text = text.strip()`.
3. `blocks = [(lang.lower(), body.strip()) for lang, body in FENCE.findall(text)]` 로 코드 펜스를 전부 수집한다.
4. **JSON 경로.** 후보 목록 `[b for lang, b in blocks if lang == "json"] + [text]` 를 순서대로 돌면서:
   1. 후보의 `.lstrip()` 이 `"{"` 로 시작하지 않으면 건너뛴다.
   2. `json.loads(후보)` 를 시도한다. `json.JSONDecodeError` 가 나면 건너뛴다 (다른 예외는 잡지 마라).
   3. 결과가 `dict` 이고 `payload.get("sql")` 이 `str` 이면:
      - `inner = payload["sql"].strip()`
      - `inner` 가 빈 문자열이거나 `inner.upper() == UNSUPPORTED` 이면 `Extraction(sql="", kind="unsupported")` 를 반환한다.
      - 아니면 `_from_sql_text(inner, whole=True)` 의 결과를 반환한다. `None` 이면 `Extraction(sql="", kind="unparsable")` 를 반환한다.
   4. 위 조건에 안 맞으면 다음 후보로 넘어간다.
5. **펜스 경로.** `blocks` 를 순서대로 돌면서 `lang` 이 `"sql"` 이거나 `""` 인 것에 대해 `_from_sql_text(body, whole=True)` 를 부른다. `None` 이 아닌 첫 결과를 반환한다. (`lang` 이 `"json"`, `"python"` 등인 펜스는 여기서 건너뛴다.)
6. **펜스 없음 경로.** `_from_sql_text(text, whole=False)` 를 부른다. `None` 이면 `Extraction(sql="", kind="unparsable")` 를 반환한다.
7. `text` 가 빈 문자열이면 6번을 거쳐 `Extraction(sql="", kind="unparsable")` 이 나온다. 별도 분기를 만들지 마라.
8. 로깅·print 를 하지 마라.

발생 예외: **없다.** `try/except` 는 4-2 의 `json.JSONDecodeError` 한 곳뿐이다.

### `tests/test_prompt.py`

규칙:
1. 아래 수용 기준의 **모든 행을 테스트로** 옮긴다. 행을 합치거나 빼지 마라.
2. **DB·네트워크에 접근하지 마라.** `pymysql`, `ollama`, `t2s.config`, `t2s.db`, `t2s.schema`, `t2s.guard` 를 import 하지 마라. `t2s.prompt` 만 import 한다.
3. `extract_sql` 케이스는 `@pytest.mark.parametrize("raw, expected_sql, expected_kind", [...])` 하나로 묶어도 된다. **파라미터 개수는 표의 행 개수와 같아야 한다.**
4. 단언은 `assert result == Extraction(sql=expected_sql, kind=expected_kind)` 로 **dataclass 전체를 `==` 비교**한다. `result.sql` 만 보거나 `in` 으로 느슨하게 비교하지 마라.
5. 입력 문자열은 파이썬 소스에 **이스케이프된 형태로** 쓴다. 실제 줄바꿈을 넣지 말고 `\n` 을 쓴다 (표의 표기를 그대로 옮기면 된다). 백슬래시가 들어가는 경우 raw string 을 쓴다.
6. `_from_sql_text` 를 직접 테스트하지 마라. 비공개 함수이고 `extract_sql` 을 통해 전부 검증된다.

## 수용 기준

`kind` 열이 기대 `Extraction.kind`, `sql` 열이 기대 `Extraction.sql` 이다. 입력의 `\n` 은 실제 줄바꿈 문자다.

**`extract_sql` — 실측 응답 (스파이크에서 받은 원문)**

| # | 입력 `text` | 기대 `sql` | 기대 `kind` | 비고 |
|---|---|---|---|---|
| 1 | ` ```sql\nSELECT COUNT(*) AS total_films\nFROM film\n```\n\n**Reason:** `film` 테이블의 전체 행 수를 세는 단순 집계 쿼리입니다. ` | `SELECT COUNT(*) AS total_films\nFROM film` | `sql` | 펜스 뒤에 산문. 줄바꿈이 SQL 안에 남는다 |
| 2 | ` ```json\n{\n  "sql": "SELECT a.first_name, a.last_name, COUNT(fa.film_id) AS film_count FROM actor a JOIN film_actor fa ON fa.actor_id = a.actor_id GROUP BY a.actor_id LIMIT 5",\n  "reason": "actor와 film_actor를 조인"\n}\n``` ` | `SELECT a.first_name, a.last_name, COUNT(fa.film_id) AS film_count FROM actor a JOIN film_actor fa ON fa.actor_id = a.actor_id GROUP BY a.actor_id LIMIT 5` | `sql` | JSON 펜스 경로 |
| 3 | `The question asks: "How many R-rated films are there?" in Korean.\n\nSimple query: SELECT COUNT(*) FROM film WHERE rating = 'R';\n\nThis returns a single aggregate row, so no LIMIT needed per rules ("Always add a LIMIT clause (at most 200) unless the query returns a single aggregate row").SELECT COUNT(*) FROM film WHERE rating = 'R'` | `SELECT COUNT(*) FROM film WHERE rating = 'R'` | `sql` | **핵심 케이스.** SELECT 가 두 번 나온다. 첫 번째를 잡으면 세미콜론이 껴서 guard 가 막는다 (설계결정 5) |
| 4 | `The question asks how many rentals are not returned.\n\nUse return_date IS NULL.</think>SELECT COUNT(*) AS not_returned_rentals\nFROM rental\nWHERE return_date IS NULL` | `SELECT COUNT(*) AS not_returned_rentals\nFROM rental\nWHERE return_date IS NULL` | `sql` | 여는 태그 없이 닫는 태그만 온다 |
| 5 | ` ```json\n{\n  "sql": "",\n  "reason": "고객 데이터를 삭제하는 요청은 DELETE 문이 필요하지만, 이 시스템은 읽기 전용(SELECT)만 허용됩니다."\n}\n``` ` | `` (빈 문자열) | `unsupported` | JSON 거부 |
| 6 | ` ```sql\nUNSUPPORTED\n``` ` | `` | `unsupported` | 펜스 거부. 지시대로 나온 형태 |
| 7 | `The user is asking in Korean: "Delete all customer data".\n\nThis is a DELETE request, which is not allowed. According to the rules, output exactly: UNSUPPORTED.UNSUPPORTED` | `` | `unsupported` | 센티널이 두 번 붙어 나온 실측 사례 |
| 8 | `죄송합니다, 이 질문에는 답변할 수 없습니다.` | `` | `unparsable` | SELECT 도 센티널도 없음 |

**`extract_sql` — 형태 변형 및 경계값**

| # | 입력 `text` | 기대 `sql` | 기대 `kind` | 비고 |
|---|---|---|---|---|
| 9 | ` ```\nSELECT title FROM film ORDER BY title LIMIT 3\n``` ` | `SELECT title FROM film ORDER BY title LIMIT 3` | `sql` | 언어 표기 없는 펜스도 받는다 (계약 5번) |
| 10 | ` ```sql\nWITH t AS (SELECT film_id FROM film) SELECT COUNT(*) FROM t\n``` ` | `WITH t AS (SELECT film_id FROM film) SELECT COUNT(*) FROM t` | `sql` | **CTE 보존.** 펜스 안에서 SELECT 를 다시 찾으면 `WITH` 절이 잘린다 (설계결정 5) |
| 11 | ` ```sql\nSELECT 'UNSUPPORTED' AS note FROM film LIMIT 1\n``` ` | `SELECT 'UNSUPPORTED' AS note FROM film LIMIT 1` | `sql` | **센티널 오탐 방지.** SELECT 가 있으므로 센티널을 보지 않는다 (설계결정 6) |
| 12 | ` ```sql\nSELECT COUNT(*) FROM film;\n``` ` | `SELECT COUNT(*) FROM film` | `sql` | 후행 세미콜론 제거 |
| 13 | ` ```sql\nSELECT COUNT(*) FROM film;;\n``` ` | `SELECT COUNT(*) FROM film` | `sql` | 세미콜론 2개도 전부 제거 (`rstrip`) |
| 14 | `` (빈 문자열) | `` | `unparsable` | 경계값 (계약 7번) |
| 15 | `   \n\n  ` (공백만) | `` | `unparsable` | 경계값 |
| 16 | `Here you go: WITH t AS (SELECT film_id FROM film) SELECT COUNT(*) FROM t` | `SELECT COUNT(*) FROM t` | `sql` | **알려진 한계.** 펜스 없는 CTE 는 `WITH` 가 잘린다. 아래 "질문 1" 참조. 이 값이 기대값이다 — 고치려 하지 마라 |
| 17 | ` ```sql\nDROP TABLE film\n``` ` | `` | `unparsable` | `SELECT`/`WITH` 로 시작하지 않는다. **`unsafe` 같은 kind 를 새로 만들지 마라** (설계결정 8) |
| 18 | ` ```python\nprint("hi")\n``` ` | `` | `unparsable` | `sql`/`""` 이 아닌 lang 은 펜스 경로에서 건너뛰고, 본문에도 SELECT 가 없다 |
| 19 | `{"sql": "SELECT 1 LIMIT 1", "reason": "ok"}` | `SELECT 1 LIMIT 1` | `sql` | 펜스 없이 본문 자체가 JSON (계약 4번 후보 목록의 `+ [text]`) |
| 20 | `{"reason": "no sql key"}` | `` | `unparsable` | `sql` 키 없음 → JSON 경로를 통과해 6번 경로로 떨어진다 |
| 21 | `분석...</think>분석2...</think>SELECT 1 LIMIT 1` | `SELECT 1 LIMIT 1` | `sql` | `</think>` 가 두 번이면 **마지막** 조각 (계약 1번) |

**`build_messages`**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 22 | `build_messages("# schema: sakila (MySQL 8.4)\nTABLE t(c INT)", "영화 몇 편?")` | `[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "# schema: sakila (MySQL 8.4)\nTABLE t(c INT)\n\nQuestion: 영화 몇 편?"}]` | 리스트 전체를 `==` 비교 |
| 23 | #22 의 결과 `[0]["content"]` | `SYSTEM_PROMPT` 와 `is` 동일 | 가공하지 않았음을 단언 (계약 2번) |
| 24 | `build_messages("S", "")` | `[1]["content"] == "S\n\nQuestion: "` | 빈 질문 경계값. 예외 없음 |
| 25 | `build_messages("  S  ", "  Q  ")` | `[1]["content"] == "  S  \n\nQuestion:   Q  "` | strip 하지 않는다 (계약 4번) |
| 26 | `len(build_messages("S", "Q"))` | `2` | |
| 27 | `SYSTEM_PROMPT` | `"Only SELECT (or WITH ... SELECT)."` 를 포함하고, `"```sql"` 을 포함하고, `"UNSUPPORTED"` 를 포함하고, `"at most 200"` 을 포함한다 | 4개 단언. 프롬프트가 통째로 갈아엎어지지 않았음을 확인 |
| 28 | `SYSTEM_PROMPT.startswith(...)` | `"You are a MySQL 8.4 query writer for the `sakila` database."` 로 시작한다 | |

**구조**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 29 | `EXTRACTION_KINDS` | `("sql", "unsupported", "unparsable")` | 순서까지 일치 |
| 30 | 수용 기준 #1~#21 의 모든 결과 | `result.kind in EXTRACTION_KINDS` | 정의되지 않은 kind 가 안 나오는지 |
| 31 | `Extraction("SELECT 1", "sql")` 에 `obj.sql = "x"` 대입 | `dataclasses.FrozenInstanceError` | frozen 확인 |
| 32 | `inspect.signature(extract_sql).parameters` 키 목록 | `["text"]` | 인자가 하나뿐 |
| 33 | `inspect.signature(build_messages).parameters` 키 목록 | `["schema_text", "question"]` | |

## 검증 명령

PowerShell 에서 저장소 루트에 서서 한 줄씩 실행한다. (`&&` 금지.)

**컨테이너를 끈 상태에서도 통과해야 한다:**
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_prompt.py -v
```
기대 출력: `failed 0`, `error 0`, `skipped 0`. 파라미터 케이스가 전부 `PASSED`.

전체 회귀:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```
기대 출력: `112 passed` 보다 큰 수. 001~004 의 기존 테스트가 **하나도 깨지지 않아야 한다.** `failed`/`error`/`skipped` 는 0.

**무의존성 확인 (가장 중요):**
```powershell
.\.venv\Scripts\python.exe -c "import ast; t=ast.parse(open('t2s/prompt.py',encoding='utf-8').read()); print(sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}))"
```
기대 출력:
```
['dataclasses', 'json', 're']
```
`ollama`, `pymysql`, `t2s.db`, `t2s.guard`, `os` 중 하나라도 보이면 설계결정 1 위반이다.

**guard·기존 모듈 무변경 확인:**
```powershell
git diff --stat t2s/guard.py t2s/config.py t2s/db.py t2s/schema.py
```
기대 출력: **빈 출력.**

**프롬프트가 그대로 옮겨졌는지 확인:**
```powershell
.\.venv\Scripts\python.exe -c "from t2s.prompt import SYSTEM_PROMPT as p; print(len(p), len(p.splitlines()))"
```
기대 출력:
```
699 19
```

**추출기 수동 확인:**
```powershell
.\.venv\Scripts\python.exe -c "from t2s.prompt import extract_sql; print(extract_sql('```sql\nWITH t AS (SELECT 1 AS a) SELECT * FROM t\n```'))"
```
기대 출력:
```
Extraction(sql='WITH t AS (SELECT 1 AS a) SELECT * FROM t', kind='sql')
```

## 하지 말 것

- **`t2s/guard.py` 를 수정하지 마라.** 추출된 SQL 의 안전성 검사는 006 이후 호출자가 `ensure_safe_sql` 로 한다.
- `prompt.py` 에서 `ollama` 를 import 하거나 네트워크를 호출하지 마라. 그건 006 이다.
- `prompt.py` 에서 `t2s.*` 를 import 하지 마라 (`t2s.guard.MAX_ROWS` 포함).
- `SYSTEM_PROMPT` 의 문구를 고치거나 다듬지 마라. few-shot 예시를 추가하지 마라 (설계결정 3·4).
- `SYSTEM_PROMPT` 를 f-string 이나 문자열 조립으로 만들지 마라.
- `extract_sql` 이 예외를 던지게 하지 마라. `raise` 를 쓰지 마라.
- `except Exception:` 을 쓰지 마라. `json.JSONDecodeError` 한 곳만 잡는다.
- 펜스 본문이나 JSON `sql` 필드 안에서 `SELECT` 를 다시 찾지 마라 (설계결정 5).
- 펜스 없는 본문에서 **첫 번째** `SELECT` 를 잡지 마라. 마지막이다.
- `EXTRACTION_KINDS` 에 `"unsafe"`, `"error"` 같은 값을 추가하지 마라. 3개가 전부다.
- 수용 기준 #16 의 기대값을 "고쳐서" 통과시키지 마라. 알려진 한계이고 그 값이 정답이다.
- `t2s/llm.py`, `t2s/graph.py`, `t2s/cli.py`, `evals/` 를 만들지 마라. 다음 스펙이다.
- `requirements.txt` 에 의존성을 추가하지 마라.
- 커밋하지 마라.

## 체크리스트

- [ ] 범위의 신규 2개만 만들었다 (수정 파일 0개)
- [ ] `git diff --stat t2s/guard.py t2s/config.py t2s/db.py t2s/schema.py` 가 빈 출력이다
- [ ] `t2s/prompt.py` 의 import 가 `dataclasses`, `json`, `re` 셋뿐이다 (검증 명령으로 확인했다)
- [ ] `SYSTEM_PROMPT` 길이가 699자, 19줄이다 (검증 명령으로 확인했다)
- [ ] `SYSTEM_PROMPT`, `Extraction`, `build_messages`, `_from_sql_text`, `extract_sql` 의 시그니처를 글자 그대로 따랐다 (`whole` 은 키워드 전용)
- [ ] `extract_sql` 동작 규칙 1~8 을 **번호 순서대로** 구현했다 (경로 우선순위가 결과를 결정한다)
- [ ] 수용 기준 33행 전부가 테스트로 존재하고, `Extraction` 전체를 `==` 로 비교한다
- [ ] `tests/test_prompt.py` 가 컨테이너를 끈 상태에서도 통과한다
- [ ] `pytest tests/ -q` 가 112개 이상 통과하고 기존 테스트가 하나도 안 깨졌다
- [ ] 커밋하지 않았다

## 질문

구현 세션이 막혔을 때 여기에 적는다. 아래는 **스펙 작성 시점에 확인된 사항**이다.

1. **[알려진 한계] 펜스 없는 CTE 는 `WITH` 절이 잘린다.** 수용 기준 #16 이 그 케이스다. 펜스 밖에서는 "마지막 `SELECT`/`WITH`" 로 자르는 수밖에 없고, CTE 는 안쪽에 `SELECT` 를 품고 있어서 구조적으로 구분할 수 없다. 다만 (a) `SYSTEM_PROMPT` 가 펜스를 강제하므로 스파이크 18/18 이 전부 펜스로 왔고 이 경로는 비상용이며, (b) 잘려도 조용히 틀리지 않는다 — `SELECT COUNT(*) FROM t` 는 실행 시 `query failed [1146]: Table 'sakila.t' doesn't exist` 로 드러난다. **이 한계를 고치려고 규칙을 복잡하게 만들지 마라.**
2. **`SYSTEM_PROMPT` 길이 699자·19줄은 스펙 작성 시점 기준이다.** 문자열을 글자 그대로 옮기면 이 값이 나온다. 값이 다르면 옮기다 문구가 바뀐 것이므로 **프롬프트를 다시 확인하라** (검증 명령 참조).
3. **[이번 범위 밖] `t2s_ro` 로도 `staff.password` 가 읽힌다.** 스파이크에서 "직원 비밀번호 목록 보여줘" 에 모델이 `SELECT staff_id, first_name, last_name, username, password FROM staff` 를 생성했고 guard 와 DB 권한을 모두 통과했다. `SYSTEM_PROMPT` 에 "민감 컬럼 금지" 를 추가해 대응하지 마라 — 프롬프트는 막는 수단이 아니다. 컬럼 차단 목록을 guard 쪽에 넣는 별도 스펙이 필요하다.
