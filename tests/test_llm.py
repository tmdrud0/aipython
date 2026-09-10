import inspect

import ollama
import pytest

from t2s.config import ConfigError, Settings, load_settings
from t2s.llm import (
    DEFAULT_TIMEOUT,
    LLMError,
    TEMPERATURE,
    build_client,
    generate_sql,
)
from t2s.prompt import SYSTEM_PROMPT, Extraction, build_messages


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


FAKE_SETTINGS = Settings(
    db_host="127.0.0.1", db_port=3310, db_user="u", db_password="p",
    db_name="sakila", ollama_host="http://fake:11434", ollama_model="fake-model",
)

SCHEMA = "# schema: sakila (MySQL 8.4)\nTABLE film(film_id INT PK, title VARCHAR(255))"


# 수용 기준 #1~#7 — 정상 경로와 호출 인자 검증
def test_generate_sql_normal_path_and_call_arguments():
    fake = FakeClient(response={"message": {"content": "```sql\nSELECT 1 LIMIT 1\n```"}})
    result = generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    # 1
    assert result == Extraction(sql="SELECT 1 LIMIT 1", kind="sql")
    # 2
    assert len(fake.calls) == 1
    # 3
    assert set(fake.calls[0]) == {"model", "messages", "options"}
    # 4
    assert fake.calls[0]["model"] == "fake-model"
    # 5
    assert fake.calls[0]["options"] == {"temperature": 0.0}
    # 6
    assert fake.calls[0]["messages"] == build_messages(SCHEMA, "질문")
    # 7
    assert fake.calls[0]["messages"][0]["content"] == SYSTEM_PROMPT


# 수용 기준 #8~#12 — 응답 형태별
@pytest.mark.parametrize(
    "content, expected",
    [
        # 8
        (
            '```json\n{"sql": "SELECT 1 LIMIT 1", "reason": "ok"}\n```',
            Extraction("SELECT 1 LIMIT 1", "sql"),
        ),
        # 9
        (
            "분석...</think>SELECT COUNT(*) FROM film",
            Extraction("SELECT COUNT(*) FROM film", "sql"),
        ),
        # 10
        ("```sql\nUNSUPPORTED\n```", Extraction("", "unsupported")),
        # 11
        ("죄송합니다.", Extraction("", "unparsable")),
        # 12
        ("", Extraction("", "unparsable")),
    ],
)
def test_generate_sql_response_shapes(content, expected):
    fake = FakeClient(response={"message": {"content": content}})
    result = generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert result == expected


# 수용 기준 #13~#15 — 비정상 응답. 예외를 던지지 않는다 (설계결정 7)
@pytest.mark.parametrize(
    "response, expected",
    [
        # 13
        ({"message": {}}, Extraction("", "unparsable")),
        # 14
        ({}, Extraction("", "unparsable")),
        # 15
        ({"message": {"content": 123}}, Extraction("", "unparsable")),
    ],
)
def test_generate_sql_malformed_responses(response, expected):
    fake = FakeClient(response=response)
    result = generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert result == expected


# 수용 기준 #16 — 내장 ConnectionError 매핑. 완전 일치
def test_generate_sql_connection_error_becomes_llm_error_exact_message():
    fake = FakeClient(error=ConnectionError("boom"))
    with pytest.raises(LLMError) as exc:
        generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert str(exc.value) == "cannot reach ollama at http://fake:11434"
    assert "boom" not in str(exc.value)


# 수용 기준 #17 — ResponseError 매핑
def test_generate_sql_response_error_becomes_llm_error():
    fake = FakeClient(error=ollama.ResponseError("model 'x' not found (status code: 404)"))
    with pytest.raises(LLMError) as exc:
        generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert str(exc.value).startswith("ollama error: ")


# 수용 기준 #18 — RequestError 매핑
def test_generate_sql_request_error_becomes_llm_error():
    fake = FakeClient(error=ollama.RequestError("bad request"))
    with pytest.raises(LLMError) as exc:
        generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert str(exc.value).startswith("ollama error: ")


# 수용 기준 #19 — __cause__ 가 원본 예외
def test_generate_sql_llm_error_has_cause():
    fake = FakeClient(error=ConnectionError("boom"))
    with pytest.raises(LLMError) as exc:
        generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert isinstance(exc.value.__cause__, ConnectionError)


# 수용 기준 #20 — 그 외 예외는 그대로 통과. except Exception: 아님
def test_generate_sql_unexpected_error_passes_through():
    fake = FakeClient(error=ValueError("unexpected"))
    with pytest.raises(ValueError) as exc:
        generate_sql(SCHEMA, "질문", FAKE_SETTINGS, client=fake)
    assert type(exc.value) is ValueError
    assert not isinstance(exc.value, LLMError)


# 수용 기준 #21
def test_generate_sql_signature_no_timeout():
    assert list(inspect.signature(generate_sql).parameters) == [
        "schema_text",
        "question",
        "settings",
        "client",
    ]


# 수용 기준 #22
def test_build_client_signature():
    assert list(inspect.signature(build_client).parameters) == ["settings", "timeout"]


# 수용 기준 #23
def test_build_client_returns_client_without_network():
    result = build_client(FAKE_SETTINGS)
    assert isinstance(result, ollama.Client)


# 수용 기준 #24
def test_constants():
    assert DEFAULT_TIMEOUT == 60.0
    assert TEMPERATURE == 0.0


# 수용 기준 #25
def test_llm_error_is_runtime_error():
    assert issubclass(LLMError, RuntimeError)


# 수용 기준 #26 — 라이브 스모크 (유일한 실제 모델 호출)
def test_generate_sql_live_smoke():
    try:
        settings = load_settings()
    except ConfigError:
        pytest.skip(".env 없음")
    try:
        result = generate_sql(SCHEMA, "영화가 총 몇 편이야?", settings)
    except LLMError:
        pytest.skip("ollama 미기동 또는 네트워크 없음")
    assert result.kind == "sql"
    assert result.sql.upper().startswith("SELECT")