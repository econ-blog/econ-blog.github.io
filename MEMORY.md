# MEMORY.md

이 저장소가 **왜** 지금의 모습인지 기록한다. `CLAUDE.md`는 운영 에이전트가 매 실행에 알아야 하는 것만 담고, 배경·근거·이력은 여기에 있다. 코드나 git 로그로 알 수 있는 것은 적지 않는다.

이 파일은 참조 문서다 — 에이전트가 실행 중에 수정하지 않는다.

---

## 1. 시스템 구성

### 지금 존재하는 것

| 층 | 실체 | 상태 |
|---|---|---|
| 사이트 | Hugo + PaperMod(서브모듈), GitHub Pages | 라이브 |
| 배포 | `.github/workflows/hugo.yml` — `main` push 시 Hugo 0.164.0 빌드 → `actions/deploy-pages` | 동작 중 (`gh-pages` 브랜치 없음) |
| 작성 | `/daily-post` — 7단계 시퀀서 + 5개 스테이지 프롬프트 | 무인·수동 양 모드 구현·검증 |
| 감사 | `/weekly-audit` — 시퀀서 + 6개 스테이지 프롬프트 + `.claude/audit/lib/` 13개 모듈·13개 테스트 | 6축 전부 구현, 2026-07-28 1회 실행 검증 |
| 문체 루프 | `.claude/loop/` | 측정 리그까지만 (§5 참조) |
| 분석 | `scripts/fetch_ga4.py` · `fetch_gsc.py` | API 연동 완료 |
| 스케줄러 | **없음** | 스펙만: `docs/superpowers/specs/2026-07-30-automation-telegram-loop.md` |

렌더 경로에는 우리가 쓴 코드가 없다. Python은 전부 오프라인 도구이며 `hugo` 빌드나 CI에서 돌지 않는다.

### 렌더 경로 밖의 Python

- `.claude/audit/lib/*.py` — 감사 에이전트의 결정론적 판정 엔진. 13개 모듈, 각각 테스트 동반.
- `.claude/loop/*.py` — 문체 측정. `extract_features.py`가 특성값을 계산하는 **유일한** 주체.
- `scripts/fetch_*.py` — GA4·GSC 리더.

모두 `.venv/bin/python`으로 호출한다. 시스템 인터프리터에는 Google API 패키지가 없다. `requirements.txt`는 아직 없다 — 자동화 스펙 AC #16이 그것을 요구한다.

### 자격증명

- `ga4-credentials.json` (서비스 계정, gitignored) — **경로가 `scripts/fetch_*.py`에 하드코딩되어 있다.** 자동화 스펙 AC #1이 이 하드코딩을 전제조건으로 지목한다.
- GA4 property `546174128`, 측정 태그 `G-E2V0CFN172`.
- GSC 사이트 확인 태그 `Pq-uzUwYArRYxLu2YzvnVhdM43JSCa7wQuHup-UJdGk`.
- 로컬 push는 저장소 전용 SSH 키 `~/.ssh/id_ed25519_econblog`를 쓴다. 클라우드 런너에는 없다 — 자동화 스펙 AC #3이 PAT으로 푼다.

---

## 2. 주요 결정과 근거

### `/daily-post`의 스테이지 파일이 `.claude/commands/` 밖에 있는 이유

Claude Code는 `.claude/commands/` **하위 디렉터리까지** 모든 `.md`를 슬래시 명령으로 자동 등록한다. 스테이지를 거기 두면 `/rank`·`/analysis`·`/draft`·`/writing-styles`·`/macro-reference`가 조용히 생긴다. 네이티브 include 기능이 없으므로 핸드오프는 "이 경로를 Read하라"는 산문이다 — 그래서 양쪽의 경로 문자열이 정확해야 한다.

### 무인 모드가 `main`에 쓰지 않는 이유

무인 실행은 사람의 눈을 통과하지 않는다. `draft: true` + 브랜치 + PR 세 겹이 미검증 내용이 사이트에 도달하는 것을 막는다. 자동화 스펙이 이 계약을 완화하지 않는다 — 스케줄 실행이 곧 무인 모드다.

