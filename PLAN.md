# 색인·AEO·자동화 개선 실행 계획

> **에이전트 작업자에게:** 이 계획은 태스크 단위로 실행한다. 각 단계는 체크박스(`- [ ]`)로
> 추적하며, 한 태스크를 끝낼 때마다 커밋하고 다음 태스크로 넘어간다. 태스크 하나가
> 독립적으로 테스트 가능한 산출물 하나를 낸다 — 여러 태스크를 묶어 한 번에 커밋하지 않는다.

작성 2026-08-09, 구체화 2026-08-10 (KST) · **임시 문서다.** 전부 구현되면 이 파일을 지운다.

> 이 파일이 저장소 규약(「남길 것이 생기면 `AGENTS.md`나 `MEMORY.md`에 직접 쓴다」)의
> 예외인 이유: 여러 세션에 걸쳐 소비될 작업 목록이고, 완료 시 통째로 삭제될 것이라
> 영구 문서 두 개에 섞으면 나중에 걷어내기 어렵다. 구현이 끝나면 **이 파일을 지우고,
> 남길 결론만** `MEMORY.md`로 옮긴다.

**목표(Goal):** 이미 좋은 글이 검색엔진·답변엔진에 발견되고 추출되게 만들고, 주간 감사가
내는 소견이 사람 손을 거치지 않고 커밋으로 바뀌는 경로를 낸다.

**구조(Architecture):** 글 본문은 건드리지 않는다. 손대는 곳은 네 겹이다 — (a) front matter와
Hugo 템플릿(구조화 데이터·FAQ 블록), (b) `/daily-post` 프롬프트 계약(제목 규율·태그 집중),
(c) `.claude/audit/lib/`의 결정론 검사 하나 추가, (d) 수집 스크립트와 감사 시퀀서의 배선.
새 런타임 코드는 없다 — 렌더 경로는 여전히 Hugo와 PaperMod뿐이다.

**기술 스택:** Hugo 0.164.0 (PaperMod 서브모듈) · Python 3 표준 라이브러리 + 정규식 ·
GitHub Actions · schema.org JSON-LD.

---

## 전역 제약 (Global Constraints)

이 절의 값은 **모든 태스크의 요구사항에 암묵적으로 포함된다.** 태스크마다 되풀이하지 않는다.

- **Hugo는 0.164.0이다.** 빌드는 `hugo --gc --minify`. CI(`.github/workflows/hugo.yml`)가
  같은 버전으로 `main` push를 배포한다.
- **`Non-page files`는 항상 1이어야 한다.** 그 1은 `content/dictionary/_terms.yaml`이 올바르게
  건너뛰어진 것이다. `Pages`는 발행마다 늘어나므로 고정값으로 보지 않는다.
- **모든 Python 호출은 `.venv/bin/python`이다.** 시스템 `python`·`python3`를 쓰지 않는다.
- **pytest는 없다.** 테스트는 `if __name__ == "__main__": unittest.main()` 형태의 스탠드얼론
  파일이고 직접 실행한다. `tests/` 디렉터리도 `scripts/__init__.py`도 만들지 않는다.
  `pytest tests/...`나 `from scripts.x import y`를 쓰는 코드는 그 자리에서 실패한다.
- **`.claude/audit/lib/`의 측정 헬퍼는 표준 라이브러리 + 정규식만 쓴다.** AST 파서·형태소
  분석기·외부 의존성을 도입하지 않는다. 클라우드 재현성 규약이다.
- **새 측정 헬퍼를 추가하면 테스트를 함께 낸다.** `.claude/audit/lib/test_<name>.py`.
- **`content/` 변경은 사용자 승인 대상이다.** 사소해 보이는 front matter 수정도 포함한다.
  승인 없이 커밋·푸시하지 않는다.
- **커밋 작성자는 `bjh7790` / `bjh7790@gmail.com`이다.**
- **`/docs/`와 `/.superpowers/`에 문서를 만들지 않는다.** 통째로 gitignored이며 규약상 금지다.
- **schema JSON-LD는 프로덕션 빌드에서만 나온다.** PaperMod의 `head.html`이
  `templates/schema_json.html`을 `hugo.IsProduction` 안에서만 부른다. 반면
  `extend_head.html`은 **모든 환경에서** 불린다 — 우리가 넣는 JSON-LD는 `hugo server`에서도
  보인다. 검증은 `public/`을 grep해서 한다.
- **`hugo.toml`·`CLAUDE.md`·`MEMORY.md`는 이 계획의 수정 대상이 아니다.** `AGENTS.md`는
  계약이 바뀌는 태스크(4·5·7·8)에서만, 그 태스크가 명시한 줄만 고친다.

---

## 실행 전 준비 (한 번만)

새 샌드박스는 서브모듈도 `.venv`도 Hugo도 없이 시작한다. 태스크에 들어가기 전에:

```bash
cd ~/econ-blog.github.io
git submodule update --init --depth 1 themes/PaperMod
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/bootstrap_sandbox.sh && export PATH="$HOME/.local/bin:$PATH"
hugo version    # v0.164.0 확인
```

기준선을 잡는다. **이 출력을 적어 둔다** — 이후 모든 빌드 검증이 여기에 대조된다.

```bash
rm -rf public && hugo --gc --minify
```

`Non-page files`가 1이 아니면 여기서 멈추고 원인을 찾는다. 태스크를 시작하지 않는다.

---

## 배경 — 지금 상태

전부 2026-08-08 감사가 실제로 측정한 값이다. 추정치가 아니다.

| 항목 | 값 |
|---|---|
| 발행 포스트 | 17 |
| 용어 사전 | 17 항목 (+ `_index.md`) |
| 사이트 연령 | 21일 |
| 28일 세션 | **7** |
| 28일 GSC 노출 | **0행** |
| 색인 (표본 5건) | **1건** — 홈만 |

유입 7세션이 전부 `(direct)`다. 외부 링크가 하나도 없다는 뜻이고, 그래서 구글이 다시 올
이유가 없다. 홈은 2026-07-19에 한 번 크롤된 뒤 그대로이고, 2026-08-01에 제출한 사이트맵은
8일째 읽히지 않았다. 나머지 4개 표본 URL은 `URL is unknown to Google` — 존재 자체를 모른다.

출처: `report/audit-2026-08-08.md`의 ② 성과 · ③ 색인 · ④ P1/P3 · ⑤ D4.

## 색인 요청은 사람이 해야 한다

**API가 없다.** 샌드박스 제약이 아니다.

Search Console API가 제공하는 것은 `searchanalytics`(조회) · `sitemaps`(목록·제출) ·
`urlInspection`(**조회 전용**) · `sites`뿐이다. GSC 화면의 "색인 생성 요청" 버튼에 대응하는
엔드포인트는 공개돼 있지 않다. 별도의 Indexing API가 있지만 공식 지원 범위가
`JobPosting`·`BroadcastEvent`로 한정돼 블로그 글에 쓰는 것은 문서화된 용도 밖이다.

즉 GitHub Actions(열린 인터넷)로 옮겨도 못 한다. 네이버 서치어드바이저의 "웹페이지 수집 요청"도
마찬가지로 UI 전용이다.

다만 `scripts/fetch_gsc.py`는 이미 `urlInspection().index().inspect()`를 호출한다.
**어느 URL이 아직 색인 안 됐는지 아는 것**은 자동화할 수 있다 — Task 6이 그것이다.
**색인해 달라고 요청하는 것**만 사람 몫이다.

---

## 0단계 — 발견 가능성 (사람만 가능, 코드 없음)

이 절은 태스크가 아니다. 에이전트가 대신할 수 없고, 병렬로 진행한다.

- [ ] GSC → URL 검사 → 발행 URL 34개(포스트 17 + 사전 17)에 색인 생성 요청. 한 번에 20분 정도.
      대상 목록은 추측하지 말고 Task 6이 만드는 명령으로 얻는다:
      `.venv/bin/python scripts/select_inspect_urls.py --all content`
- [ ] 네이버 서치어드바이저 웹페이지 수집 요청. `hugo.toml`에 인증 태그가 이미 있고
      (`params.analytics.naver.SiteVerificationTag`) `.claude/agents/naver-submit.md` 에이전트도
      있다 — **실제로 돌린 적 있는지 확인부터.** 한국어 경제 검색은 네이버가 주무대라
      여기가 가장 값싼 승부처다.
- [ ] 빙·다음 웹마스터도구 등록.
- [ ] 외부 링크를 최소 몇 개 만든다. 커뮤니티 프로필, 개인 SNS, 관련 글 댓글 등 — 구글이
      따라올 실이 하나는 있어야 한다.

**이게 안 되면 아래 전부가 측정 불가다.** 노출 0에서는 어떤 개선도 효과를 확인할 수 없다.

---

## 파일 구조

| 파일 | 상태 | 책임 | 태스크 |
|---|---|---|---|
| `content/posts/hormuz-red-sea-oil-supply-shock.md` | 수정 | front matter에 description 추가 | 1 |
| `content/dictionary/{base-rate,circuit-breaker,supply-shock}.md` | 수정 | description 추가 | 1 |
| `content/dictionary/{cofix,lng,per}.md` | 수정 | description 길이 보강 | 1 |
| `layouts/partials/extend_head.html` | 생성 | 사전 `DefinedTerm` + 포스트 `FAQPage` JSON-LD | 2·3 |
| `layouts/partials/faq.html` | 생성 | 화면에 보이는 FAQ 블록 (JSON-LD와 같은 원천) | 3 |
| `layouts/partials/extend_post_content.html` | 수정 | FAQ 블록을 푸터 맨 앞에 끼운다 | 3 |
| `assets/css/extended/faq.css` | 생성 | FAQ 블록 스타일 | 3 |
| `archetypes/posts.md` | 수정 | `faq` 필드 예시 | 3 |
| `.claude/audit/lib/headings.py` | 생성 | 제목 규율 결정론 검사 (T1~T4) | 4 |
| `.claude/audit/lib/test_headings.py` | 생성 | 위 모듈의 스탠드얼론 테스트 | 4 |
| `.claude/daily-post/draft.md` | 수정 | `faq` 규칙 · 제목 규칙 · §5에 제목 검사 배선 | 3·4 |
| `.claude/daily-post/writing-styles.md` | 수정 | H2 제목 규칙 · title 길이 규칙 | 4 |
| `.claude/daily-post/topics.yaml` | 수정 | 집중 주제 `focus: true` 표시 | 5 |
| `.claude/daily-post/rank.md` | 수정 | 집중 주제 가점 | 5 |
| `scripts/select_inspect_urls.py` | 수정 | 전수 URL 목록 모드 추가 | 6 |
| `scripts/fetch_gsc.py` | 수정 | `INSPECT_CAP` 상향 + `--inspect-cap` | 6 |
| `.github/workflows/weekly-collect.yml` | 수정 | 전수 모드 호출 | 6 |
| `scripts/test_automation.py` | 수정 | 전수 모드 테스트 + 요약 줄 테스트 | 6·7 |
| `.claude/audit/indexation.md` | 수정 | I6이 표본이 아니라 전수임을 반영 | 6 |
| `.claude/audit/system-scan.md` | 수정 | Q1을 소견이 아니라 수정안으로 낸다 | 7 |
| `.claude/commands/weekly-audit.md` | 수정 | §9-1 여덟째 줄 · §10-4 적용 범위 | 7 |
| `scripts/telegram_notify.py` | 수정 | 요약 키 하나 추가 | 7 |
| `scripts/housekeeping.py` | 생성 | 유지보수 오케스트레이터 (LLM 없음) | 7 |
| `scripts/test_housekeeping.py` | 생성 | 위 모듈의 스탠드얼론 테스트 | 7 |
| `.github/workflows/weekly-housekeeping.yml` | 생성 | 주간 유지보수 실행 (알림 없음) | 7 |
| `.claude/commands/weekly-audit.md` | 이름변경 | → `audit-improvement.md` (②·⑤·Q3, 수동 전용) | 7 |
| `AGENTS.md` | 수정 | 계약이 바뀐 줄만 (태스크 4·5·7·8) | 4·5·7·8 |

**책임 분리의 기준:** JSON-LD는 전부 `extend_head.html` 하나가 낸다(테마의
`schema_json.html`을 통째로 복사해 오버라이드하지 않는다 — 128줄짜리 테마 파일을
벤더링하면 PaperMod를 올릴 때마다 수동 병합이 생긴다). 화면에 보이는 것과 JSON-LD는
**같은 front matter 하나**를 읽어 서로 어긋날 수 없게 한다.

---

## Task 1: description 결함 7건 보강

2026-08-08 감사 소견 2~8번. 검색 결과와 AI 답변이 그대로 인용하는 문자열인데 4건은 없고
3건은 짧다. `content/` 수정이므로 **사용자 승인 게이트가 붙는다.**

**Files:**
- Modify: `content/posts/hormuz-red-sea-oil-supply-shock.md`
- Modify: `content/dictionary/base-rate.md`, `circuit-breaker.md`, `supply-shock.md` (누락)
- Modify: `content/dictionary/cofix.md`, `lng.md`, `per.md` (길이 미달)
- 판정: `.claude/audit/lib/quality.py` (수정하지 않는다 — 이 태스크의 테스트다)

**Interfaces:**
- Consumes: `quality.py`의 `DESC_MIN, DESC_MAX = 50, 160`, `front_matter_issues(path)`.
- Produces: 없음. 다른 태스크가 이 결과에 의존하지 않는다.

- [ ] **Step 1: 실패를 먼저 확인한다**

```bash
.venv/bin/python .claude/audit/lib/quality.py | python3 -m json.tool | grep -A 3 '"issues"' | head -40
```

기대: `Q1`에 7개 파일이 `description 누락` 또는 `description 길이 NN자`로 올라온다.
**7건이 아니면 멈춘다** — 그 사이 파일이 바뀐 것이므로 아래 문자열을 그대로 쓰면 안 된다.

- [ ] **Step 2: 포스트 1건에 description을 넣는다**

`content/posts/hormuz-red-sea-oil-supply-shock.md`의 `date:` 줄 **바로 아래**에 넣는다
(`draft.md` §1의 front matter 순서: title · date · description · tags · draft · source_url).

```yaml
description: "호르무즈와 홍해가 동시에 막히면 원유 수송로 두 곳이 한꺼번에 좁아집니다. 유가가 어디까지 오를 수 있는지, 그 값이 주유소와 장바구니 물가로 번지는 경로를 단계별로 풀었습니다."
```

- [ ] **Step 3: 사전 누락 3건에 description을 넣는다**

각 파일의 `date:` 줄 바로 아래.

