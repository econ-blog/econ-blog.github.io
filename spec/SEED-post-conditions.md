# Seed: 좋은 포스트의 조건 (AEO/SEO 구조 지표 → 작성 게이트)
**Version:** 1.0

## Changelog
- 1.0: Initial spec (2026-08-01)

## Intent

주간 감사가 발행된 글에서 **AEO/SEO 구조 지표**를 측정해 "좋은 포스트의 조건"을 데이터 파일 하나(`.claude/audit/post-conditions.md`)로 방출하고, `/daily-post`의 `draft.md`가 그것을 읽어 발행 전 검사에 반영한다. `topic-report.md` → `rank.md`가 **무엇을 쓸지**를 정하는 경로라면, 이것은 **어떻게 쓸지**를 정하는 경로다.

**트래픽을 근거로 삼지 않는다 — 지금은 근거가 없기 때문이다.** 2026-08-01 실측: GSC 노출 28일 0행, 색인 표본 5건 전부 `URL is unknown to Google`, GA4 세션 5건 전부 `(direct)`이고 `topPages`에 포스트 경로가 0건. 이 상태에서 트래픽 기반 조건 도출을 만들면 감사 ②와 똑같이 게이트 뒤에서 침묵하는 코드가 하나 더 생긴다. 대신 **글 자체에서 읽히는 구조 지표**를 쓴다. 트래픽이 쌓이면 그것으로 이 조건들을 **검증·반증**하는 것이 v2의 일이며, 그 자리를 지금 비워 둔다.

## Ontology

- **구조 지표 (structural indicator)**: 발행된 마크다운과 렌더 산출물에서 **결정론적으로** 읽히는 값. 트래픽·LLM 판단을 입력으로 받지 않는다. 같은 입력에 같은 출력. → AC 1·2·3
- **조건 (condition)**: 구조 지표 하나에 붙은 임계값과 판정. `충족` · `미충족` · `측정 불가` 셋 중 하나이며, **`측정 불가`를 `충족`과 같게 취급하지 않는다.** → AC 4·11
- **`post-conditions.md`**: 감사가 쓰고 `draft.md`가 읽는 **유일한** 인터페이스 파일. 형식이 계약이며 양쪽을 동시에 고쳐야 한다. 파일 부재는 정상 상태이고 `draft.md`가 조용히 건너뛴다. → AC 5·6·12
- **하드 조건 (hard condition)**: 사람 판단 없이 참·거짓이 갈리는 조건. 발행 전 게이트가 강제한다. → AC 7
- **참고 조건 (advisory condition)**: 판단이 필요해 자동 판정할 수 없는 것. 게이트가 아니라 작성 시 읽는 지침으로만 들어간다. → AC 8
- **질문 표면 (question surface)**: 검색·답변엔진 쿼리에 매칭될 수 있는 의문형 문자열. 제목과 H2에서 온다. 코퍼스 전체에서 **서로 다른** 표면의 개수가 롱테일 매칭 폭이다. → AC 2
- **답변 블록 (answer block)**: 질문형 H2 바로 뒤의 첫 문단. 답변엔진이 추출 단위로 삼는 덩어리. → AC 3·9

## Acceptance criteria

### 측정 (감사 쪽)

1. `.claude/audit/lib/aeo.py`가 `content/posts/*.md`(초안 제외)를 읽어 포스트마다 아래를 JSON으로 낸다. **표준 라이브러리 + 정규식만** 쓴다.
   - `title_len` — 제목 글자 수
   - `title_is_question` — 제목이 의문형인가 (`?`로 끝나거나 `~까`·`~나`·`~는가`로 끝남)
   - `description_len` — front matter `description` 글자 수 (없으면 `null`)
   - `h2_list` — H2 문자열 목록 (순서 보존)
   - `h2_question_count` — 그중 의문형 개수
   - `lead_len` — 첫 H2 이전 본문의 글자 수 (front matter·blockquote 제외)
   - `has_lead_summary` — 첫 H2 이전에 blockquote가 있는가
   - `answer_block_lens` — 각 질문형 H2 바로 뒤 첫 문단의 글자 수 목록
   - `table_count` · `list_count` — 표·리스트 개수
   - `primary_source_links` — 1차 출처 호스트 링크 수 (`numerics.py`의 기존 상수 재사용)

2. 같은 스크립트가 **코퍼스 전역 지표**를 낸다:
   - `distinct_h2_surfaces` — 전체 포스트에서 서로 다른 H2 문자열 수
   - `h2_reuse_ratio` — `1 - (distinct_h2_surfaces / 전체 H2 등장 수)`. 1에 가까울수록 모든 글이 같은 소제목을 쓴다는 뜻
   - `distinct_question_surfaces` — 제목·H2에서 나온 서로 다른 의문형 표면 수

3. 렌더 산출물 지표를 낸다. `public/`이 없으면 이 조각을 **`측정 불가`**로 내고 `충족`으로 처리하지 않는다:
   - `jsonld_types` — 포스트 페이지가 방출하는 `@type` 목록
   - `jsonld_author_present` — `BlogPosting`에 `author` 키가 있는가
   - `faqpage_present` — `FAQPage` 블록이 있는가

4. 각 지표에 임계값을 적용해 `충족`·`미충족`·`측정 불가`를 판정한다. **초기 임계값은 경험적으로 유도되지 않았다** — 저장소의 8/15·20건·28일과 같은 성격이며 그 사실을 출력에 명시한다.

