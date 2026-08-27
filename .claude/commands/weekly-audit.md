---
description: 폐지됨 — /health-check로 이관되었다. 이 파일은 옛 루틴 트리거를 안전하게 넘겨주는 리다이렉트 셈이다.
---

# /weekly-audit 는 폐지되었다 (2026-08-27)

주 1회 LLM 감사는 **두 갈래로 나뉘어** 사라졌다:

- **결정론 축(① 링크 · ④ 스캔 · ⑥ 수치)** -> 주간 유지보수 `scripts/housekeeping.py`
  (`weekly-housekeeping.yml`, 일 18:00 UTC). LLM이 필요 없다.
- **판단 축(운영 연속성 · ② 성과 · ③ 색인 · SEO/GEO 크롤 · ⑤ 방향)** -> `/health-check`,
  격주.

## 이 파일이 아직 있는 이유

`econ-blog /weekly-audit` 루틴 트리거가 저장소 밖(cron-job.org가 아니라 Claude Routines,
`http_api`로 생성됨)에 있고 그 프롬프트가 이 경로를 Read 하도록 적혀 있다. 에이전트는 그
트리거를 고칠 수 없다 — 자기가 만들지 않은 루틴이라 권한이 없다. 파일만 지우면 다음
일요일에 그 세션이 존재하지 않는 지침을 찾다가 **아무 지침 없이 쓰기 권한만 든 채로**
남는다. 그 상태가 조용히 나쁜 일을 할 수 있어서 셈을 남긴다.

## 이 파일을 Read 했다면

**`.claude/commands/health-check.md`를 Read 하고 그 절차를 무인 모드로 수행하라.**
그것이 이 명령을 대체한 것이다. 여기 적힌 6축·`auto/audit-*` 브랜치·승인 게이트는
전부 폐기됐으므로 기억에서 재구성하지 않는다.

## 지워도 되는 시점

`econ-blog /weekly-audit` 루틴의 이름과 프롬프트가 `/health-check`를 가리키도록 갱신된
뒤. 그때 이 파일을 지운다. 갱신 문구는 `MEMORY.md` §11-7에 적어 두었다.
