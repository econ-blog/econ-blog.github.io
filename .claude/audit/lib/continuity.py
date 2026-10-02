"""발행 연속성 — 결번·보류 초안을 결정론적으로 센다. (C1~C3)

**왜 검사기가 필요한가.** 이 축은 2026-09-27 회차 4까지 산문 지시로만 있었다
(`health-check.md` §1b·§2의 "최근 14일 발행 건수, 결번 날짜"). 결과는 회차 1이 이미
증명한 그대로였다 — 2026-09-21 KST에 발행 커밋이 아예 없었는데, **같은 날 06:00에 돈
회차 3이 「발행 39일 연속 결번 0건」이라고 적었다.** 검사기가 붙은 규칙은 즉시 수렴하고
안 붙은 규칙은 문구가 아무리 강해도 무작위로 어겨진다(회차 1의 인과). 연속성은 이
블로그의 유일한 산출 지표인데 그것을 눈으로 셌다.

세 축:
  C1 결번   — 발행 주기 한 칸(기본 7일) 안에 `date`가 하나도 없는 구간. 발행도 보류도 없던 칸이다.
  C2 보류   — `draft: true`로 남은 글. 3건 이상이면 게이트가 상시로 걸린다는 신호다.
  C3 정지   — 마지막 발행으로부터 며칠 지났나. 14일 이상이면 ④ 중대 고장이다.

2026-10-02 사람이 발행을 매일에서 주 1회(월 05:00 KST)로 바꿨다. 그 전처럼 하루 단위로
세면 글이 없는 엿새가 매주 결번으로 잡힌다. 그래서 창을 주기(`cadence_days`) 단위 칸으로
자르고, 칸 안에 글이 하나라도 있으면 결번이 아니다. 매일 발행하던 과거 구간은 어느 칸에나
글이 있으므로 그대로 통과한다. `--cadence 1`이면 예전과 같은 하루 단위 판정이다.

규약: 표준 라이브러리 + 정규식만. 네트워크를 쓰지 않는다.

사용:
    .venv/bin/python .claude/audit/lib/continuity.py            # 최근 35일, 7일 칸
    .venv/bin/python .claude/audit/lib/continuity.py --days 14 --cadence 7
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kstdate import kst_today  # noqa: E402

DRAFT = re.compile(r"^draft:\s*(true|false)\s*$", re.MULTILINE)
DATE = re.compile(r'^date:\s*"?(\d{4}-\d{2}-\d{2})', re.MULTILINE)

_REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = (
    _REPO_ROOT / "content" if (_REPO_ROOT / "content").exists() else Path("content")
)
EXCLUDE = {"_index.md", "welcome.md"}

# 발행 주기(일). 주 1회 발행이다.
CADENCE_DAYS = 7
# 발행이 이만큼 멈추면 ④ 중대 고장 — 주 1회 기준 두 번 연속 결번이다.
# `health-check.md` notification_policy 와 같은 값이다.
STALL_ALERT_DAYS = 14
# 보류가 이만큼 쌓이면 게이트가 상시로 걸린다는 뜻. §2 가 쓰는 값이다.
HELD_ALERT = 3
# 월 1회 점검이 지난 한 달을 덮도록 5주.
DEFAULT_WINDOW = 35


def _posts(content_root: Path) -> list[dict]:
    """포스트별 `date`·`draft`. 결번 판정은 발행분과 보류분을 함께 본다 —
    보류된 날은 「그날 글이 나왔지만 게이트가 막은 것」이고 결번은 「아무것도 없는 것」이라
    원인이 다르다."""
    out = []
    for md in sorted((content_root / "posts").glob("*.md")):
        if md.name in EXCLUDE or md.name.startswith("_"):
            continue
        text = md.read_text(encoding="utf-8")
        dm, tm = DATE.search(text), DRAFT.search(text)
        if not dm:
            continue
        out.append({
            "file": md.name,
            "date": dm.group(1),
            "draft": bool(tm) and tm.group(1) == "true",
        })
    return out


def gaps(content_root: Path = CONTENT_ROOT, today: str | None = None,
         days: int = DEFAULT_WINDOW, cadence_days: int = CADENCE_DAYS) -> dict:
    """오늘부터 `days`일 거슬러 본 연속성.

    `today` 자체는 결번으로 세지 않는다 — 05:00 KST 발행 전에 돌면 오늘은 아직
    비어 있는 것이 정상이고, 그것을 고장으로 부르면 발행일 새벽마다 거짓 경보가 된다.
    창은 어제부터 거꾸로 `cadence_days`일씩 칸으로 자르고, 끝에 남는 짧은 칸은 버린다
    (칸이 덜 찼는데 결번이라 부르면 거짓 경보다).
    """
    today = today or kst_today()
    t = date.fromisoformat(today)
    posts = _posts(content_root)
    by_date: dict[str, list[dict]] = {}
    for p in posts:
        by_date.setdefault(p["date"], []).append(p)

    window = [(t - timedelta(days=i)).isoformat() for i in range(1, days + 1)]
    missing = []
    for k in range(days // cadence_days):
        span = window[k * cadence_days:(k + 1) * cadence_days]
        if not any(d in by_date for d in span):
            missing.append(span[0] if cadence_days == 1 else f"{span[-1]}~{span[0]}")
    missing.sort()
    held = sorted(p["file"] for p in posts if p["draft"])
    held_in_window = sorted(
        p["file"] for p in posts if p["draft"] and p["date"] in window
    )

    live_dates = [p["date"] for p in posts if not p["draft"]]
    last_live = max(live_dates) if live_dates else None
    stall = (t - date.fromisoformat(last_live)).days if last_live else None

    findings = []
    for d in missing:
        findings.append({"check": "C1", "at": d,
                         "why": "발행도 보류도 없는 주기 — 후보 8점 미만이었나, "
                                "수집·세션이 안 돌았나, 계정 사용 한도에 막혔나를 갈라 적는다"})
    if len(held) >= HELD_ALERT:
        findings.append({"check": "C2", "at": f"{len(held)}건",
                         "why": f"보류 초안 {len(held)}건 >= {HELD_ALERT}건 — "
                                "게이트가 빡빡한 것인지 글이 나쁜 것인지 갈라 적는다"})
    if stall is not None and stall >= STALL_ALERT_DAYS:
        findings.append({"check": "C3", "at": last_live,
                         "why": f"마지막 발행으로부터 {stall}일 — "
                                f"{STALL_ALERT_DAYS}일 이상은 중대 고장이다"})

    return {
        "today": today,
        "window_days": days,
        "cadence_days": cadence_days,
        "missing": missing,
        "missing_count": len(missing),
        "held": held,
        "held_count": len(held),
        "held_in_window": held_in_window,
        "last_published": last_live,
        "stall_days": stall,
        "findings": findings,
        "total": len(findings),
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    days = DEFAULT_WINDOW
    cadence = CADENCE_DAYS
    today = None
    if "--days" in argv:
        i = argv.index("--days")
        if i + 1 >= len(argv):
            sys.exit("usage: continuity.py [--days N] [--cadence N] [--date YYYY-MM-DD]")
        days = int(argv[i + 1])
    if "--date" in argv:
        i = argv.index("--date")
        if i + 1 >= len(argv):
            sys.exit("usage: continuity.py [--days N] [--cadence N] [--date YYYY-MM-DD]")
        today = argv[i + 1]
    if "--cadence" in argv:
        i = argv.index("--cadence")
        if i + 1 >= len(argv):
            sys.exit("usage: continuity.py [--days N] [--cadence N] [--date YYYY-MM-DD]")
        cadence = int(argv[i + 1])
    print(json.dumps(gaps(CONTENT_ROOT, today, days, cadence), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
