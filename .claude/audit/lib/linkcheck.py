"""외부 링크 조회 + 링크 상태 원장.

네트워크 함수(check_url)만 requests를 쓴다 — 결정론과 무관한 경계.
분류·원장 갱신·판정은 순수 함수이며 stdlib이고 테스트 대상이다.

사용:
    .venv/bin/python .claude/audit/lib/linkcheck.py <ledger.json> <url>...
"""
import json
import sys
from datetime import date


def classify(result: dict) -> str:
    """최종 상태로 하드/연성/정상 분류. (AC Ontology ①)"""
    st = result["final_status"]
    if st is None:
        return "soft"  # 타임아웃·DNS·TLS·리다이렉트 초과 → 연성(자동 수정 금지)
    if st in (404, 410):
        return "hard"
    if 200 <= st < 400:
        return "ok"
    return "soft"  # 403·429·5xx 등


def update_ledger(ledger: dict, url: str, result: dict, today: str) -> dict:
    """AC #8 카운터 규칙. 원장을 제자리 갱신하고 반환한다."""
    e = ledger.get(url) or {
        "last_status": None,
        "final_url": url,
        "last_checked": None,
        "consecutive_hard_failures": 0,
        "consecutive_soft_failures": 0,
        "hard_streak_started": None,
        "first_seen": today,
    }
    kind = classify(result)
    e["last_status"] = result["final_status"]
    e["final_url"] = result["final_url"]
    e["last_checked"] = today
    if kind == "hard":
        if e["consecutive_hard_failures"] == 0:
            e["hard_streak_started"] = today
        e["consecutive_hard_failures"] += 1
        e["consecutive_soft_failures"] = 0
    elif kind == "soft":
        e["consecutive_soft_failures"] += 1
        # 하드 카운터: 증가시키지도 리셋하지도 않는다 (AC #8)
    else:  # ok
        e["consecutive_hard_failures"] = 0
        e["consecutive_soft_failures"] = 0
        e["hard_streak_started"] = None
    ledger[url] = e
    return ledger


if __name__ == "__main__":
    pass
