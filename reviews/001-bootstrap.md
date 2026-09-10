# 리뷰: 001-bootstrap

- 대상 스펙: specs/001-bootstrap.md
- 판정: **PASS**
- 변경 규모: 신규 5 files, +226 / -0 (전부 untracked 신규. `git diff` 는 비어 있고 기존 추적 파일 수정 0건)

## 실행한 검증

스펙 "검증 명령" 절을 그대로 실행했다 (venv·설치·컨테이너는 이미 완료 상태라 재실행 대신 상태 확인).

| 명령 | 결과 |
|---|---|
| `Test-Path .venv\Scripts\python.exe` | OK. `--version` → `Python 3.12.10` (스펙 설계결정 4 준수) |
| `pip freeze \| Select-String "PyMySQL\|python-dotenv\|ollama\|langgraph\|langchain-core\|pytest"` | 6개 전부 `requirements.txt` 와 **버전 일치**. `langgraph-checkpoint==4.2.0`, `langgraph-prebuilt==1.1.0`, `langgraph-sdk==0.4.4` 는 langgraph 의 전이 의존성이며 `requirements.txt` 에는 없다 → 규칙 위반 아님. 스펙 "질문 1"의 `ResolutionImpossible` 은 **발생하지 않았다** |
| `python -m pytest tests/ -v` | `12 passed in 0.07s`. **failed 0, error 0, skipped 0** |
| `git status --short` | `.env`, `.venv/` 없음. untracked 는 `.env.example`, `requirements.txt`, `specs/001-bootstrap.md`, `t2s/__init__.py`, `t2s/config.py`, `tests/test_config.py` 뿐 |
| `git check-ignore -v .env` | `.gitignore:8:.env` — 기존 규칙으로 이미 제외. `.gitignore` 수정 흔적 없음 |
| `git diff` / `git diff --stat` | 빈 출력 = 기존 파일 무수정. `docker/`, `docs/WORKFLOW.md`, `readme.md`, `.gitignore` 전부 무변경 |

`skipped 0` 이므로 수용 기준 #10(실제 DB 접속)이 **skip 되지 않고 실제로 통과**했다 — `SELECT COUNT(*) FROM film == 1000` 이 라이브 컨테이너에 대해 단언됐다.

## 수용 기준 대조

| # | 기준 | 결과 | 근거 |
|---|---|---|---|
| 1 | 7키 유효 → Settings 전체 일치 + `db_port` int | PASS | tests/test_config.py:26-40. `assert isinstance(settings.db_port, int)` (line 40) 포함 |
| 2 | 앞뒤 공백 strip | PASS | tests/test_config.py:43-48 ← t2s/config.py:39 `.strip()` |
| 3 | 단일 누락 메시지 | PASS | tests/test_config.py:51-58, 정확 문자열 비교 |
| 4 | 2개 누락, 선언 순서 | PASS | tests/test_config.py:61-71. t2s/config.py:41 이 `REQUIRED_KEYS` 순회로 순서 보장 (정렬 없음) |
| 5 | 공백만 → 빈 문자열 취급 | PASS | tests/test_config.py:74-80 |
| 6 | `"abc"` → 정수 아님 메시지 | PASS | tests/test_config.py:83-91 ← config.py:46-49 |
| 7 | `"0"` / `"65536"` | PASS (2개 함수) | tests/test_config.py:94-102, 105-113 ← config.py:50-51 |
| 8 | `"1"` / `"65535"` | PASS (2개 함수) | tests/test_config.py:116-121, 124-129 |
| 9 | 부재 경로 + 환경변수 → 정상 | PASS | tests/test_config.py:132-137 ← config.py:37 (`load_dotenv` 는 파일 부재 시 예외 없음) |
| 10 | 실 `.env` + 컨테이너 → 1000 | PASS (skip 아님) | tests/test_config.py:140-165. `load_settings()` 무인자(142), `ConfigError`→skip(144), `OperationalError`→skip(155-156), `try/finally` 로 close(162-163) |

