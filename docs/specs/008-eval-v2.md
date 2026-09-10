# 008: 평가 v2 — 반복 측정 + 진단 출력 (`t2s/evaluate.py`, `evals/run_eval.py`)

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "평가 · 쿼리 효율성" 두 번째 단계. 007 러너를 **편차를 잴 수 있고 실패 원인이 보이는** 도구로 고친다. 009 `graph.py` 전에 끝낸다.
- 선행 스펙: `001`~`007` (전부 커밋 완료). 단, `evals/golden.jsonl` 은 **스펙 작성자가 이미 60행으로 확장해 둔 미커밋 상태**다 (배경 참조).
- 예상 분량: 파일 3개(신규 0 / 수정 3), 약 280줄

## 목표

`python -m evals.run_eval --repeat N` 으로 문항마다 N번 시행해 **문항별 통과율**을 내고, 실패한 문항은 **기대 행·실제 행·SQL 전체**를 한 줄로 보여준다.
출력 가공 로직은 `t2s/evaluate.py` 의 순수 함수로 분리해 LLM 없이 테스트한다.

## 배경 (이 스펙의 근거)

007 이후 러너를 실제로 쓰면서 확인된 문제다.

| 관측 | 내용 |
|---|---|
| **한 번 돌린 점수는 흔들린다** | 007 구현 세션 26/27, 스펙 작성자 재실행 26/27 — 떨어진 문항이 매번 달랐다(h-05, h-03). 27문항에서 1문항 = 3.7%p 라 96% 와 100% 가 구분되지 않는다. |
| **실패 출력이 원인을 가렸다 (두 번)** | `detail = extraction.sql[:80]` 이 여러 줄 SQL 을 첫 줄 근처에서 잘랐다. ① 007 리뷰가 h-05 를 "테이블 전체 반환" 으로 오진했다 — 실제로는 `WHERE ... = (SELECT MAX(...))` 서브쿼리가 잘려 안 보였고, 원인은 동점 104건이었다. ② h-03 실패도 `LEFT JOIN inventory i ON` 에서 잘려 따로 재현해야 했다. |
| **`wrong_rows` 에 기대/실제가 없다** | 무엇이 틀렸는지 보려면 매번 스크립트를 따로 짜야 했다. |
| **요약 한글이 깨진다** | Windows cp949 콘솔에서 `통과`, `소요` 가 깨졌다 (007 리뷰 경미 3). |
| **죽은 분기** | `if detail: pass` (007 리뷰 경미 4). |

**골든셋은 스펙 작성자가 27행 → 60행으로 확장해 두었다** (미커밋). 추가한 33행은 전부 참조 SQL 을 라이브 DB 에 돌려 정답을 뽑았고, 모델로 5회씩 시험했다.

| 묶음 | 개수 | 내용 | 5회 시험 |
|---|---|---|---|
| `aj-` 반조인·부정 | 4 | 결제 안 한 고객, 배우 없는 영화 등 | 전부 5/5 |
| `st-` 문자열 | 3 | LIKE | 전부 5/5 |
| `dt-` 날짜 | 4 | 요일, 월별, 최근 일시, 평균 일수 | 전부 5/5 |
| `hv-` HAVING | 3 | | 전부 5/5 |
| `ds-` DISTINCT | 2 | | 전부 5/5 |
| `pc-` 비율 | 2 | 소수 둘째 자리 고정 | 전부 5/5 |
| `pp-` 말투 변형 | 4 | 존댓말·반말·영어 | 전부 5/5 |
| `rf-` 쓰기 요청 거부 | 4 | UPDATE/INSERT/TRUNCATE/GRANT 류 | 전부 5/5 |
| `ns-` 스키마에 없는 개념 | 3 | 감독, 나이, 만족도 | 전부 5/5 |
| `sh-` **물은 것만 답하기** | 4 | 숫자 하나를 물었는데 이름을 덧붙이는지 | **sh-01 1/5, sh-04 0/5**, 나머지 5/5 |

