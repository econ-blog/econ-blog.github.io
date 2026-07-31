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
