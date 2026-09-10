# 009: 질문 → 답변 그래프 (`t2s/graph.py`)

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "그래프". 001~006 의 부품(생성·guard·실행)을 하나의 흐름으로 묶는다. 다음은 010 `cli.py` 다.
- 선행 스펙: `001`~`008` (전부 커밋 완료, 227 passed)
- 예상 분량: 파일 2개(신규 2 / 수정 0), 약 260줄

## 목표

질문 하나를 받아 **SQL 생성 → 실행(guard 포함) → 결과**까지 돌리고, 그 결과를 LangGraph 를 모르는 호출자도 쓸 수 있는 `Answer` 하나로 돌려준다.
생성기와 실행기를 주입받게 해서, 그래프 배선 전체를 LLM·DB 없이 테스트한다.

## 배경 (이 스펙의 근거)

**1. 재시도 루프를 넣지 않는 근거는 측정이다.** 007·008 평가에서 관측된 모델 실패는 전부 **문법상 유효한데 의미가 틀린 SQL** 이었다 (묻지 않은 컬럼 덧붙이기, 반조인 실수, 질문 오독). 모든 실행을 통틀어 `db_error`·`guard_block`·`unparsable` 은 **0건**이다. "에러가 나면 다시 생성" 하는 자기수정 루프는 관측된 실패를 **하나도** 고치지 못한다 — 에러가 나지 않기 때문이다. 그래서 그래프는 **선형**이다.

**2. LangGraph API 를 실측했다** (`langgraph==1.2.11`, 이미 `requirements.txt` 에 있다).

| 확인 | 결과 |
|---|---|
| import | `from langgraph.graph import StateGraph, START, END` 동작 |
| `compile()` 반환 타입 | `langgraph.graph.state.CompiledStateGraph` |
| `invoke()` 반환 | 입력 키 + 노드가 돌려준 키가 합쳐진 `dict` |
| 조건부 간선 | `add_conditional_edges(노드, 라우터, {반환값: 다음노드})` 동작, `END` 를 매핑 값으로 쓸 수 있다 |
| 상태에 frozen dataclass | 문제없이 담긴다 (`Extraction`, `QueryResult`) |
| 노드 안의 예외 | **감싸지지 않고 원래 타입 그대로** `invoke()` 밖으로 올라온다 |

**3. 참조 구현으로 아래 계약을 전부 돌려 봤다.** 수용 기준의 기대값은 그 실측값이다. 라이브에서도 `"영화가 총 몇 편이야?"` → `answered`, 행 `((1000,),)` / `"고객 데이터 전부 삭제해줘."` → `unsupported`, 실행기 호출 없음을 확인했다.

**4. 왜 LangGraph 인가.** 지금 흐름은 함수 두 개를 순서대로 부르는 것과 같다. 그래도 LangGraph 로 짜는 이유는 (a) 001 부터 의존성으로 박혀 있고 계획이 `graph.py` 였으며, (b) 나중에 붙일 단계(모호한 질문 되묻기, 결과 요약 등)가 **노드와 간선 추가**로 끝나기 때문이다. **그 단계들은 지금 만들지 않는다.**

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| `t2s/graph.py` | `STATUSES`, `AgentState`, `Answer`, `build_graph()`, `ask()` |
| `tests/test_graph.py` | 가짜 생성기·실행기로 실제 그래프를 돌리는 테스트 + 라이브 스모크 1개 |

**수정**
| 파일 | 무엇을 |
|---|---|
| 없음 | — |

