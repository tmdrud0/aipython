# 004: 스키마 렌더러 (`t2s/schema.py`) + `db.py` 확장

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "DB 계층" 마무리. LLM 프롬프트에 넣을 스키마 텍스트를 만든다. 이 스펙이 끝나면 `llm.py` 의 입력이 전부 준비된다.
- 선행 스펙: `001-bootstrap` (PASS), `002-guard` (PASS), `003-db` (PASS)
- 예상 분량: 파일 4개(신규 2 / 수정 2), 약 260줄

## 목표

`fetch_schema()` 가 잃어버리는 두 정보 — **외래키 22개**와 **enum/set 의 실제 값** — 을 `db.py` 에 추가하고, 그것들을 LLM 프롬프트용 텍스트 한 덩어리로 렌더링하는 순수 함수 `render_schema()` 를 만든다.

## 배경 (이 스펙의 근거)

스펙 작성 전에 `glm-5.3-flash:cloud` 로 스파이크를 돌렸다. 아래 형식의 스키마 2549자를 프롬프트에 넣었을 때 한국어 질문 9종 × 2회 = **18/18 성공**했다 (추출 실패 0, guard 오탐 0, DB 에러 0, 정답 일치 8/8, 거부해야 할 요청 거부 4/4).

```
TABLE film_actor(actor_id INT PK -> actor.actor_id, film_id INT PK -> film.film_id, last_update TIMESTAMP)
TABLE film(..., rating ENUM('G','PG','PG-13','R','NC-17'), ...)
```

정확도를 만든 것은 **`-> 테이블.컬럼` 화살표(FK)** 와 **ENUM 값 인라인** 두 가지다. 둘 다 현재 `ColumnInfo` 에 없다. 그래서 이 스펙은 `db.py` 수정으로 시작한다.

이 스펙의 모든 기대값은 라이브 `t2s-sakila` 컨테이너에서 실측한 값이다. 추측값은 없다.

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| `t2s/schema.py` | `short_type()`, `render_schema()`. 순수 함수만 |
| `tests/test_schema.py` | 수용 기준 중 순수 함수 부분 |

**수정**
| 파일 | 무엇을 |
|---|---|
| `t2s/db.py` | `ColumnInfo` 에 `column_type` 필드 1개 추가 / `SCHEMA_SQL` 에 `c.COLUMN_TYPE` 1개 추가 / `ForeignKey` dataclass · `FK_SQL` 상수 · `fetch_foreign_keys()` 함수 신규. **기존 함수 3개(`connect`, `run_query`, `fetch_schema`)의 시그니처는 바꾸지 마라.** |
| `tests/test_db.py` | `ColumnInfo` 전체 비교 단언 1곳(133~140행 부근)에 `column_type="int"` 추가 + `fetch_foreign_keys` 테스트 추가. **그 외 기존 테스트를 고치지 마라.** |

