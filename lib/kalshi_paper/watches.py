"""Watches: enable / pause / disable a series in test mode, and who is evaluated or settled.

`active`   evaluated each slot; its open positions settle.
`paused`   evaluates nothing; open positions still settle (spec US2 scenario 3).
`disabled` evaluates nothing; open positions still settle (money is held to settlement).
Accounts are created once, never rewritten: changing bankrolls only affects new accounts.
"""
import json
from datetime import datetime, timezone

from . import config, money, store
from .timeutil import to_utc_iso


class WatchError(Exception):
    pass


def _iso(now):
    return to_utc_iso(now or datetime.now(timezone.utc))


def _default_version(con):
    row = con.execute("SELECT id, params_json FROM strategy_versions WHERE source='default' AND parent_id IS NULL "
                      "ORDER BY id LIMIT 1").fetchone()
    if not row:
        raise WatchError("no default strategy version; run `kalshi-paper init` first")
    return row


def _get(con, series):
    return con.execute("SELECT * FROM watches WHERE series_ticker=?", (series,)).fetchone()


def _require(con, series):
    w = _get(con, series)
    if not w:
        raise WatchError("unknown watch %r (enable it first if it is a supported series)" % series)
    return w


def _bankrolls(con, watch_row, real_micro, test_micro):
    params = json.loads(con.execute("SELECT params_json FROM strategy_versions WHERE id=?",
                                    (watch_row["strategy_version_id"],)).fetchone()[0])
    real = real_micro if real_micro is not None else params["bankrolls"]["real_micro"]
    test = test_micro if test_micro is not None else params["bankrolls"]["test_micro"]
    for name, v in (("real", real), ("test", test)):
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise WatchError("%s bankroll must be a positive integer of micro-dollars" % name)
    return {"real": real, "test": test}


def _ensure_accounts(con, watch_row, real_micro, test_micro, now_iso):
    cash = _bankrolls(con, watch_row, real_micro, test_micro)
    created = 0
    for scale, micro in cash.items():
        if store.insert_or_ignore(con, "accounts", {"watch_id": watch_row["id"], "scale": scale,
                                                    "starting_cash_micro": micro, "created_at": now_iso}):
            created += 1
    return created


def _result(series, status, changed, created_watch, accounts_created):
    return {"series": series, "status": status, "changed": changed,
            "created_watch": created_watch, "accounts_created": accounts_created}


def enable(con, series, real_micro=None, test_micro=None, now=None):
    now_iso = _iso(now)
    with con:
        w = _get(con, series)
        created_watch = False
        if not w:
            spec = next((x for x in config.load_watches() if x["series_ticker"] == series), None)
            if not spec:
                raise WatchError("unknown series %r: not in config/watches.default.json" % series)
            version = _default_version(con)
            con.execute(
                "INSERT INTO watches (series_ticker, kind, city, cli_code, obs_station, lat, lon, tz, status,"
                " strategy_version_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,'active',?,?,?)",
                (series, spec["kind"], spec["city"], spec["cli_code"], spec["obs_station"], spec["lat"],
                 spec["lon"], spec["tz"], version["id"], now_iso, now_iso))
            w = _get(con, series)
            created_watch = True
        changed = created_watch
        if w["status"] != "active":
            con.execute("UPDATE watches SET status='active', updated_at=? WHERE id=?", (now_iso, w["id"]))
            changed = True
        accounts_created = _ensure_accounts(con, w, real_micro, test_micro, now_iso)
    return _result(series, "active", changed or accounts_created > 0, created_watch, accounts_created)


def _set_status(con, series, status, now):
    with con:
        w = _require(con, series)
        if w["status"] == status:
            return _result(series, status, False, False, 0)
        con.execute("UPDATE watches SET status=?, updated_at=? WHERE id=?", (status, _iso(now), w["id"]))
    return _result(series, status, True, False, 0)


def pause(con, series, now=None):
    return _set_status(con, series, "paused", now)


def disable(con, series, now=None):
    return _set_status(con, series, "disabled", now)


def list_watches(con):
    out = []
    for w in con.execute("SELECT * FROM watches ORDER BY kind DESC, series_ticker"):
        accts = {r["scale"]: r["starting_cash_micro"] for r in con.execute(
            "SELECT scale, starting_cash_micro FROM accounts WHERE watch_id=?", (w["id"],))}
        d = dict(w)
        d["accounts"] = accts
        out.append(d)
    return out


def evaluable_watches(con):
    """Watches that get discovery, snapshots and recommendations this slot."""
    return con.execute("SELECT * FROM watches WHERE status='active' ORDER BY id").fetchall()


def settleable_watches(con):
    """Watches whose positions are settled: active or paused watches, and any watch with an open position."""
    return con.execute(
        "SELECT * FROM watches w WHERE w.status IN ('active', 'paused') OR EXISTS ("
        " SELECT 1 FROM positions p JOIN accounts a ON a.id=p.account_id WHERE a.watch_id=w.id AND p.status='open')"
        " ORDER BY w.id").fetchall()


def format_line(w):
    """One human-readable line for a `list_watches` row."""
    cash = {k: money.micro_to_dollars(v) for k, v in w["accounts"].items()}
    return "%-12s %-5s %-14s %-8s real $%s  test $%s" % (
        w["series_ticker"], w["kind"], w["city"], w["status"], cash.get("real", "-"), cash.get("test", "-"))


def describe(result):
    """One human-readable sentence for an enable/pause/disable result."""
    if not result["changed"]:
        return "%s: already %s, no change" % (result["series"], result["status"])
    extra = ", created watch" if result["created_watch"] else ""
    if result["accounts_created"]:
        extra += ", %d account%s created" % (result["accounts_created"], "" if result["accounts_created"] == 1 else "s")
    return "%s: %s%s" % (result["series"], result["status"], extra)
