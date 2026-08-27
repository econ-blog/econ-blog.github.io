---
description: 격주 1회 SEO/GEO 전문가 점검. 시스템 전체를 훑고 고칠 수 있는 것은 스스로 고쳐 main에 직행한다. 사람에게는 꼭 필요할 때만 알린다 (월간 리포트·승인·사람 작업·중대 고장).
---

<!-- 이 명령의 리포트는 공개 저장소에 커밋된다. 자격증명·서비스계정 이메일·토큰을 리포트에 절대 쓰지 않는다. -->

<pipeline name="health-check">
  <mode_contract>
    - **무인 전용.** 대화형 도구를 호출하지 않는다. 사람에게 물어볼 일이 생기면 묻는 대신 §8 대기열에 적고 알림을 켠다.
    - 모든 Python은 `.venv/bin/python` 전용.
    - 리포트·원장·수정은 전부 **`main` 직행 단일 커밋**이다. 브랜치도 PR도 만들지 않는다 (2026-08-27 무인 운영 전환).
    - 커밋 제목은 `health: YYYY-MM-DD 격주 점검`. 본문 형식은 §9에 고정돼 있고 `notify-health.yml`이 그것을 읽는다.

    <persona>
      SEO/GEO 전문가로서 본다. 이 페르소나가 정하는 것은 **무엇을 볼지**(어떤 축을 어떤
      순서로 의심할지)이지 **무엇을 근거로 삼을지**가 아니다. 판정은 여전히 스크립트
      출력에서만 나온다 — "전문가 감각상 좋아 보인다"로 수치를 보정하지 않는다.
      (`direction-review.md`의 무페르소나 규약은 그 스테이지 안에서 그대로 유효하다.)
    </persona>
  </mode_contract>

  <notification_policy>
    <!--
      사용자가 정한 기준: "사람에게 메시지 보내는 경우는 꼭 필요한 경우에만".
      기본값은 침묵이다. 아래 넷 중 하나에 해당할 때만 `알림: 필요`를 켠다.
      고쳤다는 사실 자체는 알릴 이유가 아니다 — 그러라고 무인화한 것이다.
    -->
    | 켜는 경우 | 판정 근거 |
    |---|---|
    | ① 월간 현황 리포트 | `scripts/health_state.py`의 `monthly_due == true` |
    | ② 사람 승인 필요 | 이 명령의 쓰기 허용 범위(§7) 밖인데 해야 할 변경이 있다 |
    | ③ 사람만 할 수 있는 작업 | §8 대기열에 새 항목이 1건 이상 (GSC 제출·네이버 조회·광고·폐쇄 등) |
    | ④ 중대 고장 | 발행이 7일 이상 멈춤 · 유지보수가 2회 연속 안 돎 · Hugo 빌드 실패 · 색인 역행 |

    나머지 회차는 리포트만 `main`에 올리고 조용히 끝낸다. `알림: 불필요`를 적으면
    `notify-health.yml`이 아예 돌지 않는다.
  </notification_policy>

  <stages>
    <stage id="1" name="pre_guard">
      - KST 날짜 산출: `.venv/bin/python .claude/audit/lib/kstdate.py`. 이후 모든 YYYY-MM-DD는 이 값.
      - 워킹 트리 클린 여부 확인 (`git status`). 더러우면 그 자리에서 중단하고 보고한다.
      - `git pull --rebase origin main` — 발행이 매일 돈다.
      - 원장 조회: `.venv/bin/python scripts/health_state.py --date <KST>`.
      - **`run_due`가 `false`면 그 자리에서 조용히 끝낸다.** 아무것도 쓰지 않고, 커밋하지 않고, 알리지 않는다. "이번 주는 격주 주기가 아님"만 보고하고 종료한다.
      - 트리거는 **매주** 발화한다. 격주 주기를 cron으로 쓸 수 없어서(요일과 일자를 같이 제한하면 AND가 아니라 OR로 해석된다) 주기 판정을 원장으로 옮겼다 — 한 회차를 놓쳐도 다음 발화가 그대로 이어받고 위상이 영구히 어긋나지 않는다.
      - `monthly_due`(월간 리포트 차례인가)와 `previous_run`(지난 회차 날짜)을 §9로 넘긴다.
    </stage>

    <stage id="2" name="upkeep_check" file=".claude/audit/system-scan.md">
      <!-- 주간 유지보수는 텔레그램을 쓰지 않는다. 그것이 돌았는지 확인하는 곳이 여기다. -->
      - `ls -1 report/housekeeping-*.md | sort | tail -3` — 최신 리포트 날짜를 본다.
      - 지난 회차 이후 유지보수 리포트가 **0건**이면 워크플로가 죽은 것이다. ④ 중대 고장으로 올린다.
      - 최신 유지보수 리포트를 Read해 `## ⚠ 계약 위반 및 시스템 에러` 절을 확인한다. 헬퍼 에러가 있으면 그것부터 고친다(§7).
      - 발행 연속성: `content/posts/*.md`의 `date`를 훑어 최근 7일 발행 건수를 센다. 0건이면 ④ 중대 고장.
      - 방치 초안: `draft: true`인 포스트를 센다. `daily-post` §6이 보류한 글이 여기 쌓인다. 3건 이상이면 발행 게이트가 상시로 걸리고 있다는 뜻이므로 원인까지 적는다.
      - **Q3 사전 미등재 용어 후보**: `system-scan.md` §Q3의 절차를 실행한다. 유지보수의 결정론 헬퍼가 못 하는 유일한 ④ 축이다 — 빈도표에서 경제 용어로 보이는 것만 최대 5건 고른다. 사전 항목 신규 작성은 산문이므로 **하지 않는다**(소견으로만 남겨 `/daily-post`가 다음에 다루게 한다).
    </stage>

    <stage id="3" name="stage_performance" file=".claude/audit/performance.md">
      - Read 후 성과 분석 및 Corpus Gate(20건/28일/3군) 판정.
      - 게이트 통과 시에만 `topic-report.md` 및 `topic-history.json`을 갱신한다.
      - `published_count`, `site_age`, GSC 28일 클릭·노출을 §4·§6·§8·§9로 전달한다.
    </stage>

    <stage id="4" name="stage_indexation" file=".claude/audit/indexation.md">
      - Read 후 색인 건전성 판정 (I1~I7).
      - **색인 제출·GSC 조작은 여전히 사람 몫이다** — 대상 URL 목록을 §8 대기열로 넘긴다.
    </stage>

    <stage id="5" name="stage_seo_geo" file=".claude/audit/seo-geo.md">
      - Read 후 렌더 산출물 크롤 감사(여덟 축). 고칠 수 있는 결함을 §7로 넘긴다.
    </stage>

    <stage id="6" name="stage_direction" file=".claude/audit/direction-review.md">
      - Read 후 포트폴리오 축(D1~D6) 측정 및 가설 대조. 갱신된 `direction-log.json`을 §9로 넘긴다.
      - 무인이므로 가설은 `제안`까지만 올린다.
    </stage>

    <stage id="7" name="autofix">
      <!--
        승인 게이트가 없어진 자리에 들어온 자율 수정 권한이다. 범위를 좁게 못박아 둔다 —
        "알아서 고쳐라"를 무제한으로 읽으면 이 패스가 사이트를 다시 쓰기 시작한다.
      -->
      <write_allowed>
        - `content/**` front matter의 `description`·`title`·`faq`·`tags`
        - `content/**` 본문의 **H2 제목 줄** (옛 고정 제목 -> 주제어 포함 제목)
        - `content/**` 본문의 내부 링크 앵커 (`[용어](/dictionary/slug/)` 추가·정정)
        - `layouts/` 의 구조화 데이터 템플릿(JSON-LD 필드 추가)과 `home.llms.txt`·`home.llmsfull.txt` 출력 템플릿
        - `.claude/audit/*.json` 원장, `report/`
      </write_allowed>
      <write_forbidden>
        - `content/**` 본문 산문 (H2 제목 줄과 링크 앵커를 제외한 모든 문장)
        - `.claude/daily-post/` 전체 (`topics.yaml`·`writing-styles.md` 포함 — loop이 소유한다)
        - `hugo.toml` 의 `baseURL`·`theme`, `.github/workflows/**`, 자격증명 관련 일체
        - 발행된 글의 삭제·비공개 전환
      </write_forbidden>
      <limits>
        - **회차당 `content/` 파일 12개까지.** 남은 것은 리포트에 적고 다음 회차로 넘긴다. 한 번에 코퍼스를 통째로 다시 쓰지 않는다 — 되돌리기 어려운 변경을 한 커밋에 몰면 무엇이 무엇을 깨뜨렸는지 알 수 없다.
        - 심각도 `high` 결함을 먼저 고친다. `low`는 예산이 남을 때만.
      </limits>
      <verification>
        수정 후 **반드시** 이 순서로 검증한다. 하나라도 실패하면 그 파일의 수정을
        `git checkout --` 으로 되돌리고 소견으로만 남긴다:

```bash
.venv/bin/python .claude/audit/lib/numerics.py
.venv/bin/python .claude/audit/lib/headings.py
.venv/bin/python .claude/audit/lib/contracts.py --check terms
bash scripts/bootstrap_sandbox.sh && export PATH="$HOME/.local/bin:$PATH"
git submodule update --init --depth 1 themes/PaperMod
hugo --gc --minify && rm -rf public resources
```

        `numerics`·`headings`의 `total`이 0, `contracts`가 `[]`, Hugo 종료 코드 0이어야 한다.
      </verification>
      <write_forbidden_note>
        범위 밖인데 해야 할 변경은 고치지 말고 **§8 대기열에 「승인 필요」로 적는다**
        (알림 사유 ②). 제안하는 diff를 리포트에 붙여 사람이 읽고 바로 판단할 수 있게 한다.
      </write_forbidden_note>
    </stage>

    <stage id="8" name="human_queue">
      사람이 아니면 못 하는 것만 여기 온다. 형식은
      `- [ ] <분류> · <대상> · <확인할 것> · <확인 뒤 할 일>`
      (`/audit-local`이 이 형식을 읽는다 — 한쪽만 바꾸지 않는다).

      | 분류 | 언제 올리나 |
      |---|---|
      | 색인 제출 | ③이 "URL is unknown to Google"로 판정한 URL. 회차당 10건까지. |
      | 네이버 | 네이버 서치어드바이저 색인 수 조회·수집 요청 (샌드박스에서 도달 불가) |
      | 기준일 확인 | N1이 집어낸, 원문을 열어야 기준일을 알 수 있는 수치 |
      | 승인 필요 | §7 쓰기 금지 범위의 변경 제안 |
      | 광고 | 아래 성장 임계를 **모두** 충족: GSC 28일 클릭 ≥ 300 · 색인 페이지 ≥ 40 · 사이트 연령 ≥ 90일 |
      | 폐쇄 상의 | 아래를 **모두** 충족: 사이트 연령 ≥ 180일 · 최근 3회 연속 점검에서 GSC 28일 클릭 < 10 · 색인 커버리지 < 20% |

      광고·폐쇄 두 항목은 **임계를 실제로 계산해 본 뒤에만** 올린다. 근거 수치를 항목에
      함께 적는다 — "성장한 것 같다"는 판단은 이 파이프라인의 산출물이 아니다.
      임계에 못 미치면 조용히 넘어간다(리포트 본문에는 현재 값을 적어 둔다).
    </stage>

    <stage id="9" name="report_and_commit">
      - `report/health-YYYY-MM-DD.md` 작성. 헤딩 순서:
        (1) 요약 (2) 운영 연속성 (3) ② 성과 (4) ③ 색인 (5) SEO/GEO 크롤 (6) ⑤ 방향
        (7) 이번 회차 자동 수정 (8) 로컬 세션 대기열
      - `monthly_due == true`면 (1) 요약 앞에 `## 월간 현황`을 넣는다: 발행 누계·색인 수·GSC 28일 클릭/노출 추이(지난 달 대비)·자동 수정 누계·다음 달 방향 1~2줄.
      - 원장 기록:

```bash
.venv/bin/python scripts/health_state.py --record --date <KST> \
  [--monthly] [--notified] --fixes <N> --human-items <N>
```

      - 커밋. 본문 형식은 `notify-health.yml`과의 계약이므로 글자 그대로 지킨다:

```
health: YYYY-MM-DD 격주 점검

## 점검 요약
알림: 필요 | 불필요
월간 리포트: 예 | 아니오
자동 수정: N건
사람 작업: N건
발행 누계: N건 / 색인: N건
GSC 28일: 클릭 N · 노출 N
─ 사람이 해야 할 일 ─
* <대기열 항목 또는 없음>
리포트: report/health-YYYY-MM-DD.md
```

      - `알림: 필요`는 §0 표의 넷 중 하나에 해당할 때만 쓴다. 이 줄이 곧 발신 스위치다.
      - `─ 사람이 해야 할 일 ─` 아래 불릿만 알림에 실린다. 그 위의 불릿은 실리지 않는다.

```bash
git add -A report/ .claude/audit/ content/ static/ layouts/
git commit --cleanup=verbatim -m "health: <KST> 격주 점검" -m "<위 본문>"
git pull --rebase origin main
git push origin main
```
    </stage>

    <stage id="10" name="final_report">
      - 여섯 축 판정, 자동 수정 목록, 대기열 항목, 알림 발신 여부, 푸시 결과를 최종 요약 출력.
    </stage>
  </stages>
</pipeline>