**건드리지 말 것**
- **`t2s/guard.py` — 한 글자도 고치지 마라.** 003 과 같은 이유다. `render_schema` 는 SQL 을 만들지 않으므로 guard 와 무관하다.
- `t2s/config.py`, `tests/test_config.py`, `tests/test_guard.py`
- `t2s/db.py` 의 `connect`, `run_query`, `fetch_schema` **본문 로직** (아래 계약이 지시한 최소 변경 외)
- `docker/`, `.env`, `.env.example`, `.gitignore`, `requirements.txt`, `docs/`, `readme.md`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `t2s/db.py:87` `fetch_schema()` | 커넥션 열고 → `try/finally` 로 닫고 → pymysql 예외 4종을 `QueryError` 로 감싸는 패턴. `fetch_foreign_keys()` 는 이 함수를 **그대로 베껴 쿼리와 변환만 바꾼다.** 새 접속 방식을 발명하지 마라. |
| `t2s/db.py:10` `QueryError` | 새 예외 클래스를 만들지 마라. `fetch_foreign_keys` 도 `QueryError` 를 던진다. |
| `t2s/db.py:22` `ColumnInfo` | 새 dataclass 를 만들지 말고 필드 하나만 추가한다. |
| `t2s/config.py` `Settings` | `fetch_foreign_keys(settings)` 도 `Settings` 를 인자로 받는다. |

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **`data_type` 을 지우지 말고 `column_type` 을 추가한다.** `data_type` 은 `"varchar"`, `column_type` 은 `"varchar(45)"` 다. 전자는 타입 분기에, 후자는 렌더링에 쓴다. `data_type` 을 제거하면 003 의 테스트 2개가 깨진다 — 그건 범위 이탈이다.
2. **`ColumnInfo` 의 새 필드는 `data_type` 바로 뒤에 넣는다.** 최종 필드 순서: `table_name, table_type, column_name, data_type, column_type, is_nullable, column_key`. frozen dataclass 라 순서가 곧 계약이다.
3. **외래키는 별도 함수 `fetch_foreign_keys()` 로 가져온다.** `fetch_schema()` 의 반환 타입을 바꾸지 마라 (003 검수 통과분). 쿼리 대상 테이블(`COLUMNS` vs `KEY_COLUMN_USAGE`)이 다르고 행의 모양도 다르므로 함수를 나누는 것이 맞다.
4. **`schema.py` 는 DB 를 모른다.** `fetch_schema()` 나 `fetch_foreign_keys()` 를 호출하지 마라. 이미 조회된 튜플을 인자로 받는다. 그래서 `tests/test_schema.py` 는 DB 없이 돈다.
   - `schema.py` 가 `from t2s.db import ColumnInfo, ForeignKey` 를 하는 것은 **허용한다.** 타입 정의를 가져오는 것뿐이고 호출 시점에 I/O 가 없으므로 순수성은 유지된다. 리뷰어는 이것을 위반으로 잡지 마라.
5. **뷰는 기본 제외다.** `include_views: bool = False`. 스파이크에서 BASE TABLE 16개(2549자)만으로 18/18 이 나왔다. 뷰 7개를 넣으면 954자가 늘 뿐이다. 인자로는 남겨두되 기본값은 `False`.
6. **테이블 순서를 파이썬에서 정렬하지 마라.** `SCHEMA_SQL` 의 `ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION` 이 이미 순서를 보장한다. **첫 등장 순서**를 그대로 유지한다 (`dict` 삽입 순서를 쓴다).
7. **`short_type` 은 `unsigned` 와 `tinyint(1)` 의 길이를 버린다.** `int unsigned` → `INT`, `tinyint(1)` → `TINYINT`. 스파이크에서 이 상태로 18/18 이 나왔으므로 정보 손실이 문제되지 않는다. 길이를 살리려 하지 마라.

## 파일별 계약

### `t2s/db.py` (수정)

#### 변경 1 — `ColumnInfo` 필드 추가

```python
@dataclass(frozen=True)
class ColumnInfo:
    table_name: str
    table_type: str
    column_name: str
    data_type: str
    column_type: str
    is_nullable: bool
    column_key: str
```

#### 변경 2 — `SCHEMA_SQL` 에 컬럼 하나 추가

`c.DATA_TYPE,` 바로 뒤에 `c.COLUMN_TYPE,` 를 넣는다. 최종 SELECT 목록은 다음 7개다:

```
c.TABLE_NAME, t.TABLE_TYPE, c.COLUMN_NAME, c.DATA_TYPE, c.COLUMN_TYPE, c.IS_NULLABLE, c.COLUMN_KEY
```

`FROM` 이하는 **한 글자도 바꾸지 마라.** `ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION` 도 그대로다.

#### 변경 3 — `fetch_schema()` 의 행 인덱스 보정

컬럼이 하나 늘었으므로 인덱스가 밀린다. `ColumnInfo` 생성 부분만 아래로 맞춘다. 그 외 본문(접속·예외 처리·`fetchall`)은 손대지 마라.

| 필드 | 행 인덱스 | 변환 |
|---|---|---|
| `table_name` | `row[0]` | 문자열 그대로 |
| `table_type` | `row[1]` | 문자열 그대로 |
| `column_name` | `row[2]` | 문자열 그대로 |
| `data_type` | `row[3]` | 문자열 그대로 |
| `column_type` | `row[4]` | 문자열 그대로 |
| `is_nullable` | `row[5]` | `row[5] == "YES"` |
| `column_key` | `row[6]` | 문자열 그대로 |

#### 변경 4 — `ForeignKey`, `FK_SQL`, `fetch_foreign_keys()` 신규

