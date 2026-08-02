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
| §1 랭킹 | `rank.md` | `read_snapshot.py`로 사이드카 후보 스냅샷을 읽는다(RSS 직접 수집 없음). 5기준 0–15점, 8점 바닥. 무인은 1위 자동 선택, 바닥 미달이면 조용히 중단. 수동은 3건 제시. |
| §2 원문 | 시퀀서 | 스냅샷의 `body_text`. WebFetch를 쓰지 않는다 — 샌드박스가 뉴스 사이트에 도달할 수 없다. `body_ok` 미달이면 후보를 폐기하고 중단한다. |
| §3 연관 기사 | 시퀀서 | WebSearch. 실패·0건이면 필드를 통째로 생략한다. URL을 지어내지 않는다. |
| §4 분석 | `analysis.md` | 3렌즈 분류 + 선행/동행 태깅, `macro-reference.md` 1회 조회, 지표 1–2개의 🟢/🟡/🔴 임계값. **디스크에 저장하지 않는다.** |
| §5 작성 | `draft.md` | 포스트 + 사전 항목 + 위키링크. 산문·톤 규칙은 `writing-styles.md`에 위임. 끝에 **발행 전 결정론 검사**(§5-1~5-3). |
| §6 게시 | 시퀀서 | 발행 게이트 — 아래. |

**발행 게이트.** 무인은 항상 `draft: true`를 쓰고 `auto/post-YYYY-MM-DD` 브랜치 + PR로만 올린다. `main`에 절대 직접 푸시하지 않는다. 수동은 구체적 승인 질문에 **명확한 긍정**을 받은 뒤에만 `draft: false`로 바꿔 `main`에 푸시한다. "좋아요"·"괜찮네요"는 승인이 아니다.

**발행 전 검사 게이트(§J).** `draft.md` §5가 `.claude/audit/lib/`의 N1·N2·N4·N5와 `_terms.yaml` 정합을 돌린다. 결과는 `통과` · `남은 위반 N건` · `검사 불가` 셋 중 하나이며 §6이 그것으로 분기한다. **`검사 불가`를 `통과`와 같게 취급하지 않는다.** 검사 코드는 감사 ⑥과 **같은 모듈**이다 — 재구현하면 쓰기시점과 감사시점의 판정이 갈린다.

**무인 불변조건** (각 스테이지 파일에서 각각 강제한다): `auto/post-YYYY-MM-DD`에만 푸시 · 단일 커밋만 푸시 (`git commit --cleanup=verbatim` 1건) · 항상 `draft: true` · 대화형 도구 호출 금지 · 1위가 8/15 미달이면 산출물 없이 중단.

## `/weekly-audit`

인자 없음 = 무인, `manual` = 대화형. **무인은 리포트·원장을 `main`에 직접 푸시하고, `content/` 수정이 있을 때만 `auto/audit-YYYY-MM-DD` 브랜치 + PR로 분리한다**(2026-08-01 결정 — 감사 산출물은 관측치라 반려 대상이 아니다. `content/` 수정은 여전히 승인 대상). 시퀀서 `.claude/commands/weekly-audit.md`가 `.claude/audit/` 아래 6개 스테이지를 `Read`한다: ① 링크 + 백필 → ② 성과 → ③ 색인 → ④ 시스템 스캔 → ⑥ 수치 → ⑤ 방향.

**실행 중 알아야 할 것:**

- **git 쓰기는 시퀀서 §10에서만** 한다. 스테이지는 읽기·분석·문자열 반환까지다.
- **②가 침묵하는 것이 정상이다.** 데이터 충분성 게이트(발행 20건·28일·신호 충족 주제군 3개) 미달이면 `topic-report.md`를 생성·수정·삭제하지 **않는다.** 2026-07-30 기준 세 조건 전부 미달이다.
- **`topic-report.md` 부재는 정상이다.** `rank.md`가 조용히 건너뛴다.
- **산출물은 다섯 개뿐이다**: `report/audit-YYYY-MM-DD.md` · `.claude/audit/link-state.json` · `.claude/audit/topic-history.json` · `.claude/audit/direction-log.json` · `.claude/audit/topic-report.md`(게이트 통과 시에만). 여섯 번째 파일을 만들지 않는다.
- **리포트는 `report/`에, 원장은 `.claude/audit/`에 쓴다.** 리포트(`audit-*.md`)는 매 실행이 새로 만드는 읽을거리이고, 원장 JSON 셋은 다음 실행이 되읽는 상태다 — 그래서 자리가 다르다. `.claude/audit/`에 `audit-*.md`를 만들지 않는다.
- **쓰기 금지**: `.claude/daily-post/` 전체 · `hugo.toml` · `CLAUDE.md` · `MEMORY.md` · `layouts/` · `content/` 본문 산문. `content/`에서 허용되는 유일한 변경은 확정 사망 링크 수정과 내부링크 백필이다.
- **리포트가 공개 저장소에 커밋된다.** 자격증명·서비스 계정 이메일·토큰을 리포트에 쓰지 않는다.
- **`writing-styles.md`는 `.claude/daily-post/`가 소유한다.** 감사는 읽기만 하며 항목 **수만** 센다. (문체 루프가 이 파일의 "40~60자" 문자열을 반증 테스트용 load-bearing으로 지정했었으나, 2026-08-01에 루프를 삭제해 그 근거는 사라졌다. 문자열 자체는 여전히 살아 있는 작성 규칙이므로 감사가 고치지 않는다.)

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

