"""SQLite store: schema (data-model.md), migrations, connectors, upsert helpers.

Money columns are integer micro-dollars. Read-model views (v_account_ledger etc.) are
added by the stories that need them, as later schema versions.
"""
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


class SchemaMismatch(Exception):
    """The database was written by a newer schema than this code understands."""


_DDL_V1 = """
CREATE TABLE schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    note       TEXT
);

CREATE TABLE strategy_versions (
    id          INTEGER PRIMARY KEY,
    parent_id   INTEGER REFERENCES strategy_versions(id),
    params_json TEXT NOT NULL,
    source      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    note        TEXT
);

CREATE TABLE watches (
    id                  INTEGER PRIMARY KEY,
    series_ticker       TEXT NOT NULL UNIQUE,
    kind                TEXT NOT NULL CHECK (kind IN ('high', 'low')),
    city                TEXT NOT NULL,
    cli_code            TEXT NOT NULL,
    obs_station         TEXT NOT NULL,
    lat                 REAL NOT NULL,
    lon                 REAL NOT NULL,
    tz                  TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'disabled')),
    strategy_version_id INTEGER NOT NULL REFERENCES strategy_versions(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE accounts (
    id                  INTEGER PRIMARY KEY,
    watch_id            INTEGER NOT NULL REFERENCES watches(id),
    scale               TEXT NOT NULL CHECK (scale IN ('real', 'test')),
    starting_cash_micro INTEGER NOT NULL CHECK (starting_cash_micro > 0),
    created_at          TEXT NOT NULL,
    UNIQUE (watch_id, scale)
);

CREATE TABLE snapshots (
    id                 TEXT PRIMARY KEY,
    slot_key           TEXT NOT NULL,
    fetched_at         TEXT NOT NULL,
    schema             TEXT NOT NULL,
    sources_json       TEXT NOT NULL,
    blob               BLOB NOT NULL,
    created_by_profile TEXT NOT NULL
);
CREATE INDEX idx_snapshots_slot ON snapshots(slot_key);

CREATE TABLE events (
    ticker              TEXT PRIMARY KEY,
    watch_id            INTEGER NOT NULL REFERENCES watches(id),
    local_date          TEXT NOT NULL,
    open_time           TEXT,
    close_time          TEXT,
    expected_expiration TEXT,
    status              TEXT NOT NULL,
    first_seen_at       TEXT NOT NULL
);
CREATE INDEX idx_events_watch_date ON events(watch_id, local_date);

CREATE TABLE markets (
    ticker           TEXT PRIMARY KEY,
    event_ticker     TEXT NOT NULL REFERENCES events(ticker),
    strike_type      TEXT NOT NULL CHECK (strike_type IN ('greater', 'less', 'between')),
    floor_strike     REAL,
    cap_strike       REAL,
    int_low          INTEGER,
    int_high         INTEGER,
    rules_hash       TEXT NOT NULL,
    rules_text       TEXT,
    status           TEXT NOT NULL,
    result           TEXT CHECK (result IS NULL OR result IN ('yes', 'no')),
    settled_value    REAL,
    settled_at       TEXT,
    settle_asof      TEXT,
    settle_fetched_at TEXT
);
CREATE INDEX idx_markets_event ON markets(event_ticker);

CREATE TABLE runs (
    id          INTEGER PRIMARY KEY,
    profile     TEXT NOT NULL,
    slot_key    TEXT NOT NULL,
    job         TEXT NOT NULL CHECK (job IN ('snapshot', 'evaluate', 'finalize', 'settle', 'learn')),
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL CHECK (status IN ('running', 'ok', 'partial', 'skipped', 'failed')),
    model_id    TEXT,
    UNIQUE (profile, slot_key, job)
);

CREATE TABLE run_events (
    id       INTEGER PRIMARY KEY,
    run_id   INTEGER NOT NULL REFERENCES runs(id),
    at       TEXT NOT NULL,
    level    TEXT NOT NULL CHECK (level IN ('info', 'skip', 'error')),
    watch_id INTEGER REFERENCES watches(id),
    code     TEXT NOT NULL,
    detail   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_run_events_run ON run_events(run_id);

CREATE TABLE rationales (
    id           INTEGER PRIMARY KEY,
    event_ticker TEXT NOT NULL,
    snapshot_id  TEXT NOT NULL REFERENCES snapshots(id),
    model_id     TEXT NOT NULL,
    text         TEXT NOT NULL,
    raw_hash     TEXT NOT NULL,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    created_at   TEXT NOT NULL
);

CREATE TABLE predictions (
    id                  INTEGER PRIMARY KEY,
    snapshot_id         TEXT NOT NULL REFERENCES snapshots(id),
    market_ticker       TEXT NOT NULL REFERENCES markets(ticker),
    model_id            TEXT NOT NULL,
    p_ensemble          REAL NOT NULL CHECK (p_ensemble BETWEEN 0 AND 1),
    p_llm_proposed      REAL CHECK (p_llm_proposed IS NULL OR p_llm_proposed BETWEEN 0 AND 1),
    p_final             REAL NOT NULL CHECK (p_final BETWEEN 0 AND 1),
    p_market            REAL NOT NULL CHECK (p_market BETWEEN 0 AND 1),
    p_used              REAL NOT NULL CHECK (p_used BETWEEN 0 AND 1),
    clipped             INTEGER NOT NULL DEFAULT 0 CHECK (clipped IN (0, 1)),
    llm_status          TEXT NOT NULL CHECK (llm_status IN ('ok', 'failed', 'timeout', 'invalid', 'none')),
    rationale_id        INTEGER REFERENCES rationales(id),
    strategy_version_id INTEGER NOT NULL REFERENCES strategy_versions(id),
    calib_bias          REAL NOT NULL,
    calib_sigma         REAL NOT NULL,
    created_at          TEXT NOT NULL,
    UNIQUE (snapshot_id, market_ticker, model_id)
);
CREATE INDEX idx_predictions_snapshot ON predictions(snapshot_id);

CREATE TABLE recommendations (
    id                          INTEGER PRIMARY KEY,
    prediction_id               INTEGER NOT NULL REFERENCES predictions(id),
    account_id                  INTEGER NOT NULL REFERENCES accounts(id),
    decision                    TEXT NOT NULL CHECK (decision IN ('buy_yes', 'buy_no', 'none')),
    reject_code                 TEXT,
    net_edge_micro_per_contract INTEGER,
    kelly_contracts             INTEGER,
    final_contracts             INTEGER,
    binding_cap                 TEXT CHECK (binding_cap IS NULL OR binding_cap IN ('kelly', 'trade', 'event', 'day', 'depth')),
    strategy_version_id         INTEGER NOT NULL REFERENCES strategy_versions(id),
    UNIQUE (prediction_id, account_id)
);

CREATE TABLE order_intents (
    id                INTEGER PRIMARY KEY,
    recommendation_id INTEGER NOT NULL UNIQUE REFERENCES recommendations(id),
    account_id        INTEGER NOT NULL REFERENCES accounts(id),
    market_ticker     TEXT NOT NULL REFERENCES markets(ticker),
    side              TEXT NOT NULL CHECK (side IN ('yes', 'no')),
    action            TEXT NOT NULL CHECK (action = 'buy'),
    contracts         INTEGER NOT NULL CHECK (contracts > 0),
    limit_price_micro INTEGER NOT NULL CHECK (limit_price_micro > 0 AND limit_price_micro < 1000000),
    tif               TEXT NOT NULL CHECK (tif = 'ioc'),
    mode              TEXT NOT NULL CHECK (mode = 'paper'),
    risk_check_json   TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE fills (
    id          INTEGER PRIMARY KEY,
    intent_id   INTEGER NOT NULL REFERENCES order_intents(id),
    level_index INTEGER NOT NULL,
    price_micro INTEGER NOT NULL CHECK (price_micro > 0 AND price_micro < 1000000),
    contracts   INTEGER NOT NULL CHECK (contracts > 0),
    fee_micro   INTEGER NOT NULL CHECK (fee_micro >= 0),
    book_ref    TEXT NOT NULL,
    UNIQUE (intent_id, level_index)
);
CREATE INDEX idx_fills_intent ON fills(intent_id);

CREATE TABLE positions (
    id               INTEGER PRIMARY KEY,
    account_id       INTEGER NOT NULL REFERENCES accounts(id),
    market_ticker    TEXT NOT NULL REFERENCES markets(ticker),
    side             TEXT NOT NULL CHECK (side IN ('yes', 'no')),
    contracts        INTEGER NOT NULL CHECK (contracts > 0),
    cost_micro       INTEGER NOT NULL,
    fees_micro       INTEGER NOT NULL CHECK (fees_micro >= 0),
    opened_first_at  TEXT NOT NULL,
    opened_last_at   TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('open', 'settled', 'void')),
    realized_pnl_micro INTEGER,
    settled_at       TEXT,
    UNIQUE (account_id, market_ticker, side)
);
CREATE INDEX idx_positions_account ON positions(account_id);

CREATE TABLE settlements (
    market_ticker     TEXT PRIMARY KEY REFERENCES markets(ticker),
    result            TEXT NOT NULL CHECK (result IN ('yes', 'no', 'void')),
    settled_value     REAL,
    settled_at        TEXT NOT NULL,
    source_rules_hash TEXT NOT NULL,
    asof              TEXT NOT NULL,
    fetched_at        TEXT NOT NULL
);

CREATE TABLE scores (
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    predictor     TEXT NOT NULL CHECK (predictor IN ('ensemble', 'final', 'market', 'used')),
    outcome       INTEGER NOT NULL CHECK (outcome IN (0, 1)),
    p             REAL NOT NULL CHECK (p BETWEEN 0 AND 1),
    brier         REAL NOT NULL,
    log_loss      REAL NOT NULL,
    scored_at     TEXT NOT NULL,
    PRIMARY KEY (prediction_id, predictor)
);

CREATE TABLE proposals (
    id                 INTEGER PRIMARY KEY,
    created_at         TEXT NOT NULL,
    scope              TEXT NOT NULL,
    evidence_json      TEXT NOT NULL,
    params_diff_json   TEXT NOT NULL,
    diff_hash          TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'superseded')),
    decided_at         TEXT,
    decided_by         TEXT,
    resulting_version_id INTEGER REFERENCES strategy_versions(id)
);
CREATE UNIQUE INDEX idx_proposals_pending_dedupe ON proposals(scope, diff_hash) WHERE status = 'pending';

CREATE TABLE cache_meta (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    expires_at TEXT
);
"""

