import inspect
import json
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from t2s.evaluate import GoldenItem, OUTCOMES, classify, load_golden, normalize_rows


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
    assert len(result) == 27


# 22
def test_load_golden_real_file_unsupported_count():
    result = load_golden("evals/golden.jsonl")
    assert len([item for item in result if item.expect_kind == "unsupported"]) == 3


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