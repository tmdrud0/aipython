# 001: 개발 환경 부트스트랩 (venv + 의존성 + 설정 로더)

- 대응 계획 단계: `docs/WORKFLOW.md` 의 "현재 진행 상황" 표 중 **`glm-5.3-flash:cloud` 경로 확인** 직전 단계. 이후 모든 스펙(`guard.py`, `db.py`, `llm.py` …)이 이 스펙의 산출물 위에서 돌아간다.
- 선행 스펙: 없음 (첫 번째 스펙)
- 예상 분량: 파일 5개, 약 150줄

## 목표

이 저장소에서 파이썬 코드를 돌릴 수 있는 상태를 만든다: `.venv` 생성, 핀 고정된 의존성 설치, `.env` 기반 설정 로더, 그리고 "환경이 제대로 잡혔는지"를 한 번에 확인하는 테스트.
이 스펙이 끝나면 `pytest` 한 줄로 **설정 로딩 + Sakila DB 접속**까지 확인된다.

## 범위

**신규**
| 파일 | 역할 |
|---|---|
| `requirements.txt` | 의존성 목록. 전부 `==` 핀 고정 |
| `.env.example` | 설정 키 목록 + 예시 값. 실제 `.env` 는 커밋하지 않는다 |
| `t2s/__init__.py` | 패키지 마커. 내용은 빈 파일 |
| `t2s/config.py` | `Settings` dataclass + `load_settings()` + `ConfigError` |
| `tests/test_config.py` | 수용 기준 표를 그대로 옮긴 테스트 |

**수정**
| 파일 | 무엇을 |
|---|---|
| 없음 | — |

**건드리지 말 것**
- `docker/` 전체 — 컨테이너는 이미 완료 상태다. `docker-compose.yml`, `initdb/*.sql`, `fetch_sakila.ps1` 모두 수정 금지.
- `docs/WORKFLOW.md` — 진행 상황 표 갱신은 사람이 커밋 단계에서 한다.
- `.gitignore` — `.venv/`, `__pycache__/`, `*.pyc`, `.env` 가 이미 들어 있다. 추가하지 마라.
- `docs/specs/`, `docs/reviews/`, `readme.md`

## 재사용할 기존 코드

| 경로 | 무엇을 |
|---|---|
| `docker/initdb/03-readonly-user.sql` | DB 접속 계정의 **정답 값**. `t2s_ro` / `t2s_ro_pw`, 권한은 `sakila.*` 에 대한 `SELECT`, `SHOW VIEW` 뿐이다. `.env.example` 에 이 값을 그대로 쓴다. 새 계정을 만들지 마라. |
| `docker/docker-compose.yml` | 포트의 **정답 값**. 호스트 포트는 `3310` (컨테이너 내부 3306). `3306`/`3307`/`3308` 은 다른 것이 선점 중이므로 쓰면 안 된다. |

파이썬 소스는 아직 하나도 없다. 재사용할 기존 함수·상수는 없다.

## 설계 결정 (이미 정해졌다. 바꾸지 마라)

1. **패키지 구조는 저장소 루트의 `t2s/` 평면 구조다.** `src/` 레이아웃을 쓰지 않는다. 배포용 패키지가 아니라 단일 앱이므로 `pip install -e .` 없이 루트에서 바로 `import t2s` 가 되게 한다.
2. **의존성 관리는 `requirements.txt` 하나다.** `pyproject.toml`, `poetry`, `uv.lock`, `setup.py` 를 만들지 마라. 개발 의존성(`pytest`)도 같은 파일에 넣는다. 파일을 나누지 않는다.
3. **버전은 전부 `==` 로 고정한다.** `>=`, `~=`, 버전 미기재 금지.
4. **파이썬은 3.12 를 쓴다.** (`py -3.12`. 이 머신에 3.12.10 과 3.11 이 둘 다 있어 명시하지 않으면 3.11 이 잡힐 수 있다.)
5. **`.env` 파일 자체는 커밋하지 않는다.** GLM 은 로컬에서 `.env.example` 을 복사해 `.env` 를 만들어 테스트를 돌리고, `git status` 에 `.env` 가 안 뜨는지 확인한다.
6. **DB 접속 코드(`t2s/db.py`)는 이번 스펙에 없다.** 접속 확인은 테스트 안에서 `pymysql` 을 직접 써서 한다. 커넥션 래퍼·풀·재시도 로직을 만들지 마라. 그건 다음 스펙이다.
7. **pytest 커스텀 마커를 쓰지 않는다.** (`pytest.ini` 같은 설정 파일이 늘어나므로) DB 미기동은 테스트 본문에서 `pytest.skip()` 으로 처리한다.

