# 002: SQL 안전성 관문 (`t2s/guard.py`)

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "순수 함수(DB·LLM 불필요)" 단계. 이후 `db.py` 의 실행 경로가 이 함수를 반드시 통과하게 된다.
- 선행 스펙: `specs/001-bootstrap.md` (PASS, `reviews/001-bootstrap.md`)
- 예상 분량: 파일 3개(신규 2 / 수정 1), 약 220줄

## 목표

LLM 이 생성한 SQL 문자열을 실행 직전에 검사하는 순수 함수 `ensure_safe_sql()` 을 만든다.
읽기 전용이 아닌 SQL·다중 스테이트먼트·주석 우회·시스템 스키마 접근을 차단하고, `LIMIT` 이 없으면 붙여서 정규화된 SQL 을 돌려준다.

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| `t2s/guard.py` | `UnsafeSQLError`, `MAX_ROWS`, `FORBIDDEN_KEYWORDS`, `_normalize()`, `ensure_safe_sql()` |
| `tests/test_guard.py` | 수용 기준 32행을 그대로 옮긴 테스트 |

**수정**
| 파일 | 무엇을 |
|---|---|
| `requirements.txt` | 마지막 줄 `pytest==9.1.1` 뒤에 **개행(LF) 하나만** 추가한다. `reviews/001-bootstrap.md` 의 [경미] 지적 사항이다. 내용·순서·버전은 한 글자도 바꾸지 마라. 이 파일에서 이것 외의 변경은 범위 이탈이다. |

**건드리지 말 것**
- `t2s/config.py`, `tests/test_config.py` — 001 에서 검수 PASS 된 부분이다. 한 줄도 고치지 마라.
- `t2s/__init__.py` — 0 바이트를 유지한다. `from .guard import ...` 같은 re-export 를 넣지 마라.
- `docker/` 전체, `.env`, `.env.example`, `.gitignore`, `docs/WORKFLOW.md`, `readme.md`, `specs/`, `reviews/`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `docker/initdb/03-readonly-user.sql` | `t2s_ro` 는 `sakila.*` 에 `SELECT`, `SHOW VIEW` 만 갖는다. 이것이 **2차 방어선**이고 이번 스펙은 **1차 방어선**이다. 이 파일을 근거로 "DB 가 어차피 막으니 guard 는 느슨해도 된다"고 판단하지 마라 — 두 겹 다 있어야 한다. |
| `t2s/config.py` | 예외 스타일의 참고 대상. `ConfigError(RuntimeError)` 처럼 **모듈 전용 예외 클래스를 하나 정의하고 그것만 던지는** 방식을 그대로 따른다. `config.py` 를 import 하지는 않는다 — `guard.py` 는 프로젝트 내부 모듈에 의존하지 않는다. |

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **검사는 문자열/정규식 기반이다.** `sqlglot`, `sqlparse`, `mysql-connector` 등 파서 라이브러리를 쓰지 마라. `requirements.txt` 에 의존성을 추가하지 마라. 표준 라이브러리 `re` 만 쓴다.
2. **`guard.py` 는 순수 함수 모듈이다.** DB 접속·파일 읽기·네트워크·`os.environ` 접근·`print`·`logging` 을 하지 마라. 입력은 인자뿐이고 출력은 반환값과 예외뿐이다.
3. **`LIMIT` 이 없으면 붙인다.** 거부하지 않는다. 그래서 `ensure_safe_sql` 의 반환 타입은 `str` 이다 (`bool` 이 아니다).
4. **이미 `LIMIT` 이 있으면 손대지 않는다.** `LIMIT 100000` 이어도 그대로 둔다. 숫자를 읽어 줄이는(clamp) 동작은 SQL 파싱이 필요하므로 이번 스펙에 넣지 않는다.
5. **문자열 리터럴 안의 내용은 검사 대상이 아니다.** `SELECT 'DROP TABLE film'` 은 안전한 SQL 이다. 따라서 키워드 검사는 원본이 아니라 **리터럴이 마스킹된 사본**으로 한다.
6. **검사 순서를 고정한다.** 위반이 여러 개인 입력에서 어떤 메시지가 나올지가 결정되어야 하므로, `ensure_safe_sql` 동작 규칙의 번호 순서를 반드시 지킨다.
7. **허용하는 시작 키워드는 `SELECT` 와 `WITH` 둘뿐이다.** MySQL 8 의 CTE 를 LLM 이 생성할 수 있으므로 `WITH` 를 막지 않는다. `WITH` 로 시작해도 금지 키워드 검사는 문장 전체에 그대로 적용되므로 안전하다.

