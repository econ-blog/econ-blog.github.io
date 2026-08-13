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
# 홀수 3건(2000·1000·200) → 1000. 짝수면 가운데 두 값의 평균이다.
check("포스트 중앙값(홀수)", r["median_chars"]["posts"], 1000)
# 500·300 → 400. 상위 원소(500)를 쓰면 짝수 코퍼스에서 값이 위로 치우친다.
check("사전 중앙값(짝수는 평균)", r["median_chars"]["dictionary"], 400)
check("공지·초안 제외", r["doc_count"]["total"], 5)

print("d1_composition 빈 코퍼스")
empty = d1_composition([])
check("0 나눗셈 없음", empty["mass"]["evergreen_ratio"], 0.0)
check("빈 중앙값", empty["median_chars"]["posts"], 0)

print("_median 짝수·홀수")
from portfolio import _median  # noqa: E402

check("홀수는 가운데 값", _median([1, 5, 100]), 5)
check("짝수는 두 값의 평균", _median([1, 2]), 1.5)
check("평균이 정수면 int", _median([2, 4]), 3)
check("int 타입 유지", isinstance(_median([2, 4]), int), True)
check("빈 목록", _median([]), 0)

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
# 줄 끝 주석을 떼지 않으면 그 태그가 조용히 어휘에서 빠진다
check("줄 끝 주석 무시", load_vocab("금리:  # 정책금리 포함\n부동산:\n"),
      ["금리", "부동산"])

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
# p1 2 + p2 1 + p3 2 = 5. 어휘 밖 태그(우주항공)도 "쓰인 태그"이므로 분자에 든다.
# 공지 포스트와 사전은 제외된다. (계획서의 4는 어휘 안쪽만 센 오산)
check("공지·사전 제외한 총 태그 사용", r2["total_tag_uses"], 5)
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
# 값이 [1, 2] — 짝수이므로 두 값의 평균
check("포스트당 링크 중앙값", r3["links_per_post"]["median"], 1.5)
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
# 막다른 항목이라도 PaperMod 상단 내비게이션은 항상 붙는다. 접두사만 보고
# `/dictionary/`(섹션 목록)를 나가는 링크로 세면 dead_ends가 영원히 비게 된다.
DEADEND = (
    "<nav><a href=/>홈</a><a href=/posts/>글</a><a href=/dictionary/>사전</a></nav>"
    "<article><p>나가는 링크가 없다.</p></article>"
)
NAV_ONLY_WITH_SELF = (
    "<nav><a href=/dictionary/>사전</a></nav>"
    "<article><p>자기 자신만 가리킨다 "
    "<a href=/dictionary/selfonly/>여기</a></p></article>"
)

with tempfile.TemporaryDirectory() as tmp:
    pub = _P(tmp)
    for slug, html in (("base-rate", MINIFIED), ("cofix", QUOTED),
                       ("gdi", DEADEND), ("selfonly", NAV_ONLY_WITH_SELF)):
        (pub / "dictionary" / slug).mkdir(parents=True)
        (pub / "dictionary" / slug / "index.html").write_text(html, encoding="utf-8")
    # 페이지네이션 디렉터리 — 순회 대상이 아니어야 한다
    (pub / "dictionary" / "page" / "2").mkdir(parents=True)

    T5 = {s: {"title": s, "aliases": []}
          for s in ("base-rate", "cofix", "gdi", "selfonly", "notbuilt")}
    r5 = d3_render_side(pub, T5)
    check("built", r5["built"], True)
    check("인용부호 벗겨진 백링크", r5["backlinks"]["base-rate"], 2)
    check("인용부호 있는 백링크", r5["backlinks"]["cofix"], 1)
    check("백링크 0", r5["backlinks"]["gdi"], 0)
    check("페이지 없음은 None", r5["backlinks"]["notbuilt"], None)
    check("missing_pages", r5["missing_pages"], ["notbuilt"])
    check("막다름은 나가는 링크 0", r5["dead_ends"], ["gdi", "selfonly"])
    check("본문 유출만 있어도 막다름 아님", "cofix" in r5["dead_ends"], False)
    # 회귀 검사 — 내비게이션의 /dictionary/·/posts/ 는 나가는 링크가 아니다.
    # 이 검사가 없으면 dead_ends가 구조적으로 항상 []가 되는 것을 못 잡는다.
    check("내비 링크는 막다름을 가리지 못한다", "gdi" in r5["dead_ends"], True)
    check("자기참조만 있으면 막다름", "selfonly" in r5["dead_ends"], True)
    check("상한 기록", r5["backlink_cap"], 8)

    r5b = d3_render_side(_P(tmp) / "does-not-exist", T5)
    check("빌드 없음", r5b["built"], False)
    check("빌드 없으면 막다름 비움", r5b["dead_ends"], [])

