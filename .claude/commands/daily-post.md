---
description: 오늘의 경제뉴스를 골라 해설 포스트 초안까지 만든다. 인자 없으면 무인 모드(브랜치+PR), `manual` 인자면 대화형 모드(승인 후 main 푸시)
---

<pipeline name="daily-post">
  <mode_contract>
    - [무인 (인자 없음)]: 대화형 도구 호출 금지. 1위 후보 자동 선택. `auto/post-YYYY-MM-DD` 브랜치에 단일 커밋 후 푸시 (PR 자동 생성). `main` 직접 푸시 금지.
    - [수동 (`manual`)]: 후보 3건 제시 -> 사용자 1건 선택 -> 승인 질문("draft:false로 바꿔 main에 푸시할까요?")에 명확한 긍정 확인 후 `main` 푸시.
  </mode_contract>

  <stages>
    <stage id="1" name="ranking" file=".claude/daily-post/rank.md">
      - Read 후 스냅샷 후보 채점. 1위 점수 < 8점이면 조용히 종료.
    </stage>

    <stage id="2" name="source_verification">
      - 1위 후보 `body_text` 사용 (WebFetch 금지). 사실관계 파악 불가 시 즉시 중단.
    </stage>

    <stage id="3" name="related_articles">
      - WebSearch로 과거 배경/맥락 한국 경제기사 2~3건 선별 (title, url, source). 원문 URL 제외, 0건이어도 정상 진행.
    </stage>

    <stage id="4" name="analysis" file=".claude/daily-post/analysis.md">
      - Read 후 4개 필드(건드리는 렌즈, 선행 vs 동행, 확인된 수치, 자산군별 함의) 분석 노트를 메모리로 작성.
    </stage>

    <stage id="5" name="draft" file=".claude/daily-post/draft.md">
      - Read 후 포스트 및 (필요 시) 사전 초안 작성.
      - 발행 전 결정론 검사(N1~N5, T1~T4, contracts) 실행 결과를 §6으로 전달 (`통과` | `남은 위반 N건` | `검사 불가`).
    </stage>

    <stage id="6" name="publish_gate">
      - [통과]: 무인은 `auto/post-YYYY-MM-DD` 브랜치 단일 커밋 푸시 (`git commit --cleanup=verbatim -m "post: <제목> (draft)" -m "<PR 본문>"`). 수동은 사용자 승인 후 `draft: false`로 `main` 푸시.
      - [남은 위반 / 검사 불가]: 무인은 중단하지 않고 PR 본문에 `## 발행 전 검사` 절 기록. 수동은 위반 내역을 보여주고 처리 방향 확인.
    </stage>

    <stage id="7" name="report">
      - 스냅샷 상태, 선택 기사 및 점수, 생성 파일 경로, 검사 결과, 브랜치 푸시 여부 최종 보고.
    </stage>
  </stages>
</pipeline>