- `content/posts/` — 포스트 1건 = 파일 1개. front matter: `title`·`date`·`tags`·`draft`·`source_url`(원문 URL 축자), 선택 `related_articles`(`{title, url, source}` 목록).
  - **파일명은 날짜 접두어 없는 슬러그다**(`tsmc-foundry-price-hike-10-percent.md`). 발행 순서가 필요하면 front matter `date`를 파싱한다 — 파일명·경로 정렬은 알파벳 정렬이다.
  - `related_articles`는 오래된 순, 같은 날 기사 제외, 배경 기사 우선. 살아남는 항목이 없으면 **키를 통째로 생략**한다 — 빈 리스트를 남기지 않는다.
  - 푸터 순서는 `layouts/partials/extend_post_content.html`: 내부 관련글 → 외부 `related_articles` → 출처 링크 → 면책. 내부가 먼저인 것은 체류시간이 pre-AdSense 유일 신호이기 때문이다. 외부 링크는 `rel="nofollow"`.
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

| 워크플로 | 스케줄 (KST) | 트리거 | 산출물 |
|---|---|---|---|
| `fetch-candidates.yml` | 매일 01:47 | cron-job.org | `candidates/YYYY-MM-DD.json` |
| `analytics.yml` | 일 01:20 | cron-job.org | `analytics/YYYY-MM-DD/*.json` |
| `fetch-linkstate.yml` | 일 01:37 | cron-job.org | `linkstate/YYYY-MM-DD.json` |
| `inbox.yml` | 매일 06:00 | cron-job.org | 승인 판정 처리 |
| `open-auto-pr.yml` | — | `push` on `auto/**` | PR (→ `notify.yml`) |

루틴은 `/daily-post` 매일 05:00 KST, `/weekly-audit` 일 05:00 KST. 수집은 루틴보다 최소
3시간 앞에 둔다.

**GitHub 내장 `schedule:`을 다시 넣지 않는다.** 2026-08-01까지의 실측에서 예정 시각보다
3시간 28분~3시간 58분 늦게 발화해 3시간대 여유를 통째로 잡아먹었고, 그 결과 스냅샷이
루틴보다 **뒤에** 도착해 `/daily-post`가 `no_snapshot`으로 중단됐다. 두 스케줄러가 함께
살아 있으면 같은 워크플로가 하루 두 번 돌아 사이드카에 중복 커밋이 쌓인다.

**스냅샷 파일명과 `generated_at`은 언제나 KST 기준이다.** 워크플로가 UTC 16시대에 도는데
UTC 날짜를 쓰면 매일 "스냅샷 부재"로 조용히 중단된다.

**`gh`를 루틴에서 호출하지 않는다.** 샌드박스에 설치되어 있지 않고, 토큰을 넣을 안전한
경로도 없다. PR 생성은 `open-auto-pr.yml`이 커밋 메시지 본문을 PR 본문으로 써서 만든다 —
그래서 무인 커밋은 반드시 단일 커밋 1건(`git commit --cleanup=verbatim -m "<제목>" -m "<PR 본문>"`) 형태다.

Hugo는 샌드박스에 설치 가능하다. `scripts/bootstrap_sandbox.sh`가 0.164.0을 받는다
(로컬에서는 no-op). 실패하면 ④E1·④E4·③I1·⑤D4를 **`측정 불가`**로 낸다 — `통과`가 아니다.

**사이드카 보존 정책**: `candidates/`, `analytics/`, `linkstate/` 데이터의 보존 기한은 90일로 정하며 90일 경과 스냅샷은 주기적으로 정리한다.

## 로드맵

상세와 근거는 `MEMORY.md` §6. 여기서는 범위 판정에 쓰이는 두 줄만 고정한다.

- **Agent3 (주간 감사, `/weekly-audit`)는 구현 완료다.** 범위는 여섯 축 — ① 링크 무결성 ② 성과 분석(GA4/GSC, 데이터 충분성 게이트 뒤) ③ 색인 건전성 ④ 시스템 스캔 ⑤ 방향성 점검 ⑥ 수치 무결성. **디자인·Lighthouse·성능 측정은 의도적으로 범위 밖이다** — 헤드리스 브라우저가 필요하다. 그것이 포함된다고 적은 문서는 낡은 초안을 기술하고 있다. **이 줄이 범위에 관한 최종 권위이며**, 감사 ④가 이 줄과 실제 범위의 불일치를 소견으로 낸다. 에이전트는 이 파일을 직접 수정하지 못한다.
- **Telegram 승인 루프 기반 자동화 스케줄이 구성되어 있다.** GitHub Actions(`.github/workflows/notify.yml`, `analytics.yml`, `inbox.yml`) 및 Telegram Bot을 통해 PR 통지, 주간 스냅샷 수집, 무인 승인/반려 판정을 처리한다.
