import inspect
from dataclasses import FrozenInstanceError

import pytest
from langgraph.graph.state import CompiledStateGraph

from t2s.config import ConfigError, Settings, load_settings
from t2s.db import QueryError, QueryResult, fetch_foreign_keys, fetch_schema, run_query
from t2s.graph import STATUSES, Answer, build_graph, ask
from t2s.guard import UnsafeSQLError
from t2s.llm import LLMError, generate_sql
from t2s.prompt import Extraction
from t2s.schema import render_schema


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


FAKE_SETTINGS = Settings(
    db_host="h", db_port=1, db_user="u", db_password="p", db_name="sakila",
    ollama_host="http://fake:11434", ollama_model="fake",
)
SCHEMA = "# schema: sakila (MySQL 8.4)\nTABLE film(film_id INT PK)"
QR = QueryResult(columns=("n",), rows=((1000,),), sql="SELECT COUNT(*) AS n FROM film LIMIT 200")


def _graph(generate, execute):
    return build_graph(FAKE_SETTINGS, SCHEMA, generate=generate, execute=execute)


# 수용 기준 #1~#6 — 상태별 결과 (가짜 생성기·실행기, 실제 LangGraph)
def test_ask_answered_sql_is_executed_sql():
    # 1
    gen = FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))
    exe = FakeExecute(QR)
    result = ask("질문", _graph(gen, exe))
    assert result == Answer(
        "질문", "answered", "SELECT COUNT(*) AS n FROM film LIMIT 200", ("n",), ((1000,),), ""
    )


def test_ask_unsupported():
    # 2
    gen = FakeGenerate(Extraction("", "unsupported"))
    result = ask("질문", _graph(gen, FakeExecute(QR)))
    assert result == Answer("질문", "unsupported", "", (), (), "")


def test_ask_unparsable():
    # 3
    gen = FakeGenerate(Extraction("", "unparsable"))
    result = ask("질문", _graph(gen, FakeExecute(QR)))
    assert result == Answer("질문", "unparsable", "", (), (), "")


def test_ask_llm_error():
    # 4
    gen = FakeGenerate(error=LLMError("cannot reach ollama at http://fake:11434"))
    result = ask("질문", _graph(gen, FakeExecute(QR)))
    assert result == Answer(
        "질문", "llm_error", "", (), (), "cannot reach ollama at http://fake:11434"
    )


def test_ask_blocked():
    # 5
    gen = FakeGenerate(Extraction("SELECT * FROM film FOR UPDATE", "sql"))
    exe = FakeExecute(error=UnsafeSQLError("forbidden keyword: UPDATE"))
    result = ask("질문", _graph(gen, exe))
    assert result == Answer(
        "질문", "blocked", "SELECT * FROM film FOR UPDATE", (), (), "forbidden keyword: UPDATE"
    )


def test_ask_db_error():
    # 6
    gen = FakeGenerate(Extraction("SELECT * FROM nope", "sql"))
    exe = FakeExecute(error=QueryError("query failed [1146]: Table 'sakila.nope' doesn't exist"))
    result = ask("질문", _graph(gen, exe))
    assert result == Answer(
        "질문",
        "db_error",
        "SELECT * FROM nope",
        (),
        (),
        "query failed [1146]: Table 'sakila.nope' doesn't exist",
    )


# 수용 기준 #7~#10 — 호출 횟수와 인자
def test_generate_receives_schema_question_settings():
    # 7
    gen = FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))
    exe = FakeExecute(QR)
    ask("질문", _graph(gen, exe))
    assert gen.calls == [(SCHEMA, "질문", FAKE_SETTINGS)]


def test_execute_receives_model_raw_sql():
    # 8
    gen = FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))
    exe = FakeExecute(QR)
    ask("질문", _graph(gen, exe))
    assert exe.calls == [("SELECT COUNT(*) AS n FROM film", FAKE_SETTINGS)]


@pytest.mark.parametrize(
    "gen",
    [
        # 9
        FakeGenerate(Extraction("", "unsupported")),
        FakeGenerate(Extraction("", "unparsable")),
        FakeGenerate(error=LLMError("cannot reach ollama at http://fake:11434")),
    ],
)
def test_no_execute_without_sql(gen):
    exe = FakeExecute(QR)
    ask("질문", _graph(gen, exe))
    assert exe.calls == []


