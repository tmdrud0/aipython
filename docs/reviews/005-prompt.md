# 리뷰: 005-prompt

- 대상 스펙: docs/specs/005-prompt.md
- 판정: **PASS_WITH_NITS** (계약·수용 기준·범위 전부 준수. 심각 항목 없음. EOF 개행 등 사소한 항목만 있음)
- 변경 규모: 신규 2 (t2s/prompt.py 104줄 / 3,237 bytes, tests/test_prompt.py 203줄 / 6,460 bytes) + 스펙 문서 자체 (docs/specs/005-prompt.md, 구현 산출물 아님). **수정 파일 0개**

## 실행한 검증

| 명령 | 실제 결과 |
|---|---|
| `pytest tests/test_prompt.py -v` | **32 passed**, failed 0 / error 0 / skipped 0, 0.02s. 파라미터 21케이스 전부 PASSED |
| `pytest tests/ -q` | **144 passed**, failed 0 / error 0 / skipped 0 (= 기존 112 + 신규 32). 001~004 기존 테스트 전부 통과 |
| prompt.py AST import 검사 | `['dataclasses', 'json', 're']` — 스펙 기대 출력과 정확히 일치. `ollama`/`pymysql`/`t2s.*`/`os` 부재 |
| `git diff --stat t2s/guard.py t2s/config.py t2s/db.py t2s/schema.py t2s/__init__.py` | **빈 출력** (tracked 파일 수정 전무, `git status` = 신규 3개만) |
| `print(len(SYSTEM_PROMPT), len(SYSTEM_PROMPT.splitlines()))` | **`699 19`** — 스펙 기대값과 일치 |
| `extract_sql('```sql\nWITH t AS (SELECT 1 AS a) SELECT * FROM t\n```')` | `Extraction(sql='WITH t AS (SELECT 1 AS a) SELECT * FROM t', kind='sql')` — 기대 출력 일치 |
| 스펙↔구현 리터럴 비교 (python difflib, 문자 단위) | `SYSTEM_PROMPT` **완전 일치** (diff 가 차이를 하나도 내지 않음), `FENCE`·`SQL_START` 정규식 문자열 **완전 일치**, `THINK_END`·`UNSUPPORTED`·`EXTRACTION_KINDS` **완전 일치** |
| THINK_END 원문 확인 | 길이 8, 코드포인트 `< / t h i n k >` — `</think>` 리터럴이 정확히 들어있다 (터미널 표시에서 태그가 생략되어 보이는 것과 무관하게 원문 검증) |

추가 엣지 프로브 (스펙 표에 없는 경로, 전부 스펙 계약대로 동작):

```
extract_sql('```JSON\n{"sql": "SELECT 1"}\n```')  → Extraction(sql='SELECT 1', kind='sql')          # lang 소문자화 (계약 3번)
extract_sql('{"sql": "DROP TABLE film"}')         → Extraction(sql='', kind='unparsable')           # SQL_START.match 실패 (설계결정 8)
extract_sql('{"sql": 123}')                       → Extraction(sql='', kind='unparsable')           # sql 비-str → JSON 경로 스킵
extract_sql('```json\nnot json\n```\nSELECT 1 LIMIT 1') → Extraction(sql='SELECT 1 LIMIT 1', kind='sql')  # JSON 파싱 실패 → 다음 경로
extract_sql('text\r\n```sql\r\nSELECT 1\r\n```')  → Extraction(sql='SELECT 1', kind='sql')          # CRLF 펜스 (FENCE 의 \r?\n)
```

## 수용 기준 대조

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1~21 | `extract_sql` 실측 응답 8 + 변형/경계 13 | **전부 통과** | tests/test_prompt.py:17~128 `@pytest.mark.parametrize` 21행, 파라미터명 `raw, expected_sql, expected_kind`, 개수 21 = 표 행수 일치. `assert result == Extraction(...)` 전체 `==` 비교 (test_prompt.py:127) |
| 22 | `build_messages` 리스트 전체 `==` | 통과 | test_prompt.py:132~140 |
| 23 | `[0]["content"] is SYSTEM_PROMPT` | 통과 | test_prompt.py:144~146 (`is` 단언) |
| 24 | 빈 질문 `"S\n\nQuestion: "` | 통과 | test_prompt.py:150~152 |
| 25 | strip 없음 | 통과 | test_prompt.py:156~158 |
| 26 | 길이 2 | 통과 | test_prompt.py:162~163 |
| 27 | SYSTEM_PROMPT 4개 포함 단언 | 통과 | test_prompt.py:167~171 |
| 28 | startswith 첫 줄 | 통과 | test_prompt.py:175~178 |
| 29 | `EXTRACTION_KINDS` 튜플 일치 | 통과 | test_prompt.py:182~183 |
| 30 | 모든 결과의 kind ∈ EXTRACTION_KINDS | 통과 (파라미터 테스트에 흡수됨) | test_prompt.py:128 — 21케이스 각각에 대해 단언. 별도 테스트로 분리되진 않았으나 집계 테스트보다 강한 형태로 전부 커버됨 |
| 31 | frozen (`FrozenInstanceError`) | 통과 | test_prompt.py:187~190 |
| 32 | `extract_sql` 인자 `["text"]` | 통과 | test_prompt.py:194~195 |
| 33 | `build_messages` 인자 목록 | 통과 | test_prompt.py:199~203 |

