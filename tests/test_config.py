import pymysql
import pytest

from t2s.config import ConfigError, REQUIRED_KEYS, Settings, load_settings

VALID_ENV = {
    "T2S_DB_HOST": "127.0.0.1",
    "T2S_DB_PORT": "3310",
    "T2S_DB_USER": "t2s_ro",
    "T2S_DB_PASSWORD": "t2s_ro_pw",
    "T2S_DB_NAME": "sakila",
    "T2S_OLLAMA_HOST": "http://127.0.0.1:11434",
    "T2S_OLLAMA_MODEL": "glm-5.3-flash:cloud",
}


def _set_env(monkeypatch, **overrides):
    for key in REQUIRED_KEYS:
        monkeypatch.delenv(key, raising=False)
    values = dict(VALID_ENV)
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_valid_env_returns_settings(monkeypatch, tmp_path):
    _set_env(monkeypatch)

    settings = load_settings(env_path=str(tmp_path / "absent.env"))

    assert settings == Settings(
        db_host="127.0.0.1",
        db_port=3310,
        db_user="t2s_ro",
        db_password="t2s_ro_pw",
        db_name="sakila",
        ollama_host="http://127.0.0.1:11434",
        ollama_model="glm-5.3-flash:cloud",
    )
    assert isinstance(settings.db_port, int)


def test_values_are_stripped(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_HOST="  127.0.0.1  ")

    settings = load_settings(env_path=str(tmp_path / "absent.env"))

    assert settings.db_host == "127.0.0.1"


def test_missing_single_key_raises(monkeypatch, tmp_path):
    _set_env(monkeypatch)
    monkeypatch.delenv("T2S_DB_USER")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_path=str(tmp_path / "absent.env"))

    assert str(exc_info.value) == "missing required env keys: T2S_DB_USER"


def test_missing_multiple_keys_in_declaration_order(monkeypatch, tmp_path):
    _set_env(monkeypatch)
    monkeypatch.delenv("T2S_DB_USER")
    monkeypatch.delenv("T2S_DB_NAME")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_path=str(tmp_path / "absent.env"))

    assert str(exc_info.value) == (
        "missing required env keys: T2S_DB_USER, T2S_DB_NAME"
    )


def test_whitespace_only_password_raises(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_PASSWORD="   ")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_path=str(tmp_path / "absent.env"))

    assert str(exc_info.value) == "missing required env keys: T2S_DB_PASSWORD"


def test_non_integer_port_raises(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_PORT="abc")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_path=str(tmp_path / "absent.env"))

    assert str(exc_info.value) == (
        "T2S_DB_PORT must be an integer in 1..65535, got: abc"
    )


def test_port_zero_raises(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_PORT="0")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_path=str(tmp_path / "absent.env"))

    assert str(exc_info.value) == (
        "T2S_DB_PORT must be an integer in 1..65535, got: 0"
    )


def test_port_65536_raises(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_PORT="65536")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_path=str(tmp_path / "absent.env"))

    assert str(exc_info.value) == (
        "T2S_DB_PORT must be an integer in 1..65535, got: 65536"
    )


def test_port_one_is_valid(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_PORT="1")

    settings = load_settings(env_path=str(tmp_path / "absent.env"))

    assert settings.db_port == 1


def test_port_65535_is_valid(monkeypatch, tmp_path):
    _set_env(monkeypatch, T2S_DB_PORT="65535")

    settings = load_settings(env_path=str(tmp_path / "absent.env"))

    assert settings.db_port == 65535


def test_absent_env_file_with_env_vars_ok(monkeypatch, tmp_path):
    _set_env(monkeypatch)

    settings = load_settings(env_path=str(tmp_path / "absent.env"))

    assert settings.db_port == 3310


def test_sakila_connection_film_count():
    try:
        settings = load_settings()
    except ConfigError:
        pytest.skip(".env 없음")

    try:
        connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            connect_timeout=3,
        )
    except pymysql.err.OperationalError:
        pytest.skip("DB 미기동")

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM film")
            count = cursor.fetchone()[0]
    finally:
        connection.close()

    assert count == 1000