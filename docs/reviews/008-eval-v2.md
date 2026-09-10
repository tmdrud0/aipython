# 리뷰: 008-eval-v2

- 대상 스펙: docs/specs/008-eval-v2.md
- 판정: PASS
- 변경 규모: 3 files, +428 / -68 (`evals/run_eval.py` 149, `t2s/evaluate.py` 92, `tests/test_evaluate.py` 255)
- 비고: `evals/golden.jsonl` 60행 확장분은 이미 커밋 `44f9163` 에 들어가 있다 (007 리뷰의 커밋 포함 요구 해소). 워킹트리에 golden.jsonl 변경 없음.

## 실행한 검증

| 명령 | 결과 |
|---|---|
| `python -m pytest tests/test_evaluate.py -v` | **63 passed**, failed 0, error 0, skipped 0 |
| `python -m pytest tests/ -q` | **227 passed**, failed 0 (작업 전 `2 failed` 였던 골든셋 숫자 테스트 2개 포함 전부 초록) |
| 골든셋 해시 | `60 51f971c31b7c5e90ab82d645d42aea7028b45251cd873943c87d615bb1ab5bdf` — 스펙 기대값과 **일치** |
| `git diff --stat -- t2s ':!t2s/evaluate.py'` | **빈 출력** (t2s 타 모듈 6개 무변경, SYSTEM_PROMPT 무변경) |
| import 검사 (`t2s/evaluate.py`) | `['dataclasses', 'json', 'pathlib']` — 스펙과 일치 |
| `python -m evals.run_eval --repeat 0` | `error: --repeat must be >= 1`, **exit=2** (LLM 호출 전 종료) |
| `docker compose ... up -d` | `Container t2s-sakila Running` |
| `python -m evals.run_eval --repeat 2` | 실측 완료, **exit=1** (설계결정 6 기준 정상) — 아래 전문 |

`--repeat 2` 실측 요약: 330.6초, 문항 57/60 (95%), 시행 116/120 (97%),
`wrong_rows 4`. 불안정 문항: `dt-02 1/2`, `sh-01 1/2`, `sh-04 0/2`.
`sh-01`, `sh-04` 는 스펙이 예고한 기준선 실패 그대로고, `dt-02` 는 이번에 1회 떨어진 편차다 — 스펙 지시대로 기록만 하고 골든셋·프롬프트는 건드리지 않았다.

실패 진단 줄 실측 (3건 전부):

```
[FAIL] dt-02    1/2  wrong_rows     expect=4행 [(5, 1156), (6, 2311), (7, 6709), ...] got=12행 [(1, 0), (10, 0), (11, 0), ...] | sql=WITH months AS ( SELECT 1 AS m UNION ALL SELECT 2 UNION ALL ... UNION ALL SELECT ...
[FAIL] sh-01    1/2  wrong_rows     expect=1행 [(29)] got=1행 [(GLEAMING JAWBREAKER, 29)] | sql=SELECT f.title, COUNT(*) AS rental_count FROM film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id JOIN inventory i ON i.film_id = f.film_id JOIN re...
[FAIL] sh-04    0/2  wrong_rows     expect=1행 [(60)] got=1행 [(India, 60)] | sql=SELECT c.country, COUNT(ci.city_id) AS city_count FROM country c JOIN city ci ON ci.country_id = c.country_id GROUP BY c.country_id, c.country ORDER BY city_count DESC LIMIT 1
```

- SQL 이 200자까지 공백 정리된 채 보인다 (`compact_sql` 동작 확인 — 기존 `sql[:80]` 의 잘림 오진 재현 없음).
- `expect=... got=...` 가 한 줄에 보인다.
- 요약의 `문항`, `시행`, `반복`, `소요` 한글이 cp949 콘솔에서 안 깨졌다 (`sys.stdout.reconfigure(encoding="utf-8")` 확인).
- 요약에 `불안정 문항:` 목록이 뜬다.

## 수용 기준 대조

골든셋(#1~#6), `compact_sql`(#7~#11), `format_rows`(#12~#17), `describe_failure`(#18~#26), `summarize`(#27~#32), 구조(#33~#34) — **34개 전부 테스트로 존재하고 전부 통과**한다.

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1 | 골든 60행 | 통과 | tests/test_evaluate.py:121 `== 60` |
| 2 | unsupported 10개 | 통과 | tests/test_evaluate.py:127 `== 10` |
| 3 | id 중복 없음 | 통과 | tests/test_evaluate.py:236-238 |
| 4 | sql 항목은 expect_rows + reference_sql 보유 | 통과 | tests/test_evaluate.py:242-248 |
| 5 | unsupported 항목은 정답 없음 | 통과 | tests/test_evaluate.py:252-257 |
| 6 | expect_kind 두 값뿐 | 통과 | tests/test_evaluate.py:261-263 |
| 7~11 | compact_sql 5케이스 | 통과 | tests/test_evaluate.py:267-290 |
| 12~17 | format_rows 6케이스 | 통과 | tests/test_evaluate.py:294-321 |
| 18~26 | describe_failure 9케이스 | 통과 | tests/test_evaluate.py:325-399 |
| 27~32 | summarize 6케이스 | 통과 | tests/test_evaluate.py:403-447 |
| 33 | Summary frozen | 통과 | tests/test_evaluate.py:451-454 |
| 34 | 상수 200/3 | 통과 | tests/test_evaluate.py:458-460 |

실측 기대치 대조: 기준선 실패 `sh-01`, `sh-04` 가 `--repeat 2` 에서도 불안정 문항으로 나옴 — 스펙 예상과 일치. 기대값을 코드에 맞춰 바꾼 테스트 없음 (기존 테스트 diff 는 숫자 27→60, 3→10 두 곳과 import 줄뿐임을 `git diff` 제거 라인에서 직접 확인).

## 발견 사항

### [심각]

없음.

### [경미]

1. **테스트 주석의 수용 기준 번호가 스펙끼리 겹친다** — tests/test_evaluate.py:28 등 기존 007 번호(`#1~#7 — normalize_rows`)와 008 번호(`# 수용 기준 #7` compact_sql, 267행)가 같은 파일에 공존해, 번호만 보면 어느 스펙 기준인지 모호하다. 동작에는 영향 없음. 다음 스펙에서 기존 주석에 스펙 접두사(`007 #7` 등)를 붙이는 정도로 정리하면 된다.
2. **`run_trial` 이 `describe_failure` 에 `error` 를 넘길 때 예외 메시지 원문을 그대로 쓴다** — evals/run_eval.py:43 등. 스펙이 정한 동작이고 다중 줄 메시지도 `compact_sql` 대상이 아니어서 그대로인데, `llm_error` 진단 줄이 길어지면 문항당 한 줄이 깨질 수 있다. 현재 실측에서는 `llm_error` 가 0건이라 문제 없었음. 관찰 사항으로만 남긴다.

스펙 오류로 인한 항목: 없음. (구현 세션 절차 준수 판단 불필요 — 스펙 자체의 오류는 발견되지 않았다.)

## 커밋 전 조치

없음. 참고: `evals/golden.jsonl` 은 이미 커밋 `44f9163` 에 60행으로 들어가 있고 해시 검증도 통과했다. 이번 변경분 3개 파일을 골든셋 커밋 위에 얹어 커밋하면 된다. `--repeat 2` 실측 exit=1 은 설계결정 6 기준 정상이다.