## 파일별 계약

### `requirements.txt`

아래 6줄을 **이 순서 그대로**, 주석 없이 쓴다.

```
PyMySQL==1.2.0
python-dotenv==1.2.3
ollama==0.6.2
langgraph==1.2.11
langchain-core==1.6.2
pytest==9.1.1
```

규칙:
1. 위 목록에 없는 패키지를 추가하지 마라.
2. 버전을 임의로 올리거나 내리지 마라. 설치가 실패하면 고치지 말고 **에러 전문을 이 스펙의 "질문" 절에 적고 멈춘다.**

### `.env.example`

아래 내용을 그대로 쓴다. 키 이름은 전부 `T2S_` 접두사를 갖는다.

```
# docker/docker-compose.yml 의 t2s-sakila 컨테이너 기준
T2S_DB_HOST=127.0.0.1
T2S_DB_PORT=3310
T2S_DB_USER=t2s_ro
T2S_DB_PASSWORD=t2s_ro_pw
T2S_DB_NAME=sakila

# Ollama
T2S_OLLAMA_HOST=http://127.0.0.1:11434
T2S_OLLAMA_MODEL=glm-5.3-flash:cloud
```

규칙:
1. 키를 추가하거나 이름을 바꾸지 마라. `t2s/config.py` 의 필수 키 목록과 **정확히 7개로 일치**해야 한다.
2. 여기 적힌 값은 실제로 유효한 값이다. 자리표시자(`your_password_here` 등)로 바꾸지 마라.

### `t2s/__init__.py`

빈 파일. 한 글자도 쓰지 마라 (0 바이트).

### `t2s/config.py`

```python
from dataclasses import dataclass


class ConfigError(RuntimeError):
    ...


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    ollama_host: str
    ollama_model: str


REQUIRED_KEYS: tuple[str, ...] = (
    "T2S_DB_HOST",
    "T2S_DB_PORT",
    "T2S_DB_USER",
    "T2S_DB_PASSWORD",
    "T2S_DB_NAME",
    "T2S_OLLAMA_HOST",
    "T2S_OLLAMA_MODEL",
)


def load_settings(env_path: str | None = None) -> Settings:
    ...
```

`load_settings` 동작 규칙 (번호대로, 순서대로):

1. `env_path` 가 `None` 이면 저장소 루트의 `.env` 를 대상으로 한다. 경로는 `pathlib.Path(__file__).resolve().parent.parent / ".env"` 로 계산한다. 현재 작업 디렉터리(`os.getcwd()`)에 의존하지 마라.
2. `dotenv.load_dotenv(dotenv_path=<1의 경로>, override=False)` 를 호출한다. `override=False` 이므로 **이미 설정된 환경변수가 `.env` 값보다 우선**한다.
3. 대상 파일이 존재하지 않아도 예외를 던지지 않는다. 그대로 4번으로 넘어간다 (환경변수만으로 도는 경우를 위해).
4. `REQUIRED_KEYS` 각각에 대해 `os.environ.get(key, "")` 를 읽고 `.strip()` 한다. 결과가 빈 문자열인 키를 모은다.
5. 빈 키가 하나라도 있으면 `ConfigError` 를 던진다. 메시지는 `f"missing required env keys: {', '.join(missing)}"` 이며, `missing` 은 `REQUIRED_KEYS` 에 적힌 **선언 순서**를 따른다 (정렬하지 않는다).
6. `T2S_DB_PORT` 의 strip 된 값을 `int()` 로 변환한다. `ValueError` 가 나거나 변환 결과가 `1 <= port <= 65535` 범위 밖이면 `ConfigError` 를 던진다. 메시지는 `f"T2S_DB_PORT must be an integer in 1..65535, got: {raw}"` (`raw` 는 strip 된 원본 문자열).
7. 나머지 6개 값은 strip 된 문자열 그대로 담아 `Settings` 를 만들어 반환한다.
8. 로깅·print 를 하지 마라. 반환값과 예외로만 소통한다.

발생 예외:
| 예외 | 조건 | 메시지 형식 |
|---|---|---|
| `ConfigError` | 필수 키 중 하나 이상이 없거나 strip 후 빈 문자열 | `missing required env keys: T2S_DB_USER, T2S_DB_NAME` |
| `ConfigError` | `T2S_DB_PORT` 가 정수가 아니거나 1..65535 밖 | `T2S_DB_PORT must be an integer in 1..65535, got: abc` |

