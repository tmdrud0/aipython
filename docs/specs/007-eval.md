# 007: 골든셋 평가 (`t2s/evaluate.py` + `evals/run_eval.py`)

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "평가 · 쿼리 효율성". 006 으로 end-to-end 가 연결됐으므로, 이제 **정확도를 숫자로 잰다.** 008 `graph.py` 의 설계(재시도 필요 여부)가 이 숫자로 결정된다.
- 선행 스펙: `001`~`006` (전부 커밋 완료, 164 passed)
- 예상 분량: 파일 3개(신규 3 / 수정 0), 약 220줄

## 목표

질문 27개와 실측 정답이 담긴 `evals/golden.jsonl` 을 읽어 전체 파이프라인(스키마 → LLM → guard → 실행)을 돌리고 점수표를 출력한다.
채점 로직은 순수 함수로 분리해 LLM 없이 결정적으로 테스트한다.

## 배경 (이 스펙의 근거)

`evals/golden.jsonl` **27행은 이미 저장소에 있다.** 정답은 전부 라이브 Sakila 에 참조 SQL 을 돌려 실측했다. 이 파일을 구현 세션이 만들지 않는다 (설계결정 1).

스펙 작성 시점에 참조 구현으로 전체를 돌린 결과다.

| 항목 | 값 |
|---|---|
| 통과 | **27/27 (100%)** |
| 소요 | 68초 (질문당 평균 2.5초) |
| 실패 유형 | 없음 |

**100% 라는 것이 이 스펙에서 가장 중요한 사실이다.** 회귀 감지에는 쓸모가 있지만 개선을 재는 자로는 아직 부족하다. 그래서 러너는 **점수 하나가 아니라 실패 유형별 분류**를 출력해야 한다. 나중에 난이도를 올릴 때 어디서 무너지는지 보이게 하기 위해서다.

천장을 찾으려고 더 어려운 질문도 던져봤고, 아래 두 가지를 확인했다.

1. **모델이 묻지 않은 컬럼을 덧붙인다.** "카테고리명과 제목을 알려줘" 에 `(카테고리, 제목, 대여횟수)` 3열을 반환했다. SQL 은 옳지만 요청한 모양이 아니다. 동점 처리도 참조 SQL 과 달랐다. 이런 **모양이 애매한 질문은 골든셋에서 뺐다** — 고칠 수 없는 실패가 회귀 스위트에 있으면 잡음이 된다.
2. **[보안] "고객 이메일 주소 전부 뽑아줘" 에 `SELECT email FROM customer LIMIT 200` 이 나와 실제 이메일이 출력됐다.** guard 와 `t2s_ro` 를 모두 통과한다. `staff.password` 에 이어 두 번째 사례다. 별도 스펙(컬럼 차단 목록)이 필요하다. **이 스펙에서 대응하지 마라.**

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| `t2s/evaluate.py` | `normalize_rows()`, `classify()`, `GoldenItem`, `load_golden()`, `OUTCOMES` |
| `evals/run_eval.py` | 실제 파이프라인을 돌려 점수표를 출력하는 스크립트 |
| `tests/test_evaluate.py` | `t2s/evaluate.py` 의 결정적 테스트. LLM·DB 불필요 |

**수정**
| 파일 | 무엇을 |
|---|---|
| 없음 | — |

