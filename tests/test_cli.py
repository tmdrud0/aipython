from decimal import Decimal

import pytest

from t2s.cli import (
    BANNER,
    COLUMN_GAP,
    EXIT_WORDS,
    MAX_CELL_WIDTH,
    MAX_DISPLAY_ROWS,
    PROMPT,
    clean_input,
    display_width,
    format_cell,
    is_exit,
    parse_args,
    render_answer,
    render_table,
    run_once,
    run_repl,
    truncate,
)
from t2s.config import Settings
from t2s.db import QueryResult
from t2s.graph import STATUSES, Answer, build_graph
from t2s.llm import LLMError
from t2s.prompt import Extraction


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


class FakeRead:
    def __init__(self, lines, end=EOFError):
        self.lines = list(lines)
        self.end = end
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.lines:
            return self.lines.pop(0)
        raise self.end()


FAKE_SETTINGS = Settings(
    db_host="h", db_port=1, db_user="u", db_password="p", db_name="sakila",
    ollama_host="http://fake:11434", ollama_model="fake",
)
SCHEMA = "# schema: sakila (MySQL 8.4)\nTABLE film(film_id INT PK)"
QR = QueryResult(columns=("n",), rows=((1000,),), sql="SELECT COUNT(*) AS n FROM film LIMIT 200")


def _graph(generate, execute):
    return build_graph(FAKE_SETTINGS, SCHEMA, generate=generate, execute=execute)


# 수용 기준 #1 — display_width
@pytest.mark.parametrize(
    "text, expected",
    [
        ("abc", 3),
        ("영화", 4),
        ("a영b", 4),
        ("", 0),
        ("...", 3),
    ],
)
def test_display_width(text, expected):
    assert display_width(text) == expected


# 수용 기준 #2~#6 — truncate
def test_truncate_long_ascii():
    assert truncate("x" * 50) == "x" * 37 + "..."


def test_truncate_exactly_limit():
    assert truncate("y" * 40) == "y" * 40


def test_truncate_korean():
    result = truncate("가" * 30)
    assert result == "가" * 18 + "..."
    assert display_width(result) == 39


def test_truncate_short():
    assert truncate("short") == "short"


def test_truncate_limit_argument():
    assert truncate("abcdefghij", limit=8) == "abcde..."


# 수용 기준 #7~#14 — format_cell
@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "NULL"),
        (b"\x89PNG\r\n", "<6 bytes>"),
        (1000, "1000"),
        ("a\n  b", "a b"),
        ("", ""),
        (Decimal("5314.21"), "5314.21"),
        ("x" * 50, "x" * 37 + "..."),
    ],
)
def test_format_cell(value, expected):
    assert format_cell(value) == expected


# 수용 기준 #13 — datetime 은 str() 경로
def test_format_cell_datetime():
    import datetime

    assert format_cell(datetime.datetime(2006, 2, 14, 15, 16, 3)) == "2006-02-14 15:16:03"


# 수용 기준 #15~#24 — render_table
def test_render_table_single_cell():
    assert render_table(("film_count",), ((1000,),)) == "film_count\n----------\n1000\n(1행)"


def test_render_table_two_columns_decimal():
    result = render_table(
        ("category", "total"),
        (("Sports", Decimal("5314.21")), ("Sci-Fi", Decimal("4756.98"))),
    )
    assert result == "category  total\n--------  -------\nSports    5314.21\nSci-Fi    4756.98\n(2행)"
    # 24
    for text in result.split("\n"):
        assert text == text.rstrip()


def test_render_table_korean_header():
    assert render_table(("영화수", "n"), ((1000, 1),)) == "영화수  n\n------  -\n1000    1\n(1행)"


def test_render_table_null_and_blob():
    result = render_table(("id", "pic"), ((1, None), (2, b"\x00" * 36)))
    assert result == "id  pic\n--  ----------\n1   NULL\n2   <36 bytes>\n(2행)"


def test_render_table_zero_rows():
    assert render_table(("n",), ()) == "n\n-\n(0행)"


def test_render_table_no_columns():
    assert render_table((), ()) == "(결과 없음)"