## 파일별 계약

### `t2s/guard.py`

```python
import re


class UnsafeSQLError(ValueError):
    ...


MAX_ROWS: int = 200

FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",
    "MERGE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "RENAME",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "LOCK",
    "UNLOCK",
    "SET",
    "CALL",
    "EXECUTE",
    "PREPARE",
    "DEALLOCATE",
    "LOAD",
    "INFILE",
    "OUTFILE",
    "DUMPFILE",
    "HANDLER",
    "USE",
    "SHUTDOWN",
    "KILL",
    "FLUSH",
    "INTO",
)

SYSTEM_SCHEMAS: tuple[str, ...] = (
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
)


def _normalize(sql: str) -> tuple[str, str]:
    ...


def ensure_safe_sql(sql: str, max_rows: int = MAX_ROWS) -> str:
    ...
```

키워드 튜플의 **선언 순서를 바꾸지 마라.** 금지 키워드가 두 개 이상 걸린 입력에서 어떤 메시지가 나올지가 이 순서로 결정된다.

---

#### `_normalize(sql: str) -> tuple[str, str]`

반환값은 `(stripped, masked)` 두 문자열이다.

- `stripped` — **주석만 제거**된 SQL. 문자열 리터럴과 백틱 식별자의 내용은 원본 그대로 남는다. 최종 반환 SQL 의 재료다.
- `masked` — `stripped` 에서 추가로 **문자열 리터럴과 백틱 식별자의 내용만 제거**한 것. 여는/닫는 따옴표 문자 자체는 남긴다. 모든 검사(세미콜론·키워드·스키마·LIMIT)는 반드시 이 `masked` 로 한다.

구현 방식: **왼쪽에서 오른쪽으로 한 글자씩 훑는 상태 기계 하나**로 두 버퍼를 동시에 채운다. 정규식 두 번으로 나눠 처리하지 마라 — 리터럴 안의 `--` 를 주석으로 오인한다.

