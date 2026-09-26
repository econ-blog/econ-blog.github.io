"""continuity.py 단위 테스트 — 표준 unittest, pytest 미사용."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuity  # noqa: E402


def write_post(root: Path, slug: str, d: str, draft: bool = False):
    p = root / "posts"
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{slug}.md").write_text(
        "---\n"
        f'title: "{slug}"\n'
        f"date: {d}T05:20:00+09:00\n"
        f"draft: {'true' if draft else 'false'}\n"
        "---\n\n본문\n",
        encoding="utf-8",
    )


class TestGaps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_gap_when_every_day_present(self):
        for i in range(1, 8):
            write_post(self.root, f"p{i}", f"2026-09-{20+i:02d}")
        r = continuity.gaps(self.root, today="2026-09-28", days=7)
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["total"], 0)

    def test_finds_the_missing_day(self):
        """2026-09-21 실사고의 회귀 테스트 — 회차 3은 이 결번을 눈으로 세다 놓쳤다."""
        for d in ("2026-09-20", "2026-09-22", "2026-09-23"):
            write_post(self.root, d, d)
        r = continuity.gaps(self.root, today="2026-09-24", days=4)
        self.assertEqual(r["missing"], ["2026-09-21"])
        self.assertEqual([f["check"] for f in r["findings"]], ["C1"])

    def test_today_is_never_a_gap(self):
        """05:00 KST 발행 전에 돌면 오늘은 비어 있는 것이 정상이다."""
        write_post(self.root, "a", "2026-09-26")
        r = continuity.gaps(self.root, today="2026-09-27", days=1)
        self.assertEqual(r["missing"], [])

    def test_held_draft_is_not_a_gap(self):
        """보류된 날은 결번이 아니다 — 글은 나왔고 게이트가 막은 것이라 원인이 다르다."""
        write_post(self.root, "held", "2026-09-26", draft=True)
        r = continuity.gaps(self.root, today="2026-09-27", days=2)
        self.assertNotIn("2026-09-26", r["missing"])
        self.assertEqual(r["held_count"], 1)

    def test_held_threshold_fires_at_three(self):
        write_post(self.root, "a", "2026-09-24", draft=True)
        write_post(self.root, "b", "2026-09-25", draft=True)
        r = continuity.gaps(self.root, today="2026-09-27", days=5)
        self.assertNotIn("C2", [f["check"] for f in r["findings"]])
        write_post(self.root, "c", "2026-09-26", draft=True)
        r = continuity.gaps(self.root, today="2026-09-27", days=5)
        self.assertIn("C2", [f["check"] for f in r["findings"]])
        self.assertEqual(r["held_count"], 3)

    def test_stall_alert_at_seven_days(self):
        write_post(self.root, "old", "2026-09-19")
        r = continuity.gaps(self.root, today="2026-09-26", days=7)
        checks = [f["check"] for f in r["findings"]]
        self.assertIn("C3", checks)
        self.assertEqual(r["stall_days"], 7)
        self.assertEqual(r["last_published"], "2026-09-19")

    def test_draft_does_not_count_as_last_published(self):
        write_post(self.root, "live", "2026-09-18")
        write_post(self.root, "held", "2026-09-26", draft=True)
        r = continuity.gaps(self.root, today="2026-09-26", days=9)
        self.assertEqual(r["last_published"], "2026-09-18")
        self.assertIn("C3", [f["check"] for f in r["findings"]])

    def test_excluded_files_ignored(self):
        write_post(self.root, "welcome", "2026-09-26")
        write_post(self.root, "_index", "2026-09-26")
        r = continuity.gaps(self.root, today="2026-09-27", days=2)
        self.assertIsNone(r["last_published"])

    def test_real_repo_runs(self):
        """저장소의 실제 content/ 에서도 예외 없이 돈다."""
        r = continuity.gaps(days=14)
        self.assertIn("missing", r)
        self.assertIsInstance(r["held_count"], int)


if __name__ == "__main__":
    unittest.main()
