# vendor/im-not-ai — 벤더링 기록

`humanize-korean` 스킬(한글 AI 티 제거 윤문)을 이 저장소 안에 복사해 둔 것이다.

| 항목 | 값 |
|---|---|
| 원본 | https://github.com/epoko77-ai/im-not-ai |
| 커밋 | `0ac1e84f92334f9696e69184478f91c1c6f1dc5e` |
| 스킬 버전 | 2.3.2 |
| 라이선스 | MIT (`LICENSE` 동봉) |
| 벤더링일 | 2026-08-28 |

## 왜 플러그인으로 설치하지 않고 복사했나

무인 루틴(`/daily-post`)은 cron-job.org가 깨우는 GitHub Actions 세션 안에서 돌고, 그
세션은 이 저장소만 클론한 샌드박스다. `/plugin marketplace add`는 대화형 명령이고
설치 상태가 세션 밖에 남지 않으므로 **다음 발화 때 스킬이 없다.** 저장소 안에 있어야
매 회차 확실히 존재한다.

## 배치

```
.claude/vendor/im-not-ai/          # 이 디렉터리 = SKILL_ROOT (`.claude-plugin/` 표지)
  .claude-plugin/plugin.json
  scripts/*.py                     # 런타임 스크립트 (전부 표준 라이브러리)
  skills/humanize-korean/          # SKILL.md + references/
  skills/humanize/                 # 진입 명령 (심링크하지 않음)
  skills/humanize-redo/            # 2차 윤문 진입 명령 (심링크하지 않음)
.claude/skills/humanize-korean     -> ../vendor/im-not-ai/skills/humanize-korean (심링크)
.claude/agents/humanize-{monolith,diagnostician,finalizer}.md
```

원본의 `scripts/`↔`skills/humanize-korean/references/` 상대 경로 관계를 스크립트가
`__file__` 기준으로 계산하므로 **디렉터리 구조를 그대로 보존해야 한다.** 스킬만 떼어
`.claude/skills/` 밑에 옮기면 `metrics_v2.py` import가 조용히 죽고 route_hint 없이
degrade된다. 그래서 스킬 발견 경로에는 심링크만 둔다 — 원본 `install.sh`가 쓰는 방식과
같고, SKILL.md의 `SKILL_ROOT` 유도가 `cd -P`로 심링크를 풀도록 이미 설계돼 있다.

## 원본에서 뺀 것

- `agents/` 9개 중 유지보수·릴리스용 6개 (런타임 3개만 가져왔다). 서브에이전트는
  description 매칭으로 자동 라우팅되므로, 윤문과 무관한 정의가 풀에 상주하면
  `/daily-post`·`/health-check`의 Task 호출이 엉뚱한 데로 갈 수 있다.
- `scripts/build_social_preview*.py` — PIL 의존이라 샌드박스에서 import부터 실패한다.
- `assets/`, `tests/`, `install.sh`, 문서류.

## 갱신 절차

```bash
git clone --depth 1 https://github.com/epoko77-ai/im-not-ai.git /tmp/im-not-ai
# 위 "배치"대로 다시 복사하고, 이 파일의 커밋 해시·버전을 갱신한다.
# 반드시 스모크 테스트를 통과시킬 것:
python3 .claude/vendor/im-not-ai/scripts/prepare_monolith_input.py \
  --text "$(cat content/posts/<아무 글>.md)" --genre blog
#   -> degraded=False 와 route_hint 가 찍혀야 한다. degraded=True 면 경로가 깨진 것이다.
```

`SKILL.md`는 손대지 않는다 — 이 저장소용 제약(수치·볼드·H2 불변)은 스킬이 아니라
`/daily-post` §5.3이 건다. 스킬을 고치면 갱신 때마다 충돌한다.