60행 기준선(1회): **58/60 (97%), 189초.** 실패는 정확히 `sh-01`, `sh-04` 두 개다. 이 둘은 모델이 "몇 번/몇 개" 에 제목·나라 이름을 덧붙여 `wrong_rows` 가 된 것이며 **프롬프트로 고칠 수 있는 실패**다. 즉 이제 러너가 개선 효과를 잴 여지가 생겼다. **이 스펙에서 프롬프트를 고치지 마라** (설계결정 8).

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| 없음 | — |

**수정**
| 파일 | 무엇을 |
|---|---|
| `t2s/evaluate.py` | 상수 2개와 `compact_sql()`, `format_rows()`, `describe_failure()`, `Summary`, `summarize()` 를 **추가**한다. 기존 `OUTCOMES`, `GoldenItem`, `normalize_rows`, `load_golden`, `classify` 는 한 글자도 바꾸지 마라. |
| `evals/run_eval.py` | `--repeat N` 인자, 문항당 한 줄 출력, 새 요약, UTF-8 출력. 시행 로직을 `run_trial()` 로 뽑는다. |
| `tests/test_evaluate.py` | 기존 두 테스트의 숫자를 `27 → 60`, `3 → 10` 으로 올린다. 새 함수와 골든 불변식 테스트를 추가한다. **그 외 기존 테스트는 고치지 마라.** |

**건드리지 말 것**
- **`evals/golden.jsonl` — 한 글자도 고치지 마라.** 스펙 작성자가 이미 60행으로 만들어 둔 상태다. 이 파일은 `git diff` 에 33줄 추가로 잡혀 있고 그게 정상이다. **되돌리지도 마라** (`git checkout`, `git restore` 금지). 이 스펙의 산출물과 **같은 커밋**에 들어가야 테스트가 초록이 된다.
- **`t2s/` 의 다른 6개 모듈** — `config.py`, `guard.py`, `db.py`, `schema.py`, `prompt.py`, `llm.py`. 특히 `SYSTEM_PROMPT` 를 손대지 마라.
- `t2s/__init__.py`, `evals/__init__.py` — 0 바이트 유지.
- `tests/` 의 다른 6개 파일.
- `docker/`, `.env`, `.env.example`, `.gitignore`, `requirements.txt`, `docs/`, `readme.md`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `t2s/evaluate.py` `OUTCOMES` | `summarize()` 의 동률 정렬 기준. **새 결과 유형을 추가하지 마라.** |
| `t2s/evaluate.py` `classify()` | 시행 결과 판정. `run_trial()` 이 그대로 부른다. 판정 로직을 다시 만들지 마라. |
| `t2s/evaluate.py` `normalize_rows()` | 실행 결과 정규화. |
| `evals/run_eval.py:35-60` | 현재의 시행 로직(`generate_sql` → `run_query` → 예외 3종 → `classify`). `run_trial()` 은 **이 로직을 그대로 옮기고** 반환값만 바꾼다. 잡는 예외를 늘리거나 줄이지 마라. |
| `evals/run_eval.py:29` | 스키마 텍스트를 루프 밖에서 한 번 만드는 부분. 유지한다 (007 설계결정 4). |

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **골든셋은 입력이다.** 60행은 이미 준비됐다. 구현 세션은 읽기만 한다.
2. **출력 가공은 순수 함수로 뺀다.** `compact_sql`, `format_rows`, `describe_failure`, `summarize` 는 LLM·DB·파일을 모른다. 그래서 오진을 만든 출력 로직을 결정적으로 테스트할 수 있다. `run_eval.py` 는 얇게 남긴다.
3. **SQL 은 공백을 한 칸으로 합친 뒤 200자까지 보여준다.** `sql[:80]` 처럼 원문을 자르지 마라. 줄바꿈 때문에 `WHERE` 가 잘려 오진이 났다.
4. **`--repeat` 는 재시도가 아니라 측정이다.** 기본값 1. 한 시행이 실패해도 **나머지 시행을 그대로 한다.** 통과할 때까지 반복하지 마라 — 그러면 편차가 사라져서 측정 의미가 없어진다.
5. **문항당 출력은 한 줄이다.** `--repeat 3` 이어도 문항 60개면 60줄이다. 실패가 있으면 **첫 번째 실패 시행**의 결과 유형과 진단을 보여준다.
6. **종료 코드는 모든 시행이 통과했을 때만 0 이다.** 하나라도 실패하면 1. 현재 기준선에서는 `sh-01`, `sh-04` 때문에 **1 이 정상**이다.
7. **테스트의 골든 문항 수는 박아 둔다** (`60`, 거부 `10`). 골든셋이 몰래 바뀌는 것을 막는 장치이므로 유지한다. 골든셋을 바꿀 때는 이 숫자도 같은 커밋에서 바꾼다.
8. **프롬프트를 고치지 마라.** `sh-01`, `sh-04` 를 통과시키려고 `SYSTEM_PROMPT` 를 바꾸는 것은 다음 사이클이다. 이 스펙은 **자를 만드는** 스펙이지 점수를 올리는 스펙이 아니다.
9. **인자는 `--repeat` 하나뿐이다.** 문항 필터(`--only`), 출력 파일(`--out`), 병렬 실행을 넣지 마라.

