# AGENTS.md

<system_context>
  <site_info>
    한국 경제뉴스를 비전문가에게 설명하는 Hugo 정적 사이트 (테마: PaperMod, `themes/PaperMod` 서브모듈), GitHub Pages 배포.
    Hugo 버전: 0.164.0 (CI와 로컬 버전 일치 필수).
    모든 Python 호출: `.venv/bin/python` 전용 (pytest 미사용, `if __name__ == '__main__'` 스탠드얼론 unittest).
  </site_info>

  <environment_constraints>
    - 루틴 샌드박스는 외부 웹(뉴스 사이트, Google API, 텔레그램 API 등)에 도달할 수 없다 (GitHub, PyPI, npm만 허용).
    - WebFetch는 동작하지 않으며, WebSearch만 동작한다.
    - 외부 뉴스/데이터 수집은 GitHub Actions (`daily-collect.yml`, `weekly-collect.yml`)가 비공개 사이드카(`econ-blog/automation-data`)에 수집하여 스냅샷으로 제공한다.
    - **Claude 세션은 텔레그램을 직접 보낼 수 없다.** 알림은 전부 "`main`에 파일을 커밋하면 워크플로가 그것을 보고 보낸다" 구조다. 세션이 `scripts/telegram_notify.py`를 직접 호출하려 하면 조용히 실패한다.
  </environment_constraints>

  <operating_model>
    <!-- 2026-08-27 무인 운영 전환. 그 이전 구조(초안 -> PR -> 텔레그램 승인 -> 다음날 인박스가 병합)는 전부 제거됐다. -->
    사람의 승인 없이 스스로 도는 시스템이다. 사람이 개입하는 지점은 **선택적인 사후 수정**
    (`/revise-post`)과 **샌드박스가 못 하는 외부 작업**(`/audit-local`) 둘뿐이다.

    | 주기 | 무엇이 | 무엇을 | 사람에게 |
    |---|---|---|---|
    | 매일 01:30 KST | `daily-collect.yml` | 오늘 후보 수집 -> 사이드카 | 실패 시에만 경보 |
    | 매일 05:00 KST | `/daily-post` (무인) | 글 작성 -> `main` 직행 발행 | **매일 본문 전송** |
    | 매주 일 01:20 KST | `weekly-collect.yml` | GA4·GSC·링크상태 -> 사이드카 | 실패 시에만 경보 |
    | 매주 일 02:00 KST | `weekly-housekeeping.yml` | 결정론 유지보수 -> `main` 직행 | **아무것도 보내지 않음** |
    | 격주 | `/health-check` (무인) | SEO/GEO 전수 점검 + 자율 수정 -> `main` 직행 | **꼭 필요할 때만** |

    격주 점검이 사람을 부르는 경우는 넷뿐이다: ① 월 1회 현황 리포트 ② 사람 승인이 필요한
    변경 ③ 사람만 할 수 있는 작업(GSC 색인 제출, 네이버 서치어드바이저 조회, 광고 도입,
    폐쇄 상의) ④ 중대 고장. 그 외에는 리포트만 올리고 조용히 끝낸다.
  </operating_model>
</system_context>

