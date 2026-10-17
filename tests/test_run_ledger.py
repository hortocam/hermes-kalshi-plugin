import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib.kalshi_paper import run_ledger, store

T0 = datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc)
SLOT = "2026-10-17-midday"


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "data.db"
        self.con = store.connect(self.path)
        store.migrate(self.con)
        self.addCleanup(self.con.close)

    def begin(self, job="snapshot", now=T0, **kw):
        return run_ledger.begin_run(self.con, "kalshi-bot", SLOT, job, now=now, **kw)


class BeginFinishTest(LedgerCase):
    def test_first_begin_starts_a_running_row(self):
        r = self.begin()
        self.assertEqual(r.state, "started")
        row = self.con.execute("SELECT * FROM runs WHERE id=?", (r.run_id,)).fetchone()
        self.assertEqual((row["status"], row["profile"], row["slot_key"], row["job"]),
                         ("running", "kalshi-bot", SLOT, "snapshot"))
        self.assertEqual(row["started_at"], "2026-10-17T11:00:00Z")
        self.assertIsNone(row["finished_at"])

    def test_finish_ok_sets_terminal_state(self):
        r = self.begin()
        run_ledger.finish_run(self.con, r.run_id, "ok", now=T0 + timedelta(minutes=2))
        row = self.con.execute("SELECT status, finished_at FROM runs WHERE id=?", (r.run_id,)).fetchone()
        self.assertEqual((row["status"], row["finished_at"]), ("ok", "2026-10-17T11:02:00Z"))

    def test_second_begin_after_ok_is_already_done_and_adds_no_rows(self):
        r = self.begin()
        run_ledger.finish_run(self.con, r.run_id, "ok", now=T0)
        again = self.begin()
        self.assertEqual((again.state, again.run_id, again.status), ("already_done", r.run_id, "ok"))
        self.assertEqual(self.con.execute("SELECT count(*) FROM runs").fetchone()[0], 1)

    def test_skipped_is_terminal_too(self):
        r = self.begin()
        run_ledger.finish_run(self.con, r.run_id, "skipped", now=T0)
        self.assertEqual(self.begin().state, "already_done")

    def test_failed_and_partial_may_be_retried_same_row(self):
        for status in ("failed", "partial"):
            with self.subTest(status=status):
                self.con.execute("DELETE FROM run_events")
                self.con.execute("DELETE FROM runs")
                r = self.begin()
                run_ledger.finish_run(self.con, r.run_id, status, now=T0)
                retry = self.begin(now=T0 + timedelta(minutes=5))
                self.assertEqual((retry.state, retry.run_id), ("started", r.run_id))
                row = self.con.execute("SELECT status, finished_at, started_at FROM runs").fetchone()
                self.assertEqual((row["status"], row["finished_at"]), ("running", None))
                self.assertEqual(row["started_at"], "2026-10-17T11:05:00Z")

    def test_begin_while_running_reports_in_progress(self):
        r = self.begin()
        other = self.begin(now=T0 + timedelta(minutes=1))
        self.assertEqual((other.state, other.run_id), ("in_progress", r.run_id))

    def test_stale_running_row_can_be_taken_over(self):
        r = self.begin()
        later = T0 + timedelta(seconds=run_ledger.STALE_AFTER_SECONDS + 1)
        take = self.begin(now=later)
        self.assertEqual((take.state, take.run_id), ("started", r.run_id))

    def test_jobs_are_independent(self):
        a = self.begin("snapshot")
        b = self.begin("finalize")
        self.assertNotEqual(a.run_id, b.run_id)
        self.assertEqual(b.state, "started")

    def test_invalid_job_and_status_rejected(self):
        with self.assertRaises(ValueError):
            self.begin("trade")
        r = self.begin()
        with self.assertRaises(ValueError):
            run_ledger.finish_run(self.con, r.run_id, "running", now=T0)

    def test_finish_requires_a_running_row(self):
        r = self.begin()
        run_ledger.finish_run(self.con, r.run_id, "ok", now=T0)
        with self.assertRaises(run_ledger.RunStateError):
            run_ledger.finish_run(self.con, r.run_id, "failed", now=T0)

    def test_model_id_recorded(self):
        r = self.begin("evaluate", model_id="glm-5")
        row = self.con.execute("SELECT model_id FROM runs WHERE id=?", (r.run_id,)).fetchone()
        self.assertEqual(row["model_id"], "glm-5")


class EventsTest(LedgerCase):
    def test_skip_recorded_with_code_and_detail(self):
        r = self.begin()
        run_ledger.record_event(self.con, r.run_id, "skip", "forecast_outage", "open-meteo 503", now=T0)
        ev = run_ledger.events(self.con, r.run_id)
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["level"], ev[0]["code"], ev[0]["detail"], ev[0]["at"]),
                         ("skip", "forecast_outage", "open-meteo 503", "2026-10-17T11:00:00Z"))

    def test_events_survive_a_retry(self):
        r = self.begin()
        run_ledger.record_event(self.con, r.run_id, "error", "kalshi_429_budget", now=T0)
        run_ledger.finish_run(self.con, r.run_id, "partial", now=T0)
        self.begin(now=T0 + timedelta(minutes=5))
        self.assertEqual(len(run_ledger.events(self.con, r.run_id)), 1)

    def test_invalid_level_rejected(self):
        r = self.begin()
        with self.assertRaises(ValueError):
            run_ledger.record_event(self.con, r.run_id, "loud", "x", now=T0)

    def test_skip_count_helper(self):
        r = self.begin()
        run_ledger.record_event(self.con, r.run_id, "skip", "a", now=T0)
        run_ledger.record_event(self.con, r.run_id, "info", "b", now=T0)
        run_ledger.record_event(self.con, r.run_id, "skip", "c", now=T0)
        self.assertEqual(run_ledger.count_events(self.con, r.run_id, "skip"), 2)


class ConcurrencyTest(LedgerCase):
    def test_concurrent_begin_yields_one_runner(self):
        self.con.commit()
        results, errors = [], []
        barrier = threading.Barrier(8)

        def worker():
            con = store.connect(self.path)
            try:
                barrier.wait()
                results.append(run_ledger.begin_run(con, "kalshi-bot", SLOT, "snapshot", now=T0).state)
            except Exception as e:  # pragma: no cover - reported below
                errors.append(repr(e))
            finally:
                con.close()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(results.count("started"), 1)
        self.assertEqual(results.count("in_progress"), 7)
        self.assertEqual(self.con.execute("SELECT count(*) FROM runs").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