## 파일별 계약

### `t2s/evaluate.py` (추가분만. 기존 코드 아래에 붙인다)

```python
SQL_PREVIEW_LIMIT: int = 200
ROWS_PREVIEW_LIMIT: int = 3


def compact_sql(sql: str, limit: int = SQL_PREVIEW_LIMIT) -> str:
    ...


def format_rows(
    rows: tuple[tuple[str, ...], ...] | None,
    limit: int = ROWS_PREVIEW_LIMIT,
) -> str:
    ...


def describe_failure(
    outcome: str,
    item: GoldenItem,
    got_kind: str | None,
    got_rows: tuple[tuple[str, ...], ...] | None,
    sql: str,
    error: str,
) -> str:
    ...


@dataclass(frozen=True)
class Summary:
    items: int
    trials: int
    passed_trials: int
    stable_items: int
    outcome_counts: tuple[tuple[str, int], ...]
    unstable: tuple[tuple[str, int, int], ...]


def summarize(results: tuple[tuple[str, tuple[str, ...]], ...]) -> Summary:
    ...
```

**import 를 추가하지 마라.** `evaluate.py` 의 import 는 지금처럼 `dataclasses`, `json`, `pathlib` 셋이다.

---

#### `compact_sql(sql, limit=SQL_PREVIEW_LIMIT) -> str`

1. `s = " ".join(sql.split())` — 줄바꿈·탭·연속 공백을 전부 한 칸으로 합치고 앞뒤 공백을 없앤다.
2. `len(s) <= limit` 이면 `s` 를 반환한다.
3. 아니면 `s[:limit] + "..."` 를 반환한다. (결과 길이는 `limit + 3`.)
4. 예외를 던지지 마라.

#### `format_rows(rows, limit=ROWS_PREVIEW_LIMIT) -> str`

1. `rows is None` 이면 `"None"` 을 반환한다.
2. 앞에서부터 최대 `limit` 개 행을 고른다. 각 행은 `"(" + ", ".join(row) + ")"` 로 만든다 — **따옴표를 붙이지 마라** (`repr` 을 쓰지 마라).
3. 고른 행들을 `", "` 로 잇는다. `len(rows) > limit` 이면 끝에 `", ..."` 를 붙인다.
4. `f"{len(rows)}행 [{본문}]"` 을 반환한다. 행이 0개면 `"0행 []"` 이다.
5. 예외를 던지지 마라.

#### `describe_failure(outcome, item, got_kind, got_rows, sql, error) -> str`

`outcome` 에 따라 **아래 표대로만** 만든다. `sql` 은 모델이 만든 SQL 원문(없으면 `""`), `error` 는 예외 메시지(없으면 `""`)다.

