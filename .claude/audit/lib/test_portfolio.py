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

print("d4_eeat")
from portfolio import d4_eeat, PRIMARY_SOURCE_HOSTS  # noqa: E402

check("1차 출처 호스트 다섯", len(PRIMARY_SOURCE_HOSTS), 5)
check("bok.or.kr 포함", "bok.or.kr" in PRIMARY_SOURCE_HOSTS, True)

MINI_POST = (
    '<head><meta name=author content><script type=application/ld+json>'
    '{"@type":"BreadcrumbList","itemListElement":[]}</script>'
    '<script type=application/ld+json>'
    '{"@type":"BlogPosting","headline":"가","publisher":{"name":"나"}}</script></head>'
)
D4DOCS = [
    doc("p1", "posts", 100, source=True,
        body="근거는 [ECOS](https://ecos.bok.or.kr/x)와 [한경](https://hankyung.com/y).\n"),
    doc("p2", "posts", 100, source=True, body="링크 없음.\n"),
    doc("t1", "dictionary", 100, tags=["용어사전"],
        body="[FRED](https://fred.stlouisfed.org/z) 참고. `https://kosis.kr/q`\n"),
]
with tempfile.TemporaryDirectory() as tmp:
    root, pub = _P(tmp) / "content", _P(tmp) / "public"
    root.mkdir()
    (root / "about.md").write_text("---\ntitle: a\n---\n", encoding="utf-8")
    (root / "privacy.md").write_text("---\ntitle: p\n---\n", encoding="utf-8")
    (pub / "posts" / "p1").mkdir(parents=True)
    (pub / "posts" / "p1" / "index.html").write_text(MINI_POST, encoding="utf-8")

    r4 = d4_eeat(D4DOCS, root, 'baseURL = "https://x/"\ntitle = "t"\n', pub)
    check("hugo author 미설정", r4["hugo_author"], False)
    check("meta author 태그 존재", r4["meta_author"]["tag"], True)
    check("meta author 값 비어 있음", r4["meta_author"]["value_nonempty"], False)
    check("BlogPosting 발견(2번째 블록)", r4["jsonld_blogposting"]["present"], True)
    check("author 키 없음", r4["jsonld_blogposting"]["author_key"], False)
    check("ld+json 블록 수", r4["jsonld_blogposting"]["blocks"], 2)
    check("about 있음", r4["policy_pages"]["about"], True)
    check("contact 없음", r4["policy_pages"]["contact"], False)
    check("1차 출처 총합", r4["primary_source_links"]["total"], 2)
    check("포스트 쪽", r4["primary_source_links"]["posts"], 1)
    check("사전 쪽", r4["primary_source_links"]["dictionary"], 1)
    check("코드스팬 URL 미집계",
          r4["primary_source_links"]["per_file"]["content/dictionary/t1.md"], 1)

    r4b = d4_eeat(D4DOCS, root, 'author = "홍길동"\n', _P(tmp) / "nope")
    check("hugo author 설정됨", r4b["hugo_author"], True)
    check("빌드 없음", r4b["built"], False)
    check("빌드 없으면 meta None", r4b["meta_author"], None)

print("d5_decay")
from portfolio import d5_decay, d6_slots, POST_SLOTS, DICT_SLOTS  # noqa: E402


def dated(slug, section, date, source=False, body="", tags=None):
    d = doc(slug, section, 100, source=source, body=body, tags=tags)
    d["date"] = date
    return d


D5DOCS = [
    dated("old", "posts", "2026-01-01", source=True),   # 206일 경과
    dated("new", "posts", "2026-07-20", source=True),    # 6일
    dated("ever", "posts", "2026-02-01"),                # source_url 없음 → 시의성 아님
    dated("term", "dictionary", "2026-01-01", tags=["용어사전"]),
]
r5d = d5_decay(D5DOCS, "2026-07-26")
check("사이트 연령", r5d["site_age"], 206)
check("시의성 총수", r5d["timely_total"], 2)
check("90일 경과", r5d["aged_90"], 1)
check("비율", r5d["ratio"], 0.5)
check("경과 파일", r5d["aged_files"], ["content/posts/old.md"])

check("빈 코퍼스 0 나눗셈", d5_decay([], "2026-07-26")["ratio"], 0.0)

print("d6_slots")
check("포스트 슬롯 문자열", POST_SLOTS,
      ("## 나에게 무슨 의미인가", "## 투자 관점에서 보면"))
check("사전 슬롯 문자열", DICT_SLOTS, ("## 실생활에서는", "## 투자에서는"))

D6DOCS = [
    doc("ok", "posts", 100, source=True,
        body="## 나에게 무슨 의미인가\n가\n## 투자 관점에서 보면\n나\n"),
    doc("half", "posts", 100, source=True, body="## 나에게 무슨 의미인가\n가\n"),
    doc("notice", "posts", 100, tags=["공지"], body="아무 슬롯 없음\n"),
    doc("term", "dictionary", 100, tags=["용어사전"],
        body="## 실생활에서는\n가\n## 투자에서는\n나\n"),
]
r6 = d6_slots(D6DOCS)
check("포스트 슬롯1 충족", r6["posts"]["## 나에게 무슨 의미인가"]["met"], 2)
check("포스트 슬롯2 충족", r6["posts"]["## 투자 관점에서 보면"]["met"], 1)
check("포스트 분모(공지 제외)", r6["posts"]["## 투자 관점에서 보면"]["total"], 2)
check("미충족 목록", r6["posts"]["## 투자 관점에서 보면"]["missing"],
      ["content/posts/half.md"])
check("사전 슬롯 충족", r6["dictionary"]["## 실생활에서는"]["met"], 1)
check("전부 충족 아님", r6["all_met"], False)

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")





