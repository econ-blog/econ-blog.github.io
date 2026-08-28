"""격주 점검(`/health-check`)의 원장.

이 스크립트가 답하는 질문은 하나다: **이번 회차에 사람에게 월간 리포트를 보낼
차례인가?**

격주로 도는 패스에서 "한 달에 한 번"을 세는 방법은 여러 가지가 있고 대부분 틀린다.
회차 수를 세면(2회마다 1번) 격주 스케줄이 한 번 걸러질 때마다 기준이 밀리고, 날짜를
보고 판단하면("1일에 가까우면") 실행일이 며칠씩 흔들리는 실제 스케줄에서 두 번 보내거나
한 번도 안 보내는 달이 생긴다.

그래서 **달(month)을 원장에 적고 그 달에 이미 보냈는지만 본다.** 스케줄이 밀리든
당겨지든 한 달에 정확히 한 번이 되고, 회차가 통째로 걸러진 달은 그냥 건너뛴다 —
밀린 리포트를 몰아서 보내지 않는다(지난 달 현황은 이미 지난 달 이야기다).

모든 시각 판단은 KST다.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
LEDGER_PATH = ".claude/audit/health-log.json"

# 원장에 남기는 회차 기록의 상한. 넘으면 오래된 것부터 버린다 — 이 파일은 공개
# 저장소에 커밋되고 매 회차 커진다.
MAX_RUNS = 60


def kst_today() -> str:
    return datetime.now(timezone.utc).astimezone(KST).strftime("%Y-%m-%d")


def load(path: str = LEDGER_PATH) -> dict:
    """원장을 읽는다. 없거나 깨졌으면 빈 원장으로 시작한다.

    깨진 원장에서 죽지 않는 이유: 이 스크립트가 실패하면 점검 자체가 멈추는데,
    원장은 점검의 결과물이지 입력이 아니다. 최악의 경우 월간 리포트가 한 번 더
    나갈 뿐이고, 그건 점검이 멈추는 것보다 훨씬 가볍다.
    """
    if not os.path.exists(path):
        return {"last_monthly": "", "runs": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {"last_monthly": "", "runs": []}
    if not isinstance(data, dict):
        return {"last_monthly": "", "runs": []}
    data.setdefault("last_monthly", "")
    runs = data.get("runs")
    data["runs"] = runs if isinstance(runs, list) else []
    return data


def save(ledger: dict, path: str = LEDGER_PATH):
    ledger["runs"] = ledger.get("runs", [])[-MAX_RUNS:]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def monthly_due(ledger: dict, today: str) -> bool:
    """오늘이 속한 달에 아직 월간 리포트를 보내지 않았으면 True."""
    return today[:7] != (ledger.get("last_monthly") or "")


def record(ledger: dict, today: str, monthly: bool, notified: bool,
           fixes: int = 0, human_items: int = 0) -> dict:
    """회차 하나를 원장에 적는다. 같은 날 두 번 돌면 덮어쓴다(재실행이 회차를 늘리지 않는다)."""
    entry = {"date": today, "monthly_report": bool(monthly), "notified": bool(notified),
             "fixes": int(fixes), "human_items": int(human_items)}
    runs = [r for r in ledger.get("runs", []) if r.get("date") != today]
    runs.append(entry)
    ledger["runs"] = sorted(runs, key=lambda r: r.get("date", ""))
    if monthly:
        ledger["last_monthly"] = today[:7]
    return ledger


def previous_run(ledger: dict, today: str) -> dict | None:
    """오늘 이전의 가장 최근 회차. 점검이 '지난번 이후 무엇이 달라졌나'를 볼 때 쓴다."""
    past = [r for r in ledger.get("runs", []) if r.get("date", "") < today]
    return past[-1] if past else None


# 격주 = 지난 회차로부터 이만큼 지났으면 돈다. 14가 아니라 12인 이유: 트리거가 주 단위로
# 발화하므로 정확히 14일 뒤에는 발화 자체가 없다. 13일째 발화를 잡으려면 문턱이 14보다
# 낮아야 하고, 7보다는 높아야 매주 도는 것이 되지 않는다.
BIWEEKLY_MIN_GAP_DAYS = 12


def run_due(ledger: dict, today: str, min_gap_days: int = BIWEEKLY_MIN_GAP_DAYS) -> bool:
    """이번 발화에서 실제로 점검을 돌려야 하는가.

    격주 주기를 cron으로 표현하지 않고 여기서 판정한다. 표준 cron은 "2주에 한 번"을
    쓸 수 없고(요일과 일자를 같이 제한하면 AND가 아니라 OR로 해석된다), 회차 수를
    세는 방식은 발화가 한 번 걸러질 때마다 위상이 밀린다. 그래서 트리거는 매주
    발화시키고 **지난 회차로부터 며칠 지났는지**로 가른다 — 한 회차를 놓쳐도 다음
    발화가 그대로 이어받고, 위상이 영구히 어긋나지 않는다.
    """
    prev = previous_run(ledger, today)
    if prev is None:
        return True
    try:
        last = datetime.strptime(prev["date"], "%Y-%m-%d").date()
        now = datetime.strptime(today, "%Y-%m-%d").date()
    except (ValueError, KeyError, TypeError):
        # 날짜를 못 읽으면 도는 쪽을 고른다. 건너뛰면 점검이 영영 안 돌 수 있다.
        return True
    return (now - last).days >= min_gap_days


def main(argv=None):
    ap = argparse.ArgumentParser(description="격주 점검 원장")
    ap.add_argument("--path", default=LEDGER_PATH)
    ap.add_argument("--date", default="", help="KST 날짜 (기본: 오늘)")
    ap.add_argument("--record", action="store_true", help="회차를 원장에 적는다")
    ap.add_argument("--monthly", action="store_true", help="이번 회차가 월간 리포트다")
    ap.add_argument("--notified", action="store_true", help="이번 회차가 사람에게 알렸다")
    ap.add_argument("--fixes", type=int, default=0)
    ap.add_argument("--human-items", type=int, default=0)
    a = ap.parse_args(argv)

    today = a.date or kst_today()
    ledger = load(a.path)

    if a.record:
        record(ledger, today, a.monthly, a.notified, a.fixes, a.human_items)
        save(ledger, a.path)

    prev = previous_run(ledger, today)
    print(json.dumps({
        "date": today,
        "run_due": run_due(ledger, today),
        "monthly_due": monthly_due(ledger, today),
        "last_monthly": ledger.get("last_monthly", ""),
        "previous_run": prev.get("date") if prev else None,
        "runs": len(ledger.get("runs", [])),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
