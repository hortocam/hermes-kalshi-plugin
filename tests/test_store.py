"""Schema tests. Constraint expectations are quoted from data-model.md."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lib.kalshi_paper import store

NOW = "2026-10-17T12:00:00Z"

TABLES = {
    "schema_version", "strategy_versions", "watches", "accounts", "snapshots", "events",
    "markets", "runs", "run_events", "predictions", "rationales", "recommendations",
    "order_intents", "fills", "positions", "settlements", "scores", "proposals", "cache_meta",
}


def ins(con, table, **cols):
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    cur = con.execute("INSERT INTO %s (%s) VALUES (%s)" % (table, names, marks), list(cols.values()))
    return cur.lastrowid


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "data.db"
        self.con = store.connect(self.path)
        store.migrate(self.con)
        self.addCleanup(self.con.close)

    # -- minimal parent rows -------------------------------------------------
    def strategy(self):
        return ins(self.con, "strategy_versions", params_json="{}", source="default", created_at=NOW)

    def watch(self, series="KXHIGHNY", kind="high"):
        return ins(self.con, "watches", series_ticker=series, kind=kind, city="NYC", cli_code="CLINYC",
                   obs_station="KNYC", lat=40.78, lon=-73.97, tz="America/New_York", status="active",
                   strategy_version_id=self.strategy(), created_at=NOW, updated_at=NOW)

    def account(self, watch_id, scale="test"):
        return ins(self.con, "accounts", watch_id=watch_id, scale=scale,
                   starting_cash_micro=1_000_000_000, created_at=NOW)

    def market(self, watch_id, ticker="KXHIGHNY-26OCT17-T62"):
        ins(self.con, "events", ticker="KXHIGHNY-26OCT17", watch_id=watch_id, local_date="2026-10-17",
            status="open", first_seen_at=NOW)
        ins(self.con, "markets", ticker=ticker, event_ticker="KXHIGHNY-26OCT17", strike_type="less",
            status="open", rules_hash="h")
        return ticker

    def snapshot(self, sid="abc"):
        ins(self.con, "snapshots", id=sid, slot_key="2026-10-17-morning", fetched_at=NOW, schema="1",
            sources_json="{}", blob=b"x", created_by_profile="kalshi-bot")
        return sid

    def prediction(self, ticker, sid="abc", model="m1"):
        return ins(self.con, "predictions", snapshot_id=sid, market_ticker=ticker, model_id=model,
                   p_ensemble=0.4, p_final=0.4, p_market=0.3, p_used=0.35, clipped=0, llm_status="none",
                   strategy_version_id=1, calib_bias=0.0, calib_sigma=2.5, created_at=NOW)


class SchemaTest(StoreCase):
    def test_all_tables_exist(self):
        rows = self.con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        self.assertTrue(TABLES <= {r[0] for r in rows})

    def test_migrate_is_idempotent(self):
        store.migrate(self.con)
        store.migrate(self.con)
        rows = self.con.execute("SELECT version FROM schema_version").fetchall()
        self.assertEqual([r[0] for r in rows], [store.SCHEMA_VERSION])

    def test_wal_and_foreign_keys_on(self):
        self.assertEqual(self.con.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_newer_schema_refused(self):
        self.con.execute("INSERT INTO schema_version (version, applied_at, note) VALUES (?, ?, 'future')",
                         (store.SCHEMA_VERSION + 1, NOW))
        with self.assertRaises(store.SchemaMismatch):
            store.migrate(self.con)

    def test_foreign_keys_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "accounts", watch_id=999, scale="test", starting_cash_micro=1, created_at=NOW)


class ConstraintTest(StoreCase):
    def test_watch_kind_in_high_low(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.watch(kind="mid")

    def test_watch_series_ticker_unique(self):
        self.watch()
        with self.assertRaises(sqlite3.IntegrityError):
            self.watch()

    def test_watch_status_constrained(self):
        sv = self.strategy()
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "watches", series_ticker="X", kind="high", city="c", cli_code="c", obs_station="s",
                lat=0, lon=0, tz="UTC", status="weird", strategy_version_id=sv, created_at=NOW, updated_at=NOW)

    def test_account_scale_in_real_test(self):
        w = self.watch()
        with self.assertRaises(sqlite3.IntegrityError):
            self.account(w, scale="demo")

    def test_account_unique_per_watch_and_scale(self):
        w = self.watch()
        self.account(w, "real")
        self.account(w, "test")
        with self.assertRaises(sqlite3.IntegrityError):
            self.account(w, "test")

    def test_prediction_unique_snapshot_market_model(self):
        w = self.watch()
        t = self.market(w)
        sid = self.snapshot()
        self.prediction(t, sid, "m1")
        self.prediction(t, sid, "m2")  # different model is fine
        with self.assertRaises(sqlite3.IntegrityError):
            self.prediction(t, sid, "m1")

    def _recommendation(self):
        w = self.watch()
        t = self.market(w)
        sid = self.snapshot()
        pid = self.prediction(t, sid)
        acct = self.account(w)
        rid = ins(self.con, "recommendations", prediction_id=pid, account_id=acct, decision="buy_yes",
                  strategy_version_id=1)
        return w, t, pid, acct, rid

    def test_recommendation_unique_prediction_account(self):
        w, t, pid, acct, rid = self._recommendation()
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "recommendations", prediction_id=pid, account_id=acct, decision="none",
                strategy_version_id=1)

    def test_recommendation_decision_constrained(self):
        w, t, pid, acct, rid = self._recommendation()
        acct2 = self.account(w, "real")
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "recommendations", prediction_id=pid, account_id=acct2, decision="sell",
                strategy_version_id=1)

    def _intent(self, mode="paper"):
        w, t, pid, acct, rid = self._recommendation()
        return ins(self.con, "order_intents", recommendation_id=rid, account_id=acct, market_ticker=t,
                   side="yes", action="buy", contracts=5, limit_price_micro=300_000, tif="ioc", mode=mode,
                   risk_check_json="{}", created_at=NOW)

    def test_order_intent_accepts_paper(self):
        self.assertTrue(self._intent("paper"))

    def test_order_intent_mode_is_paper_only(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._intent("live")

    def test_fill_unique_intent_level(self):
        iid = self._intent()
        ins(self.con, "fills", intent_id=iid, level_index=0, price_micro=280_000, contracts=3,
            fee_micro=20_000, book_ref="abc:yes")
        ins(self.con, "fills", intent_id=iid, level_index=1, price_micro=290_000, contracts=2,
            fee_micro=20_000, book_ref="abc:yes")
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "fills", intent_id=iid, level_index=1, price_micro=290_000, contracts=1,
                fee_micro=10_000, book_ref="abc:yes")

    def test_fill_price_contracts_fee_validation(self):
        iid = self._intent()
        base = dict(intent_id=iid, price_micro=280_000, contracts=3, fee_micro=20_000, book_ref="b")
        for i, override in enumerate((dict(price_micro=0), dict(price_micro=1_000_000),
                                      dict(contracts=0), dict(fee_micro=-1))):
            with self.assertRaises(sqlite3.IntegrityError, msg=str(override)):
                ins(self.con, "fills", level_index=10 + i, **{**base, **override})

    def test_runs_unique_profile_slot_job(self):
        ins(self.con, "runs", profile="kalshi-bot", slot_key="2026-10-17-morning", job="snapshot",
            started_at=NOW, status="running")
        ins(self.con, "runs", profile="kalshi-bot", slot_key="2026-10-17-morning", job="finalize",
            started_at=NOW, status="running")
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "runs", profile="kalshi-bot", slot_key="2026-10-17-morning", job="snapshot",
                started_at=NOW, status="running")

    def test_runs_job_and_status_constrained(self):
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "runs", profile="p", slot_key="s", job="trade", started_at=NOW, status="running")
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "runs", profile="p", slot_key="s", job="snapshot", started_at=NOW, status="meh")

    def test_run_event_level_constrained(self):
        rid = ins(self.con, "runs", profile="p", slot_key="s", job="snapshot", started_at=NOW, status="running")
        ins(self.con, "run_events", run_id=rid, at=NOW, level="skip", code="forecast_outage", detail="")
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "run_events", run_id=rid, at=NOW, level="loud", code="x", detail="")

    def test_position_unique_account_market_side(self):
        w = self.watch()
        t = self.market(w)
        a = self.account(w)
        row = dict(account_id=a, market_ticker=t, side="yes", contracts=5, cost_micro=1, fees_micro=0,
                   opened_first_at=NOW, opened_last_at=NOW, status="open")
        ins(self.con, "positions", **row)
        ins(self.con, "positions", **{**row, "side": "no"})
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "positions", **row)

    def test_market_strike_type_and_result_constrained(self):
        w = self.watch()
        self.market(w)
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "markets", ticker="m2", event_ticker="KXHIGHNY-26OCT17", strike_type="point",
                status="open", rules_hash="h")
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "markets", ticker="m3", event_ticker="KXHIGHNY-26OCT17", strike_type="less",
                status="open", rules_hash="h", result="maybe")

    def test_settlement_requires_asof_and_fetched_at(self):
        w = self.watch()
        t = self.market(w)
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "settlements", market_ticker=t, result="yes", settled_at=NOW, source_rules_hash="h",
                fetched_at=NOW)  # asof missing
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "settlements", market_ticker=t, result="yes", settled_at=NOW, source_rules_hash="h",
                asof=NOW)  # fetched_at missing

    def test_score_primary_key_and_predictor(self):
        w = self.watch()
        t = self.market(w)
        pid = self.prediction(t, self.snapshot())
        row = dict(prediction_id=pid, predictor="ensemble", outcome=1, p=0.4, brier=0.36, log_loss=0.9, scored_at=NOW)
        ins(self.con, "scores", **row)
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "scores", **row)
        with self.assertRaises(sqlite3.IntegrityError):
            ins(self.con, "scores", **{**row, "predictor": "vibes"})

    def test_no_credential_columns(self):
        for t in TABLES:
            cols = [r[1].lower() for r in self.con.execute("PRAGMA table_info(%s)" % t)
                    if r[1] not in ("tokens_in", "tokens_out")]  # LLM usage counters, not credentials
            for bad in ("password", "secret", "api_key", "token", "private_key"):
                self.assertFalse(any(bad in c for c in cols), "%s.%s" % (t, bad))


class HelperTest(StoreCase):
    def test_insert_or_ignore_reports_whether_inserted(self):
        row = dict(profile="p", slot_key="s", job="snapshot", started_at=NOW, status="running")
        self.assertTrue(store.insert_or_ignore(self.con, "runs", row))
        self.assertFalse(store.insert_or_ignore(self.con, "runs", row))
        self.assertEqual(self.con.execute("SELECT count(*) FROM runs").fetchone()[0], 1)

    def test_upsert_updates_listed_columns(self):
        store.upsert(self.con, "cache_meta", dict(key="k", value="1", fetched_at=NOW, expires_at=NOW),
                     conflict=["key"], update=["value", "fetched_at"])
        store.upsert(self.con, "cache_meta", dict(key="k", value="2", fetched_at="2026-10-18T00:00:00Z", expires_at=NOW),
                     conflict=["key"], update=["value", "fetched_at"])
        row = self.con.execute("SELECT value, fetched_at FROM cache_meta WHERE key='k'").fetchone()
        self.assertEqual((row[0], row[1]), ("2", "2026-10-18T00:00:00Z"))

    def test_table_names_are_validated(self):
        with self.assertRaises(ValueError):
            store.insert_or_ignore(self.con, "runs; DROP TABLE runs", {"a": 1})


class ReadOnlyTest(StoreCase):
    def test_read_only_open_can_read_not_write(self):
        self.watch()
        self.con.commit()
        ro = store.connect_readonly(self.path)
        self.addCleanup(ro.close)
        self.assertEqual(ro.execute("SELECT count(*) FROM watches").fetchone()[0], 1)
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute("DELETE FROM watches")

    def test_read_only_open_of_missing_db_fails(self):
        with self.assertRaises(sqlite3.OperationalError):
            store.connect_readonly(Path(self._tmp.name) / "missing.db")


if __name__ == "__main__":
    unittest.main()