@pytest.mark.parametrize(
    "gen, exe",
    [
        # 10
        (
            FakeGenerate(Extraction("SELECT * FROM film FOR UPDATE", "sql")),
            FakeExecute(error=UnsafeSQLError("forbidden keyword: UPDATE")),
        ),
        (
            FakeGenerate(Extraction("SELECT * FROM nope", "sql")),
            FakeExecute(error=QueryError("query failed [1146]: Table 'sakila.nope' doesn't exist")),
        ),
    ],
)
def test_no_retry_after_execution_failure(gen, exe):
    ask("질문", _graph(gen, exe))
    assert len(gen.calls) == 1
    assert len(exe.calls) == 1


# 수용 기준 #11~#12 — 예외 전파
def test_generate_valueerror_propagates():
    gen = FakeGenerate(error=ValueError("unexpected"))
    exe = FakeExecute(QR)
    with pytest.raises(ValueError) as exc:
        ask("질문", _graph(gen, exe))
    assert type(exc.value) is ValueError
    assert exe.calls == []


def test_execute_typeerror_propagates():
    gen = FakeGenerate(Extraction("SELECT 1", "sql"))
    exe = FakeExecute(error=TypeError("bad"))
    with pytest.raises(TypeError):
        ask("질문", _graph(gen, exe))


# 수용 기준 #13~#19 — 재사용·구조
def test_state_does_not_leak_between_calls():
    gen = FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))
    exe = FakeExecute(QR)
    graph = _graph(gen, exe)
    first = ask("첫 질문", graph)
    assert first.status == "answered"
    gen.result = Extraction("", "unsupported")
    second = ask("둘째 질문", graph)
    assert second == Answer("둘째 질문", "unsupported", "", (), (), "")


def test_build_graph_does_not_call():
    gen = FakeGenerate(Extraction("SELECT 1", "sql"))
    exe = FakeExecute(QR)
    _graph(gen, exe)
    assert gen.calls == []
    assert exe.calls == []


def test_build_graph_returns_compiled_state_graph():
    result = _graph(FakeGenerate(Extraction("SELECT 1", "sql")), FakeExecute(QR))
    assert isinstance(result, CompiledStateGraph)


def test_statuses_exact_tuple():
    assert STATUSES == (
        "answered",
        "unsupported",
        "unparsable",
        "blocked",
        "db_error",
        "llm_error",
    )


def test_all_statuses_are_in_STATUSES():
    cases = (
        (FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql")), FakeExecute(QR)),
        (FakeGenerate(Extraction("", "unsupported")), FakeExecute(QR)),
        (FakeGenerate(Extraction("", "unparsable")), FakeExecute(QR)),
        (FakeGenerate(error=LLMError("boom")), FakeExecute(QR)),
        (FakeGenerate(Extraction("SELECT * FROM film FOR UPDATE", "sql")),
         FakeExecute(error=UnsafeSQLError("forbidden keyword: UPDATE"))),
        (FakeGenerate(Extraction("SELECT * FROM nope", "sql")),
         FakeExecute(error=QueryError("query failed [1146]: Table 'sakila.nope' doesn't exist"))),
    )
    for gen, exe in cases:
        answer = ask("질문", _graph(gen, exe))
        assert answer.status in STATUSES


def test_answer_is_frozen():
    answer = Answer("q", "answered", "", (), (), "")
    with pytest.raises(FrozenInstanceError):
        answer.status = "x"


def test_build_graph_signature_and_defaults():
    params = inspect.signature(build_graph).parameters
    assert list(params) == ["settings", "schema_text", "generate", "execute"]
    assert params["generate"].default is generate_sql
    assert params["execute"].default is run_query


# 수용 기준 #20 — 라이브 스모크 (유일한 실제 LLM·DB 호출)
def test_ask_live_smoke():
    try:
        settings = load_settings()
    except ConfigError:
        pytest.skip(".env 없음")
    try:
        schema_text = render_schema(fetch_schema(settings), fetch_foreign_keys(settings))
    except QueryError:
        pytest.skip("DB 미기동")
    graph = build_graph(settings, schema_text)
    answer = ask("영화가 총 몇 편이야?", graph)
    if answer.status == "llm_error":
        pytest.skip("ollama 미기동 또는 네트워크 없음")
    assert answer.status == "answered"
    assert answer.rows == ((1000,),)