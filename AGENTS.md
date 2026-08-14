# AGENTS.md

이 저장소에서 작업하는 에이전트가 **매 실행에 알아야 하는 것**만 담는다. 배경·근거·이력은 `MEMORY.md`에 있다.

**AC 번호는 더 이상 해소되지 않는다.** 스테이지 파일과 `lib/*.py` 주석 곳곳에 `SEED AC #NN`·`Known limits #N` 표기가 남아 있으나 원본 Seed(`.claude/audit/SEED-weekly-audit.md`)는 2026-08-01에 삭제됐다(git 이력 `9c6bd4d` 이전 커밋에서 복원 가능). **그 표기는 출처 주석일 뿐 조회 대상이 아니다** — 실행에 필요한 규칙은 전부 이 파일과 스테이지 파일 본문에 있다. AC 번호를 근거로 새 판정을 만들지 않는다.

## 무엇인가

한국 경제뉴스를 비전문가에게 설명하는 Hugo 정적 사이트(테마: PaperMod, `themes/PaperMod` 서브모듈), GitHub Pages 배포. 산출물은 (a) Hugo 콘텐츠·설정과 (b) 그것을 만드는 `/daily-post`·`/weekly-audit` 슬래시 명령이다.

**렌더 경로에 우리가 쓴 코드는 없다.** Python(`.claude/audit/lib/`, `scripts/`)은 통지·감사·인박스 자동화 및 오프라인 도구로 GitHub Actions Workflows(`.github/workflows/`)에서 실행된다.

## 명령

```bash
hugo server              # 로컬 개발 서버
hugo --gc --minify       # 프로덕션 빌드 (CI가 돌리는 것) → ./public
```

CI(`.github/workflows/hugo.yml`)는 `main` push 시 Hugo **0.164.0**으로 빌드해 `actions/deploy-pages`로 배포한다. `gh-pages` 브랜치는 없다. 로컬 Hugo를 그 버전에 맞춘다.

**모든 Python 호출은 `.venv/bin/python`이다.** 의존성은 `requirements.txt`에 핀 조치되어 있다(`google-analytics-data==0.23.0`, `google-api-python-client==2.198.0`, `google-auth==2.56.2`, `requests==2.34.2`, `trafilatura==2.0.0`). GitHub Actions 및 로컬 execution 시 가상환경(`.venv`)을 사용한다.

## 검증

사이트 자체에는 린터도 테스트도 없다 — 프롬프트 파일 + 마크다운 + Hugo 설정이다. Python은 예외로 테스트가 있다.

```bash
for f in .claude/audit/lib/test_*.py; do .venv/bin/python "$f"; done
```

```bash
for f in scripts/test_*.py; do .venv/bin/python "$f"; done
```

새 측정 헬퍼를 추가하면 테스트를 함께 낸다.

**pytest는 설치되어 있지 않다.** 테스트는 `if __name__ == "__main__"` 스탠드얼론 `unittest`이며 위처럼 파일을 직접 실행한다. `tests/` 디렉터리도 `scripts/__init__.py`도 없다 — `pytest tests/...`나 `from scripts.x import y`를 쓰는 계획은 그 자리에서 실패한다.

`.claude/commands/*.md` 또는 `.claude/daily-post/*.md`를 고친 뒤:

1. `hugo --gc --minify`가 새 오류 없이 성공하고 **`Non-page files`가 1로 유지**되는지 확인한다(그 1은 `content/dictionary/_terms.yaml`이 올바르게 건너뛰어진 것이다). `Pages`는 발행마다 늘어나므로 고정값으로 보지 않는다.
2. 교차 참조(절 번호·파일 경로·필드명)가 실제로 해소되는지 grep한다.

## GitHub CLI

`gh`를 쓴다. 먼저 `gh auth status`. 읽기는 `gh pr view`·`gh pr checks`·`gh run view`. **`gh`로 merge·close·delete·push를 사용자 승인 없이 하지 않는다.** 포스트·사전 초안은 승인 전까지 `draft: true`를 유지한다.

## `/daily-post`

인자 없음 = **무인 모드**, `manual` = **대화형**. `.claude/commands/daily-post.md`는 얇은 7단계 시퀀서(§0–§6)이며 작성 로직이 거기 있지 않다 — `.claude/daily-post/` 아래 스테이지 파일을 `Read`한다.

