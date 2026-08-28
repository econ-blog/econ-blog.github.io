"""코퍼스 통계 — 발행글 수·사이트 연령. content/만으로 결정론적 계산.

②③ 게이트 stub 한 줄에 쓰이고, 이후 ⑤ D5(감쇄 노출)가 재사용한다.
네트워크·트래픽 API를 쓰지 않는다.

사용:
    .venv/bin/python .claude/audit/lib/corpus.py   # gate_stats JSON
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

from kstdate import kst_today
from mdtext import split_front_matter, strip_code_spans

DRAFT = re.compile(r"^draft:\s*(true|false)\s*$", re.MULTILINE)
DATE = re.compile(r'^date:\s*"?(\d{4}-\d{2}-\d{2})', re.MULTILINE)
TAGS = re.compile(r'^tags:\s*\[(.*)\]\s*$', re.MULTILINE)

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
CONTENT_ROOT = _REPO_ROOT / "content" if (_REPO_ROOT / "content").exists() else Path("content")
EXCLUDE = {"_index.md", "welcome.md"}


def published(content_root: Path) -> list[dict]:
    """draft: false인 해설 포스트. _index.md·welcome.md 제외."""
    out = []
    for md in sorted((content_root / "posts").glob("*.md")):
        if md.name in EXCLUDE:
            continue
        text = md.read_text(encoding="utf-8")
        dm = DRAFT.search(text)
        if not dm or dm.group(1) != "false":
            continue
        d = DATE.search(text)
        tm = TAGS.search(text)
        tags = (
            [t.strip().strip('"') for t in tm.group(1).split(",") if t.strip()]
            if tm
            else []
        )
        out.append(
            {"file": md.name, "date": d.group(1) if d else None, "tags": tags}
        )
    return out


def site_age(content_root: Path, today: str) -> int:
    pubs = [p for p in published(content_root) if p["date"]]
    if not pubs:
        return 0
    oldest = min(p["date"] for p in pubs)
    return (date.fromisoformat(today) - date.fromisoformat(oldest)).days


def gate_stats(content_root: Path, today: str) -> dict:
    age = site_age(content_root, today)
    return {
        "published_count": len(published(content_root)),
        "oldest_age": age,
        "site_age": age,
    }


def documents(content_root: Path) -> list[dict]:
    """content/posts + content/dictionary의 모든 문서. D1·D3·D6의 공통 입력. (AC #44)

    published()와 나란히 둔다 — published()는 posts만 보고 공지를 파일명으로
    제외하지만, D1·D6의 분모는 사전을 포함하고 공지를 태그로 제외한다.
    """
    out = []
    for section in ("posts", "dictionary"):
        section_dir = content_root / section
        if not section_dir.exists():
            continue
        for path in sorted(section_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            raw = path.read_text(encoding="utf-8")
            front, body = split_front_matter(raw)
            date_m = re.search(r"^date:\s*(\S+)", front, re.M)
            tags_m = re.search(r"^tags:\s*\[(.*)\]\s*$", front, re.M)
            draft_m = re.search(r"^draft:\s*(\S+)", front, re.M)
            tags = []
            if tags_m:
                tags = [
                    t.strip().strip('"').strip("'")
                    for t in tags_m.group(1).split(",")
                    if t.strip()
                ]
            out.append(
                {
                    "file": f"content/{section}/{path.name}",
                    "slug": path.stem,
                    "section": section,
                    "date": date_m.group(1)[:10] if date_m else "",
                    "tags": tags,
                    "draft": bool(draft_m) and draft_m.group(1).strip() == "true",
                    "has_source_url": bool(re.search(r"^source_url:", front, re.M)),
                    "chars": len(re.sub(r"\s", "", strip_code_spans(body))),
                    "body": body,
                }
            )
    return out


def is_notice(doc: dict) -> bool:
    """공지 판정은 태그 기준이다 — 파일명이 아니다. (AC #44 D1·D6)

    리스트 원소의 정확 일치로 판정한다. 부분 문자열 검사는 안 된다 —
    "인공지능"이 "공지"를 포함한다.
    """
    return "공지" in doc.get("tags", [])


if __name__ == "__main__":
    today = sys.argv[1] if len(sys.argv) > 1 else kst_today()
    print(json.dumps(gate_stats(CONTENT_ROOT, today), ensure_ascii=False, indent=2))
