"""골든 테스트 — contracts. CLAUDE.md가 "조용히 깨진다"고 경고한 계약들.

.venv/bin/python .claude/audit/lib/test_contracts.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contracts import ANALYSIS_FIELDS, check_four_fields  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


print("check_four_fields")
check("필드 4개", len(ANALYSIS_FIELDS), 4)

FULL_ANALYSIS = "\n".join(f"- **{f}**: 값" for f in ANALYSIS_FIELDS)
FULL_DRAFT = "\n".join(f'- "{f}"를 반영한다.' for f in ANALYSIS_FIELDS)
check("양쪽 완비 → 위반 0", check_four_fields(FULL_ANALYSIS, FULL_DRAFT), [])

# draft가 한 필드를 소비하지 않음 → 위반 1건 (실제로 한 번 일어난 사고)
DRAFT_MISSING = "\n".join(
    f'- "{f}"를 반영한다.' for f in ANALYSIS_FIELDS if f != "자산군별 함의"
)
v = check_four_fields(FULL_ANALYSIS, DRAFT_MISSING)
check("draft 미소비 → 위반 1건", len(v), 1)
check("위반에 필드명 포함", "자산군별 함의" in v[0]["detail"], True)
check("check 라벨", v[0]["check"], "4필드")

# analysis가 방출을 중단 → 위반
ANALYSIS_MISSING = "\n".join(
    f"- **{f}**: 값" for f in ANALYSIS_FIELDS if f != "확인된 수치"
)
v2 = check_four_fields(ANALYSIS_MISSING, FULL_DRAFT)
check("analysis 미방출 → 위반 1건", len(v2), 1)
check("방출 쪽 위반 문구", "방출" in v2[0]["detail"], True)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
