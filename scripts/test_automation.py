import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestScriptWireup(unittest.TestCase):
    def test_fetch_ga4_credentials_wireup(self):
        import fetch_ga4
        with patch.dict(os.environ, {"GA4_CREDENTIALS": "/tmp/custom_ga4.json"}):
            self.assertEqual(fetch_ga4.get_credentials_path(), "/tmp/custom_ga4.json")

    def test_fetch_gsc_credentials_and_site_url_wireup(self):
        import fetch_gsc
        with patch.dict(os.environ, {"GSC_CREDENTIALS": "/tmp/custom_gsc.json", "GSC_SITE_URL": "sc-domain:example.com"}):
            self.assertEqual(fetch_gsc.get_credentials_path(), "/tmp/custom_gsc.json")
            self.assertEqual(fetch_gsc.get_site_url(), "sc-domain:example.com")


class TestTelegramNotify(unittest.TestCase):
    def test_extract_verdict_token(self):
        from telegram_notify import extract_verdict_token
        self.assertEqual(extract_verdict_token("auto/post-2026-07-30", "post"), "#P0730")
        self.assertEqual(extract_verdict_token("auto/audit-2026-07-30", "audit"), "#A0730")

    def test_format_post_notification(self):
        from telegram_notify import format_post_notification
        title = "Test Title"
        body = "First sentence. Second sentence.\n\n발행 전 검사: 통과"
        url = "https://github.com/org/repo/pull/1"
        msg = format_post_notification(title, body, "auto/post-2026-07-30", url)
        self.assertIn("#P0730 오늘의 포스트", msg)
        self.assertIn("발행 전 검사: 통과", msg)

    def test_format_audit_notification(self):
        from telegram_notify import format_audit_notification
        report = """계약 위반: 1건
확정 사망 링크: 0건 / 사람 점검 필요: 2건
데이터 충분성: 미달 (발행 5 / 20건)
색인 건전성: 정상
소견: 1건 (④ 1)
새 가설 제안: 1건
─ 결정 필요 ─
* Check link X
PR: https://github.com/org/repo/pull/2"""
        msg = format_audit_notification("Weekly Audit", report, "auto/audit-2026-07-30", "https://github.com/org/repo/pull/2")
        self.assertIn("#A0730 주간 감사", msg)
        self.assertIn("계약 위반: 1건", msg)


class TestSelectInspectUrls(unittest.TestCase):
    def test_select_top_published_urls(self):
        from select_inspect_urls import parse_post_metadata
        content_draft = "---\ntitle: Post 1\ndate: 2026-07-28T10:00:00Z\ndraft: true\n---\nBody"
        content_published = "---\ntitle: Post 2\ndate: 2026-07-29T10:00:00Z\ndraft: false\n---\nBody"
        
        meta1 = parse_post_metadata(content_draft)
        meta2 = parse_post_metadata(content_published)
        
        self.assertTrue(meta1["draft"])
        self.assertFalse(meta2["draft"])
        self.assertEqual(meta2["date"], "2026-07-29T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
