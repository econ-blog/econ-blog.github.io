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
    "# 주석 라인 무시 확인\n"
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

print("resolve_internal")
from pathlib import Path as _P  # noqa: E402
from internal_links import resolve_internal, scan_broken  # noqa: E402

TERMS = load_terms(SAMPLE)
check("사전 슬러그 해소", resolve_internal("/dictionary/base-rate/", _P("content"), TERMS), True)
check("앵커 제거 후 해소", resolve_internal("/dictionary/per/#x", _P("content"), TERMS), True)
check("쿼리 스트링 제거 후 해소", resolve_internal("/dictionary/base-rate/?ref=header", _P("content"), TERMS), True)
check("없는 슬러그 미해소", resolve_internal("/dictionary/nope/", _P("content"), TERMS), False)
check("사이트 루트 해소", resolve_internal("/", _P("content"), TERMS), True)

print("scan_broken (실제 content)")
REAL = load_terms(open("content/dictionary/_terms.yaml").read())
broken = scan_broken(_P("content"), REAL)
check("실제 저장소 깨진 내부링크 0건", broken, [])

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
