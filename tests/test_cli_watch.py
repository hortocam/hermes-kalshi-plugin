"""`kalshi-paper watch list|enable|pause|disable` (contracts/cli.md; FR-004, FR-005)."""
import json
import unittest

from lib.kalshi_paper import store
from tests.test_cli_init import InitCase, run_cli


class WatchCliTest(InitCase):
    def setUp(self):
        super().setUp()
        run_cli("--db", self.db, "init")

    def status(self, series):
        return self.rows("SELECT status FROM watches WHERE series_ticker='%s'" % series)[0][0]

    def test_list_json_shape(self):
        code, out, _ = run_cli("--db", self.db, "--json", "watch", "list")
        body = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(len(body["watches"]), 8)
        w = {x["series_ticker"]: x for x in body["watches"]}["KXHIGHCHI"]
        self.assertEqual((w["kind"], w["city"], w["cli_code"], w["obs_station"], w["status"]),
                         ("high", "Chicago", "CLIMDW", "KMDW", "active"))
        self.assertEqual(w["accounts"], {"real": "100.00", "test": "1000.00"})

    def test_list_human(self):
        code, out, _ = run_cli("--db", self.db, "watch", "list")
        self.assertEqual(code, 0)
        self.assertIn("KXHIGHTBOS", out)
        self.assertIn("active", out)
        self.assertEqual(len([l for l in out.splitlines() if l.startswith("KX")]), 8)

    def test_pause_then_enable(self):
        code, out, _ = run_cli("--db", self.db, "--json", "watch", "pause", "KXHIGHTBOS")
        self.assertEqual((code, json.loads(out)["status"], json.loads(out)["changed"]), (0, "paused", True))
        self.assertEqual(self.status("KXHIGHTBOS"), "paused")
        code, out, _ = run_cli("--db", self.db, "--json", "watch", "enable", "KXHIGHTBOS")
        self.assertEqual((code, json.loads(out)["status"]), (0, "active"))

    def test_disable(self):
        run_cli("--db", self.db, "watch", "disable", "KXLOWTNYC")
        self.assertEqual(self.status("KXLOWTNYC"), "disabled")

    def test_repeat_is_a_no_op_and_says_so(self):
        run_cli("--db", self.db, "watch", "pause", "KXHIGHNY")
        code, out, _ = run_cli("--db", self.db, "watch", "pause", "KXHIGHNY")
        self.assertEqual(code, 0)
        self.assertIn("no change", out)

    def test_enable_recreates_a_missing_watch_with_both_accounts(self):
        con = store.connect(self.db)
        con.execute("DELETE FROM accounts WHERE watch_id=(SELECT id FROM watches WHERE series_ticker='KXLOWTBOS')")
        con.execute("DELETE FROM watches WHERE series_ticker='KXLOWTBOS'")
        con.commit()
        con.close()
        code, out, _ = run_cli("--db", self.db, "--json", "watch", "enable", "KXLOWTBOS")
        body = json.loads(out)
        self.assertEqual((code, body["created_watch"], body["accounts_created"]), (0, True, 2))

    def test_custom_bankrolls_in_dollars(self):
        con = store.connect(self.db)
        con.execute("DELETE FROM accounts WHERE watch_id=(SELECT id FROM watches WHERE series_ticker='KXLOWTBOS')")
        con.commit()
        con.close()
        run_cli("--db", self.db, "watch", "enable", "KXLOWTBOS", "--real-dollars", "50", "--test-dollars", "500.50")
        rows = self.rows("SELECT scale, starting_cash_micro FROM accounts a JOIN watches w ON w.id=a.watch_id "
                         "WHERE w.series_ticker='KXLOWTBOS' ORDER BY scale")
        self.assertEqual([(r[0], r[1]) for r in rows], [("real", 50_000_000), ("test", 500_500_000)])

    def test_bad_amounts_and_unknown_series_exit_2(self):
        for argv in (("watch", "enable", "KXHIGHNY", "--real-dollars", "lots"),
                     ("watch", "enable", "KXHIGHNY", "--real-dollars", "-5"),
                     ("watch", "pause", "KXNOPE"),
                     ("watch", "enable", "KXNOPE"),
                     ("watch",),
                     ("watch", "explode", "KXHIGHNY")):
            code, _, err = run_cli("--db", self.db, *argv)
            self.assertEqual(code, 2, argv)

    def test_pause_leaves_accounts_alone(self):
        before = self.rows("SELECT count(*) FROM accounts")[0][0]
        run_cli("--db", self.db, "watch", "pause", "KXHIGHNY")
        self.assertEqual(self.rows("SELECT count(*) FROM accounts")[0][0], before)


if __name__ == "__main__":
    unittest.main()
