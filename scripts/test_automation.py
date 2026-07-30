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
        body = "First sentence. Second sentence.\n\n## 발행 전 검사\n통과"
        url = "https://github.com/org/repo/pull/1"
        msg = format_post_notification(title, body, "auto/post-2026-07-30", url)
        self.assertIn("#P0730 오늘의 포스트", msg)
        self.assertIn("발행 전 검사: 통과", msg)

        body_inline = "First sentence. Second sentence.\n\n## 발행 전 검사: 통과"
        msg_inline = format_post_notification(title, body_inline, "auto/post-2026-07-30", url)
        self.assertIn("발행 전 검사: 통과", msg_inline)

    def test_flip_front_matter_draft(self):
        from process_inbox import flip_front_matter_draft
        content = "---\ntitle: Sample\ndraft: true\n---\nHere is draft: true in body."
        updated = flip_front_matter_draft(content)
        self.assertTrue(updated.startswith("---\n"))
        self.assertIn("\n---\n", updated)
        self.assertIn("draft: false", updated.split("---")[1])
        self.assertIn("Here is draft: true in body.", updated)

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


class TestProcessInbox(unittest.TestCase):
    def test_parse_verdict_strict(self):
        from process_inbox import parse_verdict
        self.assertEqual(parse_verdict("승인"), "APPROVED")
        self.assertEqual(parse_verdict("발행"), "APPROVED")
        self.assertEqual(parse_verdict("ok"), "APPROVED")
        self.assertEqual(parse_verdict("승인 #P0730"), "APPROVED")
        self.assertEqual(parse_verdict("반려 #A0730"), "REJECTED")
        self.assertEqual(parse_verdict("반려"), "REJECTED")
        
        # Must NOT approve loose words or negations
        self.assertEqual(parse_verdict("발행 안 함"), "AMBIGUOUS")
        self.assertEqual(parse_verdict("좋아요"), "AMBIGUOUS")
        self.assertEqual(parse_verdict("괜찮네요"), "AMBIGUOUS")

    def test_match_target_pr_sequence(self):
        from process_inbox import match_target_pr
        open_prs = [
            {"number": 10, "head": {"ref": "auto/post-2026-07-30"}},
            {"number": 11, "head": {"ref": "auto/audit-2026-07-30-1430"}}
        ]
        
        # 1. Reply to message with token
        up_reply = {"message": {"reply_to_message": {"text": "#P0730 오늘의 포스트"}, "text": "승인", "chat": {"id": 12345}}}
        pr, status = match_target_pr(up_reply, open_prs)
        self.assertEqual(pr["number"], 10)
        self.assertEqual(status, "TOKEN_MATCH")

        # 2. Text token
        up_text = {"message": {"text": "승인 #A0730", "chat": {"id": 12345}}}
        pr, status = match_target_pr(up_text, open_prs)
        self.assertEqual(pr["number"], 11)
        self.assertEqual(status, "TOKEN_MATCH")

        # 3. Invalid token
        up_bad_token = {"message": {"text": "승인 #P9999", "chat": {"id": 12345}}}
        pr_bad, status_bad = match_target_pr(up_bad_token, open_prs)
        self.assertIsNone(pr_bad)
        self.assertEqual(status_bad, "TOKEN_NOT_FOUND")

        # 4. 2+ open PRs without token
        up_notoken = {"message": {"text": "승인", "chat": {"id": 12345}}}
        pr, status = match_target_pr(up_notoken, open_prs)
        self.assertIsNone(pr)
        self.assertEqual(status, "MULTIPLE_PRS_NEED_TOKEN")

        # 5. 1 open PR fallback
        pr_single, status_single = match_target_pr(up_notoken, [open_prs[0]])
        self.assertEqual(pr_single["number"], 10)
        self.assertEqual(status_single, "SINGLE_PR_FALLBACK")

    def test_telegram_offset_parsing(self):
        with patch.dict(os.environ, {"TELEGRAM_OFFSET": ""}):
            raw_offset = os.environ.get("TELEGRAM_OFFSET", "").strip()
            offset_val = int(raw_offset) if raw_offset.isdigit() else 0
            self.assertEqual(offset_val, 0)


if __name__ == "__main__":
    unittest.main()