| `outcome` | 반환값 |
|---|---|
| `"pass"` | `""` |
| `"wrong_rows"` | `f"expect={format_rows(item.expect_rows)} got={format_rows(got_rows)} \| sql={compact_sql(sql)}"` |
| `"llm_error"` | `error` 그대로 |
| `"guard_block"`, `"db_error"`, `"guard_saved"` | `f"{error} \| sql={compact_sql(sql)}"` |
| `"no_sql"` | `f"kind={got_kind}"` |
| `"wrong_refusal"` | `sql` 이 빈 문자열이 아니면 `f"sql={compact_sql(sql)}"`, 빈 문자열이면 `f"kind={got_kind}"` |

(표 안의 `\|` 는 마크다운 표 이스케이프다. 실제 문자열은 `" | sql="` — 공백, 세로막대, 공백.)

- `OUTCOMES` 밖의 값이 들어오는 경우는 없다. 별도 처리를 하지 마라.
- 예외를 던지지 마라. 로깅·print 를 하지 마라.

#### `summarize(results) -> Summary`

`results` 는 `(문항 id, 시행별 결과 튜플)` 의 튜플이다. 예: `(("t1-01", ("pass", "pass")), ("sh-04", ("wrong_rows", "wrong_rows")))`.

1. `items = len(results)`
2. `trials` = 모든 시행 결과 튜플 길이의 합
3. `passed_trials` = 모든 시행 중 `"pass"` 의 개수
4. `stable_items` = 시행 결과가 **1개 이상이고 전부 `"pass"`** 인 문항 수
5. `outcome_counts` = 모든 시행을 통틀어 결과 유형별 개수. **개수가 0인 유형은 넣지 않는다.** 정렬은 **개수 내림차순**, 개수가 같으면 **`OUTCOMES` 에 선언된 순서**를 따른다. `(유형, 개수)` 튜플의 튜플이다.
6. `unstable` = `stable_items` 에 들지 않은 문항마다 `(id, 통과 횟수, 시행 횟수)`. **입력 순서를 유지한다** (정렬하지 마라).
7. `results` 가 비어 있으면 `Summary(0, 0, 0, 0, (), ())` 를 반환한다.
8. 예외를 던지지 마라.

---

### `evals/run_eval.py` (다시 쓴다)

```python
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
    ...


def run_trial(item: GoldenItem, schema_text: str, settings: Settings) -> tuple[str, str]:
    ...


def main(argv: list[str] | None = None) -> int:
    ...


if __name__ == "__main__":
    raise SystemExit(main())
```

#### `parse_args(argv)`

1. `parser = argparse.ArgumentParser(prog="python -m evals.run_eval")`
2. `parser.add_argument("--repeat", type=int, default=1, help="문항당 시행 횟수 (기본 1)")` — 이것 하나뿐이다 (설계결정 9).
3. `args = parser.parse_args(argv)`
4. `args.repeat < 1` 이면 `parser.error("--repeat must be >= 1")` 를 부른다 (argparse 가 종료 코드 2로 끝낸다).
5. `args` 를 반환한다.

#### `run_trial(item, schema_text, settings) -> tuple[str, str]`

현재 `run_eval.py:35-60` 의 로직을 그대로 옮기되, 아래 두 값을 추적한다.

1. `sql = ""`, `error = ""` 로 시작한다. `got_kind`, `got_rows`, `failure` 는 지금처럼 `None` 으로 시작한다.
2. `generate_sql(...)` 에서 `LLMError` → `failure = "llm"`, `error = str(exc)`.
3. 성공하면 `got_kind = extraction.kind`, `sql = extraction.sql`.
4. `kind == "sql"` 이면 `run_query(extraction.sql, settings)`:
   - `UnsafeSQLError` → `failure = "guard"`, `error = str(exc)`
   - `QueryError` → `failure = "db"`, `error = str(exc)`
   - 성공 → `got_rows = normalize_rows(result.rows)`
5. `outcome = classify(item, got_kind, got_rows, failure)`
6. `(outcome, describe_failure(outcome, item, got_kind, got_rows, sql, error))` 를 반환한다.
7. 잡는 예외는 `LLMError`, `UnsafeSQLError`, `QueryError` 셋뿐이다. `except Exception:` 금지.

#### `main(argv=None) -> int`

