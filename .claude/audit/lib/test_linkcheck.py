"""골든 테스트 — linkcheck 순수 로직(네트워크 제외).

.venv/bin/python .claude/audit/lib/test_linkcheck.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkcheck import _normalize_url, classify, update_ledger  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


def R(status, final="u", error=None):
    return {"final_status": status, "final_url": final, "error": error}


print("classify")
check("404 → hard", classify(R(404)), "hard")
check("410 → hard", classify(R(410)), "hard")
check("403 → soft", classify(R(403)), "soft")
check("429 → soft", classify(R(429)), "soft")
check("500 → soft", classify(R(500)), "soft")
check("None(타임아웃) → soft", classify(R(None, error="Timeout")), "soft")
check("200 → ok", classify(R(200)), "ok")
check("301 → ok", classify(R(301)), "ok")

print("_normalize_url")
check("후행 슬래시 차이 정규화", _normalize_url("https://ecos.bok.or.kr/"), _normalize_url("https://ecos.bok.or.kr"))
check("호스트 대소문자 정규화", _normalize_url("HTTPS://ECOS.BOK.OR.KR/x"), _normalize_url("https://ecos.bok.or.kr/x"))

print("update_ledger — 하드")
led = update_ledger({}, "u1", R(404), "2026-07-25")
e = led["u1"]
check("하드 카운터 1", e["consecutive_hard_failures"], 1)
check("연성 카운터 0", e["consecutive_soft_failures"], 0)
check("하드 시작일 기록", e["hard_streak_started"], "2026-07-25")
check("first_seen", e["first_seen"], "2026-07-25")
led = update_ledger(led, "u1", R(404), "2026-07-30")
check("하드 2회 누적", led["u1"]["consecutive_hard_failures"], 2)
check("하드 시작일 유지", led["u1"]["hard_streak_started"], "2026-07-25")

print("update_ledger — 연성은 하드를 증가/리셋하지 않음 (AC #8)")
led2 = update_ledger({}, "u2", R(404), "2026-07-25")
led2 = update_ledger(led2, "u2", R(403), "2026-07-26")
check("연성 후 하드 카운터 보존", led2["u2"]["consecutive_hard_failures"], 1)
check("연성 카운터 1", led2["u2"]["consecutive_soft_failures"], 1)

print("update_ledger — 회복 시 양쪽 0")
led3 = update_ledger(led2, "u2", R(200), "2026-07-27")
check("회복 후 하드 0", led3["u2"]["consecutive_hard_failures"], 0)
check("회복 후 연성 0", led3["u2"]["consecutive_soft_failures"], 0)
check("회복 후 하드 시작일 소거", led3["u2"]["hard_streak_started"], None)

print("confirmed_dead / manual / stale")
from linkcheck import confirmed_dead, needs_manual_review, ledger_stale  # noqa: E402

dead = {"consecutive_hard_failures": 2, "hard_streak_started": "2026-07-20"}
check("하드 2회 + 5일 경과 → 확정 사망", confirmed_dead(dead, "2026-07-25"), True)
near = {"consecutive_hard_failures": 2, "hard_streak_started": "2026-07-23"}
check("하드 2회지만 간격 <5일 → 미확정", confirmed_dead(near, "2026-07-25"), False)
one = {"consecutive_hard_failures": 1, "hard_streak_started": "2026-07-01"}
check("하드 1회 → 미확정", confirmed_dead(one, "2026-07-25"), False)

check("연성 4회 → 사람 점검", needs_manual_review({"consecutive_soft_failures": 4}), True)
check("연성 3회 → 아직", needs_manual_review({"consecutive_soft_failures": 3}), False)

print("규칙 C — 연성 원인 분리 (unreachable vs http soft)")
from linkcheck import needs_runner_unreachable_review  # noqa: E402

# None(타임아웃 등) 연속 실패는 consecutive_unreachable만 올리고
# consecutive_soft_failures는 건드리지 않는다
led4 = update_ledger({}, "u4", R(None, error="Timeout"), "2026-07-25")
led4 = update_ledger(led4, "u4", R(None, error="Timeout"), "2026-07-26")
check("도달 불가 카운터 누적", led4["u4"]["consecutive_unreachable"], 2)
check("HTTP 연성 카운터는 0으로 유지", led4["u4"]["consecutive_soft_failures"], 0)

# HTTP 상태코드가 있는 연성(403 등)은 반대로 consecutive_soft_failures만 올린다
led5 = update_ledger({}, "u5", R(403), "2026-07-25")
check("HTTP 연성 카운터 누적", led5["u5"]["consecutive_soft_failures"], 1)
check("도달 불가 카운터는 0으로 유지", led5["u5"]["consecutive_unreachable"], 0)

# 두 원인이 번갈아도 서로의 카운터를 리셋하지 않는다
led6 = update_ledger({}, "u6", R(None, error="Timeout"), "2026-07-25")
led6 = update_ledger(led6, "u6", R(403), "2026-07-26")
check("도달 불가 카운터 보존(HTTP 연성 뒤에도)", led6["u6"]["consecutive_unreachable"], 1)
check("HTTP 연성 카운터 1", led6["u6"]["consecutive_soft_failures"], 1)

# hard/ok는 두 연성 카운터를 함께 리셋한다
led7 = update_ledger(led6, "u6", R(200), "2026-07-27")
check("정상 회복 시 도달 불가 카운터도 0", led7["u6"]["consecutive_unreachable"], 0)
check("정상 회복 시 HTTP 연성 카운터도 0", led7["u6"]["consecutive_soft_failures"], 0)

check("도달 불가 4회 → 러너 도달 불가 의심",
      needs_runner_unreachable_review({"consecutive_unreachable": 4}), True)
check("도달 불가 3회 → 아직",
      needs_runner_unreachable_review({"consecutive_unreachable": 3}), False)
check("키 없는 기존 원장 엔트리는 False로 안전하게 읽힌다",
      needs_runner_unreachable_review({}), False)
check("manual_review도 키 없는 엔트리를 안전하게 읽는다",
      needs_manual_review({}), False)

# 마이그레이션 없이 기존(구형) 원장 엔트리를 update_ledger에 넣어도 동작한다
old_entry_ledger = {"u7": {
    "last_status": None, "final_url": "u7", "last_checked": "2026-07-20",
    "consecutive_hard_failures": 0, "consecutive_soft_failures": 3,
    "hard_streak_started": None, "first_seen": "2026-07-01",
}}  # consecutive_unreachable 키가 아예 없다 — 실제 link-state.json 형태
led8 = update_ledger(old_entry_ledger, "u7", R(None, error="Timeout"), "2026-07-25")
check("구형 엔트리도 도달 불가 카운터가 0에서 시작해 누적된다",
      led8["u7"]["consecutive_unreachable"], 1)
check("구형 엔트리의 기존 HTTP 연성 카운터는 그대로 보존된다",
      led8["u7"]["consecutive_soft_failures"], 3)

check("빈 원장 → 정체", ledger_stale({}, "2026-07-25"), True)
fresh = {"u": {"last_checked": "2026-07-20"}}
check("5일 전 확인 → 정상", ledger_stale(fresh, "2026-07-25"), False)
old = {"u": {"last_checked": "2026-07-01"}}
check("24일 전 확인 → 정체", ledger_stale(old, "2026-07-25"), True)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")