### `tests/test_config.py`

규칙:
1. 아래 "수용 기준" 표의 **모든 행을 각각 하나의 테스트 함수**로 옮긴다. 행을 합치지 마라.
2. 환경변수를 조작할 때는 반드시 pytest 의 `monkeypatch` 픽스처를 쓴다 (`monkeypatch.setenv` / `monkeypatch.delenv`). `os.environ` 을 직접 수정하지 마라 — 테스트 간 오염이 생긴다.
3. 각 테스트는 `monkeypatch.delenv(key, raising=False)` 로 7개 키를 먼저 전부 지운 뒤, 그 케이스에 필요한 키만 세팅한다. 이 공통 준비는 `_set_env(monkeypatch, **overrides)` 헬퍼 하나로 만든다.
4. `.env` 파일의 영향을 배제하기 위해, 설정 로딩 테스트는 `load_settings(env_path=str(tmp_path / "absent.env"))` 처럼 **존재하지 않는 임시 경로**를 넘겨 호출한다.
5. DB 접속 테스트(수용 기준 #10)는 다음 순서로 한다:
   - `load_settings()` 를 **인자 없이** 호출한다 (실제 `.env` 사용). `ConfigError` 가 나면 `pytest.skip(".env 없음")`.
   - `pymysql.connect(host=..., port=..., user=..., password=..., database=..., connect_timeout=3)` 로 접속한다.
   - `pymysql.err.OperationalError` 가 나면 `pytest.skip("DB 미기동")`. 다른 예외는 잡지 말고 그대로 실패시킨다.
   - `SELECT COUNT(*) FROM film` 을 실행해 결과가 `1000` 인지 단언한다.
   - 커넥션은 `try/finally` 또는 컨텍스트 매니저로 반드시 닫는다.
6. 테스트 함수 이름은 `test_` 로 시작하고 무엇을 검증하는지 영어 snake_case 로 적는다.

## 수용 기준

GLM 은 아래 표를 그대로 테스트 코드로 옮긴다.

| # | 입력 | 기대 출력 | 비고 |
|---|---|---|---|
| 1 | 7개 키 모두 유효값 (`T2S_DB_PORT="3310"`) | `Settings(db_host="127.0.0.1", db_port=3310, db_user="t2s_ro", db_password="t2s_ro_pw", db_name="sakila", ollama_host="http://127.0.0.1:11434", ollama_model="glm-5.3-flash:cloud")` | 정상 경로. `db_port` 가 `int` 타입인지도 단언 |
| 2 | 7개 키 유효, 단 값 앞뒤에 공백 (`T2S_DB_HOST="  127.0.0.1  "`) | `settings.db_host == "127.0.0.1"` | strip 확인 |
| 3 | `T2S_DB_USER` 를 지움 | `ConfigError`, 메시지 `missing required env keys: T2S_DB_USER` | 단일 누락 |
| 4 | `T2S_DB_USER` 와 `T2S_DB_NAME` 을 지움 | `ConfigError`, 메시지 `missing required env keys: T2S_DB_USER, T2S_DB_NAME` | 순서는 `REQUIRED_KEYS` 선언 순서 |
| 5 | `T2S_DB_PASSWORD="   "` (공백만) | `ConfigError`, 메시지 `missing required env keys: T2S_DB_PASSWORD` | 빈 문자열 취급 경계값 |
| 6 | `T2S_DB_PORT="abc"` | `ConfigError`, 메시지 `T2S_DB_PORT must be an integer in 1..65535, got: abc` | 정수 아님 |
| 7 | `T2S_DB_PORT="0"` / `T2S_DB_PORT="65536"` | 각각 `ConfigError`, 메시지 `... got: 0` / `... got: 65536` | 범위 밖 경계값. 두 케이스 모두 작성 |
| 8 | `T2S_DB_PORT="1"` / `T2S_DB_PORT="65535"` | 예외 없음. `db_port == 1` / `db_port == 65535` | 유효 경계값. 두 케이스 모두 작성 |
| 9 | 존재하지 않는 경로를 `env_path` 로 넘기고 환경변수 7개는 세팅 | 예외 없음, 정상 `Settings` | 파일 부재가 에러가 아님 확인 (규칙 3) |
| 10 | 실제 `.env` + 기동 중인 `t2s-sakila` 컨테이너, `SELECT COUNT(*) FROM film` | `1000` | Sakila 표준 film 행 수. DB 미기동 시 skip |

## 검증 명령

PowerShell 에서 저장소 루트(`C:\ssafy\workspace\aipython`)에 서서 **한 줄씩** 실행한다. (`&&` 는 PowerShell 5.1 에서 파서 에러다. 쓰지 마라.)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -f docker/docker-compose.yml up -d
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

기대 출력 (마지막 명령):
```
tests/test_config.py::test_... PASSED
... (수용 기준 10개 행에 대응하는 테스트가 전부 PASSED)
========== 12 passed in ...s ==========
```
`#7`·`#8` 이 각각 두 케이스이므로 테스트 함수 개수는 12개다. `failed` 와 `error` 가 0 이어야 한다.
`skipped` 가 있으면 **통과가 아니다** — DB 가 안 떠 있거나 `.env` 가 없다는 뜻이므로 원인을 고치고 다시 돌려라.

venv 활성화가 필요하면 (선택):
```powershell
.\.venv\Scripts\Activate.ps1
```
`Activate.ps1` 이 실행 정책 때문에 막히면 **정책을 바꾸지 말고**, 위 검증 명령처럼 `.\.venv\Scripts\python.exe` 를 직접 호출하는 방식으로 진행하라.

Git Bash 를 쓴다면:
```bash
source .venv/Scripts/activate
```

설치 확인:
```powershell
.\.venv\Scripts\python.exe -m pip freeze | Select-String "PyMySQL|python-dotenv|ollama|langgraph|langchain-core|pytest"
```
기대 출력: 위 6개 패키지가 `requirements.txt` 에 적힌 버전과 **정확히 같은 버전**으로 보인다.

`.env` 가 커밋 대상이 아닌지 확인:
```powershell
git status --short
```
기대 출력: `.env` 와 `.venv/` 가 **목록에 없다.** 보인다면 `.gitignore` 가 아니라 네가 만든 파일 경로가 잘못된 것이다.

## 하지 말 것

- `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini`, `tox.ini`, `uv.lock`, `poetry.lock` 을 만들지 마라.
- `requirements.txt` 의 6개 외 패키지를 설치하거나 추가하지 마라 (`sqlalchemy`, `mysql-connector-python`, `pandas`, `rich`, `typer` 전부 금지).
- `t2s/db.py`, `t2s/guard.py`, `t2s/llm.py`, `t2s/graph.py`, `t2s/cli.py` 를 만들지 마라. 다음 스펙이다.
- `.env` 를 `git add` 하지 마라.
- 도커 컨테이너를 재생성(`docker compose down -v`)하지 마라. 데이터 재적재에 시간이 오래 걸린다. `up -d` 만 쓴다.
- `readme.md` 나 `docs/WORKFLOW.md` 를 갱신하지 마라.
- 예외를 삼키고 기본값으로 넘어가지 마라. 필수 키가 없으면 반드시 `ConfigError` 다.
- 커밋하지 마라.

## 체크리스트

- [ ] 범위의 신규 파일 5개만 만들었다 (수정 파일 없음)
- [ ] `t2s/config.py` 의 시그니처를 글자 그대로 따랐다 (`ConfigError`, `Settings`, `REQUIRED_KEYS`, `load_settings`)
- [ ] 수용 기준 10개 행 전부가 테스트로 존재한다 (#7·#8 은 각각 2개, 총 12개)
- [ ] 검증 명령을 직접 실행했고 실제 출력을 그대로 보고했다 (`skipped` 개수 포함)
- [ ] `requirements.txt` 의 6개 외에 의존성을 추가하지 않았다
- [ ] `git status --short` 에 `.env`, `.venv/` 가 안 뜨는 것을 확인했다
- [ ] 커밋하지 않았다

## 질문

GLM 이 막혔을 때 여기에 적는다. 아래 두 가지는 **스펙 작성 시점에 이미 확인된 미해결 항목**이다.

1. **`langgraph==1.2.11` 과 `langchain-core==1.6.2` 의 의존성 충돌 가능성.** 두 버전 모두 PyPI 에 실재하는 최신 버전이지만, `langgraph` 가 요구하는 `langchain-core` 범위와 겹치지 않을 수 있다. pip 이 `ResolutionImpossible` 을 내면 **버전을 임의로 조정하지 말고** 에러 전문을 여기에 붙이고 멈춰라.
2. **`glm-5.3-flash:cloud` 모델이 로컬 Ollama 에 없다.** `ollama list` 결과에 `gemma4:12b` 만 있다. 이번 스펙은 LLM 을 호출하지 않으므로 문제가 되지 않지만, `.env.example` 의 `T2S_OLLAMA_MODEL` 값은 아직 검증되지 않은 값이다. 다음 스펙에서 확인한다.
