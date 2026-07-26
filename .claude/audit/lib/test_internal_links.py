"""골든 테스트 — internal_links.

.venv/bin/python .claude/audit/lib/test_internal_links.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from internal_links import load_terms  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


print("load_terms")
SAMPLE = (
    'base-rate:\n  title: "기준금리"\n  aliases: ["정책금리", "기준 금리"]\n'
    'per:\n  title: "주가수익비율"\n  aliases: ["PER", "P/E"]\n'
)
t = load_terms(SAMPLE)
check("슬러그 2개", sorted(t.keys()), ["base-rate", "per"])
check("title 파싱", t["base-rate"]["title"], "기준금리")
check("aliases 파싱", t["base-rate"]["aliases"], ["정책금리", "기준 금리"])
check("aliases 없는 형태도 허용", load_terms("x:\n  title: \"y\"\n")["x"]["aliases"], [])

raised = False
try:
    load_terms('base-rate:\n  garbage line without colon structure\n')
except ValueError:
    raised = True
check("구조 위반 시 ValueError", raised, True)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
