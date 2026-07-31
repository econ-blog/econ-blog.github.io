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

    def test_strip_front_matter_and_chunking(self):
        from telegram_notify import strip_front_matter, chunk_text, TELEGRAM_TEXT_LIMIT
        raw = '---\ntitle: "T"\ndraft: true\n---\n\n첫 문단.\n\n둘째 문단.\n'
        body = strip_front_matter(raw).strip()
        self.assertFalse(body.startswith("---"))
        self.assertNotIn("draft: true", body)
        self.assertTrue(body.startswith("첫 문단."))

        # 상한 이하는 한 덩어리로 남는다
        self.assertEqual(chunk_text(body), [body])

        # 문단 경계에서 나뉘고, 어떤 덩어리도 상한을 넘지 않는다
        paras = "\n\n".join(["가" * 1200 for _ in range(5)])
        chunks = chunk_text(paras)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= TELEGRAM_TEXT_LIMIT for c in chunks))

        # 단일 문단이 상한을 넘으면 그 문단만 강제로 잘린다 — 통째 실패보다 낫다
        giant = chunk_text("나" * (TELEGRAM_TEXT_LIMIT * 2 + 7))
        self.assertEqual(len(giant), 3)
        self.assertTrue(all(len(c) <= TELEGRAM_TEXT_LIMIT for c in giant))
        self.assertEqual("".join(giant), "나" * (TELEGRAM_TEXT_LIMIT * 2 + 7))

    def test_flip_front_matter_draft(self):
        from process_inbox import flip_front_matter_draft
        content = "---\ntitle: Sample\ndraft: true\n---\nHere is draft: true in body."
        updated = flip_front_matter_draft(content)
        self.assertTrue(updated.startswith("---\n"))
        self.assertIn("\n---\n", updated)
        self.assertIn("draft: false", updated.split("---")[1])
        self.assertIn("Here is draft: true in body.", updated)

    # weekly-audit.md §9-1이 지시하는 PR 본문 축자 템플릿. 이 상수와 그 절이
    # 어긋나면 알림에서 줄이 조용히 사라진다 — 양쪽을 함께 고친다.
    AUDIT_PR_BODY = """## 감사 요약
계약 위반: 1건
확정 사망 링크: 0건 / 사람 점검 필요: 2건
데이터 충분성: 미달 (발행 5 / 20건)
색인 건전성: 정상
소견: 1건 (④ 1, ⑥ 0)
새 가설 제안: 1건
─ 결정 필요 ─
* Check link X
PR 리포트: .claude/audit/audit-2026-07-30.md"""

    def test_format_audit_notification(self):
        from telegram_notify import format_audit_notification
        msg = format_audit_notification("Weekly Audit", self.AUDIT_PR_BODY,
                                        "auto/audit-2026-07-30",
                                        "https://github.com/org/repo/pull/2")
        self.assertIn("#A0730 주간 감사", msg)
        # 일곱 줄 전부가 살아남아야 한다. 하나라도 빠지면 요약이 반쪽이 된다.
        for line in ("계약 위반: 1건",
                     "확정 사망 링크: 0건 / 사람 점검 필요: 2건",
                     "데이터 충분성: 미달 (발행 5 / 20건)",
                     "색인 건전성: 정상",
                     "소견: 1건 (④ 1, ⑥ 0)",
                     "새 가설 제안: 1건",
                     "─ 결정 필요 ─"):
            self.assertIn(line, msg, f"§9-1 계약 줄이 필터를 통과하지 못했다: {line}")
        self.assertNotIn("요약 정보 없음", msg)

    def test_audit_notification_report_headings_do_not_match(self):
        """리포트 H2를 PR 본문으로 복사하면 빈 요약이 된다 — 그 실패를 고정한다.

        `## ⚠ 계약 위반`에는 콜론이 없어 필터를 통과하지 못한다. 이 테스트가
        깨지면 누군가 필터를 느슨하게 만든 것이고, 그 순간 §9-1 계약은
        "정규식이 알아서 맞춰준다"로 퇴화한다.
        """
        from telegram_notify import format_audit_notification
        report_body = "## ⚠ 계약 위반\n1건\n\n## ③ 색인 건전성\n정상"
        msg = format_audit_notification("Weekly Audit", report_body,
                                        "auto/audit-2026-07-30",
                                        "https://github.com/org/repo/pull/2")
        self.assertIn("요약 정보 없음", msg)


