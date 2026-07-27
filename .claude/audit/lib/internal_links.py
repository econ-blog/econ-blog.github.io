"""내부 링크 해소 — content/ 파일시스템 + _terms.yaml로 결정론적 판정.

네트워크를 쓰지 않는다. PyYAML을 쓰지 않는다(저장소 무의존성 규약) —
_terms.yaml은 slug→{title,aliases} 고정 구조라 정규식 라인 파서로 충분하며,
그 파서가 구조 위반을 감지해 AC #37의 파싱 실패 가드를 대신한다.

사용:
    .venv/bin/python .claude/audit/lib/internal_links.py   # 깨진 내부링크 JSON
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdtext import extract_links, split_front_matter  # noqa: E402

SLUG = re.compile(r"^([a-z0-9][a-z0-9-]*):\s*$")
KV = re.compile(r"^\s+(title|aliases):\s*(.+?)\s*$")

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
CONTENT_ROOT = _REPO_ROOT / "content" if (_REPO_ROOT / "content").exists() else Path("content")
TERMS_PATH = CONTENT_ROOT / "dictionary" / "_terms.yaml"


def load_terms(text: str) -> dict:
    """slug→{title,aliases}. 예상 셋(슬러그행/title/aliases/공백) 밖의 라인은
    ValueError로 올린다 — YAML 파서 없이 구조 무결성만 검사(AC #37)."""
    terms: dict = {}
    cur = None
    for i, line in enumerate(text.splitlines(), 1):
        sline = line.strip()
        if not sline or sline.startswith("#"):
            continue
        m = SLUG.match(line)
        if m:
            cur = m.group(1)
            terms[cur] = {"title": "", "aliases": []}
            continue
        m = KV.match(line)
        if m and cur is not None:
            key, val = m.group(1), m.group(2)
            if key == "title":
                terms[cur]["title"] = val.strip().strip('"')
            else:
                inner = val.strip().lstrip("[").rstrip("]")
                terms[cur]["aliases"] = [
                    a.strip().strip('"') for a in inner.split(",") if a.strip()
                ]
            continue
        raise ValueError(f"_terms.yaml {i}행 파싱 불가: {line!r}")
    return terms


def resolve_internal(target: str, content_root: Path, terms: dict) -> bool:
    """내부 링크 target이 실재 콘텐츠로 해소되는지 (AC #6).

    _terms.yaml 인덱스 등재만으로는 부족하며 .md 실재 파일이 존재해야 한다 (I3).
    """
    path = target.split("#", 1)[0].split("?", 1)[0].strip("/")
    if not path:
        return True  # 사이트 루트
    if path.startswith("dictionary/"):
        slug = path[len("dictionary/"):].strip("/")
        return (content_root / "dictionary" / f"{slug}.md").exists()
    if (content_root / f"{path}.md").exists():
        return True
    if (content_root / path / "_index.md").exists():
        return True
    return False


def scan_broken(content_root: Path, terms: dict) -> list[dict]:
    out = []
    for md in sorted(content_root.rglob("*.md")):
        _, body = split_front_matter(md.read_text(encoding="utf-8"))
        for ln in extract_links(body):
            if ln["kind"] != "internal":
                continue
            if not resolve_internal(ln["target"], content_root, terms):
                out.append(
                    {"file": md.name, "anchor": ln["anchor"], "target": ln["target"]}
                )
    return out


if __name__ == "__main__":
    terms = load_terms(TERMS_PATH.read_text(encoding="utf-8"))
    print(json.dumps(scan_broken(CONTENT_ROOT, terms), ensure_ascii=False, indent=2))

