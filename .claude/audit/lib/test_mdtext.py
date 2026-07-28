"""골든 테스트 — mdtext가 조용히 바뀌는 것을 막는다.

.venv/bin/python .claude/audit/lib/test_mdtext.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdtext import split_front_matter, strip_code_spans  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


print("split_front_matter")
FM = '---\ntitle: "x"\ndraft: false\n---\n\n본문입니다.\n'
fm, body = split_front_matter(FM)
check("front matter 분리", "title:" in fm and "본문" not in fm, True)
check("본문 분리", body.strip(), "본문입니다.")
check("front matter 없으면 빈 문자열", split_front_matter("본문만")[0], "")
check("front matter 없으면 원문 반환", split_front_matter("본문만")[1], "본문만")

print("strip_code_spans")
check("인라인 코드 제거", strip_code_spans("앞 `code` 뒤").strip(), "앞  뒤")
check(
    "펜스 코드블록 제거",
    "print" not in strip_code_spans("전\n```\nprint(1)\n```\n후"),
    True,
)
check(
    "코드 안 가짜 링크가 추출되지 않도록 제거",
    "]" not in strip_code_spans("`[가짜](/x/)`"),
    True,
)
check(
    "펜스 먼저 처리 — 펜스 내부 단일 백틱이 경계를 깨지 않음",
    "secret" not in strip_code_spans("```\na ` b secret\n```"),
    True,
)

print("mask_code_spans")
from mdtext import mask_code_spans  # noqa: E402

MASK_SRC = "첫 줄 `코드` 끝\n```\nfenced\n블록\n```\n마지막 줄\n"
masked = mask_code_spans(MASK_SRC)
check("줄 수 보존", masked.count("\n"), MASK_SRC.count("\n"))
check(
    "각 줄 길이 보존",
    [len(x) for x in masked.split("\n")],
    [len(x) for x in MASK_SRC.split("\n")],
)
check("인라인 코드 소거", "코드" in masked, False)
check("펜스 내용 소거", "fenced" in masked, False)
check("펜스 밖 텍스트 보존", "마지막 줄" in masked, True)
check("인라인 마스킹 위치 유지", masked.split("\n")[0], "첫 줄      끝")


print("extract_links")
from mdtext import extract_links, extract_front_matter_urls, inventory  # noqa: E402

links = extract_links("[코픽스](/dictionary/cofix/) 그리고 [원문](https://a.com/x)")
kinds = {ln["target"]: ln["kind"] for ln in links}
check("내부 링크 분류", kinds["/dictionary/cofix/"], "internal")
check("외부 링크 분류", kinds["https://a.com/x"], "external")
check("링크 2건", len(links), 2)
check(
    "코드 안 링크는 추출 안 됨",
    extract_links("`[x](/y/)` 실제 [진짜](/z/)"),
    [{"anchor": "진짜", "target": "/z/", "kind": "internal"}],
)

print("extract_front_matter_urls")
FM2 = (
    '---\nsource_url: "https://src.com/a"\n'
    "related_articles:\n"
    '  - title: "t1"\n    url: "https://r.com/1"\n    source: "s"\n'
    '  - title: "t2"\n    url: "https://r.com/2"\n    source: "s"\n---\n'
)
fmurls = extract_front_matter_urls(FM2)
check("source_url 추출", fmurls["source_url"], "https://src.com/a")
check("related url 2건", fmurls["related_urls"], ["https://r.com/1", "https://r.com/2"])

print("inventory")
inv = inventory(FM2 + "\n[코픽스](/dictionary/cofix/) 본문 [외부](https://b.com/y)")
check("internal 1건", [x["target"] for x in inv["internal"]], ["/dictionary/cofix/"])
check(
    "external = 본문 + source_url + related",
    sorted(inv["external"]),
    ["https://b.com/y", "https://r.com/1", "https://r.com/2", "https://src.com/a"],
)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")

