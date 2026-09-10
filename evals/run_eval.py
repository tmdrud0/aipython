import argparse
import sys
import time

from t2s.config import ConfigError, Settings, load_settings
from t2s.db import QueryError, fetch_foreign_keys, fetch_schema, run_query
from t2s.evaluate import (
    GoldenItem,
    classify,
    describe_failure,
    load_golden,
    normalize_rows,
    summarize,
)
from t2s.guard import UnsafeSQLError
from t2s.llm import LLMError, generate_sql
from t2s.schema import render_schema


GOLDEN_PATH: str = "evals/golden.jsonl"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.run_eval")
    parser.add_argument("--repeat", type=int, default=1, help="문항당 시행 횟수 (기본 1)")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    return args


def run_trial(item: GoldenItem, schema_text: str, settings: Settings) -> tuple[str, str]:
    sql = ""
    error = ""
    got_kind = None
    got_rows = None
    failure = None

    try:
        extraction = generate_sql(schema_text, item.question, settings)
    except LLMError as exc:
        failure = "llm"
        error = str(exc)
    else:
        got_kind = extraction.kind
        sql = extraction.sql
        if extraction.kind == "sql":
            try:
                result = run_query(extraction.sql, settings)
            except UnsafeSQLError as exc:
                failure = "guard"
                error = str(exc)
            except QueryError as exc:
                failure = "db"
                error = str(exc)
            else:
                got_rows = normalize_rows(result.rows)

    outcome = classify(item, got_kind, got_rows, failure)
    return outcome, describe_failure(outcome, item, got_kind, got_rows, sql, error)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc)
        return 1

    items = load_golden(GOLDEN_PATH)
    start = time.perf_counter()
    schema_text = render_schema(fetch_schema(settings), fetch_foreign_keys(settings))

    collected: list[tuple[str, tuple[str, ...]]] = []
    for item in items:
        outcomes: list[str] = []
        first_failure: tuple[str, str] | None = None
        for _ in range(args.repeat):
            outcome, detail = run_trial(item, schema_text, settings)
            outcomes.append(outcome)
            if outcome != "pass" and first_failure is None:
                first_failure = (outcome, detail)
        passed = outcomes.count("pass")
        if first_failure is None:
            print(f"[OK  ] {item.id:8} {passed}/{args.repeat}", flush=True)
        else:
            outcome, detail = first_failure
            print(
                f"[FAIL] {item.id:8} {passed}/{args.repeat}  {outcome:14} {detail}",
                flush=True,
            )
        collected.append((item.id, tuple(outcomes)))

    summary = summarize(tuple(collected))
    elapsed = time.perf_counter() - start

    print()
    print(f"문항 {summary.stable_items}/{summary.items}  ({summary.stable_items / summary.items:.0%})")
    print(f"시행 {summary.passed_trials}/{summary.trials}  ({summary.passed_trials / summary.trials:.0%})")
    print(f"반복 {args.repeat}회, 소요 {elapsed:.1f}초")
    for outcome, count in summary.outcome_counts:
        print(f"  {outcome:14} {count}")
    if summary.unstable:
        print("불안정 문항:")
        for item_id, passed, total in summary.unstable:
            print(f"  {item_id:8} {passed}/{total}")

    return 0 if summary.passed_trials == summary.trials else 1


if __name__ == "__main__":
    raise SystemExit(main())