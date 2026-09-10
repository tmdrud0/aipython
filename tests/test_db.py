import inspect

import pytest

from t2s.config import ConfigError, Settings, load_settings
from t2s.db import ColumnInfo, QueryError, QueryResult, connect, fetch_schema, run_query
from t2s.guard import UnsafeSQLError


@pytest.fixture(scope="module")
def settings():
    try:
        return load_settings()
    except ConfigError:
        pytest.skip(".env 없음")


# 1
def test_run_query_count_film_full_result(settings):
    result = run_query("SELECT COUNT(*) FROM film", settings)
    assert result.columns == ("COUNT(*)",)
    assert result.rows == ((1000,),)
    assert result.sql == "SELECT COUNT(*) FROM film LIMIT 200"


# 2
def test_run_query_alias_becomes_column_name(settings):
    result = run_query("SELECT COUNT(*) AS n FROM film", settings)
    assert result.columns == ("n",)


# 3
def test_run_query_existing_limit_preserved(settings):
    result = run_query("SELECT title FROM film ORDER BY title LIMIT 3", settings)
    assert result.rows == (
        ("ACADEMY DINOSAUR",),
        ("ACE GOLDFINGER",),
        ("ADAPTATION HOLES",),
    )
    assert result.sql == "SELECT title FROM film ORDER BY title LIMIT 3"


# 4
def test_run_query_double_defense_limits_rows(settings):
    result = run_query("SELECT * FROM film LIMIT 1000", settings)
    assert len(result.rows) == 200


# 5
def test_run_query_max_rows_argument(settings):
    result = run_query("SELECT * FROM film LIMIT 1000", settings, max_rows=7)
    assert len(result.rows) == 7


# 6
def test_run_query_frozen_dataclass_equality(settings):
    first = run_query("SELECT COUNT(*) FROM film", settings)
    second = run_query("SELECT COUNT(*) FROM film", settings)
    assert first == second


# 7
def test_run_query_drop_table_raises_unsafe_sql_error(settings):
    with pytest.raises(UnsafeSQLError) as exc:
        run_query("DROP TABLE film", settings)
    assert str(exc.value) == "only SELECT is allowed, got: DROP"
    assert type(exc.value) is not QueryError


# 8
def test_run_query_information_schema_still_blocked(settings):
    with pytest.raises(UnsafeSQLError) as exc:
        run_query("SELECT * FROM information_schema.TABLES", settings)
    assert str(exc.value) == "system schema access is not allowed: information_schema"


# 9
def test_run_query_multiple_statements_rejected(settings):
    with pytest.raises(UnsafeSQLError) as exc:
        run_query("SELECT 1; DROP TABLE film", settings)
    assert str(exc.value) == "multiple statements are not allowed"


# 10
def test_run_query_missing_table_query_error(settings):
    with pytest.raises(QueryError) as exc:
        run_query("SELECT * FROM nope", settings)
    assert str(exc.value).startswith("query failed [1146]: ")


# 11
def test_run_query_syntax_error_query_error(settings):
    with pytest.raises(QueryError) as exc:
        run_query("SELECT FROM", settings)
    assert str(exc.value).startswith("query failed [1064]: ")


# 12
def test_connect_wrong_port_query_error():
    bad_settings = Settings(
        db_host="127.0.0.1",
        db_port=1,
        db_user="t2s_ro",
        db_password="t2s_ro_pw",
        db_name="sakila",
        ollama_host="localhost:11434",
        ollama_model="llama3",
    )
    with pytest.raises(QueryError) as exc:
        connect(bad_settings)
    assert str(exc.value).startswith("cannot connect to 127.0.0.1:1: ")


# 13
def test_fetch_schema_total_column_count(settings):
    assert len(fetch_schema(settings)) == 131


# 14
def test_fetch_schema_table_count(settings):
    assert len({c.table_name for c in fetch_schema(settings)}) == 23


# 15
def test_fetch_schema_base_table_and_view_counts(settings):
    result = fetch_schema(settings)
    assert len({c.table_name for c in result if c.table_type == "BASE TABLE"}) == 16
    assert len({c.table_name for c in result if c.table_type == "VIEW"}) == 7


# 16
def test_fetch_schema_first_row_is_actor_id(settings):
    expected = ColumnInfo(
        table_name="actor",
        table_type="BASE TABLE",
        column_name="actor_id",
        data_type="int",
        is_nullable=False,
        column_key="PRI",
    )
    assert fetch_schema(settings)[0] == expected


# 17
def test_fetch_schema_film_rating_enum_nullable_yes(settings):
    match = [
        c
        for c in fetch_schema(settings)
        if c.table_name == "film" and c.column_name == "rating"
    ]
    assert len(match) == 1
    assert match[0].data_type == "enum"
    assert match[0].is_nullable is True
    assert match[0].column_key == ""


# 18
def test_fetch_schema_film_title_varchar_not_nullable_mul(settings):
    match = [
        c
        for c in fetch_schema(settings)
        if c.table_name == "film" and c.column_name == "title"
    ]
    assert len(match) == 1
    assert match[0].data_type == "varchar"
    assert match[0].is_nullable is False
    assert match[0].column_key == "MUL"


# 19
def test_fetch_schema_film_column_count(settings):
    result = fetch_schema(settings)
    assert len([c for c in result if c.table_name == "film"]) == 13


# 20
def test_fetch_schema_returns_tuple_of_column_info(settings):
    result = fetch_schema(settings)
    assert isinstance(result, tuple)
    assert all(isinstance(c, ColumnInfo) for c in result)


# 21
def test_connect_returns_open_connection_closeable(settings):
    connection = connect(settings)
    assert connection.open is True
    connection.close()
    assert connection.open is False


# 22
def test_fetch_schema_signature_has_no_sql_parameter():
    assert list(inspect.signature(fetch_schema).parameters) == ["settings"]


# 23
def test_run_query_signature_no_bypass_parameters():
    assert list(inspect.signature(run_query).parameters) == ["sql", "settings", "max_rows"]