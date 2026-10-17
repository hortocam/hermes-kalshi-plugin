"""quickstart A1: `kalshi-paper init` seeds 8 watches, 16 accounts, one strategy version; idempotent."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lib.kalshi_paper import cli, config, store, strategy
from tests.helpers import IsolatedHomeCase, temp_hermes_home

REPO = Path(__file__).resolve().parents[1]


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class InitCase(IsolatedHomeCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = str(Path(self._tmp.name) / "data.db")

    def rows(self, sql):
        con = store.connect(self.db)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()


class InitTest(InitCase):
    def test_first_run_creates_8_watches_16_accounts_1_strategy(self):
        code, out, _ = run_cli("--db", self.db, "--json", "init")
        self.assertEqual(code, 0)
        body = json.loads(out)
        self.assertEqual(body["created"], {"watches": 8, "accounts": 16, "strategy_versions": 1})
        self.assertEqual(body["totals"], {"watches": 8, "accounts": 16, "strategy_versions": 1})
        self.assertEqual(body["schema_version"], store.SCHEMA_VERSION)

    def test_accounts_hold_100_real_and_1000_test_dollars(self):
        run_cli("--db", self.db, "init")
        rows = self.rows("SELECT scale, starting_cash_micro, count(*) n FROM accounts GROUP BY scale, starting_cash_micro")
        got = {(r["scale"], r["starting_cash_micro"]): r["n"] for r in rows}
        # $100.00 = 100,000,000 micro; $1,000.00 = 1,000,000,000 micro; one of each per watch.
        self.assertEqual(got, {("real", 100_000_000): 8, ("test", 1_000_000_000): 8})

    def test_every_watch_points_at_the_default_strategy(self):
        run_cli("--db", self.db, "init")
        v = self.rows("SELECT id, source, parent_id FROM strategy_versions")
        self.assertEqual([(r["source"], r["parent_id"]) for r in v], [("default", None)])
        used = {r["strategy_version_id"] for r in self.rows("SELECT strategy_version_id FROM watches")}
        self.assertEqual(used, {v[0]["id"]})

    def test_seeded_watches_match_the_config_file(self):
        run_cli("--db", self.db, "init")
        rows = {r["series_ticker"]: r for r in self.rows("SELECT * FROM watches")}
        for w in config.load_watches():
            r = rows[w["series_ticker"]]
            self.assertEqual((r["kind"], r["cli_code"], r["obs_station"], r["tz"], r["status"]),
                             (w["kind"], w["cli_code"], w["obs_station"], w["tz"], "active"))
        self.assertEqual(rows["KXHIGHCHI"]["cli_code"], "CLIMDW")

    def test_second_run_changes_nothing(self):
        run_cli("--db", self.db, "--json", "init")
        before = {t: self.rows("SELECT * FROM %s" % t) for t in ("watches", "accounts", "strategy_versions")}
        before = {t: [tuple(r) for r in rs] for t, rs in before.items()}
        code, out, _ = run_cli("--db", self.db, "--json", "init")
        self.assertEqual(code, 0)
        body = json.loads(out)
        self.assertEqual(body["created"], {"watches": 0, "accounts": 0, "strategy_versions": 0})
        self.assertEqual(body["totals"], {"watches": 8, "accounts": 16, "strategy_versions": 1})
        after = {t: [tuple(r) for r in self.rows("SELECT * FROM %s" % t)] for t in before}
        self.assertEqual(before, after)

    def test_rerun_does_not_undo_a_paused_watch(self):
        run_cli("--db", self.db, "init")
        con = store.connect(self.db)
        con.execute("UPDATE watches SET status='paused' WHERE series_ticker='KXLOWTBOS'")
        con.commit()
        con.close()
        run_cli("--db", self.db, "init")
        self.assertEqual(self.rows("SELECT status FROM watches WHERE series_ticker='KXLOWTBOS'")[0][0], "paused")

    def test_rerun_restores_a_missing_account_only(self):
        run_cli("--db", self.db, "init")
        con = store.connect(self.db)
        con.execute("DELETE FROM accounts WHERE id = (SELECT min(id) FROM accounts)")
        con.commit()
        con.close()
        _, out, _ = run_cli("--db", self.db, "--json", "init")
        self.assertEqual(json.loads(out)["created"]["accounts"], 1)

    def test_human_output(self):
        _, out, _ = run_cli("--db", self.db, "init")
        self.assertIn("created 8 watches, 16 accounts, 1 strategy version", out)
        _, out, _ = run_cli("--db", self.db, "init")
        self.assertIn("no changes", out)

    def test_json_flag_accepted_after_the_command(self):
        code, out, _ = run_cli("--db", self.db, "init", "--json")
        self.assertEqual(code, 0)
        json.loads(out)

    def test_default_db_path_comes_from_hermes_home(self):
        with temp_hermes_home("kalshi-bot") as (root, home):
            code, _, _ = run_cli("init")
            self.assertEqual(code, 0)
            self.assertTrue((home / "plugin-data" / "hermes-kalshi" / "data.db").is_file())


class ErrorTest(InitCase):
    def test_newer_schema_exits_4(self):
        con = store.connect(self.db)
        store.migrate(con)
        con.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, 'x')", (store.SCHEMA_VERSION + 1,))
        con.commit()
        con.close()
        code, out, err = run_cli("--db", self.db, "init")
        self.assertEqual(code, 4)
        self.assertIn("schema", err)

    def test_unusable_db_path_exits_4(self):
        code, _, err = run_cli("--db", "/dev/null/nope/data.db", "init")
        self.assertEqual(code, 4)

    def test_unknown_command_exits_2(self):
        code, _, _ = run_cli("--db", self.db, "frobnicate")
        self.assertEqual(code, 2)

    def test_no_command_exits_2(self):
        code, _, _ = run_cli("--db", self.db)
        self.assertEqual(code, 2)


class StrategyDefaultsTest(unittest.TestCase):
    """Values quoted from contracts/strategy-config.md and CLAUDE.md defaults."""

    def test_defaults(self):
        p = strategy.DEFAULT_PARAMS
        self.assertEqual(p["min_net_edge"], 0.04)
        self.assertEqual(p["price_gate"], {"min": 0.05, "max": 0.95})
        self.assertEqual(p["kelly_fraction"], 0.25)
        self.assertEqual(p["caps"], {"per_trade": 0.05, "per_event": 0.10, "per_day": 0.20})
        self.assertEqual(p["llm_cap_points"], 15)
        self.assertEqual(p["max_snapshot_age_min"], 20)
        self.assertEqual(p["burn_in_days"], 3)
        self.assertEqual(p["calibration"]["default"], {"bias_f": 0.0, "sigma_f": 2.5})
        self.assertEqual(p["bankrolls"], {"real_micro": 100_000_000, "test_micro": 1_000_000_000})
        self.assertEqual(p["slots"], {"morning": "07:00", "midday": "12:30", "afternoon": "16:30",
                                      "tz": "America/New_York"})

    def test_keys_match_the_contract(self):
        self.assertEqual(set(strategy.DEFAULT_PARAMS), {
            "min_net_edge", "price_gate", "kelly_fraction", "shrink_weight_to_model", "caps",
            "llm_cap_points", "max_snapshot_age_min", "burn_in_days", "min_depth_contracts",
            "calibration", "bankrolls", "slots", "proposal_min_samples"})

    def test_canonical_json_is_stable(self):
        self.assertEqual(strategy.canonical_json(strategy.DEFAULT_PARAMS),
                         strategy.canonical_json(json.loads(json.dumps(strategy.DEFAULT_PARAMS))))


class EntryPointTest(unittest.TestCase):
    """Both invocations in contracts/cli.md work and never touch a real HERMES_HOME."""

    def _run(self, args, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "HERMES_HOME": tmp}
            env.pop("PYTHONPATH", None)
            env.update(kw.pop("env", {}))
            return subprocess.run(args, cwd=tmp, env=env, capture_output=True, text=True, **kw)

    def test_script_invocation(self):
        r = self._run([sys.executable, "-I", str(REPO / "lib" / "kalshi_paper" / "cli.py"), "--json", "init"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["totals"]["watches"], 8)

    def test_module_invocation(self):
        r = self._run([sys.executable, "-m", "kalshi_paper", "--json", "init"],
                      env={"PYTHONPATH": str(REPO / "lib")})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["totals"]["accounts"], 16)


if __name__ == "__main__":
    unittest.main()
