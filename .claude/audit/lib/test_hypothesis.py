"""골든 테스트 — hypothesis(방향 원장).

.venv/bin/python .claude/audit/lib/test_hypothesis.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypothesis import (  # noqa: E402
    FIELDS, STATES, load_ledger, next_id, record_portfolio, save_ledger, validate,
)

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


GOOD = {
    "주장": "사전 유입링크 중앙값을 3 이상으로 올리면 세션당 페이지뷰가 오른다.",
    "지표": "GA4 세션당 페이지뷰",
    "예측": "발행 20건 시점에 1.2 이상",
    "확인시점": "발행 20건",
    "기각기준": "1.1 미만이면 기각",
}

print("validate")
check("필드 다섯", FIELDS, ("주장", "지표", "예측", "확인시점", "기각기준"))
check("상태 여섯", len(STATES), 6)
check("완비 → 빈 목록", validate(GOOD), [])
missing = dict(GOOD)
del missing["기각기준"]
check("한 필드 누락", validate(missing), ["기각기준"])
blank = dict(GOOD, 예측="   ")
check("공백만도 누락", validate(blank), ["예측"])
check("빈 후보는 다섯 전부", validate({}), list(FIELDS))

print("load_ledger / save_ledger / next_id")
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "direction-log.json"
    check("부재 시 기본 골격", load_ledger(p),
          {"hypotheses": [], "portfolio_history": []})
    check("첫 id", next_id(load_ledger(p)), "H001")

    led = load_ledger(p)
    led["hypotheses"].append(dict(GOOD, id="H001", 상태="제안"))
    led["hypotheses"].append(dict(GOOD, id="H007", 상태="제안"))
    save_ledger(p, led)
    check("다음 id는 최대+1", next_id(load_ledger(p)), "H008")
    check("한글 그대로 저장", "주장" in p.read_text(encoding="utf-8"), True)
    check("끝에 개행", p.read_text(encoding="utf-8").endswith("\n"), True)

    p.write_text("{ 깨진 json", encoding="utf-8")
    try:
        load_ledger(p)
        check("파싱 실패 시 ValueError", "no raise", "ValueError")
    except ValueError:
        check("파싱 실패 시 ValueError", "ValueError", "ValueError")

print("record_portfolio")
with tempfile.TemporaryDirectory() as tmp:
    led = {"hypotheses": [], "portfolio_history": []}
    check("첫 실행은 직전값 없음",
          record_portfolio(led, {"D1": 0.27}, "2026-07-26"), None)
    prev = record_portfolio(led, {"D1": 0.31}, "2026-08-02")
    check("두 번째 실행은 직전값 반환", prev["snapshot"], {"D1": 0.27})
    check("이력 2건", len(led["portfolio_history"]), 2)
    record_portfolio(led, {"D1": 0.33}, "2026-08-02")
    check("같은 날 재실행은 덮어쓰기", len(led["portfolio_history"]), 2)
    check("덮어쓴 값", led["portfolio_history"][-1]["snapshot"], {"D1": 0.33})
    for i in range(20):
        record_portfolio(led, {"D1": i}, f"2026-09-{i + 1:02d}")
    check("이력 상한 12", len(led["portfolio_history"]), 12)

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")