| 단계 | 파일 | 하는 일 |
|---|---|---|
| §1 랭킹 | `rank.md` | `read_snapshot.py`로 사이드카 후보 스냅샷을 읽는다(RSS 직접 수집 없음). 5기준 0–15점, 8점 바닥. `topics.yaml`의 `focus: true` 주제(금리·물가·부동산·반도체)에 +1 가점, 합산 뒤 0–15로 clamp — 만점과 임계값은 고정이다. 무인은 1위 자동 선택, 바닥 미달이면 조용히 중단. 수동은 3건 제시. |
| §2 원문 | 시퀀서 | 스냅샷의 `body_text`. WebFetch를 쓰지 않는다 — 샌드박스가 뉴스 사이트에 도달할 수 없다. `body_ok` 미달이면 후보를 폐기하고 중단한다. |
| §3 연관 기사 | 시퀀서 | WebSearch. 실패·0건이면 필드를 통째로 생략한다. URL을 지어내지 않는다. |
| §4 분석 | `analysis.md` | 3렌즈 분류 + 선행/동행 태깅, `macro-reference.md` 1회 조회, 지표 1–2개의 🟢/🟡/🔴 임계값. **디스크에 저장하지 않는다.** |
| §5 작성 | `draft.md` | 포스트 + 사전 항목 + 위키링크. 산문·톤 규칙은 `writing-styles.md`에 위임. 끝에 **발행 전 결정론 검사**(§5-1~5-4) + 제목 검사. |
| §6 게시 | 시퀀서 | 발행 게이트 — 아래. |

**발행 게이트.** 무인은 항상 `draft: true`를 쓰고 `auto/post-YYYY-MM-DD` 브랜치 + PR로만 올린다. `main`에 절대 직접 푸시하지 않는다. 수동은 구체적 승인 질문에 **명확한 긍정**을 받은 뒤에만 `draft: false`로 바꿔 `main`에 푸시한다. "좋아요"·"괜찮네요"는 승인이 아니다.

**발행 전 검사 게이트(§J).** `draft.md` §5가 `.claude/audit/lib/`의 N1·N2·N4·N5, `_terms.yaml` 정합, 그리고 제목 규율 T1~T4(`headings.py`)를 돌린다. 결과는 `통과` · `남은 위반 N건` · `검사 불가` 셋 중 하나이며 §6이 그것으로 분기한다. **`검사 불가`를 `통과`와 같게 취급하지 않는다.** N 검사 코드는 감사 ⑥과 **같은 모듈**이다 — 재구현하면 쓰기시점과 감사시점의 판정이 갈린다. **T 검사는 쓰기시점 전용이며 감사에 배선하지 않는다** — 2026-08-10 결정으로 기존 17건의 옛 제목은 그대로 두므로, 감사에 넣으면 매주 같은 17행이 소견으로 되살아난다.

**무인 불변조건** (각 스테이지 파일에서 각각 강제한다): `auto/post-YYYY-MM-DD`에만 푸시 · 단일 커밋만 푸시 (`git commit --cleanup=verbatim` 1건) · 항상 `draft: true` · 대화형 도구 호출 금지 · 1위가 8/15 미달이면 산출물 없이 중단.

## `/revise-post` (수정 발행 · 대화형 클라우드 세션)

승인 루프에는 두 갈래가 있다. **승인**은 텔레그램에 `승인 #P0814`로 답하면 다음날
01:30 인박스가 집행한다. **수정**은 사람이 claude cloud session을 직접 열어
`/revise-post`를 돌리고, 그 세션이 그 자리에서 집행한다 —
`.claude/commands/revise-post.md`가 절차다.

수정 경로는 `main`에 직접 커밋·푸시하고 그날 `auto/post-YYYY-MM-DD` PR을 **닫는다**
(병합이 아니다 — 병합하면 `draft: true` 버전이 되살아난다). 이것은 무인 규약의
예외가 아니라 `/daily-post` 수동 모드와 같은 등급이며, 승인 게이트와 발행 전 검사
게이트를 그대로 거친 뒤에만 일어난다.

**다음날 인박스가 조용한 것은 자동이다.** PR이 닫혀 있으면 `get_open_prs()`가
빈 목록을 돌려주므로 인박스도 재질의(`--reask`)도 할 일이 없다. "이미 발행했으니
건너뛰라"는 플래그를 따로 만들지 않는다 — 만들면 PR 상태와 플래그가 갈린다.

