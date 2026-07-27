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

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