**건드리지 말 것**
- **`evals/golden.jsonl` — 한 행도, 한 글자도 고치지 마라.** 27행 전부 라이브 DB 실측값이다. 질문을 다듬거나 `expect_rows` 를 조정하거나 항목을 추가·삭제하지 마라. **점수가 안 나온다고 정답을 고치는 것은 가장 심각한 위반이다.**
- **`t2s/` 의 기존 6개 모듈 — 한 글자도 고치지 마라.** `config.py`, `guard.py`, `db.py`, `schema.py`, `prompt.py`, `llm.py` 전부 001~006 검수 통과분이다. 특히 `SYSTEM_PROMPT` 를 손대지 마라 (설계결정 6).
- `t2s/__init__.py` — 0 바이트 유지.
- `tests/` 의 기존 6개 파일.
- `docker/`, `.env`, `.env.example`, `.gitignore`, `requirements.txt`, `docs/`, `readme.md`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `t2s/llm.py` `generate_sql()`, `LLMError` | 질문 → `Extraction`. 다시 구현하지 마라. |
| `t2s/guard.py` `UnsafeSQLError` | `run_query` 가 던지는 것을 잡는 데 쓴다. `ensure_safe_sql` 을 **직접 부르지 마라** — `run_query` 가 내부에서 부른다 (003 계약 1번). |
| `t2s/db.py` `run_query()`, `QueryError`, `fetch_schema()`, `fetch_foreign_keys()` | SQL 실행과 스키마 조회. |
| `t2s/schema.py` `render_schema()` | 스키마 텍스트. **루프 안에서 매번 부르지 마라** — 한 번 만들어 재사용한다 (설계결정 4). |
| `t2s/config.py` `load_settings()`, `ConfigError` | `evals/run_eval.py` 에서만 부른다. `t2s/evaluate.py` 에서는 부르지 마라. |
| `t2s/prompt.py` `Extraction` | `kind` 값 `"sql"`/`"unsupported"`/`"unparsable"` 이 `classify()` 의 입력이다. |

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **`evals/golden.jsonl` 은 입력이지 산출물이 아니다.** 이미 존재한다. 만들지도, 고치지도 마라.
2. **채점은 순수 함수로 분리한다.** `t2s/evaluate.py` 는 LLM·DB·네트워크를 모른다. `classify()` 는 원시 값만 받아 결과 문자열을 돌려준다. 그래서 `tests/test_evaluate.py` 가 컨테이너·네트워크 없이 돈다.
3. **행 비교는 "셀을 문자열로 바꾼 뒤 행 단위로 정렬해서 완전 일치" 다.**
   - **문자열화** — `Decimal('5314.21')` 과 `'5314.21'` 을 같게 보기 위해서다. JSON 에 `Decimal` 을 담을 수 없으므로 골든셋도 문자열로 저장돼 있다.
   - **정렬** — 같은 답을 내는 SQL 이 행 순서를 다르게 낼 수 있다. `ORDER BY` 를 안 써도 정답으로 친다.
   - **컬럼 이름은 비교하지 않는다.** `COUNT(*)` 든 `total_films` 든 상관없다.
   - 컬럼 **개수**는 비교한다. 묻지 않은 컬럼을 덧붙이면 실패다 (배경 1번).
4. **스키마 텍스트는 한 번만 만든다.** 27회 반복 안에서 `fetch_schema()`/`render_schema()` 를 부르지 마라. DB 를 27번 더 때린다.
5. **`run_eval.py` 는 `pytest` 가 아니다.** `tests/` 에 넣지 마라. `evals/` 아래 스크립트이고 사람이 손으로 돌린다. LLM 호출 27번은 68초가 걸려서 테스트 스위트에 들어가면 안 된다.
6. **프롬프트를 고치지 마라.** 점수를 올리려고 `SYSTEM_PROMPT` 를 손대는 것은 이번 범위 밖이다. 현재 27/27 이므로 올릴 여지도 없다. 프롬프트 변경은 이 러너가 생긴 **뒤에** 별도 사이클로 한다.
7. **재시도하지 마라.** 실패한 질문을 다시 묻지 마라. 1질문 = 1호출이다.
8. **결과 유형은 8개로 고정한다.** 새 유형을 추가하지 마라 (`OUTCOMES` 상수).

## 파일별 계약

### `t2s/evaluate.py` (신규)

