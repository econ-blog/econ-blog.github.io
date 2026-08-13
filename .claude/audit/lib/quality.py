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
from contracts import WRITING_STYLES_PATH, count_self_review_items  # noqa: E402
from internal_links import CONTENT_ROOT, TERMS_PATH, load_terms  # noqa: E402
from kstdate import kst_today  # noqa: E402
from mdtext import inventory, split_front_matter, strip_code_spans  # noqa: E402

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
            # posts/와 dictionary/를 함께 훑으므로 파일명만으로는 소견의 '위치'가
            # 되지 못한다 — 같은 슬러그가 양쪽에 존재할 수 있다 (AC #33).
            out.append({
                "file": md.relative_to(content_root).as_posix(),
                "date": m.group(1),
                "age": age,
            })
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


HANGUL_TOKEN = re.compile(r"[가-힣]{2,10}|[A-Z]{2,6}")

STOPWORDS = {
    "그리고", "하지만", "그러나", "때문에", "이라고", "합니다", "입니다", "있습니다",
    "없습니다", "됩니다", "습니다", "경우에", "우리나라", "이번에", "지난해", "올해",
    "다음과", "이라는", "라는", "정도로", "만큼", "가운데", "사람들", "이야기",
    "무슨", "의미", "관점", "지표", "상황", "영향", "수준", "가능성", "이유",
}

JOSA_SUFFIXES = ("에서", "으로", "보다", "에게", "부터", "까지", "인가", "이다", "가", "을", "를", "의", "은", "는", "이", "에", "로", "도", "와", "과")


def trim_josa(tok: str) -> str:
    """한국어 조사 접미사를 잘라내어 동일 명사의 격변화를 통합한다."""
    if len(tok) <= 2:
        return tok
    for j in JOSA_SUFFIXES:
        if tok.endswith(j) and len(tok) - len(j) >= 2:
            return tok[:-len(j)]
    return tok


def term_candidates(
    content_root: Path, terms: dict, min_posts: int = 2, min_count: int = 3
) -> list[dict]:
    """Q3 — 반복 등장하지만 _terms.yaml에 없는 토큰의 결정론적 빈도표.

    경제 용어인지는 판정하지 않는다 — 그 선별은 스테이지의 LLM이 하며 재현되지
    않는다. 형태소 분석기 대신 조사 접미사 제거(trim_josa)로 체언을 정규화한다.
    """
    known = set()
    for t in terms.values():
        known.add(t["title"])
        known.update(t["aliases"])
        # 괄호 표기 변형("코픽스(COFIX)")의 앞부분도 등재로 간주
        known.add(t["title"].split("(")[0].strip())

    doc_hits: dict = {}
    total: dict = {}
    for md in sorted((content_root / "posts").glob("*.md")):
        if md.name.startswith("_"):
            continue
        _, body = split_front_matter(md.read_text(encoding="utf-8"))
        seen_here = set()
        for raw_tok in HANGUL_TOKEN.findall(strip_code_spans(body)):
            tok = trim_josa(raw_tok)
            if tok in known or tok in STOPWORDS:
                continue
            total[tok] = total.get(tok, 0) + 1
            seen_here.add(tok)
        for tok in seen_here:
            doc_hits[tok] = doc_hits.get(tok, 0) + 1

    out = [
        {"token": tok, "posts": doc_hits[tok], "count": total[tok]}
        for tok in total
        if doc_hits[tok] >= min_posts and total[tok] >= min_count
    ]
    out.sort(key=lambda x: (-x["count"], -x["posts"], x["token"]))
    return out


if __name__ == "__main__":
    today = sys.argv[1] if len(sys.argv) > 1 else kst_today()
    terms = load_terms(TERMS_PATH.read_text(encoding="utf-8"))
    files = sorted((CONTENT_ROOT / "posts").glob("*.md")) + \
        sorted((CONTENT_ROOT / "dictionary").glob("*.md"))
    ws = WRITING_STYLES_PATH.read_text(encoding="utf-8")
    print(json.dumps({
        "Q1": [
            {
                "file": p.relative_to(CONTENT_ROOT).as_posix(),
                "issues": front_matter_issues(p),
            }
            for p in files
            if not p.name.startswith("_") and front_matter_issues(p)
        ],
        "Q3": term_candidates(CONTENT_ROOT, terms)[:30],
        "Q4": stale_drafts(CONTENT_ROOT, today),
        "Q5": self_review_budget(ws),
        "P2": internal_link_density(CONTENT_ROOT),
    }, ensure_ascii=False, indent=2))


