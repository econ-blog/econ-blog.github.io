"""골든 테스트 — attribution(② 게이트·배분·조정치·감쇄).

.venv/bin/python .claude/audit/lib/test_attribution.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attribution import (  # noqa: E402
    CORPUS_MIN_AGE, CORPUS_MIN_GROUPS, CORPUS_MIN_POSTS, SIGNAL_MIN_IMPRESSIONS,
    SIGNAL_MIN_POSTS, SIGNAL_MIN_SESSIONS, corpus_gate, group_sizes, signal_groups,
)

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


print("상수")
check("말뭉치 20건", CORPUS_MIN_POSTS, 20)
check("말뭉치 28일", CORPUS_MIN_AGE, 28)
check("말뭉치 3군", CORPUS_MIN_GROUPS, 3)
check("신호 5건", SIGNAL_MIN_POSTS, 5)
check("신호 노출 300", SIGNAL_MIN_IMPRESSIONS, 300)
check("신호 세션 30", SIGNAL_MIN_SESSIONS, 30)

print("group_sizes")
POSTS = [
    {"file": "a.md", "date": "2026-07-18", "tags": ["금리", "부동산"]},
    {"file": "b.md", "date": "2026-07-19", "tags": ["금리", "물가"]},
    {"file": "c.md", "date": "2026-07-20", "tags": ["금리", "에너지", "공급망"]},
    {"file": "d.md", "date": "2026-07-21", "tags": []},
]
sizes = group_sizes(POSTS)
check("c_g 원시 개수", sizes["금리"]["c"], 3)
check("n_g 분수 배분", sizes["금리"]["n"], 1.333)   # 1/2 + 1/2 + 1/3
check("단일 태그 그룹 c", sizes["에너지"]["c"], 1)
check("단일 태그 그룹 n", sizes["에너지"]["n"], 0.333)
check("태그 없는 포스트 무시", "" in sizes, False)
check("그룹 수", len(sizes), 5)

print("signal_groups")
SIZES = {"금리": {"c": 6, "n": 2.5}, "물가": {"c": 4, "n": 1.5},
         "에너지": {"c": 7, "n": 3.0}}
METRICS = {"금리": {"impressions": 400.0, "sessions": 12.0},
           "물가": {"impressions": 900.0, "sessions": 90.0},
           "에너지": {"impressions": 120.0, "sessions": 55.0}}
gsc = signal_groups(SIZES, METRICS, has_gsc_data=True)
check("c 충족 + 노출 충족", gsc["금리"], True)
check("c 미달이면 노출 충족도 탈락", gsc["물가"], False)
check("c 충족 + 노출 미달", gsc["에너지"], False)
ga = signal_groups(SIZES, METRICS, has_gsc_data=False)
check("GSC 없으면 세션 기준", ga["금리"], False)     # 세션 12 < 30
check("GSC 없이 세션 충족", ga["에너지"], True)      # 세션 55 ≥ 30
check("지표 없는 그룹은 False", signal_groups(SIZES, {}, True)["금리"], False)

print("corpus_gate")
g = corpus_gate(9, 8, 0)
check("전부 미달", g["passed"], False)
check("조건 3개", len(g["conditions"]), 3)
check("발행 현재값", g["conditions"][0]["current"], 9)
check("발행 목표값", g["conditions"][0]["target"], 20)
check("발행 미달", g["conditions"][0]["met"], False)
check("경계 통과", corpus_gate(20, 28, 3)["passed"], True)
check("하나만 미달이면 실패", corpus_gate(20, 27, 3)["passed"], False)
check("초과는 통과", corpus_gate(50, 90, 6)["passed"], True)

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")
