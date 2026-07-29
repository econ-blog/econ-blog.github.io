"""골든 테스트 — portfolio(D1–D6). 실제 저장소 상태에 대한 앵커를 함께 둔다.

.venv/bin/python .claude/audit/lib/test_portfolio.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portfolio import d1_composition  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


def doc(slug, section, chars, source=False, draft=False, tags=None, body=""):
    return {
        "file": f"content/{section}/{slug}.md",
        "slug": slug,
        "section": section,
        "date": "2026-07-20",
        "tags": tags if tags is not None else ["금리"],
        "draft": draft,
        "has_source_url": source,
        "chars": chars,
        "body": body,
    }


print("d1_composition")
DOCS = [
    doc("p1", "posts", 2000, source=True),
    doc("p2", "posts", 1000, source=True),
    doc("t1", "dictionary", 500, tags=["용어사전"]),
    doc("t2", "dictionary", 300, tags=["용어사전"]),
    doc("essay", "posts", 200),  # source_url 없음 → 상록
    doc("notice", "posts", 9999, tags=["공지"]),  # 분모 제외
    doc("wip", "posts", 9999, source=True, draft=True),  # 분모 제외
]
r = d1_composition(DOCS)
check("질량 상록", r["mass"]["evergreen"], 1000)  # 500 + 300 + 200
check("질량 시의성", r["mass"]["timely"], 3000)  # 2000 + 1000
check("질량 합", r["mass"]["total"], 4000)
check("질량 비율", r["mass"]["evergreen_ratio"], 0.25)
check("문서 수 상록", r["doc_count"]["evergreen"], 3)
check("문서 수 시의성", r["doc_count"]["timely"], 2)
check("문서 수 비율", r["doc_count"]["evergreen_ratio"], 0.6)
check("포스트 중앙값", r["median_chars"]["posts"], 1000)
check("사전 중앙값", r["median_chars"]["dictionary"], 500)
check("공지·초안 제외", r["doc_count"]["total"], 5)

print("d1_composition 빈 코퍼스")
empty = d1_composition([])
check("0 나눗셈 없음", empty["mass"]["evergreen_ratio"], 0.0)
check("빈 중앙값", empty["median_chars"]["posts"], 0)

print("load_vocab / d2_vocabulary")
from portfolio import load_vocab, d2_vocabulary  # noqa: E402

VOCAB_SRC = """# 주석 줄
# 또 주석

금리:
  aliases: ["기준금리", "정책금리"]
부동산:
  aliases: ["주택"]
고용:
  aliases: ["실업률"]
