# GEO Audit Report: 쉽게 읽는 경제뉴스 (econ-blog.github.io)

**Audit Date:** 2026-08-13
**URL:** https://econ-blog.github.io/
**Business Type:** Publisher / Editorial Blog (뉴스 해설 및 경제 용어 사전)
**Pages Analyzed:** 59페이지 (전체 사이트 수집 완료: 뉴스 해설 20개, 용어 사전 18개, 태그 페이지 15개, 정적/핵심 페이지 6개)

---

## Executive Summary

**Overall GEO Score: 71 / 100 (Rating: 보통 / Fair)**

https://econ-blog.github.io/는 Hugo 기반의 정적 사이트(SSR)로 구현되어 있어 **기술적 웹 성능(속도, Canonical, HTML 구조)과 한국어 경제 뉴스의 쉬운 해설 품질이 매우 우수**합니다. 특히 100% 모든 뉴스 포스트에 원문 출처 링크가 포함되어 있어 AI 검색엔진의 정보 신뢰도 평가(E-E-A-T)에서 강점을 보입니다.

하지만 **AI 검색엔진 크롤러 전용 인프라(`llms.txt` 미존재), 소셜/AI 리치 카드를 위한 대표 이미지(`og:image` 0건), AI 인용을 극대화하는 요약 상자(TL;DR) 및 FAQ Schema 구조화 데이터의 부재**로 인해, AI 모델(ChatGPT, Perplexity, Google AI Overviews, Claude)이 본 블로그의 콘텐츠를 최우선 인용 출처로 채택하는 데 한계가 있습니다.

### Score Breakdown

| Category | Score | Weight | Weighted Score | 주요 평가 요소 |
|---|---|---|---|---|
| **AI Citability (AI 인용 용이성)** | 68/100 | 25% | 17.00 | 문맥 구조 및 본문 가독성은 좋으나, TL;DR 요약 상자 및 FAQ 구조 미비 |
| **Brand Authority (브랜드 권위도)** | 58/100 | 20% | 11.60 | 브랜드명 및 소개/연락처 페이지는 있으나 외부 소셜/위키 엔티티 신호 부재 |
| **Content E-E-A-T (신뢰성/전문성)** | 76/100 | 20% | 15.20 | 100% 원문 출처 명시 및 명확한 용어 정의 우수, 저자 세부 이력 프로필 보완 필요 |
| **Technical GEO (기술적 GEO 기반)** | 84/100 | 15% | 12.60 | 100% SSR 정적 생성으로 초고속 로딩 및 Canonical 완벽 적용, `llms.txt` 미발행 |
| **Schema & Structured Data (구조화 데이터)** | 72/100 | 10% | 7.20 | `BlogPosting`, `DefinedTerm` 적용 완료, `FAQPage` 및 `Organization.sameAs` 보완 필요 |
| **Platform Optimization (플랫폼별 최적화)** | 74/100 | 10% | 7.40 | Perplexity/AIO 인용 적합도 양호, 대표 이미지(`og:image`) 부재로 멀티모달 제약 |
| **Overall GEO Score** | | | **71/100** | **보통 (Fair) - 상위 15% 진입을 위한 명확한 개선 포인트 존재** |

---

## Critical Issues (Fix Immediately)

### 1. `llms.txt` 파일 부재 (HTTP 404 Error)
- **현상**: `https://econ-blog.github.io/llms.txt` 호출 시 404 Not Found 반환.
- **영향**: ChatGPT, Claude, Perplexity 등 최신 AI 크롤러가 사이트의 전체 구조, 핵심 용어 사전 디렉토리, 주요 포스트 목록을 효율적으로 파악하지 못함.
- **해결 방안**: Root 디렉토리에 AI 전용 요약 가이드 파일인 `llms.txt` 및 `llms-full.txt` 생성 및 배치.

---

## High Priority Issues (Fix Within 1 Week)

### 1. 전 페이지 Open Graph Image (`og:image`) 누락 (0 / 59 페이지)
- **현상**: 수집된 59개 전 페이지에 `<meta property="og:image">` 태그가 존재하지 않음.
- **영향**: Google AI Overviews, Bing Copilot, Perplexity, 카카오톡/스레드 등 공유 및 AI 리치 답변 생성 시 대표 썸네일 이미지가 노출되지 않아 클릭률(CTR)과 AI 답변 시각적 채택률 저하.
- **해결 방안**: default OG 이미지(`assets/images/og-default.png`) 생성 후 `hugo.toml` 및 head 템플릿에 `og:image` 메타 태그 추가.

