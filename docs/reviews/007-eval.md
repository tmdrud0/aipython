# 리뷰: 007-eval

- 대상 스펙: docs/specs/007-eval.md
- 판정: PASS_WITH_NITS
- 변경 규모: 신규 4 파일 (`t2s/evaluate.py` 79줄, `evals/run_eval.py` 92줄, `tests/test_evaluate.py` 213줄, `evals/__init__.py` 0바이트) + 스펙 문서. 수정 파일 0개 (`git diff` 빈 출력 확인)

## 실행한 검증

PowerShell 대신 Bash(Git Bash)로 동일 명령을 실행했다. 결과는 실제 출력이다.

| 명령 | 결과 |
|---|---|
| `pytest tests/test_evaluate.py -v` | **31 passed in 0.03s** (failed 0, error 0, skipped 0) |
| `pytest tests/ -q` | **195 passed in 5.21s** (기대 164 이상, failed/error/skipped 0) |
| `git diff --stat evals/golden.jsonl` | 빈 출력 |
| `git diff --stat t2s/` | 빈 출력 (전체 `git diff` 도 빈 출력 — tracked 파일 무변경) |
| 골든셋 줄 수 | **27** (utf-8 기준 non-blank) |
| AST import 점검 (`t2s/evaluate.py`) | `['dataclasses', 'json', 'pathlib']` — `t2s.*`/`pymysql`/`ollama` 없음 |
| `docker compose -f docker/docker-compose.yml up -d` | t2s-sakila 기동 완료 |
| `python -m evals.run_eval` | **26/27 (96%), 63.2초, exit=1** — 아래 실측 절 참조 |
| h-05 참조 SQL을 라이브 DB에 직접 실행 | `(('4', '10'),)` — 골든셋 `expect_rows [["4","10"]]` 와 일치. 모델 스타일 SQL(`... FROM rental` 전체)은 `((1,2),(2,4),(3,8),...)` 로 전혀 다른 행 집합 |

### 평가 실측 출력 (그대로)

```
27줄 전부 출력됨. 26줄 [OK], 1줄 [FAIL]:
[FAIL] h-05     wrong_rows     SELECT rental_id, DATEDIFF(return_date, rental_date) AS rental_days
FROM rental

통과 26/27  (96%)
소요 63.2초
  pass           26
  wrong_rows     1
exit=1
```

- **h-05 실패 원인 (실측 확인):** 모델이 참조 SQL의 `WHERE return_date IS NOT NULL ORDER BY ... LIMIT 1` 을 생략하고 테이블 전체를 반환했다. 골든 정답 `(("4","10"),)` 은 라이브 DB 실측으로 재확인했으므로 골든셋 오류가 아니고, 구현 버그도 아니다. 분류 `wrong_rows` 는 올바르다. 스펙의 지시대로 골든셋·프롬프트를 손대지 않고 실측을 기록했다. 클라우드 모델 편차로 보며, 스펙 작성 시점 27/27 대비 -1이다.
- 콘솔에서 요약의 한글(`통과`, `소요`)이 cp949 콘솔에서 깨져 보였다(출력 인코딩 문제, 파일은 UTF-8 정상). 동작에는 영향 없음.

## 수용 기준 대조

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1~7 | `normalize_rows` (int→str, Decimal, 정렬, 빈 입력, None, 중복 보존, tuple 타입) | 통과 | `t2s/evaluate.py:27-29`, `tests/test_evaluate.py:17-50`, pytest 실측 PASSED |
| 8~15 | `classify` expect_kind=="sql" 8케이스 | 통과 | `t2s/evaluate.py:71-79` (규칙 순서 그대로), `tests/test_evaluate.py:54-79` |
| 16~20 | `classify` expect_kind=="unsupported" 5케이스 | 통과 | `t2s/evaluate.py:64-69` (규칙 1이 분기보다 먼저 — `evaluate.py:61-62`), `tests/test_evaluate.py:83-101` |
| 21 | 실제 골든셋 27행 | 통과 | `tests/test_evaluate.py:105-108`, 실측 27 |
| 22 | unsupported 3개 (t5-01/t5-02/h-07) | 통과 | `tests/test_evaluate.py:112-114`, 직접 파싱으로도 확인 (t5-01, t5-02, h-07) |
| 23 | result[0] == t1-01 / sql / (("1000",),) | 통과 | `tests/test_evaluate.py:118-122`, 골든셋 1행과 일치 |
| 24 | t3-03 expect_rows 2행 | 통과 | `tests/test_evaluate.py:126-129` |
| 25 | expect_rows 가 None 또는 tuple(tuple) | 통과 | `tests/test_evaluate.py:133-139`, 변환은 `t2s/evaluate.py:41-42` |
| 26~28 | 빈 줄 건너뛰기 / UTF-8 한국어 / FileNotFoundError | 통과 | `t2s/evaluate.py:34-39` (`encoding="utf-8"` 명시), `tests/test_evaluate.py:143-182` |
| 29 | `OUTCOMES` 순서까지 일치 | 통과 | `t2s/evaluate.py:6-15`, `tests/test_evaluate.py:186-196` |
| 30 | 모든 classify 결과 in OUTCOMES | 통과 | `tests/test_evaluate.py:78,100` 에 파라미터화 테스트에 포함 |
| 31 | classify 시그니처 | 통과 | `t2s/evaluate.py:55-60`, `tests/test_evaluate.py:200-206` |
| 32 | GoldenItem frozen | 통과 | `t2s/evaluate.py:18`, `tests/test_evaluate.py:210-213` |