```python
import json
from dataclasses import dataclass
from pathlib import Path


OUTCOMES: tuple[str, ...] = (
    "pass",
    "wrong_rows",
    "no_sql",
    "guard_block",
    "db_error",
    "llm_error",
    "wrong_refusal",
    "guard_saved",
)


@dataclass(frozen=True)
class GoldenItem:
    id: str
    question: str
    expect_kind: str
    expect_rows: tuple[tuple[str, ...], ...] | None
    reference_sql: str | None


def normalize_rows(rows) -> tuple[tuple[str, ...], ...]:
    ...


def load_golden(path: str | Path) -> tuple[GoldenItem, ...]:
    ...


def classify(
    item: GoldenItem,
    got_kind: str | None,
    got_rows: tuple[tuple[str, ...], ...] | None,
    failure: str | None,
) -> str:
    ...
```

`evaluate.py` 의 import 는 위 3줄이 전부다. `t2s.*`, `pymysql`, `ollama` 를 import 하지 마라.

---

#### `normalize_rows(rows) -> tuple[tuple[str, ...], ...]`

동작 규칙 (번호대로, 순서대로):

1. `rows` 의 각 행에 대해, 각 셀을 `str(cell)` 로 바꾼 `tuple` 을 만든다.
2. 만들어진 행 `tuple` 들을 **정렬**한다 (파이썬 기본 `sorted`, 튜플 사전순).
3. 결과를 `tuple` 로 반환한다.
4. `rows` 가 비어 있으면 빈 `tuple` `()` 을 반환한다.
5. `None` 셀은 `"None"` 이 된다 (`str(None)`). 별도 처리를 하지 마라.
6. 예외를 던지지 마라.

---

#### `load_golden(path) -> tuple[GoldenItem, ...]`

동작 규칙 (번호대로, 순서대로):

1. 파일을 `encoding="utf-8"` 로 읽는다. **인코딩을 생략하지 마라** — Windows 기본 인코딩으로 읽으면 한국어 질문이 깨진다.
2. 줄 단위로 순회하며 `line.strip()` 이 빈 줄은 건너뛴다.
3. 각 줄을 `json.loads` 로 파싱한다. 예외를 잡지 마라 (골든셋이 깨졌으면 즉시 드러나야 한다).
4. `expect_rows` 가 `None` 이면 그대로 `None` 으로 둔다. `None` 이 아니면 **`tuple(tuple(str(c) for c in row) for row in expect_rows)`** 로 변환한다 (JSON 은 리스트로 읽히므로 튜플로 바꿔야 `classify` 의 `==` 비교가 성립한다). `normalize_rows` 를 여기에 적용하지 마라 — 골든셋은 이미 정렬된 상태로 저장돼 있다.
5. `GoldenItem` 으로 만들어 **파일에 적힌 순서대로** `tuple` 에 담아 반환한다. 정렬하지 마라.
6. 파일이 없으면 `FileNotFoundError` 가 그대로 올라간다. 잡지 마라.

---

#### `classify(item, got_kind, got_rows, failure) -> str`

인자의 뜻:

| 인자 | 값 | 뜻 |
|---|---|---|
| `got_kind` | `"sql"` / `"unsupported"` / `"unparsable"` / `None` | `Extraction.kind`. LLM 호출 자체가 실패했으면 `None` |
| `got_rows` | 정규화된 행 튜플 / `None` | 실행에 성공했을 때만 값이 있다 |
| `failure` | `None` / `"llm"` / `"guard"` / `"db"` | 어느 단계에서 터졌는지 |

동작 규칙 (번호대로, 순서대로). **이 순서가 결과를 결정한다.**

1. `failure == "llm"` 이면 `"llm_error"` 를 반환한다.
2. `item.expect_kind == "unsupported"` 인 경우:
   1. `got_kind == "unsupported"` 이면 `"pass"`.
   2. `failure == "guard"` 이면 `"guard_saved"` — 모델은 SQL 을 만들었지만 guard 가 막았다. 안전하되 모델은 틀렸다.
   3. 그 외 전부 `"wrong_refusal"` — 거부했어야 하는데 안 했다.
3. `item.expect_kind == "sql"` 인 경우:
   1. `failure == "guard"` 이면 `"guard_block"`.
   2. `failure == "db"` 이면 `"db_error"`.
   3. `got_kind != "sql"` 이면 `"no_sql"` (`"unsupported"` 와 `"unparsable"` 둘 다 여기).
   4. `got_rows == item.expect_rows` 이면 `"pass"`.
   5. 그 외 `"wrong_rows"`.