class TestSelectInspectUrls(unittest.TestCase):
    def test_select_top_published_urls(self):
        from select_inspect_urls import parse_post_metadata, select_top_published_urls
        content_draft = "---\ntitle: Post 1\ndate: 2026-07-28T10:00:00Z\ndraft: true\n---\nBody"
        content_published = "---\ntitle: Post 2\ndate: 2026-07-29T10:00:00Z\ndraft: false\n---\nBody"
        
        meta1 = parse_post_metadata(content_draft)
        meta2 = parse_post_metadata(content_published)
        
        self.assertTrue(meta1["draft"])
        self.assertFalse(meta2["draft"])
        self.assertEqual(meta2["date"], "2026-07-29T10:00:00Z")

        with patch.dict(os.environ, {"GSC_SITE_URL": "sc-domain:example.com"}):
            urls = select_top_published_urls("content/posts")
            if urls:
                self.assertTrue(urls[0].startswith("https://example.com/"))

    def test_fetch_gsc_parse_args(self):
        from fetch_gsc import parse_args
        opts = parse_args(["--json", "--sitemaps"])
        self.assertFalse(opts["explicit_dimensions"])
        opts_dim = parse_args(["--json", "--dimensions", "query"])
        self.assertTrue(opts_dim["explicit_dimensions"])


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


class TestAutomationAlert(unittest.TestCase):
    def test_alert_contains_workflow_reason_and_url(self):
        from telegram_notify import format_automation_alert
        msg = format_automation_alert(
            "fetch-candidates", "본문 확보 후보 0건",
            "후보 12건 중 body_ok 0건", "https://github.com/x/y/actions/runs/1")
        self.assertIn("fetch-candidates", msg)
        self.assertIn("본문 확보 후보 0건", msg)
        self.assertIn("후보 12건 중 body_ok 0건", msg)
        self.assertIn("https://github.com/x/y/actions/runs/1", msg)

    def test_alert_does_not_match_audit_summary_filter(self):
        """경보는 §9-1 PR 본문 계약과 다른 경로다. 감사 요약 필터에 걸리면 안 된다."""
        from telegram_notify import format_automation_alert, SUMMARY_LINE
        msg = format_automation_alert("fetch-candidates", "실패", "detail", "https://e.com")
        for line in msg.splitlines():
            self.assertIsNone(SUMMARY_LINE.match(line.strip()),
                              f"경보 줄이 감사 요약 매처에 걸렸다: {line}")

    @patch("telegram_notify.send_telegram_message")
    def test_main_alert_mode(self, mock_send_telegram):
        import json
        from telegram_notify import main
        creds = json.dumps({"telegram": {"bot_token": "dummy_token", "chat_id": "123456"}})
        test_args = ["telegram_notify.py", "alert", "test-workflow", "test-reason", "test-detail", "https://example.com/run/1"]
        with patch.dict(os.environ, {"CREDENTIALS_JSON": creds}), patch.object(sys, "argv", test_args):
            main()
        mock_send_telegram.assert_called_once()
        args, _ = mock_send_telegram.call_args
        self.assertEqual(args[0], "dummy_token")
        self.assertEqual(args[1], "123456")
        self.assertIn("⚠ 자동화 경보 [test-workflow]", args[2])
        self.assertIn("test-reason", args[2])
        self.assertIn("test-detail", args[2])
        self.assertIn("https://example.com/run/1", args[2])


if __name__ == "__main__":
    unittest.main()