### 위키링크가 `[[...]]`가 아닌 이유

Hugo/Goldmark에 위키링크 shortcode가 없다. `[기준금리](/dictionary/base-rate/)` 같은 평범한 상대 링크를 쓴다. shortcode를 추가하지 않기로 한 것은 결정이며 누락이 아니다.

### `_terms.yaml`이 사전 디렉터리 스캔을 대체한 이유

`draft.md`와 `rank.md`가 둘 다 `content/dictionary/`를 스캔하면 "정책금리" vs "기준금리" 같은 동의어 불일치로 링크를 놓치거나 항목을 중복 생성한다. `_terms.yaml`이 slug → `{title, aliases}` 단일 진리원이다. Hugo는 `_`로 시작하는 `content/` 파일을 건너뛰므로 페이지가 되지 않고 "Non-page files 1"로 집계된다.

`aliases`는 실제 동의어이며 문법적 활용형이 아니다.

### 푸터 순서가 내부 → 외부 → 출처 → 면책인 이유

`layouts/partials/extend_post_content.html`. 내부 관련글이 먼저인 것은 의도다 — AdSense 이전 단계에서 체류시간이 유일하게 의미 있는 신호다. 외부 링크는 매 포스트에 나가므로 `rel="nofollow"`를 단다.

### `related_articles`가 오래된 순이고 같은 날 기사를 뺀 이유

그날의 통신 기사를 한 번 더 복사한 블록이 아니라 **사건 이전의 맥락**으로 읽히게 하려는 것이다. 살아남는 항목이 없으면 필드를 통째로 생략한다 — 빈 리스트를 남기지 않는다.

### 감사 에이전트를 생성/감독 2분할로 만들지 않은 이유

두 에이전트가 같은 입력(GA4·발행글)을 보면 새 정보가 유입되지 않는다. 감독자에게 남는 레버는 "그럴듯한가"인데, 그건 생성자가 이미 최적화한 축이다. 결과는 고무도장이거나 문체 트집이다 — 이 저장소의 v1.0 외부 리뷰가 자기 지적 18건을 18건 모두 수용했던 것이 그 사례다.

결정적 반례: 2026-07-23에 유입된 외부 리서치 보고서. 표본 27개 URL 중 **17개(63%) 사망**, `youtube.com/watch?v=` 8건 전수 사망(3건은 ID 형식 자체가 부적합). 읽어서는 안 잡히고 `curl`로만 잡힌다. **에이전트를 분할하는 정당한 기준은 역할이 아니라 증거 채널이다.** 그래서 감사의 감독자는 사전등록 원장(`direction-log.json`)과 링크 검사기다.

### 성과 분석(②)의 기본 상태가 "아무것도 쓰지 않음"인 이유

`topic-report.md`의 조정치는 `rank.md`의 15점 총점에 그대로 더해져 8점 임계값을 바꾼다. 표본이 작을 때 뽑은 조정치는 노이즈이고, 노이즈를 채점기에 주입하면 **자기강화형 래칫**이 된다 — 감점된 주제는 다시 선택되지 않고, 선택되지 않으니 판정을 뒤집을 데이터가 영원히 쌓이지 않는다. 그래서 게이트(발행 20건 · 28일 · 신호 충족 주제군 3개)를 통과할 때만 쓴다. 그 셋은 **경험적으로 유도되지 않은 초기값**이며, 8/15와 같은 성격이다.

### 방향성 점검(⑤)이 `rank.md`에 도달하지 못하게 한 이유

②의 게이트를 한 세션 들여 설계해 놓고 ⑤가 옆문으로 근거 없는 조정을 흘려보내면 게이트 전체가 무의미해진다. ⑤는 `topic-report.md`를 쓰지도 읽지도 않는다.

### D1의 단위가 문서 수가 아니라 본문 글자 수인 이유

포스트 본문 중앙값 2,066자 vs 사전 항목 331자 = **6.2배**. 문서 수로 세면 사전 7건이 13건 중 54%가 되어 상록층이 3.5배 부풀고, `content/posts/`만 분모에 넣으면 0%로 축소된다. 질량 기준 실제 값이 15.4%였다. 대가는 패딩 보상이며, 그 패딩이 곧 `.claude/loop/`가 잡으려는 AI 아티팩트라는 것이 이 시스템의 가장 위험한 상호작용이다.