# Append-only: (version, note, ddl). Never edit an applied entry.
MIGRATIONS = [(1, "initial schema", _DDL_V1)]

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ident(name):
    if not _IDENT.match(name):
        raise ValueError("bad SQL identifier: %r" % (name,))
    return name


def connect(path):
    """Open (creating if needed) a read-write connection: WAL, foreign keys, busy timeout."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def connect_readonly(path):
    """Read-only connection for the dashboard (`file:...?mode=ro`, 2 s busy timeout)."""
    uri = "file:%s?mode=ro" % Path(path).resolve()
    con = sqlite3.connect(uri, uri=True, timeout=2)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=2000")
    return con


def current_version(con):
    has = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone()
    if not has:
        return 0
    return con.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]


def migrate(con):
    """Apply pending migrations; idempotent. Refuses a database from a newer schema."""
    have = current_version(con)
    if have > SCHEMA_VERSION:
        raise SchemaMismatch("database schema %d is newer than code schema %d" % (have, SCHEMA_VERSION))
    for version, note, ddl in MIGRATIONS:
        if version <= have:
            continue
        # DDL and the version row commit together, so a crash cannot leave a half-applied schema.
        record = "INSERT INTO schema_version (version, applied_at, note) VALUES (%d, '%s', '%s');" % (
            version, _now(), note.replace("'", "''"))
        con.executescript("BEGIN;\n%s\n%s\nCOMMIT;" % (ddl, record))


def insert_or_ignore(con, table, row):
    """INSERT ... ON CONFLICT DO NOTHING. Returns True when a row was inserted."""
    cols = [_ident(c) for c in row]
    sql = "INSERT INTO %s (%s) VALUES (%s) ON CONFLICT DO NOTHING" % (
        _ident(table), ", ".join(cols), ", ".join("?" for _ in cols))
    return con.execute(sql, list(row.values())).rowcount == 1


def upsert(con, table, row, conflict, update):
    """INSERT ... ON CONFLICT (conflict cols) DO UPDATE SET <update cols> = excluded.<col>."""
    cols = [_ident(c) for c in row]
    sets = ", ".join("%s = excluded.%s" % (_ident(c), c) for c in update)
    sql = "INSERT INTO %s (%s) VALUES (%s) ON CONFLICT (%s) DO UPDATE SET %s" % (
        _ident(table), ", ".join(cols), ", ".join("?" for _ in cols),
        ", ".join(_ident(c) for c in conflict), sets)
    con.execute(sql, list(row.values()))
