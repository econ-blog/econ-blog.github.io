"""마크다운 전처리 — 주간 감사의 코드스팬·링크 처리 단일 주체.

결정론적. 표준 라이브러리 + 정규식만 사용한다. AST 파서를 도입하지 않는다.
(근거: 클라우드 재현성 규약 — 표준 라이브러리 + 정규식만.)

사용:
    .venv/bin/python .claude/audit/lib/mdtext.py <파일.md>   # JSON 링크 인벤토리
"""
import json
import re
import sys
from pathlib import Path

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
SOURCE_URL = re.compile(r'^source_url:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
RELATED_URL = re.compile(r'^\s+url:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)


def split_front_matter(raw: str) -> tuple[str, str]:
    """(구분자 포함 front matter, 본문). front matter가 없으면 ('', raw)."""
    m = FRONT_MATTER.match(raw)
    if not m:
        return "", raw
    return m.group(0), raw[m.end():]


def strip_code_spans(text: str) -> str:
    """펜스 코드블록과 인라인 코드 스팬을 제거한다. (AC #5)

    펜스를 먼저 지운 뒤 인라인을 지운다 — 순서를 바꾸면 펜스 안의 단일 백틱이
    인라인 스팬을 거짓으로 열어 펜스 경계를 깨뜨린다. 링크 추출 전에 적용해
    코드 예시 안의 대괄호·괄호가 링크로 오인되는 것을 막는다.
    """
    text = FENCED_CODE.sub("", text)
    text = INLINE_CODE.sub("", text)
    return text


def mask_code_spans(text: str) -> str:
    """코드 스팬을 같은 길이의 공백으로 덮는다. 줄바꿈은 그대로 둔다. (AC #5)

    strip_code_spans와 같은 규약이되 제거 대신 마스킹한다 — 소견은 위치를
    file:line으로 요구하므로(AC #33), 제거하면 이후 줄 번호가 전부 밀린다.
    펜스를 먼저 덮는 순서도 strip_code_spans와 같다.
    """
    def blank(m):
        return "".join("\n" if ch == "\n" else " " for ch in m.group(0))

    text = FENCED_CODE.sub(blank, text)
    text = INLINE_CODE.sub(blank, text)
    return text


def _classify(target: str) -> str:
    if target.startswith("/"):
        return "internal"
    if target.startswith(("http://", "https://")):
        return "external"
    return "other"


def extract_links(body: str) -> list[dict]:
    """코드스팬 제거(AC #5) 후 마크다운 링크 목록."""
    clean = strip_code_spans(body)
    return [
        {"anchor": a, "target": t, "kind": _classify(t)}
        for a, t in MD_LINK.findall(clean)
    ]


def extract_front_matter_urls(front_matter: str) -> dict:
    """front matter의 source_url과 related_articles[].url을 정규식으로 뽑는다.

    PyYAML을 쓰지 않는다(저장소 무의존성 규약). front matter가 평탄·단순해
    정규식으로 충분하며, 복잡한 중첩이 들어오면 재현율이 떨어지는 best-effort다.
    """
    src = SOURCE_URL.search(front_matter)
    return {
        "source_url": src.group(1) if src else None,
        "related_urls": RELATED_URL.findall(front_matter),
    }


def inventory(raw: str) -> dict:
    fm, body = split_front_matter(raw)
    links = extract_links(body)
    fmurls = extract_front_matter_urls(fm)
    external = [ln["target"] for ln in links if ln["kind"] == "external"]
    if fmurls["source_url"]:
        external.append(fmurls["source_url"])
    external.extend(fmurls["related_urls"])
    return {
        "internal": [ln for ln in links if ln["kind"] == "internal"],
        "external": external,
        "source_url": fmurls["source_url"],
        "related_urls": fmurls["related_urls"],
    }


def main(argv: list[str]) -> None:
    out = {}
    for a in argv:
        p = Path(a)
        out[p.name] = inventory(p.read_text(encoding="utf-8"))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])