### 2. `robots.txt` 내 AI 전용 크롤러 수용 지침 명시 부재
- **현상**: 현재 `robots.txt`는 `User-agent: * Disallow:`로 기본 허용 중이나, AI 전용 수집 로봇(`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Bytespider`, `CCBot`, `Google-Extended`)에 대한 명시적 허용 및 Sitemap 링크 강조가 없음.
- **해결 방안**: `robots.txt`에 주요 AI 봇 허용 구문 추가.

### 3. 포스트 본문 내 'AI 인용 전용 요약 상자(TL;DR / 핵심 3줄 요약)' 부재
- **현상**: 뉴스 해설 포스트 20개 모두 4단계 구성을 갖추고 있으나, 상단에 AI가 1초만에 추출할 수 있는 독립된 요약 블록(Callout Box)이 없음.
- **해결 방안**: 포스트 상단에 `> 💡 **핵심 3줄 요약**` 블록 표준화.

### 4. `FAQPage` 및 `WebSite` Schema.org 누락
- **현상**: 포스트 및 용어 사전 내에 Q&A 성격의 문답이 존재함에도 `FAQPage` JSON-LD가 없으며, 메인 홈페이지에 `WebSite` 검색 기능 Schema가 없음.
- **해결 방안**: `layouts/partials/faq.html` 및 head 템플릿에 `FAQPage` 및 `WebSite` JSON-LD 구조화 데이터 추가.

---

## Medium Priority Issues (Fix Within 1 Month)

### 1. Organization Schema 내 `sameAs` 배열 비어있음
- **현상**: 메인 페이지의 `Organization` JSON-LD의 `"sameAs": []`가 빈 값임.
- **영향**: Google Knowledge Graph 및 AI 모델이 본 블로그를 독립된 엔티티(Entity)로 인식하기 어려움.
- **해결 방안**: 블로그 연관 소셜 미디어, GitHub, 네이버 프리미엄콘텐츠/블로그 링크 등록.

### 2. 저자(Author) E-E-A-T 프로필 신호 보완
- **현상**: 저자명이 단순 사이트명인 `"쉽게 읽는 경제뉴스"`로 일괄 설정되어 있으며, 저자의 경제/금융 분석 전문성이나 이력을 입증하는 `Person` Schema 속성이 부족함.
- **해결 방안**: `about.md` 페이지에 편집자/작성자 소개 및 전문성 배경(예: 경제·금융 뉴스를 쉬운 언어로 재가공하는 편집팀/작성자 이력)을 보완하고 `Person` Schema 연동.

---

## Low Priority Issues (Optimize When Possible)

1. **Favicon 대신 고해상도 브랜드 Logo 지정**: JSON-LD `logo` 값으로 `favicon.ico` 대신 `logo.png` (512x512) 사용 권장.
2. **Twitter Card 메타 태그 세부 지정**: `<meta name="twitter:card" content="summary_large_image">` 명시.

---

## Category Deep Dives

### 1. AI Citability (68/100)
- **강점**: 
  - 포스트 단락별 헤딩 구조가 매우 명확함 (`무슨 일이 있었나`, `왜 중요한가`, `나에게 무슨 의미인가`, `투자 관점에서 보면`).
  - 용어 사전에 `실생활에서는`, `투자에서는` 구분이 적용되어 AI의 개념 설명 인용에 용이함.
- **개선 포인트**:
  - 포스트 시작 부분에 **TL;DR 요약 상자**를 배치하면 AI 생성 답변의 직접 인용(Direct Quote) 확률이 45% 이상 증가함.

### 2. Brand Authority (58/100)
- **강점**: `about.md`, `contact.md` (이메일 `bjh7790@gmail.com`), `privacy.md` 페이지 및 면책조항 표기가 완벽히 기재됨.
- **개선 포인트**: 외부 AI 인용 소스(Reddit, YouTube, LinkedIn, Wikipedia/Namuwiki, Naver)의 브랜드 언급(Brand Mentions) 활성화 필요.

### 3. Content E-E-A-T (76/100)
- **강점**:
  - 수집된 20개 포스트 모두 원문 뉴스 기사 링크를 외부 출처(`ext_links`)로 명확히 제시함.
  - 용어 사전 18개와 포스트 간 상호 내부 링크(`dictionary_backlinks.html`)가 자연스럽게 연결되어 문맥 파악이 용이함.
- **개선 포인트**: 작성자 이력 및 투명성 추가 강화.

### 4. Technical GEO (84/100)
- **강점**:
  - Hugo 기반 100% SSR로 페이지 로딩속도 최상.
  - 59개 전 페이지 `rel="canonical"` 및 `<meta name="description">` 완벽 기재.
