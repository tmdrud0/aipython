import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    ...


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    ollama_host: str
    ollama_model: str


REQUIRED_KEYS: tuple[str, ...] = (
    "T2S_DB_HOST",
    "T2S_DB_PORT",
    "T2S_DB_USER",
    "T2S_DB_PASSWORD",
    "T2S_DB_NAME",
    "T2S_OLLAMA_HOST",
    "T2S_OLLAMA_MODEL",
)


def load_settings(env_path: str | None = None) -> Settings:
    if env_path is None:
        env_path = str(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(dotenv_path=env_path, override=False)

    values = {key: os.environ.get(key, "").strip() for key in REQUIRED_KEYS}

    missing = [key for key in REQUIRED_KEYS if values[key] == ""]
    if missing:
        raise ConfigError(f"missing required env keys: {', '.join(missing)}")

    raw = values["T2S_DB_PORT"]
    try:
        port = int(raw)
    except ValueError:
        raise ConfigError(f"T2S_DB_PORT must be an integer in 1..65535, got: {raw}")
    if not 1 <= port <= 65535:
        raise ConfigError(f"T2S_DB_PORT must be an integer in 1..65535, got: {raw}")

    return Settings(
        db_host=values["T2S_DB_HOST"],
        db_port=port,
        db_user=values["T2S_DB_USER"],
        db_password=values["T2S_DB_PASSWORD"],
        db_name=values["T2S_DB_NAME"],
        ollama_host=values["T2S_OLLAMA_HOST"],
        ollama_model=values["T2S_OLLAMA_MODEL"],
    )