### N3(교차 불일치)이 파일 교차만 보는 이유

문면 그대로 구현해 2026-07-26 코퍼스에 돌린 결과 **진탐 0 / 오탐 3**이었다. 원인은 `_terms.yaml`의 지표 이름이 수량을 식별하지 못한다는 것 — `브렌트유` 하나가 종가·장중가·등락률을 덮고 `PER` 하나가 네 회사를 덮는다. 단위별 버킷 + 한 scope 내 열거 제외 + 파일 교차 요구 세 규칙을 더해 오탐 3 → 0이 됐고, 대가로 **한 글이 스스로 어긋나는 경우를 못 본다.**

### 쓰기시점 검사(§J)가 생긴 이유

여섯 축 전부 발행 *이후*를 본다. 감사는 이미 나간 글을 검사할 뿐 나가는 것을 막지 못한다. 2026-07-26 실측에서 N1(기준일 누락)이 **42건 / 수치 주장 74건 = 57%**였고 그중 41건이 포스트 산문이었다 — 구조가 강제되는 자리는 이미 전부 통과한다. 결함은 강제가 없는 곳에 몰려 있으므로 집행 지점을 `/daily-post` §5로 옮겼다.

**그 이동이 만드는 회피 경로**: 초안 주체에게 가장 싼 해소법은 기준일을 붙이는 게 아니라 수치를 지우는 것이다. 건수만 세면 개선과 회피가 같은 숫자로 보인다. 그래서 N1 건수에 **수치 주장 총량을 분모로 병기**하고 직전값과 방향을 대조한다. D1의 패딩 문제와 같은 구조이고 처방도 같다 — 반대로 움직이는 인접 지표를 항상 함께 본다.

### SEED에 유실된 조항이 있는 이유

`.claude/audit/SEED-weekly-audit.md`의 §H·§I·§J는 별도 세션에서 작성됐다가 파일에 기록되기 전에 유실됐다. §H는 스크래치패드에서 축자 복원, §I·§J는 **재구성**(원문이 무엇이었는지 알 수 없음)이며 각 절 머리에 그 사실이 명시돼 있다. **AC #68은 남은 증거가 주제어 "주기 머리말" 넷뿐이라 재구성하지 않았다** — 주제어에서 조항을 지어내는 것은 복원이 아니라 창작이다.

**§I 재구성이 감수한 위험**: 계획에서 역산했으므로 구현 결정이 스펙의 권위를 얻는다. 코드와 §I 문면이 어긋나면 **어느 쪽이 옳은지는 열린 질문이고, 자동으로 코드가 이기지 않는다.**

### 마크다운 AST 파서를 쓰지 않는 이유

`extract_features.py`부터 "stdlib + 정규식, 외부 의존성 없음"을 클라우드 재현성 근거로 못박아 두었다. 링크 추출만 예외를 두면 그 규약이 깨진다. 코드 스팬 선제거(정규식)로 대응한다.

### 연성 실패(403 등)가 자동 수정 근거가 아닌 이유

한경·연합·네이버는 자동 클라이언트에 403/429를 반환하는 것이 정상 동작이다. 이를 죽은 링크로 오판하면 멀쩡한 출처가 삭제된다. 4주 연속이면 사람에게 넘기고, 자동 삭제는 하지 않는다.

### 페르소나 프롬프팅을 쓰지 않는 이유

"SEO 전문가처럼" 류는 어투를 바꿀 뿐 근거 접근을 바꾸지 않는다. 이 시스템의 실패 모드는 이미 과신이며, 확신만 높이고 정확도는 그대로 두는 장치를 추가하지 않는다.

---

## 3. 이미 검증된 사실 (다시 조사하지 말 것)