32행 전부 테스트로 존재하고 실제로 통과한다. 기대값을 코드에 맞춰 바꾼 흔적 없음.

## 발견 사항

### [심각]

없음.

### [경미]

1. **골든셋이 커밋 이력에 없다 (스펙 전제와 현실의 불일치).** `git log --all -- evals/golden.jsonl` 이 빈 출력 — `evals/golden.jsonl` 은 untracked 이고 어떤 커밋에도 없다. 스펙은 "27행은 이미 저장소에 있다"고 전제하고 `git diff --stat evals/golden.jsonl` 을 "가장 중요한" 검증으로 내걸었지만, 파일이 untracked 인 이상 그 검증은 **공허하게 통과**한다 (구현 세션이 골든셋을 고쳐도 git diff 로 탐지 불가). 완화 증거: 파일 mtime(14:45) 이 구현 파일들(14:53~14:54)보다 앞서고, 내용이 스펙 기술(27행, unsupported 3개=t5-01/t5-02/h-07, t1-01/t3-03 정답)과 정확히 일치하며, h-05 참조 SQL 실측이 골든 정답과 일치한다. 이는 **스펙/운영 절차 오류**지 구현 세션 위반으로 보기 어렵다. **이 커밋에 `evals/golden.jsonl` 을 반드시 포함해 커밋하라** — 그래야 이후 스펙의 무변경 검증이 실제로 작동한다.
2. **스펙 내부 모순: 실제 골든셋을 읽는 테스트 개수.** 스펙 테스트 규칙 4는 "실제 `evals/golden.jsonl` 을 읽는 테스트는 #20 하나만"이라 했지만 수용 기준 표의 #21~#25 는 전부 "#21 의 결과"에 기반해 실제 파일을 읽어야 성립한다. 구현은 5개 테스트가 각각 실제 파일을 읽는다(`tests/test_evaluate.py:106,113,119,127,134`). 수용 기준 표를 우선한 판단으로 보며 합리적 — 규칙 4의 "#20"은 표 번호 체계에 없는 값이라 **스펙 오기**로 판단한다. 절차 준수 여부: 표 우선은 정당. 모듈 수준 fixture 로 한 번만 읽게 하면 다음 스펙에서 정리 여지 있음(동작 문제 없음).
3. **요약 출력의 한글 콘솔 모지바케.** `evals/run_eval.py:79-80` 이 UTF-8 텍스트를 print 하는데 Windows cp949 콘솔에서 깨졌다. 스펙이 요구한 형식(`통과 {n}/{total} ({비율})`)은 그대로 따랐고 파일·종료 코드에는 영향 없다. 다음 스펙에서 정리 후보(예: `sys.stdout.reconfigure(encoding="utf-8")`).
4. **죽은 분기.** `evals/run_eval.py:62-64` 의 `if detail: pass` 는 no-op. 스타일 수준이며 동작 영향 없음.

## 범위·보안 확인

- 신규 파일이 정확히 스펙 범위 3개 + `evals/__init__.py`(0바이트 확인) + 스펙 문서뿐. `t2s/` 기존 6개 모듈, `tests/` 기존 6개 파일, `golden.jsonl` 모두 tracked diff 없음.
- `run_eval.py` 는 `ensure_safe_sql` 을 직접 부르지 않고 `run_query` 만 부른다 (`evals/run_eval.py:50`). 잡는 예외도 `LLMError`/`UnsafeSQLError`/`QueryError` 셋뿐 (`evals/run_eval.py:43,51,54`). `except Exception:` 없음.
- `render_schema(fetch_schema(...), fetch_foreign_keys(...))` 를 루프 밖에서 1회만 호출 (`evals/run_eval.py:29`). 재시도 없음. 파일/DB 결과 출력 없음. `sys.path` 조작 없음.
- 자격증명·키 하드코딩 없음 (`evals/run_eval.py`, `t2s/evaluate.py` 전수 확인 — settings 는 `load_settings()` 경유).
- `t2s/graph.py`, `t2s/cli.py` 미생성. `requirements.txt` 무변경.

## 커밋 전 조치

1. `evals/golden.jsonl` 을 이번 커밋에 반드시 포함할 것 (발견 사항 1). 포함하지 않으면 이후 "골든셋 무변경" 검증이 계속 무의미해진다.
2. 나머지는 없음. 판정은 PASS_WITH_NITS 이므로 위 4개 경미 항목은 커밋을 막지 않는다.