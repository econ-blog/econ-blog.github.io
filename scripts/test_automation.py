import os
import re
import sys
import json
import tempfile
import unittest
from datetime import timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class FakeResponse:
    """requests.Response 대역 — 상태 코드와 JSON 본문만 흉내 낸다."""

    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} error")

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
    """무인 운영 전환(2026-08-27) 이후의 발신부. 판정 토큰·승인 문구는 전부 사라졌고,
    남은 것은 통보 세 종류다."""

    HEALTH_BODY = (
        "## 점검 요약\n"
        "알림: 필요\n"
        "월간 리포트: 예\n"
        "자동 수정: 7건\n"
        "사람 작업: 2건\n"
        "발행 누계: 34건 / 색인: 12건\n"
        "GSC 28일: 클릭 41 · 노출 2,180\n"
        "─ 사람이 해야 할 일 ─\n"
        "* 색인 제출 · /posts/ymtc-nand/ · GSC 미색인 · 수집 요청\n"
        "리포트: report/health-2026-09-10.md\n"
    )

    def test_extract_block_stops_at_next_heading(self):
        from telegram_notify import extract_block
        body = "머리말\n\n## 점검 요약\n알림: 필요\n\n## 딴 절\n알림: 불필요\n"
        self.assertEqual(extract_block(body, "점검 요약"), ["알림: 필요"])

    def test_health_summary_keeps_fields_and_queue(self):
        from telegram_notify import extract_block, summarize_block
        out = summarize_block(extract_block(self.HEALTH_BODY, "점검 요약"))
        self.assertIn("자동 수정: 7건", out)
        self.assertIn("GSC 28일: 클릭 41 · 노출 2,180", out)
        self.assertIn("• 색인 제출 · /posts/ymtc-nand/", out)

    def test_routing_fields_stay_out_of_the_message(self):
        """`알림:`은 발신 스위치이고 `리포트:`는 URL로 따로 붙는다. 둘 다 사람이
        읽을 내용이 아니라 배선이다."""
        from telegram_notify import extract_block, summarize_block, field
        lines = extract_block(self.HEALTH_BODY, "점검 요약")
        shown = summarize_block(lines).splitlines()
        self.assertNotIn("알림: 필요", shown)
        self.assertNotIn("리포트: report/health-2026-09-10.md", shown)
        # 키가 정확히 일치할 때만 걸러진다 — `월간 리포트`는 살아남아야 한다.
        self.assertIn("월간 리포트: 예", shown)
        # 걸러지는 것은 표시일 뿐 — 파싱은 여전히 값을 읽어야 한다.
        self.assertEqual(field(lines, "알림"), "필요")

    def test_field_reads_one_value(self):
        from telegram_notify import extract_block, field
        lines = extract_block(self.HEALTH_BODY, "점검 요약")
        self.assertEqual(field(lines, "월간 리포트"), "예")
        self.assertEqual(field(lines, "없는 키", "기본"), "기본")

    def test_monthly_report_changes_the_headline(self):
        from telegram_notify import format_health_notification
        monthly = format_health_notification(self.HEALTH_BODY, "report/health-2026-09-10.md", "https://x/y")
        self.assertIn("📊 월간 현황 리포트", monthly)
        routine = format_health_notification(
            self.HEALTH_BODY.replace("월간 리포트: 예", "월간 리포트: 아니오"),
            "report/health-2026-09-24.md", "https://x/y")
        self.assertIn("사람 확인 필요", routine)
        self.assertNotIn("월간 현황 리포트", routine)

    def test_health_notification_survives_broken_body(self):
        from telegram_notify import format_health_notification
        msg = format_health_notification("## ⚠ 계약 위반\n1건", "report/health-2026-09-10.md", "https://x/y")
        self.assertIn("요약 정보 없음", msg)
        self.assertIn("health-2026-09-10.md", msg)

    def test_no_message_asks_for_a_verdict(self):
        """승인/반려를 묻는 경로는 제거됐다. 받는 쪽이 없어서 물으면 사용자가
        답장해도 아무 일도 일어나지 않는다."""
        from telegram_notify import (format_health_notification, format_automation_alert,
                                     format_post_published)
        published = "---\ntitle: \"환율 1,400원\"\ndraft: false\n---\n본문"
        msgs = [
            format_health_notification(self.HEALTH_BODY, "report/health-2026-09-10.md", "https://x/y"),
            format_automation_alert("w", "r", "d", "https://x/y"),
            format_post_published("content/posts/fx-1400.md", published),
        ]
        for msg in msgs:
            self.assertNotIn("승인", msg)
            self.assertNotIn("반려", msg)
            self.assertNotRegex(msg, r"#[paPA]\d{4}")

    def test_published_post_carries_live_url(self):
        from telegram_notify import format_post_published
        raw = "---\ntitle: \"환율 1,400원 돌파\"\ndraft: false\n---\n\n본문입니다."
        msg = format_post_published("content/posts/fx-1400.md", raw)
        self.assertIn("발행됨", msg)
        self.assertIn("환율 1,400원 돌파", msg)
        self.assertIn("https://econ-blog.github.io/posts/fx-1400/", msg)

    def test_held_post_says_it_is_not_live(self):
        """`draft: true`는 사이트에 없다는 뜻이다. 발행됐다고 알리면 거짓말이 된다."""
        from telegram_notify import format_post_published
        raw = "---\ntitle: \"환율 1,400원 돌파\"\ndraft: true\n---\n\n본문입니다."
        msg = format_post_published("content/posts/fx-1400.md", raw, note="N1 기준일 누락 2건")
        self.assertIn("보류됨", msg)
        self.assertIn("N1 기준일 누락 2건", msg)
        self.assertNotIn("https://econ-blog.github.io/posts/fx-1400/", msg)

    def test_draft_state_comes_from_the_file_not_the_commit(self):
        """커밋 메시지와 파일이 어긋나면 파일이 이긴다."""
        from telegram_notify import is_draft
        self.assertTrue(is_draft("---\ndraft: true\n---\n본문"))
        self.assertFalse(is_draft("---\ndraft: false\n---\n본문"))
        # 본문에 draft: true 라는 문자열이 있어도 front matter가 아니면 무시한다.
        self.assertFalse(is_draft("---\ndraft: false\n---\n예시: draft: true"))

    def test_strip_front_matter_and_chunking(self):
        from telegram_notify import strip_front_matter, chunk_text
        raw = "---\ntitle: T\ndraft: false\n---\n\n첫 문단.\n\n둘째 문단."
        body = strip_front_matter(raw).strip()
        self.assertTrue(body.startswith("첫 문단."))
        self.assertNotIn("title: T", body)
        chunks = chunk_text("가" * 50 + "\n\n" + "나" * 50, limit=60)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(len(c) <= 60 for c in chunks))

    def test_unknown_mode_exits_nonzero(self):
        from telegram_notify import main
        creds = json.dumps({"telegram": {"bot_token": "t", "chat_id": "1"}})
        with patch.dict(os.environ, {"CREDENTIALS_JSON": creds}), \
             patch.object(sys, "argv", ["telegram_notify.py", "audit-report"]):
            with self.assertRaises(SystemExit):
                main()


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

    def _write(self, d, slug, date):
        with open(os.path.join(d, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write(f'---\ntitle: {slug}\ndate: {date}\ndraft: false\n---\nBody\n')

    def test_sample_is_homepage_newest_and_oldest(self):
        """I6 표본은 최신순 상위 N건이 아니라 진입점·최신·최고령 혼합이다."""
        from select_inspect_urls import select_top_published_urls
        with tempfile.TemporaryDirectory() as d:
            for i in range(1, 7):
                self._write(d, f"p{i}", f"2026-07-{10 + i:02d}T10:00:00Z")
            urls = select_top_published_urls(d, base_url="https://ex.io")

        self.assertEqual(urls[0], "https://ex.io/", "홈페이지가 항상 첫 항목")
        self.assertEqual(len(urls), 5, "쿼터 5건을 채운다")
        self.assertIn("https://ex.io/posts/p6/", urls, "최신 포함")
        self.assertIn("https://ex.io/posts/p5/", urls, "차신 포함")
        self.assertIn("https://ex.io/posts/p1/", urls, "최고령 포함")
        self.assertIn("https://ex.io/posts/p2/", urls, "차고령 포함")
        self.assertNotIn("https://ex.io/posts/p3/", urls, "중간 글은 표본 밖")

    def test_sample_dedupes_when_few_posts(self):
        """발행글이 적으면 최신과 최고령이 겹친다 — 중복 없이 줄어들 뿐 깨지지 않는다."""
        from select_inspect_urls import select_top_published_urls
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "only", "2026-07-11T10:00:00Z")
            urls = select_top_published_urls(d, base_url="https://ex.io")
        self.assertEqual(urls, ["https://ex.io/", "https://ex.io/posts/only/"])

    def test_sample_survives_empty_corpus(self):
        """발행글이 0건이어도 홈페이지 한 건은 낸다 — 진입점 판정은 여전히 가능하다."""
        from select_inspect_urls import select_top_published_urls
        with tempfile.TemporaryDirectory() as d:
            urls = select_top_published_urls(d, base_url="https://ex.io")
        self.assertEqual(urls, ["https://ex.io/"])

    def test_sample_respects_smaller_limit(self):
        """limit이 줄면 홈페이지가 가장 먼저 살아남는다."""
        from select_inspect_urls import select_top_published_urls
        with tempfile.TemporaryDirectory() as d:
            for i in range(1, 7):
                self._write(d, f"p{i}", f"2026-07-{10 + i:02d}T10:00:00Z")
            urls = select_top_published_urls(d, base_url="https://ex.io", limit=2)
        self.assertEqual(urls, ["https://ex.io/", "https://ex.io/posts/p6/"])

    def test_fetch_gsc_parse_args(self):
        from fetch_gsc import parse_args
        opts = parse_args(["--json", "--sitemaps"])
        self.assertFalse(opts["explicit_dimensions"])
        opts_dim = parse_args(["--json", "--dimensions", "query"])
        self.assertTrue(opts_dim["explicit_dimensions"])


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

    def test_alert_is_not_mistaken_for_a_summary_block(self):
        """경보는 요약 블록 계약과 다른 경로다. `## 점검 요약` 헤딩이 없으므로
        `extract_block`이 아무것도 집어내지 못해야 한다."""
        from telegram_notify import format_automation_alert, extract_block
        msg = format_automation_alert("fetch-candidates", "실패", "detail", "https://e.com")
        self.assertEqual(extract_block(msg, "점검 요약"), [])
        self.assertEqual(extract_block(msg, "발행"), [])

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


class TestSelectAllUrls(unittest.TestCase):
    """I6 전수 목록. 표본이 아니라 '아직 색인 안 된 URL'의 완전한 목록을 만든다."""

    def _fixture(self):
        root = tempfile.mkdtemp()
        posts = os.path.join(root, "posts")
        dicts = os.path.join(root, "dictionary")
        os.makedirs(posts)
        os.makedirs(dicts)

        def w(path, name, date, draft):
            with open(os.path.join(path, name), "w", encoding="utf-8") as f:
                f.write(f'---\ntitle: "t"\ndate: {date}\ndraft: {str(draft).lower()}\n---\n본문\n')

        w(posts, "old-post.md", "2026-07-01T09:00:00+09:00", False)
        w(posts, "new-post.md", "2026-08-01T09:00:00+09:00", False)
        w(posts, "hidden-post.md", "2026-08-02T09:00:00+09:00", True)
        w(posts, "welcome.md", "2026-06-01T09:00:00+09:00", False)
        w(dicts, "base-rate.md", "2026-07-15T09:00:00+09:00", False)
        w(dicts, "_index.md", "2026-07-01T09:00:00+09:00", False)
        return root

    def test_includes_entry_points_first(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        self.assertEqual(urls[:3], [
            "https://example.com/",
            "https://example.com/posts/",
            "https://example.com/dictionary/",
        ])

    def test_covers_posts_and_dictionary(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        self.assertIn("https://example.com/posts/old-post/", urls)
        self.assertIn("https://example.com/posts/new-post/", urls)
        self.assertIn("https://example.com/dictionary/base-rate/", urls)

    def test_excludes_draft_welcome_and_underscore(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        self.assertNotIn("https://example.com/posts/hidden-post/", urls)
        self.assertNotIn("https://example.com/posts/welcome/", urls)
        self.assertNotIn("https://example.com/dictionary/_index/", urls)

    def test_newest_first_after_entry_points(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        body = urls[3:]
        self.assertEqual(body[0], "https://example.com/posts/new-post/")
        self.assertEqual(body[-1], "https://example.com/posts/old-post/")

    def test_sample_mode_unchanged(self):
        """전수 모드를 더해도 기존 표본 함수는 그대로여야 한다."""
        from select_inspect_urls import select_top_published_urls
        urls = select_top_published_urls(
            os.path.join(self._fixture(), "posts"), base_url="https://example.com")
        self.assertEqual(urls[0], "https://example.com/")
        self.assertLessEqual(len(urls), 5)


class TestInspectCap(unittest.TestCase):
    def test_cap_default_and_override(self):
        import fetch_gsc
        self.assertEqual(fetch_gsc.DEFAULT_INSPECT_CAP, 60)
        opts = fetch_gsc.parse_args(["--json", "--inspect-cap", "3",
                                     "--inspect", "https://a/", "https://b/"])
        self.assertEqual(opts["inspect_cap"], 3)
        self.assertEqual(opts["inspect"], ["https://a/", "https://b/"])


if __name__ == "__main__":
    unittest.main()