`content/dictionary/base-rate.md`:
```yaml
description: "한국은행이 정하는 돈값의 기준으로, 예금·대출 금리가 여기서부터 줄줄이 정해집니다. 기준금리가 한 번 움직이면 내 이자와 자산 가격이 어떤 순서로 따라 움직이는지 짚었습니다."
```

`content/dictionary/circuit-breaker.md`:
```yaml
description: "주가가 급락할 때 거래를 통째로 멈춰 투자자에게 판단할 시간을 주는 제도입니다. 단계에 따라 멈추는 시간이 다르고, 발동되면 내가 낸 주문도 함께 멈춥니다."
```

`content/dictionary/supply-shock.md`:
```yaml
description: "원자재나 부품 공급이 갑자기 끊길 때 그 여파가 물가 전체로 번지는 현상입니다. 수요는 그대로인데 공급만 줄어 값이 오르고, 그 값이 다른 상품 가격으로 옮겨붙습니다."
```

- [ ] **Step 4: 사전 미달 3건을 교체한다**

기존 `description:` 줄을 통째로 바꾼다. 앞부분은 원문을 살리고 두 번째 문장만 붙였다 —
사전 리드 문단과 어긋나지 않게 하기 위해서다.

`content/dictionary/cofix.md` — 기존 48자를 다음으로 교체:
```yaml
description: "은행이 손님에게 대출해 줄 돈을 모아올 때 들어간 평균 이자 비용입니다. 이 지표가 오르면 변동금리 주택담보대출 이자가 몇 달 뒤 따라 오릅니다."
```

`content/dictionary/lng.md` — 기존 40자를 다음으로 교체:
```yaml
description: "기체 상태의 천연가스를 극저온으로 냉각해 액체로 만든 에너지 자원입니다. 배로 실어 나를 수 있다는 점 하나가 발전 단가와 겨울 난방비를 좌우합니다."
```

`content/dictionary/per.md` — 기존 44자를 다음으로 교체:
```yaml
description: "회사가 벌어들이는 이익에 비해 지금 주가가 얼마나 비싼지를 보여주는 저울입니다. 같은 이익을 내도 시장의 기대가 크면 이 숫자는 높아집니다."
```

**글자 수를 눈으로 세지 않는다.** 위 문자열은 전부 50~160자로 맞춰 썼지만 판정은 Step 5의
스크립트가 한다. 50자 미만이 나오면 그 문장에 **본문에 이미 있는 사실 한 조각만** 덧붙인다 —
새 수치나 새 주장을 만들지 않는다(`writing-styles.md`의 "숫자·사실관계 규칙").

- [ ] **Step 5: 검사가 통과하는지 확인한다**

```bash
.venv/bin/python .claude/audit/lib/quality.py | grep -c "description"
```

기대: `0`. 0이 아니면 남은 파일을 Step 4의 방식으로 고치고 다시 돌린다.

- [ ] **Step 6: 빌드가 깨지지 않았는지 확인한다**

```bash
rm -rf public && hugo --gc --minify
grep -cE '<meta name="?description"?' public/dictionary/base-rate/index.html
```

기대: 빌드 성공 · `Non-page files` 1 · grep 결과 `1`.

**속성 따옴표를 고정 문자열로 찾지 않는다.** `--minify`가 `name="description"`을 `name=description`으로
줄이므로 따옴표를 박아 넣은 grep은 빌드가 멀쩡해도 `0`을 낸다. `public/`을 검사하는 모든 grep에
같은 규칙이 적용된다.

- [ ] **Step 7: 승인을 받고 커밋한다**

**`content/` 수정이다 — 사용자에게 7개 파일 경로와 각 description 문자열을 제시하고
명확한 긍정을 받은 뒤에만** 다음을 실행한다.

```bash
git add content/posts/hormuz-red-sea-oil-supply-shock.md \
        content/dictionary/base-rate.md content/dictionary/circuit-breaker.md \
        content/dictionary/supply-shock.md content/dictionary/cofix.md \
        content/dictionary/lng.md content/dictionary/per.md
git commit -m "content: description 결함 7건 보강 (감사 2026-08-08 소견 2~8)"
```

---

## Task 2: 용어사전에 `DefinedTerm` 스키마

지금 17개 사전 항목이 전부 `BlogPosting`으로만 나가 파서 눈에는 블로그 글과 구분이 안 된다.
용어사전은 정의 출처로 인용되기 가장 쉬운 자산인데 라벨이 없다.

**설계 판단:** 테마의 `templates/schema_json.html`을 오버라이드해 `BlogPosting`을 **치환**하지
않고, `extend_head.html`로 `DefinedTerm`을 **추가**한다. 이유는 두 가지다 — (a) 오버라이드는
128줄짜리 테마 파일을 벤더링하는 것이라 PaperMod 업그레이드마다 수동 병합이 생기고,
(b) 사전 항목은 글이면서 동시에 정의이므로 두 타입이 공존하는 것이 사실과 어긋나지 않는다.
없던 라벨이 생기는 것이 이 태스크의 목표이고 그것은 추가만으로 달성된다.

**Files:**
- Create: `layouts/partials/extend_head.html`
- 검증: `public/dictionary/*/index.html` (빌드 산출물, 추적 대상 아님)

**Interfaces:**
- Consumes: PaperMod `layouts/_partials/head.html`이 `{{- partial "extend_head.html" . -}}`를
  부른다 (프로덕션 가드 **밖**이므로 모든 환경에서 실행된다).
- Produces: `layouts/partials/extend_head.html` — Task 3이 이 파일 끝에 FAQ 블록을 덧붙인다.

- [ ] **Step 1: 실패를 먼저 확인한다**

```bash
rm -rf public && hugo --gc --minify
grep -l 'DefinedTerm' public/dictionary/*/index.html | wc -l
```

기대: `0`.

- [ ] **Step 2: `layouts/partials/extend_head.html`을 만든다**

```html
{{- /* 사전 항목 = DefinedTerm. 테마가 내는 BlogPosting 은 그대로 두고 라벨만 더한다.
       테마의 templates/schema_json.html 을 오버라이드하지 않는 것은 의도적이다 —
       128줄 벤더링은 PaperMod 업그레이드마다 수동 병합을 만든다. */ -}}
{{- if and .IsPage (eq .Section "dictionary") }}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "DefinedTerm",
  "name": {{ .Title | plainify }},
  "description": {{ with .Description | plainify }}{{ . }}{{ else }}{{ .Summary | plainify }}{{ end }},
  "url": {{ .Permalink | safeHTML }},
  "inLanguage": {{ .Language.Lang | default "ko" }},
  "inDefinedTermSet": {
    "@type": "DefinedTermSet",
    "name": "경제 용어 사전",
    "url": {{ (site.GetPage "/dictionary").Permalink | safeHTML }}
  }
}
</script>
{{- end }}
{{- if and .IsSection (eq .Section "dictionary") }}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "DefinedTermSet",
  "name": "경제 용어 사전",
  "url": {{ .Permalink | safeHTML }},
  "inLanguage": {{ .Language.Lang | default "ko" }}
}
</script>
{{- end }}
```

- [ ] **Step 3: 빌드하고 개수를 센다**

```bash
rm -rf public && hugo --gc --minify
EXPECTED=$(ls content/dictionary/*.md | grep -v '/_' | wc -l)
ACTUAL=$(grep -l 'DefinedTerm' public/dictionary/*/index.html | wc -l)
echo "expected=$EXPECTED actual=$ACTUAL"
grep -c 'DefinedTermSet' public/dictionary/index.html
```

기대: `expected`와 `actual`이 같다(현재 17). 섹션 페이지의 `DefinedTermSet`은 `1`.

**`actual`이 0이면** 프로젝트 레벨 `layouts/partials/`가 테마의 `_partials/`로 해소되지 않은
것이다. 파일을 `layouts/_partials/extend_head.html`로 옮기고 다시 빌드한다. (`layouts/partials/`
쪽이 먼저다 — 이 저장소의 다른 파셜 6개가 전부 그 경로에 있고 실제로 동작한다.)

- [ ] **Step 4: 포스트가 망가지지 않았는지 확인한다**

```bash
grep -c 'BlogPosting' public/posts/tsmc-foundry-price-hike-10-percent/index.html
grep -c 'DefinedTerm' public/posts/tsmc-foundry-price-hike-10-percent/index.html
```

기대: 각각 `1`, `0`. `Non-page files`도 여전히 1이어야 한다.

- [ ] **Step 5: JSON이 실제로 유효한지 확인한다**

```bash
.venv/bin/python - <<'EOF'
import json, re, glob, sys
bad, n = [], 0
for f in glob.glob("public/dictionary/*/index.html") + glob.glob("public/posts/*/index.html"):
    for block in re.findall(r'<script type="?application/ld\+json"?>(.*?)</script>',
                            open(f, encoding="utf-8").read(), re.DOTALL):
        n += 1
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            bad.append((f, str(e)))
print(f"검사한 블록 {n}개 / 깨진 JSON-LD {len(bad)}건")
for f, e in bad[:5]:
    print(" ", f, e)
sys.exit(1 if (bad or n == 0) else 0)
EOF
```

기대: `검사한 블록 87개 / 깨진 JSON-LD 0건`, 종료 코드 0. 이 스크립트는 저장하지 않는다 — 일회성 검증이다.

**블록 수를 반드시 함께 본다.** 정규식이 하나도 못 맞히면 깨진 것이 없어서가 아니라 검사를 안 해서
`0건`이 나온다 — 그것은 통과가 아니라 실패다. 그래서 `n == 0`도 종료 코드 1로 낸다. `--minify`가
`type="application/ld+json"`의 따옴표를 지우므로 따옴표를 고정한 정규식은 이 함정에 그대로 빠진다.

- [ ] **Step 6: 커밋**

```bash
git add layouts/partials/extend_head.html
git commit -m "layouts: 용어사전에 DefinedTerm JSON-LD 추가"
```

---

## Task 3: FAQ 블록과 `FAQPage` 스키마

금융 질의는 질문형이다. 글마다 실제 질문 2~3개를 **화면에 보이게** 넣고 같은 데이터로
`FAQPage` JSON-LD를 낸다.

**먼저 알아 둘 것 — 리치 결과는 기대하지 않는다.** 구글은 2023년 8월에 FAQ 리치 결과를
정부·보건 등 권위 사이트로 제한했다. 이 태스크의 값어치는 리치 스니펫이 아니라 (a) 답변엔진과
LLM이 질문–답 쌍을 그대로 추출할 수 있게 되는 것, (b) 독자가 실제로 궁금해하는 것에 답이
붙는 것이다. 리치 결과를 목표로 적은 문서가 있다면 그것은 낡았다.

**보이지 않는 FAQ JSON-LD는 넣지 않는다.** 구조화 데이터는 페이지에 실제로 보이는 내용만
기술해야 한다. 그래서 파셜 하나가 화면 블록과 JSON-LD를 **같은 front matter에서** 만든다.

**Files:**
- Create: `layouts/partials/faq.html`
- Create: `assets/css/extended/faq.css`
- Modify: `layouts/partials/extend_head.html` (Task 2가 만든 파일 끝에 덧붙인다)
- Modify: `layouts/partials/extend_post_content.html`
- Modify: `archetypes/posts.md`
- Modify: `.claude/daily-post/draft.md` (§1 front matter 블록 + 새 규칙)

**Interfaces:**
- Consumes: 포스트 front matter의 선택 필드 `faq` — `{q: string, a: string}` 목록.
  키는 소문자 `q`·`a`다(`related_articles`가 `title`·`url`·`source`를 쓰는 것과 같은 규약).
- Produces: `.Params.faq`. 기존 17건에는 이 키가 없고, 없으면 파셜이 아무것도 내지 않는다 —
  소급 수정이 필요 없다.

- [ ] **Step 1: 실패를 먼저 확인한다**

임시 검증용으로 기존 포스트 하나에 `faq`를 넣어 본다. **커밋하지 않는다.**

`content/posts/tsmc-foundry-price-hike-10-percent.md`의 `draft:` 줄 아래에 임시로 추가:

```yaml
faq:
  - q: "파운드리 가격이 오르면 내가 사는 전자제품 값도 오르나요?"
    a: "곧바로는 아닙니다. 파운드리 단가는 칩 원가의 일부이고, 칩은 완제품 원가의 일부입니다. 인상분이 세트 가격에 반영되기까지는 보통 두세 분기가 걸립니다."
  - q: "TSMC 한 곳이 올리면 다른 파운드리도 따라 올리나요?"
    a: "선단 공정은 대체할 곳이 사실상 없어 가격 주도권이 한쪽에 쏠려 있습니다. 후발 업체가 같은 폭으로 올리는지는 공정 세대에 따라 갈립니다."
```

```bash
rm -rf public && hugo --gc --minify
grep -c 'FAQPage' public/posts/tsmc-foundry-price-hike-10-percent/index.html
grep -c '자주 묻는 질문' public/posts/tsmc-foundry-price-hike-10-percent/index.html
```

기대: 둘 다 `0`.

- [ ] **Step 2: `layouts/partials/faq.html`을 만든다**

```html
{{- /* 화면에 보이는 FAQ. extend_head.html 의 FAQPage JSON-LD 와 같은 front matter 를
       읽는다 — 한쪽만 고치면 보이지 않는 구조화 데이터가 되어 규정 위반이 된다. */ -}}
{{- if eq .Section "posts" }}
{{- with .Params.faq }}
<section class="post-faq">
  <h2 class="post-faq-title">자주 묻는 질문</h2>
  {{- range . }}
  <div class="post-faq-item">
    <h3 class="post-faq-q">{{ .q }}</h3>
    <p class="post-faq-a">{{ .a }}</p>
  </div>
  {{- end }}
</section>
{{- end }}
{{- end }}
```

- [ ] **Step 3: `assets/css/extended/faq.css`를 만든다**

```css
.post-faq {
    margin-top: var(--content-gap);
    padding: 16px 18px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

.post-faq-title {
    font-size: 18px;
    color: var(--primary);
    margin: 0 0 12px;
}

.post-faq-item {
    border-top: 1px solid var(--border);
    padding-top: 12px;
    margin-top: 12px;
}

.post-faq-item:first-of-type {
    border-top: none;
    padding-top: 0;
    margin-top: 0;
}

.post-faq-q {
    font-size: 16px;
    color: var(--primary);
    margin: 0 0 6px;
}

.post-faq-a {
    font-size: 15px;
    color: var(--content);
    line-height: 1.6;
    margin: 0;
}
```

- [ ] **Step 4: 푸터 순서에 끼운다**

