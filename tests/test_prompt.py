import inspect
from dataclasses import FrozenInstanceError

import pytest

from t2s.prompt import (
    EXTRACTION_KINDS,
    SYSTEM_PROMPT,
    Extraction,
    build_messages,
    extract_sql,
)


# 수용 기준 #1~#21 — extract_sql 실측 응답 + 형태 변형/경계값
# 30
@pytest.mark.parametrize(
    "raw, expected_sql, expected_kind",
    [
        # 1
        (
            "```sql\nSELECT COUNT(*) AS total_films\nFROM film\n```\n\n"
            "**Reason:** `film` 테이블의 전체 행 수를 세는 단순 집계 쿼리입니다.",
            "SELECT COUNT(*) AS total_films\nFROM film",
            "sql",
        ),
        # 2
        (
            '```json\n{\n  "sql": "SELECT a.first_name, a.last_name, '
            'COUNT(fa.film_id) AS film_count FROM actor a JOIN film_actor fa '
            'ON fa.actor_id = a.actor_id GROUP BY a.actor_id LIMIT 5",\n'
            '  "reason": "actor와 film_actor를 조인"\n}\n```',
            "SELECT a.first_name, a.last_name, COUNT(fa.film_id) AS film_count "
            "FROM actor a JOIN film_actor fa ON fa.actor_id = a.actor_id "
            "GROUP BY a.actor_id LIMIT 5",
            "sql",
        ),
        # 3
        (
            'The question asks: "How many R-rated films are there?" in Korean.\n\n'
            "Simple query: SELECT COUNT(*) FROM film WHERE rating = 'R';\n\n"
            "This returns a single aggregate row, so no LIMIT needed per rules "
            '("Always add a LIMIT clause (at most 200) unless the query returns '
            "a single aggregate row\")."
            "SELECT COUNT(*) FROM film WHERE rating = 'R'",
            "SELECT COUNT(*) FROM film WHERE rating = 'R'",
            "sql",
        ),
        # 4
        (
            "The question asks how many rentals are not returned.\n\n"
            "Use return_date IS NULL.</think>SELECT COUNT(*) AS not_returned_rentals\n"
            "FROM rental\nWHERE return_date IS NULL",
            "SELECT COUNT(*) AS not_returned_rentals\nFROM rental\n"
            "WHERE return_date IS NULL",
            "sql",
        ),
        # 5
        (
            '```json\n{\n  "sql": "",\n  "reason": "고객 데이터를 삭제하는 요청은 '
            'DELETE 문이 필요하지만, 이 시스템은 읽기 전용(SELECT)만 허용됩니다."\n}\n```',
            "",
            "unsupported",
        ),
        # 6
        ("```sql\nUNSUPPORTED\n```", "", "unsupported"),
        # 7
        (
            'The user is asking in Korean: "Delete all customer data".\n\n'
            "This is a DELETE request, which is not allowed. According to the "
            "rules, output exactly: UNSUPPORTED.UNSUPPORTED",
            "",
            "unsupported",
        ),
        # 8
        ("죄송합니다, 이 질문에는 답변할 수 없습니다.", "", "unparsable"),
        # 9
        ("```\nSELECT title FROM film ORDER BY title LIMIT 3\n```",
         "SELECT title FROM film ORDER BY title LIMIT 3",
         "sql"),
        # 10
        (
            "```sql\nWITH t AS (SELECT film_id FROM film) "
            "SELECT COUNT(*) FROM t\n```",
            "WITH t AS (SELECT film_id FROM film) SELECT COUNT(*) FROM t",
            "sql",
        ),
        # 11
        (
            "```sql\nSELECT 'UNSUPPORTED' AS note FROM film LIMIT 1\n```",
            "SELECT 'UNSUPPORTED' AS note FROM film LIMIT 1",
            "sql",
        ),
        # 12
        ("```sql\nSELECT COUNT(*) FROM film;\n```",
         "SELECT COUNT(*) FROM film",
         "sql"),
        # 13
        ("```sql\nSELECT COUNT(*) FROM film;;\n```",
         "SELECT COUNT(*) FROM film",
         "sql"),
        # 14
        ("", "", "unparsable"),
        # 15
        ("   \n\n  ", "", "unparsable"),
        # 16
        (
            "Here you go: WITH t AS (SELECT film_id FROM film) "
            "SELECT COUNT(*) FROM t",
            "SELECT COUNT(*) FROM t",
            "sql",
        ),
        # 17
        ("```sql\nDROP TABLE film\n```", "", "unparsable"),
        # 18
        ('```python\nprint("hi")\n```', "", "unparsable"),
        # 19
        ('{"sql": "SELECT 1 LIMIT 1", "reason": "ok"}', "SELECT 1 LIMIT 1", "sql"),
        # 20
        ('{"reason": "no sql key"}', "", "unparsable"),
        # 21
        ("분석...</think>분석2...</think>SELECT 1 LIMIT 1", "SELECT 1 LIMIT 1", "sql"),
    ],
)
def test_extract_sql(raw, expected_sql, expected_kind):
    result = extract_sql(raw)
    assert result == Extraction(sql=expected_sql, kind=expected_kind)
    assert result.kind in EXTRACTION_KINDS


# 22
def test_build_messages_full_list():
    result = build_messages("# schema: sakila (MySQL 8.4)\nTABLE t(c INT)", "영화 몇 편?")
    assert result == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "# schema: sakila (MySQL 8.4)\nTABLE t(c INT)\n\nQuestion: 영화 몇 편?",
        },
    ]


# 23
def test_build_messages_system_content_is_system_prompt_object():
    result = build_messages("S", "Q")
    assert result[0]["content"] is SYSTEM_PROMPT


# 24
def test_build_messages_empty_question():
    result = build_messages("S", "")
    assert result[1]["content"] == "S\n\nQuestion: "


# 25
def test_build_messages_no_strip():
    result = build_messages("  S  ", "  Q  ")
    assert result[1]["content"] == "  S  \n\nQuestion:   Q  "


# 26
def test_build_messages_length_two():
    assert len(build_messages("S", "Q")) == 2


# 27
def test_system_prompt_contains_rules():
    assert "Only SELECT (or WITH ... SELECT)." in SYSTEM_PROMPT
    assert "```sql" in SYSTEM_PROMPT
    assert "UNSUPPORTED" in SYSTEM_PROMPT
    assert "at most 200" in SYSTEM_PROMPT


# 28
def test_system_prompt_starts_with_writer_line():
    assert SYSTEM_PROMPT.startswith(
        "You are a MySQL 8.4 query writer for the `sakila` database."
    )


# 29
def test_extraction_kinds_exact_tuple():
    assert EXTRACTION_KINDS == ("sql", "unsupported", "unparsable")


# 31
def test_extraction_is_frozen():
    obj = Extraction("SELECT 1", "sql")
    with pytest.raises(FrozenInstanceError):
        obj.sql = "x"


# 32
def test_extract_sql_signature_single_parameter():
    assert list(inspect.signature(extract_sql).parameters) == ["text"]


# 33
def test_build_messages_signature_parameters():
    assert list(inspect.signature(build_messages).parameters) == [
        "schema_text",
        "question",
    ]