**수정 세션은 `auto/**` 브랜치에 아무것도 밀지 않는다.** 그 푸시는
`open-auto-pr.yml`을 깨우고, 그 시점에 PR을 만들 이유가 없다.

텔레그램에 `수정`은 판정 어휘가 아니다. `process_inbox.py`는 승인/반려만 알고
그 밖의 답장은 `판정불가`로 되돌려 보낸다 — 수정할 날은 답장하지 않고 세션만 연다.

## `/weekly-housekeeping` (무인 유지보수 · LLM 없음)

GitHub Actions(`.github/workflows/weekly-housekeeping.yml`, 외부 cron-job.org 호출)로 자동 실행된다. ① 링크+백필 · ③ 색인 · ④ E/Q(결정론 규칙) · ⑥ 수치 축을 순수 Python(`scripts/housekeeping.py`)으로 판정하고 기계적 정정을 적용한다.

- **산출물**: `report/housekeeping-YYYY-MM-DD.md` · `.claude/audit/link-state.json`.
- **알림**: 텔레그램 알림을 보내지 않는다 (`report/housekeeping-*.md` 경로 사용으로 `notify-audit-report.yml` 미발화). 워크플로 실행 실패 시에만 실패 경보를 보낸다.
- **git**: 리포트·원장은 `main` 직행, `content/` 정정(확정 사망 링크 제거 · 백필)이 발생할 때만 `auto/audit-YYYY-MM-DD` 브랜치 + PR 생성.

## `/audit-improvement` (수동 개선 · LLM 사용)

`.claude/commands/audit-improvement.md`로 사람이 필요 시 수동 실행한다. ② 성과 · ⑤ 방향 · ④ Q3(미등재 용어 후보 선별) 등 판단과 LLM이 필요한 축을 담당한다.

- **산출물**: `report/audit-YYYY-MM-DD.md` · `.claude/audit/topic-history.json` · `.claude/audit/direction-log.json` · `.claude/audit/topic-report.md`(데이터 충분성 게이트 통과 시에만).
- **알림**: `report/audit-YYYY-MM-DD.md` 커밋 시 `notify-audit-report.yml`에 의해 텔레그램 알림 발송.
- **기타**: ② 성과 분석 데이터 미달 시 `topic-report.md` 부재 유지는 기존과 동일.
- **쓰기 금지**: `.claude/daily-post/` 전체 · `hugo.toml` · `CLAUDE.md` · `MEMORY.md` · `layouts/` · `content/` 본문 산문. `content/`에서 허용되는 변경은 셋뿐이다 — 확정 사망 링크 수정 · 내부링크 백필 · **Q1 front matter 결함 수정**(description 누락·길이. 2026-08-10 추가). 셋 다 `auto/audit-*` PR로만 나가며 승인 없이 `main`에 가지 않는다. **본문 산문은 여전히 손대지 않는다.**

## 조용히 깨지는 계약 셋

양쪽을 동시에 고치지 않으면 런타임에 오류 없이 드롭된다.

1. **분석 4필드** — `analysis.md`가 방출하는 `건드리는 렌즈` / `선행 vs 동행` / `확인된 수치` / `자산군별 함의` 각각에 `draft.md` §2의 소비 불릿이 하나씩 대응해야 한다. 대응 없는 필드는 조용히 사라진다. 한 번 일어났고 사람 리뷰가 잡았다.
2. **감사 점수 계약** — 아래 「`topic-report.md` 형식 계약」이 형식을 고정하고 `rank.md`가 그것을 읽는다. 어느 쪽도 단독으로 재설계하지 않는다.
3. **`_terms.yaml` 정합** — `draft.md` §3이 사전 파일 생성과 `_terms.yaml` append를 **따로** 하므로 한쪽만 하면 그 자리에서 깨진다. `/daily-post` §5의 계약 검사가 이것 하나를 본다.

## `topic-report.md` 형식 계약

`rank.md`가 소비하는 `.claude/audit/topic-report.md`의 형식이다. 감사 ②는 **데이터 충분성 게이트를 통과할 때만** 이 파일을 쓴다. 게이트가 미달인 동안 파일은 존재하지 않으며 그것이 정상 상태다 — 없으면 `rank.md`가 조용히 건너뛴다.