`layouts/partials/extend_post_content.html`을 다음으로 만든다. FAQ가 맨 앞이다 — 본문의
연장이지 푸터 내비게이션이 아니다.

```html
{{- partial "faq.html" . -}}
{{- partial "related.html" . -}}
{{- partial "dictionary_backlinks.html" . -}}
{{- partial "related_articles.html" . -}}
{{- partial "source_link.html" . -}}
{{- partial "disclaimer.html" . -}}
```

- [ ] **Step 5: JSON-LD를 덧붙인다**

`layouts/partials/extend_head.html` **끝에** 추가한다(Task 2가 만든 두 블록은 그대로 둔다).

```html
{{- /* FAQPage. faq.html 이 같은 데이터를 화면에 렌더한다 — 보이지 않는 FAQ 마크업은
       구조화 데이터 정책 위반이라 둘을 떼어 놓지 않는다.
       리치 결과는 기대하지 않는다(2023-08 이후 권위 사이트 한정). 목적은 답변엔진 추출이다. */ -}}
{{- if and .IsPage (eq .Section "posts") }}
{{- with .Params.faq }}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{- range $i, $e := . }}{{ if $i }},{{ end }}
    {
      "@type": "Question",
      "name": {{ $e.q }},
      "acceptedAnswer": {
        "@type": "Answer",
        "text": {{ $e.a }}
      }
    }
    {{- end }}
  ]
}
</script>
{{- end }}
{{- end }}
```

- [ ] **Step 6: 통과를 확인한다**

```bash
rm -rf public && hugo --gc --minify
grep -c 'FAQPage' public/posts/tsmc-foundry-price-hike-10-percent/index.html
grep -c '자주 묻는 질문' public/posts/tsmc-foundry-price-hike-10-percent/index.html
grep -c 'FAQPage' public/posts/welcome/index.html
```

기대: 앞의 둘은 `1`, 마지막은 `0`(`faq` 없는 글에는 아무것도 나오지 않는다).
`Non-page files`는 여전히 1.

Step 5의 JSON 유효성 스크립트(Task 2 Step 5)를 다시 돌려 `깨진 JSON-LD 0건`을 확인한다.

- [ ] **Step 7: 임시 데이터를 되돌린다**

```bash
git checkout content/posts/tsmc-foundry-price-hike-10-percent.md
git diff --stat content/     # 아무것도 나오지 않아야 한다
```

기존 17건에 FAQ를 소급해 넣지 않는다 — 질문과 답을 새로 써야 하고, 그것은 본문 작성이라
이 태스크의 범위 밖이다.

- [ ] **Step 8: `archetypes/posts.md`에 예시를 넣는다**

`draft:` 줄 아래에 주석과 함께 추가한다:

```yaml
# faq 는 선택이다. 넣을 때는 2~3개, 본문이 실제로 답한 질문만.
# faq:
#   - q: "질문 한 문장"
#     a: "답 두세 문장. 본문에 없는 사실을 새로 만들지 않는다."
```

- [ ] **Step 9: `draft.md`에 작성 규칙을 넣는다**

`.claude/daily-post/draft.md` §1의 front matter 블록에서 `related_articles` 바로 위에 추가:

```yaml
    faq:                         # 선택. 2~3개. 넣을 것이 없으면 필드 전체를 생략한다(빈 배열 금지).
      - q: "<독자가 실제로 검색할 법한 질문 한 문장>"
        a: "<두세 문장. 본문에 이미 있는 사실로만 답한다>"
```

같은 §1의 본문 규칙 목록 끝에 다음 불릿을 추가한다:

```markdown
- **`faq`는 본문이 이미 답한 것만 담는다.** `layouts/partials/faq.html`이 이 값을 글 아래
  "자주 묻는 질문" 블록으로 렌더하고, `layouts/partials/extend_head.html`이 같은 값으로
  `FAQPage` JSON-LD를 낸다 — 화면에 없는 질문을 JSON-LD로만 내보내는 것은 구조화 데이터
  정책 위반이므로 둘을 떼어 놓을 수 없다.
  - 질문은 독자의 말로 쓴다. "파운드리 가격 인상의 파급효과는?"이 아니라 "파운드리 가격이
    오르면 내가 사는 전자제품 값도 오르나요?"다.
  - 답은 2~3문장. **본문에 없는 수치·사실을 여기서 새로 만들지 않는다** —
    `writing-styles.md`의 "숫자·사실관계 규칙"이 그대로 적용된다.
  - 본문 문장을 그대로 복사해 붙이지 않는다. 같은 사실을 질문에 맞춰 다시 말한다.
  - 답에 개인화 조언을 넣지 않는다("지금 사라"·"눈여겨볼 시점"). 면책 문구도 쓰지 않는다.
  - 쓸 질문이 떠오르지 않으면 **필드를 통째로 생략한다.** 억지로 채우지 않는다.
```

- [ ] **Step 10: 프롬프트 수정 뒤 교차 참조를 확인한다**

```bash
rm -rf public && hugo --gc --minify          # 새 오류 없음 · Non-page files 1
grep -n "faq.html\|extend_head.html" .claude/daily-post/draft.md
ls layouts/partials/faq.html layouts/partials/extend_head.html
```

기대: `draft.md`가 가리키는 두 경로가 실제로 존재한다.

- [ ] **Step 11: 커밋**

```bash
git add layouts/partials/faq.html layouts/partials/extend_head.html \
        layouts/partials/extend_post_content.html assets/css/extended/faq.css \
        archetypes/posts.md .claude/daily-post/draft.md
git commit -m "layouts: 포스트 FAQ 블록 + FAQPage JSON-LD, daily-post 작성 규칙 추가"
```

- [ ] **Step 12: `AGENTS.md`의 푸터 순서 문장을 갱신한다**

「콘텐츠 모델」 절의 푸터 순서 줄을 다음으로 바꾼다:

```markdown
  - 푸터 순서는 `layouts/partials/extend_post_content.html`: FAQ → 내부 관련글 → 외부 `related_articles` → 출처 링크 → 면책. FAQ가 맨 앞인 것은 본문의 연장이기 때문이고, 내부 관련글이 외부보다 먼저인 것은 체류시간이 pre-AdSense 유일 신호이기 때문이다. 외부 링크는 `rel="nofollow"`.
```

같은 절의 포스트 front matter 줄에 `faq`를 선택 필드로 추가한다:

```markdown
  front matter: `title`·`date`·`tags`·`draft`·`source_url`(원문 URL 축자), 선택 `faq`(`{q, a}` 목록)·`related_articles`(`{title, url, source}` 목록).
```

```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 푸터 순서·front matter에 faq 반영"
```

---

## Task 4: 제목 계약 — H2를 주제화하고 title 길이에 상한을 둔다

17개 글의 H2가 글자 단위로 똑같다: `무슨 일이 있었나` / `왜 중요한가` /
`나에게 무슨 의미인가` / `투자 관점에서 보면`. 검색엔진과 답변엔진은 제목으로
*어느 문단이 이 질문에 답하는가*를 찾는데, 아무도 "무슨 일이 있었나"를 검색하지 않는다.
지금 제목이 나르는 주제 신호는 0이고 파서 입장에서 17개 글은 구조가 동일하다.

4단 구성은 **작성 규율로 유지**하되 출력 제목이 주제를 말하게 한다 —
`## 근원물가가 2년 7개월 만에 최고치를 찍은 이유`.

**결정 (2026-08-10): 기존 17건은 소급 수정하지 않는다.** 규칙과 검사만 바꾸고 앞으로 쓰는
글에 적용한다. 이미 색인 요청을 넣은 URL의 본문이 흔들리지 않고, ⑥ N1/N4 재검사와 내부링크
앵커 확인이 딸려 오지 않는다. 대가는 기존 17건의 제목이 계속 주제 신호 0이라는 것이다.

**같은 이유로 이 검사를 감사에 배선하지 않는다.** `.claude/audit/lib/`에 두지만 부르는 곳은
`draft.md` §5(쓰기시점)뿐이다. 감사에 넣으면 소급 수정하지 않기로 한 17건이 매주 소견
17행으로 되살아난다.

**title 길이:** 현재 17건은 29~49자, 중앙값 40자다. 한국어 SERP는 30~35자에서 잘려 변별력
있는 뒷부분이 날아간다. 권장선 35자, **위반선 40자**로 둔다 — 35를 위반선으로 하면 지금
글의 절반 이상이 못 쓰는 제목이 되어 규칙이 무시된다.

**Files:**
- Create: `.claude/audit/lib/headings.py`
- Create: `.claude/audit/lib/test_headings.py`
- Modify: `.claude/daily-post/writing-styles.md` (9·11번째 줄 부근)
- Modify: `.claude/daily-post/draft.md` (§1 구조 규칙, §5 검사 배선)
- Modify: `AGENTS.md` (발행 전 검사 게이트 문장)

**Interfaces:**
- Consumes: `.claude/audit/lib/mdtext.py`의 `split_front_matter(raw) -> (front, body)`,
  `mask_code_spans(text) -> str`.
- Produces: `headings.check_file(path: Path) -> dict` —
  `{"file": str, "issues": [{"check": str, "detail": str}], "total": int}`.
  `numerics.check_file`과 같은 모양이라 `draft.md` §5가 두 출력을 같은 방식으로 읽는다.
  CLI: `.venv/bin/python .claude/audit/lib/headings.py --file <경로>` → JSON to stdout.
  검사 이름은 `T1`(섹션 수) · `T2`(옛 고정 제목) · `T3`(title 길이) · `T4`(주제어).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`.claude/audit/lib/test_headings.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from headings import check_file, stems  # noqa: E402

GOOD = '''---
title: "근원물가가 2년 7개월 만에 최고치를 찍은 이유"
date: 2026-08-10T09:00:00+09:00
description: "설명"
tags: ["금리", "물가"]
draft: true
source_url: "https://example.com/a"
---

첫 문단이다.

> 요약 인용블록.

## 근원물가가 최고치를 찍은 경위

내용.

## 근원물가가 왜 한은의 발목을 잡나

내용.

## 최고치가 내 대출 이자에 닿는 경로

내용.

## 물가 국면에서 자산군이 갈리는 지점

내용.
'''

LEGACY = GOOD.replace("## 근원물가가 최고치를 찍은 경위", "## 무슨 일이 있었나") \
             .replace("## 근원물가가 왜 한은의 발목을 잡나", "## 왜 중요한가") \
             .replace("## 최고치가 내 대출 이자에 닿는 경로", "## 나에게 무슨 의미인가") \
             .replace("## 물가 국면에서 자산군이 갈리는 지점", "## 투자 관점에서 보면")

LONG_TITLE = GOOD.replace(
    '"근원물가가 2년 7개월 만에 최고치를 찍은 이유"',
    '"근원물가가 2년 7개월 만에 최고치를 찍으며 한국은행의 8월 금리 결정 셈법이 복잡해진 이유"',
)

THREE_SECTIONS = GOOD.replace("## 물가 국면에서 자산군이 갈리는 지점\n\n내용.\n", "")

GENERIC = GOOD.replace("## 근원물가가 최고치를 찍은 경위", "## 배경") \
              .replace("## 근원물가가 왜 한은의 발목을 잡나", "## 의미") \
              .replace("## 최고치가 내 대출 이자에 닿는 경로", "## 영향") \
              .replace("## 물가 국면에서 자산군이 갈리는 지점", "## 앞으로")


def write(text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "sample.md"
    p.write_text(text, encoding="utf-8")
    return p


def checks(text: str) -> list[str]:
    return [i["check"] for i in check_file(write(text))["issues"]]


class TestHeadings(unittest.TestCase):
    def test_good_post_passes(self):
        self.assertEqual(check_file(write(GOOD))["total"], 0)

    def test_legacy_headings_flagged(self):
        self.assertEqual(checks(LEGACY).count("T2"), 4)

    def test_long_title_flagged(self):
        self.assertEqual(checks(LONG_TITLE), ["T3"])

    def test_wrong_section_count_flagged(self):
        self.assertIn("T1", checks(THREE_SECTIONS))

    def test_generic_headings_flagged(self):
        self.assertEqual(checks(GENERIC), ["T4"])

    def test_stems_strips_particles(self):
        self.assertIn("근원물가", stems("근원물가가 최고치를 찍었다"))
        self.assertIn("최고치", stems("근원물가가 최고치를 찍었다"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
.venv/bin/python .claude/audit/lib/test_headings.py
```

기대: `ModuleNotFoundError: No module named 'headings'`.

- [ ] **Step 3: `.claude/audit/lib/headings.py`를 쓴다**