4. 반환값은 반드시 `OUTCOMES` 안의 값이다.
5. 예외를 던지지 마라. 로깅·print 를 하지 마라.

---

### `evals/run_eval.py` (신규)

```python
def main() -> int:
    ...


if __name__ == "__main__":
    raise SystemExit(main())
```

동작 규칙 (번호대로, 순서대로):

1. `sys.path` 를 조작하지 마라. 저장소 루트에서 `python -m evals.run_eval` 로 실행되는 것을 전제한다. 따라서 `evals/__init__.py` 를 **빈 파일로 만든다** (`t2s/__init__.py` 와 같이 0 바이트).
2. `load_settings()` 를 부른다. `ConfigError` 가 나면 그 메시지를 출력하고 `1` 을 반환한다 (`raise` 하지 마라).
3. `load_golden("evals/golden.jsonl")` 로 27행을 읽는다. 경로는 모듈 상수 `GOLDEN_PATH: str = "evals/golden.jsonl"` 로 둔다.
4. `render_schema(fetch_schema(settings), fetch_foreign_keys(settings))` 를 **한 번만** 호출해 변수에 담는다 (설계결정 4).
5. 각 항목에 대해 순서대로:
   1. `generate_sql(schema_text, item.question, settings)` 를 부른다. `LLMError` 가 나면 `got_kind=None, got_rows=None, failure="llm"`.
   2. `Extraction.kind` 가 `"sql"` 이면 `run_query(extraction.sql, settings)` 를 부른다.
      - `UnsafeSQLError` → `failure="guard"`, `got_rows=None`
      - `QueryError` → `failure="db"`, `got_rows=None`
      - 성공 → `failure=None`, `got_rows=normalize_rows(result.rows)`
   3. `"sql"` 이 아니면 실행을 시도하지 마라. `got_rows=None, failure=None`.
   4. `classify(...)` 로 결과를 얻는다.
   5. 한 줄을 출력한다. 형식: `f"[{'OK  ' if outcome == 'pass' else 'FAIL'}] {item.id:8} {outcome:14} {detail}"` — `detail` 은 통과면 빈 문자열, 실패면 진단에 필요한 정보(에러 메시지 또는 생성된 SQL 앞부분)를 담는다.
   6. **`except Exception:` 을 쓰지 마라.** 잡는 것은 `LLMError`, `UnsafeSQLError`, `QueryError` 셋뿐이다.
6. 전부 끝나면 요약을 출력한다. 반드시 아래 세 가지를 포함한다:
   1. `통과 {pass_count}/{total}  ({비율:.0%})`
   2. 총 소요 시간(초)
   3. **결과 유형별 개수** — `OUTCOMES` 중 개수가 0이 아닌 것만, 개수 내림차순. (설계결정 8, 배경의 "점수 하나가 아니라 분류" )
7. 모든 항목이 `"pass"` 면 `0` 을, 하나라도 아니면 `1` 을 반환한다.
8. 재시도하지 마라. 각 항목당 `generate_sql` 은 정확히 한 번이다.
9. 결과를 파일로 쓰지 마라. 표준 출력만 쓴다.

### `tests/test_evaluate.py` (신규)

규칙:
1. 아래 수용 기준의 모든 행을 테스트로 옮긴다.
2. **`t2s.evaluate` 만 import 한다.** `t2s.llm`, `t2s.db`, `ollama`, `pymysql`, `evals.run_eval` 을 import 하지 마라. 네트워크·DB 에 접근하지 마라.
3. `GoldenItem` 은 테스트 안에서 직접 만든다.
4. `load_golden` 테스트는 `tmp_path` 에 임시 jsonl 을 써서 한다. **실제 `evals/golden.jsonl` 을 읽는 테스트는 #20 하나만** 만든다.
5. 비교는 `==` 완전 일치. 튜플과 리스트를 혼동하지 마라 — 반환 타입이 `tuple` 인지도 단언한다.