이 계약은 재설계 대상이 아니다. 생성 측(`.claude/audit/lib/topicreport.py` + 골든 테스트 `test_topicreport.py`)과 소비 측(`rank.md`)을 동시에 고치지 않으면 조용히 깨진다.

```markdown
생성일: YYYY-MM-DD

## 잘 되는 주제
- <주제 설명> (조정치: +N)

## 안 되는 주제
- <주제 설명> (조정치: -N)

## 좋은 포스트의 조건
- <조건 설명>
```

- `생성일`은 최상단, 반드시 `YYYY-MM-DD`.
- 각 항목은 후보 총점에 더할 조정치를 `(조정치: ±N)`으로 명시한다. `rank.md`는 그 값을 그대로 읽고 재해석하지 않는다.
- 범위는 −2~+3. 벗어난 값은 `rank.md`가 범위 끝값으로 clamp한다.
- "좋은 포스트의 조건"은 점수에 반영되지 않는 참고 섹션이다.
- **신선도**: `생성일`이 90일을 넘으면 가점만 최대 +1까지 적용하고 감점은 적용하지 않는다. 낡은 데이터로 밀어주는 것보다 낡은 데이터로 탈락시키는 쪽이 더 위험하다.
- 15점 만점·8점 임계값은 이 파일의 존재 여부와 무관하게 고정이다. 리포트는 조정치일 뿐 채점 기준을 바꾸지 않는다.
- **감쇄는 이 계약 밖이다.** 음수 조정치가 60일 이상 유지되면 절대값을 1 줄인다(−2 → −1 → 0). 양수는 감쇄하지 않는다. 매주 재생성하면 `생성일`이 영원히 최신이라 90일 신선도 규칙이 무력하므로, 감쇄에 필요한 날짜 상태는 `topic-history.json`에 따로 보관한다.

## `.claude/audit/lib/` 규약

- 실행: `.venv/bin/python .claude/audit/lib/<name>.py <args>` (시스템 python 금지).
- 측정 헬퍼(`mdtext`·`internal_links`·`backfill`·`corpus`)는 **표준 라이브러리 + 정규식만**. AST 파서·형태소 분석기·외부 의존성을 도입하지 않는다 — 클라우드 재현성 규약이다.
- `linkcheck.py`만 네트워크 I/O에 `requests`를 쓴다. 순수 로직(원장 갱신·판정)은 여전히 stdlib이며 테스트 대상이다.
- 각 헬퍼는 파일 경로를 argv로 받아 JSON을 stdout에 낸다. 같은 입력에 같은 출력이며 **LLM은 여기의 어떤 값도 산출하지 않는다.**
- 이 디렉터리의 `.py`는 에이전트 **소스**다. "산출물 5개 외 파일 금지"는 감사 **실행**이 남기는 파일에 대한 제약이지 소스에 대한 것이 아니다.
- 테스트: `.venv/bin/python .claude/audit/lib/test_<name>.py` — 전부 통과 시 "전부 통과", 실패 시 exit 1.

## 스테이지 파일이 `.claude/commands/` 밖에 있는 이유

Claude Code는 `.claude/commands/` **하위 디렉터리까지** 모든 `.md`를 슬래시 명령으로 자동 등록한다. 스테이지를 거기 두면 `/rank`·`/analysis`·`/draft`·`/writing-styles`·`/macro-reference`·`/link-check` 등이 조용히 생긴다. 네이티브 include가 없으므로 핸드오프는 "이 경로를 Read하라"는 산문이며, **양쪽의 경로 문자열을 정확하게 유지해야 한다.**

## 콘텐츠 모델

- `content/posts/` — 포스트 1건 = 파일 1개. front matter: `title`·`date`·`tags`·`draft`·`source_url`(원문 URL 축자), 선택 `faq`(`{q, a}` 목록)·`related_articles`(`{title, url, source}` 목록).
  - **파일명은 날짜 접두어 없는 슬러그다**(`tsmc-foundry-price-hike-10-percent.md`). 발행 순서가 필요하면 front matter `date`를 파싱한다 — 파일명·경로 정렬은 알파벳 정렬이다.
  - `related_articles`는 오래된 순, 같은 날 기사 제외, 배경 기사 우선. 살아남는 항목이 없으면 **키를 통째로 생략**한다 — 빈 리스트를 남기지 않는다.
  - 푸터 순서는 `layouts/partials/extend_post_content.html`: FAQ → 내부 관련글 → 외부 `related_articles` → 출처 링크 → 면책. FAQ가 맨 앞인 것은 본문의 연장이기 때문이고, 내부 관련글이 외부보다 먼저인 것은 체류시간이 pre-AdSense 유일 신호이기 때문이다. 외부 링크는 `rel="nofollow"`.