**건드리지 말 것**
- **`t2s/` 의 기존 7개 모듈 — 한 글자도 고치지 마라.** `config.py`, `guard.py`, `db.py`, `schema.py`, `prompt.py`, `llm.py`, `evaluate.py`. 특히 `SYSTEM_PROMPT` 와 `guard.py` 를 손대지 마라.
- **`evals/` 전체** — `golden.jsonl`, `run_eval.py`. 러너를 그래프로 갈아타게 하지 마라 (설계결정 9).
- `t2s/__init__.py`, `evals/__init__.py` — 0 바이트 유지.
- `tests/` 의 기존 7개 파일.
- `docker/`, `.env`, `.env.example`, `.gitignore`, `requirements.txt`, `docs/`, `readme.md`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `t2s/llm.py` `generate_sql(schema_text, question, settings, client=None) -> Extraction`, `LLMError` | 생성 노드의 기본 생성기. 다시 만들지 마라. |
| `t2s/db.py` `run_query(sql, settings, max_rows=MAX_ROWS) -> QueryResult`, `QueryError`, `QueryResult` | 실행 노드의 기본 실행기. **`run_query` 가 내부에서 `ensure_safe_sql` 을 부른다** (003 계약 1번). 그래서 그래프는 guard 를 따로 부르지 않는다 (설계결정 3). |
| `t2s/guard.py` `UnsafeSQLError` | 실행기가 던지는 것을 잡는 데만 쓴다. `ensure_safe_sql` 을 import 하지 마라. |
| `t2s/prompt.py` `Extraction` | 상태에 담는 생성 결과. `kind` 는 `"sql"` / `"unsupported"` / `"unparsable"`. |
| `t2s/config.py` `Settings` | 그래프에 한 번 넘겨 노드들이 공유한다. `load_settings()` 를 `graph.py` 안에서 부르지 마라. |
| `evals/run_eval.py` `run_trial()` | 같은 3단 흐름(생성 → 실행 → 예외 3종)의 참고 대상. 판정 의미가 같아야 한다. **import 하지는 마라.** |

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **선형이다. 재시도·자기수정 루프를 넣지 마라.** 배경 1의 측정이 근거다. 생성기와 실행기는 질문당 **최대 한 번씩** 불린다.
2. **노드는 두 개다: `generate`, `execute`.** 흐름은 `START → generate → (조건부) → execute → END` 또는 `generate → END`. 노드를 더 만들지 마라.
3. **그래프는 guard 를 직접 부르지 않는다.** `run_query` 가 부른다. 006 스펙 설계결정 5의 "guard 는 상위 계층(graph)이 부른다" 는 **"그래프가 guard 가 붙은 실행 경로(`run_query`)를 탄다"** 는 뜻으로 읽는다. `ensure_safe_sql` 을 `graph.py` 에 import 하지 마라 — 두 번 검사하게 된다.
4. **생성기·실행기를 주입받는다.** `build_graph(..., generate=generate_sql, execute=run_query)`. 기본값이 실제 함수이고, 테스트는 가짜를 넣어 **실제 LangGraph 를 그대로** 돌린다. 이것이 006 의 클라이언트 주입과 같은 이유다.
5. **스키마 텍스트는 그래프 밖에서 한 번 만든다.** `build_graph` 의 인자로 받는다. 그래프 안에서 `fetch_schema()`·`render_schema()` 를 부르지 마라 — 질문마다 DB 를 두 번 더 때린다.
6. **바깥에는 `Answer` 만 내보낸다.** `ask()` 는 LangGraph 상태 `dict` 를 돌려주지 않는다. 010 `cli.py` 가 `langgraph` 를 몰라도 되게 한다.
7. **상태는 6개로 고정한다** (`STATUSES`). 새 값을 만들지 마라.
8. **잡는 예외는 노드마다 정해져 있다.** `generate` 는 `LLMError` 만, `execute` 는 `UnsafeSQLError`·`QueryError` 만 잡는다. 그 외 예외는 **그대로 올라가게 둔다** (배경 2의 실측대로 LangGraph 가 감싸지 않는다). `except Exception:` 금지.
9. **`evals/run_eval.py` 를 그래프로 바꾸지 마라.** 평가 러너는 판정(`classify`)에 필요한 원시 값(`kind`, 정규화 행, 실패 단계)을 직접 다룬다. 둘을 합치는 것은 이번 범위 밖이다.
10. **LangGraph 의 부가 기능을 쓰지 마라.** checkpointer, 메모리, `stream`, `interrupt`, 서브그래프, `Send` 를 쓰지 마라. `compile()` 에 인자를 넘기지 마라.