```python
"""제목 규율 검사 — 쓰기시점 전용 (T1~T4).

`/daily-post` §5가 이번 실행이 만든 포스트 1건에만 돌린다.

**감사에 배선하지 않는다.** 2026-08-10 결정으로 이미 발행된 17건은 옛 4개 고정 H2를 그대로
두기로 했고, 감사 축에 넣으면 그 17건이 매주 소견 17행으로 되살아난다. 쓰기시점 게이트와
감사시점 판정이 갈리는 것이 여기서는 의도된 것이며, N1·N2·N4·N5(`numerics.py`)와는 다르다.

규약: 표준 라이브러리 + 정규식만(`AGENTS.md`의 「.claude/audit/lib/ 규약」). 형태소 분석기를
쓰지 않으므로 조사만 잘라 낸다 — 어미는 건드리지 않는다.

사용:
    .venv/bin/python .claude/audit/lib/headings.py --file content/posts/<slug>.md
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdtext import mask_code_spans, split_front_matter  # noqa: E402

# 2026-08-10 이전 17건이 글자 단위로 공유하던 제목. 새 글에서 되살아나면 위반이다.
LEGACY_H2 = ("무슨 일이 있었나", "왜 중요한가", "나에게 무슨 의미인가", "투자 관점에서 보면")

SECTION_COUNT = 4     # 4단 구성은 유지한다 — 바뀌는 것은 제목 문자열뿐이다
TITLE_MAX = 40        # 위반선
TITLE_SOFT = 35       # 권장선. 위반으로 만들지 않는다
TOPICAL_FLOOR = 3     # 4개 중 3개는 title 의 주제어를 담아야 한다

FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
H2 = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
TITLE = re.compile(r'^title:\s*"(.*)"\s*$', re.MULTILINE)
TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|은|는|이|가|을|를|의|에|도|와|과|로)$")
PUNCT = re.compile(r"[\s.,!?·…\-—:;'\"()\[\]]")


def _norm(text: str) -> str:
    """공백·문장부호를 떼어 낸 비교용 형태. '## 왜 중요한가?' 도 옛 제목으로 잡는다."""
    return PUNCT.sub("", text)


def stems(text: str) -> set[str]:
    """토큰과 조사 제거형을 함께 낸다. 조사만 자른다 — 형태소 분석기는 규약상 금지다."""
    out = set()
    for tok in TOKEN.findall(text):
        out.add(tok)
        s = PARTICLE.sub("", tok)
        if len(s) >= 2:
            out.add(s)
    return out


def check_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    front, body = split_front_matter(raw)
    body = mask_code_spans(FENCE.sub("", body))
    heads = [h.strip() for h in H2.findall(body)]
    m = TITLE.search(front)
    title = m.group(1) if m else ""

    issues: list[dict] = []

    if len(heads) != SECTION_COUNT:
        issues.append({
            "check": "T1",
            "detail": f"본문 H2가 {len(heads)}개 — 4단 구성은 정확히 {SECTION_COUNT}개다",
        })

    legacy = {_norm(s) for s in LEGACY_H2}
    for h in heads:
        if _norm(h) in legacy:
            issues.append({
                "check": "T2",
                "detail": f"'## {h}' 는 옛 고정 제목이다 — 이 글의 주제를 말하는 제목으로 바꾼다",
            })

    if not title:
        issues.append({
            "check": "T3",
            "detail": 'front matter title 을 `title: "..."` 형태로 읽지 못했다',
        })
    else:
        if len(title) > TITLE_MAX:
            issues.append({
                "check": "T3",
                "detail": f"title {len(title)}자 > 상한 {TITLE_MAX}자 "
                          f"(권장 {TITLE_SOFT}자 이하 — 한국어 SERP는 30~35자에서 잘린다)",
            })
        if heads:
            keys = stems(title)
            topical = sum(1 for h in heads if any(k in h for k in keys))
            if topical < TOPICAL_FLOOR:
                issues.append({
                    "check": "T4",
                    "detail": f"title 의 주제어를 담은 H2가 {topical}개 — "
                              f"최소 {TOPICAL_FLOOR}개여야 한다",
                })

    return {"file": path.as_posix(), "issues": issues, "total": len(issues)}


USAGE = "usage: headings.py --file <경로>"


def main() -> None:
    argv = sys.argv[1:]
    # numerics.py 와 같은 규약 — 알아듣지 못한 호출을 통과로 흘리지 않는다.
    if argv[:1] != ["--file"] or len(argv) != 2:
        sys.exit(USAGE)
    print(json.dumps(check_file(Path(argv[1])), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
.venv/bin/python .claude/audit/lib/test_headings.py
```

기대: `OK` (6 tests).

- [ ] **Step 5: 기존 lib 테스트가 깨지지 않았는지 확인한다**

```bash
for f in .claude/audit/lib/test_*.py; do echo "== $f"; .venv/bin/python "$f" || break; done
```

기대: 전부 `OK`.

- [ ] **Step 6: 커밋 (검사 모듈)**

```bash
git add .claude/audit/lib/headings.py .claude/audit/lib/test_headings.py
git commit -m "audit/lib: 제목 규율 결정론 검사 headings.py 추가 (쓰기시점 전용)"
```

- [ ] **Step 7: `writing-styles.md`의 두 줄을 바꾼다**

11번째 줄(섹션 구분)을 다음으로 교체한다:

```markdown
- 섹션 구분: 본문은 4개의 H2(`##`) 헤더로 구조화한다. 순서와 역할은 고정이다 — ① 무슨 일이 있었나 ② 왜 중요한가 ③ 나에게 무슨 의미인가 ④ 투자 관점에서 보면. **다만 제목 문자열을 그 네 문구로 쓰지 않는다.** 각 헤더는 그 절이 실제로 다루는 주제를 말해야 한다(예: ①을 `## 근원물가가 2년 7개월 만에 최고치를 찍은 경위`로). 검색엔진과 답변엔진은 헤더로 "어느 문단이 이 질문에 답하는가"를 찾는데, 모든 글이 같은 네 문구를 쓰면 그 신호가 0이 된다. 넷 중 최소 셋은 `title`에 나온 주제어를 담는다 — `.claude/audit/lib/headings.py`가 T4로 센다.
```

9번째 줄(두괄식)에서 `"무슨 일이 있었나"에 곧장 답한다`는 그대로 둔다 — 그것은 제목 문자열이
아니라 답해야 할 질문을 가리키는 산문이다.

"description 작성 규칙" 절 **바로 위에** 새 절을 넣는다:

```markdown
## title 작성 규칙
- 40자를 넘기지 않는다. 35자 이하가 권장이다 — 한국어 검색 결과는 30~35자에서 잘려 뒷부분이 통째로 사라진다. `.claude/audit/lib/headings.py`가 T3로 40자 초과를 위반으로 낸다.
- 변별력 있는 고유명사·지표·정책명을 **앞 20자 안에** 둔다. `A…B` 형태로 쓸 때 잘려 나가는 쪽은 항상 B다.
- 자극적 낚시 제목을 쓰지 않는다. 본문이 확인한 사실만 제목에 올린다 — "숫자·사실관계 규칙"이 제목에도 그대로 적용된다.
```

**자가검토 항목 수는 건드리지 않는다.** `contracts.py`의 `check_self_review_budget`이
"## AI 흔적 자가검토" 아래 번호 항목을 세고 예산은 12개다. 위 두 절은 번호 목록이 아니고
그 헤딩 아래도 아니므로 예산에 영향이 없다. Step 10에서 확인한다.

- [ ] **Step 8: `draft.md` §1의 구조 규칙을 바꾼다**

§1 본문 규칙의 "구조:" 불릿(현재 4개 고정 제목을 나열하는 곳)을 다음으로 교체한다:

```markdown
- 구조: 서론 문단 및 핵심 요약 인용블록(`>`)에 이어, 4개의 마크다운 2단계 헤더(`##`)로 섹션을 명시적으로 구분한다. 순서와 역할은 고정이고 **제목 문자열은 이 글의 주제를 말해야 한다.**
  1. 무슨 일이 있었나 — 사건 자체. 예: `## 근원물가가 2년 7개월 만에 최고치를 찍은 경위`
  2. 왜 중요한가 — 파급. 예: `## 이 수치가 한은의 8월 결정을 어렵게 만드는 이유`
  3. 나에게 무슨 의미인가 — 생활 경로. 예: `## 근원물가가 내 대출 이자에 닿는 길`
  4. 투자 관점에서 보면 — 자산군. 예: `## 물가 국면에서 자산군이 갈리는 지점`
  - **`## 무슨 일이 있었나` 같은 옛 고정 문구를 그대로 쓰지 않는다.** 아무도 그 말을 검색하지 않고, 그 제목을 쓰는 순간 이 글은 파서 눈에 다른 17개 글과 구조가 같아진다.
  - 넷 중 최소 셋은 `title`에 나온 주제어를 담는다. §5-3의 검사가 이것을 센다.
  - 표현 규칙은 `.claude/daily-post/writing-styles.md`의 "섹션 구분"과 "title 작성 규칙"을 따른다.
```

- [ ] **Step 9: `draft.md` §5에 검사를 배선한다**

현재 §5-3("검사를 실행할 수 없을 때")을 **§5-4로 번호만 옮기고**, 그 자리에 새 §5-3을 넣는다:

```markdown
### 5-3. 제목 검사

이번 실행이 만든 **포스트 파일 1건에만** 실행한다(사전 항목에는 돌리지 않는다):

```
.venv/bin/python .claude/audit/lib/headings.py --file <포스트경로>
```

출력 JSON의 `total`이 0이면 통과다. 0이 아니면 검사별로 고친다:

| 검사 | 잡히는 것 | 고치는 법 |
|---|---|---|
| `T1` | 본문 H2가 4개가 아니다 | 4단 구성으로 되돌린다. 절을 합치거나 나눈다 |
| `T2` | 옛 4개 고정 제목을 그대로 썼다 | 그 절이 실제로 다루는 주제를 말하는 제목으로 바꾼다 |
| `T3` | `title`이 40자를 넘는다 | 변별 키워드를 앞에 남기고 뒤를 줄인다. **제목의 사실을 바꾸지 않는다** |
| `T4` | `title`의 주제어를 담은 H2가 3개 미만이다 | 일반명사 제목(`## 배경`·`## 전망`)을 주제어가 들어간 제목으로 바꾼다 |

고친 뒤 **같은 명령을 다시 돌린다.** `total`이 0이 될 때까지 반복하되 **재시도는 최대 2회**다.
2회 뒤에도 남으면 §6 자가검토를 마친 뒤 시퀀서에 남은 위반 목록을 그대로 넘긴다.

**이 검사는 감사 축이 아니다.** 이미 발행된 글에는 돌리지 않으며, 주간 감사도 이것을 세지
않는다 — 옛 제목을 쓰는 17건은 2026-08-10 결정으로 그대로 두기로 했다.
```

§5 도입 문장("§1~4로 쓴 파일을 대상으로 아래 **두** 검사를 돌린다")의 "두"를 "세"로 고친다.

- [ ] **Step 10: 계약 검사와 빌드를 확인한다**

```bash
.venv/bin/python .claude/audit/lib/contracts.py
rm -rf public && hugo --gc --minify
grep -n "5-1\|5-2\|5-3\|5-4" .claude/daily-post/draft.md
grep -rn "headings.py" .claude/daily-post/draft.md
```

기대: `contracts.py`가 `[]`(자가검토 예산 위반 없음, 4필드 유지) · 빌드 성공 ·
`Non-page files` 1 · §5 번호가 5-1부터 5-4까지 빠짐없이 · `headings.py` 경로가 실재.

- [ ] **Step 11: 커밋 (프롬프트 계약)**

```bash
git add .claude/daily-post/draft.md .claude/daily-post/writing-styles.md
git commit -m "daily-post: H2 제목 주제화 + title 40자 상한, 발행 전 제목 검사 배선"
```

- [ ] **Step 12: `AGENTS.md`의 게이트 문장을 갱신한다**

「발행 전 검사 게이트(§J)」 문단의 첫 문장을 다음으로 바꾼다:

```markdown
**발행 전 검사 게이트(§J).** `draft.md` §5가 `.claude/audit/lib/`의 N1·N2·N4·N5, `_terms.yaml` 정합, 그리고 제목 규율 T1~T4(`headings.py`)를 돌린다. 결과는 `통과` · `남은 위반 N건` · `검사 불가` 셋 중 하나이며 §6이 그것으로 분기한다. **`검사 불가`를 `통과`와 같게 취급하지 않는다.** N 검사 코드는 감사 ⑥과 **같은 모듈**이다 — 재구현하면 쓰기시점과 감사시점의 판정이 갈린다. **T 검사는 쓰기시점 전용이며 감사에 배선하지 않는다** — 2026-08-10 결정으로 기존 17건의 옛 제목은 그대로 두므로, 감사에 넣으면 매주 같은 17행이 소견으로 되살아난다.
```

같은 파일 `/daily-post` 표의 §5 행 설명 끝에 `+ 제목 검사`를 덧붙인다.

```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 발행 전 검사 게이트에 제목 검사 반영"
```

---

## Task 5: 주제 집중 — `focus` 표시와 랭킹 가점

17개 글이 주제군 11개로 흩어져 있다. 최대 `c_g`가 9이고 전 주제군이 미달이라 감사 ②의 데이터
충분성 게이트(신호 충족 주제군 3개)가 열릴 길이 없다. 지금 속도로 넓게 가면 `topic-report.md`는
영원히 안 생긴다.

**결정 (2026-08-10): 금리 · 물가 · 부동산 · 반도체 넷을 집중 주제로 둔다.** 어휘 목록에서 다른
태그를 지우지는 않는다 — 지우면 그 주제 기사가 태그 없이 떠돌고 `portfolio.py`의 D2 통제 어휘
소진 계산도 분모를 잃는다. 대신 랭킹에서 밀어준다.

**Files:**
- Modify: `.claude/daily-post/topics.yaml`
- Modify: `.claude/daily-post/rank.md` (§3)
- Modify: `.claude/daily-post/draft.md` (§1 tags 규칙)
- Modify: `AGENTS.md` (`/daily-post` 표의 §1 행)

**Interfaces:**
- Consumes: `topics.yaml`의 최상위 태그 목록. `portfolio.py`의 `load_vocab`은 **들여쓰기 없는
  줄만** 최상위 키로 보므로, 각 주제 아래에 `  focus: true`를 들여쓰기해 넣으면 D2 계산이
  바뀌지 않는다. Step 4에서 그것을 확인한다.
- Produces: `topics.yaml`의 `focus: true` 표시. `rank.md` §3과 `draft.md` §1이 읽는다.

- [ ] **Step 1: 현재 D2 어휘 계산을 기록한다 (회귀 기준선)**

```bash
.venv/bin/python .claude/audit/lib/portfolio.py > /tmp/portfolio-before.json
grep -o '"D2"[^}]*' /tmp/portfolio-before.json | head -3
```

출력을 적어 둔다. Step 4에서 같은 값이 나와야 한다.

- [ ] **Step 2: `topics.yaml`에 표시를 넣는다**

파일 상단 주석 블록 **끝에** 다음 두 문단을 추가한다:

```yaml
# `focus: true`가 붙은 주제는 2026-08-10에 정한 집중 축이다 — 금리·물가·부동산·반도체.
# 주제 권위는 같은 주제군에 글이 쌓여야 생기고, 감사 ②의 데이터 충분성 게이트(신호 충족
# 주제군 3개)도 그 방법으로만 열린다. 넓게 가면 어느 군도 표본이 차지 않는다.
#
# 표시의 효과는 두 곳뿐이다: `rank.md` §3의 집중 주제 가점(+1)과 `draft.md` §1의 태그 선택
# 우선순위. **어휘 목록 자체는 줄이지 않는다** — 지우면 그 주제 기사가 태그 없이 떠돌고
# `portfolio.py`의 D2 통제 어휘 소진 계산이 분모를 잃는다.
```

그다음 네 주제에 `focus: true`를 **들여쓰기해서** 넣는다:

```yaml
금리:
  focus: true
  aliases: ["기준금리", "정책금리", "대출금리", "채권", "통화정책", "코픽스"]
부동산:
  focus: true
  aliases: ["주택", "전세", "주담대", "주택담보대출", "가계부채", "청약"]
물가:
  focus: true
  aliases: ["인플레이션", "소비자물가", "생산자물가", "디플레이션", "물가상승"]
```

그리고:

```yaml
반도체:
  focus: true
  aliases: ["파운드리", "메모리", "D램", "낸드", "칩", "위탁생산"]
