# CLAUDE.md

이 저장소에서 작업하는 에이전트가 **매 실행에 알아야 하는 것**만 담는다. 배경·근거·이력은 `MEMORY.md`, 감사 에이전트의 판정 근거는 `.claude/audit/SEED-weekly-audit.md`에 있다.

## 무엇인가

한국 경제뉴스를 비전문가에게 설명하는 Hugo 정적 사이트(테마: PaperMod, `themes/PaperMod` 서브모듈), GitHub Pages 배포. 산출물은 (a) Hugo 콘텐츠·설정과 (b) 그것을 만드는 `/daily-post`·`/weekly-audit` 슬래시 명령이다.

**렌더 경로에 우리가 쓴 코드는 없다.** Python(`.claude/audit/lib/`, `.claude/loop/`, `scripts/`)은 전부 오프라인 도구이며 `hugo` 빌드나 CI에서 돌지 않는다.

## 명령

```bash
hugo server              # 로컬 개발 서버
hugo --gc --minify       # 프로덕션 빌드 (CI가 돌리는 것) → ./public
```

CI(`.github/workflows/hugo.yml`)는 `main` push 시 Hugo **0.164.0**으로 빌드해 `actions/deploy-pages`로 배포한다. `gh-pages` 브랜치는 없다. 로컬 Hugo를 그 버전에 맞춘다.

**모든 Python 호출은 `.venv/bin/python`이다.** 시스템 인터프리터에는 Google API 패키지가 없어 `python`·`python3`로는 import가 실패한다. **`requirements.txt`는 없다** — `.venv`는 손으로 구성됐다. 재현이 필요하면 설치 버전을 `MEMORY.md` §3에서 읽는다.

## 검증

사이트 자체에는 린터도 테스트도 없다 — 프롬프트 파일 + 마크다운 + Hugo 설정이다. Python은 예외로 테스트가 있다.

```bash
.venv/bin/python .claude/loop/test_extract_features.py
```