10행 → 12개 함수, 함수 개수도 스펙 기대치와 일치. **기대값을 코드에 맞춰 바꿔치기한 테스트는 없다** — 메시지는 전부 스펙 문자열과 `==` 비교이고 하드코딩된 기대값이 스펙 표와 글자 단위로 같다.

## 계약 준수

- `t2s/config.py:8-9` `ConfigError(RuntimeError)`, `:12-20` `@dataclass(frozen=True) Settings` 7필드 순서·타입 그대로, `:23-31` `REQUIRED_KEYS: tuple[str, ...]` 7개 선언 순서 그대로, `:34` `load_settings(env_path: str | None = None) -> Settings` — 시그니처 전부 스펙과 글자 일치.
- 동작 규칙 1~8 순서대로 대조: 1 → `:35-36` (`Path(__file__).resolve().parent.parent / ".env"`, cwd 비의존) / 2 → `:37` (`override=False`) / 3 → 예외 처리 없이 진행 / 4 → `:39` / 5 → `:41-43` / 6 → `:45-51` / 7 → `:53-61` / 8 → print·logging 없음. **전부 준수.**
- `t2s/__init__.py` = 0 바이트 (확인: `wc -c` → 0).
- `.env.example` 7키, `T2S_` 접두사, 값은 스펙 리터럴 그대로. `docker/initdb/03-readonly-user.sql:3-4` 의 `t2s_ro`/`t2s_ro_pw` 및 `docker/docker-compose.yml:17` 의 `3310:3306` 과 교차 확인 완료 — 새 계정·다른 포트 없음.
- `requirements.txt` 6줄, 순서·버전 스펙과 동일, 주석 없음.

## 범위 이탈

없음. 금지 파일 부재를 직접 확인했다: `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini`, `tox.ini`, `uv.lock`, `poetry.lock`, `t2s/db.py`, `t2s/guard.py`, `t2s/llm.py`, `t2s/graph.py`, `t2s/cli.py` 전부 없음 (`ls` → No such file). 커넥션 래퍼·풀·재시도 로직도 없다 (설계결정 6 준수 — 접속은 tests/test_config.py:147 에서 `pymysql` 직접 호출).

## 보안 경계

- 하드코딩된 비밀: `t2s/config.py` 에 자격증명 리터럴 0건 — 전부 `os.environ` 경유(`:39`).
- `tests/test_config.py:6-14` `VALID_ENV` 에 `t2s_ro`/`t2s_ro_pw` 가 있으나 이는 스펙이 지정한 읽기 전용 계정이고 `.env.example` 에 이미 평문으로 존재하는 값이다 (스펙 `.env.example` 규칙 2가 자리표시자 사용을 금지). `t2s_ro` 이외 계정·root 자격증명 사용 흔적 없음.
- `.env` 는 로컬에 존재하고 `.gitignore:8` 로 제외됨. `git status --untracked-files=all` 에도 안 뜬다.
- SQL 가드 관련 코드는 이번 스펙 범위 밖(다음 스펙). LLM 생성 SQL 경로 자체가 아직 없다.

## 발견 사항

### [경미] `requirements.txt` 마지막 줄에 개선 문자(newline)가 없다

`wc -c requirements.txt` → 103 바이트. 6줄 전부 LF 종료라면 104 바이트여야 하므로 `pytest==9.1.1` 뒤 newline 이 빠졌다. pip 은 정상 파싱하며 검증 명령도 통과했으므로 기능 영향은 없다. 다음 스펙에서 이 파일을 편집할 때 정리하면 된다.

그 외 [심각] 항목 없음.

## 커밋 전 조치

없음. 그대로 커밋 가능.

참고: untracked 목록에 `specs/001-bootstrap.md` 가 함께 잡혀 있다. 이는 GLM 산출물이 아니라 스펙 문서 자체이므로 같은 커밋에 넣을지는 사람이 판단한다.
