---
description: 주 1회 감사 패스. 인자 없으면 무인(리포트·원장은 main 직행, content/ 수정만 auto/audit PR), `manual` 인자면 대화형. 여섯 축 = ① 링크 ② 성과 ③ 색인 ④ 스캔 ⑤ 방향 ⑥ 수치.
---

<!-- 이 명령의 리포트는 공개 저장소에 커밋된다. 자격증명·서비스계정 이메일·토큰을 리포트에 절대 쓰지 않는다. -->

<pipeline name="weekly-audit">
  <mode_contract>
    - [무인 (인자 없음)]: 대화형 도구 호출 금지. 리포트와 원장 JSON은 승인 없이 `main`에 직접 커밋·푸시. `content/` 수정(사망링크/백필/front matter)이 있을 때만 `auto/audit-YYYY-MM-DD` 브랜치 및 PR 생성.
    - [수동 (`manual`)]: 파이프라인 동일, `content/` 수정이 있을 경우 최종 승인 후 `main` 푸시.
    - 모든 Python 호출은 `.venv/bin/python` 전용.
  </mode_contract>

  <stages>
    <stage id="1" name="pre_guard">
      - KST 날짜 산출: `.venv/bin/python .claude/audit/lib/kstdate.py` (이후 모든 YYYY-MM-DD는 이 값을 사용).
      - 워킹 트리 클린 여부 확인 (`git status`).
      - 미처리 감사 PR 유무 확인 (`git ls-remote --heads origin 'auto/audit-*'`). 미처리 PR이 있으면 새 콘텐츠 PR을 만들지 않고 리포트/원장만 `main`에 반영.
    </stage>

    <stage id="2" name="stage_link_check" file=".claude/audit/link-check.md">
      - Read 후 링크 무결성 검사 및 내부 링크 백필 후보 탐지. 결과 텍스트 반환.
    </stage>

    <stage id="3" name="stage_performance" file=".claude/audit/performance.md">
      - Read 후 성과 분석 및 Corpus Gate(20건/28일/3군) 판정.
      - 게이트 통과 시에만 `topic-report.md` 내용 및 `topic-history.json` 갱신 문자열 반환.
      - `published_count`, `site_age`를 §4와 §7로 전달.
    </stage>

    <stage id="4" name="stage_indexation" file=".claude/audit/indexation.md">
      - Read 후 색인 건전성 판정 (I1~I7).
    </stage>

    <stage id="5" name="stage_system_scan" file=".claude/audit/system-scan.md">
      - Read 후 시스템 스캔 (E1~E4, Q1~Q5, P1~P2).
      - (A) 계약 위반 블록, (B) ④ 섹션, (C) front matter 수정안 문자열 반환 (읽기 전용).
    </stage>

    <stage id="6" name="stage_numeric_integrity" file=".claude/audit/numeric-integrity.md">
      - Read 후 수치 무결성 검사 (N1~N5). ⑥ 섹션 텍스트 반환.
    </stage>

    <stage id="7" name="stage_direction_review" file=".claude/audit/direction-review.md">
      - Read 후 포트폴리오 축(D1~D6) 측정 및 가설 대조.
      - 갱신된 `direction-log.json` 문자열 반환 (무인은 `제안`까지만 기록).
    </stage>

    <stage id="8" name="report_assembly">
      - `report/audit-YYYY-MM-DD[-HHMM].md` 파일 작성.
      - 헤딩 순서: (1) 계약 위반 (2) 현재 방향 (3) ① 링크 (4) ① 백필 (5) ② 성과 (6) ③ 색인 (7) ④ 스캔 (8) ⑥ 수치 (9) ⑤ 방향 (10) 로컬 세션 대기열.
    </stage>

    <stage id="9" name="summary_and_triaging">
      - 소견 3분기: `Claude 판정` (저장소 닫힌 규칙 -> PR 반영), `사람 판정` (정책 선택 -> `─ 결정 필요 ─` 등재), `로컬 세션` (외부 Egress 필요 -> 대기열 등재).
      - 커밋 메시지 본문용 8줄 요약 블록 작성:
```
## 감사 요약
계약 위반: N건
확정 사망 링크: N건 / 사람 점검 필요: N건
데이터 충분성: 미달 (발행 N / 20건)
색인 건전성: 정상
소견: N건 (④ N, ⑥ N)
front matter 수정: N건
새 가설 제안: N건
─ 결정 필요 ─
* <사람 판단 필요 항목 또는 없음>
PR 리포트: report/audit-YYYY-MM-DD[-HHMM].md
```
    </stage>

    <stage id="10" name="publish_and_git">
      - 리포트 및 원장(`link-state.json`, `direction-log.json`, 통과 시 `topic-report.md`, `topic-history.json`)은 `main`에 직접 커밋·푸시 (`git commit --cleanup=verbatim -m "audit: YYYY-MM-DD 주간 감사" -m "<§9 요약 본문>"`).
      - `content/` 수정(사망링크 제거, 백필, front matter 수정)이 1건 이상일 때만 `auto/audit-YYYY-MM-DD` 브랜치 커밋 및 푸시 (PR 자동 생성).
    </stage>

    <stage id="11" name="final_report">
      - Hugo 상태, 6대 축 판정, 생성 파일 목록, Git 푸시 상태 최종 요약 출력.
    </stage>
  </stages>
</pipeline>
