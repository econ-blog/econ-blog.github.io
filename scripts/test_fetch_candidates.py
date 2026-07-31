import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_candidates import (
    KST, parse_feed, within_window, cap_by_recency, kst_date_str,
)

FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>코스피 사상 첫 이틀 연속 서킷브레이커</title>
  <link>https://www.hankyung.com/article/1111</link>
  <pubDate>Fri, 31 Jul 2026 09:12:00 +0900</pubDate>
</item>
<item>
  <title><![CDATA[한국은행, 기준금리 동결]]></title>
  <link>https://www.hankyung.com/article/2222</link>
  <pubDate>Thu, 30 Jul 2026 23:00:00 +0900</pubDate>
</item>
</channel></rss>"""


class TestParseFeed(unittest.TestCase):
    def test_parses_title_link_pubdate(self):
        items = parse_feed(FEED_XML, "hankyung/economy", "한국경제")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "코스피 사상 첫 이틀 연속 서킷브레이커")
        self.assertEqual(items[0]["url"], "https://www.hankyung.com/article/1111")
        self.assertEqual(items[0]["feed"], "hankyung/economy")
        self.assertEqual(items[0]["source"], "한국경제")

    def test_unwraps_cdata(self):
        items = parse_feed(FEED_XML, "hankyung/economy", "한국경제")
        self.assertEqual(items[1]["title"], "한국은행, 기준금리 동결")

    def test_pubdate_becomes_kst_aware(self):
        items = parse_feed(FEED_XML, "hankyung/economy", "한국경제")
        dt = items[0]["published_at"]
        self.assertIsNotNone(dt.tzinfo)
        self.assertEqual(dt.astimezone(KST).hour, 9)

    def test_malformed_xml_returns_empty(self):
        self.assertEqual(parse_feed("<not xml", "x", "y"), [])

    def test_item_missing_pubdate_is_dropped(self):
        xml = ('<rss><channel><item><title>t</title>'
               '<link>https://e.com/1</link></item></channel></rss>')
        self.assertEqual(parse_feed(xml, "x", "y"), [])


class TestWindow(unittest.TestCase):
    def _item(self, hours_ago, now):
        return {"title": "t", "url": f"https://e.com/{hours_ago}",
                "published_at": now - timedelta(hours=hours_ago),
                "source": "s", "feed": "f"}

    def test_boundary_2359_kept_2401_dropped(self):
        now = datetime(2026, 7, 31, 1, 47, tzinfo=KST)
        items = [
            self._item(23.983, now),   # 23시간 59분
            self._item(24.017, now),   # 24시간 01분
        ]
        kept = within_window(items, now, hours=24)
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0]["url"].startswith("https://e.com/23"))

    def test_future_dated_item_is_kept(self):
        now = datetime(2026, 7, 31, 1, 47, tzinfo=KST)
        items = [self._item(-1, now)]
        self.assertEqual(len(within_window(items, now, hours=24)), 1)


class TestCap(unittest.TestCase):
    def test_caps_at_limit_keeping_newest(self):
        now = datetime(2026, 7, 31, 1, 47, tzinfo=KST)
        items = [{"title": str(i), "url": f"https://e.com/{i}",
                  "published_at": now - timedelta(minutes=i),
                  "source": "s", "feed": "f"} for i in range(40)]
        capped = cap_by_recency(items, limit=30)
        self.assertEqual(len(capped), 30)
        self.assertEqual(capped[0]["title"], "0")
        self.assertEqual(capped[-1]["title"], "29")

    def test_under_limit_is_untouched(self):
        now = datetime(2026, 7, 31, 1, 47, tzinfo=KST)
        items = [{"title": "a", "url": "https://e.com/a",
                  "published_at": now, "source": "s", "feed": "f"}]
        self.assertEqual(len(cap_by_recency(items, limit=30)), 1)


class TestKstDate(unittest.TestCase):
    def test_utc_1647_is_next_day_in_kst(self):
        """UTC 16:47 = KST 익일 01:47. 파일명이 KST 날짜여야 한다."""
        utc_now = datetime(2026, 7, 30, 16, 47, tzinfo=timezone.utc)
        self.assertEqual(kst_date_str(utc_now), "2026-07-31")

    def test_kst_midday_is_same_day(self):
        self.assertEqual(
            kst_date_str(datetime(2026, 7, 31, 12, 0, tzinfo=KST)), "2026-07-31")


if __name__ == "__main__":
    unittest.main()
