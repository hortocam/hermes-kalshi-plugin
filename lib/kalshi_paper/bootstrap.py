"""`init`: migrate, then seed the default strategy version, watches, and accounts.

Idempotent and non-destructive: existing rows are never modified (a paused watch stays
paused); only missing rows are created.
"""
from datetime import datetime, timezone

from . import config, store, strategy
from .timeutil import to_utc_iso

TOTAL_TABLES = ("watches", "accounts", "strategy_versions")


def _count(con, table):
    return con.execute("SELECT count(*) FROM %s" % table).fetchone()[0]


def initialize(con, watches=None, now=None):
    """Returns {"created": {...}, "totals": {...}, "schema_version": n}."""
    watches = watches if watches is not None else config.load_watches()
    now_iso = to_utc_iso(now or datetime.now(timezone.utc))
    store.migrate(con)
    created = {"watches": 0, "accounts": 0, "strategy_versions": 0}
    with con:
        row = con.execute("SELECT id FROM strategy_versions WHERE source='default' AND parent_id IS NULL "
                          "ORDER BY id LIMIT 1").fetchone()
        if row:
            version_id = row["id"]
            params = strategy.DEFAULT_PARAMS
        else:
            params = strategy.DEFAULT_PARAMS
            version_id = con.execute(
                "INSERT INTO strategy_versions (params_json, source, created_at, note) VALUES (?, 'default', ?, ?)",
                (strategy.canonical_json(params), now_iso, "initial defaults")).lastrowid
            created["strategy_versions"] += 1
        bankrolls = {"real": params["bankrolls"]["real_micro"], "test": params["bankrolls"]["test_micro"]}
        for w in watches:
            if store.insert_or_ignore(con, "watches", {
                    "series_ticker": w["series_ticker"], "kind": w["kind"], "city": w["city"],
                    "cli_code": w["cli_code"], "obs_station": w["obs_station"], "lat": w["lat"],
                    "lon": w["lon"], "tz": w["tz"], "status": "active", "strategy_version_id": version_id,
                    "created_at": now_iso, "updated_at": now_iso}):
                created["watches"] += 1
            watch_id = con.execute("SELECT id FROM watches WHERE series_ticker=?", (w["series_ticker"],)).fetchone()["id"]
            for scale, cash in bankrolls.items():
                if store.insert_or_ignore(con, "accounts", {
                        "watch_id": watch_id, "scale": scale, "starting_cash_micro": cash, "created_at": now_iso}):
                    created["accounts"] += 1
    return {"created": created, "totals": {t: _count(con, t) for t in TOTAL_TABLES},
            "schema_version": store.current_version(con)}
