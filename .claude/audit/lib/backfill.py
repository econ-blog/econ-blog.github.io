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

HANGUL = re.compile(r"[가-힣]")
ALNUM = re.compile(r"[A-Za-z0-9]")

# 표면 뒤에 붙어도 낱말 경계로 허용하는 한국어 조사. 최장 것부터 시도해야
# "이라는"이 "이"에 먹혀 짧게 매칭되는 일이 없다.
# 한계: 이 목록은 닫힌 목록이라 여기 없는 조사(예: "이나", "든지")가 붙으면
# 오탐(낱말 내부로 오판)이 남는다 — 재현율보다 오탐 억제를 우선한 결정.
PARTICLES = tuple(sorted([
    "은", "는", "이", "가", "을", "를", "의", "에서", "에", "으로", "로",
    "와", "과", "도", "만", "까지", "부터", "보다", "처럼", "라는", "이라는",
], key=len, reverse=True))


def _edge_class(ch: str) -> str | None:
    if HANGUL.match(ch):
        return "hangul"
    if ALNUM.match(ch):
        return "alnum"
    return None


def _passes_word_boundary(clean: str, start: int, end: int, surface: str) -> bool:
    """매칭된 표면이 더 긴 낱말의 일부가 아닌지 판정한다.

    앞: 표면 첫 글자와 같은 문자군(한글/영숫자)이 바로 앞에 붙어 있으면 그
    표면은 더 긴 낱말의 뒷부분이다 — 조사 같은 예외가 없으므로 무조건 버린다
    (한국어 복합어·접두사가 앞쪽에 붙기 때문).
    뒤: 표면 마지막 글자와 같은 문자군이 바로 뒤에 붙어 있으면 원칙적으로
    버리되, 한글 표면이고 그 자리부터 한국어 조사(PARTICLES)로 시작하면
    조사가 낱말 경계 역할을 하므로 예외로 통과시킨다. 영숫자 표면(LNG·PER
    등)에는 조사 개념이 없으므로 이 예외를 적용하지 않는다.
    """
    if not surface:
        return False
    first_class = _edge_class(surface[0])
    if first_class is not None and start > 0:
        prev = clean[start - 1]
        if _edge_class(prev) == first_class:
            return False

    last_class = _edge_class(surface[-1])
    if last_class is not None and end < len(clean):
        nxt = clean[end]
        if _edge_class(nxt) == last_class:
            if last_class == "hangul":
                matched_p = next((p for p in PARTICLES if clean[end:].startswith(p)), None)
                if matched_p:
                    rest = clean[end + len(matched_p):]
                    if not rest or _edge_class(rest[0]) != "hangul":
                        pass  # 유효한 조사 — 낱말 경계로 허용
                    else:
                        return False
                else:
                    return False
            else:
                return False
    return True


def _find_valid_surface(clean: str, surface: str) -> bool:
    """clean 안에 낱말 경계를 통과하는 surface 등장이 하나라도 있는가."""
    start = 0
    while True:
        idx = clean.find(surface, start)
        if idx == -1:
            return False
        if _passes_word_boundary(clean, idx, idx + len(surface), surface):
            return True
        start = idx + 1
    return False


def _mask_fenced_code(text: str) -> str:
    """다행 펜스 코드블록 내 개행 제외 문자를 공백으로 대체하여 줄번호를 유지한다."""
    return FENCED_CODE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _linked_slugs_and_lines(body: str) -> dict:
    """이 문서가 이미 링크한 사전 slug → 첫 링크 등장 줄번호."""
    out: dict = {}
    for lineno, line in enumerate(body.splitlines(), 1):
        for _, target in MD_LINK.findall(line):
            if "dictionary/" in target:
                clean_target = target.split("#", 1)[0].split("?", 1)[0]
                parts = clean_target.split("dictionary/", 1)
                if len(parts) > 1:
                    slug = parts[1].strip("/").split("/")[0]
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
        fm, body = split_front_matter(raw)
        fm_offset = fm.count("\n") if fm else 0
        masked_body = _mask_fenced_code(body)
        own_slug = path.stem  # 사전 항목이 자기 자신을 링크하지 않도록
        linked = _linked_slugs_and_lines(masked_body)
        seen: set = set()
        # Relative file path from repo root or CONTENT_ROOT parent
        try:
            rel_file = str(path.relative_to(CONTENT_ROOT.parent))
        except Exception:
            rel_file = str(path)

        doc_backfill_count = 0
        for lineno, line in enumerate(masked_body.splitlines(), 1):
            file_line = lineno + fm_offset
            stripped = line.lstrip()
            if stripped.startswith(("#", "|", ">")) or line.startswith("    ") or line.startswith("\t"):
                continue  # 제목·표·인용문·들여쓰기 코드블록 제외 (AC #64)
            # 코드스팬 제거 후 기존 링크 텍스트도 제거해 앵커 안 등장을 배제
            clean = MD_LINK.sub(" ", strip_code_spans(line))
            for surface, slug in lookup:
                if slug in seen or slug == own_slug:
                    continue
                if _find_valid_surface(clean, surface):
                    if slug in linked:
                        if lineno < linked[slug]:
                            out.append({"file": rel_file, "slug": slug,
                                        "term": surface, "line": file_line,
                                        "kind": "precedence"})  # AC #66 소견만
                    else:
                        if doc_backfill_count < 3:
                            out.append({"file": rel_file, "slug": slug,
                                        "term": surface, "line": file_line,
                                        "kind": "backfill"})  # AC #65
                            doc_backfill_count += 1
                    seen.add(slug)
    return out


if __name__ == "__main__":
    terms = load_terms(TERMS_PATH.read_text(encoding="utf-8"))
    files = sorted((CONTENT_ROOT / "posts").glob("*.md")) + \
        sorted((CONTENT_ROOT / "dictionary").glob("*.md"))
    files = [f for f in files if f.name not in {"_index.md", "welcome.md"}]
    print(json.dumps(find_candidates(files, terms), ensure_ascii=False, indent=2))