<command_registry>
  <command name="/daily-post" file=".claude/commands/daily-post.md">
    - 일간 뉴스 해설 포스트 작성 및 발행.
    - 인자 없음 = 무인 모드 (`draft: false` + `main` 직행. 승인 없음, 브랜치·PR 없음).
    - `manual` 인자 = 대화형 수동 모드 (후보 3건 제시 -> 선택 -> 승인 후 `main` 푸시).
    - 발행 전 결정론 검사(N1~N5, T1~T4, contracts)가 **유일한 게이트**다. 위반이 남으면 `draft: true`로 보류해 `main`에 올린다.
  </command>

  <command name="/revise-post" file=".claude/commands/revise-post.md">
    - 이미 `main`에 있는 그날 글의 사후 수정. 대화형 전용, 승인 후 `main` 푸시.
    - 커밋 제목은 `post(revise): ` — `post: `로 쓰면 텔레그램이 같은 글을 두 번 보낸다.
  </command>

  <command name="/health-check" file=".claude/commands/health-check.md">
    - 격주 1회 SEO/GEO 점검 (운영 연속성, ② 성과, ③ 색인, SEO/GEO 크롤, ⑤ 방향).
    - 고칠 수 있는 것은 §7의 쓰기 허용 범위 안에서 스스로 고쳐 `main`에 직행한다 (회차당 `content/` 12파일 상한).
    - 리포트는 `report/health-YYYY-MM-DD.md`. 알림 발신 여부는 커밋 메시지의 `알림:` 줄이 정한다.
  </command>

  <command name="/weekly-housekeeping">
    - 순수 Python 무인 유지보수 (`scripts/housekeeping.py`, GitHub Actions 매주 일요일).
    - ① 링크 · ④ 스캔 · ⑥ 수치를 결정론적으로 돌리고 리포트·원장·본문 정정을 `main`에 직행시킨다.
    - **텔레그램을 쓰지 않는다.** 안전장치는 알림이 아니라 커밋 앞에 놓인 단위 테스트다.
  </command>

  <command name="/audit-local" file=".claude/commands/audit-local.md">
    - 로컬 대화형 전용 세션. 격주 점검 리포트의 「로컬 세션 대기열」을 처리한다 (색인 제출, N1 기준일 확인 등).
  </command>
</command_registry>

<content_model>
  <posts path="content/posts/<slug>.md">
    - Front matter: `title` (40자 이하), `date` (+09:00 KST), `description` (100자 내외), `tags` (2~3개, topics.yaml 목록 내), `draft`, `source_url`, `faq` (선택/권장 2개), `related_articles` (선택).
    - `draft`는 발행 전 검사 결과가 정한다: 통과 -> `false` (발행), 위반 잔존/검사 불가 -> `true` (보류).
    - 본문: 볼드체(`**`) 절대 금지, 선 정의 후 비유, 4단 H2 구성, 투자 관점 섹션(3단계 인과 사슬 + 시소 매트릭스).
  </posts>

  <dictionary path="content/dictionary/<term-slug>.md">
    - Front matter: `title`, `date`, `description` (한 문장 정의 필수), `tags: ["용어사전"]`, `draft` (같은 회차 포스트와 동일한 값).
    - 슬롯: 리드 정의 + `## 실생활에서는` + `## 투자에서는` + (선택)`## 숫자로 보면` + (선택)`## 함께 보면 좋은 용어`.
    - 색인 진리원: `content/dictionary/_terms.yaml` (새 용어 추가 시 동시 등록 필수).
  </dictionary>

  <wikilinks>
    - Goldmark 상대 링크: `[용어](/dictionary/slug/)`
    - `[[...]]` shortcode 문법 금지.
  </wikilinks>
</content_model>