```python
@dataclass(frozen=True)
class ForeignKey:
    table_name: str
    column_name: str
    referenced_table: str
    referenced_column: str


FK_SQL: str = (
    "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
    "FROM information_schema.KEY_COLUMN_USAGE "
    "WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL "
    "ORDER BY TABLE_NAME, COLUMN_NAME"
)


def fetch_foreign_keys(settings: Settings) -> tuple[ForeignKey, ...]:
    ...
```

`fetch_foreign_keys` 동작 규칙 (번호대로, 순서대로):

1. **`sql` 파라미터를 만들지 마라.** 실행 문장은 `FK_SQL` 하나뿐이다 (003 설계결정 2와 같은 이유).
2. `ensure_safe_sql` 을 호출하지 마라. `FK_SQL` 은 신뢰된 상수이고, `information_schema` 를 읽으므로 guard 는 이것을 거부한다. **guard 를 고치지 마라.**
3. `connect(settings)` → `try/finally` 로 `close()`. `fetch_schema` 와 동일하다.
4. `cursor.execute(FK_SQL, (settings.db_name,))` — 스키마 이름은 반드시 `%s` 바인딩.
5. 예외 처리는 `fetch_schema` 와 동일하다: `pymysql.err.OperationalError`, `ProgrammingError`, `InternalError`, `DataError` 를 잡아 `QueryError(f"query failed [{exc.args[0]}]: {exc.args[1]}")` 로 감싸고 `raise ... from exc`. `except Exception:` 금지.
6. `cursor.fetchall()` 의 각 행 `(table_name, column_name, referenced_table, referenced_column)` 을 `ForeignKey` 로 변환한다. 네 값 모두 문자열 그대로 담는다.
7. `tuple` 로 반환한다. 파이썬에서 재정렬하지 마라.
8. 로깅·print 를 하지 마라.

발생 예외:
| 예외 | 조건 | 메시지 형식 |
|---|---|---|
| `QueryError` | 접속 실패 | `cannot connect to 127.0.0.1:3310: ...` (`connect()` 가 던진 것이 그대로 올라감) |
| `QueryError` | 실행 실패 | `query failed [1142]: ...` |

---

### `t2s/schema.py` (신규)

```python
from t2s.db import ColumnInfo, ForeignKey

PARAM_TYPES: frozenset[str] = frozenset({"varchar", "char", "decimal"})
VERBATIM_TYPES: frozenset[str] = frozenset({"enum", "set"})

HEADER: str = "# schema: sakila (MySQL 8.4)"


def short_type(column_type: str) -> str:
    ...


def render_schema(
    columns: tuple[ColumnInfo, ...],
    foreign_keys: tuple[ForeignKey, ...],
    include_views: bool = False,
) -> str:
    ...
```

`schema.py` 에서 `pymysql` 을 직접 import 하지 마라. `os`, `logging` 도 마찬가지다.

---

#### `short_type(column_type: str) -> str`

동작 규칙 (번호대로, 순서대로):

1. `base = column_type.split("(")[0].split(" ")[0].lower()` 로 기본 타입 이름을 얻는다.
2. `base` 가 `VERBATIM_TYPES` 에 있으면 → `base.upper() + column_type[len(base):]` 를 반환한다. 괄호 안의 값 목록을 **원본 그대로** 붙인다.
   - `"enum('G','PG','PG-13','R','NC-17')"` → `"ENUM('G','PG','PG-13','R','NC-17')"`
3. `base` 가 `PARAM_TYPES` 에 있고 `column_type` 에 `(` 가 있으면 → `base.upper() + column_type[column_type.index("("):column_type.index(")") + 1]` 를 반환한다.
   - `"varchar(45)"` → `"VARCHAR(45)"`, `"decimal(4,2)"` → `"DECIMAL(4,2)"`
4. 그 외 전부 → `base.upper()` 를 반환한다. 괄호와 `unsigned` 는 버린다.
   - `"int unsigned"` → `"INT"`, `"tinyint(1)"` → `"TINYINT"`, `"year"` → `"YEAR"`
5. 예외를 던지지 마라. 어떤 문자열이 와도 4번 규칙으로 값을 낸다.

---

#### `render_schema(columns, foreign_keys, include_views=False) -> str`

동작 규칙 (번호대로, 순서대로):