1. **맨 먼저** `sys.stdout.reconfigure(encoding="utf-8")` 를 호출한다.
2. `args = parse_args(argv)`
3. `load_settings()` 에서 `ConfigError` 가 나면 메시지를 print 하고 `1` 을 반환한다.
4. `items = load_golden(GOLDEN_PATH)`, 시간 측정 시작(`time.perf_counter()`), 스키마 텍스트를 **한 번만** 만든다.
5. 문항마다:
   1. `run_trial` 을 `args.repeat` 번 부른다. **중간에 멈추지 마라** (설계결정 4).
   2. 시행 결과 유형을 튜플로 모으고, **첫 번째 실패 시행**의 `(outcome, detail)` 을 기억한다.
   3. 한 줄을 출력한다 (`flush=True`). 형식은 둘 중 하나다:
      - 전부 통과: `f"[OK  ] {item.id:8} {passed}/{args.repeat}"`
      - 하나라도 실패: `f"[FAIL] {item.id:8} {passed}/{args.repeat}  {outcome:14} {detail}"` — `outcome`, `detail` 은 첫 번째 실패 시행의 것
   4. `(item.id, 결과 튜플)` 을 모은다.
6. `summary = summarize(tuple(모은 것))`, 경과 시간을 잰다.
7. 요약을 **이 형식 그대로** 출력한다:
   ```python
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
   ```
8. `summary.passed_trials == summary.trials` 이면 `0`, 아니면 `1` 을 반환한다.
9. 결과를 파일로 쓰지 마라. `sys.path` 를 조작하지 마라.

---

### `tests/test_evaluate.py` (수정)

1. `test_load_golden_real_file` 의 `assert len(result) == 27` 을 **`== 60`** 으로 바꾼다.
2. `test_load_golden_real_file_unsupported_count` 의 `== 3` 을 **`== 10`** 으로 바꾼다.
3. import 줄에 `Summary`, `compact_sql`, `describe_failure`, `format_rows`, `summarize` 를 추가한다.
4. 아래 수용 기준 #3~#34 를 파일 끝에 추가한다.
5. **그 외 기존 테스트는 고치지 마라.** 특히 `t1-01`, `t3-03` 을 보는 테스트는 그대로 통과해야 한다.
6. 새 테스트는 LLM·DB 에 접근하지 마라. `evals.run_eval` 을 import 하지 마라. `t2s.evaluate` 만 쓴다.
7. 비교는 `==` 완전 일치다.

## 수용 기준

기대값은 전부 참조 구현으로 미리 계산한 값이다.

**골든셋 (실제 파일)**

| # | 입력 | 기대 | 비고 |
|---|---|---|---|
| 1 | `len(load_golden("evals/golden.jsonl"))` | `60` | 기존 테스트 숫자 변경 |
| 2 | 위 결과 중 `expect_kind == "unsupported"` 개수 | `10` | 기존 테스트 숫자 변경 |
| 3 | 위 결과의 `id` 목록 | 중복 없음 (`len(set(ids)) == 60`) | 신규 불변식 |
| 4 | `expect_kind == "sql"` 인 모든 항목 | `expect_rows is not None` 이고 `reference_sql` 이 빈 문자열이 아님 | 신규 불변식. 정답 없는 sql 문항 방지 |
| 5 | `expect_kind == "unsupported"` 인 모든 항목 | `expect_rows is None` 이고 `reference_sql is None` | 신규 불변식 |
| 6 | 모든 항목의 `expect_kind` | `"sql"` 또는 `"unsupported"` 둘 중 하나 | 신규 불변식 |

**`compact_sql`**

| # | 입력 | 기대 | 비고 |
|---|---|---|---|
| 7 | `"SELECT a\nFROM t\n  WHERE x = 1"` | `"SELECT a FROM t WHERE x = 1"` | **오진의 원인이던 줄바꿈** 제거 |
| 8 | `""` | `""` | |
| 9 | `"A" * 250` | 길이 `203`, `"A" * 200 + "..."` | 자르기 |
| 10 | `"B" * 200` | `"B" * 200` (길이 200, `...` 없음) | 경계값: 정확히 limit |
| 11 | `compact_sql("SELECT * FROM film", limit=10)` | `"SELECT * F..."` | limit 인자 |

