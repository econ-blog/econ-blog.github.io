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
    .venv/bin/python .claude/audit/lib/kstdate.py           # YYYY-MM-DD (KST)
    .venv/bin/python .claude/audit/lib/kstdate.py --stamp   # front matter 의 date: 값 그대로
"""
import sys
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


def kst_stamp(now: datetime | None = None) -> str:
    """포스트 front matter 의 `date:` 값 — `YYYY-MM-DDTHH:MM:SS+09:00`.

    2026-09-13 발행분이 `date: 2026-09-12`로 나갔다. 하루가 밀린 것도 문제지만
    진짜 문제는 **같은 날 두 건, 빈 날 하루**가 되어 발행 연속성 계측이
    결번을 잘못 세게 된 것이다. 원인은 하나다 — `draft.md`가 날짜를
    `<현재시각 KST>`라고만 적어 두고 아무 헬퍼도 부르지 않았다. 사람이든
    모델이든 손으로 적는 값은 언젠가 틀린다. 그래서 여기서 찍어 준다.

    `kst_today()`와 같은 시각을 본다 — 두 값이 갈리면 게이트(quality Q11)가
    스스로를 못 믿게 되므로 상수도 구현도 하나로 둔다.
    """
    moment = datetime.now(timezone.utc) if now is None else now
    if moment.tzinfo is None:
        raise ValueError("naive datetime은 받지 않는다 — tz-aware로 넘긴다")
    return moment.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


if __name__ == "__main__":
    print(kst_stamp() if "--stamp" in sys.argv[1:] else kst_today())
