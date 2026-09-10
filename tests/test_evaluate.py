import inspect
import json
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from t2s.evaluate import (
    ROWS_PREVIEW_LIMIT,
    SQL_PREVIEW_LIMIT,
    GoldenItem,
    OUTCOMES,
    Summary,
    classify,
    compact_sql,
    describe_failure,
    format_rows,
    load_golden,
    normalize_rows,
    summarize,
)


ITEM_SQL = GoldenItem("x", "q", "sql", (("1000",),), None)
ITEM_REFUSE = GoldenItem("y", "q", "unsupported", None, None)


# 수용 기준 #1~#7 — normalize_rows
# 1
def test_normalize_rows_int_becomes_str():
    assert normalize_rows(((1000,),)) == (("1000",),)


# 2
def test_normalize_rows_decimal_becomes_str():
    assert normalize_rows(((Decimal("5314.21"),),)) == (("5314.21",),)


# 3
def test_normalize_rows_sorts_rows():
    assert normalize_rows(((2, "b"), (1, "a"))) == (("1", "a"), ("2", "b"))


# 4
def test_normalize_rows_empty_input():
    assert normalize_rows(()) == ()


# 5
def test_normalize_rows_none_cell_becomes_str_none():
    assert normalize_rows(((None,),)) == (("None",),)


# 6
def test_normalize_rows_keeps_duplicate_rows():
    assert normalize_rows(((1,), (1,))) == (("1",), ("1",))


# 7
def test_normalize_rows_returns_tuple_of_tuples():
    result = normalize_rows(((1,),))
    assert isinstance(result, tuple)
    assert all(isinstance(row, tuple) for row in result)


# 수용 기준 #8~#15 — classify, expect_kind == "sql"
@pytest.mark.parametrize(
    "got_kind, got_rows, failure, expected",
    [
        # 8
        ("sql", (("1000",),), None, "pass"),
        # 9
        ("sql", (("999",),), None, "wrong_rows"),
        # 10
        ("sql", (("1000", "extra"),), None, "wrong_rows"),
        # 11
        ("unsupported", None, None, "no_sql"),
        # 12
        ("unparsable", None, None, "no_sql"),
        # 13
        ("sql", None, "guard", "guard_block"),
        # 14
        ("sql", None, "db", "db_error"),
        # 15
        (None, None, "llm", "llm_error"),
    ],
)
def test_classify_expect_sql(got_kind, got_rows, failure, expected):
    result = classify(ITEM_SQL, got_kind, got_rows, failure)
    # 30
    assert result in OUTCOMES
    assert result == expected


# 수용 기준 #16~#20 — classify, expect_kind == "unsupported"
@pytest.mark.parametrize(
    "got_kind, got_rows, failure, expected",
    [
        # 16
        ("unsupported", None, None, "pass"),
        # 17
        ("sql", None, "guard", "guard_saved"),
        # 18
        ("sql", (("1",),), None, "wrong_refusal"),
        # 19
        ("unparsable", None, None, "wrong_refusal"),
        # 20
        (None, None, "llm", "llm_error"),
    ],
)
def test_classify_expect_unsupported(got_kind, got_rows, failure, expected):
    result = classify(ITEM_REFUSE, got_kind, got_rows, failure)
    assert result in OUTCOMES
    assert result == expected


# 수용 기준 #21 — 유일하게 실제 골든셋을 읽는 테스트
def test_load_golden_real_file():
    result = load_golden("evals/golden.jsonl")
    assert isinstance(result, tuple)
    assert len(result) == 60


# 22
def test_load_golden_real_file_unsupported_count():
    result = load_golden("evals/golden.jsonl")
    assert len([item for item in result if item.expect_kind == "unsupported"]) == 10


# 23
def test_load_golden_real_file_first_item():
    result = load_golden("evals/golden.jsonl")
    assert result[0].id == "t1-01"
    assert result[0].expect_kind == "sql"
    assert result[0].expect_rows == (("1000",),)


# 24
def test_load_golden_real_file_two_row_item():
    result = load_golden("evals/golden.jsonl")
    item = [i for i in result if i.id == "t3-03"][0]
    assert item.expect_rows == (("1", "7923"), ("2", "8121"))


# 25
def test_load_golden_real_file_expect_rows_are_tuples():
    result = load_golden("evals/golden.jsonl")
    for item in result:
        if item.expect_rows is None:
            continue
        assert isinstance(item.expect_rows, tuple)
        assert all(isinstance(row, tuple) for row in item.expect_rows)