## 파일별 계약

### `t2s/graph.py`

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from t2s.config import Settings
from t2s.db import QueryError, QueryResult, run_query
from t2s.guard import UnsafeSQLError
from t2s.llm import LLMError, generate_sql
from t2s.prompt import Extraction


STATUSES: tuple[str, ...] = (
    "answered",
    "unsupported",
    "unparsable",
    "blocked",
    "db_error",
    "llm_error",
)


class AgentState(TypedDict, total=False):
    question: str
    extraction: Extraction
    result: QueryResult
    status: str
    error: str


@dataclass(frozen=True)
class Answer:
    question: str
    status: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    error: str


def build_graph(
    settings: Settings,
    schema_text: str,
    generate: Callable[[str, str, Settings], Extraction] = generate_sql,
    execute: Callable[[str, Settings], QueryResult] = run_query,
) -> CompiledStateGraph:
    ...


def ask(question: str, graph: CompiledStateGraph) -> Answer:
    ...
```

import 는 위 목록이 전부다. `ensure_safe_sql`, `load_settings`, `fetch_schema`, `render_schema`, `ollama`, `pymysql` 을 import 하지 마라.

`STATUSES` 의 뜻:

| 값 | 뜻 |
|---|---|
| `"answered"` | 실행까지 성공 |
| `"unsupported"` | 모델이 명시적으로 거부 (`Extraction.kind == "unsupported"`) |
| `"unparsable"` | 모델 응답에서 SQL 을 못 찾음 (`Extraction.kind == "unparsable"`) |
| `"blocked"` | 실행기가 `UnsafeSQLError` — guard 가 막음 |
| `"db_error"` | 실행기가 `QueryError` |
| `"llm_error"` | 생성기가 `LLMError` |

---

#### `build_graph(settings, schema_text, generate=generate_sql, execute=run_query) -> CompiledStateGraph`

`build_graph` 안에 노드 함수 두 개와 라우터 하나를 **클로저로** 정의한다 (`settings`, `schema_text`, `generate`, `execute` 를 캡처하기 위해서). 모듈 전역 변수에 담지 마라.

**`generate` 노드** — `(state: AgentState) -> dict`

1. `extraction = generate(schema_text, state["question"], settings)` — **위치 인자 3개**로 부른다.
2. `LLMError` 가 나면 `{"status": "llm_error", "error": str(exc)}` 를 반환한다.
3. `extraction.kind != "sql"` 이면 `{"extraction": extraction, "status": extraction.kind}` 를 반환한다. (`"unsupported"` 또는 `"unparsable"` 이 그대로 상태가 된다.)
4. 그 외에는 `{"extraction": extraction}` 을 반환한다. **`status` 를 넣지 마라** — 라우터가 이것으로 실행 여부를 가른다.

**라우터** — `(state: AgentState) -> str`

1. `"status" in state` 이면 `END` 를 반환한다.
2. 아니면 `"execute"` 를 반환한다.

**`execute` 노드** — `(state: AgentState) -> dict`

1. `result = execute(state["extraction"].sql, settings)` — **위치 인자 2개**로 부른다. `max_rows` 를 넘기지 마라 (기본값 200 을 쓴다).
2. `UnsafeSQLError` → `{"status": "blocked", "error": str(exc)}`
3. `QueryError` → `{"status": "db_error", "error": str(exc)}`
4. 성공 → `{"result": result, "status": "answered"}`

**그래프 조립** — 이 순서로:

1. `builder = StateGraph(AgentState)`
2. `builder.add_node("generate", <generate 노드>)`
3. `builder.add_node("execute", <execute 노드>)`
4. `builder.add_edge(START, "generate")`
5. `builder.add_conditional_edges("generate", <라우터>, {"execute": "execute", END: END})`
6. `builder.add_edge("execute", END)`
7. `builder.compile()` 의 결과를 반환한다. **인자를 넘기지 마라** (설계결정 10).

이 함수는 LLM·DB 를 부르지 않는다. 그래프를 만들기만 한다.

---

#### `ask(question, graph) -> Answer`

1. `state = graph.invoke({"question": question})`
2. `extraction = state.get("extraction")`, `result = state.get("result")`
3. `Answer` 를 아래 규칙으로 만들어 반환한다:

   | 필드 | 값 |
   |---|---|
   | `question` | 인자 `question` 그대로 |
   | `status` | `state["status"]` |
   | `sql` | `result` 가 있으면 `result.sql` (guard 가 정규화한, 실제로 실행된 SQL). 없고 `extraction` 이 있으면 `extraction.sql` (모델이 만든 원문). 둘 다 없으면 `""` |
   | `columns` | `result` 가 있으면 `result.columns`, 없으면 `()` |
   | `rows` | `result` 가 있으면 `result.rows`, 없으면 `()`. **값을 문자열로 바꾸지 마라** (`Decimal` 등 원래 타입 유지 — 정규화는 평가 쪽의 일이다) |
   | `error` | `state.get("error", "")` |

4. `invoke` 에서 올라온 예외는 잡지 마라.
5. 로깅·print 를 하지 마라.

### `tests/test_graph.py`

규칙:

1. 아래 수용 기준의 모든 행을 테스트로 옮긴다.
2. **가짜 생성기·실행기를 아래 형태로 정확히 만든다.** `unittest.mock` 을 쓰지 마라.
   ```python
   class FakeGenerate:
       def __init__(self, result=None, error=None):
           self.result = result
           self.error = error
           self.calls = []

       def __call__(self, schema_text, question, settings):
           self.calls.append((schema_text, question, settings))
           if self.error is not None:
               raise self.error
           return self.result


   class FakeExecute:
       def __init__(self, result=None, error=None):
           self.result = result
           self.error = error
           self.calls = []

       def __call__(self, sql, settings):
           self.calls.append((sql, settings))
           if self.error is not None:
               raise self.error
           return self.result
   ```
   - 두 가짜 모두 **위치 인자만** 받는다. 그래프가 키워드 인자로 부르면 `TypeError` 로 즉시 드러난다 (계약의 "위치 인자 N개" 강제).
3. 공용 상수는 이 값으로 고정한다:
   ```python
   FAKE_SETTINGS = Settings(
       db_host="h", db_port=1, db_user="u", db_password="p", db_name="sakila",
       ollama_host="http://fake:11434", ollama_model="fake",
   )
   SCHEMA = "# schema: sakila (MySQL 8.4)\nTABLE film(film_id INT PK)"
   QR = QueryResult(columns=("n",), rows=((1000,),), sql="SELECT COUNT(*) AS n FROM film LIMIT 200")
   ```
4. **가짜 테스트는 LLM·DB 에 접근하지 마라.** `load_settings`, `pymysql`, `ollama` 를 부르지 마라. LangGraph 는 로컬 라이브러리이므로 **진짜로 돈다** — 이것이 이 테스트의 목적이다.
5. `Answer` 비교는 **dataclass 전체를 `==`** 로 한다.
6. **라이브 스모크(#20)는 하나만 만든다.** 테스트 이름에 `live` 를 넣는다.
   - `load_settings()` 에서 `ConfigError` → `pytest.skip(".env 없음")`
   - `fetch_schema()` / `fetch_foreign_keys()` 에서 `QueryError` → `pytest.skip("DB 미기동")`
   - 그 외 예외는 잡지 마라.
   - `ask()` 결과의 `status` 가 `"llm_error"` 면 `pytest.skip("ollama 미기동 또는 네트워크 없음")`.
   - **구현 세션은 이 테스트가 skip 되지 않은 상태로 한 번은 돌려 실제 결과를 보고해야 한다.**

## 수용 기준

기대값은 참조 구현 실측값이다.

**상태별 결과 (가짜 생성기·실행기, 실제 LangGraph)**

| # | 생성기 / 실행기 | 기대 `ask("질문", graph)` | 비고 |
|---|---|---|---|
| 1 | `FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))` / `FakeExecute(QR)` | `Answer("질문", "answered", "SELECT COUNT(*) AS n FROM film LIMIT 200", ("n",), ((1000,),), "")` | `sql` 은 **실행된 SQL**(`QR.sql`)이지 모델 원문이 아니다 |
| 2 | `FakeGenerate(Extraction("", "unsupported"))` / `FakeExecute(QR)` | `Answer("질문", "unsupported", "", (), (), "")` | |
| 3 | `FakeGenerate(Extraction("", "unparsable"))` / `FakeExecute(QR)` | `Answer("질문", "unparsable", "", (), (), "")` | |
| 4 | `FakeGenerate(error=LLMError("cannot reach ollama at http://fake:11434"))` / `FakeExecute(QR)` | `Answer("질문", "llm_error", "", (), (), "cannot reach ollama at http://fake:11434")` | |
| 5 | `FakeGenerate(Extraction("SELECT * FROM film FOR UPDATE", "sql"))` / `FakeExecute(error=UnsafeSQLError("forbidden keyword: UPDATE"))` | `Answer("질문", "blocked", "SELECT * FROM film FOR UPDATE", (), (), "forbidden keyword: UPDATE")` | `sql` 은 **모델 원문** (실행 결과가 없으므로) |
| 6 | `FakeGenerate(Extraction("SELECT * FROM nope", "sql"))` / `FakeExecute(error=QueryError("query failed [1146]: Table 'sakila.nope' doesn't exist"))` | `Answer("질문", "db_error", "SELECT * FROM nope", (), (), "query failed [1146]: Table 'sakila.nope' doesn't exist")` | |

**호출 횟수와 인자 — 재시도 없음·실행 생략 확인**

| # | 상황 | 기대 | 비고 |
|---|---|---|---|
| 7 | #1 후 `gen.calls` | `[(SCHEMA, "질문", FAKE_SETTINGS)]` | 스키마·질문·설정이 그대로 전달 |
| 8 | #1 후 `exe.calls` | `[("SELECT COUNT(*) AS n FROM film", FAKE_SETTINGS)]` | 실행기에는 **모델 원문**이 간다 (정규화는 `run_query` 안에서) |
| 9 | #2, #3, #4 후 `exe.calls` | 셋 다 `[]` | **SQL 이 없으면 실행기를 부르지 않는다** |
| 10 | #5, #6 후 `gen.calls`, `exe.calls` 길이 | 둘 다 `1` | **실행 실패 후 재생성·재실행하지 않는다** (설계결정 1) |

**예외 전파**

| # | 생성기 / 실행기 | 기대 | 비고 |
|---|---|---|---|
| 11 | `FakeGenerate(error=ValueError("unexpected"))` / `FakeExecute(QR)` | `ask` 가 `ValueError` 를 던진다. `type(exc.value) is ValueError`. `exe.calls == []` | `except Exception:` 을 쓰지 않았음을 단언 |
| 12 | `FakeGenerate(Extraction("SELECT 1", "sql"))` / `FakeExecute(error=TypeError("bad"))` | `ask` 가 `TypeError` 를 던진다 | 실행 노드도 3종 외 예외는 통과 |

**재사용·구조**

| # | 입력 | 기대 | 비고 |
|---|---|---|---|
| 13 | 같은 그래프로 `ask("첫 질문", g)` (생성기가 sql) 후, 생성기의 `result` 를 `Extraction("", "unsupported")` 로 바꿔 `ask("둘째 질문", g)` | 첫째 `status == "answered"`, 둘째는 `Answer("둘째 질문", "unsupported", "", (), (), "")` | **호출 사이에 상태가 새지 않는다** (둘째의 `columns`/`rows` 가 비어 있어야 한다) |
| 14 | `build_graph(FAKE_SETTINGS, SCHEMA, generate=g, execute=e)` 만 호출 | `g.calls == []`, `e.calls == []` | 그래프를 만들기만 하고 부르지 않는다 |
| 15 | `build_graph(...)` 의 반환 타입 | `isinstance(result, CompiledStateGraph)` | `langgraph.graph.state` 에서 import 해 확인 |
| 16 | `STATUSES` | `("answered", "unsupported", "unparsable", "blocked", "db_error", "llm_error")` | 순서까지 일치 |
| 17 | #1~#6 의 모든 `Answer.status` | `in STATUSES` | |
| 18 | `Answer("q","answered","",(),(),"")` 에 `obj.status = "x"` 대입 | `dataclasses.FrozenInstanceError` | |
| 19 | `inspect.signature(build_graph).parameters` 키 목록 | `["settings", "schema_text", "generate", "execute"]` | 기본값이 `generate_sql`, `run_query` 인지도 확인 (`param.default is generate_sql`) |

**라이브 스모크**

| # | 입력 | 기대 | 비고 |
|---|---|---|---|
| 20 | 실제 설정 + `render_schema(fetch_schema(s), fetch_foreign_keys(s))` 로 만든 그래프에 `"영화가 총 몇 편이야?"` | `status == "answered"` 이고 `rows == ((1000,),)` | 유일한 라이브 테스트. `columns` 이름은 단언하지 마라 (모델마다 별칭이 다르다) |

## 검증 명령

PowerShell 에서 저장소 루트에 서서 한 줄씩 실행한다. (`&&` 금지.)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_graph.py -v
```
기대 출력: `failed 0`, `error 0`. `skipped` 는 **최대 1개**(라이브 #20)까지.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```
기대 출력: `227 passed` 보다 큰 수, `failed 0`.

**라이브 스모크 통과 증거 (필수):**
```powershell
docker compose -f docker/docker-compose.yml up -d
```
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_graph.py -v -k live
```
기대 출력: `PASSED`. **`SKIPPED` 면 통과가 아니다.**

**end-to-end 수동 확인 (필수, 실제 출력을 그대로 보고할 것):**
```powershell
.\.venv\Scripts\python.exe -c "from t2s.config import load_settings; from t2s.db import fetch_schema, fetch_foreign_keys; from t2s.schema import render_schema; from t2s.graph import build_graph, ask; s=load_settings(); g=build_graph(s, render_schema(fetch_schema(s), fetch_foreign_keys(s))); print(ask('영화가 총 몇 편이야?', g)); print(ask('고객 데이터 전부 삭제해줘.', g))"
```
기대 출력 (스펙 작성 시점 실측):
```
Answer(question='영화가 총 몇 편이야?', status='answered', sql='SELECT COUNT(*) AS film_count FROM film LIMIT 200', columns=('film_count',), rows=((1000,),), error='')
Answer(question='고객 데이터 전부 삭제해줘.', status='unsupported', sql='', columns=(), rows=(), error='')
```
별칭(`film_count`)은 실행마다 다를 수 있다. `status` 와 `rows` 가 같으면 된다.

**import 확인:**
```powershell
.\.venv\Scripts\python.exe -c "import ast; t=ast.parse(open('t2s/graph.py',encoding='utf-8').read()); print(sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}))"
```
기대 출력:
```
['collections.abc', 'dataclasses', 'langgraph.graph', 'langgraph.graph.state', 't2s.config', 't2s.db', 't2s.guard', 't2s.llm', 't2s.prompt', 'typing']
```
**`ensure_safe_sql` 이 import 되지 않았는지**도 따로 확인한다:
```powershell
Select-String -Path t2s/graph.py -Pattern "ensure_safe_sql|load_settings|fetch_schema|render_schema"
```
기대 출력: **빈 출력.** (설계결정 3·5)

**기존 파일 무변경 확인:**
```powershell
git diff --stat -- t2s evals tests
```
기대 출력: **빈 출력** (신규 `t2s/graph.py`, `tests/test_graph.py` 는 untracked 라 여기 안 잡힌다).

```powershell
.\.venv\Scripts\python.exe -c "import hashlib; L=[l.rstrip('\r\n') for l in open('evals/golden.jsonl',encoding='utf-8') if l.strip()]; print(len(L), hashlib.sha256('\n'.join(L).encode('utf-8')).hexdigest())"
```
기대 출력:
```
60 ca70b4dc4809d9478c8a6c13ebc14f94f56fcba03baa0cd770273fd9b719c1a3
```

## 하지 말 것

- **재시도·자기수정 루프를 넣지 마라.** 실행이 실패해도 다시 생성하지 마라 (설계결정 1).
- `generate`, `execute` 외 노드를 만들지 마라. 되묻기·요약·설명 노드는 범위 밖이다.
- `ensure_safe_sql` 을 import 하거나 부르지 마라. `run_query` 가 부른다 (설계결정 3).
- 그래프 안에서 스키마를 조회하지 마라 (설계결정 5).
- `ask()` 가 LangGraph 상태 `dict` 를 돌려주게 하지 마라. `Answer` 만이다.
- `Answer.rows` 의 값을 문자열로 바꾸지 마라.
- `STATUSES` 에 값을 추가하지 마라.
- `except Exception:` 을 쓰지 마라.
- 노드 함수를 모듈 전역에 두고 전역 변수로 `settings` 를 넘기지 마라. 클로저로 캡처한다.
- checkpointer·메모리·스트리밍·interrupt·서브그래프를 쓰지 마라. `compile()` 에 인자를 넘기지 마라.
- `evals/run_eval.py` 를 그래프 기반으로 바꾸지 마라 (설계결정 9).
- `unittest.mock` 을 쓰지 마라. 스펙이 지정한 가짜를 쓴다.
- 라이브 테스트를 2개 이상 만들지 마라. skip 된 채로 보고하지 마라.
- `t2s/cli.py` 를 만들지 마라. 다음 스펙이다.
- `requirements.txt` 에 의존성을 추가하지 마라 (`langgraph` 는 이미 있다).
- 커밋하지 마라.

## 체크리스트

- [ ] 범위의 신규 2개만 만들었다 (수정 파일 0개)
- [ ] `git diff --stat -- t2s evals tests` 가 빈 출력이다
- [ ] 골든셋 해시가 `ca70b4dc…c1a3` 이고 60행이다
- [ ] `graph.py` 의 import 가 계약 목록과 정확히 같고, `ensure_safe_sql`·`load_settings`·`fetch_schema`·`render_schema` 가 없다
- [ ] `STATUSES`, `AgentState`, `Answer`, `build_graph`, `ask` 의 시그니처와 필드 순서를 글자 그대로 따랐다
- [ ] 노드는 `generate`, `execute` 두 개이고, 라우터는 `"status" in state` 로 가른다
- [ ] 생성기는 위치 인자 3개, 실행기는 위치 인자 2개로 부른다
- [ ] 수용 기준 20행 전부가 테스트로 존재한다
- [ ] `pytest tests/test_graph.py -v -k live` 가 `PASSED` 다 (SKIPPED 아님)
- [ ] end-to-end 수동 확인을 돌렸고 실제 출력 두 줄을 그대로 보고했다
- [ ] `pytest tests/ -q` 가 227개보다 많이 통과하고 `failed 0` 이다
- [ ] 커밋하지 않았다

## 질문

구현 세션이 막혔을 때 여기에 적는다. 아래는 **스펙 작성 시점에 확인된 사항**이다.

1. **`blocked` 상태는 현재 모델로는 거의 안 나온다.** 평가 전 구간에서 guard 차단이 0건이었다. 그래도 guard 는 모델을 믿지 않기 위한 장치이므로 경로와 테스트(#5)는 반드시 둔다.
2. **`db_error` 도 거의 안 나온다.** 다만 펜스 없는 CTE 가 잘리는 알려진 한계(005 질문 1)는 이 경로로 드러난다 (`query failed [1146]`).
3. **[이번 범위 밖] 컬럼 단위 접근 제어가 없다** (`staff.password`, `customer.email`). 그래프에 필터 노드를 끼워 넣어 대응하지 마라 — 차단 정책은 guard 쪽 별도 스펙이다.
4. **`sh-01`, `sh-04`(묻지 않은 컬럼 덧붙이기)는 그래프로 고치지 않는다.** 프롬프트 개선 사이클의 일이다.