**`format_rows`**

| # | 입력 | 기대 | 비고 |
|---|---|---|---|
| 12 | `None` | `"None"` | |
| 13 | `()` | `"0행 []"` | |
| 14 | `(("India", "60"),)` | `"1행 [(India, 60)]"` | 따옴표 없음 |
| 15 | `(("1", "a"), ("2", "b"), ("3", "c"))` | `"3행 [(1, a), (2, b), (3, c)]"` | 경계값: 정확히 limit |
| 16 | `(("1",), ("2",), ("3",), ("4",))` | `"4행 [(1), (2), (3), ...]"` | limit 초과 |
| 17 | `format_rows((("1",), ("2",)), limit=1)` | `"2행 [(1), ...]"` | limit 인자 |

**`describe_failure`** (`ITEM = GoldenItem("x", "q", "sql", (("1000",),), None)`)

| # | `outcome`, `got_kind`, `got_rows`, `sql`, `error` | 기대 |
|---|---|---|
| 18 | `"pass"`, `"sql"`, `(("1000",),)`, `"SELECT 1"`, `""` | `""` |
| 19 | `"wrong_rows"`, `"sql"`, `(("India", "60"),)`, `"SELECT c.country,\n  COUNT(*) FROM city"`, `""` | `"expect=1행 [(1000)] got=1행 [(India, 60)] \| sql=SELECT c.country, COUNT(*) FROM city"` |
| 20 | `"llm_error"`, `None`, `None`, `""`, `"cannot reach ollama at http://x:11434"` | `"cannot reach ollama at http://x:11434"` |
| 21 | `"guard_block"`, `"sql"`, `None`, `"SELECT 1\nFOR UPDATE"`, `"forbidden keyword: UPDATE"` | `"forbidden keyword: UPDATE \| sql=SELECT 1 FOR UPDATE"` |
| 22 | `"db_error"`, `"sql"`, `None`, `"SELECT * FROM nope"`, `"query failed [1146]: Table 'sakila.nope' doesn't exist"` | `"query failed [1146]: Table 'sakila.nope' doesn't exist \| sql=SELECT * FROM nope"` |
| 23 | `"no_sql"`, `"unsupported"`, `None`, `""`, `""` | `"kind=unsupported"` |
| 24 | `"wrong_refusal"`, `"sql"`, `(("a@b",),)`, `"SELECT email\nFROM customer"`, `""` | `"sql=SELECT email FROM customer"` |
| 25 | `"wrong_refusal"`, `"unparsable"`, `None`, `""`, `""` | `"kind=unparsable"` |
| 26 | `"guard_saved"`, `"sql"`, `None`, `"SELECT * FROM mysql.user"`, `"system schema access is not allowed: mysql"` | `"system schema access is not allowed: mysql \| sql=SELECT * FROM mysql.user"` |

(표의 `\|` 는 실제 문자열에서 `|` 다.)

**`summarize`**

| # | 입력 | 기대 |
|---|---|---|
| 27 | `()` | `Summary(0, 0, 0, 0, (), ())` |
| 28 | `(("a", ("pass", "pass")), ("b", ("pass", "wrong_rows")), ("c", ("db_error", "wrong_rows")))` | `Summary(items=3, trials=6, passed_trials=3, stable_items=1, outcome_counts=(("pass", 3), ("wrong_rows", 2), ("db_error", 1)), unstable=(("b", 1, 2), ("c", 0, 2)))` |
| 29 | `(("a", ("db_error",)), ("b", ("wrong_rows",)))` | `outcome_counts == (("wrong_rows", 1), ("db_error", 1))` — **동률이면 `OUTCOMES` 순서** (`wrong_rows` 가 `db_error` 보다 앞) |
| 30 | #29 의 `unstable` | `(("a", 0, 1), ("b", 0, 1))` — 입력 순서 유지 |
| 31 | `(("a", ("pass",)), ("b", ("pass",)))` | `Summary(2, 2, 2, 2, (("pass", 2),), ())` |
| 32 | `(("z", ("wrong_rows",)), ("a", ("pass", "wrong_rows")))` 의 `unstable` | `(("z", 0, 1), ("a", 1, 2))` — id 로 정렬하지 않는다 |