# 26
def test_load_golden_skips_blank_lines(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text(
        '{"id": "a", "question": "q1", "expect_kind": "sql", '
        '"expect_rows": [["1"]], "reference_sql": null}\n'
        "\n"
        '{"id": "b", "question": "q2", "expect_kind": "unsupported", '
        '"expect_rows": null, "reference_sql": null}\n',
        encoding="utf-8",
    )
    result = load_golden(path)
    assert len(result) == 2


# 27
def test_load_golden_reads_korean_utf8(tmp_path):
    path = tmp_path / "golden.jsonl"
    question = "영화가 총 몇 편이야?"
    path.write_text(
        json.dumps(
            {
                "id": "k",
                "question": question,
                "expect_kind": "sql",
                "expect_rows": [["1000"]],
                "reference_sql": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    result = load_golden(path)
    assert result[0].question == question


# 28
def test_load_golden_missing_path_raises():
    with pytest.raises(FileNotFoundError):
        load_golden("no-such-dir/no-such-file.jsonl")


# 수용 기준 #29
def test_outcomes_exact_tuple():
    assert OUTCOMES == (
        "pass",
        "wrong_rows",
        "no_sql",
        "guard_block",
        "db_error",
        "llm_error",
        "wrong_refusal",
        "guard_saved",
    )


# 수용 기준 #31
def test_classify_signature():
    assert list(inspect.signature(classify).parameters) == [
        "item",
        "got_kind",
        "got_rows",
        "failure",
    ]


# 수용 기준 #32
def test_golden_item_is_frozen():
    item = GoldenItem("a", "b", "sql", None, None)
    with pytest.raises(FrozenInstanceError):
        item.id = "x"


# === 008 추가분 ===

GOLDEN = load_golden("evals/golden.jsonl")
ITEM = GoldenItem("x", "q", "sql", (("1000",),), None)


# 수용 기준 #3
def test_load_golden_real_file_ids_unique():
    ids = [item.id for item in GOLDEN]
    assert len(set(ids)) == 60


# 수용 기준 #4
def test_load_golden_real_file_sql_items_have_rows_and_reference():
    for item in GOLDEN:
        if item.expect_kind != "sql":
            continue
        assert item.expect_rows is not None
        assert item.reference_sql is not None
        assert item.reference_sql != ""


# 수용 기준 #5
def test_load_golden_real_file_unsupported_items_have_no_answer():
    for item in GOLDEN:
        if item.expect_kind != "unsupported":
            continue
        assert item.expect_rows is None
        assert item.reference_sql is None


# 수용 기준 #6
def test_load_golden_real_file_expect_kind_is_two_values_only():
    for item in GOLDEN:
        assert item.expect_kind in ("sql", "unsupported")


# 수용 기준 #7
def test_compact_sql_collapses_whitespace():
    assert compact_sql("SELECT a\nFROM t\n  WHERE x = 1") == "SELECT a FROM t WHERE x = 1"


# 수용 기준 #8
def test_compact_sql_empty():
    assert compact_sql("") == ""


# 수용 기준 #9
def test_compact_sql_truncates():
    result = compact_sql("A" * 250)
    assert len(result) == 203
    assert result == "A" * 200 + "..."


# 수용 기준 #10
def test_compact_sql_exactly_limit_no_ellipsis():
    assert compact_sql("B" * 200) == "B" * 200


# 수용 기준 #11
def test_compact_sql_limit_argument():
    assert compact_sql("SELECT * FROM film", limit=10) == "SELECT * F..."


# 수용 기준 #12
def test_format_rows_none():
    assert format_rows(None) == "None"


# 수용 기준 #13
def test_format_rows_empty():
    assert format_rows(()) == "0행 []"


# 수용 기준 #14
def test_format_rows_single_row_no_quotes():
    assert format_rows((("India", "60"),)) == "1행 [(India, 60)]"


# 수용 기준 #15
def test_format_rows_exactly_limit():
    assert format_rows((("1", "a"), ("2", "b"), ("3", "c"))) == "3행 [(1, a), (2, b), (3, c)]"


# 수용 기준 #16
def test_format_rows_over_limit():
    rows = (("1",), ("2",), ("3",), ("4",))
    assert format_rows(rows) == "4행 [(1), (2), (3), ...]"


# 수용 기준 #17
def test_format_rows_limit_argument():
    assert format_rows((("1",), ("2",)), limit=1) == "2행 [(1), ...]"


# 수용 기준 #18
def test_describe_failure_pass():
    assert describe_failure("pass", ITEM, "sql", (("1000",),), "SELECT 1", "") == ""


# 수용 기준 #19
def test_describe_failure_wrong_rows():
    got = (("India", "60"),)
    result = describe_failure(
        "wrong_rows", ITEM, "sql", got, "SELECT c.country,\n  COUNT(*) FROM city", ""
    )
    assert result == "expect=1행 [(1000)] got=1행 [(India, 60)] | sql=SELECT c.country, COUNT(*) FROM city"


# 수용 기준 #20
def test_describe_failure_llm_error():
    result = describe_failure(
        "llm_error", ITEM, None, None, "", "cannot reach ollama at http://x:11434"
    )
    assert result == "cannot reach ollama at http://x:11434"


# 수용 기준 #21
def test_describe_failure_guard_block():
    result = describe_failure(
        "guard_block", ITEM, "sql", None, "SELECT 1\nFOR UPDATE", "forbidden keyword: UPDATE"
    )
    assert result == "forbidden keyword: UPDATE | sql=SELECT 1 FOR UPDATE"


# 수용 기준 #22
def test_describe_failure_db_error():
    result = describe_failure(
        "db_error",
        ITEM,
        "sql",
        None,
        "SELECT * FROM nope",
        "query failed [1146]: Table 'sakila.nope' doesn't exist",
    )
    assert result == (
        "query failed [1146]: Table 'sakila.nope' doesn't exist | sql=SELECT * FROM nope"
    )


# 수용 기준 #23
def test_describe_failure_no_sql():
    result = describe_failure("no_sql", ITEM, "unsupported", None, "", "")
    assert result == "kind=unsupported"


# 수용 기준 #24
def test_describe_failure_wrong_refusal_with_sql():
    result = describe_failure(
        "wrong_refusal", ITEM, "sql", (("a@b",),), "SELECT email\nFROM customer", ""
    )
    assert result == "sql=SELECT email FROM customer"


# 수용 기준 #25
def test_describe_failure_wrong_refusal_without_sql():
    result = describe_failure("wrong_refusal", ITEM, "unparsable", None, "", "")
    assert result == "kind=unparsable"


# 수용 기준 #26
def test_describe_failure_guard_saved():
    result = describe_failure(
        "guard_saved",
        ITEM,
        "sql",
        None,
        "SELECT * FROM mysql.user",
        "system schema access is not allowed: mysql",
    )
    assert result == "system schema access is not allowed: mysql | sql=SELECT * FROM mysql.user"


# 수용 기준 #27
def test_summarize_empty():
    assert summarize(()) == Summary(0, 0, 0, 0, (), ())


# 수용 기준 #28
def test_summarize_mixed():
    results = (
        ("a", ("pass", "pass")),
        ("b", ("pass", "wrong_rows")),
        ("c", ("db_error", "wrong_rows")),
    )
    assert summarize(results) == Summary(
        items=3,
        trials=6,
        passed_trials=3,
        stable_items=1,
        outcome_counts=(("pass", 3), ("wrong_rows", 2), ("db_error", 1)),
        unstable=(("b", 1, 2), ("c", 0, 2)),
    )


# 수용 기준 #29
def test_summarize_tie_follows_outcomes_order():
    results = (("a", ("db_error",)), ("b", ("wrong_rows",)))
    summary = summarize(results)
    assert summary.outcome_counts == (("wrong_rows", 1), ("db_error", 1))


# 수용 기준 #30
def test_summarize_unstable_keeps_input_order():
    results = (("a", ("db_error",)), ("b", ("wrong_rows",)))
    assert summarize(results).unstable == (("a", 0, 1), ("b", 0, 1))


# 수용 기준 #31
def test_summarize_all_pass():
    assert summarize((("a", ("pass",)), ("b", ("pass",)),)) == Summary(
        2, 2, 2, 2, (("pass", 2),), ()
    )


# 수용 기준 #32
def test_summarize_unstable_not_sorted_by_id():
    results = (("z", ("wrong_rows",)), ("a", ("pass", "wrong_rows")))
    assert summarize(results).unstable == (("z", 0, 1), ("a", 1, 2))


# 수용 기준 #33
def test_summary_is_frozen():
    summary = Summary(0, 0, 0, 0, (), ())
    with pytest.raises(FrozenInstanceError):
        summary.items = 1


# 수용 기준 #34
def test_preview_limits():
    assert SQL_PREVIEW_LIMIT == 200
    assert ROWS_PREVIEW_LIMIT == 3