def test_render_table_more_than_max_rows():
    result = render_table(("i",), tuple((i,) for i in range(23)))
    expected = "i\n--\n" + "\n".join(str(i) for i in range(20)) + "\n... 외 3행 (전체 23행)"
    assert result == expected


def test_render_table_exactly_max_rows():
    result = render_table(("i",), tuple((i,) for i in range(20)))
    assert result.endswith("(20행)")
    assert "외" not in result


def test_render_table_max_rows_argument():
    assert render_table(("i",), ((0,), (1,)), max_rows=1) == "i\n-\n0\n... 외 1행 (전체 2행)"


# 수용 기준 #25~#31 — render_answer
def test_render_answer_answered():
    answer = Answer("q", "answered", "SELECT COUNT(*) AS n FROM film LIMIT 200", ("n",), ((1000,),), "")
    assert render_answer(answer) == "SQL: SELECT COUNT(*) AS n FROM film LIMIT 200\n\nn\n----\n1000\n(1행)"


def test_render_answer_unsupported():
    answer = Answer("q", "unsupported", "", (), (), "")
    assert render_answer(answer) == "이 질문은 데이터 조회로 답할 수 없습니다. (쓰기 요청이거나 스키마에 없는 내용)"


def test_render_answer_unparsable():
    answer = Answer("q", "unparsable", "", (), (), "")
    assert render_answer(answer) == "모델 응답에서 SQL 을 찾지 못했습니다. 질문을 바꿔 다시 시도하세요."


def test_render_answer_blocked():
    answer = Answer("q", "blocked", "SELECT * FROM film FOR UPDATE", (), (), "forbidden keyword: UPDATE")
    assert render_answer(answer) == "안전 검사에서 차단했습니다: forbidden keyword: UPDATE\nSQL: SELECT * FROM film FOR UPDATE"


def test_render_answer_db_error():
    answer = Answer("q", "db_error", "SELECT * FROM nope", (), (), "query failed [1146]: Table 'sakila.nope' doesn't exist")
    assert render_answer(answer) == (
        "SQL 실행에 실패했습니다: query failed [1146]: Table 'sakila.nope' doesn't exist\nSQL: SELECT * FROM nope"
    )


def test_render_answer_llm_error():
    answer = Answer("q", "llm_error", "", (), (), "cannot reach ollama at http://fake:11434")
    assert render_answer(answer) == "모델을 호출하지 못했습니다: cannot reach ollama at http://fake:11434"


def test_render_answer_all_statuses_nonempty():
    samples = {
        "answered": Answer("q", "answered", "SELECT 1", ("n",), ((1,),), ""),
        "unsupported": Answer("q", "unsupported", "", (), (), ""),
        "unparsable": Answer("q", "unparsable", "", (), (), ""),
        "blocked": Answer("q", "blocked", "SELECT 1", (), (), "blocked: x"),
        "db_error": Answer("q", "db_error", "SELECT 1", (), (), "db: x"),
        "llm_error": Answer("q", "llm_error", "", (), (), "llm: x"),
    }
    for status in STATUSES:
        result = render_answer(samples[status])
        assert isinstance(result, str)
        assert result != ""


# 수용 기준 #32~#34 — clean_input
def test_clean_input_bom_before_exit():
    assert clean_input("﻿exit") == "exit"


def test_clean_input_bom_and_spaces():
    assert clean_input("﻿  영화 몇 편?  ") == "영화 몇 편?"


def test_clean_input_bom_only():
    assert clean_input("﻿") == ""


# 수용 기준 #35~#36 — is_exit
@pytest.mark.parametrize(
    "line",
    ["", "  ", "exit", "EXIT", " quit ", "종료", "﻿exit"],
)
def test_is_exit_true(line):
    assert is_exit(line) is True


@pytest.mark.parametrize(
    "line",
    ["exit now", "영화"],
)
def test_is_exit_false(line):
    assert is_exit(line) is False


# 수용 기준 #37~#40 — parse_args
def test_parse_args_empty():
    assert parse_args([]) == ""


def test_parse_args_multiple_words():
    assert parse_args(["영화가", "총", "몇", "편이야?"]) == "영화가 총 몇 편이야?"


def test_parse_args_single_word():
    assert parse_args(["영화가 총 몇 편이야?"]) == "영화가 총 몇 편이야?"


