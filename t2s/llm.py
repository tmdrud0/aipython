import ollama

from t2s.config import Settings
from t2s.prompt import Extraction, build_messages, extract_sql


class LLMError(RuntimeError):
    ...


DEFAULT_TIMEOUT: float = 60.0
TEMPERATURE: float = 0.0


def build_client(settings: Settings, timeout: float = DEFAULT_TIMEOUT) -> ollama.Client:
    return ollama.Client(host=settings.ollama_host, timeout=timeout)


def generate_sql(
    schema_text: str,
    question: str,
    settings: Settings,
    client: ollama.Client | None = None,
) -> Extraction:
    if client is None:
        client = build_client(settings)

    messages = build_messages(schema_text, question)

    try:
        resp = client.chat(
            model=settings.ollama_model,
            messages=messages,
            options={"temperature": TEMPERATURE},
        )
    except ConnectionError as exc:
        raise LLMError(f"cannot reach ollama at {settings.ollama_host}") from exc
    except ollama.ResponseError as exc:
        raise LLMError(f"ollama error: {exc}") from exc
    except ollama.RequestError as exc:
        raise LLMError(f"ollama error: {exc}") from exc

    try:
        message = resp["message"]
        content = message["content"]
    except (KeyError, TypeError):
        content = ""
    if not isinstance(content, str):
        content = ""

    return extract_sql(content)