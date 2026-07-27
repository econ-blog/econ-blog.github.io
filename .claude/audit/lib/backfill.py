"""내부 링크 백필 후보 탐지 — ①의 확장(I).

_terms.yaml의 title·aliases만 연결 후보로 삼는다(사전 확장 안 함, AC #63).
대상당 1링크: 문서가 그 slug를 이미 링크하면 backfill 후보로 만들지 않는다(AC #65).
연결 금지 구간(front matter·제목·표·인용문·코드스팬·기존 링크)을 제외한다(AC #64).

결정론적. stdlib + 정규식만. 사용:
    .venv/bin/python .claude/audit/lib/backfill.py   # 후보 JSON
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from internal_links import CONTENT_ROOT, TERMS_PATH, load_terms  # noqa: E402
import re
from mdtext import FENCED_CODE, MD_LINK, split_front_matter, strip_code_spans  # noqa: E402

DICT_PREFIX = "/dictionary/"


def _mask_fenced_code(text: str) -> str:
    """다행 펜스 코드블록 내 개행 제외 문자를 공백으로 대체하여 줄번호를 유지한다."""
    return FENCED_CODE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _linked_slugs_and_lines(body: str) -> dict:
    """이 문서가 이미 링크한 사전 slug → 첫 링크 등장 줄번호."""
    out: dict = {}
    for lineno, line in enumerate(body.splitlines(), 1):
        for _, target in MD_LINK.findall(line):
            if target.startswith(DICT_PREFIX) or target.startswith("dictionary/"):
                clean_target = target.split("#", 1)[0].split("?", 1)[0]
                slug = clean_target.split("dictionary/", 1)[1].strip("/").split("/")[0]
                if slug:
                    out.setdefault(slug, lineno)
    return out


def find_candidates(files: list[Path], terms: dict) -> list[dict]:
    lookup = []  # (surface, slug) — 긴 표면부터 매칭해 부분일치 오탐 감소
    for slug, t in terms.items():
        for surface in [t["title"], *t["aliases"]]:
            if surface:
                lookup.append((surface, slug))
    lookup.sort(key=lambda x: -len(x[0]))

    out = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        _, body = split_front_matter(raw)
        masked_body = _mask_fenced_code(body)
        own_slug = path.stem  # 사전 항목이 자기 자신을 링크하지 않도록
        linked = _linked_slugs_and_lines(masked_body)
        seen: set = set()
        for lineno, line in enumerate(masked_body.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith(("#", "|", ">")):
                continue  # 제목·표·인용문 제외 (AC #64)
            # 코드스팬 제거 후 기존 링크 텍스트도 제거해 앵커 안 등장을 배제
            clean = MD_LINK.sub(" ", strip_code_spans(line))
            for surface, slug in lookup:
                if slug in seen or slug == own_slug:
                    continue
                if surface in clean:
                    if slug in linked:
                        if lineno < linked[slug]:
                            out.append({"file": path.name, "slug": slug,
                                        "term": surface, "line": lineno,
                                        "kind": "precedence"})  # AC #66 소견만
                    else:
                        out.append({"file": path.name, "slug": slug,
                                    "term": surface, "line": lineno,
                                    "kind": "backfill"})  # AC #65
                    seen.add(slug)
    return out


if __name__ == "__main__":
    terms = load_terms(TERMS_PATH.read_text(encoding="utf-8"))
    files = sorted((CONTENT_ROOT / "posts").glob("*.md")) + \
        sorted((CONTENT_ROOT / "dictionary").glob("*.md"))
    files = [f for f in files if f.name not in {"_index.md", "welcome.md"}]
    print(json.dumps(find_candidates(files, terms), ensure_ascii=False, indent=2))
