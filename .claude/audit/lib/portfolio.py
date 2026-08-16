"""⑤ 방향성 — 포트폴리오 축 D1–D6. (SEED AC #44)

순수·결정론. content/ · topics.yaml · hugo.toml · public/ 만 읽고 네트워크를
쓰지 않는다. 표준 라이브러리 + 정규식만 — AST/HTML 파서를 도입하지 않는다.

  .venv/bin/python .claude/audit/lib/portfolio.py
"""
import os
import re
import sys
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import documents, is_notice  # noqa: E402
from internal_links import load_terms  # noqa: E402
from kstdate import kst_today  # noqa: E402
from mdtext import MD_LINK, strip_code_spans  # noqa: E402

EVERGREEN_RULE = (
    "사전 항목은 전부 상록. 포스트는 front matter에 source_url이 있으면 시의성, "
    "없으면 상록. 분모는 content/posts + content/dictionary의 발행글(공지·초안 제외)이며 "
    "content/ 루트의 정책 페이지(about·contact·privacy)는 포함하지 않는다."
)


def _median(values: list[int]) -> int | float:
    """진짜 중앙값 — 짝수 개면 가운데 두 값의 평균. 정수로 떨어지면 int로 돌려준다.

    상위 원소를 그대로 쓰면(s[n // 2]) 짝수 코퍼스에서 값이 위로 치우치고 문서
    한 건이 늘 때마다 계단식으로 뛴다. D1 중앙값과 D3 유입 중앙값은 감사 간
    대조 대상(스냅샷 키)이므로 그 편향을 남겨 두지 않는다.
    """
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    mid = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return int(mid) if float(mid).is_integer() else mid


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
    evergreen_files = {d["file"] for d in evergreen}
    timely = [d for d in live if d["file"] not in evergreen_files]

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


TRAILING_COMMENT = re.compile(r"\s+#.*$")


def load_vocab(text: str) -> list[str]:
    """topics.yaml의 최상위 태그를 파일 순서대로. (AC #44 D2)

    PyYAML을 쓰지 않는다 — internal_links.load_terms와 같은 규약(정규식 파싱)이다.
    최상위 키는 들여쓰기가 없고 콜론으로 끝나는 줄이다.

    줄 끝 주석(`금리:  # 설명`)을 먼저 떼어 낸다 — 떼지 않으면 그 줄이 콜론으로
    끝나지 않아 어휘에서 **조용히** 빠지고, D2의 분모가 소리 없이 줄어든다.
    """
    out = []
    for line in text.splitlines():
        if not line or line.startswith(("#", " ", "\t")):
            continue
        stripped = TRAILING_COMMENT.sub("", line).rstrip()
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
# 정규식 하나로 둘 다 잡는다 (쌍따옴표·홑따옴표·따옴표없음). HTML 파서를 도입하지 않는다(Constraints).
# (?<![-\w])는 data-href= 같은 접미 속성이 href로 잡히는 것을 막는다.
HTML_HREF = re.compile(
    r'(?<![-\w])href=(?:"(?P<q>[^"]*)"|\'(?P<s>[^\']*)\'|(?P<b>[^\s>"]+))'
)
BACKLINK_BLOCK = re.compile(r"related-posts-list(?P<inner>.*?)</ul>", re.S)

# 슬러그 한 칸을 반드시 요구한다. `/dictionary/`·`/posts/`(섹션 목록)는 제외 —
# 그 둘은 PaperMod 상단 내비게이션이 **모든 페이지에** 넣는 링크다.
POST_PAGE_HREF = re.compile(r"\A/posts/[^/]+/\Z")
CONTENT_PAGE_HREF = re.compile(r"\A/(?:posts|dictionary)/[^/]+/\Z")


def _pick(m: re.Match | None) -> str:
    """따옴표 세 형태(쌍·홑·없음) 중 실제로 매치된 그룹의 값."""
    if m is None:
        return ""
    for g in m.groups():
        if g is not None:
            return g
    return ""


def _html_hrefs(html: str) -> list[str]:
    return [_pick(m) for m in HTML_HREF.finditer(html)]


