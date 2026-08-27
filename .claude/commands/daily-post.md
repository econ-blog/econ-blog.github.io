---
description: 오늘의 경제뉴스를 골라 해설 포스트를 쓰고 바로 발행한다. 인자 없으면 무인 모드(main 직행 발행), `manual` 인자면 대화형 모드(승인 후 발행)
---

<pipeline name="daily-post">
  <mode_contract>
    - [무인 (인자 없음)]: 대화형 도구 호출 금지. 1위 후보 자동 선택. **`draft: false`로 `main`에 단일 커밋 푸시** — 승인을 기다리지 않는다. 브랜치도 PR도 만들지 않는다.
    - [수동 (`manual`)]: 후보 3건 제시 -> 사용자 1건 선택 -> 승인 질문에 명확한 긍정 확인 후 `main` 푸시.
    - **커밋 제목은 반드시 `post: <제목>`으로 시작한다.** `notify-post.yml`이 이 접두사만 보고 본문을 텔레그램으로 밀어 준다. `audit:`·`post(revise):`는 의도적으로 걸러지므로, 접두사가 틀리면 오류 없이 그냥 알림이 오지 않는다.
    - 2026-08-27 이전의 `auto/post-YYYY-MM-DD` 브랜치 규칙은 **폐기됐다.** 그 규칙은 PR 생성(`open-auto-pr.yml`)과 승인 알림(`notify.yml`)이 그 접두사에 배선돼 있어서 존재했고, 두 워크플로 모두 제거됐다. 이제 `auto/**`로 푸시하면 아무 데도 도착하지 않는다.
    - CCR 세션이 요구하는 "세션 지정 브랜치"(`claude/xxx`)로도 푸시하지 않는다. 발행은 `main`이다.
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
      - 발행 전 결정론 검사(N1~N5, T1~T4, contracts) 실행. 결과를 §6으로 전달 (`통과` | `남은 위반 N건` | `검사 불가`).
    </stage>

    <stage id="6" name="publish_gate">
      <!--
        사람이 최종 확인을 하던 자리에 이 게이트가 들어왔다. 예전에는 위반이 남아도
        PR 본문에 적어 두고 넘어갔다 — 사람이 텔레그램에서 읽고 반려할 수 있었으니까.
        이제 그 독자가 없으므로 위반이 남은 글은 **사이트에 올리지 않는다.**
        버리지도 않는다: `draft: true`로 main에 올려 두면 사이트에는 노출되지 않고,
        파일은 남아 격주 점검의 Q4(방치 초안)가 집어내고 `/revise-post`가 고칠 수 있다.
      -->
      - [통과] -> **발행**. front matter를 `draft: false`로 두고 `main`에 단일 커밋 푸시.
      - [남은 위반 / 검사 불가] -> **보류**. front matter를 `draft: true`로 두고 그대로 `main`에 푸시한다. 중단하지 않는다 — 파일이 남아야 사람이 고칠 수 있다.
      - 커밋 명령(두 경우 공통):

```bash
git add content/posts/<슬러그>.md content/dictionary/<슬러그>.md content/dictionary/_terms.yaml
git commit --cleanup=verbatim -m "post: <제목>" -m "<아래 발행 블록>"
git push origin main
```

      - 커밋 메시지 본문은 이 형식을 지킨다. `notify-post.yml`이 `사유:`를 읽어 보류
        알림에 싣는다(발행일 때는 비운다):

```
## 발행
상태: 발행 | 보류
검사: 통과 | 남은 위반 N건 | 검사 불가
사유: <보류일 때만 — 무엇이 걸렸고 무엇을 고쳐야 하는지 한 문장>
```

      - 푸시가 네트워크 오류로 실패하면 2s·4s·8s·16s로 최대 4회 재시도한다.
      - 푸시 직전에 `git pull --rebase origin main`을 한 번 한다. 유지보수·점검이 같은 날 `main`을 건드렸을 수 있다.
    </stage>

    <stage id="7" name="report">
      - 스냅샷 상태, 선택 기사 및 점수, 생성 파일 경로, 검사 결과, 발행/보류 여부, 푸시 결과 최종 보고.
    </stage>
  </stages>
</pipeline>
