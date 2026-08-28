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
      - 발행 전 결정론 검사 실행. 결과를 §6으로 전달 (`통과` | `남은 위반 N건` | `검사 불가`).

```bash
.venv/bin/python .claude/audit/lib/numerics.py                  # N1~N5
.venv/bin/python .claude/audit/lib/headings.py --file content/posts/<슬러그>.md   # T1~T4
.venv/bin/python .claude/audit/lib/contracts.py                 # 계약 전체
.venv/bin/python .claude/audit/lib/quality.py                   # Q6 = 볼드체(`**`) 금지
```

      - **볼드체(Q6)는 `남은 위반`으로 센다.** `writing-styles.md`가 가장 강한 어조로
        금지한 규칙인데 2026-08-28까지 검사기가 없었고, 그동안 발행글 39건 중 26건이
        어겼다. 같은 기간 검사기가 붙어 있던 headings·FAQ 규칙은 위반이 0이었다 —
        규칙 문구가 아니라 검사기가 준수를 만든다. 검사기 없이 두면 이 규칙은 다시 샌다.
    </stage>

    <stage id="5.5" name="independent_review" agent="post-reviewer">
      <!--
        사람 승인이 사라지면서 "쓴 사람이 아닌 눈"이 없어졌다. 결정론 검사가 그 자리를
        메웠지만 그것들이 보는 것은 형식이다 — 기준일이 붙었는지, 제목이 몇 자인지.
        원문에는 "2분기"인데 글에는 "상반기"라고 쓴 것, 전망을 확정으로 옮긴 것,
        원문에 없는 인과를 만들어 낸 것은 형식 검사가 원리적으로 못 본다.
        그리고 그것들은 하필 글쓴이가 자기 글에서 가장 못 보는 것들이다.
      -->
      - Task 도구로 `post-reviewer` 서브에이전트를 호출한다. 넘기는 것: 포스트 경로 · 사전 항목 경로(있으면) · 후보 스냅샷 경로.
      - **§5의 결정론 검사를 먼저 통과시킨 뒤에 부른다.** 형식 위반이 남은 글을 보내면 검토자가 그것을 다시 세느라 정작 봐야 할 축을 못 본다.
      - 검토자는 파일을 고치지 않는다. 판정과 「고칠 방법」만 돌려준다 — 고치는 것은 이 세션이다.
      - 반환된 판정으로 갈린다:

      | 판정 | 이 세션이 할 일 |
      |---|---|
      | 발행 가능 | 그대로 §6으로. 권고는 판단해서 반영하되 반영 여부가 발행을 막지 않는다. |
      | 수정 필요 | 차단 항목을 전부 고치고 §5 결정론 검사를 다시 돌린 뒤 **검토자를 한 번 더** 부른다. |
      | 보류 | 고치지 않는다. §6으로 가되 **보류**로 처리한다. |

      - **재검토는 최대 1회다.** 두 번째 검토에서도 차단이 남으면 그것으로 확정하고 보류한다. 무한 왕복은 비용도 문제지만, 세 번째 수정쯤 되면 검토자를 통과시키려고 글을 비트는 쪽으로 기운다.
      - 검토자가 호출되지 않거나 응답을 파싱할 수 없으면 **검사 불가**로 보고 보류한다. 검토를 건너뛰고 발행하지 않는다 — 건너뛸 수 있게 해 두면 그 경로가 기본값이 된다.
      - 판정과 차단 건수를 §6 커밋 본문의 `검토:` 줄로 넘긴다.
    </stage>

    <stage id="6" name="publish_gate">
      <!--
        사람이 최종 확인을 하던 자리에 이 게이트가 들어왔다. 예전에는 위반이 남아도
        PR 본문에 적어 두고 넘어갔다 — 사람이 텔레그램에서 읽고 반려할 수 있었으니까.
        이제 그 독자가 없으므로 위반이 남은 글은 **사이트에 올리지 않는다.**
        버리지도 않는다: `draft: true`로 main에 올려 두면 사이트에는 노출되지 않고,
        파일은 남아 격주 점검의 Q4(방치 초안)가 집어내고 `/revise-post`가 고칠 수 있다.
      -->
      - **발행 조건은 둘 다 통과다**: §5 결정론 검사 `통과` **그리고** §5.5 검토 `발행 가능`.
      - [둘 다 통과] -> **발행**. front matter를 `draft: false`로 두고 `main`에 단일 커밋 푸시.
      - [한쪽이라도 미통과 / 검사 불가 / 검토 불가] -> **보류**. front matter를 `draft: true`로 두고 그대로 `main`에 푸시한다. 중단하지 않는다 — 파일이 남아야 사람이 고칠 수 있다.
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
검토: 발행 가능 | 수정 필요(차단 N건) | 보류(차단 N건) | 검토 불가
사유: <보류일 때만 — 무엇이 걸렸고 무엇을 고쳐야 하는지 한 문장>
```

      - **푸시 전에 Hugo 빌드를 확인한다.** front matter가 깨진 파일은 `draft` 값과
        무관하게 빌드를 실패시키고(초안도 front matter는 파싱된다), 그러면 `hugo.yml`이
        죽어 **사이트 전체가 그날 배포되지 않는다.** 그런데 `notify-post.yml`은 커밋
        접두사만 보므로 텔레그램에는 "발행됨"이 그대로 나간다 — 실패가 조용하다.

```bash
bash scripts/bootstrap_sandbox.sh && export PATH="$HOME/.local/bin:$PATH"
git submodule update --init --depth 1 themes/PaperMod
hugo --gc --minify && rm -rf public resources
```

      - [빌드 성공] -> 위 판정대로 푸시한다.
      - [빌드 실패] -> `draft: true`로 바꾸고 **다시 빌드한다.** 통과하면 보류로 푸시한다.
      - [`draft: true`로도 실패] -> **푸시하지 않는다.** 이때만은 파일을 남기지 않는다 —
        글 한 건을 잃는 것보다 사이트 전체를 내리는 쪽이 크다. §7 최종 보고에
        `빌드 실패`와 원인을 적어 격주 점검이 ④ 중대 고장으로 집어내게 한다.
      - 푸시가 네트워크 오류로 실패하면 2s·4s·8s·16s로 최대 4회 재시도한다.
      - 푸시 직전에 `git pull --rebase origin main`을 한 번 한다. 유지보수·점검이 같은 날 `main`을 건드렸을 수 있다.
    </stage>

    <stage id="7" name="report">
      - 스냅샷 상태, 선택 기사 및 점수, 생성 파일 경로, 결정론 검사 결과, **검토자 판정과 차단·권고 건수**, 재검토 여부, 발행/보류 여부, 푸시 결과 최종 보고.
      - 검토자가 낸 권고 중 반영하지 않은 것이 있으면 그 목록과 이유를 함께 적는다 — 다음 회차와 격주 점검이 반복되는 지적을 알아볼 수 있어야 한다.
    </stage>
  </stages>
</pipeline>