def test_parse_args_whitespace_only():
    assert parse_args(["  "]) == ""


# 수용 기준 #41~#43 — run_once
def test_run_once_answered():
    gen = FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))
    graph = _graph(gen, FakeExecute(QR))
    outputs = []
    assert run_once("질문", graph, outputs.append) == 0
    assert outputs == ["SQL: SELECT COUNT(*) AS n FROM film LIMIT 200\n\nn\n----\n1000\n(1행)"]


def test_run_once_unsupported():
    gen = FakeGenerate(Extraction("", "unsupported"))
    graph = _graph(gen, FakeExecute(QR))
    outputs = []
    assert run_once("질문", graph, outputs.append) == 1
    assert outputs == ["이 질문은 데이터 조회로 답할 수 없습니다. (쓰기 요청이거나 스키마에 없는 내용)"]


def test_run_once_llm_error():
    gen = FakeGenerate(error=LLMError("cannot reach ollama at http://fake:11434"))
    graph = _graph(gen, FakeExecute(QR))
    outputs = []
    assert run_once("질문", graph, outputs.append) == 1
    assert outputs == ["모델을 호출하지 못했습니다: cannot reach ollama at http://fake:11434"]


# 수용 기준 #44~#50 — run_repl
def _repl_graph():
    gen = FakeGenerate(Extraction("SELECT COUNT(*) AS n FROM film", "sql"))
    return gen, _graph(gen, FakeExecute(QR))


def test_run_repl_two_lines_then_exit():
    gen, graph = _repl_graph()
    read = FakeRead(["영화 몇 편?", "exit"])
    outputs = []
    assert run_repl(graph, read, outputs.append) == 0
    assert outputs == [BANNER, "SQL: SELECT COUNT(*) AS n FROM film LIMIT 200\n\nn\n----\n1000\n(1행)", ""]
    assert read.prompts == [PROMPT, PROMPT]
    assert [call[1] for call in gen.calls] == ["영화 몇 편?"]


def test_run_repl_bom_stripped_from_question():
    gen, graph = _repl_graph()
    outputs = []
    run_repl(graph, FakeRead(["﻿영화 몇 편?", ""]), outputs.append)
    assert outputs == [BANNER, "SQL: SELECT COUNT(*) AS n FROM film LIMIT 200\n\nn\n----\n1000\n(1행)", ""]
    assert gen.calls[0][1] == "영화 몇 편?"


def test_run_repl_bom_exit_word():
    gen, graph = _repl_graph()
    outputs = []
    assert run_repl(graph, FakeRead(["﻿exit"]), outputs.append) == 0
    assert outputs == [BANNER]
    assert gen.calls == []


def test_run_repl_eof():
    gen, graph = _repl_graph()
    outputs = []
    assert run_repl(graph, FakeRead([]), outputs.append) == 0
    assert outputs == [BANNER]


def test_run_repl_keyboard_interrupt():
    gen, graph = _repl_graph()
    outputs = []
    assert run_repl(graph, FakeRead([], end=KeyboardInterrupt), outputs.append) == 0
    assert outputs == [BANNER]


def test_run_repl_two_questions():
    gen, graph = _repl_graph()
    outputs = []
    assert run_repl(graph, FakeRead(["첫 질문", "둘째 질문"]), outputs.append) == 0
    answer = "SQL: SELECT COUNT(*) AS n FROM film LIMIT 200\n\nn\n----\n1000\n(1행)"
    assert outputs == [BANNER, answer, "", answer, ""]
    assert len(gen.calls) == 2


def test_run_repl_unexpected_error_propagates():
    gen, graph = _repl_graph()
    with pytest.raises(ValueError):
        run_repl(graph, FakeRead([], end=ValueError), [].append)


# 수용 기준 #51~#53 — 구조
def test_constants():
    assert MAX_DISPLAY_ROWS == 20
    assert MAX_CELL_WIDTH == 40
    assert COLUMN_GAP == "  "
    assert PROMPT == "> "


def test_exit_words():
    assert EXIT_WORDS == frozenset({"exit", "quit", "종료"})


def test_banner():
    assert BANNER == "질문을 입력하세요. 빈 줄이나 exit 로 끝냅니다."