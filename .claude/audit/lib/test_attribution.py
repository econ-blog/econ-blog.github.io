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

print("per_post_metric / ratios / adjustment")
from attribution import (  # noqa: E402
    ADJUSTMENT_TABLE, adjustment, clamp_no_gsc, decay, demote, load_history,
    per_post_metric, ratios, save_history,
)

SZ = {"a": {"c": 6, "n": 2.0}, "b": {"c": 6, "n": 4.0}, "c": {"c": 6, "n": 0.0}}
m = per_post_metric(SZ, {"a": 100.0, "b": 100.0, "c": 50.0})
check("m_g = X_g / n_g", m["a"], 50.0)
check("n_g가 크면 m_g 작다", m["b"], 25.0)
check("n_g 0이면 0", m["c"], 0.0)

r, M = ratios({"a": 90.0, "b": 30.0, "c": 30.0})
check("중앙값", M, 30.0)
check("배율 상", r["a"], 3.0)
check("배율 중앙값 그룹", r["b"], 1.0)
r_even, M_even = ratios({"a": 10.0, "b": 20.0, "c": 30.0, "d": 40.0})
check("짝수 개 중앙값은 가운데 두 값의 평균", M_even, 25.0)
check("짝수 개 배율", r_even["b"], 0.8)
check("6개 중앙값", ratios({k: v for k, v in zip("abcdef", [1.0, 2.0, 3.0, 5.0, 8.0, 13.0])})[1], 4.0)
r0, M0 = ratios({"a": 0.0, "b": 0.0})
check("M=0이면 배율 0", r0["a"], 0.0)
check("M=0 보고", M0, 0.0)

check("표 다섯 구간", len(ADJUSTMENT_TABLE), 5)
check("r=3.0 → +3", adjustment(3.0), 3)
check("r=2.9 → +2", adjustment(2.9), 2)
check("r=2.0 → +2", adjustment(2.0), 2)
check("r=1.3 → +1", adjustment(1.3), 1)
check("r=1.0 → 0", adjustment(1.0), 0)
check("r=0.7 → 0", adjustment(0.7), 0)
check("r=0.69 → -1", adjustment(0.69), -1)
check("r=0.4 → -1", adjustment(0.4), -1)
check("r=0.39 → -2", adjustment(0.39), -2)
check("r=0.0 → -2", adjustment(0.0), -2)

print("demote")
MED = {"avg_position": 20.0, "clicks_top_third": 5.0}
adj, why = demote(2, {"avg_position": 35.0, "clicks": 0}, MED)
check("양수 강등", adj, 0)
check("강등 사유 있음", why is None, False)
check("클릭 있으면 유지", demote(2, {"avg_position": 35.0, "clicks": 3}, MED)[0], 2)
check("순위 좋으면 유지", demote(2, {"avg_position": 8.0, "clicks": 0}, MED)[0], 2)
check("음수 강등", demote(-2, {"avg_position": 30.0, "clicks": 9}, MED)[0], 0)
check("음수 유지", demote(-2, {"avg_position": 30.0, "clicks": 1}, MED)[0], -2)
check("지표 없으면 강등 안 함", demote(2, {}, MED), (2, None))
check("0은 그대로", demote(0, {"avg_position": 99.0, "clicks": 0}, MED), (0, None))
check("중앙값 없으면 양수 강등 안 함",
      demote(2, {"avg_position": 35.0, "clicks": 0}, {}), (2, None))
check("중앙값 없으면 음수 강등 안 함",
      demote(-2, {"avg_position": 30.0, "clicks": 9}, {}), (-2, None))
check("강등 사유에 실제 비교값이 들어간다",
      "중앙값 20.0" in demote(2, {"avg_position": 35.0, "clicks": 0}, MED)[1], True)

print("clamp_no_gsc")
check("+3 → +1", clamp_no_gsc(3), 1)
check("-2 → -1", clamp_no_gsc(-2), -1)
check("0 유지", clamp_no_gsc(0), 0)

print("decay / load_history / save_history")
import tempfile  # noqa: E402
from pathlib import Path as _P  # noqa: E402

HIST = {"금리": {"조정치": -2, "최초부여일": "2026-01-01", "마지막감쇄일": None}}
adj, entry = decay(HIST, "금리", -2, "2026-03-15")   # 73일 경과
check("60일 넘으면 절대값 -1", adj, -1)
check("마지막감쇄일 기록", entry["마지막감쇄일"], "2026-03-15")
adj2, _ = decay({"금리": {"조정치": -2, "최초부여일": "2026-03-01",
                        "마지막감쇄일": None}}, "금리", -2, "2026-03-15")
check("60일 이내면 유지", adj2, -2)
adj3, _ = decay({"금리": {"조정치": 3, "최초부여일": "2026-01-01",
                        "마지막감쇄일": None}}, "금리", 3, "2026-07-01")
check("양수는 감쇄하지 않는다", adj3, 3)
adj4, entry4 = decay({}, "신규", -1, "2026-07-26")
check("이력 없으면 최초부여", entry4["최초부여일"], "2026-07-26")
check("최초부여 회차는 감쇄 없음", adj4, -1)
adj5, _ = decay({"금리": {"조정치": -1, "최초부여일": "2026-01-01",
                        "마지막감쇄일": None}}, "금리", -1, "2026-07-01")
check("-1은 0까지 감쇄", adj5, 0)

# 음수 → 양수 → 다시 음수: 시계가 되감기지 않으면 재진입 첫 주에 곧바로 감쇄된다
RE = {}
decay(RE, "금리", -2, "2026-01-01")
decay(RE, "금리", -2, "2026-03-15")            # 73일 → -1
decay(RE, "금리", 1, "2026-04-01")             # 음수 해제
check("양수로 풀리면 최초부여일 지워짐", RE["금리"]["최초부여일"], None)
check("양수로 풀리면 마지막감쇄일 초기화", RE["금리"]["마지막감쇄일"], None)
check("재진입 첫 회차는 감쇄 없음", decay(RE, "금리", -2, "2026-06-01")[0], -2)
check("재진입일이 새 최초부여일", RE["금리"]["최초부여일"], "2026-06-01")
check("재진입 59일째는 유지", decay(RE, "금리", -2, "2026-07-29")[0], -2)
check("재진입 60일째 감쇄", decay(RE, "금리", -2, "2026-07-31")[0], -1)

with tempfile.TemporaryDirectory() as tmp:
    p = _P(tmp) / "topic-history.json"
    check("부재 시 빈 dict", load_history(p), {})
    save_history(p, {"금리": {"조정치": -1, "최초부여일": "2026-07-26",
                            "마지막감쇄일": None}})
    check("왕복", load_history(p)["금리"]["조정치"], -1)
    check("끝에 개행", p.read_text(encoding="utf-8").endswith("\n"), True)

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")

