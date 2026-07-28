"""골든 테스트 — quality (Q1·Q3·Q4·Q5·P2).

.venv/bin/python .claude/audit/lib/test_quality.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality import front_matter_issues  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


DESC = "이것은 오십 자 이상 백육십 자 이하의 적정 길이 설명문입니다. 경제 뉴스를 쉽게 풀어 설명하는 문장을 담고 있습니다."

FULL_POST = (
    "---\n"
    'title: "제목"\n'
    "date: 2026-07-21T19:30:00+09:00\n"
    f'description: "{DESC}"\n'
    'tags: ["금리"]\n'
    "draft: false\n"
    'source_url: "https://a.com/x"\n'
    "---\n\n본문\n"
)


def write(tmp, sub, name, text):
    d = Path(tmp) / sub
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


print("front_matter_issues — 포스트")
with tempfile.TemporaryDirectory() as tmp:
    ok_post = write(tmp, "posts", "a.md", FULL_POST)
    check("완비 → 결함 0", front_matter_issues(ok_post), [])

    no_src = write(tmp, "posts", "b.md", FULL_POST.replace(
        'source_url: "https://a.com/x"\n', ""))
    check("source_url 누락 감지", any("source_url" in i for i in front_matter_issues(no_src)), True)

    short = write(tmp, "posts", "c.md", FULL_POST.replace(DESC, "짧은 설명"))
    check("description 짧음 감지", any("description" in i for i in front_matter_issues(short)), True)

    long_desc = write(tmp, "posts", "d.md", FULL_POST.replace(DESC, "가" * 200))
    check("description 김 감지", any("description" in i for i in front_matter_issues(long_desc)), True)

    print("front_matter_issues — 공지 예외")
    notice = write(tmp, "posts", "welcome.md",
                   '---\ntitle: "공지"\ndate: 2026-07-18T09:00:00+09:00\n'
                   'tags: ["공지"]\ndraft: false\n---\n\n본문\n')
    check("공지는 source_url·description 면제", front_matter_issues(notice), [])

    print("front_matter_issues — 사전")
    dict_ok = write(tmp, "dictionary", "cofix.md",
                    "---\n"
                    'title: "코픽스"\n'
                    "date: 2026-07-21T19:30:00+09:00\n"
                    f'description: "{DESC}"\n'
                    'tags: ["용어사전"]\n'
                    "draft: false\n---\n\n본문\n")
    check("사전은 source_url 면제", front_matter_issues(dict_ok), [])

print("stale_drafts (Q4)")
from quality import stale_drafts, self_review_budget, internal_link_density  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(tmp, "posts", "old-draft.md",
          '---\ntitle: "x"\ndate: 2026-07-01T00:00:00+09:00\n'
          'tags: ["금리"]\ndraft: true\n---\n\n본문\n')
    write(tmp, "posts", "new-draft.md",
          '---\ntitle: "y"\ndate: 2026-07-24T00:00:00+09:00\n'
          'tags: ["금리"]\ndraft: true\n---\n\n본문\n')
    write(tmp, "posts", "published.md", FULL_POST)
    st = stale_drafts(root, "2026-07-25")
    check("7일 이상 방치만", [s["file"] for s in st], ["old-draft.md"])
    check("경과일 계산", st[0]["age"], 24)

print("self_review_budget (Q5)")
WS5 = "## AI 흔적 자가검토\n1. a\n2. b\n3. c\n"
b = self_review_budget(WS5)
check("항목 수", b["count"], 3)
check("예산", b["budget"], 12)
check("잔량", b["remaining"], 9)

print("internal_link_density (P2)")
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(tmp, "posts", "two.md", FULL_POST.replace(
        "본문\n", "[a](/dictionary/base-rate/) [b](/dictionary/per/)\n"))
    write(tmp, "posts", "zero.md", FULL_POST)
    d = internal_link_density(root)
    per = {x["file"]: x["internal_links"] for x in d["per_post"]}
    check("링크 2건 문서", per["two.md"], 2)
    check("링크 0건 문서", per["zero.md"], 0)
    check("무링크 포스트 목록", d["zero_link_posts"], ["zero.md"])
    check("중앙값", d["median"], 1.0)

print("term_candidates (Q3)")
from quality import term_candidates  # noqa: E402

TERMS_Q3 = {"base-rate": {"title": "기준금리", "aliases": ["정책금리"]}}
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    body = "환율 이야기. 환율 변동. 환율 전망. 기준금리 이야기."
    write(tmp, "posts", "p1.md", FULL_POST.replace("본문\n", body + "\n"))
    write(tmp, "posts", "p2.md", FULL_POST.replace("본문\n", "환율 재등장. 환율 또.\n"))
    cands = term_candidates(root, TERMS_Q3, min_posts=2, min_count=3)
    tokens = [c["token"] for c in cands]
    check("반복 토큰 후보에 포함", "환율" in tokens, True)
    check("_terms 등재 용어는 제외", "기준금리" not in tokens, True)
    hit = [c for c in cands if c["token"] == "환율"][0]
    check("등장 포스트 수", hit["posts"], 2)
    check("총 등장 수", hit["count"], 5)

    # 1개 포스트에만 있으면 탈락
    write(tmp, "posts", "p3.md", FULL_POST.replace("본문\n", "고용 고용 고용.\n"))
    tokens2 = [c["token"] for c in term_candidates(root, TERMS_Q3, 2, 3)]
    check("단일 포스트 토큰 제외", "고용" not in tokens2, True)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")