1. `foreign_keys` 로 조회용 `dict` 를 만든다. 키는 `(fk.table_name, fk.column_name)`, 값은 `(fk.referenced_table, fk.referenced_column)`. **같은 키가 두 번 나오면 먼저 나온 것을 쓴다** (덮어쓰지 마라).
2. `columns` 를 순서대로 훑으며 테이블별로 모은다. `include_views` 가 `False` 이면 `column.table_type == "VIEW"` 인 항목을 건너뛴다.
3. 테이블의 등장 순서를 보존한다. 파이썬에서 정렬하지 마라 (설계결정 6).
4. 출력의 첫 줄은 `HEADER` 상수다.
5. 테이블마다 한 줄을 만든다. 형식:
   ```
   {KIND} {table_name}({part}, {part}, ...)
   ```
   - `KIND` 는 `column.table_type == "VIEW"` 이면 `"VIEW"`, 아니면 `"TABLE"`.
   - 구분자는 쉼표 + 공백 한 칸(`", "`).
6. 각 `part` 는 아래 순서로 조립한다:
   1. `f"{column_name} {short_type(column_type)}"`
   2. `column_key == "PRI"` 이면 `" PK"` 를 덧붙인다.
   3. 1번 `dict` 에 `(table_name, column_name)` 이 있으면 `f" -> {ref_table}.{ref_column}"` 를 덧붙인다.
   - `is_nullable` 은 **출력에 넣지 마라.** 스파이크에서 없어도 18/18 이었고 길이만 늘어난다.
7. 줄들을 `"\n"` 으로 이어 반환한다. 마지막에 개행을 붙이지 마라. 앞뒤 공백도 없다.
8. `columns` 가 비어 있으면 `HEADER` 한 줄만 반환한다 (빈 문자열이 아니다).
9. 예외를 던지지 마라. DB·파일·네트워크에 접근하지 마라.

---

### `tests/test_db.py` (수정)

1. `ColumnInfo` 전체 비교 단언(133~140행 부근, `expected = ColumnInfo(...)`)에 `column_type="int"` 를 추가한다. `data_type="int"` 바로 뒤다. **다른 필드 값은 바꾸지 마라.**
2. import 줄에 `ForeignKey`, `fetch_foreign_keys` 를 추가한다.
3. 아래 수용 기준 #7~#10 에 해당하는 테스트를 파일 끝에 추가한다.
4. **그 외 기존 테스트를 고치지 마라.** 특히 `data_type` 을 단언하는 두 테스트(152행·165행 부근)는 그대로 통과해야 한다. 통과하지 않으면 `SCHEMA_SQL` 을 잘못 고친 것이다.

### `tests/test_schema.py` (신규)

1. 수용 기준 #11~#22 를 옮긴다.
2. **DB 에 접속하지 마라.** `pymysql`, `load_settings`, `connect`, `fetch_schema` 를 import 하지 마라. `ColumnInfo` / `ForeignKey` 객체를 테스트 안에서 직접 만들어 넘긴다.
3. 단, #19~#22 는 실제 Sakila 전체 데이터가 필요하다. 이 네 개만 `tests/test_db_render.py` 가 아니라 **`tests/test_db.py` 에** 넣는다 (그쪽은 이미 DB 를 쓴다). `tests/test_schema.py` 는 끝까지 DB 를 모른다.
4. 기대값 비교는 `==` 완전 일치. `in` 이나 `startswith` 를 쓰지 마라.

## 수용 기준

기대값은 전부 라이브 컨테이너 실측값이다.

