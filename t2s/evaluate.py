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


SQL_PREVIEW_LIMIT: int = 200
ROWS_PREVIEW_LIMIT: int = 3


def compact_sql(sql: str, limit: int = SQL_PREVIEW_LIMIT) -> str:
    s = " ".join(sql.split())
    if len(s) <= limit:
        return s
    return s[:limit] + "..."


def format_rows(
    rows: tuple[tuple[str, ...], ...] | None,
    limit: int = ROWS_PREVIEW_LIMIT,
) -> str:
    if rows is None:
        return "None"
    parts = ["(" + ", ".join(row) + ")" for row in rows[:limit]]
    body = ", ".join(parts)
    if len(rows) > limit:
        body += ", ..."
    return f"{len(rows)}행 [{body}]"


def describe_failure(
    outcome: str,
    item: GoldenItem,
    got_kind: str | None,
    got_rows: tuple[tuple[str, ...], ...] | None,
    sql: str,
    error: str,
) -> str:
    if outcome == "pass":
        return ""
    if outcome == "wrong_rows":
        return f"expect={format_rows(item.expect_rows)} got={format_rows(got_rows)} | sql={compact_sql(sql)}"
    if outcome == "llm_error":
        return error
    if outcome in ("guard_block", "db_error", "guard_saved"):
        return f"{error} | sql={compact_sql(sql)}"
    if outcome == "no_sql":
        return f"kind={got_kind}"
    if sql != "":
        return f"sql={compact_sql(sql)}"
    return f"kind={got_kind}"


@dataclass(frozen=True)
class Summary:
    items: int
    trials: int
    passed_trials: int
    stable_items: int
    outcome_counts: tuple[tuple[str, int], ...]
    unstable: tuple[tuple[str, int, int], ...]


def summarize(results: tuple[tuple[str, tuple[str, ...]], ...]) -> Summary:
    if not results:
        return Summary(0, 0, 0, 0, (), ())

    items = len(results)
    trials = sum(len(outcomes) for _, outcomes in results)
    passed_trials = sum(
        1 for _, outcomes in results for outcome in outcomes if outcome == "pass"
    )
    stable_items = sum(
        1 for _, outcomes in results if len(outcomes) > 0 and all(o == "pass" for o in outcomes)
    )

    counts: dict[str, int] = {}
    for _, outcomes in results:
        for outcome in outcomes:
            counts[outcome] = counts.get(outcome, 0) + 1
    order = {outcome: index for index, outcome in enumerate(OUTCOMES)}
    present = [outcome for outcome in OUTCOMES if counts.get(outcome, 0) > 0]
    outcome_counts = tuple(
        (outcome, counts[outcome])
        for outcome in sorted(present, key=lambda o: (-counts[o], order[o]))
    )

    unstable = tuple(
        (item_id, sum(1 for o in outcomes if o == "pass"), len(outcomes))
        for item_id, outcomes in results
        if not (len(outcomes) > 0 and all(o == "pass" for o in outcomes))
    )

    return Summary(items, trials, passed_trials, stable_items, outcome_counts, unstable)