**구조**

| # | 입력 | 기대 |
|---|---|---|
| 33 | `Summary(0,0,0,0,(),())` 에 `obj.items = 1` 대입 | `dataclasses.FrozenInstanceError` |
| 34 | `SQL_PREVIEW_LIMIT`, `ROWS_PREVIEW_LIMIT` | `200`, `3` |

## 검증 명령

PowerShell 에서 저장소 루트에 서서 한 줄씩 실행한다. (`&&` 금지.)

**단위 테스트 (LLM·DB 불필요):**
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluate.py -v
```
기대 출력: `failed 0`, `error 0`, `skipped 0`.

**전체 회귀:**
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```
기대 출력: `failed 0`. 작업 전에는 골든셋 확장 때문에 `2 failed, 193 passed` 가 정상이다 — 작업 후 그 2개가 초록이 되고 새 테스트가 더해진다.

**골든셋 무변경 확인 (가장 중요):**
```powershell
.\.venv\Scripts\python.exe -c "import hashlib; L=[l.rstrip('\r\n') for l in open('evals/golden.jsonl',encoding='utf-8') if l.strip()]; print(len(L), hashlib.sha256('\n'.join(L).encode('utf-8')).hexdigest())"
```
기대 출력:
```
60 51f971c31b7c5e90ab82d645d42aea7028b45251cd873943c87d615bb1ab5bdf
```
줄바꿈(CRLF/LF)과 무관하게 내용만 비교하는 해시다. **값이 다르면 골든셋을 건드린 것이고 FAIL 이다.** (`git diff --stat evals/golden.jsonl` 은 스펙 작성자의 확장분 33줄 추가가 잡히는 게 정상이므로 이 검증에 쓰지 않는다.)

**다른 모듈 무변경 확인:**
```powershell
git diff --stat -- t2s ':!t2s/evaluate.py'
```
기대 출력: **빈 출력.**

**import 무변경 확인:**
```powershell
.\.venv\Scripts\python.exe -c "import ast; t=ast.parse(open('t2s/evaluate.py',encoding='utf-8').read()); print(sorted({n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}))"
```
기대 출력:
```
['dataclasses', 'json', 'pathlib']
```

**인자 검증:**
```powershell
.\.venv\Scripts\python.exe -m evals.run_eval --repeat 0; echo "exit=$LASTEXITCODE"
```
기대 출력: `--repeat must be >= 1` 이 포함된 오류와 `exit=2`. (LLM 을 부르기 전에 끝나야 한다.)

**실측 (필수, 실제 출력을 그대로 보고할 것):**
```powershell
docker compose -f docker/docker-compose.yml up -d
```
```powershell
.\.venv\Scripts\python.exe -m evals.run_eval --repeat 2; echo "exit=$LASTEXITCODE"
```
기대 출력 (약 6~7분):
- 문항당 한 줄씩 60줄, 이어서 요약.
- 스펙 작성 시점 기준선은 1회 58/60 이고 실패는 `sh-01`, `sh-04` 였다. `--repeat 2` 에서도 **이 두 문항이 `불안정 문항:` 에 나오는 것이 예상 결과**다.
- 실패 줄의 진단에 **공백이 정리된 SQL 전체**(200자까지)와 `expect=... got=...` 가 보여야 한다. 예: `[FAIL] sh-04    0/2  wrong_rows     expect=1행 [(60)] got=1행 [(India, 60)] | sql=SELECT ...`
- 요약의 `문항`, `시행`, `반복`, `소요` 한글이 깨지지 않아야 한다.
- `exit=1` 이 정상이다 (설계결정 6).
- 다른 문항이 떨어져도 **골든셋이나 프롬프트를 고치지 마라.** 그 문항과 진단 줄을 그대로 보고하라. 그게 이 러너가 잡으려는 편차다.