**`tests/test_db.py` 에 들어갈 것 (DB 필요)**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 1 | `fetch_schema(settings)[0]` | `ColumnInfo(table_name="actor", table_type="BASE TABLE", column_name="actor_id", data_type="int", column_type="int unsigned", is_nullable=False, column_key="PRI")` | 기존 테스트 수정. `column_type` 추가. **(수정됨)** 구현 세션 실측에서 원문이 `int unsigned` 로 확인되어 기대값을 고쳤다 — `data_type` 은 `int`, `column_type` 은 `int unsigned` 이므로 오히려 004 #3 의 "두 필드가 다름" 취지에 부합한다 |
| 2 | `len(fetch_schema(settings))` | `131` | 기존 테스트. 그대로 통과해야 함 |
| 3 | `film.rating` 의 `ColumnInfo` | `data_type == "enum"`, `column_type == "enum('G','PG','PG-13','R','NC-17')"` | 두 필드가 다름을 확인 |
| 4 | `film.special_features` 의 `ColumnInfo` | `column_type == "set('Trailers','Commentaries','Deleted Scenes','Behind the Scenes')"` | |
| 5 | `customer.active` 의 `ColumnInfo` | `data_type == "tinyint"`, `column_type == "tinyint(1)"` | |
| 6 | `film.length` 의 `ColumnInfo` | `column_type == "smallint unsigned"` | `unsigned` 원문 보존 확인 |
| 7 | `len(fetch_foreign_keys(settings))` | `22` | Sakila FK 총 개수 |
| 8 | `fetch_foreign_keys(settings)[0]` | `ForeignKey(table_name="address", column_name="city_id", referenced_table="city", referenced_column="city_id")` | `ORDER BY TABLE_NAME, COLUMN_NAME` 로 첫 행 결정 |
| 9 | `fetch_foreign_keys` 결과 중 `table_name == "film"` 인 것 | 2개. `column_name` 이 `{"language_id", "original_language_id"}`, 둘 다 `referenced_table == "language"` | 한 테이블이 같은 테이블을 두 번 참조하는 경계값 |
| 10 | `inspect.signature(fetch_foreign_keys).parameters` 키 목록 | `["settings"]` | `sql` 파라미터가 없음을 단언 (설계결정 3) |
| 11 | `fetch_foreign_keys` 반환 타입 | `isinstance(result, tuple)` 이고 모든 원소가 `ForeignKey` | |
| 12 | `render_schema(fetch_schema(s), fetch_foreign_keys(s))` | `len(text) == 2549`, `len(text.splitlines()) == 17` | 통합. 기본값(뷰 제외) |
| 13 | 같은 입력, `include_views=True` | `len(text) == 3503`, `len(text.splitlines()) == 24` | 뷰 7개 추가분 |
| 14 | #12 의 `text.splitlines()[0]` | `"# schema: sakila (MySQL 8.4)"` | |
| 15 | #12 의 `text.splitlines()[-1]` | `"TABLE store(store_id INT PK, manager_staff_id INT -> staff.staff_id, address_id INT -> address.address_id, last_update TIMESTAMP)"` | |
| 16 | #12 에서 `"TABLE film_actor("` 로 시작하는 줄 | `"TABLE film_actor(actor_id INT PK -> actor.actor_id, film_id INT PK -> film.film_id, last_update TIMESTAMP)"` | PK + FK 동시 부착 경계값 |
| 17 | #12 에서 `"TABLE film("` 로 시작하는 줄 | `"TABLE film(film_id INT PK, title VARCHAR(255), description TEXT, release_year YEAR, language_id INT -> language.language_id, original_language_id INT -> language.language_id, rental_duration TINYINT, rental_rate DECIMAL(4,2), length SMALLINT, replacement_cost DECIMAL(5,2), rating ENUM('G','PG','PG-13','R','NC-17'), special_features SET('Trailers','Commentaries','Deleted Scenes','Behind the Scenes'), last_update TIMESTAMP)"` | 가장 복잡한 줄. 완전 일치 비교 |
| 18 | #12 의 `text` 에 `"VIEW "` 포함 여부 | `False` | 기본값이 뷰를 뺀다 (설계결정 5) |

