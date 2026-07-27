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

DRAFT = re.compile(r"^draft:\s*(true|false)\s*$", re.MULTILINE)
DATE = re.compile(r'^date:\s*"?(\d{4}-\d{2}-\d{2})', re.MULTILINE)
TAGS = re.compile(r'^tags:\s*\[(.*)\]\s*$', re.MULTILINE)

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
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


if __name__ == "__main__":
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(json.dumps(gate_stats(CONTENT_ROOT, today), ensure_ascii=False, indent=2))
