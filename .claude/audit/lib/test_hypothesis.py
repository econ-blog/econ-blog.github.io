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

print("종결 가설 방어")
h_done = register(led, GOOD, "2026-07-26")
resolve(h_done, "확증", "근거", "2026-07-27")
try:
    postpone(h_done, "2026-08-03", "GSC 0행")
    check("종결 가설 연기 거부", "no raise", "ValueError")
except ValueError:
    check("종결 가설 연기 거부", "ValueError", "ValueError")
check("연기횟수 안 늘어남", h_done["연기횟수"], 0)

# 손으로 만든 원장 항목에 대조이력 키가 없어도 KeyError를 내지 않는다
bare = {"id": "H900", "상태": "확인대기", "연기횟수": 0}
resolve(bare, "반증", "근거", "2026-08-03")
check("대조이력 자동 생성", len(bare["대조이력"]), 1)

print("CLI — 원장을 stdout으로만 낸다")
import subprocess  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# test_contracts.py 와 같은 이유로 `.venv` 경로를 짐작하지 않는다. 러너가 첫 실패에서
# 멈추는 탓에 2026-08-30 고장 때 이 파일은 돌지도 못했고, 앞엣것만 고쳤다면 다음 주에
# 똑같은 예외가 여기서 떴을 것이다.
PY = sys.executable
CLI = os.path.join(HERE, "hypothesis.py")


def run(*args, stdin=None):
    r = subprocess.run([PY, CLI, *args], capture_output=True, text=True,
                       input=stdin)
    if r.returncode != 0:
        raise AssertionError(f"{args} → exit {r.returncode}\n{r.stderr}")
    return json.loads(r.stdout)


with tempfile.TemporaryDirectory() as tmp:
    lp = Path(tmp) / "direction-log.json"
    save_ledger(lp, {"hypotheses": [], "portfolio_history": []})
    snap_path = Path(tmp) / "snap.json"
    # portfolio.py 전체 출력을 그대로 줘도 snapshot 키를 꺼내 쓴다
    snap_path.write_text(json.dumps(
        {"generated": "2026-07-26", "snapshot": {"d2_vocab_used": 11}}),
        encoding="utf-8")

    out = run("record", str(lp), str(snap_path), "2026-07-26",
              "n1_count=4", "claims_total=87", "claims_per_post=7.9")
    snap = out["ledger"]["portfolio_history"][-1]["snapshot"]
    check("전체 출력에서 snapshot 추출", snap["d2_vocab_used"], 11)
    check("⑥ 정수값", snap["n1_count"], 4)
    check("⑥ 실수값", snap["claims_per_post"], 7.9)
    check("첫 실행 직전값 없음", out["previous"], None)
    # 적재 후에 판정하면 최신 이력이 늘 오늘이라 경고가 영원히 null이 된다
    check("정체 경고는 적재 전 기준", out["stale"] is None, False)
    check("원장 파일은 그대로", json.loads(lp.read_text())["portfolio_history"], [])

    # ⑥ 값을 안 넘기면 키 자체가 없다 — None을 채우지 않는다
    save_ledger(lp, out["ledger"])
    fresh = run("record", str(lp), str(snap_path), "2026-07-27")
    check("직전 이력이 최신이면 경고 없음", fresh["stale"], None)
    check("직전 스냅샷 반환", fresh["previous"]["snapshot"]["n1_count"], 4)
    save_ledger(lp, {"hypotheses": [], "portfolio_history": []})

    out2 = run("record", str(lp), str(snap_path), "2026-07-26")
    snap2 = out2["ledger"]["portfolio_history"][-1]["snapshot"]
    check("⑥ 미제공이면 키 생략", "n1_count" in snap2, False)

    # 파이프: record 출력을 register가 그대로 받는다
    cand = Path(tmp) / "cand.json"
    cand.write_text(json.dumps([GOOD, dict(GOOD, 주장="둘"), dict(GOOD, 주장="셋"),
                                dict(GOOD, 주장="넷")], ensure_ascii=False),
                    encoding="utf-8")
    piped = run("register", "-", str(cand), "2026-07-26",
                stdin=json.dumps(out))
    check("상한 3건", len(piped["registered"]), 3)
    check("버린 건수", piped["dropped"], 1)
    check("이전 단계 이력 보존",
          len(piped["ledger"]["portfolio_history"]), 1)

    led_path = Path(tmp) / "l2.json"
    save_ledger(led_path, piped["ledger"])
    adopted = run("adopt", str(led_path), "H001", "2026-07-27")
    check("CLI 채택", adopted["adopted"][0]["상태"], "확인대기")
    save_ledger(led_path, adopted["ledger"])
    check("CLI due", [h["id"] for h in run("due", str(led_path), "20", "8")],
          ["H001"])
    resolved = run("resolve", str(led_path), "H001", "확증", "1.31",
                   "2026-08-30")
    check("CLI 확증", resolved["resolved"]["상태"], "확증")
    summary = run("summary", str(led_path), "2026-07-27")
    check("CLI summary 상태 집계", summary["counts_by_state"]["제안"], 2)

    # 외부 출처가 붙은 후보는 register_external 경로로 간다
    ext = Path(tmp) / "ext.json"
    ext.write_text(json.dumps(
        dict(GOOD, 출처=external_source("사용자", "2026-07-26", ["https://x/y"], 2)),
        ensure_ascii=False), encoding="utf-8")
    e2 = run("register", str(led_path), str(ext), "2026-07-26")
    check("CLI 외부 등록", e2["registered"][0]["출처"]["유형"], "외부")
    check("출처가 5필드에 섞이지 않음",
          "출처" in validate(e2["registered"][0]), False)

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")
