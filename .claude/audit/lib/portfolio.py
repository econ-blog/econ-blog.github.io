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
