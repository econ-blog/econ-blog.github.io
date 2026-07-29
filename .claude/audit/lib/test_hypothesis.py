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

print("register / enforce_cap")
from hypothesis import (  # noqa: E402
    PROPOSAL_CAP, adopt, current_direction, due, enforce_cap, postpone,
    register, resolve, stale_warning,
)

led = {"hypotheses": [], "portfolio_history": []}
h1 = register(led, GOOD, "2026-07-26")
check("id 부여", h1["id"], "H001")
check("초기 상태", h1["상태"], "제안")
check("제기일", h1["제기일"], "2026-07-26")
check("채택일 비움", h1["채택일"], None)
check("연기횟수 0", h1["연기횟수"], 0)
check("대조이력 빈 목록", h1["대조이력"], [])
check("원장에 들어감", len(led["hypotheses"]), 1)

try:
    register(led, {"주장": "그냥 좋아 보인다"}, "2026-07-26")
    check("미달 등록 거부", "no raise", "ValueError")
except ValueError:
    check("미달 등록 거부", "ValueError", "ValueError")

check("상한 3", PROPOSAL_CAP, 3)
kept, dropped = enforce_cap([{"n": i} for i in range(5)])
check("상위 3건만", [k["n"] for k in kept], [0, 1, 2])
check("버린 건수", dropped, 2)
check("3건 이하면 그대로", enforce_cap([{"n": 0}])[1], 0)

print("adopt / due / resolve / postpone")
h1 = adopt(h1, "2026-07-27")
check("채택 후 상태", h1["상태"], "확인대기")
check("채택일 기록", h1["채택일"], "2026-07-27")

check("발행 미달이면 미도달", due(led, 10, 8), [])
check("발행 도달", [h["id"] for h in due(led, 20, 8)], ["H001"])

h2 = register(led, dict(GOOD, 확인시점="사이트 연령 D 42일"), "2026-07-26")
h2 = adopt(h2, "2026-07-26")
check("연령 미달", [h["id"] for h in due(led, 0, 41)], [])
check("연령 도달", [h["id"] for h in due(led, 0, 42)], ["H002"])

h3 = register(led, dict(GOOD, 확인시점="분위기가 좋아질 때"), "2026-07-26")
h3 = adopt(h3, "2026-07-26")
check("파싱 불가는 미도달", [h["id"] for h in due(led, 999, 999)],
      ["H001", "H002"])

resolve(h1, "확증", "세션당 페이지뷰 1.31", "2026-08-30")
check("확증 상태", h1["상태"], "확증")
check("대조이력 1건", len(h1["대조이력"]), 1)
check("대조이력 내용", h1["대조이력"][0]["outcome"], "확증")

postpone(h2, "2026-08-30", "GSC 0행")
check("연기 1", h2["연기횟수"], 1)
check("연기 중 상태 유지", h2["상태"], "확인대기")
postpone(h2, "2026-09-06", "GSC 0행")
postpone(h2, "2026-09-13", "GSC 0행")
check("연기 3회 → 기각", h2["상태"], "기각")
check("기각 사유 고정", h2["대조이력"][-1]["evidence"], "측정 불가")

print("current_direction / stale_warning")
check("현재 방향은 채택·확인대기만",
      [h["id"] for h in current_direction(led)], ["H003"])
check("이력 없으면 경고", stale_warning(led, "2026-07-26") is None, False)
led["portfolio_history"].append({"date": "2026-07-26", "snapshot": {}})
check("최신 이력이면 경고 없음", stale_warning(led, "2026-07-26"), None)
check("14일 지나면 경고", stale_warning(led, "2026-08-20") is None, False)

print("external_source / register_external")
from hypothesis import external_source, register_external  # noqa: E402

src = external_source("사용자", "2026-07-26",
                      ["https://developers.google.com/search/docs"], 4)
check("유형 외부", src["유형"], "외부")
check("통과 URL", src["통과URL"], ["https://developers.google.com/search/docs"])
check("기각된 형제 수", src["기각된형제주장수"], 4)
check("근거미확인 기본 False", src["근거미확인"], False)
check("연성 실패 표시", external_source("사용자", "2026-07-26", [], 0,
                                    unverified=True)["근거미확인"], True)

led2 = {"hypotheses": [], "portfolio_history": []}
e = register_external(led2, GOOD, "2026-07-26", src)
check("외부 가설도 제안 상태", e["상태"], "제안")
check("출처 보존", e["출처"]["제시자"], "사용자")
try:
    register_external(led2, GOOD, "2026-07-26", {"유형": "내부"})
    check("내부 출처 거부", "no raise", "ValueError")
except ValueError:
    check("내부 출처 거부", "ValueError", "ValueError")

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")


