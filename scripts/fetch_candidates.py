"""후보 기사 수집 — RSS 파싱·시간창·상한·본문 추출.

판단하지 않는다. 채점·중복 판정·후속 보도 예외는 .claude/daily-post/rank.md가 한다.
네트워크 함수(fetch_url)만 requests를 쓴다 — 결정론과 무관한 경계.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))

# .claude/daily-post/rank.md §1이 유일한 진리원이다. 여기서 독자적으로 늘리지 않는다.
FEEDS_PRIMARY = [
    ("hankyung/economy", "한국경제", "https://www.hankyung.com/feed/economy"),
    ("hankyung/finance", "한국경제", "https://www.hankyung.com/feed/finance"),
    ("hankyung/realestate", "한국경제", "https://www.hankyung.com/feed/realestate"),
]

# 매일경제는 403을 반환하므로 제외한다. 한겨레는 끝 슬래시를 붙이지 않는다(308).
FEEDS_FALLBACK = [
    ("yna/economy", "연합뉴스", "https://www.yna.co.kr/rss/economy.xml"),
    ("khan/economy", "경향신문", "https://www.khan.co.kr/rss/rssdata/economy_news.xml"),
    ("donga/economy", "동아일보", "https://rss.donga.com/economy.xml"),
    ("hani/economy", "한겨레", "https://www.hani.co.kr/rss/economy"),
]

WINDOW_HOURS = 24
POOL_LIMIT = 30
FALLBACK_THRESHOLD = 10


def kst_date_str(now: datetime) -> str:
    """스냅샷 파일명용 KST 날짜. UTC 날짜를 쓰면 안 된다 — 워크플로가 UTC 16시대에 돈다."""
    return now.astimezone(KST).strftime("%Y-%m-%d")


def parse_feed(xml_text: str, feed_id: str, source: str) -> list:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub_raw = (node.findtext("pubDate") or "").strip()
        if not (title and link and pub_raw):
            continue
        try:
            published = parsedate_to_datetime(pub_raw)
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=KST)
        items.append({
            "title": title,
            "url": link,
            "published_at": published,
            "source": source,
            "feed": feed_id,
        })
    return items


def within_window(items: list, now: datetime, hours: int = WINDOW_HOURS) -> list:
    cutoff = now - timedelta(hours=hours)
    return [i for i in items if i["published_at"] > cutoff]


def cap_by_recency(items: list, limit: int = POOL_LIMIT) -> list:
    return sorted(items, key=lambda i: i["published_at"], reverse=True)[:limit]


import argparse
import json
import os
import sys
import time

BODY_MIN_CHARS = 400
FETCH_TIMEOUT = 20
USER_AGENT = "econ-blog-automation/1.0 (+https://econ-blog.github.io)"


def attach_body(item: dict, extract) -> dict:
    """본문을 붙인다. 추출기가 던지는 예외를 삼키지 않고 기록한다.

    실패를 빈 문자열로 뭉개면 body_chars 게이트가 '짧은 기사'와 '추출 실패'를
    구분하지 못한다. 둘 다 중단이지만 진단이 달라진다.
    """
    out = dict(item)
    try:
        text = extract(item["url"])
    except Exception as exc:  # 추출기 실패는 후보 폐기 사유이지 실행 중단 사유가 아니다
        out["body_text"] = ""
        out["body_chars"] = 0
        out["body_error"] = f"{type(exc).__name__}: {exc}"
        return out

    if text is None:
        out["body_text"] = ""
        out["body_chars"] = 0
        out["body_error"] = "extraction_returned_none"
        return out

    out["body_text"] = text
    out["body_chars"] = len(text)
    out["body_error"] = None
    return out


def body_ok(item: dict) -> bool:
    return item.get("body_error") is None and item.get("body_chars", 0) >= BODY_MIN_CHARS


def dedupe_by_url(items: list) -> list:
    best = {}
    for item in items:
        prev = best.get(item["url"])
        if prev is None or item["published_at"] > prev["published_at"]:
            best[item["url"]] = item
    return sorted(best.values(), key=lambda i: i["published_at"], reverse=True)


def build_snapshot(items: list, feeds_used: list, feed_errors: list, now: datetime) -> dict:
    return {
        "generated_at": now.astimezone(KST).isoformat(),
        "feeds_used": feeds_used,
        "feed_errors": feed_errors,
        "window_hours": WINDOW_HOURS,
        "candidates": [
            {
                "title": i["title"],
                "url": i["url"],
                "published_at": i["published_at"].astimezone(KST).isoformat(),
                "source": i["source"],
                "feed": i["feed"],
                "body_text": i.get("body_text", ""),
                "body_chars": i.get("body_chars", 0),
                "body_error": i.get("body_error"),
                "body_ok": body_ok(i),
            }
            for i in items
        ],
    }


def fetch_url(url: str) -> str:
    import requests
    resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def extract_body(url: str):
    import trafilatura
    html = fetch_url(url)
    return trafilatura.extract(html, include_comments=False, include_tables=False)


def collect(now: datetime, fetch=fetch_url, extract=extract_body) -> dict:
    pool, feeds_used, feed_errors = [], [], []

    for group in (FEEDS_PRIMARY, FEEDS_FALLBACK):
        for feed_id, source, url in group:
            if group is FEEDS_FALLBACK and len(pool) >= FALLBACK_THRESHOLD:
                break
            try:
                items = parse_feed(fetch(url), feed_id, source)
            except Exception as exc:
                feed_errors.append({"feed": feed_id, "error": f"{type(exc).__name__}: {exc}"})
                continue
            feeds_used.append(feed_id)
            pool.extend(within_window(items, now))
            time.sleep(1)  # 호스트당 최소 간격

    pool = cap_by_recency(dedupe_by_url(pool))
    pool = [attach_body(i, extract) for i in pool]
    return build_snapshot(pool, feeds_used, feed_errors, now)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="스냅샷을 쓸 디렉터리")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    snap = collect(now)

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"{kst_date_str(now)}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=2)

    total = len(snap["candidates"])
    usable = sum(1 for c in snap["candidates"] if c["body_ok"])
    print(json.dumps({"path": path, "total": total, "usable": usable,
                      "feed_errors": len(snap["feed_errors"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