print("d4_eeat")
from portfolio import d4_eeat, PRIMARY_SOURCE_HOSTS  # noqa: E402

check("1차 출처 호스트 여섯", len(PRIMARY_SOURCE_HOSTS), 6)
check("bok.or.kr 포함", "bok.or.kr" in PRIMARY_SOURCE_HOSTS, True)
check("kfb.or.kr 포함", "kfb.or.kr" in PRIMARY_SOURCE_HOSTS, True)

from portfolio import _is_primary_source  # noqa: E402

check("정확 일치", _is_primary_source("kosis.kr"), True)
check("www. 접미 일치", _is_primary_source("www.kosis.kr"), True)
check("서브도메인 접미 일치", _is_primary_source("ecos.bok.or.kr"), True)
check("서브도메인 접미 일치 (kfb)", _is_primary_source("portal.kfb.or.kr"), True)
check("포트 제거", _is_primary_source("kosis.kr:443"), True)
check("남의 도메인 접미 오탐 없음", _is_primary_source("notkosis.kr"), False)
check("무관 호스트", _is_primary_source("hankyung.com"), False)

from portfolio import _meta_author  # noqa: E402

check("속성 순서 무관", _meta_author("<meta content=홍길동 name=author>"),
      (True, True))
check("홑따옴표 값", _meta_author("<meta name='author' content='홍길동'>"),
      (True, True))
check("minify 빈 값은 태그만 True",
      _meta_author("<meta name=author content>"), (True, False))
check("author 아닌 meta 무시",
      _meta_author("<meta name=description content=설명>"), (False, False))

