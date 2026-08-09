"""KST 오늘 날짜 — 감사가 찍는 날짜는 전부 여기서 나온다.

루틴 샌드박스도 GitHub Actions 러너도 UTC로 돈다. `date.today()`를 쓰면
KST 00:00–09:00 구간의 실행이 **전날** 날짜를 찍는다. 주간 감사는 일요일
05:00 KST에 돌아 정확히 그 구간에 들어가므로, 2026-08-09 06:27 KST 실행이
리포트를 `report/audit-2026-08-08.md`로 내보냈다 — 하루 밀린 이름이다.

스냅샷 파일명과 `generated_at`이 언제나 KST인 것과 같은 규약이다
(`scripts/fetch_candidates.py`의 `kst_date_str`). 저쪽은 `scripts/`,
이쪽은 `.claude/audit/lib/`이고 둘을 잇는 패키지 경로가 없어 상수를
각자 갖는다 — 값은 같아야 한다.

사용:
    .venv/bin/python .claude/audit/lib/kstdate.py   # YYYY-MM-DD (KST)
"""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def kst_today(now: datetime | None = None) -> str:
    """KST 기준 오늘을 `YYYY-MM-DD`로.

    `now`는 테스트 주입용이며 **tz-aware여야 한다.** naive datetime을 받으면
    `astimezone`이 로컬 타임존을 가정해 러너마다 답이 갈리므로 거절한다.
    """
    moment = datetime.now(timezone.utc) if now is None else now
    if moment.tzinfo is None:
        raise ValueError("naive datetime은 받지 않는다 — tz-aware로 넘긴다")
    return moment.astimezone(KST).strftime("%Y-%m-%d")


if __name__ == "__main__":
    print(kst_today())