- **PaperMod는 `BlogPosting`·`BreadcrumbList` JSON-LD를 이미 방출한다.** "구조화 데이터를 도입해야 한다"는 흔한 권고는 이 저장소에서 충족 상태다. 실제 공백은 `author` 하나이며, 그것도 템플릿이 아니라 `hugo.toml` 설정 누락이다.
- **`<meta name="author">` 태그는 렌더되지만 값이 비어 있다.** 존재 여부가 아니라 값을 봐야 한다.
- **`--gc`는 고아 산출물을 지우지 않는다.** `public/`을 그대로 두고 센 빌드 카운트는 신뢰할 수 없다 — 태그 정리로 사라진 `tags/파운드리/` 등이 남아 있었다. 그래서 감사 E1은 고정 기댓값과 비교하지 않고 실행 전후 동일성만 본다.
- **GSC는 연동됐는데 90일 조회 결과가 0행이었다.** "연동됨"과 "데이터 있음"은 별도 판정이다. 2026-07-26 실측에서 I1·I2·I3·I5 전부 통과 + I4 "제출됨"인데 **포스트는 한 건도 크롤되지 않았고**(`URL is unknown to Google`) 색인된 것은 홈 하나였다.
- **아직 읽히지 않은 sitemap의 API 응답에는 `lastDownloaded` 키가 아예 없다.** 부재는 실패가 아니다. 직접 접근하면 `KeyError`다.
- **`/daily-post`의 위키링크 규약은 실제로 작동한다.** 2026-07-23 실측 고아 사전 항목 0건, 포스트당 사전 링크 2.00.
- **`.claude/loop/` 진단 결과**: 코퍼스 IQR 밖 특성 중 패치 가능한 AI 아티팩트로 인정되는 것은 `sentence_len_cv` 하나뿐이었다.
- **`.venv`는 손으로 구성됐고 `requirements.txt`가 없다.** 2026-07-30 실측 설치 버전: `google-analytics-data 0.23.0` · `google-api-python-client 2.198.0` · `google-auth 2.56.2` · `requests 2.34.2`(전이 의존: `google-api-core 2.32.0` · `google-auth-httplib2 0.4.0` · `googleapis-common-protos 1.75.0`). 자동화 스펙 AC #16이 "로컬 값으로 핀"이라고 요구하는 그 값이다.
- **pytest는 없고 `tests/`·`scripts/__init__.py`도 없다.** 테스트 관행은 스탠드얼론 `unittest` 파일 직접 실행이다. `scripts/`는 패키지가 아니어서 `from scripts.x import y`가 불가능하다.
- **`/docs/`는 gitignored다.** 스펙·계획 파일은 추적되지 않는다. 지우면 git 이력에도 남지 않는다 — §7의 삭제 이력이 그것을 전제한다.
- **`GITHUB_TOKEN`이 만든 push·PR은 다른 워크플로를 트리거하지 않는다.** PR 생성뿐 아니라 **`main` 병합에도** 적용된다 — `GITHUB_TOKEN`으로 병합하면 `hugo.yml`이 깨어나지 않아 배포가 일어나지 않는다. 또 `GITHUB_TOKEN`에는 저장소 변수(`actions/variables`) 쓰기 권한이 없다(admin 스코프).

---

## 4. 감사 에이전트 참조점

전체 스펙은 `.claude/audit/SEED-weekly-audit.md`(v3.6, 71개 AC, Known limits 25건)에 있다. 여기서는 위치만 적는다.

