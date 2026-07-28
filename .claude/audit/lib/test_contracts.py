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

print("check_terms_sync")
import tempfile  # noqa: E402
from pathlib import Path as _P  # noqa: E402
from contracts import (  # noqa: E402
    check_terms_sync,
    count_self_review_items,
    check_self_review_budget,
    check_topic_report_format,
)

with tempfile.TemporaryDirectory() as tmp:
    d = _P(tmp)
    (d / "base-rate.md").write_text("x", encoding="utf-8")
    (d / "_index.md").write_text("x", encoding="utf-8")  # 제외 대상
    (d / "_terms.yaml").write_text("x", encoding="utf-8")  # 제외 대상
    check("일치 → 위반 0", check_terms_sync({"base-rate": {}}, d), [])

    # yaml에만 있고 파일 없음
    v = check_terms_sync({"base-rate": {}, "ghost": {}}, d)
    check("yaml 전용 항목 → 위반", len(v), 1)
    check("위반에 슬러그", "ghost" in v[0]["detail"], True)

    # 파일만 있고 yaml에 없음
    (d / "orphan.md").write_text("x", encoding="utf-8")
    v2 = check_terms_sync({"base-rate": {}}, d)
    check("파일 전용 항목 → 위반", len(v2), 1)
    check("위반에 파일명", "orphan" in v2[0]["detail"], True)

print("count_self_review_items")
WS = (
    "## 개인화 조언 금지\n무관한 내용\n\n"
    "## AI 흔적 자가검토\n설명 줄\n\n"
    "1. **예고형 서론**: a\n2. **공허한 맺음말**: b\n3. **추상 형용사**: c\n\n"
    "## 다음 섹션\n1. 여기 항목은 세지 않는다\n"
)
check("자가검토 항목 3개", count_self_review_items(WS), 3)
check("예산 내 → 위반 0", check_self_review_budget(WS, 12), [])
BIG = "## AI 흔적 자가검토\n" + "\n".join(f"{i}. 항목" for i in range(1, 14))
check("13개 → 예산 위반", len(check_self_review_budget(BIG, 12)), 1)

print("check_topic_report_format")
check("파일 부재 → 위반 0 (정상)", check_topic_report_format(None), [])
GOOD = (
    "생성일: 2026-07-25\n\n## 잘 되는 주제\n- 금리 (조정치: +2)\n\n"
    "## 안 되는 주제\n- 반도체 (조정치: -1)\n\n## 좋은 포스트의 조건\n- 조건\n"
)
check("계약 준수 → 위반 0", check_topic_report_format(GOOD), [])
check("생성일 누락 → 위반", len(check_topic_report_format("## 잘 되는 주제\n- x")) >= 1, True)
OUT_OF_RANGE = GOOD.replace("(조정치: +2)", "(조정치: +9)")
check("조정치 범위 이탈 → 위반", len(check_topic_report_format(OUT_OF_RANGE)), 1)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
