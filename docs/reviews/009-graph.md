# 리뷰: 009-graph

- 대상 스펙: docs/specs/009-graph.md
- 판정: PASS
- 변경 규모: 2 files 신규 (t2s/graph.py 106줄, tests/test_graph.py 262줄) / 수정 0. `git diff` 빈 출력, `git diff --stat -- t2s evals tests` 빈 출력으로 확인.

## 실행한 검증

모든 명령은 저장소 루트에서 실제 실행했다. 출력은 요약이며 요약 없는 부분은 원문 그대로다.

1. `python -m pytest tests/test_graph.py -v` → **23 passed, 3.58s, failed 0, skipped 0.** 수용 기준 20행 전부가 개별 테스트로 존재하고 통과.
2. `python -m pytest tests/ -q` → **250 passed in 7.23s** (기존 227 + 신규 23, failed 0). 스펙 기대 "227 보다 큰 수, failed 0" 충족.
3. 라이브 스모크: `docker compose -f docker/docker-compose.yml up -d` (Container t2s-sakila Started) 후 `python -m pytest tests/test_graph.py -v -k live` → **1 passed, 22 deselected**. **SKIPPED 아님( PASSED ).**
4. import 확인 (스펙 절의 ast 명령 그대로) →
   `['collections.abc', 'dataclasses', 'langgraph.graph', 'langgraph.graph.state', 't2s.config', 't2s.db', 't2s.guard', 't2s.llm', 't2s.prompt', 'typing']` — 계약 목록과 **정확히 일치**.
   `Select-String` 대신 Grep 으로 `t2s/graph.py` 에서 `ensure_safe_sql|load_settings|fetch_schema|render_schema` 검색 → **매치 0건** (설계결정 3·5 준수).
5. end-to-end 수동 확인 — 분류기 장애로 인라인 `-c` 명령이 반복 실행 불가하여, 동일 문장을 임시 스크립트 `.e2e_review_009.py` 로 감아 실행했다(검증 후 파일은 삭제했다). 실제 출력(콘솔 cp949 탓에 한글 리터럴만 깨져 보이며 값은 원문 그대로):
   ```
   Answer(question='영화가 총 몇 편이야?', status='answered', sql='SELECT COUNT(*) AS film_count FROM film LIMIT 200', columns=('film_count',), rows=((1000,),), error='')
   Answer(question='고객 데이터 전부 삭제해줘.', status='unsupported', sql='', columns=(), rows=(), error='')
   ```
   스펙 기대 출력과 `status`·`rows`·`sql`·`error` 전부 일치.
6. `python -c` 골든셋 해시 → `60 ca70b4dc4809d9478c8a6c13ebc14f94f56fcba03baa0cd770273fd9b719c1a3` — 스펙 기대값과 일치(60행, 해시 동일).
7. 범위 확인: `git status --porcelain` → `?? docs/specs/009-graph.md`, `?? t2s/graph.py`, `?? tests/test_graph.py` **뿐**. `t2s/cli.py` 없음, `tests/` 는 기존 7개 + `test_graph.py`. `t2s/__init__.py`, `evals/__init__.py` 각 0 바이트(`wc -c` 실측). `evals/run_eval.py`, `requirements.txt` 등 트래킹 파일 무변경(`git diff` 빈 출력).