"""
check("load_vocab 순서 유지", load_vocab(VOCAB_SRC), ["금리", "부동산", "고용"])
check("aliases 줄 무시", "aliases" in load_vocab(VOCAB_SRC), False)

D2DOCS = [
    doc("p1", "posts", 100, source=True, tags=["금리", "부동산"]),
    doc("p2", "posts", 100, source=True, tags=["금리"]),
    doc("p3", "posts", 100, source=True, tags=["금리", "우주항공"]),
    doc("notice", "posts", 100, tags=["공지"]),
    doc("t1", "dictionary", 100, tags=["용어사전"]),
]
r2 = d2_vocabulary(D2DOCS, ["금리", "부동산", "고용"])
check("counts vocab 순서", list(r2["counts"].keys()), ["금리", "부동산", "고용"])
check("금리 3회", r2["counts"]["금리"], 3)
check("부동산 1회", r2["counts"]["부동산"], 1)
check("고용 0회 유지", r2["counts"]["고용"], 0)
check("used", r2["used"], 2)
check("unused", r2["unused"], ["고용"])
check("어휘 밖 태그", r2["outside"], ["우주항공"])
check("사전 용어사전 태그 미포함", "용어사전" in r2["outside"], False)
check("공지 제외", r2["total_tag_uses"], 5)
check("최다/최소 배율", r2["max_min_ratio"], 3.0)

r2b = d2_vocabulary([], ["금리"])
check("빈 코퍼스 배율 None", r2b["max_min_ratio"], None)

print("d3_source_side")
from portfolio import d3_source_side  # noqa: E402

TERMS3 = {
    "base-rate": {"title": "기준금리", "aliases": []},
    "cofix": {"title": "코픽스", "aliases": []},
    "lonely": {"title": "외톨이", "aliases": []},
}
D3DOCS = [
    doc("p1", "posts", 100, source=True,
        body="[기준금리](/dictionary/base-rate/)가 올랐고 "
             "다시 [기준금리](/dictionary/base-rate/)를 본다.\n"),
    doc("p2", "posts", 100, source=True,
        body="[코픽스](/dictionary/cofix/) 이야기. `[가짜](/dictionary/base-rate/)`\n"),
    doc("notice", "posts", 100, tags=["공지"],
        body="[기준금리](/dictionary/base-rate/)\n"),
    doc("base-rate", "dictionary", 100, tags=["용어사전"],
        body="## 실생활에서는\n[코픽스](/dictionary/cofix/) 참고.\n"
             "## 투자에서는\n[자기](/dictionary/base-rate/)\n"),
    doc("cofix", "dictionary", 100, tags=["용어사전"], body="설명만 있다.\n"),
    doc("lonely", "dictionary", 100, tags=["용어사전"], body="# 큰제목\n외톨이.\n"),
]
r3 = d3_source_side(D3DOCS, TERMS3)
check("유입은 출현 횟수", r3["inbound"]["base-rate"], 3)   # p1 2회 + 공지 1회
check("코드스팬 링크 제외", r3["inbound"]["cofix"], 1)      # p2의 백틱 링크는 미집계
check("유입 0 슬러그도 키 유지", r3["inbound"]["lonely"], 0)
check("고아 목록", r3["orphans"], ["lonely"])
check("포스트당 링크 값", r3["links_per_post"]["values"], [1, 2])
check("포스트당 링크 중앙값", r3["links_per_post"]["median"], 2)
check("본문 유출에서 자기참조 제외", r3["body_outbound"]["base-rate"], 1)
check("유출 0 항목", sorted(r3["body_outbound_zero"]), ["cofix", "lonely"])
check("자기참조 목록", r3["self_reference"], ["base-rate"])
check("헤딩 수(## 이상만)", r3["headings"]["base-rate"], 2)
check("h1은 세지 않음", r3["headings"]["lonely"], 0)

print("d3_render_side")
import tempfile  # noqa: E402
from pathlib import Path as _P  # noqa: E402
from portfolio import d3_render_side  # noqa: E402

# minify가 인용부호를 벗긴 형태를 그대로 재현한다
MINIFIED = (
    "<article><p>본문 <a href=/dictionary/cofix/>코픽스</a></p>"
    "<div class=related-posts><h3 class=related-posts-title>이 용어가 나온 글</h3>"
    "<ul class=related-posts-list>"
    "<li><a href=/posts/aaa/>가</a></li><li><a href=/posts/bbb/>나</a></li>"
    "</ul></div></article>"
)
QUOTED = (
    '<article><ul class="related-posts-list">'
    '<li><a href="/posts/ccc/">다</a></li></ul></article>'
)
DEADEND = "<article><p>나가는 링크가 없다.</p></article>"

with tempfile.TemporaryDirectory() as tmp:
    pub = _P(tmp)
    for slug, html in (("base-rate", MINIFIED), ("cofix", QUOTED), ("gdi", DEADEND)):
        (pub / "dictionary" / slug).mkdir(parents=True)
        (pub / "dictionary" / slug / "index.html").write_text(html, encoding="utf-8")
    # 페이지네이션 디렉터리 — 순회 대상이 아니어야 한다
    (pub / "dictionary" / "page" / "2").mkdir(parents=True)

    T5 = {s: {"title": s, "aliases": []}
          for s in ("base-rate", "cofix", "gdi", "notbuilt")}
    r5 = d3_render_side(pub, T5)
    check("built", r5["built"], True)
    check("인용부호 벗겨진 백링크", r5["backlinks"]["base-rate"], 2)
    check("인용부호 있는 백링크", r5["backlinks"]["cofix"], 1)
    check("백링크 0", r5["backlinks"]["gdi"], 0)
    check("페이지 없음은 None", r5["backlinks"]["notbuilt"], None)
    check("missing_pages", r5["missing_pages"], ["notbuilt"])
    check("막다름은 나가는 링크 0", r5["dead_ends"], ["gdi"])
    check("본문 유출만 있어도 막다름 아님", "cofix" in r5["dead_ends"], False)
    check("상한 기록", r5["backlink_cap"], 8)

    r5b = d3_render_side(_P(tmp) / "does-not-exist", T5)
    check("빌드 없음", r5b["built"], False)
    check("빌드 없으면 막다름 비움", r5b["dead_ends"], [])

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")