**`tests/test_schema.py` 에 들어갈 것 (DB 없이)**

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 19 | `short_type("int")` | `"INT"` | |
| 20 | `short_type("int unsigned")` | `"INT"` | `unsigned` 제거 |
| 21 | `short_type("tinyint(1)")` | `"TINYINT"` | 길이 제거 |
| 22 | `short_type("smallint unsigned")` | `"SMALLINT"` | |
| 23 | `short_type("varchar(45)")` | `"VARCHAR(45)"` | 길이 보존 |
| 24 | `short_type("char(20)")` | `"CHAR(20)"` | |
| 25 | `short_type("decimal(4,2)")` | `"DECIMAL(4,2)"` | 쉼표 포함 |
| 26 | `short_type("decimal(27,2)")` | `"DECIMAL(27,2)"` | |
| 27 | `short_type("varchar")` | `"VARCHAR"` | 괄호 없는 PARAM 타입 경계값 |
| 28 | `short_type("enum('G','PG','PG-13','R','NC-17')")` | `"ENUM('G','PG','PG-13','R','NC-17')"` | |
| 29 | `short_type("set('Trailers','Commentaries','Deleted Scenes','Behind the Scenes')")` | `"SET('Trailers','Commentaries','Deleted Scenes','Behind the Scenes')"` | 값에 공백 포함 |
| 30 | `short_type("text")` / `("timestamp")` / `("datetime")` / `("year")` / `("mediumblob")` | `"TEXT"` / `"TIMESTAMP"` / `"DATETIME"` / `"YEAR"` / `"MEDIUMBLOB"` | 파라미터 5개 |
| 31 | `render_schema((), ())` | `"# schema: sakila (MySQL 8.4)"` | 빈 입력 경계값 (규칙 8) |
| 32 | 컬럼 1개(PK 아님, FK 없음)만 넘김 | `"# schema: sakila (MySQL 8.4)\nTABLE t(c INT)"` | 최소 케이스 |
| 33 | 컬럼 1개, `column_key="PRI"` | `...\nTABLE t(c INT PK)` | PK 부착 |
| 34 | 컬럼 1개 + 일치하는 FK 1개 | `...\nTABLE t(c INT -> other.oid)` | FK 부착 |
| 35 | 컬럼 1개(`column_key="PRI"`) + 일치하는 FK 1개 | `...\nTABLE t(c INT PK -> other.oid)` | PK 와 FK 동시. 순서는 PK 먼저 |
| 36 | 컬럼 1개, `is_nullable=True` | `...\nTABLE t(c INT)` | nullable 은 출력에 없다 (규칙 6) |
| 37 | 테이블 2개를 `b`, `a` 순서로 넘김 | `b` 줄이 `a` 줄보다 먼저 | 알파벳 정렬하지 않는다 (설계결정 6) |
| 38 | `table_type="VIEW"` 인 컬럼 1개만, `include_views=False` | `"# schema: sakila (MySQL 8.4)"` | 뷰만 있으면 헤더만 남는다 |
| 39 | 같은 입력, `include_views=True` | `"# schema: sakila (MySQL 8.4)\nVIEW v(c INT)"` | `KIND` 가 `VIEW` |
| 40 | 같은 `(table, column)` 에 FK 2개를 넣고 호출 | 먼저 넣은 FK 의 참조가 출력됨 | 중복 키 규칙 (규칙 1) |
| 41 | `inspect` 로 `t2s/schema.py` 의 import 목록 | `["t2s.db"]` | `pymysql` 부재 확인. 검증 명령으로도 확인 |

## 검증 명령

PowerShell 에서 저장소 루트에 서서 한 줄씩 실행한다. (`&&` 금지.)

```powershell
docker compose -f docker/docker-compose.yml up -d
```

DB 없이 도는 부분:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_schema.py -v
```
기대 출력: `failed 0`, `error 0`, `skipped 0`.

DB 를 쓰는 부분:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_db.py -v
```
기대 출력: `failed 0`, `error 0`, **`skipped 0`**.

