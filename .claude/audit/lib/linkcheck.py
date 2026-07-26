"""외부 링크 조회 + 링크 상태 원장.

네트워크 함수(check_url)만 requests를 쓴다 — 결정론과 무관한 경계.
분류·원장 갱신·판정은 순수 함수이며 stdlib이고 테스트 대상이다.

사용:
    .venv/bin/python .claude/audit/lib/linkcheck.py <ledger.json> <url>...
"""
import json
import sys
import time
from datetime import date
from urllib.parse import urlparse

import requests


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


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def confirmed_dead(entry: dict, today: str) -> bool:
    """하드 2회 이상 + 하드 연속 시작으로부터 5일 이상. 수정 대상. (AC #9)"""
    if entry.get("consecutive_hard_failures", 0) < 2:
        return False
    start = entry.get("hard_streak_started")
    if not start:
        return False
    return _days(today, start) >= 5


def needs_manual_review(entry: dict) -> bool:
    """연성 4회 연속 → 리포트 사람 점검 섹션. 자동 수정 안 함. (AC #10)"""
    return entry.get("consecutive_soft_failures", 0) >= 4


def ledger_stale(ledger: dict, today: str) -> bool:
    """최신 확인이 14일 초과 경과 또는 원장 없음 → 2-strike 판정 불가 경고. (AC #13)"""
    if not ledger:
        return True
    checked = [e["last_checked"] for e in ledger.values() if e.get("last_checked")]
    if not checked:
        return True
    return _days(today, max(checked)) > 14


UA = "Mozilla/5.0 (compatible; econ-blog-audit/1.0; +https://github.com)"


def check_url(url: str, timeout: int = 10) -> dict:
    """HEAD→(405/501 시)GET. 리다이렉트 ≤5 추적, 최종 상태 반환. (AC #7)

    네트워크 함수. 결정론 규약 밖이며 단위 테스트하지 않는다 — Task 14 스모크가
    저장소의 실제 외부 링크로 검증한다.
    """
    s = requests.Session()
    s.max_redirects = 5
    s.headers["User-Agent"] = UA
    try:
        r = s.head(url, allow_redirects=True, timeout=timeout)
        if r.status_code in (405, 501):
            r = s.get(url, allow_redirects=True, timeout=timeout, stream=True)
        return {"final_status": r.status_code, "final_url": r.url, "error": None}
    except requests.TooManyRedirects:
        return {"final_status": None, "final_url": url, "error": "too_many_redirects"}
    except requests.RequestException as exc:
        return {"final_status": None, "final_url": url, "error": type(exc).__name__}


def check_all(ledger: dict, urls: list[str], today: str, min_interval: float = 1.0) -> dict:
    """호스트당 ≥min_interval초 간격 순차 조회. 원장을 갱신해 반환한다. (Constraints)"""
    last_hit: dict = {}
    for url in urls:
        host = urlparse(url).netloc
        prev = last_hit.get(host)
        if prev is not None:
            wait = min_interval - (time.monotonic() - prev)
            if wait > 0:
                time.sleep(wait)
        result = check_url(url)
        last_hit[host] = time.monotonic()
        update_ledger(ledger, url, result, today)
    return ledger


if __name__ == "__main__":
    ledger_path = sys.argv[1]
    urls = sys.argv[2:]
    today = date.today().isoformat()
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            ledger = json.load(fh)
    except FileNotFoundError:
        ledger = {}
    stale_before = ledger_stale(ledger, today)
    check_all(ledger, urls, today)
    with open(ledger_path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2, sort_keys=True)
    summary = {
        "ledger_was_stale": stale_before,
        "confirmed_dead": [u for u, e in ledger.items() if confirmed_dead(e, today)],
        "manual_review": [u for u, e in ledger.items() if needs_manual_review(e)],
        "moved": [
            {"url": u, "final_url": e["final_url"]}
            for u, e in ledger.items()
            if e.get("final_url") and e["final_url"] != u and classify(
                {"final_status": e["last_status"]}
            ) == "ok"
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