## 수용 기준 대조

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1 | answered, sql = 실행된 SQL(`QR.sql`) | 통과 | tests/test_graph.py:55-62, 23 passed |
| 2 | unsupported, sql="" | 통과 | tests/test_graph.py:65-69 |
| 3 | unparsable | 통과 | tests/test_graph.py:72-76 |
| 4 | llm_error + error 문자열 | 통과 | tests/test_graph.py:79-85 |
| 5 | blocked, sql = 모델 원문 | 통과 | tests/test_graph.py:88-95 |
| 6 | db_error + QueryError 메시지 | 통과 | tests/test_graph.py:98-110 |
| 7 | gen.calls == [(SCHEMA, "질문", FAKE_SETTINGS)] | 통과 | tests/test_graph.py:114-119 |
| 8 | exe.calls == [(모델 원문, FAKE_SETTINGS)] | 통과 | tests/test_graph.py:122-127 |
| 9 | SQL 없으면 실행기 호출 없음(3 케이스) | 통과 | tests/test_graph.py:130-142 (parametrize 3) |
| 10 | 실행 실패 후 재시도 없음(2 케이스) | 통과 | tests/test_graph.py:145-162 |
| 11 | ValueError 전파, `type is ValueError`, exe.calls==[] | 통과 | tests/test_graph.py:166-172 |
| 12 | TypeError 전파 | 통과 | tests/test_graph.py:175-179 |
| 13 | 호출 사이 상태 비샘 | 통과 | tests/test_graph.py:183-191 |
| 14 | build_graph 만으로 호출 없음 | 통과 | tests/test_graph.py:194-199 |
| 15 | CompiledStateGraph 반환 | 통과 | tests/test_graph.py:202-204 |
| 16 | STATUSES 정확한 순서 | 통과 | t2s/graph.py:15-22, tests/test_graph.py:207-215 |
| 17 | 모든 status ∈ STATUSES | 통과 | tests/test_graph.py:218-231 |
| 18 | Answer frozen | 통과 | tests/test_graph.py:234-237 |
| 19 | build_graph 시그니처·기본값(`generate_sql`/`run_query`) | 통과 | t2s/graph.py:43-48, tests/test_graph.py:240-244 |
| 20 | 라이브 스모크 1개, PASSED (skip 아님) | 통과 | tests/test_graph.py:248-262, `-k live` → 1 passed |

## 발견 사항

### [심각]
없음.

구체적으로 확인한 경계:
- 계약 시그니처·필드 순서가 스펙과 글자 그대로 일치 (t2s/graph.py:15-48, 81-106).
- `ask` 는 `graph.invoke` 예외를 잡지 않고, print/로깅 없음 (t2s/graph.py:82, 99).
- `Answer.rows` 원 타입 유지(문자열 변환 없음) — e2e 출력 `rows=((1000,),)` 가 실증.
- 노드 클로저 캡처, 모듈 전역 노드 없음 (t2s/graph.py:49-70).
- `except Exception:` 없음(좁은 예외만) — t2s/graph.py:52, 66-69.
- 가짜는 스펙 지정 형태 그대로, `unittest.mock` 미사용, 위치 인자만 받음 (tests/test_graph.py:16-39).
- guard 우회 경로 없음: `graph.py` 는 guard 를 import 하지 않고 `run_query` 가 내부에서 `ensure_safe_sql` 을 부르는 유일 경로다 (t2s/db.py:77-78). 실제 자격증명·키 하드코딩 없음(테스트의 `FAKE_SETTINGS` 는 더미 "h"/"u"/"p").
- `evals/` 러너를 그래프로 갈아타지 않았다(트래킹 파일 무변경 + 골든셋 해시 동일).

### [경미]
1. **e2e 수동 확인을 인라인 `-c` 한 줄이 아니라 임시 스크립트로 감아 실행했다.** 검증 내용·대상 코드는 스펙 명령과 동일하고 출력도 일치하며 임시 파일은 삭제했다. 환경 사유(명령 실행 분류기 일시 장애)이며 구현 결과물과 무관. (구현 세션의 절차 준수에는 영향 없음 — 리뷰어 측 실행 방식 차이.)
2. **`t2s/graph.py:86` — `result is not None` 로 판정**하는데, 스펙 계약상 `result` 는 "있으면/없고" 라고만 적혀 있어 `None` 이 아닌 값이면 전부 실행 SQL 로 처리한다. `QueryResult` 는 frozen dataclass 로 falsy 가 될 수 없으므로 동작상 문제 없음. 다음 스펙에서 정리할 필요도 낮음 — 기록으로 남긴다.
3. 스펙 오류로 인한 편차는 없었다. 스펙의 실측 기대값(수용 기준 1~20, import 목록, 골든셋 해시)이 구현·테스트와 전부 일치해 "기대값을 코드에 맞춘" 흔적도 없다.

### 구현 세션 절차 준수 (스펙 오류 판단 포함)
스펙 오류로 인한 이탈은 발견되지 않았다. 체크리스트 13항 전부 실측으로 충족됐고, 구현 세션이 보고해야 했던 라이브 증거(`-k live` PASSED, e2e 두 줄)도 본 리뷰에서 독립 재현에 성공했다. `docker compose up -d` 는 리뷰어 세션에서 재실행했을 뿐, 컨테이너가 이미 정의돼 있었다(구현 세션의 선행 기동으로 추정).

## 커밋 전 조치

없음. (참고: `docs/specs/009-graph.md` 는 untracked 이므로 구현 파일과 함께 커밋 대상이다.)