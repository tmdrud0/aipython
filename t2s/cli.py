import argparse
import sys
import unicodedata
from collections.abc import Callable
from typing import Any

from t2s.config import ConfigError, load_settings
from t2s.db import QueryError, fetch_foreign_keys, fetch_schema
from t2s.graph import Answer, ask, build_graph
from t2s.schema import render_schema


MAX_DISPLAY_ROWS: int = 20
MAX_CELL_WIDTH: int = 40
COLUMN_GAP: str = "  "
EXIT_WORDS: frozenset[str] = frozenset({"exit", "quit", "종료"})
BANNER: str = "질문을 입력하세요. 빈 줄이나 exit 로 끝냅니다."
PROMPT: str = "> "


def display_width(text: str) -> int:
    total = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            total += 2
        else:
            total += 1
    return total


def truncate(text: str, limit: int = MAX_CELL_WIDTH) -> str:
    if display_width(text) <= limit:
        return text
    budget = limit - 3
    collected: list[str] = []
    width = 0
    for ch in text:
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if width + w > budget:
            break
        collected.append(ch)
        width += w
    return "".join(collected) + "..."


def format_cell(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    s = " ".join(str(value).split())
    return truncate(s)


def render_table(
    columns: tuple[str, ...],
    rows: tuple[tuple, ...],
    max_rows: int = MAX_DISPLAY_ROWS,
) -> str:
    if not columns:
        return "(결과 없음)"

    header = [format_cell(c) for c in columns]
    body = [[format_cell(v) for v in row] for row in rows[:max_rows]]

    widths: list[int] = []
    for i in range(len(columns)):
        width = display_width(header[i])
        for cells in body:
            width = max(width, display_width(cells[i]))
        widths.append(width)

    def line(cells: list[str]) -> str:
        padded = [cell + " " * (width - display_width(cell)) for cell, width in zip(cells, widths)]
        return COLUMN_GAP.join(padded).rstrip()

    lines = [line(header)]
    lines.append(COLUMN_GAP.join("-" * width for width in widths))
    for cells in body:
        lines.append(line(cells))
    if len(rows) > max_rows:
        lines.append(f"... 외 {len(rows) - max_rows}행 (전체 {len(rows)}행)")
    else:
        lines.append(f"({len(rows)}행)")
    return "\n".join(lines)


def render_answer(answer: Answer) -> str:
    if answer.status == "answered":
        return f"SQL: {answer.sql}\n\n{render_table(answer.columns, answer.rows)}"
    if answer.status == "unsupported":
        return "이 질문은 데이터 조회로 답할 수 없습니다. (쓰기 요청이거나 스키마에 없는 내용)"
    if answer.status == "unparsable":
        return "모델 응답에서 SQL 을 찾지 못했습니다. 질문을 바꿔 다시 시도하세요."
    if answer.status == "blocked":
        return f"안전 검사에서 차단했습니다: {answer.error}\nSQL: {answer.sql}"
    if answer.status == "db_error":
        return f"SQL 실행에 실패했습니다: {answer.error}\nSQL: {answer.sql}"
    return f"모델을 호출하지 못했습니다: {answer.error}"


def clean_input(line: str) -> str:
    return line.lstrip("\ufeff").strip()


def is_exit(line: str) -> bool:
    s = clean_input(line)
    return s == "" or s.lower() in EXIT_WORDS


def parse_args(argv: list[str] | None) -> str:
    parser = argparse.ArgumentParser(prog="python -m t2s", description="Sakila 에 한국어로 질문한다.")
    parser.add_argument("question", nargs="*", help="질문. 비우면 대화형으로 시작한다.")
    args = parser.parse_args(argv)
    return " ".join(args.question).strip()


def run_once(question: str, graph: Any, out: Callable[[str], None]) -> int:
    answer = ask(question, graph)
    out(render_answer(answer))
    return 0 if answer.status == "answered" else 1


def run_repl(graph: Any, read: Callable[[str], str], out: Callable[[str], None]) -> int:
    out(BANNER)
    try:
        while True:
            line = read(PROMPT)
            if is_exit(line):
                break
            out(render_answer(ask(clean_input(line), graph)))
            out("")
    except (EOFError, KeyboardInterrupt):
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    question = parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"설정 오류: {exc}")
        return 2

    try:
        schema_text = render_schema(fetch_schema(settings), fetch_foreign_keys(settings))
    except QueryError as exc:
        print(f"DB 연결 실패: {exc}")
        return 2

    graph = build_graph(settings, schema_text)

    if question != "":
        return run_once(question, graph, print)
    return run_repl(graph, input, print)