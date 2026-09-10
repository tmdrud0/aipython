import time

from t2s.config import ConfigError, load_settings
from t2s.db import (
    QueryError,
    fetch_foreign_keys,
    fetch_schema,
    run_query,
)
from t2s.evaluate import OUTCOMES, classify, load_golden, normalize_rows
from t2s.guard import UnsafeSQLError
from t2s.llm import LLMError, generate_sql
from t2s.schema import render_schema


GOLDEN_PATH: str = "evals/golden.jsonl"


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc)
        return 1

    items = load_golden(GOLDEN_PATH)

    start = time.perf_counter()
    schema_text = render_schema(fetch_schema(settings), fetch_foreign_keys(settings))

    pass_count = 0
    counts: dict[str, int] = {}

    for item in items:
        extraction = None
        got_kind = None
        got_rows = None
        failure = None
        detail = ""

        try:
            extraction = generate_sql(schema_text, item.question, settings)
        except LLMError as exc:
            failure = "llm"
            detail = str(exc)
        else:
            got_kind = extraction.kind
            if extraction.kind == "sql":
                try:
                    result = run_query(extraction.sql, settings)
                except UnsafeSQLError as exc:
                    failure = "guard"
                    detail = str(exc)
                except QueryError as exc:
                    failure = "db"
                    detail = str(exc)
                else:
                    got_rows = normalize_rows(result.rows)

        outcome = classify(item, got_kind, got_rows, failure)

        if outcome != "pass":
            if detail:
                pass
            elif extraction is not None and extraction.sql:
                detail = extraction.sql[:80]
            elif extraction is not None:
                detail = extraction.kind

        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome == "pass":
            pass_count += 1
        marker = "OK  " if outcome == "pass" else "FAIL"
        print(f"[{marker}] {item.id:8} {outcome:14} {detail}")

    elapsed = time.perf_counter() - start
    total = len(items)
    print()
    print(f"통과 {pass_count}/{total}  ({pass_count / total:.0%})")
    print(f"소요 {elapsed:.1f}초")
    ranked = sorted(
        (o for o in OUTCOMES if counts.get(o, 0) > 0),
        key=lambda outcome: -counts[outcome],
    )
    for outcome in ranked:
        print(f"  {outcome:14} {counts[outcome]}")

    return 0 if pass_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())