<critical_contracts>
  <contract name="commit_prefix_routing">
    **`main` 커밋의 제목 접두사가 곧 알림 배선이다.** 워크플로가 이 접두사만 보고 반응하므로,
    틀리게 쓰면 오류 없이 그냥 아무 일도 일어나지 않는다.

    | 접두사 | 쓰는 곳 | 반응하는 워크플로 |
    |---|---|---|
    | `post: ` | `/daily-post` 발행·보류 | `notify-post.yml` -> 텔레그램 본문 전송 |
    | `post(revise): ` | `/revise-post` | **없음** (의도적 — 사람이 세션 안에 있다) |
    | `audit: ` | `weekly-housekeeping.yml` | **없음** |
    | `health: ` | `/health-check` | `notify-health.yml` (본문에 `알림: 필요`가 있을 때만) |
  </contract>

  <contract name="commit_body_summary_block">
    `/daily-post`는 커밋 본문에 `## 발행` 블록을, `/health-check`는 `## 점검 요약` 블록을
    싣는다. `scripts/telegram_notify.py`가 그 블록만 잘라 읽는다 (`extract_block`).
    `키: 값` 줄과 `─ 사람이 해야 할 일 ─` 아래 불릿만 알림에 실린다.
    한쪽 형식을 바꾸면 다른 쪽 알림이 "요약 정보 없음"이 된다.
  </contract>

  <contract name="analysis_4_fields">
    `analysis.md`가 방출하는 4개 필드(`건드리는 렌즈`, `선행 vs 동행`, `확인된 수치`, `자산군별 함의`)는 `draft.md` §2에서 빠짐없이 소비되어야 한다.
  </contract>

  <contract name="terms_yaml_sync">
    `content/dictionary/*.md` 파일과 `content/dictionary/_terms.yaml`의 슬러그 키는 항상 100% 양방향 일치해야 한다 (`contracts.py --check terms`).
  </contract>

  <contract name="primary_source_hosts">
    1차 출처 인정 호스트는 `numerics.py`의 `PRIMARY_HOSTS` 6개(ECOS, FRED, KOSIS, DART, 전국은행연합회 소비자포털, BIS)로 단일화되어 있다.
  </contract>

  <contract name="headings_discipline">
    포스트 본문 H2는 정확히 4개이며, 옛 고정 제목을 금지하고, 4개 중 최소 3개는 `title`의 핵심 주제어를 포함해야 한다 (`headings.py`).
  </contract>

  <contract name="topic_report_format">
    `topic-report.md`는 최상단 `생성일: YYYY-MM-DD`로 시작하며, `## 잘 되는 주제`, `## 안 되는 주제`, `## 좋은 포스트의 조건` 섹션과 `(조정치: ±N)` 표기를 엄격히 준수한다.
  </contract>
</critical_contracts>

<runtime_invariants>
  - **무인 불변조건**: `main`에만 푸시 · 단일 커밋만 푸시 (`git commit --cleanup=verbatim`) · 대화형 도구 호출 금지 · 푸시 직전 `git pull --rebase origin main` · 1위 후보 < 8점이면 조용히 종료.

  - **`auto/**` 브랜치 규칙은 폐기됐다 (2026-08-27).** 2026-08-19 실사고 이후 "무인 커밋은 반드시 `auto/post-*`·`auto/audit-*`로"라는 규칙이 있었다. 그 규칙은 `open-auto-pr.yml`(PR 자동 생성)과 `notify.yml`(승인 알림)이 그 접두사에만 배선돼 있었기 때문에 존재했고, **두 워크플로 모두 제거됐다.** 지금 `auto/**`로 푸시하면 그때와 똑같은 방식으로 아무 일도 일어나지 않는다 — 오류 없이, 글이 사이트에 오르지도 텔레그램이 가지도 않는다. 발행 경로는 `main` 하나다.

  - **CCR 세션 지정 브랜치 우선순위**: Claude Code 세션이 별도의 "세션 지정 브랜치"(예: `claude/xxx`)를 요구하더라도, 무인 발행·점검 커밋은 `main`으로 간다. 시스템 자체를 고치는 작업(워크플로·스크립트·명령 파일 수정)은 지정 브랜치를 따른다 — 그쪽은 사람이 읽고 병합할 변경이다.

  - **발행 게이트**: 무인 발행은 결정론 검사가 유일한 게이트다. 위반을 안고 발행하지 않는다. 버리지도 않는다 — `draft: true`로 `main`에 남겨 격주 점검의 Q4(방치 초안)와 `/revise-post`가 처리할 수 있게 한다.

  - **수동 불변조건**: 명확한 사용자 긍정 확인 후에만 `draft: false` 변경 및 `main` 푸시. "좋아요"·"괜찮네요"는 승인이 아니다.

  - **쓰기 금지 영역**: 점검·유지보수 실행 시 `.claude/daily-post/` 전체(`topics.yaml`·`writing-styles.md` 포함), `hugo.toml`의 `baseURL`·`theme`, `.github/workflows/**`, `content/` 본문 산문(H2 제목 줄과 링크 앵커는 예외 — `health-check.md` §7)은 수정하지 않는다.

  - **자율 수정 상한**: 격주 점검은 회차당 `content/` 12파일까지만 고친다. 수정 후 `numerics`·`headings`·`contracts`·Hugo 빌드를 전부 통과해야 하며, 하나라도 실패하면 그 파일을 되돌리고 소견으로만 남긴다.
</runtime_invariants>