```

나머지 9개 주제는 손대지 않는다.

- [ ] **Step 3: `rank.md` §3에 가점 규칙을 넣는다**

"### 감사 리포트 반영 (있으면만)" 절 **바로 위에** 새 절을 넣는다:

```markdown
### 집중 주제 가점

`.claude/daily-post/topics.yaml`을 Read해 `focus: true`가 붙은 주제(2026-08-10 기준
금리·물가·부동산·반도체)를 얻는다. 후보에 붙일 태그가 그중 **하나라도** 포함하면 총점에 +1.
둘 이상 포함해도 +1이며 중복 가산하지 않는다.

붙일 태그는 `draft.md` §1의 태그 규칙(목록 안에서만, `aliases`로 상위 태그 매핑)과 같은
방식으로 판단한다 — 여기서 다른 어휘를 쓰지 않는다.
```

같은 §3 맨 끝(감사 리포트 반영 절 다음)에 합산 순서를 못박는 절을 추가한다:

```markdown
### 총점 합산 순서

순서를 바꾸면 clamp 지점이 달라져 같은 후보가 다른 점수를 받는다. 아래 순서로만 계산한다.

1. 5개 기준 합계 (0~15)
2. `topic-report.md` 조정치 (−2~+3, 파일이 없으면 0)
3. 집중 주제 가점 (0 또는 +1)
4. 결과를 **0~15로 clamp**
5. 8점 임계값 판정

**15점 만점과 8점 임계값은 고정이다.** 가점도 조정치도 그 둘을 바꾸지 않는다 — 만점을 넘길
수 없고 임계값이 내려가지도 않는다.
```

- [ ] **Step 4: 회귀와 계약을 확인한다**

```bash
.venv/bin/python .claude/audit/lib/portfolio.py > /tmp/portfolio-after.json
diff <(grep -o '"D2"[^}]*' /tmp/portfolio-before.json) \
     <(grep -o '"D2"[^}]*' /tmp/portfolio-after.json) && echo "D2 동일"
.venv/bin/python .claude/audit/lib/test_portfolio.py
.venv/bin/python .claude/audit/lib/contracts.py
```

기대: `D2 동일` · `test_portfolio.py` OK · `contracts.py`가 `[]`.

**`D2 동일`이 나오지 않으면** `focus: true`가 들여쓰기 없이 들어간 것이다. `load_vocab`이
그 줄을 최상위 태그로 읽어 어휘에 `focus`가 생긴다. 들여쓰기를 확인한다.

- [ ] **Step 5: `draft.md` §1의 태그 규칙을 보강한다**

§1 tags 불릿의 하위 항목 목록에 다음 한 줄을 **맨 앞에** 넣는다:

```markdown
  - **`focus: true`가 붙은 주제(금리·물가·부동산·반도체)가 후보에 있으면 그것을 먼저 고른다.** 둘 다 맞는 상황에서만 적용한다 — 맞지 않는 태그를 억지로 붙이라는 뜻이 아니다. 이 표시는 주제군에 표본을 쌓기 위한 것이고, 틀린 태그는 표본을 쌓는 게 아니라 오염시킨다.
```

- [ ] **Step 6: 교차 참조를 확인하고 커밋한다**

```bash
grep -n "focus" .claude/daily-post/topics.yaml .claude/daily-post/rank.md .claude/daily-post/draft.md
rm -rf public && hugo --gc --minify
```

기대: 세 파일이 서로를 가리키는 문자열이 실재 · 빌드 성공 · `Non-page files` 1.

```bash
git add .claude/daily-post/topics.yaml .claude/daily-post/rank.md .claude/daily-post/draft.md
git commit -m "daily-post: 집중 주제(금리·물가·부동산·반도체) 표시와 랭킹 가점 추가"
```

- [ ] **Step 7: `AGENTS.md`의 랭킹 행을 갱신한다**

`/daily-post` 표의 §1 랭킹 행 설명을 다음으로 바꾼다:

```markdown
| §1 랭킹 | `rank.md` | `read_snapshot.py`로 사이드카 후보 스냅샷을 읽는다(RSS 직접 수집 없음). 5기준 0–15점, 8점 바닥. `topics.yaml`의 `focus: true` 주제(금리·물가·부동산·반도체)에 +1 가점, 합산 뒤 0–15로 clamp — 만점과 임계값은 고정이다. 무인은 1위 자동 선택, 바닥 미달이면 조용히 중단. 수동은 3건 제시. |
```

```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 랭킹 설명에 집중 주제 가점 반영"
```

---

## Task 6: I6 색인 조회를 표본에서 전수로

지금 `fetch_gsc.py`는 `INSPECT_CAP = 5`라 발행 URL 34개 중 5개만 본다. 그 결과 "어느 URL이
아직 색인 안 됐는지"를 모르고, 0단계의 GSC 수작업이 추측이 된다. 전수로 바꾸면 그 수작업이
정확한 작업 목록이 된다.

**쿼터:** URL Inspection API는 속성당 하루 2,000회, 분당 600회다. 주 1회 실행에 40건 남짓이면
여유가 크다. 그래도 상한은 남긴다 — 발행글이 수백 건이 되는 날 무한정 부르지 않게 하고,
쿼터 초과가 조용한 절삭이 아니라 명시적 판단이 되게 하기 위해서다. `INSPECT_CAP`을 60으로
올리고 `--inspect-cap`으로 덮어쓸 수 있게 한다.

**Files:**
- Modify: `scripts/select_inspect_urls.py`
- Modify: `scripts/fetch_gsc.py:24` (`INSPECT_CAP`), `parse_args`, `inspect_urls`
- Modify: `.github/workflows/weekly-collect.yml:58`
- Modify: `scripts/test_automation.py` (새 테스트 클래스)
- Modify: `.claude/audit/indexation.md` (§3 표 · I6 문단 · §5)

**Interfaces:**
- Consumes: `parse_post_metadata(content) -> {"draft": bool, "date": str}` (기존 함수, 그대로).
- Produces:
  - `select_all_urls(content_dir: str = "content", base_url: str = None) -> list[str]`
  - CLI `python scripts/select_inspect_urls.py --all content` → 공백 구분 URL 목록
  - `select_top_published_urls`는 **시그니처·동작 그대로 남긴다** — 기존 테스트 4건이 부른다.
  - `fetch_gsc.inspect_urls(site_url, urls, cap=DEFAULT_INSPECT_CAP)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`scripts/test_automation.py` 끝(`if __name__ == "__main__"` 위)에 추가한다:

```python
class TestSelectAllUrls(unittest.TestCase):
    """I6 전수 목록. 표본이 아니라 '아직 색인 안 된 URL'의 완전한 목록을 만든다."""

    def _fixture(self):
        root = tempfile.mkdtemp()
        posts = os.path.join(root, "posts")
        dicts = os.path.join(root, "dictionary")
        os.makedirs(posts)
        os.makedirs(dicts)

        def w(path, name, date, draft):
            with open(os.path.join(path, name), "w", encoding="utf-8") as f:
                f.write(f'---\ntitle: "t"\ndate: {date}\ndraft: {str(draft).lower()}\n---\n본문\n')

        w(posts, "old-post.md", "2026-07-01T09:00:00+09:00", False)
        w(posts, "new-post.md", "2026-08-01T09:00:00+09:00", False)
        w(posts, "hidden-post.md", "2026-08-02T09:00:00+09:00", True)
        w(posts, "welcome.md", "2026-06-01T09:00:00+09:00", False)
        w(dicts, "base-rate.md", "2026-07-15T09:00:00+09:00", False)
        w(dicts, "_index.md", "2026-07-01T09:00:00+09:00", False)
        return root

    def test_includes_entry_points_first(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        self.assertEqual(urls[:3], [
            "https://example.com/",
            "https://example.com/posts/",
            "https://example.com/dictionary/",
        ])

    def test_covers_posts_and_dictionary(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        self.assertIn("https://example.com/posts/old-post/", urls)
        self.assertIn("https://example.com/posts/new-post/", urls)
        self.assertIn("https://example.com/dictionary/base-rate/", urls)

    def test_excludes_draft_welcome_and_underscore(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        self.assertNotIn("https://example.com/posts/hidden-post/", urls)
        self.assertNotIn("https://example.com/posts/welcome/", urls)
        self.assertNotIn("https://example.com/dictionary/_index/", urls)

    def test_oldest_first_after_entry_points(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        body = urls[3:]
        self.assertEqual(body[0], "https://example.com/posts/old-post/")
        self.assertEqual(body[-1], "https://example.com/posts/new-post/")

    def test_sample_mode_unchanged(self):
        """전수 모드를 더해도 기존 표본 함수는 그대로여야 한다."""
        from select_inspect_urls import select_top_published_urls
        urls = select_top_published_urls(
            os.path.join(self._fixture(), "posts"), base_url="https://example.com")
        self.assertEqual(urls[0], "https://example.com/")
        self.assertLessEqual(len(urls), 5)


class TestInspectCap(unittest.TestCase):
    def test_cap_default_and_override(self):
        import fetch_gsc
        self.assertEqual(fetch_gsc.DEFAULT_INSPECT_CAP, 60)
        opts = fetch_gsc.parse_args(["--json", "--inspect-cap", "3",
                                     "--inspect", "https://a/", "https://b/"])
        self.assertEqual(opts["inspect_cap"], 3)
        self.assertEqual(opts["inspect"], ["https://a/", "https://b/"])
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
.venv/bin/python scripts/test_automation.py
```

기대: `ImportError: cannot import name 'select_all_urls'` 및
`AttributeError: module 'fetch_gsc' has no attribute 'DEFAULT_INSPECT_CAP'`.

- [ ] **Step 3: `select_inspect_urls.py`에 전수 모드를 넣는다**

기존 `select_top_published_urls`의 base_url 정규화 부분을 헬퍼로 뽑고 그대로 쓴다.
파일 상단 `import` 아래에 추가:

```python
def _root(base_url: str = None) -> str:
    if not base_url:
        base_url = os.environ.get("GSC_SITE_URL") or "https://econ-blog.github.io"
    if base_url.startswith("sc-domain:"):
        base_url = "https://" + base_url.removeprefix("sc-domain:")
    return base_url.rstrip("/")


def _published(md_dir: str, url_prefix: str, root: str) -> List[tuple]:
    """(발행일, URL) 목록. draft·welcome·`_` 시작 파일은 뺀다."""
    out = []
    if not os.path.isdir(md_dir):
        return out
    for fpath in sorted(glob.glob(os.path.join(md_dir, "*.md"))):
        name = os.path.basename(fpath)
        if name.startswith("_") or name == "welcome.md":
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            meta = parse_post_metadata(f.read())
        if meta["draft"] or not meta["date"]:
            continue
        out.append((meta["date"], f"{root}/{url_prefix}/{name.removesuffix('.md')}/"))
    return out


def select_all_urls(content_dir: str = "content", base_url: str = None) -> List[str]:
    """I6 전수 목록. **표본이 아니다** — '아직 색인 안 된 URL'의 완전한 목록을 만든다.

    순서가 곧 우선순위다. `fetch_gsc.py`가 cap 에서 자르므로 앞에 둔 것이 살아남는다:
      1. 홈 — 크롤 진입점
      2. 섹션 목록 두 개 — 여기가 수집되면 개별 글로 퍼진다
      3. 발행 글·사전 항목을 **오래된 순으로** — 오래된 글은 색인될 시간을 이미 받았으므로
         그것마저 미색인이면 신호가 세다. 최신순으로 두면 정의상 가장 색인 안 됐을 URL만
         앞에 오고, cap 에 걸렸을 때 정보량이 가장 적은 쪽이 살아남는다.
    """
    root = _root(base_url)
    urls = [f"{root}/", f"{root}/posts/", f"{root}/dictionary/"]
    rows = _published(os.path.join(content_dir, "posts"), "posts", root)
    rows += _published(os.path.join(content_dir, "dictionary"), "dictionary", root)
    rows.sort(key=lambda x: x[0])
    for _, url in rows:
        if url not in urls:
            urls.append(url)
    return urls
```

`select_top_published_urls` 안의 base_url 정규화 네 줄을 `root = _root(base_url)` 한 줄로
바꾼다. **나머지 로직은 손대지 않는다** — 기존 테스트 4건이 그 동작에 걸려 있다.

파일 맨 아래 `__main__` 블록을 다음으로 교체한다:

```python
if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] == ["--all"]:
        # 인자를 조용히 흘리면 워크플로가 표본을 전수로 오독한다.
        print(" ".join(select_all_urls(argv[1] if len(argv) > 1 else "content")))
    elif argv[:1] and argv[0].startswith("--"):
        sys.exit("usage: select_inspect_urls.py [--all <content_dir> | <posts_dir>]")
    else:
        print(" ".join(select_top_published_urls(argv[0] if argv else "content/posts")))
```

- [ ] **Step 4: `fetch_gsc.py`의 상한을 올린다**

24번째 줄 `INSPECT_CAP = 5`를 다음으로 교체한다:

```python
# URL Inspection API 쿼터는 속성당 하루 2,000회 · 분당 600회다. 주 1회 40건 남짓이면
# 여유가 크지만 상한은 남긴다 — 발행글이 수백 건이 되는 날 조용히 절삭되는 대신
# `truncated: true`로 드러나게 하기 위해서다. (2026-08-10, I6 표본 → 전수 전환)
DEFAULT_INSPECT_CAP = 60
```

`parse_args`의 opts 초기값에 `"inspect_cap": DEFAULT_INSPECT_CAP,`을 넣고, `--days` 분기
바로 아래에 파싱을 추가한다:

```python
        elif token == "--inspect-cap" and i + 1 < len(argv):
            opts["inspect_cap"] = max(1, int(argv[i + 1]))
            i += 2
```

**`--inspect-cap`은 `--inspect`보다 먼저 검사돼야 한다.** `--inspect`는 `--`로 시작하지 않는
토큰을 전부 삼키므로 순서가 뒤집히면 상한 값이 URL로 들어간다. `elif` 사슬에서
`--inspect-cap` 분기를 `--inspect` 분기 **위**에 둔다.

`inspect_urls`의 시그니처와 절삭을 바꾼다:

```python
def inspect_urls(site_url, urls, cap=DEFAULT_INSPECT_CAP):
    """I6 — coverageState는 가공하지 않는다. 상한은 쿼터 보호용이며 표본 설계가 아니다."""
    service = get_search_console_service()
    out = []
    for url in urls[:cap]:
```

`main()`의 호출부 두 줄을 바꾼다:

