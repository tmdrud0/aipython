import json
from dataclasses import dataclass
from pathlib import Path


OUTCOMES: tuple[str, ...] = (
    "pass",
    "wrong_rows",
    "no_sql",
    "guard_block",
    "db_error",
    "llm_error",
    "wrong_refusal",
    "guard_saved",
)


@dataclass(frozen=True)
class GoldenItem:
    id: str
    question: str
    expect_kind: str
    expect_rows: tuple[tuple[str, ...], ...] | None
    reference_sql: str | None


def normalize_rows(rows) -> tuple[tuple[str, ...], ...]:
    normalized = tuple(tuple(str(cell) for cell in row) for row in rows)
    return tuple(sorted(normalized))


def load_golden(path: str | Path) -> tuple[GoldenItem, ...]:
    items: list[GoldenItem] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            expect_rows = payload["expect_rows"]
            if expect_rows is not None:
                expect_rows = tuple(tuple(str(c) for c in row) for row in expect_rows)
            items.append(
                GoldenItem(
                    id=payload["id"],
                    question=payload["question"],
                    expect_kind=payload["expect_kind"],
                    expect_rows=expect_rows,
                    reference_sql=payload["reference_sql"],
                )
            )
    return tuple(items)


def classify(
    item: GoldenItem,
    got_kind: str | None,
    got_rows: tuple[tuple[str, ...], ...] | None,
    failure: str | None,
) -> str:
    if failure == "llm":
        return "llm_error"

    if item.expect_kind == "unsupported":
        if got_kind == "unsupported":
            return "pass"
        if failure == "guard":
            return "guard_saved"
        return "wrong_refusal"

    if failure == "guard":
        return "guard_block"
    if failure == "db":
        return "db_error"
    if got_kind != "sql":
        return "no_sql"
    if got_rows == item.expect_rows:
        return "pass"
    return "wrong_rows"