## 하지 말 것

- **`evals/golden.jsonl` 을 수정하거나 되돌리지 마라.** 해시가 바뀌면 FAIL 이다.
- **`SYSTEM_PROMPT` 를 고치지 마라.** `sh-01`, `sh-04` 를 통과시키려는 어떤 변경도 범위 밖이다 (설계결정 8).
- `t2s/evaluate.py` 의 기존 5개 요소(`OUTCOMES`, `GoldenItem`, `normalize_rows`, `load_golden`, `classify`)를 고치지 마라.
- `OUTCOMES` 에 새 유형을 추가하지 마라.
- `evaluate.py` 에 import 를 추가하지 마라.
- `sql[:N]` 로 원문을 자르지 마라. `compact_sql()` 을 써라.
- `format_rows` 에서 `repr()` 이나 따옴표를 쓰지 마라.
- `--repeat` 를 "통과할 때까지 재시도" 로 구현하지 마라. 시행 도중 멈추지 마라.
- `--repeat` 외 인자(`--only`, `--out`, `--jobs` 등)를 넣지 마라.
- 시행마다 한 줄씩 찍지 마라. 문항당 한 줄이다.
- 루프 안에서 `fetch_schema()` / `render_schema()` 를 부르지 마라.
- `except Exception:` 을 쓰지 마라.
- 결과를 파일에 쓰지 마라. `sys.path` 를 조작하지 마라.
- `tests/test_evaluate.py` 의 기존 테스트를 숫자 두 개 외에 고치지 마라.
- `t2s/graph.py`, `t2s/cli.py` 를 만들지 마라. 다음 스펙이다.
- `requirements.txt` 에 의존성을 추가하지 마라.
- 커밋하지 마라.

## 체크리스트

- [ ] 수정한 파일이 `t2s/evaluate.py`, `evals/run_eval.py`, `tests/test_evaluate.py` 셋뿐이다
- [ ] 골든셋 해시가 `51f971c3…bdf` 이고 행 수가 60 이다
- [ ] `git diff --stat -- t2s ':!t2s/evaluate.py'` 가 빈 출력이다
- [ ] `evaluate.py` 의 import 가 `dataclasses`, `json`, `pathlib` 셋 그대로다
- [ ] 새 함수·상수·`Summary` 의 시그니처와 필드 순서를 글자 그대로 따랐다
- [ ] `run_trial` 이 잡는 예외가 `LLMError`, `UnsafeSQLError`, `QueryError` 셋뿐이다
- [ ] 수용 기준 34행 전부가 테스트로 존재한다 (#1·#2 는 기존 테스트 숫자 변경)
- [ ] `pytest tests/ -q` 가 `failed 0` 이다
- [ ] `--repeat 0` 이 `exit=2` 로 끝난다
- [ ] `--repeat 2` 를 실제로 돌렸고 출력 전문(60줄 + 요약)과 `exit` 값을 그대로 보고했다
- [ ] 커밋하지 않았다

## 질문

구현 세션이 막혔을 때 여기에 적는다. 아래는 **스펙 작성 시점에 확인된 사항**이다.

1. **`sh-` 묶음은 "물은 것만 답했는가" 를 엄격하게 채점한다.** 사람이 보는 제품에서는 `(India, 60)` 이 오히려 친절할 수 있다. 이 기준은 스펙 작성자가 사용자에게 확인을 요청해 둔 판단이다 — 사용자가 빼기로 하면 골든셋에서 4줄을 지우고 이 스펙의 숫자(`60`, 해시)가 바뀐다. **구현 세션이 임의로 빼지 마라.**
2. **`--repeat 2` 실측이 6~7분 걸린다.** 클라우드 모델 호출 120번이다. 중간에 끊지 말고 끝까지 돌려서 보고하라.
3. **[이번 범위 밖] 컬럼 단위 접근 제어가 여전히 없다** (`staff.password`, `customer.email`). 해당 문항은 차단 정책이 생길 때 골든셋에 넣는다.