```python
            if opts["inspect"]:
                payload["inspections"] = inspect_urls(site_url, opts["inspect"],
                                                      cap=opts["inspect_cap"])
                if len(opts["inspect"]) > opts["inspect_cap"]:
                    payload["truncated"] = True
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

```bash
.venv/bin/python scripts/test_automation.py
for f in scripts/test_*.py; do echo "== $f"; .venv/bin/python "$f" || break; done
```

기대: 전부 `OK`. 특히 기존 `select_top_published_urls` 테스트 4건이 살아 있어야 한다.

- [ ] **Step 6: 로컬에서 실제 목록을 확인한다**

```bash
.venv/bin/python scripts/select_inspect_urls.py --all content | tr ' ' '\n' | head -6
.venv/bin/python scripts/select_inspect_urls.py --all content | wc -w
.venv/bin/python scripts/select_inspect_urls.py content/posts | wc -w
```

기대: 앞 3줄이 홈·`/posts/`·`/dictionary/` · 전수는 37개(진입점 3 + 포스트 17 + 사전 17) ·
표본 모드는 여전히 5 이하.

- [ ] **Step 7: 워크플로를 바꾼다**

`.github/workflows/weekly-collect.yml`의 58번째 줄을 교체한다:

```yaml
          INSPECT_URLS=$(python scripts/select_inspect_urls.py --all content)
```

**`if [ -n "$INSPECT_URLS" ]` 가드는 그대로 둔다.** 목록이 비면 `--inspect` 뒤에 아무것도
없어 `fetch_gsc.py`가 전 URL을 조회하는 것이 아니라 인자 파싱이 어긋난다.

- [ ] **Step 8: `indexation.md`를 실제와 맞춘다**

세 곳을 고친다.

(a) §3 표의 I6 행:

```markdown
| I6 색인 커버리지 | `fetch_gsc.py --inspect <url…>` (전수, 상한 60건) | 아니오 |
```

(b) "**I6은 표본이다.**"로 시작하는 문단을 통째로 교체한다. 이 문단의 마지막 줄
("표본은 최신 발행글 우선으로 고른다")은 §5의 실제 설계와 **이미 어긋나 있었다** —
같이 지운다.

```markdown
**I6은 2026-08-10부터 전수다.** 발행 URL 전부와 진입점 세 개(홈·`/posts/`·`/dictionary/`)를
조회한다. 쿼터는 속성당 하루 2,000회라 여유가 크고, 상한 60건은 발행글이 크게 늘었을 때를
위한 보호선이다. 상한에 걸리면 응답의 `truncated`가 `true`가 되며, 그때는 **조용히 표본으로
퇴화한 것이므로** 리포트에 그 사실을 적는다.
```

(c) §5의 제목과 본문. "5. I6 표본 선택과 조회"를 "5. I6 전수 목록과 조회"로 바꾸고,
명령과 "돌려주는 5건은…" 표를 다음으로 교체한다:

```markdown
.venv/bin/python scripts/select_inspect_urls.py --all content
```

```markdown
돌려주는 목록의 **순서가 우선순위다**(상한에 걸리면 앞이 살아남는다):

| 자리 | 무엇 | 무엇에 답하나 |
|---|---|---|
| 1 | 홈페이지 | 크롤 진입점이 살아 있는가. 여기가 죽으면 나머지는 볼 필요도 없다 |
| 2–3 | `/posts/` · `/dictionary/` 목록 | 여기가 수집되면 개별 글로 퍼진다 |
| 4– | 발행 글·사전 항목 전부, 오래된 순 | 어느 URL이 아직 색인 안 됐는가 |

**목록 생성은 `scripts/select_inspect_urls.py`가 유일한 주체다.** 여기에 목록을 직접 만들지
않는다 — 이 절과 스크립트가 각자 목록을 정하던 동안 둘이 어긋났고, 수집 워크플로가 스크립트
쪽을 쓰는 바람에 홈페이지가 한 번도 조회되지 않아 2026-08-01까지 13일간 홈이 이미 색인돼
있다는 사실을 놓쳤다.
```

(d) §6 리포트 조립에 새 섹션을 추가한다. **이것이 이 태스크의 실제 산출물이다** —
0단계의 사람 작업이 추측이 아니라 목록이 된다:

```markdown
### 색인 요청 대상 (사람이 GSC·네이버에 넣을 목록)

`verdict`가 `PASS`가 아닌 URL을 **그대로** 나열한다. 상한 20건, 초과분은 "외 N건".
`coverage_state` 문자열을 번역하거나 요약하지 않는다 — Search Console UI와 같아야 사람이
대조할 수 있다. 전부 색인돼 있으면 `- 없음` 한 줄로 끝낸다.

| URL | coverage_state | 마지막 크롤 |
|---|---|---|
```

- [ ] **Step 9: 교차 참조를 확인하고 커밋한다**

```bash
grep -rn "INSPECT_CAP\|inspect-cap\|select_inspect_urls" \
  scripts/ .github/workflows/ .claude/audit/indexation.md .claude/agents/naver-submit.md
grep -n "표본" .claude/audit/indexation.md
```

기대: `INSPECT_CAP = 5`가 남아 있지 않다 · 워크플로가 `--all content`를 쓴다 ·
`indexation.md`에 "I6은 표본이다"가 남아 있지 않다.

`naver-submit.md`는 `select_inspect_urls.py content/posts`(표본 모드)를 부르는데 그 함수는
그대로 살아 있으므로 깨지지 않는다. 다만 전수 목록이 더 유용하므로 그 줄도 `--all content`로
바꾸고, 바로 아래 사이트맵 `curl` 대안 문단은 그대로 둔다(샌드박스가 사이트에 도달하지
못하는 경우의 대비다).

```bash
git add scripts/select_inspect_urls.py scripts/fetch_gsc.py scripts/test_automation.py \
        .github/workflows/weekly-collect.yml .claude/audit/indexation.md \
        .claude/agents/naver-submit.md
