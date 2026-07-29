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

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")