## 수용 기준

**`normalize_rows`**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 1 | `((1000,),)` | `(("1000",),)` | int → str |
| 2 | `((Decimal("5314.21"),),)` | `(("5314.21",),)` | `decimal.Decimal` 을 테스트에서 import 해 쓴다 |
| 3 | `((2, "b"), (1, "a"))` | `(("1", "a"), ("2", "b"))` | 정렬 |
| 4 | `()` | `()` | 빈 입력 |
| 5 | `((None,),)` | `(("None",),)` | `str(None)` (규칙 5) |
| 6 | `((1,), (1,))` | `(("1",), ("1",))` | 중복 행을 합치지 않는다 |
| 7 | `normalize_rows(((1,),))` 의 타입 | `tuple` 이고 원소도 `tuple` | `list` 아님 |

**`classify` — `expect_kind == "sql"` 인 항목** (`ITEM_SQL = GoldenItem("x", "q", "sql", (("1000",),), None)`)

| # | `got_kind`, `got_rows`, `failure` | 기대 | 비고 |
|---|---|---|---|
| 8 | `"sql"`, `(("1000",),)`, `None` | `"pass"` | 정상 |
| 9 | `"sql"`, `(("999",),)`, `None` | `"wrong_rows"` | 값 불일치 |
| 10 | `"sql"`, `(("1000", "extra"),)`, `None` | `"wrong_rows"` | **묻지 않은 컬럼 추가** (설계결정 3) |
| 11 | `"unsupported"`, `None`, `None` | `"no_sql"` | 답할 수 있는데 거부했다 |
| 12 | `"unparsable"`, `None`, `None` | `"no_sql"` | 11과 같은 결과 |
| 13 | `"sql"`, `None`, `"guard"` | `"guard_block"` | guard 가 막음 |
| 14 | `"sql"`, `None`, `"db"` | `"db_error"` | 실행 실패 |
| 15 | `None`, `None`, `"llm"` | `"llm_error"` | 규칙 1이 가장 먼저 |

**`classify` — `expect_kind == "unsupported"` 인 항목** (`ITEM_REFUSE = GoldenItem("y", "q", "unsupported", None, None)`)

| # | `got_kind`, `got_rows`, `failure` | 기대 | 비고 |
|---|---|---|---|
| 16 | `"unsupported"`, `None`, `None` | `"pass"` | 제대로 거부 |
| 17 | `"sql"`, `None`, `"guard"` | `"guard_saved"` | 모델은 틀렸지만 guard 가 막았다 |
| 18 | `"sql"`, `(("1",),)`, `None` | `"wrong_refusal"` | 거부했어야 하는데 실행됐다 |
| 19 | `"unparsable"`, `None`, `None` | `"wrong_refusal"` | 거부로 인정하지 않는다 |
| 20 | `None`, `None`, `"llm"` | `"llm_error"` | 규칙 1이 `expect_kind` 분기보다 먼저 |

**`load_golden`**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 21 | 실제 `evals/golden.jsonl` | `len(result) == 27` | **유일하게 실제 파일을 읽는 테스트** |
| 22 | #21 의 결과 중 `expect_kind == "unsupported"` 인 개수 | `3` | `t5-01`, `t5-02`, `h-07` |
| 23 | #21 의 `result[0]` | `id == "t1-01"`, `expect_kind == "sql"`, `expect_rows == (("1000",),)` | 첫 행. 파일 순서 보존 (규칙 5) |
| 24 | #21 의 결과에서 `id == "t3-03"` 인 항목의 `expect_rows` | `(("1", "7923"), ("2", "8121"))` | 2행짜리 항목 |
| 25 | #21 의 모든 항목의 `expect_rows` 타입 | `None` 이거나 `tuple`, 내부 원소도 `tuple` | `list` 가 남아 있으면 `classify` 의 `==` 가 항상 실패한다 (규칙 4) |
| 26 | `tmp_path` 에 빈 줄이 섞인 2행 jsonl | `len(result) == 2` | 빈 줄 건너뛰기 (규칙 2) |
| 27 | `tmp_path` 에 한국어 질문이 든 1행 jsonl | `result[0].question` 이 원문과 `==` | UTF-8 확인 (규칙 1) |
| 28 | 없는 경로 | `FileNotFoundError` | 잡지 않는다 (규칙 6) |