- `content/dictionary/` — 용어 1건 = 파일 1개, `tags: ["용어사전"]`.
- `content/dictionary/_terms.yaml` — **Hugo 페이지가 아니다**(`_` 시작 파일을 건너뛴다. "Non-page files"로 집계된다). slug → `{title, aliases}`이며 위키링크 매칭의 단일 진리원이다. `draft.md`와 `rank.md`가 사전 디렉터리를 스캔하는 대신 이 파일을 읽는다. **항목을 추가할 때 여기에도 append한다.** `aliases`는 다른 글이 실제로 쓸 동의어이며 문법적 활용형이 아니다.
- 위키링크는 평범한 Hugo/Goldmark 상대 링크(`[기준금리](/dictionary/base-rate/)`)다. **`[[...]]`를 쓰지 않는다** — shortcode가 없고 추가하지 않기로 한 결정이다.
- `archetypes/posts.md` · `archetypes/dictionary.md`는 슬래시 명령이 직접 쓰는 front matter를 반영한다.

## 저장소 규약

- 커밋 작성자: `bjh7790` / `bjh7790@gmail.com`.
- 로컬 push는 저장소 전용 SSH 키(`~/.ssh/id_ed25519_econblog`)로 인증한다 — 자격증명 프롬프트가 뜨지 않는다.
- **포스트·사전 초안을 사용자 승인 없이 커밋·푸시하지 않는다.** 이미 작성된 콘텐츠의 사소해 보이는 수정에도 적용된다.
- **`/docs/`와 `/.superpowers/`는 통째로 gitignored다.** 스펙·계획·리뷰 diff는 2026-08-01에 삭제했고 git 이력에도 없다 — 거기에만 있던 운영 지식은 이 파일과 `MEMORY.md`로 옮겼다. **그 디렉터리에 새 문서를 만들지 않는다.** 남길 것이 생기면 `AGENTS.md`(매 실행 필요)나 `MEMORY.md`(근거·이력)에 직접 쓴다.
- **자격증명은 `credentials.json` 하나다**(저장소 루트, gitignored). 스키마는 GitHub Secret `CREDENTIALS_JSON`과 **동일**하다: `{"telegram": {bot_token, chat_id}, "ga4": {"service_account": {…}}}`. 시크릿을 갱신할 때 이 파일을 그대로 올린다:

  ```bash
  gh secret set CREDENTIALS_JSON < credentials.json
  ```

  `scripts/credentials.py`가 단일 진입점이다. `service_account_path()`는 `GSC_CREDENTIALS`·`GA4_CREDENTIALS`·`GOOGLE_APPLICATION_CREDENTIALS` 환경변수(워크플로가 평탄한 SA 파일을 RUNNER_TEMP에 풀어 넘긴다)를 먼저 보고, 없으면 로컬 `credentials.json`의 `ga4.service_account`를 0600 임시 파일로 풀어 그 경로를 돌려준다(프로세스 종료 시 삭제). `fetch_ga4.py`·`fetch_gsc.py`가 이것만 쓴다 — 두 스크립트에 경로를 하드코딩하지 않는다.

## 자동화 평면 (매 실행에 알아야 하는 것)

**루틴 샌드박스는 뉴스 사이트·Google API·`econ-blog.github.io`에 도달할 수 없다.**
egress allowlist는 GitHub 계열 + PyPI + npm뿐이다(2026-07-30 프로브 3회 실측).
WebSearch는 동작하고 **WebFetch는 동작하지 않는다.**

따라서 열린 인터넷이 필요한 수집은 GitHub Actions가 하고, 결과는 **비공개** 사이드카
`econ-blog/automation-data`로 배달된다. `econ-blog.github.io`는 PUBLIC이므로 기사 본문
(제3자 저작물)과 분석 데이터를 여기 커밋하지 않는다.

**스케줄은 GitHub 크론이 아니라 cron-job.org가 건다** (2026-08-02 전환). 워크플로에
`schedule:` 트리거가 없다 — 전부 `workflow_dispatch`뿐이고, 외부 스케줄러가 REST API로
호출한다. 크론 시각을 바꾸려면 저장소가 아니라 cron-job.org 대시보드를 고친다. 근거와
잡별 설정값은 `MEMORY.md` §9.

