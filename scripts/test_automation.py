import os
import re
import sys
import json
import tempfile
import unittest
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

    def test_format_audit_report_notification(self):
        """`main` 직행 리포트 알림. 같은 §9-1 본문에서 같은 줄이 살아남는다."""
        from telegram_notify import format_audit_report_notification
        msg = format_audit_report_notification(
            self.AUDIT_PR_BODY, "report/audit-2026-08-09.md",
            "https://github.com/org/repo/blob/abc123/report/audit-2026-08-09.md")
        self.assertIn("audit-2026-08-09.md", msg)
        for line in ("계약 위반: 1건",
                     "확정 사망 링크: 0건 / 사람 점검 필요: 2건",
                     "데이터 충분성: 미달 (발행 5 / 20건)",
                     "색인 건전성: 정상",
                     "소견: 1건 (④ 1, ⑥ 0)",
                     "새 가설 제안: 1건",
                     "─ 결정 필요 ─"):
            self.assertIn(line, msg, f"§9-1 계약 줄이 필터를 통과하지 못했다: {line}")
        self.assertIn("blob/abc123", msg)

    def test_audit_report_notification_carries_no_verdict_token(self):
        """리포트는 승인 대상이 아니다 — `#A0809` 토큰도 승인 문구도 넣지 않는다.

        토큰이 들어가면 사용자가 답장했을 때 `process_inbox.py`가 열려 있지도
        않은 `auto/audit-*` PR을 찾아 '대기 중인 PR이 없습니다'로 튄다.
        """
        from telegram_notify import format_audit_report_notification
        from process_inbox import parse_verdict
        msg = format_audit_report_notification(
            self.AUDIT_PR_BODY, "report/audit-2026-08-09.md",
            "https://github.com/org/repo/blob/abc123/report/audit-2026-08-09.md")
        self.assertIsNone(re.search(r'#[paPA]\d{4}', msg),
                          "리포트 알림에 판정 토큰이 들어갔다")
        self.assertNotIn("승인 / 반려 로 답장", msg)
        # 본문이 그 자체로 승인 판정처럼 파싱되지 않는지도 본다.
        self.assertEqual(parse_verdict(msg), "AMBIGUOUS")

    def test_audit_report_notification_survives_broken_body(self):
        """계약을 어긴 본문에도 조용히 반쪽 요약을 내지 않는다."""
        from telegram_notify import format_audit_report_notification
        msg = format_audit_report_notification(
            "## ⚠ 계약 위반\n1건", "report/audit-2026-08-09.md", "https://x/y")
        self.assertIn("요약 정보 없음", msg)
        self.assertIn("audit-2026-08-09.md", msg)


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

        # 2-1. 직접 친 토큰이 답장 대상의 토큰을 이긴다 — 대기 목록 안내에는 토큰이
        # 여러 개 실려 있어서, 답장 우선이면 목록 첫 줄의 다른 글이 병합된다.
        up_conflict = {"message": {"reply_to_message": {"text": "#P0730 — 포스트 PR #10\n#A0730 — 감사 PR #11"},
                                   "text": "승인 #A0730", "chat": {"id": 12345}}}
        pr, status = match_target_pr(up_conflict, open_prs)
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

    def test_pending_pr_lines_carry_tokens(self):
        """토큰 형식만 알려 주고 목록을 빼면 어느 토큰을 쓸지 알 수 없다."""
        from process_inbox import pending_pr_lines
        lines = pending_pr_lines([
            {"number": 8, "head": {"ref": "auto/post-2026-08-04"}},
            {"number": 11, "head": {"ref": "auto/audit-2026-08-01-1824"}},
        ])
        self.assertIn("#P0804", lines)
        self.assertIn("#A0801", lines)
        self.assertIn("PR #8", lines)
        self.assertIn("PR #11", lines)

    def test_multiple_prs_message_lists_every_token(self):
        """매칭 실패 메시지가 그대로 다음 답장의 안내가 된다."""
        import process_inbox
        sent = []
        open_prs = [
            {"number": 8, "head": {"ref": "auto/post-2026-08-04"}},
            {"number": 9, "head": {"ref": "auto/post-2026-08-05"}},
        ]
        up = {"message": {"chat": {"id": 1}, "text": "승인"}}

        with patch.object(process_inbox, "send_telegram", lambda *a: sent.append(a[2])):
            remaining = process_inbox.handle_update(up, open_prs, "o/r", "p", "tok", "1")

        self.assertEqual(remaining, open_prs)  # 아무 PR도 건드리지 않았다
        self.assertEqual(len(sent), 1)
        self.assertIn("#P0804", sent[0])
        self.assertIn("#P0805", sent[0])

    def test_backlog_alert_fires_at_two(self):
        """토큰 없는 답장은 2건부터 깨진다 — 경보가 3건이면 하루 늦다."""
        import process_inbox
        creds = json.dumps({"telegram": {"bot_token": "tok", "chat_id": "1"}})
        open_prs = [
            {"number": 8, "head": {"ref": "auto/post-2026-08-04"}},
            {"number": 9, "head": {"ref": "auto/post-2026-08-05"}},
        ]
        sent = []

        with patch.dict(os.environ, {"CREDENTIALS_JSON": creds, "PAT": "p", "REPO": "o/r", "TELEGRAM_OFFSET": "99"}), \
             patch.object(process_inbox, "get_open_prs", lambda *a: open_prs), \
             patch.object(process_inbox.requests, "get", lambda url, **kw: FakeResponse(200, {"result": []})), \
             patch.object(process_inbox, "send_telegram", lambda *a: sent.append(a[2])):
            process_inbox.main()

        self.assertEqual(len(sent), 1)
        self.assertIn("2건", sent[0])
        self.assertIn("#P0804", sent[0])
        self.assertIn("#P0805", sent[0])

    def test_merge_retries_transient_405(self):
        """커밋을 민 직후 GitHub의 mergeable은 null이고 PUT /merge는 405를 준다 — 재시도 대상이다."""
        import process_inbox
        pr_ready = {"state": "open", "mergeable": True, "head": {"sha": "abc"}}
        calls = []

        def fake_get(url, **kw):
            return FakeResponse(200, pr_ready)

        def fake_put(url, headers=None, json=None, timeout=None):
            calls.append(json["merge_method"])
            if len(calls) == 1:
                return FakeResponse(405, {"message": "Pull Request is not mergeable"})
            return FakeResponse(200, {"merged": True})

        with patch.object(process_inbox.requests, "get", fake_get), \
             patch.object(process_inbox.requests, "put", fake_put):
            process_inbox.merge_pr("o/r", 7, "pat", sleep=lambda s: None)

        self.assertEqual(calls, ["squash", "squash"])

    def test_merge_falls_back_when_squash_disabled(self):
        import process_inbox
        pr_ready = {"state": "open", "mergeable": True, "head": {"sha": "abc"}}
        calls = []

        def fake_put(url, headers=None, json=None, timeout=None):
            calls.append(json["merge_method"])
            if json["merge_method"] == "squash":
                return FakeResponse(405, {"message": "Squash merges are not allowed on this repository."})
            return FakeResponse(200, {"merged": True})

        with patch.object(process_inbox.requests, "get", lambda url, **kw: FakeResponse(200, pr_ready)), \
             patch.object(process_inbox.requests, "put", fake_put):
            process_inbox.merge_pr("o/r", 7, "pat", sleep=lambda s: None)

        # squash는 한 번만 시도하고(영구 거부) 곧장 merge로 내려간다
        self.assertEqual(calls, ["squash", "merge"])

    def test_merge_reports_github_reason(self):
        """raise_for_status()는 본문을 버린다. 텔레그램에 실제 사유가 실려야 한다."""
        import process_inbox
        pr_blocked = {"state": "open", "mergeable": False, "mergeable_state": "dirty", "head": {"sha": "abc"}}
        with patch.object(process_inbox.requests, "get", lambda url, **kw: FakeResponse(200, pr_blocked)):
            with self.assertRaises(RuntimeError) as ctx:
                process_inbox.merge_pr("o/r", 7, "pat", sleep=lambda s: None)
        self.assertIn("dirty", str(ctx.exception))

    def test_failed_verdict_is_not_consumed(self):
        """실행이 실패하면 그 업데이트의 오프셋을 넘기지 않는다 — 넘기면 승인이 사라진다."""
        import process_inbox
        creds = json.dumps({"telegram": {"bot_token": "tok", "chat_id": "1"}})
        updates = [{"update_id": 100, "message": {"chat": {"id": 1}, "text": "승인"}}]
        recorded = []

        def boom(*args, **kwargs):
            raise RuntimeError("PR #7 병합 실패: 405 Pull Request is not mergeable")

        env = {"CREDENTIALS_JSON": creds, "PAT": "p", "REPO": "o/r", "TELEGRAM_OFFSET": "99"}
        with patch.dict(os.environ, env), \
             patch.object(process_inbox, "get_open_prs", lambda *a: [{"number": 7, "head": {"ref": "auto/post-2026-08-03"}}]), \
             patch.object(process_inbox.requests, "get", lambda url, **kw: FakeResponse(200, {"result": updates})), \
             patch.object(process_inbox, "execute_approved_post", boom), \
             patch.object(process_inbox, "update_telegram_offset", lambda *a: recorded.append(a[2])), \
             patch.object(process_inbox, "send_telegram", lambda *a: recorded.append(a[2])):
            with self.assertRaises(SystemExit) as ctx:
                process_inbox.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertNotIn(101, recorded)  # 오프셋이 전진하지 않았다
        self.assertTrue(any("405" in str(r) for r in recorded))  # 사유가 실려 나갔다

    def test_successful_verdict_consumes_update(self):
        import process_inbox
        creds = json.dumps({"telegram": {"bot_token": "tok", "chat_id": "1"}})
        updates = [{"update_id": 100, "message": {"chat": {"id": 1}, "text": "승인"}}]
        offsets = []

        with patch.dict(os.environ, {"CREDENTIALS_JSON": creds, "PAT": "p", "REPO": "o/r", "TELEGRAM_OFFSET": "99"}), \
             patch.object(process_inbox, "get_open_prs", lambda *a: [{"number": 7, "head": {"ref": "auto/post-2026-08-03"}}]), \
             patch.object(process_inbox.requests, "get", lambda url, **kw: FakeResponse(200, {"result": updates})), \
             patch.object(process_inbox, "execute_approved_post", lambda *a: True), \
             patch.object(process_inbox, "update_telegram_offset", lambda *a: offsets.append(a[2])), \
             patch.object(process_inbox, "send_telegram", lambda *a: None):
            process_inbox.main()

        self.assertEqual(offsets, [101])

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

    def test_oldest_first_after_entry_points(self):
        from select_inspect_urls import select_all_urls
        urls = select_all_urls(self._fixture(), base_url="https://example.com")
        body = urls[3:]
        self.assertEqual(body[0], "https://example.com/posts/old-post/")
        self.assertEqual(body[-1], "https://example.com/posts/new-post/")

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