git commit -m "collect: I6 색인 조회를 표본 5건에서 전수로 확대"
```

- [ ] **Step 10: 다음 일요일 실행을 확인한다 (사람)**

`weekly-collect.yml`은 cron-job.org가 일 01:20 KST에 건다. 다음 실행 뒤
사이드카 `econ-blog/automation-data`의 `analytics/YYYY-MM-DD/gsc_inspect.json`에
`inspections` 항목이 30건 이상 들어왔는지 확인한다. 실패하면 워크플로 로그의
`Fetch GA4 & GSC Snapshots` 스텝을 본다 — 쿼터 초과라면 `--inspect-cap`을 낮춘다.

---

## Task 7: 감사를 유지보수(무인 · LLM 없음)와 개선(수동 · LLM)으로 가른다

지금 `/weekly-audit` 한 명령이 여섯 축을 다 짊어진다. 그런데 축의 성격이 둘로 갈린다 —
**있는 것이 맞는지 보는 축**(① 링크 · ③ 색인 · ④ E/Q · ⑥ 수치)과 **무엇을 더할지 정하는
축**(② 성과 · ⑤ 방향 · ④ Q3)이다. 앞쪽은 전부 결정론이고 뒤쪽만 LLM이 필요하다.

**설계 판단 (2026-08-11): 유지보수 절반은 LLM 없이 GitHub Actions로 돌린다.** 근거는 추정이
아니라 저장소가 이미 갖고 있는 사실이다.

- 유지보수 네 축은 전부 `.claude/audit/lib/`의 결정론 모듈이 판정한다. `AGENTS.md`
  「`.claude/audit/lib/` 규약」이 못박은 대로 **"LLM은 여기의 어떤 값도 산출하지 않는다."**
- 쓰기 경로 둘도 기계적이다. 확정 사망 링크는 `link-check.md` §4의 (a)(b)(c) 규칙이
  문자열 조작으로 끝나고, 백필은 `backfill.py`가 `{term, line, slug, kind}`로 위치까지
  주며 규칙은 "그 줄 첫 등장 1회, 문서당 ≤3, 전체 ≤20"이다. 양쪽 다 **"문장·단락을
  재작성하지 않는다"**(AC #12).
- 소견의 `제안` 문자열은 검사 ID마다 고정이다 — `numeric-integrity.md`·`indexation.md`가
  이미 표로 갖고 있다.
- 네트워크 수집은 이미 Actions에서 돈다(`weekly-collect.yml`의 `analytics`·`linkstate`).

즉 지금 LLM이 하는 일은 **측정이 아니라 오케스트레이션과 한국어 리포트 조립**이다. 그것을
스크립트로 옮기면 주간 무인 루틴에서 LLM이 통째로 빠진다 — 비재현성·토큰비용·샌드박스
의존이 한꺼번에 사라진다.

**대가를 숨기지 않는다.** 리포트 산문이 합성되지 않고 표 + 고정 문구가 된다. 지금 리포트의
읽는 맛 일부는 잃는다. 잃지 않는 것은 판정값이다 — 그것은 원래 전부 결정론이었다.

**Task 8보다 먼저 한다.** Task 8은 Q1 `description` **제안값을 LLM이 쓰게** 하는데 그 값은
무인 유지보수 실행에 들어갈 수 없다. 순서를 뒤집으면 Task 8을 구현한 뒤 곧바로 옮기는
헛일이 된다. 이 태스크를 먼저 넣고, Task 8은 처음부터 **개선 명령 쪽에** 쓴다 — Q1
**탐지**는 유지보수에 남고 **제안값 생성**만 개선으로 간다. Task 8의 §9-1·`SUMMARY_KEYS`
작업도 `audit-improvement.md` 기준으로 쓴다(유지보수는 알림을 보내지 않으므로).

**Files:**
- Create: `scripts/housekeeping.py` — 유지보수 오케스트레이터(①③④E/Q⑥ + 기계적 수정 적용 + 리포트 렌더)
- Create: `scripts/test_housekeeping.py`
- Create: `.github/workflows/weekly-housekeeping.yml`
- Rename: `.claude/commands/weekly-audit.md` → `.claude/commands/audit-improvement.md` (②·⑤·Q3 전용, **수동만**)
- Modify: `.claude/audit/system-scan.md` (Q3를 개선 쪽으로, E/Q 나머지는 유지보수 쪽으로 표시)
- Modify: `AGENTS.md` (`/weekly-audit` 절 → 두 절로, 산출물 목록, 자동화 평면 표)

**Interfaces:**
- Consumes: 기존 `lib/*.py` 전부. **`lib/`는 한 줄도 고치지 않는다** — 이 태스크는 배선
  변경이지 판정 변경이 아니다.
- Produces:
  - 유지보수 → `report/housekeeping-YYYY-MM-DD.md` + `.claude/audit/link-state.json`.
    **알림을 보내지 않는다** — 아래 「알림은 개선 쪽에만」 참조.
  - 개선 → `report/audit-YYYY-MM-DD.md`(경로 **유지** — `notify-audit-report.yml`이 이
    경로에 걸려 있다) + `topic-history.json` · `topic-report.md` · `direction-log.json`

**알림은 개선 쪽에만 (2026-08-11 결정).** 유지보수는 **저장만 한다.** 리포트도 원장도
텔레그램으로 보내지 않는다 — 매주 자동으로 도는 관측치라 사람이 즉시 볼 것이 없고, 알림이
잦으면 정작 판단이 필요한 알림이 묻힌다. 개선 명령이 수동 실행 때 유지보수 산출물을
**읽어서** 처리한다.

기술적으로는 **파일명 하나로 갈린다.** `notify-audit-report.yml`은 `report/audit-*.md`
경로에만 걸려 있으므로 유지보수가 `report/housekeeping-*.md`로 쓰면 워크플로를 손대지
않고도 조용해진다. **`notify-audit-report.yml`을 수정하지 않는다.**

- [ ] **Step 1: 실패하는 테스트를 먼저 쓴다**

`scripts/test_housekeeping.py`에 최소 넷을 담는다. **리포트 산문이 아니라 판정과 편집을
검증한다.**

1. 확정 사망 내부 링크 → 대상 없으면 `[기준금리](/x/)` → `기준금리` (앵커 텍스트 보존)
2. `related_articles` 항목 제거 후 목록이 비면 **키 자체가 사라진다**(빈 리스트 금지)
3. `source_url`은 죽어도 **바뀌지 않는다**
4. 백필 적용이 문서당 3건·전체 20건에서 멈춘다

- [ ] **Step 2: `scripts/housekeeping.py`를 쓴다**

한 함수가 한 축이다. 전부 기존 lib 호출 + 문자열 조립이며 새 판정 로직을 만들지 않는다.

```
run_links()      → ① + 백필      (linkcheck.py, backfill.py, internal_links.py)
run_indexation() → ③ I1–I7       (indexation.py, fetch_gsc.py 스냅샷)
run_scan()       → ④ E/Q (Q3 제외) (quality.py, contracts.py, corpus.py)
run_numerics()   → ⑥ N1–N5       (numerics.py)
render_report()  → report/housekeeping-YYYY-MM-DD.md
apply_edits()    → 확정 사망 + 백필만
```

- 날짜는 **반드시** `kstdate.py`에서 받는다. `date.today()`를 쓰지 않는다.
- 어떤 헬퍼든 exit != 0 이면 그 결과를 해석하지 말고 리포트 최상단 '계약 위반 및 시스템
  에러' 섹션에 원문을 싣는다(I5 에러 가드). **`측정 불가`를 `통과`로 접지 않는다.**
- Hugo 부트스트랩 실패 시 ④E1·E4·③I1은 `측정 불가`다.

- [ ] **Step 3: 테스트를 통과시킨다**

```bash
.venv/bin/python scripts/test_housekeeping.py
for f in scripts/test_*.py; do echo "== $f"; .venv/bin/python "$f" || break; done
for f in .claude/audit/lib/test_*.py; do echo "== $f"; .venv/bin/python "$f" || break; done
```

기대: 전부 OK. **`lib/` 테스트가 하나도 바뀌지 않아야 한다** — 판정을 안 건드렸다는 증거다.

- [ ] **Step 4: 지난주 리포트와 대조한다 (회귀의 핵심)**

```bash
.venv/bin/python scripts/housekeeping.py --dry-run > /tmp/hk.md
diff <(grep -oE "(E[0-9]|I[0-9]|N[0-9]|Q[0-9]) [^|]*\| *[가-힣]+" report/audit-2026-08-08.md | sort) \
     <(grep -oE "(E[0-9]|I[0-9]|N[0-9]|Q[0-9]) [^|]*\| *[가-힣]+" /tmp/hk.md | sort)
```

기대: **판정 토큰(통과/관찰/소견/측정 불가)이 축별로 일치한다.** 산문은 달라도 되지만
판정이 달라지면 배선 중에 로직이 새로 들어간 것이다 — 멈추고 원인을 찾는다.

- [ ] **Step 5: 워크플로를 만든다**

`.github/workflows/weekly-housekeeping.yml` — `workflow_dispatch`만 둔다(**`schedule:`을
넣지 않는다**, cron-job.org가 건다). `weekly-collect.yml`보다 **뒤**에 걸어 그 주 스냅샷을
읽게 한다.

- 리포트·원장은 `main` 직행, `content/` 수정이 있을 때만 `auto/audit-YYYY-MM-DD` 브랜치 +
  PR(2026-08-01 결정 유지).
- **알림 스텝을 넣지 않는다.** 리포트가 `report/housekeeping-*.md`라 `notify-audit-report.yml`
  (경로 `report/audit-*.md`)이 애초에 발화하지 않는다. `telegram_notify.py`를 부르는 스텝도
  만들지 않는다 — 유지보수는 저장까지가 끝이다.
- 다만 **워크플로 자체가 실패했을 때의 경보는 남긴다**(`weekly-collect.yml`의
  `Alert on workflow failure`와 같은 형태). 조용한 것과 죽은 것을 구분할 수 없으면
  유지보수가 몇 주째 안 돌아도 아무도 모른다.
- 커밋 메시지는 사람이 읽을 수 있게 축별 판정 요약을 담되, **§9-1 블록 형식에 묶이지
  않는다** — 그 형식은 텔레그램 요약 파서를 위한 것이었고 유지보수는 알림을 보내지 않는다.

- [ ] **Step 6: 개선 명령을 분리한다**

`.claude/commands/weekly-audit.md`를 `audit-improvement.md`로 옮기고 ②·⑤·Q3만 남긴다.

- **수동 전용**이다. 무인 모드 분기를 지운다.
- ②의 데이터 충분성 게이트는 그대로. 미달이면 여전히 침묵한다.
- ⑤는 `published_count`·`site_age`를 이제 `housekeeping.py --json`에서 받는다.
- ⑥의 `n1_count`·`claims_total`·`claims_per_post` 세 값도 같은 경로로 받는다.

- [ ] **Step 7: 교차 참조와 계약을 확인한다**

```bash
.venv/bin/python .claude/audit/lib/contracts.py
grep -rn "weekly-audit" .claude/ .github/ AGENTS.md
rm -rf public && hugo --gc --minify
```

기대: `contracts.py`가 `[]` · `weekly-audit`를 가리키는 죽은 참조가 없다 · 빌드 성공 ·
`Non-page files` 1.

- [ ] **Step 8: `AGENTS.md`를 갱신한다**

`/weekly-audit` 절을 두 절로 가르고, 산출물 목록을 명령별로 나누고, 자동화 평면 표에
`weekly-housekeeping.yml` 행을 넣는다. **로드맵의 Agent3 여섯 축 문장은 그대로 둔다** —
축은 그대로이고 실행 주체만 갈렸다.

- [ ] **Step 9: 커밋**

```bash
git add scripts/housekeeping.py scripts/test_housekeeping.py \
        .github/workflows/weekly-housekeeping.yml \
        .claude/commands/audit-improvement.md .claude/audit/system-scan.md AGENTS.md
git commit -m "audit: 유지보수(무인·LLM 없음)와 개선(수동·LLM)을 두 명령으로 분리"
```

- [ ] **Step 10: 다음 일요일 실행을 확인한다 (사람)**

`report/housekeeping-*.md`가 `main`에 올라왔는지, **그리고 텔레그램이 조용한지** 본다
(알림이 왔다면 경로가 `audit-*`로 새어 `notify-audit-report.yml`이 물린 것이다). 판정이 지난주와
크게 다르면 Step 4의 대조를 다시 돌린다.

---

## Task 8: 감사 소견을 커밋으로 바꾸는 경로

2026-08-08 감사가 소견 23건을 냈고 그중 7건이 S비용 front matter 결함인데 지금까지 아무것도
처리되지 않았다. 감사는 잘 돌아간다 — `hormuz-red-sea`의 description 누락도 사람보다 먼저
찾아냈다. 문제는 소견을 커밋으로 바꾸는 단계가 없다는 것이다.

**설계 판단:** ④는 **여전히 파일을 쓰지 않는다.** ④가 만드는 것은 수정안(파일 경로 + 새
description 문자열)이고, 적용은 시퀀서 §10-4가 한다. ④의 읽기 전용 불변조건을 깨지 않으면서
결과만 PR로 나간다.

**결정론이 아니라는 점을 숨기지 않는다.** description 문자열은 LLM이 쓴다. 그래서 이 수정은
`main` 직행이 아니라 `auto/audit-*` PR로만 나가고, `process_inbox.py`는 텔레그램 "승인" 답장을
받은 PR만 머지한다 — 사람이 반드시 본다.

**알려진 한계:** 사람이 반려하면 그 PR은 닫히고, 다음 주 감사가 같은 수정안을 다시 만든다.
반려를 기억할 원장이 없다(산출물은 다섯 개로 고정이며 여섯 번째 파일을 만들지 않는다).
반려는 "사람이 직접 고치거나 규칙을 바꾼다"는 뜻으로 쓴다. 이것이 반복되면 그때 원장 추가를
따로 판단한다 — 지금 만들지 않는다.

**Files:**
- Modify: `AGENTS.md` (`/weekly-audit`의 쓰기 금지 목록 한 줄)
- Modify: `.claude/audit/system-scan.md` (§2 Q1, 리포트 조립)
- Modify: `.claude/commands/weekly-audit.md` (§5 수신, §9-1 블록, §10-4)
- Modify: `scripts/telegram_notify.py:49` (`SUMMARY_KEYS`)
- Modify: `scripts/test_automation.py` (요약 필터 테스트)

**Interfaces:**
- Consumes: `.claude/audit/lib/quality.py`의 `Q1` 출력 — `{파일경로: [결함 문자열, …]}`.
  **`quality.py`는 수정하지 않는다.**
- Produces: ④가 시퀀서에 넘기는 세 번째 덩어리 `(C) front matter 수정안` —
  `[{path, field, current, proposed}]` 형태의 목록. §10-4가 소비한다.

- [ ] **Step 1: 요약 필터에 실패하는 테스트를 쓴다**

`scripts/test_automation.py`의 `TestTelegramNotify` 클래스에 추가한다:

```python
    def test_front_matter_fix_line_survives_filter(self):
        from telegram_notify import summarize_audit_body
        body = (
            "## 감사 요약\n"
            "계약 위반: 0건\n"
            "확정 사망 링크: 0건 / 사람 점검 필요: 1건\n"
            "데이터 충분성: 미달 (발행 17 / 20건)\n"
            "색인 건전성: 관찰\n"
            "소견: 12건 (④ 5, ⑥ 7)\n"
            "front matter 수정: 3건\n"
            "새 가설 제안: 0건\n"
            "─ 결정 필요 ─\n"
            "* description 3건 수정안 승인 필요\n"
        )
        out = summarize_audit_body(body)
        self.assertIn("front matter 수정: 3건", out)
        self.assertIn("소견: 12건 (④ 5, ⑥ 7)", out)
        self.assertIn("* description 3건 수정안 승인 필요", out)
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
.venv/bin/python scripts/test_automation.py 2>&1 | tail -20
```

기대: `AssertionError: 'front matter 수정: 3건' not found in ...` — 그 줄이 필터에서
탈락한다.

- [ ] **Step 3: `SUMMARY_KEYS`에 키를 추가한다**

`scripts/telegram_notify.py`의 46~49번째 줄을 교체한다:

```python
# weekly-audit.md §9-1이 PR 본문에 쓰기로 한 일곱 줄의 키. `키:` 형태만 받는다.
# 리포트 본문의 H2(`## ⚠ 계약 위반`)는 콜론이 없어 의도적으로 탈락한다 — 리포트를
# 통째로 복사하면 값이 빠진 헤딩만 늘어서 요약처럼 보이는 빈 메시지가 된다.
SUMMARY_KEYS = ("계약 위반", "확정 사망 링크", "데이터 충분성",
                "색인 건전성", "소견", "front matter 수정", "새 가설 제안")
```

**필터 상한을 확인한다.** `summarize_audit_body`는 `filtered_lines[:12]`로 자른다. 요약 7줄 +
구분선 1줄 + 결정 항목이면 12에 여유가 있다. 상한을 바꾸지 않는다.

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
.venv/bin/python scripts/test_automation.py
```

기대: `OK`. 기존 `TestTelegramNotify` 테스트도 전부 살아 있어야 한다.

- [ ] **Step 5: 커밋 (알림 계약)**

```bash
git add scripts/telegram_notify.py scripts/test_automation.py
git commit -m "notify: 감사 요약에 front matter 수정 줄 추가"
```

- [ ] **Step 6: `AGENTS.md`의 허용 목록을 넓힌다**

`/weekly-audit` 절의 "**쓰기 금지**" 불릿 마지막 문장을 교체한다:

```markdown
- **쓰기 금지**: `.claude/daily-post/` 전체 · `hugo.toml` · `CLAUDE.md` · `MEMORY.md` · `layouts/` · `content/` 본문 산문. `content/`에서 허용되는 변경은 셋뿐이다 — 확정 사망 링크 수정 · 내부링크 백필 · **Q1 front matter 결함 수정**(description 누락·길이. 2026-08-10 추가). 셋 다 `auto/audit-*` PR로만 나가며 승인 없이 `main`에 가지 않는다. **본문 산문은 여전히 손대지 않는다.**
```

- [ ] **Step 7: `system-scan.md`의 Q1을 수정안으로 바꾼다**

§2의 Q1 불릿을 다음으로 교체한다:

```markdown
- **Q1 front matter 완비**: 결함마다 **수정안**을 만든다. 소견 표에 올리지 **않는다** —
  수정으로 나가는 항목을 소견으로도 세면 §9-1의 `소견:` 줄이 이중 계상된다.
  - 수정안 하나는 `{경로, 필드, 현재값, 제안값}` 넷을 갖춘다.
  - `description` 결함(누락·길이)이면 제안값을 **그 파일의 리드 문단에서** 뽑아
    50~160자로 쓴다. `writing-styles.md`의 "description 작성 규칙"을 따르되
    **그 파일을 읽기만 한다**(`.claude/daily-post/`는 쓰기 금지다).
  - **본문에 없는 사실·수치를 제안값에 만들지 않는다.** 리드 문단이 짧아 50자를 못
    채우면 수정안을 만들지 말고 그 파일만 소견으로 남긴다(제안 = 사람이 작성).
  - `description` 외의 필드 결함(`source_url`·`tags` 누락 등)은 **수정안을 만들지 않는다** —
    값을 지어내야 하기 때문이다. 종전처럼 소견으로 낸다.
  - **④는 여전히 어떤 파일도 쓰지 않는다.** 적용은 시퀀서 §10-4가 한다.
```

"리포트 조립 (시퀀서가 소비)" 절에 세 번째 덩어리를 추가한다:

```markdown
**(C) front matter 수정안 — §10-4용.** 0건이면 이 블록을 생략한다. 리포트 본문에는 표로
싣되(`위치 | 필드 | 현재값 | 제안값`), 소견 표와는 **다른 섹션**에 둔다.
```

- [ ] **Step 8: 시퀀서 §5의 수신부를 고친다**

`.claude/commands/weekly-audit.md` §5(④ 시스템 스캔)에서 ④가 돌려주는 덩어리를 받는 문장에
`(C)`를 더한다. ④가 (A) 계약 위반 · (B) 소견 · (C) front matter 수정안 셋을 넘기며, (C)는
§10-4까지 들고 간다고 명시한다.

- [ ] **Step 9: §9-1 블록에 여덟째 줄을 넣는다**

블록 예시의 `소견:` 줄 **아래**에 추가한다(순서를 지킨다 — 필터는 순서를 보지 않지만 사람이
읽는 순서가 계약이다):

```
front matter 수정: N건
```

같은 절의 표에 행을 추가한다:

```markdown
| `front matter 수정:` | §5(④)가 낸 (C) 블록의 항목 수. 0건이면 `0건`으로 적는다 — 줄을 생략하지 않는다 |
```

그리고 절 안의 "**일곱 줄 블록**"·"아래 일곱 줄의 문자열"이라는 표현을 **여덟**으로 고친다.

```bash
grep -n "일곱 줄" .claude/commands/weekly-audit.md
```

기대: 고친 뒤 결과 없음.

- [ ] **Step 10: §10-4의 적용 범위를 넓힌다**

§10-4의 첫 문장을 교체한다:

```markdown
  4. **콘텐츠 수정이 1건 이상일 때만** 그것만 담아 `auto/audit-YYYY-MM-DD[-HHMM]` 브랜치를
     만들어 커밋·푸시한다. 콘텐츠 수정은 셋이다 — 확정 사망 링크 수정 · 내부링크 백필 ·
     ④가 넘긴 **(C) front matter 수정안 적용**. (C)를 적용할 때는 해당 파일의 front matter
     **그 필드 한 줄만** 바꾼다. 본문은 한 글자도 건드리지 않는다.
```

같은 항목의 커밋 메시지 지침에 한 문장을 더한다:

```markdown
     커밋 메시지 본문에는 어떤 파일을 왜 고쳤는지(URL·실패 이력, front matter는 필드명과
     현재값→제안값)를 적는다. **description 제안값은 LLM 산출물이라 결정론이 아니다** —
     본문과 어긋나지 않는지가 사람이 이 PR에서 볼 것이며, 그 사실을 PR 본문에 한 줄로 적는다.
```

§10-5("콘텐츠 수정이 0건이면 §10-4를 건너뛴다. 그것이 통상 상태다")를 다음으로 바꾼다:

```markdown
  5. 콘텐츠 수정이 0건이면 §10-4를 건너뛴다. Q1 결함이 남아 있는 동안은 통상 상태가 아니다.
```

수동 모드 문단에도 한 문장을 더한다:

```markdown
  front matter 수정안이 1건 이상이면 파일 경로·필드·현재값·제안값을 표로 제시하고
  링크 수정과 **함께** 승인을 구한다. 승인 질문을 나누지 않는다 — 같은 PR로 나간다.
```

- [ ] **Step 11: 교차 참조와 계약을 확인한다**

```bash
.venv/bin/python .claude/audit/lib/contracts.py
.venv/bin/python scripts/test_automation.py
grep -n "front matter 수정" .claude/commands/weekly-audit.md .claude/audit/system-scan.md \
     scripts/telegram_notify.py AGENTS.md
grep -n "(C)" .claude/commands/weekly-audit.md .claude/audit/system-scan.md
rm -rf public && hugo --gc --minify
```

기대: `contracts.py`가 `[]` · 테스트 OK · 네 파일이 같은 문자열 `front matter 수정`을 쓴다 ·
`(C)` 블록이 생성 측과 소비 측 양쪽에 있다 · 빌드 성공 · `Non-page files` 1.

- [ ] **Step 12: 커밋**

```bash
git add AGENTS.md .claude/audit/system-scan.md .claude/commands/weekly-audit.md
git commit -m "audit: Q1 front matter 결함을 소견이 아니라 수정 PR로 내보낸다"
```

- [ ] **Step 13: 다음 감사 실행을 확인한다 (사람)**

일요일 05:00 KST `/weekly-audit` 실행 뒤:
1. 텔레그램 리포트 알림에 `front matter 수정: N건` 줄이 보이는가 (안 보이면 §9-1 형식이
   깨진 것이다 — `summarize_audit_body`가 그 줄을 못 읽는다).
2. Task 1을 이미 적용했다면 **N은 0이어야 한다.** 0이 아니면 그 사이 새로 생긴 결함이거나
   Q1 판정과 수정안 생성이 어긋난 것이다.
3. 수정안이 있으면 `auto/audit-*` PR이 열리고 별도 알림이 온다. PR 본문의 현재값→제안값을
   확인하고 텔레그램에 "승인" 또는 "반려"로 답한다.

---

## Task 9: `_terms.yaml` 병합 충돌을 구조적으로 없앤다

**2026-08-12에 실제로 터진 사고다.** PR #15(P0811)가 승인됐는데 병합되지 않고
`❌ 판정 처리 중 오류 발생: PR #15 — 병합 불가 (mergeable_state=dirty)`만 반복됐다.

원인은 스크립트가 아니다. `process_inbox.py`는 `mergeable=false`를 정상적으로 감지해 보고했고
판정도 소비하지 않았다(:379). **해소 경로가 없었을 뿐이다.**

진짜 원인은 `draft.md` §3이 새 용어를 `content/dictionary/_terms.yaml` **파일 끝에 append**한다는
것이다. 포스트 PR 두 건이 각자 표제어를 추가하면 둘 다 같은 지점(파일 끝)을 고치므로, 그 사이에
main이 전진하는 순간 git이 "changed in both"로 판정한다. #15는 base `9dacb8f`에서 열렸고
#13·#14가 08-11T16:30에 병합되며 main이 `b385707`로 갔다 — 그 순간 #15가 dirty가 됐다.

**`AGENTS.md`의 「글 PR이 둘 동시에 열려 있는 구간이 없다」는 이미 사실이 아니다.** 인박스가
매일 도는 것을 전제한 문장인데, 사람이 며칠치 판정을 몰아서 답하면 #13·#14·#15처럼 셋이 함께
열린다. 그 상태가 이 충돌의 필요조건이다.

**설계 판단: 두 겹으로 막는다.** 하나만으로는 부족하다.

1. **정렬 삽입(발생 확률을 낮춘다).** 표제어를 슬러그 사전순 위치에 넣으면 서로 다른 슬러그는
   대개 다른 줄에 들어가 충돌하지 않는다. 인접 슬러그는 여전히 부딪히므로 이것만으로는 부족하다.
2. **인박스 자동 해소(남은 것을 처리한다).** `mergeable_state=dirty`이고 충돌 파일이
   `_terms.yaml` **하나뿐일 때만**, main을 브랜치에 병합해 양쪽 표제어를 모두 보존하고 다시 민 뒤
   병합을 1회 재시도한다. 2026-08-12에 사람이 손으로 한 것과 같은 절차다.

**`.gitattributes`의 `merge=union`은 쓰지 않는다.** git 내장 드라이버지만 GitHub 서버측 병합이
이것을 존중하는지 문서로 보장되지 않고, 존중하더라도 같은 슬러그가 양쪽에 들어오면 중복 키를
조용히 만든다. 우리 코드 안에서 검증 가능한 경로를 택한다.

**범위 밖(하지 않는다).** `_terms.yaml`을 사전 파일 front matter에서 파생시키는 방식은 근본적이지만
`aliases`가 사전 `.md`에 없어서 스키마 변경이 먼저다. 이 태스크에서 하지 않는다.

**Files:**
- Modify: `scripts/process_inbox.py` (dirty 자동 해소 경로)
- Modify: `scripts/test_automation.py` (새 테스트)
- Modify: `.claude/daily-post/draft.md` (§3 정렬 삽입 규칙)
- Modify: `.claude/audit/lib/contracts.py` + `test_contracts.py` (중복 키 검사)
- Modify: `AGENTS.md` (「글 PR이 둘 동시에」 문장 정정)

**Interfaces:**
- Consumes: `process_inbox.py`의 `wait_until_mergeable`(현행 유지), GitHub PR API의
  `mergeable_state`.
- Produces: 없음. 다른 태스크가 이 결과에 의존하지 않는다.

- [ ] **Step 1: 실패하는 테스트를 먼저 쓴다**

`scripts/test_automation.py`에 넷을 담는다. **네트워크를 타지 않는다** — 병합 결과 문자열을
만드는 순수 함수를 테스트한다.

1. 서로 다른 표제어 두 건 → 양쪽 모두 살아남고 중복 0
2. **같은 슬러그가 양쪽에 있으면 → 병합하지 않고 실패로 낸다**(사람이 봐야 한다)
3. 충돌 파일이 `_terms.yaml` 외에 하나라도 더 있으면 → 자동 해소하지 않는다
4. 해소 결과가 표제어 사이 빈 줄 규약을 지킨다

- [ ] **Step 2: 중복 키 검사를 `contracts.py`에 넣는다**

`check_terms_sync`는 slug ↔ 파일 대응만 본다. **같은 키가 두 번 나오는 경우를 보지 않는다** —
자동 해소가 만들 수 있는 유일한 오염이므로 여기서 막는다. `test_contracts.py`에 테스트를 함께 낸다.

- [ ] **Step 3: 인박스에 자동 해소 경로를 넣는다**

`wait_until_mergeable`이 `BLOCKED (mergeable_state=dirty)`를 돌려줄 때만 탄다.

```
1. PR의 충돌 파일 목록을 얻는다
2. `content/dictionary/_terms.yaml` 하나뿐이 아니면 → 종전대로 BLOCKED 보고하고 멈춘다
3. 맞으면 main을 PR 브랜치에 병합하고 _terms.yaml 을 양쪽 보존으로 해소한다
4. 중복 키가 생기면 되돌리고 BLOCKED 보고 (Step 2의 검사를 쓴다)
5. push 하고 병합을 **1회만** 재시도한다
```

- **재시도는 1회다.** 무한 루프를 만들지 않는다.
- **판정은 여전히 소비하지 않는다.** 실패하면 다음 회차가 다시 시도한다(:379 규약 유지).
- 자동 해소를 했으면 텔레그램에 **한 줄로 알린다** — 사람이 모르는 사이에 콘텐츠 브랜치가
  바뀌는 일이 없어야 한다.

- [ ] **Step 4: `draft.md` §3을 정렬 삽입으로 바꾼다**

"파일 끝에 append"를 "슬러그 사전순 위치에 삽입"으로 바꾼다. 기존 항목 순서를 재정렬하지
**않는다** — 한 번에 전부 정렬하면 그 커밋 자체가 거대한 충돌이 된다. 새 항목만 제자리에 넣는다.

- [ ] **Step 5: `AGENTS.md`의 사실과 다른 문장을 고친다**

「하루는 한 방향으로 흐른다」 절의 "글 PR이 둘 동시에 열려 있는 구간이 없다"를 바꾼다 —
사람이 며칠치를 몰아 답하면 여러 건이 함께 열리며, 그것이 정상 운영 범위임을 적는다.

- [ ] **Step 6: 검증**

```bash
.venv/bin/python scripts/test_automation.py
.venv/bin/python .claude/audit/lib/test_contracts.py
.venv/bin/python .claude/audit/lib/contracts.py     # []
for f in scripts/test_*.py; do .venv/bin/python "$f" || break; done
```

**회귀 재현**: `9dacb8f`(#15 base)와 `b385707`(당시 main)로 2026-08-12 충돌을 그대로 재현해
자동 해소가 표제어 19개·중복 0·고아 0을 내는지 확인한다. 그 값이 사람이 손으로 낸 결과다.

- [ ] **Step 7: 커밋**

```bash
git add scripts/process_inbox.py scripts/test_automation.py \
        .claude/audit/lib/contracts.py .claude/audit/lib/test_contracts.py \
        .claude/daily-post/draft.md AGENTS.md
git commit -m "inbox: _terms.yaml 단독 충돌을 자동 해소하고 중복 키를 막는다"
```

---

## 자기 검토 (계획 작성자가 이미 돌린 것)

**1. 스펙 커버리지.** 원래 PLAN.md의 다섯 단계 중:
- 1단계(발견 가능성) → 「0단계」로 남겼다. 코드가 없어 태스크가 아니다.
- 2단계(AEO) 네 항목 → description은 Task 1, `DefinedTerm`은 Task 2, `FAQPage`는 Task 3,
  제목 길이는 Task 4에 흡수했다(같은 두 파일의 같은 줄을 건드려 태스크를 나누면 충돌한다).
- 3단계(H2 구조) → Task 4. 소급 수정 없음으로 확정.
- 4단계(주제 집중) → Task 5. 금리·물가·부동산·반도체로 확정.
- 5단계(소견 소비) 세 항목 → 자동 수정과 판단 소견 분리는 Task 8, I6 확대는 Task 6.
  감사를 유지보수/개선 두 명령으로 가르는 Task 7은 2026-08-11에 추가했다 — Task 8보다
  **먼저** 한다(Q1 제안값이 LLM 산출물이라 무인 유지보수에 들어갈 수 없다).

**2. 남은 결정.** 없다. 3·4단계의 "합의 필요" 두 건은 2026-08-10에 확정했고 해당 태스크
본문에 근거와 대가를 함께 적었다.

**3. 타입 정합.** Task 4의 `check_file` 반환 모양은 `numerics.check_file`과 같고(`file`·
`total` + 항목 목록), 검사 이름 `T1~T4`는 기존 `N1·N2·N4·N5`, `Q1·Q3·Q4·Q5`, `E1~E4`,
`I1~I7`, `D1~D4`, `P1~P3` 어느 것과도 겹치지 않는다. Task 6의 `select_top_published_urls`는
시그니처를 그대로 두고 `_root`만 뽑아 썼으므로 기존 테스트 4건이 그대로 통과한다.
Task 3의 front matter 키는 `q`·`a` 소문자로 `related_articles`의 `title`·`url`·`source`와
같은 규약이다.

**4. 조용히 깨질 수 있는 곳.** 계획이 새로 만드는 양방향 계약은 셋이다. 각각 같은 태스크
안에서 양쪽을 고치도록 단계를 배치했다.
- `faq` front matter ↔ `faq.html`(화면) ↔ `extend_head.html`(JSON-LD) — Task 3.
  한쪽만 고치면 보이지 않는 구조화 데이터가 되어 정책 위반이 된다.
- `topics.yaml`의 `focus` ↔ `rank.md` 가점 — Task 5. Step 4가 `load_vocab` 회귀를 잡는다.
- §9-1 여덟째 줄 ↔ `SUMMARY_KEYS` — Task 8. Step 1의 테스트가 그것 하나를 본다.
  (Task 7 뒤에는 이 계약이 `audit-improvement.md` 쪽에만 걸린다 — 유지보수는 알림을
  보내지 않으므로 요약 파서를 타지 않는다.)

---

## AdSense 재평가 기준

구글은 최소 글 수나 트래픽 기준을 공개하지 않는다. 숫자를 대는 사람은 추측하는 것이다.
대신 *지금 신청하면 왜 떨어지는가*는 분명하다 — 구글 자신이 한 페이지밖에 색인하지 않은
사이트를 심사자가 열어보게 된다.

| 조건 | 현재 | 기준 | 판정 |
|---|---|---|---|
| 정책 페이지 (소개·연락처·개인정보) | 3 / 3 | 3 | 충족 |
| 발행 글 수 | 17 | 꾸준한 발행 이력 | 사실상 충족 |
| 색인된 페이지 | 1 / 5 표본 | 대부분 색인 | **미달** |
| GSC 노출 (28일) | 0 | 몇 주 연속 0 아님 | **미달** |
| 자연 유입 비중 | 0% | direct 100%가 아닐 것 | **미달** |
| 도메인 | `github.io` | 사용자 도메인 권장 | 권장 |

현실적으로 0단계가 이번 주에 되면 **4~8주 뒤**가 재평가 시점이다. 신청은 한 번에 되는 게
낫다 — 반려되면 재신청까지 시간이 든다. `github.io`는 AdSense가 받아주긴 하지만 공유
도메인이라, 신청 전에 도메인을 사두는 쪽을 권한다. SEO 자산을 나중에 옮길 수 있다는 이유만으로도
값어치가 있다.

Task 6이 들어가면 위 표의 "색인된 페이지" 행이 표본이 아니라 전수 값이 된다. 재평가 판단을
그 값으로 한다.

---

## 글 자체는 바꾸지 않는다

바꾸라는 얘기가 위에 하나도 없다는 점을 분명히 해둔다.
`content/posts/bok-august-rate-hike-core-inflation-dilemma.md`를 끝까지 읽은 결과다.
수치마다 값·출처·기준일이 표로 붙고, 애널리스트 인용은 소속과 함께 *서로 반대되는 쪽*을
나란히 놓았고, 지난 글로 이어지는 맥락을 명시적으로 짚는다. 근원물가 사전 항목은 정의 대신
몸무게 비유로 시작한다.

그건 답변엔진이 인용하고 싶어 하는 형태다. 위 계획은 전부 **그 글이 발견되고 추출되게 만드는**
얘기지, 다르게 쓰라는 얘기가 아니다. Task 1이 유일하게 `content/`를 건드리는데 그것도
front matter 한 줄이고, Task 3·4의 새 규칙은 앞으로 쓰는 글에만 적용된다.

---

## 완료 후

일곱 태스크가 전부 끝나고 0단계의 색인 요청이 한 바퀴 돈 뒤:

1. 이 파일을 **지운다**(`git rm PLAN.md`).
2. `AGENTS.md`의 「저장소 규약」에서 `PLAN.md` 불릿을 지운다.
3. `MEMORY.md`에 남길 것은 결론뿐이다 — 왜 소급 수정을 하지 않았는지, 왜 집중 주제가
   넷인지, 왜 `DefinedTerm`을 오버라이드가 아니라 추가로 넣었는지, T 검사를 감사에 배선하지
   않은 이유. 태스크 목록과 코드는 옮기지 않는다. git 이력에 있다.
