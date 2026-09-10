import pytest

from t2s.guard import UnsafeSQLError, ensure_safe_sql


@pytest.mark.parametrize(
    "sql, expected",
    [
        # 1
        ("SELECT * FROM film", "SELECT * FROM film LIMIT 200"),
        # 2
        ("SELECT * FROM film LIMIT 5", "SELECT * FROM film LIMIT 5"),
        # 3
        ("SELECT * FROM film limit 5", "SELECT * FROM film limit 5"),
        # 4
        ("select title from film", "select title from film LIMIT 200"),
        # 5
        ("  SELECT   1  ", "SELECT 1 LIMIT 200"),
        # 6
        ("SELECT\n1", "SELECT 1 LIMIT 200"),
        # 7
        ("SELECT 1;", "SELECT 1 LIMIT 200"),
        # 8
        ("SELECT 1 ;  ", "SELECT 1 LIMIT 200"),
        # 11
        (
            "WITH t AS (SELECT 1) SELECT * FROM t",
            "WITH t AS (SELECT 1) SELECT * FROM t LIMIT 200",
        ),
        # 12
        ("SELECT * FROM film -- 코멘트", "SELECT * FROM film LIMIT 200"),
        # 13
        ("SELECT * FROM film # 코멘트", "SELECT * FROM film LIMIT 200"),
        # 14
        ("SELECT /* hi */ 1", "SELECT 1 LIMIT 200"),
        # 15
        ("SELECT 1 -- ; DROP TABLE film", "SELECT 1 LIMIT 200"),
        # 16
        ("SELECT 1--2", "SELECT 1--2 LIMIT 200"),
        # 21
        ("SELECT 'DROP TABLE film' AS x", "SELECT 'DROP TABLE film' AS x LIMIT 200"),
        # 22
        (
            "SELECT title FROM film WHERE title = 'it''s'",
            "SELECT title FROM film WHERE title = 'it''s' LIMIT 200",
        ),
        # 23
        (r"SELECT 'a\'b' AS x", r"SELECT 'a\'b' AS x LIMIT 200"),
        # 24
        ("SELECT `drop` FROM film", "SELECT `drop` FROM film LIMIT 200"),
    ],
)
def test_pass_cases(sql: str, expected: str) -> None:
    assert ensure_safe_sql(sql) == expected


@pytest.mark.parametrize(
    "sql, message",
    [
        # 9
        ("SELECT 1;;", "multiple statements are not allowed"),
        # 10
        ("SELECT 1; DROP TABLE film", "multiple statements are not allowed"),
        # 17
        ("SELECT /*! DROP TABLE film */ 1", "executable comment is not allowed"),
        # 18
        ("SELECT /* 안 닫힘", "unterminated block comment"),
        # 19
        ("SELECT 'abc", "unterminated string literal"),
        # 20
        ("SELECT `abc", "unterminated identifier"),
        # 25
        ("DROP TABLE film", "only SELECT is allowed, got: DROP"),
        # 26
        ("SET @a = 1", "only SELECT is allowed, got: SET"),
        # 27
        ("SELECT * FROM film FOR UPDATE", "forbidden keyword: UPDATE"),
        # 28
        ("SELECT * FROM film INTO OUTFILE '/tmp/x'", "forbidden keyword: OUTFILE"),
        # 29
        ("SELECT * FROM mysql.user", "system schema access is not allowed: mysql"),
        # 30
        (
            "SELECT * FROM information_schema.tables",
            "system schema access is not allowed: information_schema",
        ),
        # 31
        ("", "empty SQL"),
        ("   ", "empty SQL"),
        ("-- 주석뿐", "empty SQL"),
    ],
)
def test_fail_cases(sql: str, message: str) -> None:
    with pytest.raises(UnsafeSQLError) as exc:
        ensure_safe_sql(sql)
    assert str(exc.value) == message


# 32
def test_max_rows_argument() -> None:
    assert ensure_safe_sql("SELECT 1", max_rows=10) == "SELECT 1 LIMIT 10"


# 33
def test_max_rows_zero_is_plain_valueerror() -> None:
    with pytest.raises(ValueError) as exc:
        ensure_safe_sql("SELECT 1", max_rows=0)
    assert type(exc.value) is ValueError
    assert str(exc.value) == "max_rows must be >= 1, got: 0"


# 34
def test_max_rows_bool_rejected() -> None:
    with pytest.raises(ValueError) as exc:
        ensure_safe_sql("SELECT 1", max_rows=True)
    assert type(exc.value) is ValueError
    assert str(exc.value) == "max_rows must be >= 1, got: True"


# 35
def test_sql_not_str() -> None:
    with pytest.raises(TypeError) as exc:
        ensure_safe_sql(123)
    assert str(exc.value) == "sql must be str, got: int"


# 36
def test_pure_function_same_input_same_output() -> None:
    first = ensure_safe_sql("SELECT * FROM film")
    second = ensure_safe_sql("SELECT * FROM film")
    assert first == second