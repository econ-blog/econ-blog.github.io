#!/usr/bin/env python3
"""SEO/GEO 크롤 감사기.

Hugo가 뽑아낸 `public/` 트리를 로컬 크롤러로 훑어 여덟 축을 판정한다.
축: 크롤 가능성 / 색인 / 페이지 의도 / 타이틀 / 내부 링크 / 구조화 데이터 /
출처 인용 / 답변 우선 서술.

`.claude/audit/lib/`의 주간 감사와 겹치지 않는다 — 저쪽은 `content/` 마크다운을
읽고 이쪽은 **렌더된 HTML**을 읽는다. 검색엔진과 답변엔진이 실제로 보는 것은
후자이며, 두 층이 어긋나는 결함(테마가 삼키는 메타, 부분 렌더되는 JSON-LD,
페이지네이션이 만드는 얕은 사본)은 마크다운 쪽에서는 원리적으로 보이지 않는다.

사용:
    hugo --environment production --destination /tmp/public
    .venv/bin/python scripts/seo_geo_audit.py /tmp/public --json out.json
"""

import argparse
import collections
import html
import json
import os
import re
import sys
import urllib.parse

BASE = "https://econ-blog.github.io/"

# numerics.PRIMARY_HOSTS 와 같은 6개 (계약: primary_source_hosts).
# 여기서 다시 적는 것은 중복이 아니라 렌더 산출물 쪽 독립 관측이다 —
# 마크다운에 있던 링크가 HTML 까지 살아 나왔는지를 본다.
PRIMARY_HOSTS = (
    "ecos.bok.or.kr",
    "fred.stlouisfed.org",
    "kosis.kr",
    "dart.fss.or.kr",
    "portal.kfb.or.kr",
    "bis.org",
)

# 답변엔진이 인용 단위로 자르는 첫 덩어리. 이보다 길면 리드에서 답이 끝나지 않는다.
ANSWER_LEAD_MAX_CHARS = 320
# 구글이 한국어 타이틀을 자르는 대략적 경계(픽셀 기준을 글자수로 환산).
TITLE_MAX_CHARS = 35
DESC_MIN_CHARS, DESC_MAX_CHARS = 70, 160
THIN_PAGE_CHARS = 600


# ---------------------------------------------------------------- HTML 파싱
# 정규식 파싱은 임의의 HTML 에는 부적절하지만 여기 입력은 Hugo 가 만든
# 우리 자신의 템플릿 출력이며 형태가 고정돼 있다. 의존성 0개를 유지한다.

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style|nav)\b.*?</\1>", re.S | re.I)


def strip_tags(s):
    return html.unescape(TAG_RE.sub("", s)).strip()


def collapse_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def meta(doc, name=None, prop=None):
    if name:
        pat = r'<meta[^>]+name=["\']%s["\'][^>]*>' % re.escape(name)
    else:
        pat = r'<meta[^>]+property=["\']%s["\'][^>]*>' % re.escape(prop)
    m = re.search(pat, doc, re.I)
    if not m:
        return None
    c = re.search(r'content=["\'](.*?)["\']', m.group(0), re.S)
    return html.unescape(c.group(1)).strip() if c else None


def jsonld_blocks(doc):
    """(파싱된 객체 | None, 원문) 목록. 파싱 실패도 결함이므로 버리지 않는다."""
    out = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', doc, re.S | re.I
    ):
        try:
            out.append((json.loads(raw), raw))
        except Exception:
            out.append((None, raw))
    return out


def headings(doc):
    body = doc.split("<body", 1)[-1]
    body = re.sub(r"<footer class=\"footer\".*?</footer>", " ", body, flags=re.S)
    body = SCRIPT_STYLE_RE.sub(" ", body)
    return [
        (t.lower(), collapse_ws(strip_tags(x)).rstrip("#").strip())
        for t, x in re.findall(r"<(h[1-6])\b[^>]*>(.*?)</\1>", body, re.S | re.I)
    ]


