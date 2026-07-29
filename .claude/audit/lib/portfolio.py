"""⑤ 방향성 — 포트폴리오 축 D1–D6. (SEED AC #44)

순수·결정론. content/ · topics.yaml · hugo.toml · public/ 만 읽고 네트워크를
쓰지 않는다. 표준 라이브러리 + 정규식만 — AST/HTML 파서를 도입하지 않는다.

  .venv/bin/python .claude/audit/lib/portfolio.py
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import documents, is_notice  # noqa: E402
from mdtext import MD_LINK, strip_code_spans  # noqa: E402

EVERGREEN_RULE = (
    "사전 항목은 전부 상록. 포스트는 front matter에 source_url이 있으면 시의성, "
    "없으면 상록. 분모는 content/posts + content/dictionary의 발행글(공지·초안 제외)이며 "
    "content/ 루트의 정책 페이지(about·contact·privacy)는 포함하지 않는다."
)


def _median(values: list[int]) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[len(s) // 2]


def _ratio(part: int, whole: int) -> float:
    if not whole:
        return 0.0
    return round(part / whole, 4)


def d1_composition(docs: list[dict]) -> dict:
    """D1 상록/시의성 구성. 판정은 질량, 문서 수는 참고로 병기. (AC #44 D1)"""
    live = [d for d in docs if not d["draft"] and not is_notice(d)]
    evergreen = [
        d
        for d in live
        if d["section"] == "dictionary" or not d["has_source_url"]
    ]
    timely = [d for d in live if d not in evergreen]

    mass_e = sum(d["chars"] for d in evergreen)
    mass_t = sum(d["chars"] for d in timely)
    return {
        "mass": {
            "evergreen": mass_e,
            "timely": mass_t,
            "total": mass_e + mass_t,
            "evergreen_ratio": _ratio(mass_e, mass_e + mass_t),
        },
        "doc_count": {
            "evergreen": len(evergreen),
            "timely": len(timely),
            "total": len(live),
            "evergreen_ratio": _ratio(len(evergreen), len(live)),
        },
        "median_chars": {
            "posts": _median(
                [d["chars"] for d in live if d["section"] == "posts"]
            ),
            "dictionary": _median(
                [d["chars"] for d in live if d["section"] == "dictionary"]
            ),
        },
        "denominator": "content/posts + content/dictionary (공지·초안 제외)",
    }


def load_vocab(text: str) -> list[str]:
    """topics.yaml의 최상위 태그를 파일 순서대로. (AC #44 D2)

    PyYAML을 쓰지 않는다 — internal_links.load_terms와 같은 규약(정규식 파싱)이다.
    최상위 키는 들여쓰기가 없고 콜론으로 끝나는 줄이다.
    """
    out = []
    for line in text.splitlines():
        if not line or line.startswith(("#", " ", "\t")):
            continue
        stripped = line.rstrip()
        if stripped.endswith(":"):
            out.append(stripped[:-1].strip())
    return out


def d2_vocabulary(docs: list[dict], vocab: list[str]) -> dict:
    """D2 통제 어휘 소진. 미사용 태그는 관측치이며 소견이 아니다. (AC #44 D2)"""
    counts = {tag: 0 for tag in vocab}
    outside = set()
    total = 0
    for d in docs:
        if d["section"] != "posts" or d["draft"] or is_notice(d):
            continue
        for tag in d["tags"]:
            total += 1
            if tag in counts:
                counts[tag] += 1
            else:
                outside.add(tag)
    used = [v for v in counts.values() if v]
    return {
        "counts": counts,
        "used": len(used),
        "unused": [t for t, v in counts.items() if not v],
        "outside": sorted(outside),
        "max_min_ratio": round(max(used) / min(used), 2) if used else None,
        "total_tag_uses": total,
    }


DICT_HREF = re.compile(r"\A/dictionary/([^/]+)/\Z")
HEADING = re.compile(r"^#{2,}\s", re.M)


def _internal_targets(body: str) -> list[str]:
    """본문의 내부 링크 대상. 코드 스팬은 먼저 제거한다. (AC #5·#6 재사용)"""
    return [
        m.group(2)
        for m in MD_LINK.finditer(strip_code_spans(body))
        if m.group(2).startswith("/")
    ]


def d3_source_side(docs: list[dict], terms: dict) -> dict:
    """D3의 원문 기준 절반 — 유입·본문유출·자기참조·구조. (AC #44 D3)

    렌더 기준 백링크와 막다름은 d3_render_side가 별도로 센다. 원문만 세면
    dictionary_backlinks.html이 이미 해결한 문제를 오탐으로 보고하게 된다.
    """
    inbound = {slug: 0 for slug in terms}
    per_post = []
    for d in docs:
        if d["section"] != "posts" or d["draft"]:
            continue
        n = 0
        for href in _internal_targets(d["body"]):
            m = DICT_HREF.match(href)
            if not m:
                continue
            n += 1
            if m.group(1) in inbound:
                inbound[m.group(1)] += 1
        if not is_notice(d):
            per_post.append(n)

    body_outbound, self_ref, headings = {}, [], {}
    for d in docs:
        if d["section"] != "dictionary" or d["draft"]:
            continue
        slug = d["slug"]
        targets = _internal_targets(d["body"])
        own = f"/dictionary/{slug}/"
        if own in targets:
            self_ref.append(slug)
        body_outbound[slug] = len([t for t in targets if t != own])
        headings[slug] = len(HEADING.findall(d["body"]))

    return {
        "inbound": inbound,
        "orphans": sorted(s for s, v in inbound.items() if not v),
        "links_per_post": {"values": sorted(per_post), "median": _median(per_post)},
        "body_outbound": body_outbound,
        "body_outbound_zero": sorted(s for s, v in body_outbound.items() if not v),
        "self_reference": sorted(self_ref),
        "headings": headings,
    }


# --minify가 값에 공백이 없는 속성의 인용부호를 벗긴다: href="/x/" → href=/x/
# 정규식 하나로 둘 다 잡는다. HTML 파서를 도입하지 않는다(Constraints).
HTML_HREF = re.compile(r'href=(?:"(?P<q>[^"]*)"|(?P<b>[^\s>"]+))')
BACKLINK_BLOCK = re.compile(r"related-posts-list(?P<inner>.*?)</ul>", re.S)


def _html_hrefs(html: str) -> list[str]:
    return [
        m.group("q") if m.group("q") is not None else m.group("b")
        for m in HTML_HREF.finditer(html)
    ]


def d3_render_side(public_root: Path, terms: dict) -> dict:
    """D3의 렌더 기준 절반 — 백링크 수와 막다른 항목. (AC #44 D3)

    막다름은 원문이 아니라 빌드 산출물로 판정한다 —
    layouts/partials/dictionary_backlinks.html이 사전→포스트 간선을 렌더 시점에
    만들기 때문에, 원문만 세면 partial이 이미 해결한 문제를 오탐으로 낸다.

    순회 대상은 terms의 슬러그다. public/dictionary/를 iterdir()하면
    page/ 페이지네이션 디렉터리가 섞인다.
    """
    backlinks, missing, dead_ends = {}, [], []
    built = False
    for slug in terms:
        page = public_root / "dictionary" / slug / "index.html"
        if not page.is_file():
            backlinks[slug] = None
            missing.append(slug)
            continue
        built = True
        html = page.read_text(encoding="utf-8")
        block = BACKLINK_BLOCK.search(html)
        backlinks[slug] = (
            len([h for h in _html_hrefs(block.group("inner")) if h.startswith("/posts/")])
            if block
            else 0
        )
        outgoing = [
            h
            for h in _html_hrefs(html)
            if h.startswith(("/posts/", "/dictionary/")) and h != f"/dictionary/{slug}/"
        ]
        if not outgoing:
            dead_ends.append(slug)

    if not built:
        return {
            "built": False,
            "backlinks": {},
            "dead_ends": [],
            "missing_pages": sorted(terms),
            "backlink_cap": 8,
        }
    return {
        "built": True,
        "backlinks": backlinks,
        "dead_ends": sorted(dead_ends),
        "missing_pages": sorted(missing),
        "backlink_cap": 8,
    }


PRIMARY_SOURCE_HOSTS = (
    "ecos.bok.or.kr",
    "fred.stlouisfed.org",
    "dart.fss.or.kr",
    "kosis.kr",
    "bok.or.kr",
)

# minify는 content=""를 content로 줄인다: <meta name=author content>
META_AUTHOR = re.compile(
    r'<meta\s+name=(?:"author"|author)(?P<rest>[^>]*)>', re.I
)
META_AUTHOR_VALUE = re.compile(r'content=(?:"(?P<q>[^"]*)"|(?P<b>[^\s>"]+))')
LDJSON = re.compile(
    r"<script[^>]*application/ld\+json[^>]*>(?P<body>.*?)</script>",
    re.S | re.I,
)
URL_HOST = re.compile(r"https?://(?P<host>[^/\s)\"']+)")


def _hugo_author_set(hugo_toml: str) -> bool:
    return bool(re.search(r"^\s*author\s*=", hugo_toml, re.M))


def _sample_post_html(public_root: Path) -> tuple[Path | None, str]:
    pages = sorted((public_root / "posts").glob("*/index.html"))
    if not pages:
        return None, ""
    return pages[0], pages[0].read_text(encoding="utf-8")


def d4_eeat(
    docs: list[dict], content_root: Path, hugo_toml: str, public_root: Path
) -> dict:
    """D4 E-E-A-T 표면. 경제·금융은 YMYL이라 별도 축으로 둔다. (AC #44 D4)

    (b)는 빌드 산출물에서 본다 — 테마가 무엇을 방출하는지는 템플릿을 읽어서가
    아니라 public/을 봐야 알 수 있다. PaperMod는 BlogPosting을 이미 방출하며
    실제 공백은 author 하나다.
    """
    per_file, by_section = {}, {"posts": 0, "dictionary": 0}
    for d in docs:
        if d["draft"] or is_notice(d):
            continue
        hosts = URL_HOST.findall(strip_code_spans(d["body"]))
        n = sum(1 for h in hosts if h in PRIMARY_SOURCE_HOSTS)
        per_file[d["file"]] = n
        by_section[d["section"]] += n

    result = {
        "hugo_author": _hugo_author_set(hugo_toml),
        "policy_pages": {
            name: (content_root / f"{name}.md").is_file()
            for name in ("about", "contact", "privacy")
        },
        "primary_source_links": {
            "total": by_section["posts"] + by_section["dictionary"],
            "posts": by_section["posts"],
            "dictionary": by_section["dictionary"],
            "per_file": per_file,
        },
    }

    sample, html = _sample_post_html(public_root)
    if sample is None:
        result.update(
            {"built": False, "meta_author": None, "jsonld_blogposting": None}
        )
        return result

    tag = META_AUTHOR.search(html)
    value = ""
    if tag:
        vm = META_AUTHOR_VALUE.search(tag.group("rest"))
        if vm:
            value = (
                vm.group("q") if vm.group("q") is not None else vm.group("b")
            ) or ""

    blocks = [m.group("body") for m in LDJSON.finditer(html)]
    blogposting = next((b for b in blocks if '"BlogPosting"' in b), None)

    result.update(
        {
            "built": True,
            "meta_author": {
                "tag": bool(tag),
                "value_nonempty": bool(value.strip()),
                "sample": str(sample),
            },
            "jsonld_blogposting": {
                "present": blogposting is not None,
                "author_key": bool(blogposting) and '"author"' in blogposting,
                "blocks": len(blocks),
            },
        }
    )
    return result




