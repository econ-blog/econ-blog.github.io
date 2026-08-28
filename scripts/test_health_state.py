import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import health_state


class TestMonthlyCadence(unittest.TestCase):
    """격주로 도는 패스에서 '한 달에 한 번'을 세는 규칙. 회차 수가 아니라 달을
    원장에 적는다 — 스케줄이 밀리거나 걸러져도 한 달에 정확히 한 번이 되도록."""

    def test_first_run_is_due(self):
        self.assertTrue(health_state.monthly_due({"last_monthly": ""}, "2026-09-10"))

    def test_same_month_is_not_due_again(self):
        led = health_state.record({"last_monthly": "", "runs": []}, "2026-09-10", True, True)
        self.assertFalse(health_state.monthly_due(led, "2026-09-24"))

    def test_next_month_is_due(self):
        led = health_state.record({"last_monthly": "", "runs": []}, "2026-09-10", True, True)
        self.assertTrue(health_state.monthly_due(led, "2026-10-08"))

    def test_a_skipped_month_is_not_repaid(self):
        """10월 회차가 통째로 걸러졌다면 11월에 두 번 보내지 않는다 — 지난 달 현황은
        이미 지난 달 이야기다."""
        led = health_state.record({"last_monthly": "", "runs": []}, "2026-09-10", True, True)
        led = health_state.record(led, "2026-11-05", True, True)
        self.assertEqual(led["last_monthly"], "2026-11")
        self.assertFalse(health_state.monthly_due(led, "2026-11-19"))

    def test_non_monthly_run_does_not_consume_the_month(self):
        led = health_state.record({"last_monthly": "", "runs": []}, "2026-09-10", False, False)
        self.assertTrue(health_state.monthly_due(led, "2026-09-24"))


class TestBiweeklyGate(unittest.TestCase):
    """격주 주기는 cron이 아니라 여기서 판정한다. 트리거는 매주 발화하고 이 게이트가
    가른다 — 표준 cron으로 '2주에 한 번'을 쓸 수 없고, 회차 수를 세면 발화가 걸러질
    때마다 위상이 밀린다."""

    def _after(self, last_date, today):
        led = health_state.record({"last_monthly": "", "runs": []}, last_date, False, False)
        return health_state.run_due(led, today)

    def test_first_ever_run_proceeds(self):
        self.assertTrue(health_state.run_due({"last_monthly": "", "runs": []}, "2026-09-06"))

    def test_next_week_is_skipped(self):
        self.assertFalse(self._after("2026-09-06", "2026-09-13"))

    def test_two_weeks_later_proceeds(self):
        self.assertTrue(self._after("2026-09-06", "2026-09-20"))

    def test_a_missed_firing_is_picked_up_by_the_next_one(self):
        """9/20 발화가 걸러졌으면 9/27이 그대로 이어받는다 — 다시 2주를 기다리지 않는다."""
        self.assertTrue(self._after("2026-09-06", "2026-09-27"))

    def test_threshold_catches_the_13th_day(self):
        """주 단위로 발화하므로 정확히 14일째 발화는 없다. 문턱이 14면 매번 한 주씩 밀린다."""
        self.assertTrue(self._after("2026-09-06", "2026-09-19"))
        self.assertFalse(self._after("2026-09-06", "2026-09-12"))

    def test_unreadable_date_errs_toward_running(self):
        """건너뛰면 점검이 영영 안 돌 수 있다. 읽을 수 없으면 도는 쪽을 고른다.

        날짜는 오늘보다 앞서도록(문자열 정렬 기준) 두되 `strptime`이 거부하는 값을
        쓴다 — 그래야 `previous_run`을 통과해 실제로 파싱 분기까지 간다."""
        led = {"last_monthly": "", "runs": [{"date": "2026-02-30"}]}
        self.assertIsNotNone(health_state.previous_run(led, "2026-09-13"))
        self.assertTrue(health_state.run_due(led, "2026-09-13"))


class TestLedger(unittest.TestCase):
    def test_rerun_on_same_day_overwrites_instead_of_appending(self):
        led = health_state.record({"last_monthly": "", "runs": []}, "2026-09-10", False, False, fixes=3)
        led = health_state.record(led, "2026-09-10", False, True, fixes=5, human_items=1)
        self.assertEqual(len(led["runs"]), 1)
        self.assertEqual(led["runs"][0]["fixes"], 5)
        self.assertEqual(led["runs"][0]["human_items"], 1)

    def test_runs_stay_sorted_by_date(self):
        led = {"last_monthly": "", "runs": []}
        for d in ("2026-09-24", "2026-09-10", "2026-10-08"):
            led = health_state.record(led, d, False, False)
        self.assertEqual([r["date"] for r in led["runs"]],
                         ["2026-09-10", "2026-09-24", "2026-10-08"])

    def test_previous_run_ignores_today(self):
        led = {"last_monthly": "", "runs": []}
        led = health_state.record(led, "2026-09-10", False, False)
        led = health_state.record(led, "2026-09-24", False, False)
        self.assertEqual(health_state.previous_run(led, "2026-09-24")["date"], "2026-09-10")
        self.assertIsNone(health_state.previous_run(led, "2026-09-10"))

    def test_missing_or_broken_ledger_starts_empty_instead_of_dying(self):
        """원장은 점검의 산출물이지 입력이 아니다. 여기서 죽으면 점검 자체가 멈춘다."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "nope.json")
            self.assertEqual(health_state.load(missing), {"last_monthly": "", "runs": []})

            broken = os.path.join(tmp, "broken.json")
            with open(broken, "w", encoding="utf-8") as fh:
                fh.write("not json{")
            self.assertEqual(health_state.load(broken), {"last_monthly": "", "runs": []})

            wrong_type = os.path.join(tmp, "list.json")
            with open(wrong_type, "w", encoding="utf-8") as fh:
                fh.write('["a"]')
            self.assertEqual(health_state.load(wrong_type), {"last_monthly": "", "runs": []})

    def test_round_trip_through_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "health-log.json")
            led = health_state.record(health_state.load(path), "2026-09-10", True, True, fixes=2)
            health_state.save(led, path)
            back = health_state.load(path)
            self.assertEqual(back["last_monthly"], "2026-09")
            self.assertEqual(back["runs"][0]["fixes"], 2)
            self.assertFalse(health_state.monthly_due(back, "2026-09-24"))

    def test_runs_are_capped(self):
        led = {"last_monthly": "", "runs": [{"date": f"2020-01-{i:02d}"} for i in range(1, 29)] * 4}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.json")
            health_state.save(led, path)
            self.assertEqual(len(health_state.load(path)["runs"]), health_state.MAX_RUNS)


class TestCli(unittest.TestCase):
    def test_check_reports_due_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.json")
            health_state.main(["--path", path, "--date", "2026-09-10"])
            self.assertFalse(os.path.exists(path), "조회만 했는데 원장이 생겼다")

    def test_record_persists_and_flips_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.json")
            health_state.main(["--path", path, "--date", "2026-09-10",
                               "--record", "--monthly", "--notified", "--fixes", "4"])
            with open(path, encoding="utf-8") as fh:
                led = json.load(fh)
            self.assertEqual(led["last_monthly"], "2026-09")
            self.assertFalse(health_state.monthly_due(led, "2026-09-24"))


if __name__ == '__main__':
    unittest.main()