상태는 6개다: `NORMAL`, `SQUOTE`(`'`), `DQUOTE`(`"`), `BACKTICK`(`` ` ``), `LINE_COMMENT`, `BLOCK_COMMENT`.

동작 규칙 (번호대로, 순서대로):

1. 초기 상태는 `NORMAL`. `stripped`, `masked` 두 버퍼는 빈 문자열로 시작한다.
2. `NORMAL` 에서 현재 위치를 아래 순서로 판정한다. 먼저 걸리는 것이 이긴다.
   1. `/*!` 로 시작하면 → 즉시 `UnsafeSQLError("executable comment is not allowed")`. (MySQL 은 `/*! ... */` 안의 SQL 을 **실행한다.** 주석이 아니다.)
   2. `/*` 로 시작하면 → 두 버퍼에 공백 `" "` 을 하나씩 넣고 `BLOCK_COMMENT` 로 전이, 커서를 2 전진.
   3. `--` 로 시작하고 **그 다음 글자가 공백류이거나 문자열의 끝**이면 → 두 버퍼에 공백 하나씩 넣고 `LINE_COMMENT` 로 전이, 커서를 2 전진. (`a--b` 처럼 뒤에 공백이 없으면 MySQL 에서 주석이 아니다. 주석으로 처리하지 마라.)
   4. `#` 이면 → 두 버퍼에 공백 하나씩 넣고 `LINE_COMMENT` 로 전이, 커서를 1 전진.
   5. `'` / `"` / `` ` `` 이면 → 그 글자를 **두 버퍼 모두**에 넣고 각각 `SQUOTE` / `DQUOTE` / `BACKTICK` 으로 전이.
   6. 그 외 → 그 글자를 두 버퍼 모두에 넣는다.
3. `LINE_COMMENT` 에서는 `\n` 을 만날 때까지 아무 버퍼에도 넣지 않고 버린다. `\n` 을 만나면 그 `\n` 은 버리고 `NORMAL` 로 돌아간다. 문자열 끝에 도달해도 예외를 던지지 않는다 (줄 주석은 종료 표시가 필요 없다).
4. `BLOCK_COMMENT` 에서는 `*/` 를 만날 때까지 버린다. `*/` 를 만나면 커서를 2 전진하고 `NORMAL` 로 돌아간다. `*/` 없이 문자열 끝에 도달하면 → `UnsafeSQLError("unterminated block comment")`.
5. `SQUOTE` 에서:
   1. `\` 이면 → `\` 와 **그 다음 한 글자**를 `stripped` 에만 넣고 커서를 2 전진한다 (`masked` 에는 아무것도 넣지 않는다). 다음 글자가 없으면 → `UnsafeSQLError("unterminated string literal")`.
   2. `''` (작은따옴표 두 개 연속)이면 → 두 글자를 `stripped` 에만 넣고 커서를 2 전진한다. 리터럴은 끝나지 않는다.
   3. `'` 하나이면 → 그 글자를 **두 버퍼 모두**에 넣고 `NORMAL` 로 돌아간다.
   4. 그 외 → `stripped` 에만 넣는다.
   5. `NORMAL` 로 돌아오지 못한 채 문자열 끝에 도달하면 → `UnsafeSQLError("unterminated string literal")`.
6. `DQUOTE` 는 5번과 완전히 동일하되 기준 문자가 `"` 다. (MySQL 기본 모드에서 `"` 는 식별자가 아니라 문자열 리터럴이다.)
7. `BACKTICK` 에서:
   1. `` `` `` (백틱 두 개 연속)이면 → 두 글자를 `stripped` 에만 넣고 커서를 2 전진한다.
   2. `` ` `` 하나이면 → 두 버퍼 모두에 넣고 `NORMAL` 로 돌아간다.
   3. 그 외 → `stripped` 에만 넣는다.
   4. 끝까지 닫히지 않으면 → `UnsafeSQLError("unterminated identifier")`. (백틱 안에서는 `\` 가 이스케이프가 아니다. 5-1 규칙을 적용하지 마라.)
8. 훑기가 끝나면 `(stripped, masked)` 를 그대로 반환한다. 이 함수는 공백 정규화·strip 을 하지 않는다.

발생 예외:
| 예외 | 조건 | 메시지 형식 |
|---|---|---|
| `UnsafeSQLError` | `/*!` 로 시작하는 블록 주석 | `executable comment is not allowed` |
| `UnsafeSQLError` | `*/` 없이 끝난 블록 주석 | `unterminated block comment` |
| `UnsafeSQLError` | 닫히지 않은 `'` 또는 `"` 리터럴 | `unterminated string literal` |
| `UnsafeSQLError` | 닫히지 않은 `` ` `` 식별자 | `unterminated identifier` |

---

#### `ensure_safe_sql(sql: str, max_rows: int = MAX_ROWS) -> str`

동작 규칙 (번호대로, 순서대로). **이 순서가 곧 에러 메시지의 우선순위다.**

1. `max_rows` 가 `int` 가 아니거나 `1` 미만이면 → `ValueError(f"max_rows must be >= 1, got: {max_rows}")`. `UnsafeSQLError` 가 아니라 **맨 `ValueError`** 를 던진다 (호출자 코드의 버그이지 SQL 의 문제가 아니다). `bool` 은 `int` 의 서브클래스이므로 `isinstance(max_rows, bool)` 인 경우도 이 예외로 거른다.
2. `sql` 이 `str` 이 아니면 → `TypeError(f"sql must be str, got: {type(sql).__name__}")`.
3. `stripped, masked = _normalize(sql)` 을 호출한다. 여기서 나온 `UnsafeSQLError` 는 잡지 말고 그대로 올려보낸다.
4. 두 문자열 각각에 `re.sub(r"\s+", " ", s).strip()` 을 적용한다. 이후 모든 공백은 한 칸이고 앞뒤 공백은 없다.
5. `masked` 가 `;` 로 끝나면, `stripped` 와 `masked` **각각의 마지막 글자 하나**를 제거하고 다시 `.strip()` 한다. 이 제거는 **최대 한 번만** 한다 (반복문으로 여러 개를 지우지 마라).
6. `masked` 에 `;` 가 남아 있으면 → `UnsafeSQLError("multiple statements are not allowed")`.
7. `masked` 가 빈 문자열이면 → `UnsafeSQLError("empty SQL")`.
8. `masked.split()[0]` 을 대문자로 바꾼 값이 `"SELECT"` 도 `"WITH"` 도 아니면 → `UnsafeSQLError(f"only SELECT is allowed, got: {token}")`. `token` 은 **대문자로 바꾼 값**이다.
9. `FORBIDDEN_KEYWORDS` 를 **선언 순서대로** 돌면서 `re.search(rf"\b{kw}\b", masked, re.IGNORECASE)` 가 걸리는 첫 키워드에 대해 → `UnsafeSQLError(f"forbidden keyword: {kw}")`. `kw` 는 튜플에 적힌 대문자 그대로다.
10. `SYSTEM_SCHEMAS` 를 **선언 순서대로** 돌면서 `re.search(rf"\b{name}\s*\.", masked, re.IGNORECASE)` 가 걸리는 첫 이름에 대해 → `UnsafeSQLError(f"system schema access is not allowed: {name}")`. 뒤에 점(`.`)이 붙은 경우만 막는다 — `sys` 라는 이름의 컬럼을 오탐하지 않기 위해서다.
11. `re.search(r"\bLIMIT\b", masked, re.IGNORECASE)` 가 없으면 `stripped` 뒤에 `f" LIMIT {max_rows}"` 를 붙인다. 있으면 `stripped` 를 그대로 둔다.
12. `stripped` 를 반환한다. 반환값은 항상 한 줄이고, 앞뒤 공백이 없고, 세미콜론으로 끝나지 않는다.

발생 예외:
| 예외 | 조건 | 메시지 형식 |
|---|---|---|
| `ValueError` | `max_rows` 가 int 가 아니거나 1 미만 | `max_rows must be >= 1, got: 0` |
| `TypeError` | `sql` 이 str 이 아님 | `sql must be str, got: int` |
| `UnsafeSQLError` | 유효 세미콜론이 2개 이상 | `multiple statements are not allowed` |
| `UnsafeSQLError` | 주석/공백 제거 후 내용이 없음 | `empty SQL` |
| `UnsafeSQLError` | 첫 키워드가 SELECT/WITH 가 아님 | `only SELECT is allowed, got: DROP` |
| `UnsafeSQLError` | 금지 키워드 포함 | `forbidden keyword: UPDATE` |
| `UnsafeSQLError` | 시스템 스키마 참조 | `system schema access is not allowed: mysql` |
| `UnsafeSQLError` | `_normalize` 에서 올라온 4종 | 위 `_normalize` 표 참조 |

### `tests/test_guard.py`

규칙:
1. 아래 "수용 기준" 표의 **32행을 전부** 테스트로 옮긴다. 행을 합치거나 빼지 마라.
2. 통과 케이스(기대 출력이 문자열인 행)는 `@pytest.mark.parametrize("sql, expected", [...])` 하나로 묶어도 된다. 실패 케이스(기대가 예외인 행)도 `@pytest.mark.parametrize("sql, message", [...])` 하나로 묶어도 된다. **파라미터 케이스 개수는 표의 행 개수와 같아야 한다.**
3. 통과 케이스는 `assert ensure_safe_sql(sql) == expected` 로 **완전 일치** 비교한다. `in` 이나 `startswith` 로 느슨하게 비교하지 마라.
4. 예외 케이스는 `with pytest.raises(UnsafeSQLError) as exc:` 로 잡고 `assert str(exc.value) == message` 로 **완전 일치** 비교한다. `pytest.raises(..., match=...)` 는 부분 정규식 매칭이라 쓰지 마라.
5. `#29`, `#30` 은 `UnsafeSQLError` 가 아니라 각각 `ValueError`, `TypeError` 다. `UnsafeSQLError` 가 `ValueError` 의 서브클래스이므로, `#29` 는 `assert type(exc.value) is ValueError` 를 함께 단언해 서브클래스가 아닌 정확한 타입임을 확인한다.
6. 테스트에서 DB·네트워크·환경변수·파일을 건드리지 마라. `monkeypatch`, `tmp_path`, `pymysql` 을 import 하지 마라 — 순수 함수 테스트다.
7. `_normalize` 를 직접 테스트하지 마라. 비공개 함수이고 `ensure_safe_sql` 을 통해 전부 검증된다.

## 수용 기준

GLM 은 아래 표를 그대로 테스트 코드로 옮긴다. `expected` 열의 문자열은 **따옴표 안의 내용이 글자 단위로 정확한 기대값**이다.

| # | 입력 `sql` | 기대 | 비고 |
|---|---|---|---|
| 1 | `SELECT * FROM film` | `SELECT * FROM film LIMIT 200` | 기본 경로. LIMIT 자동 부착 |
| 2 | `SELECT * FROM film LIMIT 5` | `SELECT * FROM film LIMIT 5` | 기존 LIMIT 보존 (설계결정 4) |
| 3 | `SELECT * FROM film limit 5` | `SELECT * FROM film limit 5` | 소문자 limit 도 인식. 부착 안 함 |
| 4 | `select title from film` | `select title from film LIMIT 200` | 입력 대소문자는 보존. 부착되는 LIMIT 만 대문자 |
| 5 | `  SELECT   1  ` | `SELECT 1 LIMIT 200` | 공백 정규화 (규칙 4) |
| 6 | `SELECT\n1` (실제 개행) | `SELECT 1 LIMIT 200` | 개행도 한 칸 공백으로 |
| 7 | `SELECT 1;` | `SELECT 1 LIMIT 200` | 후행 세미콜론 1개 허용·제거 |
| 8 | `SELECT 1 ;  ` | `SELECT 1 LIMIT 200` | 세미콜론 앞뒤 공백 |
| 9 | `SELECT 1;;` | `UnsafeSQLError` / `multiple statements are not allowed` | 1개만 제거하므로 남은 것이 검출됨 (규칙 5-6 경계값) |
| 10 | `SELECT 1; DROP TABLE film` | `UnsafeSQLError` / `multiple statements are not allowed` | 세미콜론 검사가 키워드 검사보다 **먼저** |
| 11 | `WITH t AS (SELECT 1) SELECT * FROM t` | `WITH t AS (SELECT 1) SELECT * FROM t LIMIT 200` | CTE 허용 (설계결정 7) |
| 12 | `SELECT * FROM film -- 코멘트` | `SELECT * FROM film LIMIT 200` | `--` 줄 주석 |
| 13 | `SELECT * FROM film # 코멘트` | `SELECT * FROM film LIMIT 200` | `#` 줄 주석 |
| 14 | `SELECT /* hi */ 1` | `SELECT 1 LIMIT 200` | 블록 주석 → 공백 1칸 |
| 15 | `SELECT 1 -- ; DROP TABLE film` | `SELECT 1 LIMIT 200` | 주석 안의 세미콜론·키워드는 무해 |
| 16 | `SELECT 1--2` | `SELECT 1--2 LIMIT 200` | 뒤에 공백 없는 `--` 는 주석이 아님 (규칙 2-3 경계값) |
| 17 | `SELECT /*! DROP TABLE film */ 1` | `UnsafeSQLError` / `executable comment is not allowed` | MySQL 실행 주석 우회 |
| 18 | `SELECT /* 안 닫힘` | `UnsafeSQLError` / `unterminated block comment` | |
| 19 | `SELECT 'abc` | `UnsafeSQLError` / `unterminated string literal` | |
| 20 | ``SELECT `abc`` (백틱 하나만) | `UnsafeSQLError` / `unterminated identifier` | |
| 21 | `SELECT 'DROP TABLE film' AS x` | `SELECT 'DROP TABLE film' AS x LIMIT 200` | 리터럴 안 키워드는 통과, 원문 보존 (설계결정 5) |
| 22 | `SELECT title FROM film WHERE title = 'it''s'` | `SELECT title FROM film WHERE title = 'it''s' LIMIT 200` | `''` 이스케이프 |
| 23 | `SELECT 'a\'b' AS x` | `SELECT 'a\'b' AS x LIMIT 200` | 백슬래시 이스케이프. 파이썬 소스에서 raw string 으로 쓸 것 |
| 24 | ``SELECT `drop` FROM film`` | ``SELECT `drop` FROM film LIMIT 200`` | 백틱 식별자 안 키워드는 통과 |
| 25 | `DROP TABLE film` | `UnsafeSQLError` / `only SELECT is allowed, got: DROP` | 첫 키워드 검사가 금지 키워드 검사보다 **먼저** |
| 26 | `SET @a = 1` | `UnsafeSQLError` / `only SELECT is allowed, got: SET` | |
| 27 | `SELECT * FROM film FOR UPDATE` | `UnsafeSQLError` / `forbidden keyword: UPDATE` | SELECT 로 시작하지만 잠금 획득 |
| 28 | `SELECT * FROM film INTO OUTFILE '/tmp/x'` | `UnsafeSQLError` / `forbidden keyword: INTO` | `INTO` 가 `OUTFILE` 보다 튜플에서 앞이 아님에 주의 — **`OUTFILE` 이 아니라 `INTO` 가 맞다**. `INTO` 는 튜플 마지막이지만 `OUTFILE` 도 있으므로 선언 순서상 `OUTFILE`(25번째)이 `INTO`(32번째)보다 먼저 걸린다. **따라서 기대 메시지는 `forbidden keyword: OUTFILE` 이다.** |
| 29 | `SELECT * FROM mysql.user` | `UnsafeSQLError` / `system schema access is not allowed: mysql` | |
| 30 | `SELECT * FROM information_schema.tables` | `UnsafeSQLError` / `system schema access is not allowed: information_schema` | |
| 31 | `` (빈 문자열) / `   ` / `-- 주석뿐` | 셋 다 `UnsafeSQLError` / `empty SQL` | 파라미터 3개로 작성 |
| 32 | `SELECT 1` + `max_rows=10` | `SELECT 1 LIMIT 10` | 인자 전달 |

추가 케이스 (표 밖, 반드시 작성):

| # | 입력 | 기대 | 비고 |
|---|---|---|---|
| 33 | `ensure_safe_sql("SELECT 1", max_rows=0)` | `ValueError` / `max_rows must be >= 1, got: 0` | `type(exc.value) is ValueError` 도 단언 (규칙 5) |
| 34 | `ensure_safe_sql("SELECT 1", max_rows=True)` | `ValueError` / `max_rows must be >= 1, got: True` | `bool` 배제 경계값 |
| 35 | `ensure_safe_sql(123)` | `TypeError` / `sql must be str, got: int` | |
| 36 | `ensure_safe_sql("SELECT * FROM film")` 를 연속 두 번 호출 | 두 반환값이 동일 | 순수성 확인 |

**#28 주의:** 위 표의 비고대로 기대 메시지는 `forbidden keyword: OUTFILE` 이다. 표의 "기대" 열이 아니라 **비고의 결론을 따르라.** 헷갈리면 `FORBIDDEN_KEYWORDS` 튜플을 위에서부터 세어 먼저 나오는 키워드가 답이다.

## 검증 명령

PowerShell 에서 저장소 루트에 서서 한 줄씩 실행한다. (`&&` 금지.)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_guard.py -v
```
기대 출력: `failed 0`, `error 0`, `skipped 0`. 파라미터 케이스가 전부 `PASSED`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```
기대 출력: 001 의 12개를 포함해 전부 통과. `12 passed` 보다 큰 수가 나오고 `failed`/`error`/`skipped` 가 0 이어야 한다.

순수성·무의존성 확인:
```powershell
.\.venv\Scripts\python.exe -c "import ast,sys; t=ast.parse(open('t2s/guard.py',encoding='utf-8').read()); print(sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}))"
```
기대 출력:
```
['re']
```
`re` 외의 것이 하나라도 보이면 설계결정 1·2 위반이다.

의존성 무변경 확인:
```powershell
git diff --stat requirements.txt
```
기대 출력: `1 file changed, 1 insertion(+), 1 deletion(-)` (마지막 줄 개행 추가 하나뿐). 그 이상이면 범위 이탈이다.

## 하지 말 것

- `sqlglot`, `sqlparse`, `sqlalchemy` 등 파서 라이브러리를 설치하거나 import 하지 마라. `requirements.txt` 에 줄을 추가하지 마라.
- `re` 외의 모듈을 `t2s/guard.py` 에서 import 하지 마라 (`os`, `logging`, `typing`, `dataclasses` 전부 불필요하다).
- `LIMIT` 숫자를 읽어서 줄이지(clamp) 마라. 있으면 그대로 둔다.
- SQL 을 대문자로 통일해서 반환하지 마라. 입력의 대소문자를 보존한다.
- `t2s/config.py`, `tests/test_config.py` 를 고치지 마라. 001 검수 통과분이다.
- `t2s/db.py`, `t2s/llm.py`, `t2s/graph.py`, `t2s/cli.py` 를 만들지 마라.
- 위반을 발견했을 때 `False` 를 반환하거나 빈 문자열을 반환하지 마라. 반드시 예외를 던진다.
- 기대 메시지가 안 맞는다고 스펙의 메시지 문구를 코드에 맞춰 바꾸지 마라. 코드를 스펙에 맞춰라.
- 커밋하지 마라.

## 체크리스트

- [ ] 범위의 신규 2개 + 수정 1개(개행만)만 변경했다
- [ ] `UnsafeSQLError`, `MAX_ROWS`, `FORBIDDEN_KEYWORDS`, `SYSTEM_SCHEMAS`, `_normalize`, `ensure_safe_sql` 의 시그니처와 선언 순서를 글자 그대로 따랐다
- [ ] `ensure_safe_sql` 동작 규칙 1~12 를 **번호 순서대로** 구현했다 (검사 순서가 메시지를 결정한다)
- [ ] 수용 기준 36행 전부가 테스트로 존재하고, 예외 메시지를 `==` 로 완전 일치 비교한다
- [ ] `t2s/guard.py` 의 import 가 `re` 하나뿐이다 (검증 명령으로 확인했다)
- [ ] `pytest tests/ -q` 를 직접 실행했고 실제 출력을 그대로 보고했다
- [ ] `requirements.txt` 에 패키지를 추가하지 않았다
- [ ] 커밋하지 않았다

## 질문

GLM 이 막혔을 때 여기에 적는다. 초기값: 없음