def d3_render_side(public_root: Path, terms: dict) -> dict:
    """D3의 렌더 기준 절반 — 백링크 수와 막다른 항목. (AC #44 D3)

    막다름은 원문이 아니라 빌드 산출물로 판정한다 —
    layouts/partials/dictionary_backlinks.html이 사전→포스트 간선을 렌더 시점에
    만들기 때문에, 원문만 세면 partial이 이미 해결한 문제를 오탐으로 낸다.

    순회 대상은 terms의 슬러그다. public/dictionary/를 iterdir()하면
    page/ 페이지네이션 디렉터리가 섞인다.

    **나가는 링크는 슬러그가 있는 개별 페이지만 센다.** PaperMod 상단
    내비게이션이 모든 페이지에 `/dictionary/`(섹션 목록)를 넣으므로, 접두사만
    보면 outgoing이 절대 비지 않고 dead_ends가 영원히 빈 목록이 된다 —
    값이 0인 것과 판정이 죽은 것을 구분할 수 없게 되는 AC #28 I1 계열의 함정이다.
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
            len([h for h in _html_hrefs(block.group("inner"))
                 if POST_PAGE_HREF.match(h)])
            if block
            else 0
        )
        outgoing = [
            h
            for h in _html_hrefs(html)
            if CONTENT_PAGE_HREF.match(h) and h != f"/dictionary/{slug}/"
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
    "kfb.or.kr",
)

# 속성 순서를 가정하지 않는다 — <meta> 태그를 먼저 잡고 그 안에서 속성을 읽는다.
# minify는 content=""를 content로 줄인다: <meta name=author content>
META_TAG = re.compile(r"<meta\s(?P<attrs>[^>]*)>", re.I)
ATTR_NAME = re.compile(r"""(?<![-\w])name=(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""", re.I)
ATTR_CONTENT = re.compile(
    r"""(?<![-\w])content=(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""", re.I
)
LDJSON = re.compile(
    r"<script[^>]*application/ld\+json[^>]*>(?P<body>.*?)</script>",
    re.S | re.I,
)
URL_HOST = re.compile(r"https?://(?P<host>[^/\s)\"']+)")


def _is_primary_source(host: str) -> bool:
    """호스트 일치는 접미 일치다 — www.kosis.kr·서브도메인을 놓치지 않는다.

    정확 일치만 보면 정당한 1차 출처 링크가 0건으로 집계되고, "포스트당 1차
    출처 링크 0건"이 승격 조건이므로 글쓴이가 해소할 수 없는 소견이 매주 뜬다.
    포트는 떼고 비교한다.
    """
    h = host.split(":")[0].lower()
    return any(h == p or h.endswith("." + p) for p in PRIMARY_SOURCE_HOSTS)


def _hugo_author_set(hugo_toml: str) -> bool:
    return bool(re.search(r"^\s*author\s*=", hugo_toml, re.M))


def _meta_author(html: str) -> tuple[bool, bool]:
    """(태그 존재, 값이 비어 있지 않음). AC #44 D4(b)는 존재가 아니라 값을 묻는다."""
    for m in META_TAG.finditer(html):
        attrs = m.group("attrs")
        nm = ATTR_NAME.search(attrs)
        if not nm or _pick(nm).strip().lower() != "author":
            continue
        return True, bool(_pick(ATTR_CONTENT.search(attrs)).strip())
    return False, False


def _post_pages(public_root: Path) -> list[Path]:
    return sorted((public_root / "posts").glob("*/index.html"))


def d4_eeat(
    docs: list[dict], content_root: Path, hugo_toml: str, public_root: Path
) -> dict:
    """D4 E-E-A-T 표면. 경제·금융은 YMYL이라 별도 축으로 둔다. (AC #44 D4)

    (b)는 빌드 산출물에서 본다 — 테마가 무엇을 방출하는지는 템플릿을 읽어서가
    아니라 public/을 봐야 알 수 있다. PaperMod는 BlogPosting을 이미 방출하며
    실제 공백은 author 하나다.

    **표본 한 장이 아니라 발행된 포스트 페이지 전부를 본다.** 축은 템플릿
    속성이라 보통 전 페이지가 같지만, 레이아웃 override로 한 장만 어긋나는
    경우를 표본 추출로는 영영 볼 수 없다. 불리언 키는 **전 페이지가 충족할
    때만** True이며(한 장이라도 어긋나면 소견으로 승격된다), 몇 장 중 몇 장인지는
    `*_pages` 카운트로 함께 낸다.
    """
    per_file, by_section = {}, {"posts": 0, "dictionary": 0}
    for d in docs:
        if d["draft"] or is_notice(d):
            continue
        hosts = URL_HOST.findall(strip_code_spans(d["body"]))
        n = sum(1 for h in hosts if _is_primary_source(h))
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

    pages = _post_pages(public_root)
    if not pages:
        result.update(
            {"built": False, "meta_author": None, "jsonld_blogposting": None}
        )
        return result

    tag_pages = value_pages = present_pages = author_pages = 0
    blocks_on_sample = 0
    for i, page in enumerate(pages):
        html = page.read_text(encoding="utf-8")
        has_tag, has_value = _meta_author(html)
        tag_pages += has_tag
        value_pages += has_value

        blocks = [m.group("body") for m in LDJSON.finditer(html)]
        if i == 0:
            blocks_on_sample = len(blocks)
        blogposting = next((b for b in blocks if '"BlogPosting"' in b), None)
        present_pages += blogposting is not None
        author_pages += blogposting is not None and '"author"' in blogposting

    n = len(pages)
    result.update(
        {
            "built": True,
            "meta_author": {
                "tag": tag_pages == n,
                "value_nonempty": value_pages == n,
                "pages": n,
                "tag_pages": tag_pages,
                "value_nonempty_pages": value_pages,
                "sample": str(pages[0]),
            },
            "jsonld_blogposting": {
                "present": present_pages == n,
                "author_key": author_pages == n,
                "pages": n,
                "present_pages": present_pages,
                "author_key_pages": author_pages,
                "blocks": blocks_on_sample,
            },
        }
    )
    return result


POST_SLOTS = ("## 나에게 무슨 의미인가", "## 투자 관점에서 보면")
DICT_SLOTS = ("## 실생활에서는", "## 투자에서는")

# 포스트 H2는 2026-08-10 제목 규율(`headings.py` T2·`draft.md` §1)로 **주제 특화
# 문구**가 됐다. 그 뒤에 쓰인 글은 `## 투자 관점에서 보면` 대신 `## 물가 국면에서
# 자산군이 갈리는 지점` 같은 제목을 쓴다 — 옛 고정 문구를 쓰는 것이 이제 위반이다.
# 그래서 문자열로만 찾으면 **규칙을 지킨 글일수록 D6에서 떨어지고**, 충족률은
# 발행할수록 0을 향해 내려간다. 2026-08-16 감사 ⑤ 소견 2(22/24)가 그 첫 두 건이다.
#
# 슬롯을 **구조로도** 인정해 이 모순을 닫는다: draft.md가 고정한 4단 구성이면
# 3번째·4번째 H2가 각각 생활 경로·투자 관점 자리다. 옛 글은 문자열이 그대로 남아
# 있어 어느 쪽으로든 통과하므로 소급 수정이 필요 없다. 사전 슬롯은 고정 문자열
# 그대로다 — 제목 규율은 포스트에만 적용된다.
POST_SECTION_COUNT = 4
POST_H2 = re.compile(r"^##[ \t]+.+$", re.MULTILINE)


def _slot_met(section: str, slot: str, body: str) -> bool:
    """슬롯이 채워졌는가. 포스트는 고정 문자열 또는 4단 구성 중 하나면 충족."""
    if slot in body:
        return True
    return section == "posts" and len(POST_H2.findall(body)) == POST_SECTION_COUNT


def _days_between(start: str, end: str) -> int:
    try:
        return (_date.fromisoformat(end) - _date.fromisoformat(start)).days
    except (ValueError, TypeError):
        return 0


def d5_decay(docs: list[dict], today: str) -> dict:
    """D5 감쇄 노출 — 시의성 글 중 90일 경과 비율. D < 90이면 항상 0이 정상. (AC #44 D5)

    `corpus_age`는 **사전을 포함한** 코퍼스 전체의 최고령 문서 기준이며,
    ②③ 게이트가 쓰는 `corpus.site_age`(포스트만, welcome.md 제외)와 분모가
    다르다. 두 값이 같은 리포트에 다른 뜻으로 실리지 않도록 이름을 분리한다.
    """
    live = [d for d in docs if not d["draft"] and not is_notice(d)]
    timely = [
        d
        for d in live
        if d["section"] == "posts" and d["has_source_url"] and d["date"]
    ]
    aged = [d for d in timely if _days_between(d["date"], today) >= 90]
    dates = [d["date"] for d in live if d["date"]]
    return {
        "corpus_age": _days_between(min(dates), today) if dates else 0,
        "timely_total": len(timely),
        "aged_90": len(aged),
        "ratio": _ratio(len(aged), len(timely)),
        "aged_files": sorted(d["file"] for d in aged),
    }


def d6_slots(docs: list[dict]) -> dict:
    """D6 차별점 슬롯 충족률. 슬롯의 존재만 본다 — 내용의 품질은 판정하지 않는다. (AC #44 D6)

    포스트는 고정 문자열과 4단 구성 둘 중 하나면 충족이다. 근거는 `_slot_met` 위 주석.
    """
    out = {}
    for section, slots in (("posts", POST_SLOTS), ("dictionary", DICT_SLOTS)):
        group = [
            d
            for d in docs
            if d["section"] == section and not d["draft"] and not is_notice(d)
        ]
        out[section] = {}
        for slot in slots:
            missing = sorted(
                d["file"] for d in group if not _slot_met(section, slot, d["body"])
            )
            out[section][slot] = {
                "met": len(group) - len(missing),
                "total": len(group),
                "missing": missing,
            }
    out["all_met"] = all(
        not s["missing"]
        for section in ("posts", "dictionary")
        for s in out[section].values()
    )
    return out


SNAPSHOT_KEYS = (
    "d1_evergreen_mass_ratio",
    "d2_vocab_used",
    "d3_links_per_post_median",
    "d3_self_reference",
    "d3_dead_ends",
    "d4_primary_source_links",
    "d5_aged_ratio",
    "d6_all_met",
)


def snapshot(axes: dict) -> dict:
    """D1–D6 결과에서 원장 스냅샷 8개 키를 뽑는다. (AC #45)

    스테이지가 손으로 옮겨 적지 않게 하려는 함수다 — 손으로 적으면 표의 행과
    스냅샷 키가 조용히 어긋나고, 다음 감사의 "변화" 열이 엉뚱한 것을 비교한다.
    ⑥의 세 값(n1_count·claims_total·claims_per_post)은 여기서 만들지 않는다.
    시퀀서가 hypothesis.py record에 넘기며, 없으면 **키 자체를 생략**한다.
    """
    return {
        "d1_evergreen_mass_ratio": axes["D1"]["mass"]["evergreen_ratio"],
        "d2_vocab_used": axes["D2"]["used"],
        "d3_links_per_post_median": axes["D3_source"]["links_per_post"]["median"],
        "d3_self_reference": len(axes["D3_source"]["self_reference"]),
        "d3_dead_ends": (
            len(axes["D3_render"]["dead_ends"])
            if axes["D3_render"]["built"]
            else None
        ),
        "d4_primary_source_links": axes["D4"]["primary_source_links"]["total"],
        "d5_aged_ratio": axes["D5"]["ratio"],
        "d6_all_met": axes["D6"]["all_met"],
    }


def main() -> None:
    """D1–D6을 한 JSON으로. 스테이지는 이 출력만 소비한다. (AC #45)"""
    import json

    content = Path("content")
    docs = documents(content)
    vocab = load_vocab(
        Path(".claude/daily-post/topics.yaml").read_text(encoding="utf-8")
    )
    terms = load_terms(
        Path("content/dictionary/_terms.yaml").read_text(encoding="utf-8")
    )
    public = Path("public")

    today = kst_today()
    axes = {
        "D1": d1_composition(docs),
        "D2": d2_vocabulary(docs, vocab),
        "D3_source": d3_source_side(docs, terms),
        "D3_render": d3_render_side(public, terms),
        "D4": d4_eeat(
            docs,
            content,
            Path("hugo.toml").read_text(encoding="utf-8"),
            public,
        ),
        "D5": d5_decay(docs, today),
        "D6": d6_slots(docs),
    }
    print(
        json.dumps(
            {
                "generated": today,
                "evergreen_rule": EVERGREEN_RULE,
                **axes,
                "snapshot": snapshot(axes),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