```bash
for f in .claude/audit/lib/test_*.py; do .venv/bin/python "$f"; done
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
| §1 랭킹 | `rank.md` | 한경 3피드 → 신선 후보 10건 미만이면 연합/경향/동아/한겨레 폴백. 5기준 0–15점, 8점 바닥. 무인은 1위 자동 선택, 바닥 미달이면 조용히 중단. 수동은 3건 제시. |
| §2 원문 | 시퀀서 | WebFetch. 실패 시 지어내지 않고 중단 — 무인은 후보를 폐기하고 2위로 넘어가지 않는다. |
| §3 연관 기사 | 시퀀서 | WebSearch. 실패·0건이면 필드를 통째로 생략한다. URL을 지어내지 않는다. |
| §4 분석 | `analysis.md` | 3렌즈 분류 + 선행/동행 태깅, `macro-reference.md` 1회 조회, 지표 1–2개의 🟢/🟡/🔴 임계값. **디스크에 저장하지 않는다.** |
| §5 작성 | `draft.md` | 포스트 + 사전 항목 + 위키링크. 산문·톤 규칙은 `writing-styles.md`에 위임. 끝에 **발행 전 결정론 검사**(§5-1~5-3). |
| §6 게시 | 시퀀서 | 발행 게이트 — 아래. |

**발행 게이트.** 무인은 항상 `draft: true`를 쓰고 `auto/post-YYYY-MM-DD` 브랜치 + PR로만 올린다. `main`에 절대 직접 푸시하지 않는다. 수동은 구체적 승인 질문에 **명확한 긍정**을 받은 뒤에만 `draft: false`로 바꿔 `main`에 푸시한다. "좋아요"·"괜찮네요"는 승인이 아니다.

**발행 전 검사 게이트(§J).** `draft.md` §5가 `.claude/audit/lib/`의 N1·N2·N4·N5와 `_terms.yaml` 정합을 돌린다. 결과는 `통과` · `남은 위반 N건` · `검사 불가` 셋 중 하나이며 §6이 그것으로 분기한다. **`검사 불가`를 `통과`와 같게 취급하지 않는다.** 검사 코드는 감사 ⑥과 **같은 모듈**이다 — 재구현하면 쓰기시점과 감사시점의 판정이 갈린다.

**무인 불변조건** (각 스테이지 파일에서 각각 강제한다): `auto/post-YYYY-MM-DD`에만 푸시 · 항상 `draft: true` · 대화형 도구 호출 금지 · 1위가 8/15 미달이면 산출물 없이 중단.

## `/weekly-audit`

인자 없음 = 무인(`auto/audit-YYYY-MM-DD` 브랜치 + PR), `manual` = 대화형. 시퀀서 `.claude/commands/weekly-audit.md`가 `.claude/audit/` 아래 6개 스테이지를 `Read`한다: ① 링크 + 백필 → ② 성과 → ③ 색인 → ④ 시스템 스캔 → ⑥ 수치 → ⑤ 방향.

**실행 중 알아야 할 것:**

- **git 쓰기는 시퀀서 §10에서만** 한다. 스테이지는 읽기·분석·문자열 반환까지다.
- **②가 침묵하는 것이 정상이다.** 데이터 충분성 게이트(발행 20건·28일·신호 충족 주제군 3개) 미달이면 `topic-report.md`를 생성·수정·삭제하지 **않는다.** 2026-07-30 기준 세 조건 전부 미달이다.
- **`topic-report.md` 부재는 정상이다.** `rank.md`가 조용히 건너뛴다.
- **산출물은 다섯 개뿐이다**: `audit-YYYY-MM-DD.md` · `link-state.json` · `topic-history.json` · `direction-log.json` · `topic-report.md`(게이트 통과 시에만). 여섯 번째 파일을 만들지 않는다.
- **쓰기 금지**: `.claude/daily-post/` 전체 · `.claude/loop/` 전체 · `hugo.toml` · `CLAUDE.md` · `MEMORY.md` · `layouts/` · `content/` 본문 산문. `content/`에서 허용되는 유일한 변경은 확정 사망 링크 수정과 내부링크 백필이다.
- **리포트가 공개 저장소에 커밋된다.** 자격증명·서비스 계정 이메일·토큰을 리포트에 쓰지 않는다.
- **`writing-styles.md`는 `.claude/loop/`가 소유한다.** 감사는 읽기만 한다. 특히 `genre-diagnostic.md`가 반증 테스트용으로 load-bearing으로 지정한 **"40~60자" 문자열 두 곳을 건드리지 않는다.**

## 조용히 깨지는 계약 셋

양쪽을 동시에 고치지 않으면 런타임에 오류 없이 드롭된다.

1. **분석 4필드** — `analysis.md`가 방출하는 `건드리는 렌즈` / `선행 vs 동행` / `확인된 수치` / `자산군별 함의` 각각에 `draft.md` §2의 소비 불릿이 하나씩 대응해야 한다. 대응 없는 필드는 조용히 사라진다. 한 번 일어났고 사람 리뷰가 잡았다.
2. **감사 점수 계약** — `.claude/audit/README.md`가 `topic-report.md` 형식을 고정하고 `rank.md`가 그것을 읽는다. 어느 쪽도 단독으로 재설계하지 않는다.
3. **`_terms.yaml` 정합** — `draft.md` §3이 사전 파일 생성과 `_terms.yaml` append를 **따로** 하므로 한쪽만 하면 그 자리에서 깨진다. `/daily-post` §5의 계약 검사가 이것 하나를 본다.

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
- `.claude/loop/reference-corpus/`는 제3자 저작물이다. 로컬 전용, gitignored, **발행·재배포 금지.**
- **`/docs/`는 통째로 gitignored다.** `docs/superpowers/` 아래 스펙·계획은 커밋되지 않고 git 이력에도 없다 — `git add docs/...`는 무효다. 그 안에만 있는 운영 지식은 파일을 지우면 유실되므로, 남길 것은 `CLAUDE.md`(매 실행 필요)나 `MEMORY.md`(근거·이력)로 옮긴다.
- `ga4-credentials.json`(저장소 루트, gitignored)은 **Google 서비스 계정 키 원본**이다 — 래퍼 JSON이 아니다. `scripts/fetch_gsc.py:8`이 이 경로를 모듈 상수로 하드코딩하고 `fetch_ga4.py`는 `main()`에서 `GOOGLE_APPLICATION_CREDENTIALS`를 먼저 본다.

## 로드맵

상세와 근거는 `MEMORY.md` §6. 여기서는 범위 판정에 쓰이는 두 줄만 고정한다.

- **Agent3 (주간 감사, `/weekly-audit`)는 구현 완료다.** 범위는 여섯 축 — ① 링크 무결성 ② 성과 분석(GA4/GSC, 데이터 충분성 게이트 뒤) ③ 색인 건전성 ④ 시스템 스캔 ⑤ 방향성 점검 ⑥ 수치 무결성. **디자인·Lighthouse·성능 측정은 의도적으로 범위 밖이다** — 헤드리스 브라우저가 필요하다. 그것이 포함된다고 적은 문서는 낡은 초안을 기술하고 있다. **이 줄이 범위에 관한 최종 권위이며**, SEED AC #35는 이 줄과 실제 범위가 어긋나면 소견을 내게 한다. 에이전트는 이 파일을 직접 수정하지 못한다(AC #34·#38).
- **스케줄 실행은 아직 없다.** `/daily-post`·`/weekly-audit`의 무인 경로는 구현·검증됐지만 아무것도 그것을 호출하지 않는다. 스펙: `docs/superpowers/specs/2026-07-30-automation-telegram-loop.md`(Claude routine + GitHub Actions + Telegram 승인 루프).