**구조**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 29 | `OUTCOMES` | `("pass", "wrong_rows", "no_sql", "guard_block", "db_error", "llm_error", "wrong_refusal", "guard_saved")` | 순서까지 일치 |
| 30 | 수용 기준 #8~#20 의 모든 `classify` 결과 | `result in OUTCOMES` | 정의 밖 값이 안 나오는지 |
| 31 | `inspect.signature(classify).parameters` 키 목록 | `["item", "got_kind", "got_rows", "failure"]` | |
| 32 | `GoldenItem("a","b","sql",None,None)` 에 `obj.id = "x"` 대입 | `dataclasses.FrozenInstanceError` | frozen 확인 |

## 검증 명령

PowerShell 에서 저장소 루트에 서서 한 줄씩 실행한다. (`&&` 금지.)

**단위 테스트 (LLM·DB 불필요):**
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluate.py -v
```
기대 출력: `failed 0`, `error 0`, `skipped 0`.

**전체 회귀:**
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```
기대 출력: `164 passed` 보다 큰 수. 001~006 의 기존 테스트가 **하나도 깨지지 않아야 한다.** `failed`/`error`/`skipped` 는 0.

**골든셋 무변경 확인 (가장 중요):**
```powershell
git diff --stat evals/golden.jsonl
```
기대 출력: **빈 출력.** 한 줄이라도 나오면 정답을 손댄 것이고 FAIL 이다.

```powershell
.\.venv\Scripts\python.exe -c "print(sum(1 for l in open('evals/golden.jsonl',encoding='utf-8') if l.strip()))"
```
기대 출력:
```
27
```

**기존 모듈 무변경 확인:**
```powershell
git diff --stat t2s/
```
기대 출력: **빈 출력** (신규 `t2s/evaluate.py` 는 untracked 라 `git diff` 에 안 잡힌다. 잡히는 게 있으면 기존 파일을 고친 것이다).

**평가 실행 (필수, 실제 출력을 그대로 보고할 것):**
```powershell
docker compose -f docker/docker-compose.yml up -d
```
```powershell
.\.venv\Scripts\python.exe -m evals.run_eval
```
기대 출력: 27줄의 항목별 결과에 이어 요약. 스펙 작성 시점 참조 구현의 실측은 **27/27 (100%), 68초** 였다.
- 점수가 27/27 보다 낮게 나와도 **골든셋이나 프롬프트를 고치지 마라.** 실제 숫자와 실패 항목의 `detail` 을 그대로 보고하라. 클라우드 모델이라 편차가 있을 수 있고, 그 편차를 기록하는 것이 이 러너의 목적이다.
- 종료 코드 확인:
```powershell
.\.venv\Scripts\python.exe -m evals.run_eval; echo "exit=$LASTEXITCODE"
```
기대 출력: 27/27 이면 `exit=0`.

**무의존성 확인:**
```powershell
.\.venv\Scripts\python.exe -c "import ast; t=ast.parse(open('t2s/evaluate.py',encoding='utf-8').read()); print(sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}))"
```
기대 출력:
```
['dataclasses', 'json', 'pathlib']
```
`t2s.llm`, `t2s.db`, `ollama`, `pymysql` 중 하나라도 보이면 설계결정 2 위반이다.

## 하지 말 것

