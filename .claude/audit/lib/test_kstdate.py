"""골든 테스트 — kstdate. UTC 러너에서 KST 날짜가 밀리지 않는지 고정한다.

.venv/bin/python .claude/audit/lib/test_kstdate.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kstdate import KST, kst_today  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


UTC = timezone.utc

print("kst_today")
# 이 버그를 만든 실제 순간: 2026-08-08 21:27 UTC = 2026-08-09 06:27 KST.
check("UTC 21:27 → 익일 KST",
      kst_today(datetime(2026, 8, 8, 21, 27, tzinfo=UTC)), "2026-08-09")
# 일 05:00 KST 루틴이 도는 구간 전체가 UTC 전날이다.
check("UTC 20:00 → 익일 KST",
      kst_today(datetime(2026, 8, 8, 20, 0, tzinfo=UTC)), "2026-08-09")
check("UTC 15:00 → 익일 KST (경계 직후)",
      kst_today(datetime(2026, 8, 8, 15, 0, tzinfo=UTC)), "2026-08-09")
check("UTC 14:59 → 같은 날 KST (경계 직전)",
      kst_today(datetime(2026, 8, 8, 14, 59, tzinfo=UTC)), "2026-08-08")
check("UTC 정오 → 같은 날 KST",
      kst_today(datetime(2026, 8, 8, 12, 0, tzinfo=UTC)), "2026-08-08")
check("KST 입력은 그대로",
      kst_today(datetime(2026, 8, 9, 6, 27, tzinfo=KST)), "2026-08-09")
# 월·연 경계에서 날짜가 아니라 달까지 넘어가는지.
check("월 경계", kst_today(datetime(2026, 7, 31, 16, 0, tzinfo=UTC)), "2026-08-01")
check("연 경계", kst_today(datetime(2026, 12, 31, 16, 0, tzinfo=UTC)), "2027-01-01")

print("offset")
check("KST는 UTC+9", KST.utcoffset(None), timedelta(hours=9))

print("naive 거절")
try:
    kst_today(datetime(2026, 8, 8, 21, 27))
    check("naive datetime은 ValueError", "예외 없음", "ValueError")
except ValueError:
    check("naive datetime은 ValueError", "ValueError", "ValueError")

print("인자 없는 호출")
today = kst_today()
check("YYYY-MM-DD 형식", len(today) == 10 and today[4] == "-" and today[7] == "-", True)
check("UTC 오늘과 최대 1일 차",
      abs((datetime.strptime(today, "%Y-%m-%d").date()
           - datetime.now(UTC).date()).days) <= 1, True)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