MINI_POST = (
    '<head><meta name=author content><script type=application/ld+json>'
    '{"@type":"BreadcrumbList","itemListElement":[]}</script>'
    '<script type=application/ld+json>'
    '{"@type":"BlogPosting","headline":"가","publisher":{"name":"나"}}</script></head>'
)
# 속성 순서가 뒤집히고 홑따옴표를 쓴 형태 — 정규식이 name= 을 먼저 요구하면 놓친다
MINI_POST_REORDERED = (
    "<head><meta charset=utf-8><meta property=og:x content "
    "name='author'><script type=application/ld+json>"
    '{"@type":"BlogPosting","headline":"나"}</script></head>'
)
D4DOCS = [
    doc("p1", "posts", 100, source=True,
        body="근거는 [ECOS](https://ecos.bok.or.kr/x)와 [한경](https://hankyung.com/y).\n"),
    doc("p2", "posts", 100, source=True, body="링크 없음.\n"),
    doc("t1", "dictionary", 100, tags=["용어사전"],
        body="[FRED](https://fred.stlouisfed.org/z) 참고. `https://kosis.kr/q`\n"
             "[KOSIS](https://www.kosis.kr/w) 접미 일치.\n"),
]
with tempfile.TemporaryDirectory() as tmp:
    root, pub = _P(tmp) / "content", _P(tmp) / "public"
    root.mkdir()
    (root / "about.md").write_text("---\ntitle: a\n---\n", encoding="utf-8")
    (root / "privacy.md").write_text("---\ntitle: p\n---\n", encoding="utf-8")
    (pub / "posts" / "p1").mkdir(parents=True)
    (pub / "posts" / "p1" / "index.html").write_text(MINI_POST, encoding="utf-8")
    (pub / "posts" / "p2").mkdir(parents=True)
    (pub / "posts" / "p2" / "index.html").write_text(
        MINI_POST_REORDERED, encoding="utf-8")

    r4 = d4_eeat(D4DOCS, root, 'baseURL = "https://x/"\ntitle = "t"\n', pub)
    check("hugo author 미설정", r4["hugo_author"], False)
    check("표본 한 장이 아니라 전 페이지", r4["meta_author"]["pages"], 2)
    # 속성 순서가 뒤집힌 두 번째 페이지도 태그로 잡혀야 한다
    check("meta author 태그 전 페이지 존재", r4["meta_author"]["tag"], True)
    check("태그 페이지 수", r4["meta_author"]["tag_pages"], 2)
    check("meta author 값 비어 있음", r4["meta_author"]["value_nonempty"], False)
    check("값 있는 페이지 0", r4["meta_author"]["value_nonempty_pages"], 0)
    check("BlogPosting 발견(2번째 블록)", r4["jsonld_blogposting"]["present"], True)
    check("author 키 없음", r4["jsonld_blogposting"]["author_key"], False)
    check("ld+json 블록 수(표본)", r4["jsonld_blogposting"]["blocks"], 2)
    check("about 있음", r4["policy_pages"]["about"], True)
    check("contact 없음", r4["policy_pages"]["contact"], False)
    check("1차 출처 총합", r4["primary_source_links"]["total"], 3)
    check("포스트 쪽", r4["primary_source_links"]["posts"], 1)
    check("사전 쪽(www. 접미 일치 포함)",
          r4["primary_source_links"]["dictionary"], 2)
    check("코드스팬 URL 미집계",
          r4["primary_source_links"]["per_file"]["content/dictionary/t1.md"], 2)

    # 한 장만 어긋나도 불리언은 False — 표본 추출이면 영영 못 본다
    (pub / "posts" / "p3").mkdir(parents=True)
    (pub / "posts" / "p3" / "index.html").write_text(
        "<head><title>슬롯 없음</title></head>", encoding="utf-8")
    r4c = d4_eeat(D4DOCS, root, 'title = "t"\n', pub)
    check("한 장이 어긋나면 tag False", r4c["meta_author"]["tag"], False)
    check("어긋난 장을 카운트로 노출", r4c["meta_author"]["tag_pages"], 2)
    check("페이지 수 3", r4c["meta_author"]["pages"], 3)
    check("BlogPosting도 전 페이지 기준",
          r4c["jsonld_blogposting"]["present"], False)
    check("present_pages", r4c["jsonld_blogposting"]["present_pages"], 2)

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
# corpus.site_age(포스트만·welcome.md 제외)와 분모가 달라 이름을 분리했다
check("코퍼스 연령", r5d["corpus_age"], 206)
check("site_age 키를 쓰지 않는다", "site_age" in r5d, False)
check("시의성 총수", r5d["timely_total"], 2)
check("90일 경과", r5d["aged_90"], 1)
check("비율", r5d["ratio"], 0.5)
check("경과 파일", r5d["aged_files"], ["content/posts/old.md"])

check("빈 코퍼스 0 나눗셈", d5_decay([], "2026-07-26")["ratio"], 0.0)
check(
    "잘못된 날짜 예외 회피",
    d5_decay([dated("invalid", "posts", "TBD", source=True)], "2026-07-26")[
        "corpus_age"
    ],
    0,
)

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

print("snapshot")
from portfolio import SNAPSHOT_KEYS, snapshot  # noqa: E402

AXES = {
    "D1": {"mass": {"evergreen_ratio": 0.26}},
    "D2": {"used": 11},
    "D3_source": {"links_per_post": {"median": 3}, "self_reference": ["gdi"]},
    "D3_render": {"built": True, "dead_ends": []},
    "D4": {"primary_source_links": {"total": 1}},
    "D5": {"ratio": 0.0},
    "D6": {"all_met": True},
}
snap = snapshot(AXES)
check("스냅샷 키 여덟", tuple(snap), SNAPSHOT_KEYS)
check("D1 비율", snap["d1_evergreen_mass_ratio"], 0.26)
check("자기참조는 개수로", snap["d3_self_reference"], 1)
check("막다름은 개수로", snap["d3_dead_ends"], 0)
check("D6 불리언", snap["d6_all_met"], True)
# 빌드가 없으면 0이 아니라 None — "0건"과 "미측정"을 구분해야 한다
unbuilt = snapshot({**AXES, "D3_render": {"built": False, "dead_ends": []}})
check("미측정은 None", unbuilt["d3_dead_ends"], None)

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")
