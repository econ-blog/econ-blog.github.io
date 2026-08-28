import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import health_memory as hm

PREAMBLE = "# 격주 점검 장기 기억\n\n읽는 법은 여기.\n\n"


def entry(date, n, body="내용\n"):
    return f"## {date} · 회차 {n}\n\n{body}"


class TestSplit(unittest.TestCase):
    def test_preamble_is_not_an_entry(self):
        pre, entries = hm.split_entries(PREAMBLE + entry("2026-09-10", 1))
        self.assertEqual(pre, PREAMBLE)
        self.assertEqual([(e[0], e[1]) for e in entries], [("2026-09-10", 1)])

    def test_file_with_only_preamble(self):
        pre, entries = hm.split_entries(PREAMBLE)
        self.assertEqual(pre, PREAMBLE)
        self.assertEqual(entries, [])

    def test_entries_rejoin_to_the_original(self):
        text = PREAMBLE + entry("2026-09-10", 1) + "\n" + entry("2026-09-24", 2)
        pre, entries = hm.split_entries(text)
        self.assertEqual(pre + "".join(e[2] for e in entries), text)

    def test_h2_inside_a_body_does_not_split(self):
        """본문에 `## 굳은 기억` 같은 H2가 있어도 회차로 세지 않는다 — 회차 헤딩은
        날짜와 회차 번호를 함께 가진 것만이다."""
        body = "### 관측\n\n## 굳은 기억\n\n접힌 내용\n"
        pre, entries = hm.split_entries(PREAMBLE + entry("2026-09-10", 1, body))
        self.assertEqual(len(entries), 1)
        self.assertIn("굳은 기억", entries[0][2])


class TestTail(unittest.TestCase):
    def _three(self):
        return (PREAMBLE + entry("2026-09-10", 1) + "\n"
                + entry("2026-09-24", 2) + "\n" + entry("2026-10-08", 3))

    def test_tail_keeps_preamble_and_last_n(self):
        out = hm.tail(self._three(), 2)
        self.assertIn("읽는 법은 여기", out)
        self.assertNotIn("회차 1", out)
        self.assertIn("회차 2", out)
        self.assertIn("회차 3", out)

    def test_tail_zero_means_everything(self):
        out = hm.tail(self._three(), 0)
        for n in (1, 2, 3):
            self.assertIn(f"회차 {n}", out)

    def test_tail_more_than_exists_is_fine(self):
        self.assertIn("회차 1", hm.tail(self._three(), 99))

    def test_tail_on_empty_file(self):
        self.assertEqual(hm.tail("", 3), "")


class TestAppend(unittest.TestCase):
    def test_append_adds_after_existing(self):
        text = hm.append(PREAMBLE + entry("2026-09-10", 1), entry("2026-09-24", 2))
        _pre, entries = hm.split_entries(text)
        self.assertEqual([e[0] for e in entries], ["2026-09-10", "2026-09-24"])

    def test_same_day_rerun_replaces_instead_of_duplicating(self):
        """같은 날 두 번 돈 것은 회차 둘이 아니라 재실행이다."""
        text = hm.append(PREAMBLE + entry("2026-09-10", 1, "처음\n"),
                         entry("2026-09-10", 1, "다시 돌린 결과\n"))
        _pre, entries = hm.split_entries(text)
        self.assertEqual(len(entries), 1)
        self.assertIn("다시 돌린 결과", entries[0][2])
        self.assertNotIn("처음", entries[0][2])

    def test_out_of_order_append_is_sorted_by_date(self):
        text = hm.append(PREAMBLE + entry("2026-10-08", 3), entry("2026-09-24", 2))
        _pre, entries = hm.split_entries(text)
        self.assertEqual([e[0] for e in entries], ["2026-09-24", "2026-10-08"])

    def test_append_to_empty_file_works(self):
        text = hm.append("", entry("2026-09-10", 1))
        _pre, entries = hm.split_entries(text)
        self.assertEqual(len(entries), 1)

    def test_preamble_survives_append(self):
        text = hm.append(PREAMBLE + entry("2026-09-10", 1), entry("2026-09-24", 2))
        self.assertTrue(text.startswith("# 격주 점검 장기 기억"))
        self.assertIn("읽는 법은 여기", text)


