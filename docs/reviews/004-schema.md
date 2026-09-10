# 리뷰: 004-schema

- 대상 스펙: docs/specs/004-schema.md
- 판정: **FAIL** (코드 로직은 전부 정확. 수용 기준 #1 의 기대값이 스펙 오류라 1개 테스트가 red — 아래 재작업 지시문 1곳만 고치면 PASS)
- 변경 규모: 수정 2 (t2s/db.py +50/-3, tests/test_db.py +160/-2) + 신규 2 (t2s/schema.py 52줄, tests/test_schema.py 200줄)

## 실행한 검증

| 명령 | 실제 결과 |
|---|---|
| `docker compose -f docker/docker-compose.yml up -d` | `Container t2s-sakila Running` |
| `pytest tests/test_schema.py -v` | **23 passed**, failed 0 / error 0 / skipped 0 |
| `pytest tests/test_db.py -v` | **1 failed, 38 passed**, skipped 0. 실패 1개 = 수용 기준 #1 (아래 발견 사항 참고) |
| `pytest tests/ -q` | **1 failed, 111 passed**, skipped 0. 73개 요구 충족. 001·002·003 기존 테스트 전부 통과 |
| `git diff --stat t2s/guard.py t2s/config.py` | **빈 출력** (guard 무변경 확인) |
| `git diff --stat t2s/db.py` | `1 file changed, 50 insertions(+), 3 deletions(-)` |
| `t2s/schema.py` import AST 검사 | `['t2s.db']` — `pymysql`/`os`/`dotenv` 부재 확인 |
| 렌더 결과 실측 | 첫 줄 `2549 17`, 이어서 16개 TABLE 줄. #15·#16·#17 기대 문자열과 눈으로 일치 확인 |
| 라이브 DB 실측 | `SELECT DATA_TYPE, COLUMN_TYPE ... TABLE_NAME='actor' AND COLUMN_NAME='actor_id'` → `('int', 'int unsigned')` |

## 수용 기준 대조

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1 | `fetch_schema(settings)[0]` == `ColumnInfo(..., column_type="int", ...)` | **실패** | tests/test_db.py:152. 실측 `column_type == 'int unsigned'` (아래 [심각]) |
| 2 | `len(fetch_schema(settings)) == 131` | 통과 | 기존 테스트 그대로 (test_db.py) |
| 3 | film.rating `data_type`/`column_type` 분리 | 통과 | tests/test_db.py:212 `test_fetch_schema_film_rating_data_type_vs_column_type` |
| 4 | film.special_features SET 원문 | 통과 | tests/test_db.py:225 |
| 5 | customer.active `tinyint(1)` | 통과 | tests/test_db.py:237 |
| 6 | film.length `smallint unsigned` 원문 보존 | 통과 | tests/test_db.py:248 |
| 7 | FK 22개 | 통과 | tests/test_db.py:255 |
| 8 | FK 첫 행 address.city_id -> city.city_id | 통과 | tests/test_db.py:259 |
| 9 | film 의 FK 2개, 모두 language 참조 | 통과 | tests/test_db.py:272 |
| 10 | `fetch_foreign_keys` 시그니처 `["settings"]` | 통과 | tests/test_db.py:281 |
| 11 | 반환 `tuple[ForeignKey, ...]` | 통과 | tests/test_db.py:285 |
| 12 | 렌더 `len==2549`, `17` 줄 | 통과 | tests/test_db.py:291. 실측 명령으로도 `2549 17` 확인 |
| 13 | `include_views=True` `len==3503`, `24` 줄 | 통과 | tests/test_db.py:297 |
| 14 | 첫 줄 헤더 | 통과 | tests/test_db.py:307 |
| 15 | 마지막 줄 store | 통과 | tests/test_db.py:312 |
| 16 | film_actor 줄 (PK+FK 동시) | 통과 | tests/test_db.py:320 |
| 17 | film 줄 완전 일치 | 통과 | tests/test_db.py:328 |
| 18 | 기본 출력에 `VIEW ` 부재 | 통과 | tests/test_db.py:341 |
| 19~30 | `short_type` 12개 케이스 | 통과 | tests/test_schema.py:20~82 |
| 31 | `render_schema((), ())` → 헤더만 | 통과 | tests/test_schema.py:86 |
| 32~36 | 최소 케이스 / PK / FK / PK+FK / nullable 미출력 | 통과 | tests/test_schema.py:91~132 |
| 37 | 첫 등장 순서 보존 (b 먼저) | 통과 | tests/test_schema.py:136 |
| 38~39 | 뷰 제외 기본 / `include_views` KIND=VIEW | 통과 | tests/test_schema.py:150, 164 |
| 40 | FK 중복 키 첫 값 사용 | 통과 | tests/test_schema.py:179 |
| 41 | import 목록 `["t2s.db"]` | 통과 | tests/test_schema.py:191 + AST 검증 명령 |

41개 전부 테스트로 존재하고, #1 하나만 실패다. 기대값을 코드에 맞춰 바꿔치기한 테스트는 없다 (실패 1개가 오히려 그 증거다).

## 발견 사항

### [심각] 수용 기준 #1 기대값이 스펙 자체의 오류 — `column_type="int"` vs 실측 `"int unsigned"`

- 어디서: docs/specs/004-schema.md 수용 기준 표 #1 (`column_type="int"`) ↔ tests/test_db.py:148 (`column_type="int"`).
- 실측: 라이브 컨테이너에서 `actor.actor_id` 는 `DATA_TYPE='int'`, `COLUMN_TYPE='int unsigned'`. 즉 **코드(`t2s/db.py:128` `column_type=row[4]`, 원문 그대로)는 정확하고, 스펙 표의 기대값이 틀렸다.**
- 구현 세션은 이미 스펙 "질문" 절(004-schema.md:375)에 이 사실을 보고했고, 테스트 기대값을 코드에 맞추는 것이 금지되어 있어 테스트를 스펙 그대로 두고 실패로 보고했다 — 절차상 올바른 행동이다.
- 스펙 질문 절의 분석대로 **선택지 B(fetch_schema 가 unsigned 를 잘라 반환)는 수용 기준 #6(`film.length` → `column_type == "smallint unsigned"` 원문 보존)과 정면으로 모순**되므로 유일하게 일관된 해는 **선택지 A(테스트 기대값을 실측값으로 고침)** 다.
- 이것은 구현 결함이 아니라 스펙 기재 오류다. 코드 변경은 0, 테스트 기대값 1토큰 수정이 전부다.

### [경미] `db.py` 삽입 50줄 — 스펙 검증 명령의 "40줄 이내" 초과

- t2s/db.py +50/-3. 스펙 검증 절 기준(40줄 이내)을 10줄 넘는다. 단, 100줄 재작성 기준은 아니다.
- 실제 내용을 보면 스펙이 요구한 것 외에 없다: `ColumnInfo` 필드 1줄, `SCHEMA_SQL` 1줄 교체, 인덱스 보정 3줄, `ForeignKey` 7줄, `FK_SQL` 8줄, `fetch_foreign_keys` 27줄 — 스펙 계약(004-schema.md:106~138)이 요구하는 분량 자체가 약 45줄이라 스펙 측 산출 미달이다. 범위 이탈 아님. 스펙 작성 시 수치를 다음 스펙부터 여유 있게 잡을 것.

### [경미] tests/test_schema.py 최상위 `import inspect` 미사용

- tests/test_schema.py:1 의 `import inspect` 는 사용되지 않는다 (#41 이 함수 내부에서 다시 import 한다). 동작에 영향 없음. 다음 스펙에서 정리.

### [참고] 줄바꿈 없는 EOF, 스펙 번호 혼선

- t2s/db.py 와 tests/test_db.py 의 EOF 개행 부재는 003 커밋분부터 존재하던 상태다(이번 변경으로 새로 생기지 않았다). test_db.py 끝에 추가된 150줄은 개행 없이 붙었으므로 커밋 전 파일 끝 개행을 넣으면 diff 가 더 깔끔해진다(선택).
- 스펙 본문이 "단, #19~#22 는 DB 필요 → test_db.py 에 넣는다"(004-schema.md:226)라고 썼는데, 표 번호상 DB 가 필요한 것은 #12~#18 이다. 구현은 의도대로 #12~#18 을 test_db.py 에 넣어 correctly 처리했다. 스펙 쪽 오타.

## 보안 경계

- `FK_SQL` 은 스키마 이름을 `%s` 바인딩으로 넣는다 (t2s/db.py:141). 문자열 포맷팅 없음.
- `fetch_foreign_keys` 는 `ensure_safe_sql` 을 우회하지 않는다 — guard 를 호출하지 않을 뿐 LLM 입력 경로가 아니므로 스펙 설계대로다. guard 무변경 확인됨.
- 자격증명 변화 없음. `t2s_ro` 만 사용 (tests/test_db.py fixture 실측 출력 참고).
- `render_schema` 는 I/O 가 없고 예외를 삼키지 않으며 (t2s/schema.py:9~52), DB 모듈 import 는 타입 정의뿐 — 스펙 설계결정 4 가 허용한 범위다.

## 커밋 전 조치

없음 (구현 자체에 대한 조치는 없다). 아래 재작업 지시문을 실행한 뒤 다시 판정받을 것.

## 구현 세션 재작업 지시문

스펙 표 #1 의 기대값은 스펙 작성 오류로 확정됐다 (선택지 B 는 수용 기준 #6 과 모순 → 선택지 A 채택). 라이브 컨테이너 실측값 `('int', 'int unsigned')` 가 근거다.

1. `tests/test_db.py` 의 `test_fetch_schema_first_row_is_actor_id` 에서 `column_type="int"` 를 `column_type="int unsigned"` 로 고친다. 이 한 토큰 외에 아무것도 바꾸지 마라.
2. `pytest tests/test_db.py -v` 로 `39 passed, 0 failed` 를 확인하고, `pytest tests/ -q` 로 `112 passed, 0 failed, 0 skipped` 를 확인한다.
3. `tests/test_db.py` 파일 끝에 개행을 붙인다 (선택, diff 청결용).
4. 스펙 표 #1 의 `column_type="int"` 도 `column_type="int unsigned"` 로 정정 요청을 사람에게 전달한다 (스펙 파일은 구현 세션이 고치는 곳이 아니다).