- **`evals/golden.jsonl` 을 수정하지 마라.** 점수가 안 나와도 정답을 고치지 마라. 질문 문구도 건드리지 마라.
- **`t2s/` 의 기존 6개 모듈을 수정하지 마라.** 특히 점수를 올리려고 `SYSTEM_PROMPT` 를 손대지 마라 (설계결정 6).
- `t2s/evaluate.py` 에서 `t2s.*`, `pymysql`, `ollama` 를 import 하지 마라.
- `run_eval.py` 를 `tests/` 에 넣지 마라. `pytest` 가 27번 LLM 을 부르게 하지 마라 (설계결정 5).
- 루프 안에서 `fetch_schema()` / `render_schema()` 를 부르지 마라.
- 실패한 질문을 재시도하지 마라.
- `except Exception:` 을 쓰지 마라. `LLMError`, `UnsafeSQLError`, `QueryError` 셋만 잡는다.
- `ensure_safe_sql()` 을 직접 부르지 마라. `run_query()` 가 부른다.
- `OUTCOMES` 에 새 값을 추가하지 마라. 8개가 전부다.
- 행 비교에서 컬럼 이름을 쓰지 마라. 값만 본다.
- `sys.path` 를 조작하지 마라. `python -m evals.run_eval` 로 돈다.
- 평가 결과를 파일이나 DB 에 쓰지 마라. 표준 출력만.
- 배경 2번의 컬럼 노출 문제를 이 스펙에서 고치려 하지 마라. `SYSTEM_PROMPT` 나 `guard.py` 를 건드리지 마라.
- `t2s/graph.py`, `t2s/cli.py` 를 만들지 마라. 다음 스펙이다.
- `requirements.txt` 에 의존성을 추가하지 마라.
- 커밋하지 마라.

## 체크리스트

- [ ] 범위의 신규 3개(+`evals/__init__.py`)만 만들었다. 수정 파일 0개
- [ ] `git diff --stat evals/golden.jsonl` 이 빈 출력이다
- [ ] `git diff --stat t2s/` 가 빈 출력이다
- [ ] `t2s/evaluate.py` 의 import 가 `dataclasses`, `json`, `pathlib` 셋뿐이다 (검증 명령으로 확인했다)
- [ ] `OUTCOMES`, `GoldenItem`, `normalize_rows`, `load_golden`, `classify` 의 시그니처와 필드 순서를 글자 그대로 따랐다
- [ ] `classify` 동작 규칙 1~5 를 **번호 순서대로** 구현했다 (`failure == "llm"` 이 가장 먼저)
- [ ] `load_golden` 이 `expect_rows` 를 `tuple` 로 변환한다 (`list` 로 두면 비교가 항상 실패한다)
- [ ] 수용 기준 32행 전부가 테스트로 존재한다
- [ ] `python -m evals.run_eval` 을 실제로 돌렸고 점수·소요시간·유형별 개수를 그대로 보고했다
- [ ] `pytest tests/ -q` 가 164개 이상 통과하고 기존 테스트가 하나도 안 깨졌다
- [ ] 커밋하지 않았다

## 질문

구현 세션이 막혔을 때 여기에 적는다. 아래는 **스펙 작성 시점에 확인된 사항**이다.

1. **골든셋이 현재 100% 라서 개선을 재는 자로는 부족하다.** 회귀 감지용으로는 유효하다. 난이도를 올린 항목을 추가하는 것은 이 러너가 생긴 **뒤에** 별도 사이클로 한다. 이 스펙에서 항목을 추가하지 마라.
2. **모양이 애매한 질문은 의도적으로 뺐다.** "각 카테고리에서 가장 많이 대여된 영화" 같은 질문에 모델이 묻지 않은 컬럼(대여 횟수)을 덧붙이고 동점 처리도 참조 SQL 과 달랐다. 설계결정 3의 "컬럼 개수도 비교한다" 때문에 이런 항목은 고칠 수 없는 실패가 된다. 골든셋에 넣지 마라.
3. **[이번 범위 밖, 미해결] 컬럼 단위 접근 제어가 없다.** "고객 이메일 주소 전부 뽑아줘" → `SELECT email FROM customer LIMIT 200` 이 실제 이메일을 반환한다. `staff.password` 에 이어 두 번째다. guard 에 컬럼 차단 목록을 넣는 별도 스펙이 필요하고, 그때 `evals/golden.jsonl` 에 해당 케이스를 추가한다. **이 스펙에서 대응하지 마라.**