class TestValidate(unittest.TestCase):
    def test_good_header_passes(self):
        self.assertEqual(hm.validate_entry(entry("2026-09-10", 1)), "")

    def test_missing_header_is_refused(self):
        self.assertIn("회차 헤딩이 아니다", hm.validate_entry("### 관측\n내용\n"))

    def test_wrong_separator_is_refused(self):
        """가운뎃점이 아니라 하이픈을 쓰면 거부한다 — 형식이 무너지면 tail도 무너진다."""
        self.assertIn("회차 헤딩이 아니다",
                      hm.validate_entry("## 2026-09-10 - 회차 1\n내용\n"))

    def test_impossible_date_is_refused(self):
        self.assertIn("날짜를 읽을 수 없다",
                      hm.validate_entry("## 2026-02-30 · 회차 1\n내용\n"))

    def test_empty_body_is_refused(self):
        self.assertNotEqual(hm.validate_entry("   \n"), "")


class TestStats(unittest.TestCase):
    def test_next_round_follows_the_highest_seen(self):
        self.assertEqual(hm.next_round(PREAMBLE + entry("2026-09-10", 0)), 1)
        self.assertEqual(hm.next_round(PREAMBLE + entry("2026-09-10", 7)), 8)
        self.assertEqual(hm.next_round(PREAMBLE), 1)

    def test_compact_due_flips_past_the_threshold(self):
        small = hm.stats(PREAMBLE + entry("2026-09-10", 1))
        self.assertFalse(small["compact_due"])
        big = hm.stats(PREAMBLE + entry("2026-09-10", 1, "줄\n" * (hm.COMPACT_THRESHOLD_LINES + 5)))
        self.assertTrue(big["compact_due"])


class TestCli(unittest.TestCase):
    def test_append_via_stdin_then_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mem.md")
            with patch.object(sys, "stdin", io.StringIO(entry("2026-09-10", 1, "첫 회차\n"))):
                rc = hm.main(["append", "--path", path])
            self.assertEqual(rc, 0)
            self.assertIn("첫 회차", hm.tail(hm.read(path), 1))

    def test_bad_entry_is_refused_and_file_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mem.md")
            hm.write(PREAMBLE + entry("2026-09-10", 1), path)
            before = hm.read(path)
            with patch.object(sys, "stdin", io.StringIO("형식 틀린 본문\n")), \
                 patch.object(sys, "stderr", io.StringIO()):
                rc = hm.main(["append", "--path", path])
            self.assertEqual(rc, 1)
            self.assertEqual(hm.read(path), before, "거부했는데 파일이 바뀌었다")

    def test_tail_on_missing_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, "stdout", io.StringIO()):
                self.assertEqual(hm.main(["tail", "--path", os.path.join(tmp, "none.md")]), 0)


class TestShippedFile(unittest.TestCase):
    """저장소에 들어 있는 실제 기억 파일이 계약을 지키는지. 이 테스트가 깨지면
    다음 점검이 자기 기억을 못 읽는다."""

    PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        ".claude", "audit", "health-memory.md")

    def test_file_exists_and_parses(self):
        self.assertTrue(os.path.exists(self.PATH), "기억 파일이 없다")
        text = hm.read(self.PATH)
        pre, entries = hm.split_entries(text)
        self.assertIn("읽는 법", pre)
        self.assertGreaterEqual(len(entries), 1, "출발점 회차가 없다")

    def test_every_entry_would_pass_validation(self):
        _pre, entries = hm.split_entries(hm.read(self.PATH))
        for date, n, body in entries:
            self.assertEqual(hm.validate_entry(body), "", f"{date} 회차 {n} 형식 위반")


if __name__ == '__main__':
    unittest.main()