| 워크플로 | 스케줄 (KST) | 트리거 | 잡 (순서) | 산출물 |
|---|---|---|---|---|
| `daily-collect.yml` | 매일 01:30 | cron-job.org | `inbox` → (`reask` ∥ `candidates`) | 승인 판정 처리 + 미결 재질의 + `candidates/YYYY-MM-DD.json` |
| `weekly-collect.yml` | 일 01:20 | cron-job.org | `analytics` ∥ `linkstate` | `analytics/YYYY-MM-DD/*.json` + `linkstate/YYYY-MM-DD.json` |
| `weekly-housekeeping.yml` | 일 01:40 | cron-job.org | `housekeeping` | `report/housekeeping-YYYY-MM-DD.md` + `.claude/audit/link-state.json` |
| `open-auto-pr.yml` | — | `push` on `auto/**` | — | PR (→ `notify.yml`) |
| `notify-audit-report.yml` | — | `push` on `main`의 `report/audit-*.md` | — | 감사 리포트 텔레그램 알림 |

루틴은 `/daily-post` 매일 05:00 KST, `/weekly-audit` 일 05:00 KST. 수집은 루틴보다 최소
3시간 앞에 둔다.

**하루는 한 방향으로 흐른다**: `인박스(어제 글 판정) → 후보 수집 → 루틴 05:00(오늘 글
PR 생성·텔레그램 발송)`. 인박스가 매일 도는 것을 전제하면 어제 PR이 닫힌 뒤 오늘 PR이 열린다.
다만 사람이 며칠치 판정을 몰아서 답하면 글 PR이 여럿 동시에 열려 있을 수 있으며, 이것은 정상 운영 범위다.

**판정 폴링은 하루 한 번이고 그것이 유일한 회수 경로다.** 텔레그램 `getUpdates`는
오프셋으로 확인되지 않은 업데이트를 **24시간만** 보관하고 그 뒤 영구 삭제한다. 따라서
회차 하나가 걸러지면 그 사이에 온 판정은 되찾을 수 없다 — 2026-08-07 01:30 회차가 러너를
배정받지 못해 취소되면서 08-06 21:29의 `승인 #P0804`가 그렇게 사라졌다(`MEMORY.md` §9).
**유실은 막을 수 없고, 교착만 깬다**: `reask` 잡이 같은 회차 끝에서 다시 물어본다.

**`reask`는 인박스 뒤에 와야 한다.** 앞에 두면 방금 승인한 PR까지 목록에 실려 "승인했는데
또 물어본다"가 된다 — 2026-08-08까지의 적체 경보가 폴링 **전에** 나가서 정확히 그랬고,
그래서 그 경보를 없앴다. `candidates`와 달리 `if: always()`를 붙이지 않는다: 인박스가
실패하면 판정이 소비되지 않은 채 넘어가므로 "아직 미결입니다"가 거짓이 된다.

**재질의 대상은 KST 날짜 경계로 가른다** — 나이(N시간)가 아니다. 재질의는 새벽 01:3x에
도는데 어제 05:00 PR은 그 시점에 20시간대라 "24시간 경과" 규칙이면 정작 물어야 할 PR이
하루 밀린다. 날짜 경계는 오늘 만들어진 PR을 같은 날 어느 시각에 돌려도(수동 실행 포함)
건드리지 않는다.

**재질의는 텔레그램 큐를 읽지 않는다.** `--reask`는 `getUpdates`를 호출하지 않고 오프셋도
쓰지 않으며, 워크플로도 `TELEGRAM_OFFSET`을 넘기지 않는다. 읽으면 이 잡이 다음 회차가
처리해야 할 판정을 먼저 소비하는데, 이 경로에는 PR 병합 로직이 없어 판정이 그대로 증발한다.

**`candidates` 잡은 `needs: inbox` + `if: always()`다.** 순서만 강제하고 성공은 요구하지
않는다. 인박스가 실패했다고 수집까지 막으면 그날 `/daily-post`가 통째로 `no_snapshot`이
된다. `if: always()`를 떼지 않는다.

**`weekly-collect.yml`의 두 잡은 병렬이고 그대로 둔다.** 스텝을 한 잡으로 이어 붙이면
GA4 조회 실패가 링크 점검까지 죽여 감사 ①이 근거 없이 '측정 안 함'으로 저하된다.

