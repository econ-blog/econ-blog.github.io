"""골든 테스트 — linkcheck 순수 로직(네트워크 제외).

.venv/bin/python .claude/audit/lib/test_linkcheck.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkcheck import classify, update_ledger  # noqa: E402

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

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