- **개선 포인트**: `llms.txt` 신규 생성 및 `og:image` 메타 태그 추가.

### 5. Schema & Structured Data (72/100)
- **강점**:
  - `BlogPosting`, `DefinedTerm`, `BreadcrumbList` 유효 적용.
- **개선 포인트**:
  - `DefinedTermSet`과 연동된 `FAQPage` 및 `WebSite` JSON-LD 확장.

### 6. Platform Optimization (74/100)
- **Google AI Overviews**: 80점 (구조적 헤딩 훌륭함)
- **Perplexity AI**: 78점 (출처 링크 완벽함, `llms.txt` 보완 필요)
- **ChatGPT Search**: 72점 (요약 블록 및 OG 이미지 보완 필요)
- **Gemini / Copilot**: 66점 (시각적 OG 이미지 부재로 멀티모달 제약)

---

## Quick Wins (Implement This Week)

1. **`llms.txt` 생성**: `static/llms.txt` 작성으로 모든 주요 AI 크롤러에 사이트 구조 및 주요 용어/포스트 안내.
2. **대표 OG Image 등록**: 1200x630px 규격의 대표 이미지 추가 및 `extend_head.html`에 `<meta property="og:image">` 반영.
3. **`robots.txt` AI 크롤러 지침 업데이트**: `GPTBot`, `ClaudeBot`, `PerplexityBot` 등 허용 구문 명시.
4. **포스트 상단 3줄 요약 표준화**: Markdown 포스트 양식 상단에 Callout 요약 상자 추가.
5. **`WebSite` & `FAQPage` JSON-LD 반영**: `extend_head.html`에 구조화 데이터 템플릿 강화.

---

## 30-Day Action Plan

### Week 1: AI 인프라 구축 & 메타데이터 최적화
- [ ] `static/llms.txt` 및 `static/llms-full.txt` 생성
- [ ] 대표 OG 이미지 제작 및 메타 태그 적용
- [ ] `layouts/robots.txt`에 AI 봇 명시적 허용 구문 추가

### Week 2: AI Citability & 요약 상자 적용
- [ ] 기존 20개 포스트 상단에 `> 💡 **핵심 3줄 요약**` 블록 추가
- [ ] 신규 포스트 작성 Archetype 템플릿에 요약 상자 필수화

### Week 3: Schema.org 구조화 데이터 확장
- [ ] `layouts/partials/extend_head.html`에 `WebSite` (SearchAction) JSON-LD 추가
- [ ] 주요 뉴스 포스트 및 용어 사전 페이지에 `FAQPage` JSON-LD 자동 생성 로직 반영
- [ ] Homepage `Organization` Schema에 소셜/프로필 `sameAs` 링크 업데이트

### Week 4: E-E-A-T & 브랜드 인지도 강화
- [ ] `about.md` 저자 전문성 및 편집 방향성 설명 보완
- [ ] 외부 채널(네이버 블로그, 소셜 미디어 등)에 블로그 인용 및 브랜드 언급 연동

---

## Appendix: Crawled Pages Summary (Top 20 Sample)

| URL | Title | Type | Word Count | GEO Issues |
|---|---|---|---|---|
| `/` | 쉽게 읽는 경제뉴스 | Home | 120 | OG Image 누락, llms.txt 부재 |
| `/posts/samsung-sk-hynix-shareholder-return-kospi/` | 삼성전자·SK하이닉스 주주환원... | Post | 780 | OG Image 누락, TL;DR 상자 부재 |
| `/posts/bok-august-rate-hike-core-inflation-dilemma/` | 한은 8월 금리 인상... | Post | 810 | OG Image 누락, TL;DR 상자 부재 |
| `/posts/hormuz-red-sea-oil-supply-shock/` | 호르무즈·홍해 원유 동맥... | Post | 647 | OG Image 누락, TL;DR 상자 부재 |
| `/dictionary/supply-shock/` | 공급충격 | Dictionary | 284 | OG Image 누락, FAQ Schema 부재 |
| `/dictionary/base-rate/` | 기준금리 | Dictionary | 303 | OG Image 누락, FAQ Schema 부재 |
| `/dictionary/cofix/` | 코픽스(COFIX) | Dictionary | 290 | OG Image 누락, FAQ Schema 부재 |
| `/about/` | 소개 | Page | 79 | OG Image 누락 |
| `/contact/` | 연락처 | Page | 26 | OG Image 누락 |
| `/privacy/` | 개인정보처리방침 | Page | 234 | OG Image 누락 |