def article_html(doc):
    """본문 컨테이너. PaperMod 는 `<div class="post-content">` 로 감싼다."""
    m = re.search(r'<div class="post-content[^"]*">(.*?)</article>', doc, re.S)
    if m:
        return m.group(1)
    m = re.search(r'<div class="post-content[^"]*">(.*)', doc, re.S)
    return m.group(1) if m else ""


def links(doc):
    out = []
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", doc, re.S | re.I):
        attrs, text = m.group(1), collapse_ws(strip_tags(m.group(2)))
        href = re.search(r'href=["\'](.*?)["\']', attrs)
        if not href:
            continue
        rel = re.search(r'rel=["\'](.*?)["\']', attrs)
        out.append((html.unescape(href.group(1)).strip(), text, rel.group(1) if rel else ""))
    return out


# ------------------------------------------------------------------ 페이지

class Page(object):
    def __init__(self, path, root):
        self.path = path
        with open(path, encoding="utf-8") as fh:
            self.doc = fh.read()
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        self.url = "/" + re.sub(r"(^|/)index\.html$", r"\1", rel)
        if self.url != "/" and not self.url.endswith("/"):
            self.url = self.url  # 404.html 같은 낱장 파일
        self.section = self.url.strip("/").split("/")[0] if self.url != "/" else ""

    # -- 메타 --------------------------------------------------------------
    @property
    def title(self):
        m = re.search(r"<title>(.*?)</title>", self.doc, re.S | re.I)
        return html.unescape(m.group(1)).strip() if m else ""

    @property
    def title_head(self):
        """사이트명 접미사를 뗀 실제 제목."""
        return self.title.rsplit(" | ", 1)[0].strip()

    @property
    def description(self):
        return meta(self.doc, name="description") or ""

    @property
    def canonical(self):
        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*>', self.doc, re.I)
        if not m:
            return None
        h = re.search(r'href=["\'](.*?)["\']', m.group(0))
        return h.group(1).strip() if h else None

    @property
    def robots(self):
        return (meta(self.doc, name="robots") or "").lower()

    @property
    def noindex(self):
        return "noindex" in self.robots

    @property
    def og_image(self):
        return meta(self.doc, prop="og:image")

    # -- 본문 --------------------------------------------------------------
    @property
    def h1s(self):
        return [t for tag, t in headings(self.doc) if tag == "h1"]

    @property
    def h2s(self):
        return [t for tag, t in headings(self.doc) if tag == "h2"]

    @property
    def body_text(self):
        return collapse_ws(strip_tags(SCRIPT_STYLE_RE.sub(" ", article_html(self.doc))))

    @property
    def char_count(self):
        return len(re.sub(r"\s", "", self.body_text))

    @property
    def lead(self):
        """본문 첫 문단 — 답변엔진이 가장 먼저 자르는 덩어리."""
        for p in re.findall(r"<p\b[^>]*>(.*?)</p>", article_html(self.doc), re.S | re.I):
            t = collapse_ws(strip_tags(p))
            if len(t) >= 20:
                return t
        return ""

    @property
    def jsonld_types(self):
        out = []
        for obj, _ in jsonld_blocks(self.doc):
            if obj is None:
                out.append("!PARSE_ERROR")
            elif isinstance(obj, dict):
                out.append(obj.get("@type", "?"))
        return out

    def jsonld_of(self, typ):
        for obj, _ in jsonld_blocks(self.doc):
            if isinstance(obj, dict) and obj.get("@type") == typ:
                return obj
        return None


# ------------------------------------------------------------------ 크롤

def load_pages(root):
    pages = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".html"):
                p = Page(os.path.join(dirpath, f), root)
                pages[p.url] = p
    return pages


def normalize(href, from_url):
    """사이트 내부 URL 로 정규화. 외부/앵커/메일이면 None."""
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    if href.startswith("//"):
        return None
    if href.startswith("http"):
        if not href.startswith(BASE):
            return None
        href = "/" + href[len(BASE):]
    if not href.startswith("/"):
        href = urllib.parse.urljoin(from_url, href)
    return urllib.parse.unquote(urllib.parse.urlparse(href).path)