5. 감사 시퀀서가 측정 결과를 `.claude/audit/post-conditions.md`로 쓴다. **이 파일이 AC #36 산출물 다섯 개에 더해지는 여섯 번째다** — `AGENTS.md`의 산출물 목록을 함께 갱신한다.

6. `post-conditions.md` 형식은 아래로 고정한다. `draft.md`가 이것을 파싱한다.

   ```markdown
   생성일: YYYY-MM-DD
   근거: 구조 지표 (트래픽 미반영 — 사유)

   ## 하드 조건
   - <조건 이름> | <임계값> | 현재 충족률 N/M

   ## 참고 조건
   - <조건 설명>

   ## 코퍼스 관측치
   - <지표 이름>: <값>
   ```

### 적용 (작성 쪽)

7. `draft.md` §5에 **AEO 검사** 절이 추가되고, 하드 조건만 게이트로 강제한다. 결과는 기존 §J와 같은 어휘 — `통과` · `남은 위반 N건` · `검사 불가` — 로 §6에 넘어간다. **`검사 불가`를 `통과`와 같게 취급하지 않는다.**

8. 참고 조건은 `writing-styles.md`가 아니라 `draft.md` §1의 작성 지침에 인용으로 들어간다. `writing-styles.md`는 이 스펙이 수정하지 않는다.

9. 초기 하드 조건은 넷이다(전부 객관 측정 가능):
   - `description`이 50~160자
   - 질문형 H2 최소 1개
   - 각 답변 블록이 80자 이상 (답변엔진이 추출할 만큼의 분량)
   - 첫 H2 이전에 리드 요약(blockquote) 존재

10. 초기 참고 조건은 둘이다(자동 판정 불가):
    - H2 중 최소 1개는 그 글에 고유한 질문일 것 — 12개 포스트가 동일 H2 4개를 쓰고 있어 질문 표면이 사실상 4개다
    - 제목에 숫자 또는 고유명사를 포함할 것

### 구조화 데이터

11. `layouts/partials/`에 JSON-LD를 보강하는 파트셜을 추가한다. PaperMod 테마 파일(`themes/PaperMod/`)은 **수정하지 않는다** — 서브모듈이다.
    - `BlogPosting`에 `author` 키를 넣는다 (`hugo.toml`에 `author` 설정 추가가 선행)
    - 질문형 H2와 그 답변 블록으로 `FAQPage`를 방출한다

12. 감사 ④의 계약 검사(`contracts.py`)에 **`post-conditions.md` 형식 ↔ `draft.md` 소비 로직** 정합 검사를 추가한다. 한쪽만 고치면 계약 위반으로 잡힌다.

### 검증

13. `.venv/bin/python .claude/audit/lib/test_aeo.py` — 전부 통과.
14. `for f in .claude/audit/lib/test_*.py; do .venv/bin/python "$f"; done` — 전부 통과.
15. `.venv/bin/python .claude/audit/lib/contracts.py` — `[]`.
16. `hugo --gc --minify` — 성공, `Non-page files`가 **1** 유지.
17. 현재 발행된 12개 포스트 전부에 대해 측정이 돌아가고, 하드 조건 충족률이 리포트에 숫자로 나온다.

## Constraints

- **배치**: 측정은 주간 감사 안에 붙인다(새 축이 아니라 ④ 시스템 스캔의 하위 절). 갱신은 `post-conditions.md` 파일 경유로만 한다. **감사는 `.claude/daily-post/` 아래 어떤 파일도 쓰지 않는다** — `AGENTS.md`의 쓰기 금지 계약을 깨지 않는다.
- 측정 헬퍼는 **표준 라이브러리 + 정규식만**. AST 파서·형태소 분석기·외부 의존성 금지.
- 모든 Python 호출은 `.venv/bin/python`. 테스트는 스탠드얼론 `unittest`이며 파일을 직접 실행한다(pytest 없음).
- 감사는 읽기 전용 원칙을 유지한다 — `content/`의 산문을 이 스펙 때문에 고치지 않는다. 미충족 포스트는 **소견**으로만 낸다.
- `themes/PaperMod/`는 서브모듈이라 수정하지 않는다.
- `writing-styles.md`의 "40~60자" 문자열은 건드리지 않는다.
- 임계값은 전부 **초기값**이며 경험적으로 유도되지 않았다. 리포트에 그 사실을 매번 명시한다.

## Out of scope

- **트래픽 기반 조건 도출** — 데이터가 0이다. v2의 일이며 감사 ② 게이트(20건·28일·신호군 3개)가 열린 뒤에 착수한다. 이 스펙은 그 자리만 비워 둔다.
- **기존 12개 포스트 소급 수정** — 미충족은 소견으로만 낸다. 발행된 산문을 자동으로 고치지 않는다.
- **H2 슬롯 구조 자체의 재설계** — `D6 슬롯 충족`이 현재 100%이고 감사가 그것을 측정한다. 슬롯을 바꾸면 D6 계약과 `draft.md` §1이 동시에 깨진다. 별도 작업이다.
- **네이버·다음 최적화** — 감사 ③이 Google만 보는 것과 같은 경계.
- **Lighthouse·Core Web Vitals** — 헤드리스 브라우저가 필요하고 Agent3 범위 밖으로 명시돼 있다.
- **`writing-styles.md` 수정** — 이 스펙은 읽기만 한다.
