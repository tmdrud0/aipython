# 리뷰: 002-guard

- 대상 스펙: specs/002-guard.md
- 판정: PASS
- 변경 규모: 4 files (신규 3: t2s/guard.py 195행, tests/test_guard.py 131행, specs/002-guard.md / 수정 1: requirements.txt +1/-1)

## 실행한 검증

스펙 "검증 명령" 절을 저장소 루트에서 그대로 실행했다. (`&&` 미사용.)

1. `.\.venv\Scripts\python.exe -m pytest tests/test_guard.py -v`
   → **38 passed, 0 failed, 0 error, 0 skipped**. 파라미터 33개(통과 18 + 실패 15) + 단일 테스트 5개 전부 PASSED.
2. `.\.venv\Scripts\python.exe -m pytest tests/ -q`
   → **50 passed**. (001 의 12개 포함, failed/error/skipped 0)
3. AST import 검사
   → 출력 `['re']`. 설계결정 1·2(파서 라이브러리 금지, 순수 함수 모듈) 충족.
4. `git diff --stat requirements.txt`
   → `1 file changed, 1 insertion(+), 1 deletion(-)`. diff 내용은 마지막 줄 `pytest==9.1.1` 뒤 개행 추가가 전부. 내용·순서·버전 무변경. (경고 "LF will be replaced by CRLF" 는 저장소 autocrlf 설정에 따른 것으로 내용 변경이 아님.)
5. 표 밖 경계값 추가 탐침(구현 직접 호출): `--` 문자열 끝, `;` 뒤 주석, 백틱 이중 이스케이프 `` `a``b` ``, 리터럴 안 `--`, 더블쿼트 리터럴, `/* a /* b */`, 개행 종료 줄 주석, `sys_log`(접두사 오탐 없음), `sys.x`(차단) — 전부 스펙 규칙과 일치.

## 수용 기준 대조

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1–8, 11–16, 21–24 | 통과 케이스 18행, 완전 일치 `==` | 통과 | tests/test_guard.py:6–52 (`test_pass_cases` 18 파라미터), 실행 38 passed |
| 9,10,17–20,25–30 | 실패 케이스 12행, 메시지 `==` 완전 일치 | 통과 | tests/test_guard.py:57–96 (`test_fail_cases`, `pytest.raises` + `str(exc.value) == message`, `match=` 미사용) |
| 28 | 기대 메시지가 `OUTFILE` 이어야 함(선언 순서) | 통과 | tests/test_guard.py:79, guard.py:34–35 튜플 순서상 OUTFILE(25번째) < INTO(32번째) |
| 31 | 빈/공백/주석뿐 3개 파라미터 | 통과 | tests/test_guard.py:88–90 |
| 32 | `max_rows=10` 인자 전달 | 통과 | tests/test_guard.py:100–101 |
| 33 | `max_rows=0` → 맨 `ValueError`, `type(exc.value) is ValueError` | 통과 | tests/test_guard.py:105–109 |
| 34 | `max_rows=True` bool 배제 | 통과 | tests/test_guard.py:113–117 |
| 35 | `sql` 비-str → `TypeError` | 통과 | tests/test_guard.py:121–124 |
| 36 | 순수성(동일 입력 → 동일 출력) | 통과 | tests/test_guard.py:128–131 |
| — | 테스트 규칙: DB/네트워크/monkeypatch/tmp_path/pymysql 금지 | 준수 | tests/test_guard.py 에 해당 요소 없음 |
| — | `_normalize` 직접 테스트 금지 | 준수 | import 가 `UnsafeSQLError, ensure_safe_sql` 뿐 (tests/test_guard.py:3) |

## 발견 사항

### [심각]
없음.

### [경미]
1. **스펙 자체의 번호 불일치(구현 문제 아님)** — specs/002-guard.md 테스트 규칙 5 의 "#29, #30" 은 ValueError/TypeError 케이스를 가리키지만, 같은 문서의 수용 기준 표에서 #29/#30 은 시스템 스키마 케이스다. 테스트 파일은 추가 케이스 표(#33–#35) 기준으로 올바르게 작성해 실제 동작에는 문제 없다. 다음 스펙 작성 시 문서 번호를 정리할 것.
2. **`guard.py:161` bool/int 검사 조건 순서** — `isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1` 로 스펙 규칙 1 의 의도(bool 도 ValueError)를 정확히 충족한다. 지적으로만 기록: 규칙 서술의 나열 순서와 논리 순서만 다를 뿐 결과는 동일. 조치 불필요.

### 보안 경계 점검
- `/*!` 실행 주석 즉시 차단 (t2s/guard.py:70–71)
- 다중 스테이트먼트 검출이 키워드 검사보다 선행 (t2s/guard.py:175 vs 184) — `SELECT 1; DROP TABLE film` 이 세미콜론에서 먼저 걸림 확인
- 리터럴 마스킹 후 키워드 검사라 `'DROP TABLE film'` 오탐 없음 (t2s/guard.py:184–186, 마스킹된 사본 기준)
- `OUTFILE` 이 `INTO` 보다 선언 순서상 먼저라 우회 메시지 왜곡 없음, 둘 다 튜플에 존재
- `sys` 접두사 오타 없음(`\bsys\s*\.` 만 차단, guard.py:189) — `sys_log` 통과, `sys.x` 차단 탐침으로 확인
- 자격증명·비밀번호·키 하드코딩 없음. `os.environ`/`print`/`logging`/DB 접속 없음(AST 검사로 `re` 단일 import 확인)
- `t2s/__init__.py` 0바이트 유지, re-export 없음 (git status 에 미등장)
- `t2s/config.py`, `tests/test_config.py` 무변경 (git status 에 미등장)

## 커밋 전 조치

없음. (참고: 커밋 시 autocrlf 경고로 requirements.txt 가 CRLF 로 정규화될 수 있으나 내용 변화는 없다.)

## GLM 재작업 지시문

해당 없음 (PASS).