전체 회귀:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```
기대 출력: `73 passed` 보다 큰 수. 001·002·003 의 기존 테스트가 **하나도 깨지지 않아야 한다.** `failed`/`error`/`skipped` 는 0.

**guard 무변경 확인:**
```powershell
git diff --stat t2s/guard.py t2s/config.py
```
기대 출력: **빈 출력.** 한 줄이라도 나오면 FAIL 이다.

**`db.py` 최소 변경 확인:**
```powershell
git diff --stat t2s/db.py
```
기대 출력: `1 file changed` 이고 삽입이 40줄 이내. 100줄이 넘으면 기존 함수를 재작성한 것이므로 범위 이탈이다.

**`schema.py` 무의존성 확인:**
```powershell
.\.venv\Scripts\python.exe -c "import ast; t=ast.parse(open('t2s/schema.py',encoding='utf-8').read()); print(sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}))"
```
기대 출력:
```
['t2s.db']
```
`pymysql`, `os`, `dotenv` 가 보이면 설계결정 4 위반이다.

**렌더 결과 눈으로 확인:**
```powershell
.\.venv\Scripts\python.exe -c "from t2s.config import load_settings; from t2s.db import fetch_schema, fetch_foreign_keys; from t2s.schema import render_schema; s=load_settings(); t=render_schema(fetch_schema(s), fetch_foreign_keys(s)); print(len(t), len(t.splitlines())); print(t)"
```
기대 출력: 첫 줄이 `2549 17`, 이어서 스키마 17줄.

## 하지 말 것

- **`t2s/guard.py` 를 수정하지 마라.** `FK_SQL` 이 `information_schema` 를 읽지만 guard 를 타지 않으므로 애초에 충돌하지 않는다.
- `fetch_schema()` 의 시그니처와 반환 타입을 바꾸지 마라. `ColumnInfo` 필드 추가와 인덱스 보정 외에 손대지 마라.
- `ColumnInfo` 에서 `data_type` 을 지우지 마라 (설계결정 1).
- `fetch_foreign_keys` 에 `sql` 파라미터를 만들지 마라.
- `schema.py` 에서 DB 에 접속하지 마라. `pymysql` 을 import 하지 마라.
- `render_schema` 안에서 테이블·컬럼을 정렬하지 마라.
- 출력에 `NOT NULL` / `NULL` / `unsigned` / 인덱스 정보를 추가하지 마라. 형식은 위 계약이 전부다.
- 출력 마지막에 개행(`\n`)을 붙이지 마라.
- `tests/test_db.py` 의 기존 테스트를 "고쳐서" 통과시키지 마라. `column_type` 추가 한 곳 외에 기대값이 바뀌면 구현이 틀린 것이다.
- `t2s/llm.py`, `t2s/graph.py`, `t2s/cli.py`, `evals/` 를 만들지 마라. 다음 스펙이다.
- `requirements.txt` 에 의존성을 추가하지 마라.
- 커밋하지 마라.

## 체크리스트

- [ ] 범위의 신규 2개 + 수정 2개만 변경했다
- [ ] `git diff --stat t2s/guard.py t2s/config.py` 가 빈 출력이다
- [ ] `ColumnInfo` 필드 순서가 `table_name, table_type, column_name, data_type, column_type, is_nullable, column_key` 다
- [ ] `fetch_schema`, `run_query`, `connect` 의 시그니처가 003 과 동일하다
- [ ] `fetch_foreign_keys` 에 `sql` 파라미터가 없다
- [ ] `t2s/schema.py` 의 import 가 `t2s.db` 하나뿐이다 (검증 명령으로 확인했다)
- [ ] 수용 기준 41행 전부가 테스트로 존재한다
- [ ] `pytest tests/ -q` 가 73개 이상 통과하고 기존 테스트가 하나도 안 깨졌다
- [ ] 검증 명령을 직접 실행했고 실제 출력을 그대로 보고했다 (`2549 17` 포함)
- [ ] 커밋하지 않았다

## 질문

구현 세션이 막혔을 때 여기에 적는다. 아래는 **스펙 작성 시점에 확인된 사항**이다.

1. **`render_schema` 의 출력 길이 2549 는 Sakila 표준 덤프에 묶인 값이다.** `docker compose down -v` 로 DB 를 재적재하면 같은 값이 나오지만, 덤프 버전이 바뀌면 #12·#13 의 기대값이 흔들린다. 지금은 컨테이너가 고정이므로 상수로 박는다.
2. **[보안, 이번 범위 밖] guard 는 컬럼 단위 접근을 막지 않는다.** 스파이크에서 "직원 비밀번호 목록 보여줘" 에 모델이 `SELECT staff_id, first_name, last_name, username, password FROM staff` 를 생성했고, `SELECT` 라서 guard 와 `t2s_ro` 권한을 모두 통과했다. Sakila 는 더미 데이터라 실해가 없지만, **컬럼 차단 목록이 별도 스펙으로 필요하다.** 이 스펙에서 guard 를 고쳐 대응하지 마라.

구현 세션이 추가한 질문:

- [x] (수용 기준 표 #1 → `tests/test_db.py::test_fetch_schema_first_row_is_actor_id`) `actor.actor_id` 의 `column_type` 기대값. 라이브 컨테이너에 직접 쿼리한 실측 결과는 `('int', 'int unsigned')` 이다. **결정(사람): A — 표의 기대값을 실측값 `int unsigned` 로 고쳤다.** 선택지 B(`fetch_schema` 가 `unsigned` 를 잘라 반환)는 004 #6 의 `film.length` → `smallint unsigned` 원문 보존과 모순되므로 기각.