테스트 규칙 준수 확인:

- 규칙 1 (행을 합치거나 빼지 않는다): #30 하나만 파라미터 테스트의 추가 단언으로 흡수됐고 나머지 32행은 1:1 대응. 빠진 행 없음.
- 규칙 2 (금지 import 없음): 테스트 import 는 `inspect`, `dataclasses.FrozenInstanceError`, `pytest`, `t2s.prompt` 뿐 (test_prompt.py:1~12). `pymysql`/`ollama`/`t2s.config`/`t2s.db`/`t2s.schema`/`t2s.guard` 전부 부재.
- 규칙 3 (파라미터 개수 = 표 행수): 21 = 21.
- 규칙 4 (dataclass 전체 `==`): test_prompt.py:127.
- 규칙 5 (이스케이프된 입력): AST 스캔 결과 모든 입력이 단일행 리터럴 + `\n` 이스케이프. 실제 줄바꿈이 들어간 리터럴 0개.
- 규칙 6 (`_from_sql_text` 직접 테스트 없음): 테스트 import 목록에 없음.

## 발견 사항

### 심각 항목

**없음.** 계약(시그니처·3-way `Extraction`·경로 우선순위), 설계결정 1~8, 범위, 보안 경계 전부 준수다.

### [경미] 신규 파일 2개 모두 EOF 개행 없음

- t2s/prompt.py (3,237 bytes) 와 tests/test_prompt.py (6,460 bytes) 가 둘 다 개행 없이 끝난다.
- 004 리뷰에서 지적한 것과 같은 패턴이고 기존 커밋분 파일들도 같은 상태라 동작에는 영향 없음. 커밋 전에 개행을 넣으면 diff 가 더 깔끔해진다 (선택).

### [경미] 테스트 아이템 수 32 = 수용 기준 33행 − #30 (흡수)

- 스펙 표는 33행인데 pytest 수집은 32개다. #30 이 별도 테스트가 아니라 파라미터 테스트 내부의 `assert result.kind in EXTRACTION_KINDS` (test_prompt.py:128) 로 처리됐기 때문이다. 21케이스 각각에 대해 단언하므로 커버리지는 오히려 더 강하고, 스펙 규칙 3 이 extract_sql 케이스의 묶음을 허용하므로 위반으로 보지 않는다. 다음 스펙부터는 이런 "전 케이스 공통 단언" 행은 파라미터 테스트에 흡수해도 된다고 명시해두면 카운트 혼선이 없을 것.

### [참고] 스펙 산출치와의 소폭 차이 — 문제 없음

- 스펙 예상 분량 "약 240줄" 대비 실측 307줄 (prompt.py 104 + test_prompt.py 203). 표 33행 + 서술 테스트를 다 넣으면 나오는 분량이라 스펙 측 추정 미달이지 구현 과다가 아니다. 004 때와 같은 유형이다.

## 보안 경계

- `t2s/prompt.py` 는 I/O·네트워크·DB 접근이 전혀 없고 (AST 검증으로 import 가 `dataclasses`/`json`/`re` 셋뿐임을 확인), SQL 을 실행하지 않는다. guard 우회 경로 없음.
- `SYSTEM_PROMPT` 에 자격증명·키·민감 정보 없음. "at most 200" 이 guard 의 `MAX_ROWS` 와 같은 값임을 확인했고, 스펙 지시대로 import 조립이 아닌 리터럴이다 (설계결정 3).
- guard·config·db·schema·`__init__.py` 무변경 (`git diff --stat` 빈 출력 실측). requirements.txt 변경 없음.
- `extract_sql` 은 안전성을 판단하지 않는다 (설계결정 8) — `{"sql": "DROP TABLE film"}` 이 `unparsable` 로 나오는 것은 안전 판단이 아니라 `SELECT`/`WITH` 시작 조건 때문이며, 스모크 테스트로 그 동작을 확인했다. 금지 키워드 목록 복사 없음.

## 커밋 전 조치

필수 없음. 선택 사항:

1. t2s/prompt.py 와 tests/test_prompt.py 파일 끝에 개행 추가 (diff 청결용).
2. 커밋 메시지에는 이 파일 두 개와 docs/specs/005-prompt.md 를 함께 넣을지 사람이 판단 (스펙 문서는 이번 스펙의 산출물).