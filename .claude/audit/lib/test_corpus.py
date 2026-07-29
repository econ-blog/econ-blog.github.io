"""골든 테스트 — corpus. 실제 저장소 상태에 대한 앵커.

.venv/bin/python .claude/audit/lib/test_corpus.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import published, site_age, gate_stats  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


ROOT = Path(__file__).resolve().parents[3] / "content"
pubs = published(ROOT)
names = {p["file"] for p in pubs}
print("published")
check("welcome.md 제외", "welcome.md" not in names, True)
check("_index.md 제외", "_index.md" not in names, True)
check("해설글 하한 9건 이상", len(pubs) >= 9, True)
check("mortgage 포스트 포함", "mortgage-rate-7-5-percent-exceeded.md" in names, True)

print("site_age")
# 가장 오래된 발행글은 2026-07-18 welcome 다음의 첫 해설글대이며 D는 양수.
age = site_age(ROOT, "2026-07-25")
check("사이트 연령 양수", age > 0, True)
check("gate_stats site_age 일치", gate_stats(ROOT, "2026-07-25")["site_age"], age)
check("gate_stats 발행글 수 일치", gate_stats(ROOT, "2026-07-25")["published_count"], len(pubs))

import tempfile

print("documents / is_notice")
from corpus import documents, is_notice  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "posts").mkdir()
    (root / "dictionary").mkdir()
    (root / "posts" / "_index.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    (root / "posts" / "a.md").write_text(
        '---\ntitle: "가"\ndate: 2026-07-18T09:00:00+09:00\ntags: ["금리", "물가"]\n'
        'draft: false\nsource_url: "https://x.com/1"\n---\n'
        "본문 한 줄.\n\n`코드` 제거 대상.\n",
        encoding="utf-8")
    (root / "posts" / "n.md").write_text(
        '---\ntitle: "공지"\ndate: 2026-07-17T09:00:00+09:00\ntags: ["공지"]\n'
        'draft: false\n---\n짧은 공지.\n',
        encoding="utf-8")
    (root / "dictionary" / "t.md").write_text(
        '---\ntitle: "용어"\ndate: 2026-07-20T09:00:00+09:00\ntags: ["용어사전"]\n'
        'draft: true\n---\n## 실생활에서는\n설명.\n',
        encoding="utf-8")

    docs = documents(root)
    check("_index.md 제외", sorted(d["slug"] for d in docs), ["a", "n", "t"])
    a = next(d for d in docs if d["slug"] == "a")
    check("section", a["section"], "posts")
    check("date 10자", a["date"], "2026-07-18")
    check("tags", a["tags"], ["금리", "물가"])
    check("draft false", a["draft"], False)
    check("source_url 있음", a["has_source_url"], True)
    # "본문한줄." 5자 + "제거대상." 5자 = 10 (공백·코드스팬 제외)
    check("chars 공백·코드스팬 제외", a["chars"], 10)
    check("body는 코드스팬 원문 보존", "`코드`" in a["body"], True)

    t = next(d for d in docs if d["slug"] == "t")
    check("사전 draft true", t["draft"], True)
    check("사전 source_url 없음", t["has_source_url"], False)

    n = next(d for d in docs if d["slug"] == "n")
    check("공지 판정", is_notice(n), True)
    check("비공지 판정", is_notice(a), False)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")