def build_graph(pages):
    """내부 링크 그래프. 본문 링크와 크롬(네비·푸터) 링크를 나눠 센다 —
    모든 페이지에 공짜로 붙는 크롬 링크를 함께 세면 고아 페이지가 사라진다."""
    edges = collections.defaultdict(set)          # 전체(도달성 판정용)
    body_in = collections.Counter()               # 본문 인바운드(가치 판정용)
    anchors = collections.defaultdict(list)
    broken = []
    external = collections.Counter()
    for url, pg in pages.items():
        body = article_html(pg.doc)
        body_hrefs = {h for h, _t, _r in links(body)}
        for href, text, _rel in links(pg.doc):
            tgt = normalize(href, url)
            if tgt is None:
                if href.startswith("http") and not href.startswith(BASE):
                    external[urllib.parse.urlparse(href).netloc] += 1
                continue
            if tgt not in pages and not os.path.splitext(tgt)[1]:
                broken.append((url, href, text))
                continue
            if tgt == url:
                continue
            edges[url].add(tgt)
            if href in body_hrefs and tgt in pages:
                body_in[tgt] += 1
                if text:
                    anchors[tgt].append(text)
    return edges, body_in, anchors, broken, external


def depths(edges, start="/"):
    d, q = {start: 0}, collections.deque([start])
    while q:
        u = q.popleft()
        for v in edges.get(u, ()):
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


# ------------------------------------------------------------------ 판정

def sitemap_urls(root):
    p = os.path.join(root, "sitemap.xml")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return re.findall(r"<loc>(.*?)</loc>", fh.read())


