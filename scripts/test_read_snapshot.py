import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from read_snapshot import resolve_sidecar, gate, build_result, load_snapshot_dir


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

    def test_linkstate_shaped_snapshot_is_ok_when_fresh(self):
        """candidates 키가 아예 없는 스냅샷(예: linkstate)은 본문 게이트 대상이 아니다."""
        linkstate = {"generated_at": "2026-07-31T01:47:00+09:00",
                     "inventory": [], "summary": {}, "ledger": []}
        r = gate(linkstate, "2026-07-31")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["candidates"], [])

    def test_linkstate_shaped_snapshot_is_stale_when_old(self):
        linkstate = {"generated_at": "2026-07-30T01:47:00+09:00",
                     "inventory": [], "summary": {}, "ledger": []}
        r = gate(linkstate, "2026-07-31")
        self.assertEqual(r["status"], "stale")
        self.assertEqual(r["candidates"], [])

    def test_candidates_key_present_but_empty_stays_no_usable(self):
        """candidates: [] 는 후보 스냅샷이다 — 키 부재와 혼동하면 안 된다(회귀 가드)."""
        r = gate(snap("2026-07-31", []), "2026-07-31")
        self.assertEqual(r["status"], "no_usable")
        self.assertEqual(r["candidates"], [])


class TestBuildResult(unittest.TestCase):
    def test_snapshot_path_present_when_loaded_from_file(self):
        r = build_result(snap("2026-07-31", [cand()]), "2026-07-31", "sibling",
                          "/abs/path/candidates/2026-07-31.json")
        self.assertEqual(r["snapshot_path"], "/abs/path/candidates/2026-07-31.json")

    def test_snapshot_path_absent_when_locally_collected(self):
        """--allow-local-fetch 로 그 자리에서 수집한 경우 가리킬 파일이 없다."""
        r = build_result(snap("2026-07-31", [cand()]), "2026-07-31", "sibling", None)
        self.assertNotIn("snapshot_path", r)

    def test_candidates_path_output_unchanged_besides_snapshot_path(self):
        """/daily-post 소비 경로 회귀 가드: candidates 스냅샷은 여전히 status/candidates/
        reason/sidecar_via/feeds_used/feed_errors 만 나오고(+ snapshot_path), 스냅샷의
        다른 키가 섞여 들어오지 않는다."""
        r = build_result(snap("2026-07-31", [cand()]), "2026-07-31", "env",
                          "/x/candidates/2026-07-31.json")
        self.assertEqual(set(r.keys()),
                          {"status", "candidates", "reason", "sidecar_via",
                           "feeds_used", "feed_errors", "snapshot_path"})

    def test_linkstate_summary_and_ledger_reach_result(self):
        linkstate = {"generated_at": "2026-07-31T01:47:00+09:00",
                     "inventory": {"a.md": {"external": []}},
                     "summary": {"confirmed_dead": [], "manual_review": [], "moved": [],
                                 "ledger_was_stale": False},
                     "ledger": [{"url": "https://e.com/x", "status": "ok"}]}
        r = build_result(linkstate, "2026-07-31", "sibling",
                          "/x/linkstate/2026-07-31.json")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["summary"], linkstate["summary"])
        self.assertEqual(r["ledger"], linkstate["ledger"])
        self.assertEqual(r["inventory"], linkstate["inventory"])
        self.assertEqual(r["snapshot_path"], "/x/linkstate/2026-07-31.json")

    def test_linkstate_payload_never_clobbers_contract_keys(self):
        """스냅샷 페이로드에 계약 키와 이름이 겹치는 필드가 있어도 결과의 계약 값이
        이긴다 — 예컨대 스냅샷 안에 우연히 'status' 라는 페이로드 키가 있어도 무시한다."""
        linkstate = {"generated_at": "2026-07-31T01:47:00+09:00",
                     "status": "should-not-leak", "summary": {"x": 1}, "ledger": []}
        r = build_result(linkstate, "2026-07-31", "sibling", "/x/linkstate/2026-07-31.json")
        self.assertEqual(r["status"], "ok")  # gate()의 판정이 이긴다, 스냅샷의 "status" 아님
        self.assertEqual(r["summary"], {"x": 1})

    def test_stale_linkstate_still_passes_through_payload(self):
        """stale 이어도 candidates 없는 스냅샷이면 페이로드는 통과시킨다 — 호출부가
        status로 알아서 걸러 쓴다(§3의 '측정 안 함' 규칙은 소비자 쪽 책임)."""
        linkstate = {"generated_at": "2026-07-30T01:47:00+09:00",
                     "summary": {"confirmed_dead": []}, "ledger": []}
        r = build_result(linkstate, "2026-07-31", "sibling", "/x/linkstate/2026-07-30.json")
        self.assertEqual(r["status"], "stale")
        self.assertEqual(r["summary"], {"confirmed_dead": []})


class TestDirMode(unittest.TestCase):
    def test_loads_every_json_in_the_date_directory(self):
        import json, tempfile
        from read_snapshot import load_snapshot_dir
        with tempfile.TemporaryDirectory() as tmp:
            day = os.path.join(tmp, "analytics", "2026-07-31")
            os.makedirs(day)
            for name in ("ga4_28d", "gsc_page_28d"):
                with open(os.path.join(day, f"{name}.json"), "w") as fh:
                    json.dump({"total_rows": 3}, fh)
            out = load_snapshot_dir(tmp, "analytics", "2026-07-31")
            self.assertEqual(sorted(out["files"]), ["ga4_28d", "gsc_page_28d"])
            self.assertEqual(out["files"]["ga4_28d"]["total_rows"], 3)

    def test_missing_directory_raises(self):
        from read_snapshot import load_snapshot_dir
        with self.assertRaises(FileNotFoundError):
            load_snapshot_dir("/nonexistent-xyz", "analytics", "2026-07-31")

    def test_no_candidates_key_so_gate_treats_it_as_freshness_only(self):
        """load_snapshot_dir()가 candidates 키를 내지 않는다는 것은 회귀 가드가 필요한
        계약이다 — 있으면 gate()가 candidates: [] 있음으로 오인해 no_usable로 오판정한다."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            day = os.path.join(tmp, "analytics", "2026-07-31")
            os.makedirs(day)
            out = load_snapshot_dir(tmp, "analytics", "2026-07-31")
            self.assertNotIn("candidates", out)
            r = gate(out, "2026-07-31")
            self.assertEqual(r["status"], "ok")


if __name__ == "__main__":
    unittest.main()