**사이드카 push는 재시도·rebase를 거친다**(`scripts/sidecar_push.sh`). 일요일에는 세
잡이 10분 안에 같은 저장소로 밀기 때문에 단발 `git push`는 non-fast-forward로 튕긴다.

**GitHub 내장 `schedule:`을 다시 넣지 않는다.** 2026-08-01까지의 실측에서 예정 시각보다
3시간 28분~3시간 58분 늦게 발화해 3시간대 여유를 통째로 잡아먹었고, 그 결과 스냅샷이
루틴보다 **뒤에** 도착해 `/daily-post`가 `no_snapshot`으로 중단됐다. 두 스케줄러가 함께
살아 있으면 같은 워크플로가 하루 두 번 돌아 사이드카에 중복 커밋이 쌓인다.

**스냅샷 파일명과 `generated_at`은 언제나 KST 기준이다.** 워크플로가 UTC 16시대에 도는데
UTC 날짜를 쓰면 매일 "스냅샷 부재"로 조용히 중단된다.

**`gh`를 루틴에서 호출하지 않는다.** 샌드박스에 설치되어 있지 않고, 토큰을 넣을 안전한
경로도 없다. PR 생성은 `open-auto-pr.yml`이 커밋 메시지 본문을 PR 본문으로 써서 만든다 —
그래서 무인 커밋은 반드시 단일 커밋 1건(`git commit --cleanup=verbatim -m "<제목>" -m "<PR 본문>"`) 형태다.

**`open-auto-pr.yml`은 `chore: publish`·`chore: auto-resolve` 커밋을 건너뛴다.**
인박스가 승인을 집행할 때 `draft` 플립을 **파일마다 따로** Contents API로 밀기
때문에 푸시 1건 = 이 워크플로 1회인데, 러너가 잡히는 ~40초 사이에 인박스는 이미
PR을 병합하고 브랜치를 지운다. 그러면 `gh pr list --head ... --state open`이 0을
돌려줘(PR이 방금 닫혔으므로) 가드를 통과하고, `gh pr create`가
`No commits between main and auto/post-...`로 실패해 **병합이 성공한 뒤에**
"승인 루프가 끊긴다"는 거짓 경보가 나간다. 2026-08-11·08-13 회차에서 5건 발생했다.
커밋 메시지 가드에 더해 브랜치 존재·`ahead_by` 확인도 넣었으니, 이 워크플로의 실패
경보는 이제 진짜 실패를 뜻한다 — 가드를 떼면 그 성질이 사라진다.

Hugo는 샌드박스에 설치 가능하다. `scripts/bootstrap_sandbox.sh`가 0.164.0을 받는다
(로컬에서는 no-op). 실패하면 ④E1·④E4·③I1·⑤D4를 **`측정 불가`**로 낸다 — `통과`가 아니다.

**사이드카 보존 정책**: `candidates/`, `analytics/`, `linkstate/` 데이터의 보존 기한은 90일로 정하며 90일 경과 스냅샷은 주기적으로 정리한다.

## 로드맵

상세와 근거는 `MEMORY.md` §6. 여기서는 범위 판정에 쓰이는 두 줄만 고정한다.

- **Agent3 (주간 감사, `/weekly-audit`)는 구현 완료다.** 범위는 여섯 축 — ① 링크 무결성 ② 성과 분석(GA4/GSC, 데이터 충분성 게이트 뒤) ③ 색인 건전성 ④ 시스템 스캔 ⑤ 방향성 점검 ⑥ 수치 무결성. **디자인·Lighthouse·성능 측정은 의도적으로 범위 밖이다** — 헤드리스 브라우저가 필요하다. 그것이 포함된다고 적은 문서는 낡은 초안을 기술하고 있다. **이 줄이 범위에 관한 최종 권위이며**, 감사 ④가 이 줄과 실제 범위의 불일치를 소견으로 낸다. 에이전트는 이 파일을 직접 수정하지 못한다.
- **Telegram 승인 루프 기반 자동화 스케줄이 구성되어 있다.** GitHub Actions(`.github/workflows/notify.yml`, `weekly-collect.yml`, `daily-collect.yml`) 및 Telegram Bot을 통해 PR 통지, 주간 스냅샷 수집, 무인 승인/반려 판정을 처리한다.