def audit(root):
    pages = load_pages(root)
    edges, body_in, anchors, broken, external = build_graph(pages)
    depth = depths(edges)
    sm = [u.replace(BASE, "/") for u in sitemap_urls(root)]
    # `/page/N/` 는 Hugo 페이지네이션 별칭이며 실제 문서가 아니다 — 코퍼스에서 뺀다.
    def _leaf(prefix, u):
        return u.startswith(prefix) and u != prefix and "/page/" not in u

    posts = {u: p for u, p in pages.items() if _leaf("/posts/", u)}
    dicts = {u: p for u, p in pages.items() if _leaf("/dictionary/", u)}
    content = dict(posts)
    content.update(dicts)
    findings = []

    def add(axis, code, sev, msg, items=None):
        findings.append(
            {"axis": axis, "code": code, "severity": sev, "message": msg,
             "count": len(items or []), "items": (items or [])[:40]}
        )

    # -- ① 크롤 가능성 ------------------------------------------------------
    robots = os.path.join(root, "robots.txt")
    rtxt = ""
    if os.path.exists(robots):
        with open(robots, encoding="utf-8") as fh:
            rtxt = fh.read()
    if not rtxt:
        add("crawl", "C1", "high", "robots.txt 없음")
    elif re.search(r"^\s*Disallow:\s*/\s*$", rtxt, re.M):
        add("crawl", "C1", "high", "robots.txt 전체 차단")
    if "Sitemap:" not in rtxt:
        add("crawl", "C2", "high", "robots.txt 에 Sitemap 줄 없음")
    if broken:
        add("crawl", "C3", "high", "깨진 내부 링크",
            ["%s -> %s" % (a, b) for a, b, _ in broken])
    unreach = sorted(u for u in content if u not in depth)
    if unreach:
        add("crawl", "C4", "high", "홈에서 도달 불가", unreach)
    deep = sorted(u for u in content if u in depth and depth[u] >= 4)
    if deep:
        add("crawl", "C5", "med", "클릭 깊이 4 이상", ["%s (d=%d)" % (u, depth[u]) for u in deep])

    # -- ② 색인 ------------------------------------------------------------
    missing_sm = sorted(u for u, p in content.items() if not p.noindex and u not in sm)
    if missing_sm:
        add("index", "I1", "high", "sitemap 누락(색인 가능 페이지)", missing_sm)
    ni = sorted(u for u, p in pages.items() if p.noindex)
    if ni:
        add("index", "I2", "med", "noindex 페이지", ni)
    bad_canon = sorted(
        u for u, p in content.items()
        if p.canonical and p.canonical.rstrip("/") != (BASE.rstrip("/") + u).rstrip("/")
    )
    if bad_canon:
        add("index", "I3", "high", "canonical 자기참조 아님", bad_canon)
    thin = sorted(
        "%s (%d자)" % (u, p.char_count) for u, p in content.items()
        if p.char_count < THIN_PAGE_CHARS
    )
    if thin:
        add("index", "I4", "med", "얇은 페이지(본문 %d자 미만)" % THIN_PAGE_CHARS, thin)

    # -- ③ 페이지 의도 ------------------------------------------------------
    # 뉴스 해설 = 정보형(사건+수치), 사전 = 정의형. 의도와 서술 형태가 어긋나면 낸다.
    intent_bad = []
    for u, p in dicts.items():
        # 정의형 페이지의 리드는 "X는 ~이다" 한 문장으로 끝나야 답변엔진이 뽑는다.
        if not re.search(r"(이란|란|는|은)\s", p.lead[:40]):
            intent_bad.append("%s 리드가 정의문 형태 아님" % u)
    if intent_bad:
        add("intent", "P1", "low", "정의형 페이지 리드 형태", intent_bad)
    q_posts = [u for u, p in posts.items() if "?" in p.title_head]
    add("intent", "P2", "info",
        "의문형 타이틀 포스트 %d/%d" % (len(q_posts), len(posts)), q_posts)

    # -- ④ 타이틀 / 메타 ----------------------------------------------------
    long_t = sorted(
        "%s (%d자) %s" % (u, len(p.title), p.title) for u, p in content.items()
        if len(p.title) > TITLE_MAX_CHARS
    )
    if long_t:
        add("title", "T1", "med", "타이틀 %d자 초과(접미사 포함 잘림)" % TITLE_MAX_CHARS, long_t)
    dup_all = {t: us for t, us in _group((p.title, u) for u, p in pages.items()).items()
               if len(us) > 1}
    dup_real, dup_page = [], []
    for t, us in sorted(dup_all.items()):
        line = "%s :: %s" % (t, ", ".join(sorted(us)))
        # `/page/N/` 사본끼리의 중복은 Hugo 페이지네이션의 기본 동작이다.
        (dup_page if all("/page/" in u for u in us if u not in (min(us, key=len),))
         else dup_real).append(line)
    if dup_real:
        add("title", "T2", "high", "중복 타이틀", dup_real)
    if dup_page:
        add("title", "T2b", "low", "페이지네이션 사본 간 중복 타이틀(Hugo 기본)", dup_page)
    nodesc = sorted(u for u, p in content.items() if not p.description)
    if nodesc:
        add("title", "T3", "high", "description 없음", nodesc)
    baddesc = sorted(
        "%s (%d자)" % (u, len(p.description)) for u, p in content.items()
        if p.description and not (DESC_MIN_CHARS <= len(p.description) <= DESC_MAX_CHARS)
    )
    if baddesc:
        add("title", "T4", "low", "description 길이 %d~%d자 밖" % (DESC_MIN_CHARS, DESC_MAX_CHARS),
            baddesc)
    badh1 = sorted("%s (h1 %d개)" % (u, len(p.h1s)) for u, p in content.items() if len(p.h1s) != 1)
    if badh1:
        add("title", "T5", "high", "h1 이 정확히 1개가 아님", badh1)
    # og:image 가 전 페이지 동일 = 소셜/답변엔진 카드에서 글이 구분되지 않는다.
    ogs = collections.Counter(p.og_image for p in content.values())
    if len(ogs) == 1:
        add("title", "T6", "low",
            "og:image 가 전 페이지 동일(%s) — 페이지별 카드 구분 불가" % list(ogs)[0], [])

    # -- ⑤ 내부 링크 --------------------------------------------------------
    orphan = sorted(u for u in content if body_in[u] == 0)
    if orphan:
        add("links", "L1", "high", "본문 인바운드 0(크롬 링크 제외)", orphan)
    thin_in = sorted(
        "%s (%d)" % (u, body_in[u]) for u in content if 0 < body_in[u] <= 1
    )
    if thin_in:
        add("links", "L2", "low", "본문 인바운드 1건", thin_in)
    generic = sorted(
        "%s <- %r" % (u, a) for u, ts in anchors.items() for a in set(ts)
        if a in ("여기", "링크", "자세히", "더보기", "원문", "click here")
    )
    if generic:
        add("links", "L3", "low", "일반 앵커 텍스트", generic)

    # -- ⑥ 구조화 데이터 ----------------------------------------------------
    parse_err = sorted(u for u, p in pages.items() if "!PARSE_ERROR" in p.jsonld_types)
    if parse_err:
        add("schema", "S1", "high", "JSON-LD 파싱 실패", parse_err)
    no_bp = sorted(u for u, p in posts.items() if not p.jsonld_of("BlogPosting"))
    if no_bp:
        add("schema", "S2", "high", "포스트에 BlogPosting 없음", no_bp)
    no_img = sorted(
        u for u, p in posts.items()
        if (p.jsonld_of("BlogPosting") or {}) and "image" not in (p.jsonld_of("BlogPosting") or {})
    )
    if no_img:
        add("schema", "S3", "med", "BlogPosting 에 image 없음(리치결과 필수 권장)", no_img)
    long_head = sorted(
        "%s (%d자)" % (u, len((p.jsonld_of("BlogPosting") or {}).get("headline", "")))
        for u, p in posts.items()
        if len((p.jsonld_of("BlogPosting") or {}).get("headline", "")) > 110
    )
    if long_head:
        add("schema", "S4", "low", "BlogPosting.headline 110자 초과(구글 무시)", long_head)
    no_faq = sorted(u for u, p in posts.items() if not p.jsonld_of("FAQPage"))
    if no_faq:
        add("schema", "S5", "high",
            "FAQPage 없음 — 답변엔진 추출 단위 부재(%d/%d)" % (len(no_faq), len(posts)), no_faq)
    no_dt = sorted(u for u, p in dicts.items() if not p.jsonld_of("DefinedTerm"))
    if no_dt:
        add("schema", "S6", "high", "사전 항목에 DefinedTerm 없음", no_dt)
    no_bc = sorted(u for u, p in content.items() if not p.jsonld_of("BreadcrumbList"))
    if no_bc:
        add("schema", "S7", "low", "BreadcrumbList 없음", no_bc)
    # 인용 출처를 구조화 데이터로 노출하지 않으면 답변엔진이 근거를 기계적으로 못 읽는다.
    no_cite = sorted(
        u for u, p in posts.items() if "citation" not in (p.jsonld_of("BlogPosting") or {})
    )
    if no_cite:
        add("schema", "S8", "med", "BlogPosting 에 citation/isBasedOn 없음", no_cite)

    # -- ⑦ 출처 인용 --------------------------------------------------------
    nosrc, noprimary = [], []
    for u, p in posts.items():
        ext = [h for h, _t, _r in links(p.doc) if h.startswith("http") and not h.startswith(BASE)]
        if not ext:
            nosrc.append(u)
        if not any(any(ph in h for ph in PRIMARY_HOSTS) for h in ext):
            noprimary.append(u)
    if nosrc:
        add("cite", "R1", "high", "외부 출처 링크 0건", sorted(nosrc))
    if noprimary:
        add("cite", "R2", "med",
            "1차 출처(ECOS·FRED·KOSIS·DART·은행연합회·BIS) 링크 0건 (%d/%d)"
            % (len(noprimary), len(posts)), sorted(noprimary))

    # -- ⑧ 답변 우선 서술 ---------------------------------------------------
    long_lead = sorted(
        "%s (%d자)" % (u, len(p.lead)) for u, p in posts.items()
        if len(p.lead) > ANSWER_LEAD_MAX_CHARS
    )
    if long_lead:
        add("answer", "A1", "med",
            "리드 문단 %d자 초과 — 답이 첫 덩어리에서 끝나지 않음" % ANSWER_LEAD_MAX_CHARS,
            long_lead)
    no_num_lead = sorted(u for u, p in posts.items() if not re.search(r"\d", p.lead))
    if no_num_lead:
        add("answer", "A2", "med", "리드에 수치 없음", no_num_lead)
    # 옛 고정 H2 = 제목의 주제어가 없어 어떤 쿼리에도 대응하지 않는 소제목.
    LEGACY = ("무슨 일이 있었나", "왜 중요한가", "나에게 무슨 의미인가", "투자 관점에서 보면")
    legacy = sorted(
        "%s (%d/4)" % (u, sum(1 for h in p.h2s if h in LEGACY))
        for u, p in posts.items() if any(h in LEGACY for h in p.h2s)
    )
    if legacy:
        add("answer", "A3", "high",
            "옛 고정 H2 사용 — 소제목이 쿼리 대응을 못 함(%d/%d)" % (len(legacy), len(posts)),
            legacy)
    # 리드 직후의 요약 블록(인용문)은 답변엔진이 통째로 인용하기 가장 좋은 단위다.
    no_tldr = sorted(
        u for u, p in posts.items()
        if not re.search(r"<blockquote", article_html(p.doc)[:4000], re.I)
    )
    if no_tldr:
        add("answer", "A6", "med",
            "리드 근처 요약 블록 없음(%d/%d)" % (len(no_tldr), len(posts)), no_tldr)
    no_list = sorted(
        u for u, p in posts.items()
        if "<ul" not in article_html(p.doc) and "<ol" not in article_html(p.doc)
        and "<table" not in article_html(p.doc)
    )
    if no_list:
        add("answer", "A4", "low", "목록/표 없음 — 발췌 단위 부족", no_list)

    # -- llms.txt (GEO 진입점) ----------------------------------------------
    lp = os.path.join(root, "llms.txt")
    if not os.path.exists(lp):
        add("answer", "A5", "med", "llms.txt 없음")
    else:
        with open(lp, encoding="utf-8") as fh:
            ltxt = fh.read()
        listed = set(re.findall(r"https://econ-blog\.github\.io(/[^)\s]*)", ltxt))
        miss = sorted(u for u in content if u not in listed)
        if miss:
            add("answer", "A5", "high",
                "llms.txt 가 전체 코퍼스를 담지 못함 — %d/%d 페이지 누락"
                % (len(miss), len(content)), miss)

    return {
        "root": root,
        "totals": {
            "html_pages": len(pages),
            "posts": len(posts),
            "dictionary": len(dicts),
            "sitemap_locs": len(sm),
            "internal_edges": sum(len(v) for v in edges.values()),
            "external_hosts": len(external),
            "max_depth": max(depth.values()) if depth else 0,
        },
        "findings": findings,
    }


def _group(pairs):
    d = collections.defaultdict(list)
    for k, v in pairs:
        d[k].append(v)
    return d


SEV_ORDER = {"high": 0, "med": 1, "low": 2, "info": 3}


def render(rep):
    t = rep["totals"]
    out = [
        "# SEO/GEO 크롤 감사",
        "",
        "대상: `%s`" % rep["root"],
        "",
        "| 항목 | 값 |",
        "|---|---|",
    ]
    for k, v in t.items():
        out.append("| %s | %s |" % (k, v))
    out += ["", "## 판정", "", "| 축 | 코드 | 심각도 | 건수 | 내용 |", "|---|---|---|---|---|"]
    for f in sorted(rep["findings"], key=lambda x: (SEV_ORDER[x["severity"]], x["axis"])):
        out.append("| %s | %s | %s | %d | %s |"
                   % (f["axis"], f["code"], f["severity"], f["count"], f["message"]))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="hugo 산출 디렉터리")
    ap.add_argument("--json", help="판정 전문을 이 경로에 JSON 으로 쓴다")
    a = ap.parse_args(argv)
    rep = audit(a.root)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=2)
    print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