- **출력 형식 계약**: `.claude/audit/README.md`가 `topic-report.md` 형식을 고정한다. `rank.md`가 그것을 읽는다. **양쪽을 동시에 고치지 않으면 조용히 깨진다.**
- **산출물은 다섯 개로 못박혀 있다**: `audit-YYYY-MM-DD.md` · `link-state.json` · `topic-history.json` · `direction-log.json` · `topic-report.md`(게이트 통과 시에만). 여섯 번째 파일을 만들지 않는다 — 자동화 스펙이 분석 스냅샷을 Actions 아티팩트로 둔 이유다.
- **원장은 PR 병합에만 누적된다**(Known limits #3·#17·#24). PR을 방치하면 2-strike 판정·감쇄·⑥ 회귀 판정이 전부 성립하지 않는다.
- **⑥이 ⑤의 원장을 읽는다**: 회귀 판정용 직전값 3개(`n1_count`·`claims_total`·`claims_per_post`)를 `direction-log.json`의 `portfolio_history`에 얹었다. `portfolio_history`의 11개 키가 두 축에서 왔다는 사실을 아는 사람만 그것을 옳게 읽는다.
- **리포트가 공개 저장소에 들어간다**. 트래픽 절대수치와 유입 경로가 공개된다. 원치 않으면 `audit-*.md`만 gitignore하고 원장 셋은 추적을 유지해야 한다.

### 2026-07-30 시점 구현 상태

Plan 1–6 전부 구현·커밋 완료(총 48 Task). `.claude/audit/lib/` 테스트 13개 파일 전부 통과. 남은 것:

- **AC #68** — 유실, 재구성하지 않음(위 §2 참조). 필요해지면 새 번호의 새 조항으로 도입한다.
- **AC #71** — ②③ 게이트 stub 과도기 조항. Plan 6 병합으로 소멸했고 2026-07-30에 SEED에서 삭제했다.
- **AC #25(문체 사후검증)** — `accepted-patches.md`가 없으므로 영구 침묵 중. Known limits #11이 그것을 정상이라고 명시한다.
- **수용 판정된 이연 소견 2건** — `indexation.REMOTE_HOST`의 repo 그룹이 점에서 잘려 커스텀 도메인 baseURL이면 I3 오탐(이 저장소에선 무해) / ②의 판정 근거가 두 표로 나뉘어 한 주제군의 경로를 보려면 대조가 필요(주제군 표는 게이트 전에도 재보정 데이터를 남기므로 의도된 설계).

---

## 5. 문체 루프 (`.claude/loop/`) — 설계 요약

설계 스펙 원문(`2026-07-20-loop-writing-style-design.md`, v3.0)은 2026-07-30에 삭제했다. 핵심만 남긴다.

**하는 일**: `writing-styles.md`의 "AI 흔적 자가검토" 체크리스트를 자동 확장한다. (1) 현행 스킬로 고정 평가주제에 초안을 쓰고 (2) 초안과 참조 코퍼스의 텍스트 특성 분포를 결정론적으로 추출하고 (3) 장르 차이로 설명되지 않는 차이가 노이즈 바닥을 넘으면 규칙을 제안·검증·append한다.

**설계의 뼈대**:
- **특성값을 LLM이 산출하는 것을 금지한다.** 모델이 "대략 0.3쯤"이라고 답한 수치는 측정이 아니라 조작값이고, 루프 전체를 무의미하게 만든다. `extract_features.py`가 유일한 계산 주체다.
- **`genre_invariant` 게이트** — 초안·코퍼스 차이가 "AI 흔적"인지 "`writing-styles.md`가 의무화한 장르 차이"인지 사람이 판정한다. 이 값을 틀리면 **루프가 자기 스타일 가이드를 공격한다.** 근거를 문장으로 못 쓰면 기본값은 `false`.
- **단방향 위반 판정** — 스타일 가이드가 *의도적으로* 코퍼스 밖으로 밀어낸 값을 위반으로 잡지 않기 위해 `violation_direction`(`high`/`low`/`both`)을 둔다.
- **체크리스트 예산 12개** — `writing-styles.md`는 매 `/daily-post` 실행마다 컨텍스트에 올라간다. 항목이 늘면 개별 항목에 배분되는 주의력이 줄어 **모든** 후속 포스트가 나빠진다. 상한 도달은 루프 종료 조건이다.
- **노이즈 바닥** — 패치 없이 같은 9슬롯(주제 3 × 재생성 3)을 생성했을 때의 거리 표준편차 `σ₀`. 단순 감소는 accept 사유가 아니고 `μ_p ≤ μ₀ − σ₀`여야 한다. LLM 출력 분산이 패치 효과보다 클 수 있기 때문이다.
- **전량 롤백** — n=9로는 어느 패치가 누적 재검증을 망쳤는지 특정할 수 없어 부분 롤백을 포기했다. 좋은 패치와 나쁜 패치가 섞이면 둘 다 버려진다.
- **대리지표가 상위 목표와 연결된다는 보장이 없다.** 목표는 트래픽인데 루프는 특성 분포만 최적화한다. 이 연결이 약하면 루프는 정상 작동하면서 아무 효과를 내지 못한다 — 감사 AC #25가 그것을 확인할 유일한 경로다.

**현재 구현**: 측정·진단만. `collect_corpus.py`·`extract_features.py`(+골든 테스트)·`diagnose.py`·`discover.py`·`genre-diagnostic.md`가 있고, `loop-writing-style.md` 명령·`feature-spec.yaml`·`noise-floor.json`·`accepted-patches.md`는 **없다.**

**`genre-diagnostic.md`가 제안한 미실행 반증 테스트**: `writing-styles.md`에서 "40~60자" 범위를 제거하고 재측정. 그래서 그 문자열 두 곳이 load-bearing이며, 감사 에이전트도 건드리지 못한다.

**`reference-corpus/`는 제3자 저작물이다.** 로컬 전용, gitignored, 발행·재배포 금지.

---

## 6. 로드맵과 미해결 항목

### 자동화 (다음 작업)

`docs/superpowers/specs/2026-07-30-automation-telegram-loop.md`. 요지: Claude routine이 LLM 작업을, GitHub Actions가 자격증명이 필요한 I/O 전부를 맡고, 두 런타임은 저장소(브랜치·PR)로만 통신한다. 승인은 텔레그램 답장 닫힌 어휘로 판정한다.

### Cloud Routine Environment Verification Log

To satisfy Spec Known Limit #6, the following 4 environment items must be executed and recorded in the Cloud Sandbox:
1. `.venv` creation & dependency installation (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
2. Hugo `0.164.0` binary availability check (`hugo version`).
3. Submodule recursive initialization (`git submodule update --init --recursive`).
4. Remote push capability check using fine-grained GitHub PAT (`git push https://$PAT@github.com/...`).

**구현 첫 단계는 기능이 아니라 실측이다** — 클라우드 샌드박스에서 `.venv` 부트스트랩 / Hugo 설치 / submodule / PAT push 넷이 한 번도 실행된 적이 없고, 한경 RSS가 데이터센터 IP에서 열리는지도 미검증이다.

**계획 파일**: `docs/superpowers/plans/2026-07-30-automation-telegram-loop.md`(6 Task). 2026-07-30에 리뷰했고 **착수 전 수정이 필요한 상태다.** 계획 파일은 gitignored이고 결국 삭제되므로, 리뷰에서 나온 계획-독립 사실은 위 §3에, 아래 다섯 가지는 여기에 남긴다.

- **인박스 워크플로도 PAT을 쓴다.** `GITHUB_TOKEN`으로는 병합이 배포를 깨우지 못하고 `TELEGRAM_OFFSET` 변수도 못 쓴다(§3). 스펙 AC #3은 PR 생성만 다뤘고 병합·변수 쓰기는 그 논리의 확장이다.
- **`CREDENTIALS_JSON` 전문을 서비스 계정 키 파일로 넘길 수 없다.** 그 JSON은 `{telegram:…, ga4:{service_account:…}}` 래퍼이고 `service_account.Credentials.from_service_account_file()`은 `type`·`private_key`·`client_email`이 최상위인 파일을 요구한다. 워크플로가 `.ga4.service_account`만 별도 파일로 추출해야 한다.
- **승인 판정은 정규화 후 전체 문자열 완전일치다.** 부분·단어 단위 매칭을 넣으면 `"발행 안 함"`이 승인으로 읽힌다 — 스펙 Constraints가 금지한 실패 모드가 정확히 이 형태로 되돌아온다.
- **판정 토큰 매칭 실패는 `판정불가`다.** 토큰이 있는데 어느 PR과도 맞지 않을 때 "대기 PR 1건" 폴백으로 떨어뜨리면 사람이 지정하지 않은 글을 발행한다. AC #8의 3단계 폴백은 **토큰이 없을 때만** 적용된다.
- **미해결 스펙 모순**: AC #27(스냅샷 부재를 게이트 미달과 구분)·#28(Hugo 실패 시 `측정 불가`)은 감사 ②③④ 스테이지 파일 수정을 요구하는데, 같은 스펙 Constraints가 "스테이지 파일은 변경되지 않는다"고 못박았다. 어느 쪽을 접을지 정하지 않은 채 구현하면 조용히 드롭된다.

**루틴 등록 파라미터**(계획 Task 6이 지워질 문서에 두려던 것): 데일리 = 매일 KST 07:00 `/daily-post`, 인박스(KST 06:00)보다 뒤. 위클리 = 일요일 KST 08:00 `/weekly-audit`, 데일리 작성보다 뒤(감사 AC #4가 더티 트리에서 중단한다). 둘 다 부트스트랩으로 `python -m venv .venv && .venv/bin/pip install -r requirements.txt` + `git submodule update --init --recursive`, 자격증명은 fine-grained PAT(`contents: write` · `pull_requests: write`) 하나.

### Claude Routine Parameters

1. **Daily Post Routine**
   - **Schedule**: Every day KST 07:00
   - **Command**: `/daily-post`
   - **Bootstrap**: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && git submodule update --init --recursive`
   - **Credentials**: GitHub PAT (`contents: write`, `pull_requests: write`)

2. **Weekly Audit Routine**
   - **Schedule**: Every Sunday KST 08:00
   - **Command**: `/weekly-audit`
   - **Bootstrap**: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && gh run download --name analytics-snapshot --dir snapshot_output || true`
   - **Credentials**: GitHub PAT (`contents: write`, `pull_requests: write`)

### 미해결·미착수

- **8/15 임계값 재보정** — 초기값이다. 실제 실행 2주치 점수 분포로 다시 정해야 한다. ②의 게이트 임계값(20건·28일·3군·노출 300·60일 감쇄)도 같은 성격이다.
- **사실 교차검증** — §2가 한경 RSS 단일 출처다. 폴백 체인은 물량을 늘리지 검증을 늘리지 않는다. `/delegate`의 `agy`(Antigravity, Gemini 3.1 Pro High) 딥리서치로 교차검증하는 안이 열려 있다. **참고: `agy`는 연관 기사 링크 수집용으로는 별도 평가 후 기각됐다** — 딥리서치는 보고서 생성기이고 `WebSearch`가 URL을 더 싸게 준다.
- **네이버 SEO** — 미착수. 감사 ③은 Google Search Console만 본다. 한국 경제 블로그 유입에서 네이버 비중이 클 수 있으나 API가 없다.
- **Google AdSense · Kakao AdFit** — 미신청. 감사는 AdSense 섹션을 통째로 생략한다("데이터 없음" placeholder를 만들지 않는다).
- **경쟁 블로그 자동 분석** — 두 번째 증거 채널로서 유일하게 정당한 확장이지만, 크롤링 범위·저작권·`reference-corpus/` 로컬 전용 제약과 얽혀 별도 작업이다.

---

## 7. 문서 정리 이력

**2026-07-30** — `docs/superpowers/plans/*`(구현 계획 6개, 총 9,870행)와 `.superpowers/sdd/*`(SDD 진행 산출물 101개), `docs/superpowers/specs/2026-07-20-loop-writing-style-design.md`를 삭제했다. 전부 gitignored였으므로 git 이력에도 없다.

- **계획 파일** — Plan 1–6 전부 구현·커밋 완료되어 역할이 끝났다. 계획에 있던 정보 중 스펙에 없던 것(이연 소견 2건의 수용 판정, Task 완료 상태)은 위 §4에 옮겼다.
- **`.superpowers/sdd/`** — Task 브리프·리포트·리뷰 diff. 진행 상태 추적용이며 커밋 이력이 같은 정보를 담는다.
- **loop 설계 스펙** — 설계 근거를 위 §5로 옮겼다. AC 문면(13개 조항)은 옮기지 않았다 — 구현이 그 스펙의 3분의 1 수준에서 멈춰 있고, 재개 시점에 다시 쓰는 편이 낫다.

**남긴 것**: `.claude/audit/SEED-weekly-audit.md`(감사 에이전트가 실행 중 참조하는 판정 근거이고, 스테이지 파일과 lib 주석 약 200곳이 AC 번호로 그것을 가리킨다) · 자동화 스펙 하나.
