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


