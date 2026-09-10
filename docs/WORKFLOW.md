# 작업 흐름

Text-to-SQL 에이전트를 **설계·검수 세션(Claude)이 설계·검수하고, 구현 세션(LLM 백엔드)이 구현하는** 방식으로 만든다.
한 사이클은 아래 4단계이고, 마지막 커밋은 사람이 한다.

```
 [1] 설계·검수 세션(Claude) / spec-writer      계획 → specs/NNN-<slug>.md
          │
          ▼
 [2] 구현 세션 / implementer                   스펙 → 코드 + 테스트 실행
          │
          ▼
 [3] 설계·검수 세션(Claude) / impl-reviewer    git diff + 스펙 대조 → reviews/NNN-<slug>.md
          │
          ├── FAIL ──────────► [2] 로 되돌림 (판정문의 재작업 지시문 사용)
          │
          ▼
 [4] 사람                                      diff + 판정문 확인 → git commit
```

## 역할

| # | 어디서 | 정의 | 산출물 | 하지 않는 것 |
|---|---|---|---|---|
| 1 | 설계·검수 세션(Claude) | [`spec-writer`](../agents/spec-writer.md) | `specs/NNN-*.md` | 구현 코드를 쓰지 않는다 |
| 2 | 구현 세션 | [`implementer`](../agents/implementer.md) | 소스 + 테스트 | 설계 판단, 범위 밖 수정, 커밋 |
| 3 | 설계·검수 세션(Claude) | [`impl-reviewer`](../agents/impl-reviewer.md) | `reviews/NNN-*.md` | 코드를 고치지 않는다 |
| 4 | 사람 | — | 커밋 | — |

## 파일 위치

에이전트 지침은 **`agents/` 한 곳에만** 둔다. 이 폴더는 도구 중립적이라
어떤 세션(LLM 백엔드)에서도 같은 경로로 읽는다.

```
agents/
  implementer.md              [2] 구현 세션이 직접 읽음 (spawn 하지 말 것)
  spec-writer.md              [1] 실제 지침
  impl-reviewer.md            [3] 실제 지침
.claude/agents/               Claude 세션용 spawn 등록 wrapper (내용 없음)
  spec-writer.md              → agents/spec-writer.md 를 읽게 전달만 한다
  impl-reviewer.md            → agents/impl-reviewer.md 를 읽게 전달만 한다
docs/WORKFLOW.md              이 문서
specs/TEMPLATE.md             스펙 양식
specs/NNN-<slug>.md           [1] 산출물 → [2] 입력 → [3] 대조 기준
reviews/NNN-<slug>.md         [3] 산출물 → 사람이 커밋 전에 읽음
```

`.claude/agents/` 는 Claude Code 가 서브에이전트를 자동 등록하기 위한 규약 폴더일 뿐,
**실제 내용은 갖지 않는다.** 지침을 고칠 때는 `agents/` 만 고친다.

`agents/implementer.md` 는 **서브에이전트로 spawn 하지 않는다.**
spawn 하면 설계·검수 세션이 구현하게 되어 구현 세션에 넘기는 의미가 사라진다.
구현 세션에 파일 경로를 직접 지시하는 방식으로 쓴다.

이 분리가 핵심이다. **설계·검수와 구현을 같은 세션이 하면 검수가 자기 코드를 감싸게 된다.**
그리고 구현 모델은 빠른 대신 애매한 지시에서 임의 판단을 하므로, 판단할 여지를 스펙 단계에서 없앤다.

## 실행 방법

**[1] 스펙 작성** — 설계·검수 세션(Claude)에서
```
spec-writer 로 다음 단계 스펙 써줘
```

**[2] 구현** — 구현 세션(LLM 백엔드)에서 (같은 저장소)
```
specs/003-guard.md 를 구현하라. agents/implementer.md 의 규칙을 따르라.
```

**[3] 검수** — 설계·검수 세션(Claude)에서
```
impl-reviewer 로 003 리뷰해줘
```

**[4] 커밋** — 사람이 직접
```bash
git diff
cat reviews/003-guard.md
git add -A && git commit
```

## 규칙

- **한 스펙 = 한 커밋.** 스펙 여러 개를 몰아서 구현하지 않는다. diff 가 커지면 검수 품질이 떨어진다.
- **스펙 크기 상한: 파일 5개, 300줄.** 넘으면 쪼갠다.
- **`FAIL` 판정이 난 코드는 커밋하지 않는다.** 판정문의 재작업 지시문을 구현 세션에 그대로 넘긴다.
- **테스트 없는 스펙은 스펙이 아니다.** 수용 기준 표가 곧 테스트 케이스다.
- **구현 세션은 커밋하지 않는다.** 사람이 diff 를 눈으로 보는 단계를 건너뛰지 않기 위한 장치다.
- 스펙 순서는 의존 관계를 따른다. 순수 함수(DB·LLM 불필요) → DB 계층 → LLM 계층 → 그래프 → CLI.
  앞쪽일수록 검증이 싸고 확실하므로 먼저 쌓는다.

## 현재 진행 상황

| 단계 | 상태 |
|---|---|
| Sakila 컨테이너 (`docker/`) | 완료 — `t2s-sakila`, MySQL 8.4.10, `127.0.0.1:3310` |
| LLM 경로 확인 (`llm.py`) | 미착수 |
| `guard.py` (SQL 안전성 검사) | 완료 — 리뷰 PASS (`reviews/002-guard.md`) |
| `db.py` / `schema.py` | 미착수 |
| `graph.py` / `cli.py` | 미착수 |
| 평가 · 쿼리 효율성 (v2) | 미착수 |