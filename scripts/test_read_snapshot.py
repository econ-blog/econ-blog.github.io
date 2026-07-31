import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from read_snapshot import resolve_sidecar, gate


def snap(date_iso, candidates):
    return {"generated_at": f"{date_iso}T01:47:00+09:00",
            "feeds_used": ["hankyung/economy"], "feed_errors": [],
            "window_hours": 24, "candidates": candidates}


def cand(chars=800, err=None):
    return {"title": "t", "url": "https://e.com/1",
            "published_at": "2026-07-31T00:30:00+09:00",
            "source": "s", "feed": "f", "body_text": "가" * max(chars, 0),
            "body_chars": chars, "body_error": err, "body_ok": err is None and chars >= 400}


class TestResolveSidecar(unittest.TestCase):
    def test_explicit_arg_wins(self):
        path, how = resolve_sidecar("/x/side", {"AUTOMATION_DATA_DIR": "/y"}, "/z")
        self.assertEqual(path, "/x/side")
        self.assertEqual(how, "arg")

    def test_env_used_when_no_arg(self):
        path, how = resolve_sidecar(None, {"AUTOMATION_DATA_DIR": "/y"}, "/z")
        self.assertEqual(path, "/y")
        self.assertEqual(how, "env")

    def test_sibling_used_when_it_exists(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            sib = os.path.join(tmp, "automation-data")
            os.makedirs(sib)
            path, how = resolve_sidecar(None, {}, tmp)
            self.assertEqual(path, sib)
            self.assertEqual(how, "sibling")

    def test_falls_through_to_clone_signal(self):
        path, how = resolve_sidecar(None, {}, "/nonexistent-parent-xyz")
        self.assertIsNone(path)
        self.assertEqual(how, "clone")


class TestGate(unittest.TestCase):
    def test_ok_when_fresh_and_usable(self):
        r = gate(snap("2026-07-31", [cand()]), "2026-07-31")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["candidates"]), 1)

    def test_stale_when_date_differs(self):
        r = gate(snap("2026-07-30", [cand()]), "2026-07-31")
        self.assertEqual(r["status"], "stale")
        self.assertEqual(r["candidates"], [])

    def test_utc_boundary_snapshot_is_fresh(self):
        """UTC 16:47 생성 = KST 익일 01:47. KST 05:00 실행 시 같은 날이어야 한다."""
        r = gate(snap("2026-07-31", [cand()]), "2026-07-31")
        self.assertEqual(r["status"], "ok")

    def test_no_usable_when_all_bodies_fail(self):
        r = gate(snap("2026-07-31", [cand(chars=399), cand(err="boom")]), "2026-07-31")
        self.assertEqual(r["status"], "no_usable")
        self.assertEqual(r["candidates"], [])

    def test_unusable_candidates_are_filtered_out(self):
        r = gate(snap("2026-07-31", [cand(chars=399), cand(chars=900)]), "2026-07-31")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["candidates"]), 1)
        self.assertEqual(r["candidates"][0]["body_chars"], 900)

    def test_body_ok_is_recomputed_not_trusted(self):
        """스냅샷의 body_ok 필드를 그대로 믿지 않는다 — 게이트가 다시 계산한다."""
        bad = cand(chars=100)
        bad["body_ok"] = True
        r = gate(snap("2026-07-31", [bad]), "2026-07-31")
        self.assertEqual(r["status"], "no_usable")

    def test_empty_snapshot_is_no_usable_not_ok(self):
        r = gate(snap("2026-07-31", []), "2026-07-31")
        self.assertEqual(r["status"], "no_usable")


if __name__ == "__main__":
    unittest.main()
