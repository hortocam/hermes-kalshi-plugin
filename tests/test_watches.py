"""US2 acceptance 1 and 3: enable creates a watch with two bankrolls; paused watches evaluate nothing
but their open positions still settle."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lib.kalshi_paper import bootstrap, store, watches

T0 = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 17, 13, 0, tzinfo=timezone.utc)
SERIES = "KXHIGHTBOS"


class WatchCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.con = store.connect(Path(self._tmp.name) / "data.db")
        self.addCleanup(self.con.close)
        bootstrap.initialize(self.con, now=T0)

    def accounts(self, series=SERIES):
        rows = self.con.execute(
            "SELECT a.scale, a.starting_cash_micro FROM accounts a JOIN watches w ON w.id=a.watch_id "
            "WHERE w.series_ticker=? ORDER BY a.scale", (series,)).fetchall()
        return {r["scale"]: r["starting_cash_micro"] for r in rows}

    def status(self, series=SERIES):
        return self.con.execute("SELECT status FROM watches WHERE series_ticker=?", (series,)).fetchone()[0]

    def open_position(self, series=SERIES):
        """Give a watch an open position (event, market, account, position rows)."""
        w = self.con.execute("SELECT id FROM watches WHERE series_ticker=?", (series,)).fetchone()["id"]
        acct = self.con.execute("SELECT id FROM accounts WHERE watch_id=? AND scale='test'", (w,)).fetchone()["id"]
        ev, mk = "%s-26OCT17" % series, "%s-26OCT17-T59" % series
        self.con.execute("INSERT INTO events (ticker, watch_id, local_date, status, first_seen_at) VALUES (?,?,?,?,?)",
                         (ev, w, "2026-10-17", "open", "x"))
        self.con.execute("INSERT INTO markets (ticker, event_ticker, strike_type, status, rules_hash) VALUES (?,?,?,?,?)",
                         (mk, ev, "less", "open", "h"))
        self.con.execute("INSERT INTO positions (account_id, market_ticker, side, contracts, cost_micro, fees_micro,"
                         " opened_first_at, opened_last_at, status) VALUES (?,?,?,?,?,?,?,?,?)",
                         (acct, mk, "yes", 5, 1_500_000, 20_000, "x", "x", "open"))
        self.con.commit()


class EnableTest(WatchCase):
    def test_enable_with_no_watch_creates_it_with_both_bankrolls(self):
        self.con.execute("DELETE FROM accounts WHERE watch_id=(SELECT id FROM watches WHERE series_ticker=?)", (SERIES,))
        self.con.execute("DELETE FROM watches WHERE series_ticker=?", (SERIES,))
        self.con.commit()
        r = watches.enable(self.con, SERIES, now=T1)
        self.assertEqual((r["status"], r["created_watch"], r["accounts_created"]), ("active", True, 2))
        # $100.00 and $1,000.00 in micro-dollars
        self.assertEqual(self.accounts(), {"real": 100_000_000, "test": 1_000_000_000})
        row = self.con.execute("SELECT kind, cli_code, strategy_version_id FROM watches WHERE series_ticker=?",
                               (SERIES,)).fetchone()
        self.assertEqual((row["kind"], row["cli_code"]), ("high", "CLIBOS"))
        self.assertIsNotNone(row["strategy_version_id"])

    def test_enable_is_idempotent(self):
        r = watches.enable(self.con, SERIES, now=T1)
        self.assertEqual((r["changed"], r["created_watch"], r["accounts_created"]), (False, False, 0))
        self.assertEqual(self.con.execute("SELECT count(*) FROM accounts").fetchone()[0], 16)

    def test_custom_bankrolls_apply_to_new_accounts_only(self):
        self.con.execute("DELETE FROM accounts WHERE watch_id=(SELECT id FROM watches WHERE series_ticker=?)", (SERIES,))
        self.con.commit()
        watches.enable(self.con, SERIES, real_micro=50_000_000, test_micro=500_000_000, now=T1)
        self.assertEqual(self.accounts(), {"real": 50_000_000, "test": 500_000_000})
        watches.enable(self.con, SERIES, real_micro=1, test_micro=1, now=T1)  # must not rewrite existing accounts
        self.assertEqual(self.accounts(), {"real": 50_000_000, "test": 500_000_000})

    def test_unknown_series_rejected(self):
        with self.assertRaises(watches.WatchError):
            watches.enable(self.con, "KXNOPE", now=T1)
        with self.assertRaises(watches.WatchError):
            watches.pause(self.con, "KXNOPE", now=T1)

    def test_bankroll_must_be_positive(self):
        with self.assertRaises(watches.WatchError):
            watches.enable(self.con, SERIES, real_micro=0, now=T1)


class PauseDisableTest(WatchCase):
    def test_pause_sets_status_keeps_accounts_and_stamps_update(self):
        r = watches.pause(self.con, SERIES, now=T1)
        self.assertEqual((r["status"], r["changed"]), ("paused", True))
        self.assertEqual(self.status(), "paused")
        self.assertEqual(len(self.accounts()), 2)
        row = self.con.execute("SELECT created_at, updated_at FROM watches WHERE series_ticker=?", (SERIES,)).fetchone()
        self.assertEqual((row["created_at"], row["updated_at"]), ("2026-10-17T12:00:00Z", "2026-10-17T13:00:00Z"))

    def test_repeating_a_status_changes_nothing(self):
        watches.pause(self.con, SERIES, now=T1)
        r = watches.pause(self.con, SERIES, now=datetime(2026, 10, 18, tzinfo=timezone.utc))
        self.assertFalse(r["changed"])
        row = self.con.execute("SELECT updated_at FROM watches WHERE series_ticker=?", (SERIES,)).fetchone()
        self.assertEqual(row["updated_at"], "2026-10-17T13:00:00Z")

    def test_disable_then_reenable(self):
        watches.disable(self.con, SERIES, now=T1)
        self.assertEqual(self.status(), "disabled")
        r = watches.enable(self.con, SERIES, now=T1)
        self.assertEqual((r["status"], r["changed"], r["accounts_created"]), ("active", True, 0))

    def test_paused_watch_is_not_evaluated(self):
        watches.pause(self.con, SERIES, now=T1)
        ev = {w["series_ticker"] for w in watches.evaluable_watches(self.con)}
        self.assertNotIn(SERIES, ev)
        self.assertEqual(len(ev), 7)

    def test_disabled_watch_is_not_evaluated_either(self):
        watches.disable(self.con, SERIES, now=T1)
        self.assertNotIn(SERIES, {w["series_ticker"] for w in watches.evaluable_watches(self.con)})

    def test_open_positions_still_settle_on_a_paused_watch(self):
        self.open_position()
        watches.pause(self.con, SERIES, now=T1)
        self.assertIn(SERIES, {w["series_ticker"] for w in watches.settleable_watches(self.con)})

    def test_open_positions_still_settle_on_a_disabled_watch(self):
        self.open_position()
        watches.disable(self.con, SERIES, now=T1)
        self.assertIn(SERIES, {w["series_ticker"] for w in watches.settleable_watches(self.con)})

    def test_disabled_watch_without_positions_has_nothing_to_settle(self):
        watches.disable(self.con, SERIES, now=T1)
        self.assertNotIn(SERIES, {w["series_ticker"] for w in watches.settleable_watches(self.con)})

    def test_settled_positions_do_not_keep_a_watch_settleable(self):
        self.open_position()
        self.con.execute("UPDATE positions SET status='settled'")
        self.con.commit()
        watches.disable(self.con, SERIES, now=T1)
        self.assertNotIn(SERIES, {w["series_ticker"] for w in watches.settleable_watches(self.con)})


class ListTest(WatchCase):
    def test_list_reports_status_and_accounts(self):
        watches.pause(self.con, "KXLOWTBOS", now=T1)
        rows = {w["series_ticker"]: w for w in watches.list_watches(self.con)}
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows["KXLOWTBOS"]["status"], "paused")
        self.assertEqual(rows["KXHIGHTBOS"]["accounts"], {"real": 100_000_000, "test": 1_000_000_000})
        self.assertEqual((rows["KXHIGHCHI"]["kind"], rows["KXHIGHCHI"]["cli_code"]), ("high", "CLIMDW"))


if __name__ == "__main__":
    unittest.main()
