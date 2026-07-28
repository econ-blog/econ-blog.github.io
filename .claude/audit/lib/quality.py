"""포스트 품질·내부 순환 축 (Q1·Q3·Q4·Q5·P2).

결정론적. stdlib + 정규식만. 어떤 파일도 수정하지 않는다 — ④는 읽기 전용이다(AC #34).
Q2(미연결 용어)는 backfill.py가 같은 계산을 이미 하므로 재구현하지 않고 재사용한다.

사용:
    .venv/bin/python .claude/audit/lib/quality.py   # 전체 축 JSON
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import count_self_review_items  # noqa: E402
from mdtext import inventory, split_front_matter  # noqa: E402

DESC_MIN, DESC_MAX = 50, 160

FIELD = {
    "title": re.compile(r"^title:\s*\S", re.MULTILINE),
    "date": re.compile(r"^date:\s*\S", re.MULTILINE),
    "tags": re.compile(r"^tags:\s*\[", re.MULTILINE),
    "draft": re.compile(r"^draft:\s*(true|false)\s*$", re.MULTILINE),
    "source_url": re.compile(r"^source_url:\s*\S", re.MULTILINE),
}
DESCRIPTION = re.compile(r'^description:\s*"?(.*?)"?\s*$', re.MULTILINE)
NOTICE_TAG = re.compile(r'^tags:\s*\[[^\]]*"공지"', re.MULTILINE)


def _required(path: Path, front: str) -> list[str]:
    """파일 유형별 필수 필드. 공지는 source_url·description 면제(원문이 없다)."""
    base = ["title", "date", "tags", "draft"]
    if NOTICE_TAG.search(front):
        return base
    if path.parent.name == "dictionary":
        return base + ["description"]
    return base + ["source_url", "description"]


def front_matter_issues(path: Path) -> list[str]:
    """Q1 — front matter 완비 + description 길이."""
    front, _ = split_front_matter(path.read_text(encoding="utf-8"))
    if not front:
        return ["front matter 없음"]
    required = _required(path, front)
    out = []
    for name in required:
        if name == "description":
            m = DESCRIPTION.search(front)
            if not m or not m.group(1).strip():
                out.append("description 누락")
                continue
            n = len(m.group(1).strip())
            if not (DESC_MIN <= n <= DESC_MAX):
                out.append(f"description 길이 {n}자 (권장 {DESC_MIN}~{DESC_MAX})")
            continue
        if not FIELD[name].search(front):
            out.append(f"{name} 누락")
    return out


DRAFT_TRUE = re.compile(r"^draft:\s*true\s*$", re.MULTILINE)
DATE_ONLY = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def stale_drafts(content_root: Path, today: str, days: int = 7) -> list[dict]:
    """Q4 — draft: true로 days일 이상 방치된 파일."""
    out = []
    for md in sorted(content_root.rglob("*.md")):
        if md.name.startswith("_"):
            continue
        front, _ = split_front_matter(md.read_text(encoding="utf-8"))
        if not DRAFT_TRUE.search(front):
            continue
        m = DATE_ONLY.search(front)
        if not m:
            continue
        age = (date.fromisoformat(today) - date.fromisoformat(m.group(1))).days
        if age >= days:
            out.append({"file": md.name, "date": m.group(1), "age": age})
    return out


def self_review_budget(writing_styles_text: str, budget: int = 12) -> dict:
    """Q5 — 자가검토 항목 수와 예산 잔량. 개수만 센다(내용은 loop 소유)."""
    n = count_self_review_items(writing_styles_text)
    return {"count": n, "budget": budget, "remaining": budget - n}


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    mid = len(s) // 2
    return float(s[mid]) if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def internal_link_density(content_root: Path) -> dict:
    """P2 — 포스트당 내부 링크 수. 체류시간은 pre-AdSense 유일 신호이므로 별도로 본다."""
    per = []
    for md in sorted((content_root / "posts").glob("*.md")):
        if md.name.startswith("_"):
            continue
        inv = inventory(md.read_text(encoding="utf-8"))
        per.append({"file": md.name, "internal_links": len(inv["internal"])})
    counts = [float(x["internal_links"]) for x in per]
    return {
        "per_post": per,
        "median": _median(counts),
        "zero_link_posts": [x["file"] for x in per if x["internal_links"] == 0],
    }


if __name__ == "__main__":
    pass

