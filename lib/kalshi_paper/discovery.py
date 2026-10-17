"""Event and bracket discovery (FR-003, FR-006).

For each active watch, list the series' open events from the API and store those whose
market date is the station's standard-time today or tomorrow. Nothing about event tickers is
hardcoded: the date comes from the ticker's `-YYMMMDD` suffix, whatever the series is called.

Each market gets a whole-degree set [int_low, int_high] (None = unbounded) derived from the
strikes and cross-checked against the human label; an event whose brackets do not form an
exact partition of the integers is skipped, never half-stored.
"""
import hashlib
import re
from datetime import date, timedelta

from . import kalshi_client, run_ledger, store, timeutil, watches
from .timeutil import to_utc_iso

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
_EVENT_DATE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})$")
_BELOW = re.compile(r"^\s*(-?\d+)\s*°\s*or\s+below\s*$")
_ABOVE = re.compile(r"^\s*(-?\d+)\s*°\s*or\s+above\s*$")
_BAND = re.compile(r"^\s*(-?\d+)\s*°\s*to\s+(-?\d+)\s*°\s*$")


class DiscoveryError(Exception):
    code = "discovery_error"


class BracketMismatch(DiscoveryError):
    code = "bracket_label_mismatch"


class BracketPartitionInvalid(DiscoveryError):
    code = "bracket_partition_invalid"


class EventNotExclusive(DiscoveryError):
    code = "event_not_exclusive"


def wanted_dates(now, tz_name):
    """(today, tomorrow) in the station's standard-time market calendar."""
    today = timeutil.market_date(now, tz_name)
    return today, today + timedelta(days=1)


def event_date(ticker):
    m = _EVENT_DATE.search(ticker)
    if not m or m.group(2) not in _MONTHS:
        raise DiscoveryError("cannot read a date from event ticker %r" % ticker)
    try:
        return date(2000 + int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3)))
    except ValueError:
        raise DiscoveryError("invalid date in event ticker %r" % ticker)


def rules_text(market):
    return ((market.get("rules_primary") or "").strip() + "\n\n" + (market.get("rules_secondary") or "").strip()).strip()


def rules_hash(market):
    return hashlib.sha256(rules_text(market).encode("utf-8")).hexdigest()


def label_range(label):
    """(low, high) from labels like '61° or below', '70° or above', '62° to 63°'; None if unrecognized."""
    label = label or ""
    if m := _BELOW.match(label):
        return (None, int(m.group(1)))
    if m := _ABOVE.match(label):
        return (int(m.group(1)), None)
    if m := _BAND.match(label):
        return (int(m.group(1)), int(m.group(2)))
    return None


def _whole(value, what, ticker):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise DiscoveryError("%s: %s must be a whole degree, got %r" % (ticker, what, value))
    return int(value)


def bracket_range(market):
    """Whole degrees the market's YES covers: less cap=C -> (None, C-1); greater floor=F -> (F+1, None);
    between F..C -> (F, C). Disagreement with the label raises BracketMismatch."""
    ticker, kind = market.get("ticker"), market.get("strike_type")
    if kind == "less":
        rng = (None, _whole(market.get("cap_strike"), "cap_strike", ticker) - 1)
    elif kind == "greater":
        rng = (_whole(market.get("floor_strike"), "floor_strike", ticker) + 1, None)
    elif kind == "between":
        rng = (_whole(market.get("floor_strike"), "floor_strike", ticker),
               _whole(market.get("cap_strike"), "cap_strike", ticker))
    else:
        raise DiscoveryError("%s: unsupported strike_type %r" % (ticker, kind))
    labelled = label_range(market.get("yes_sub_title"))
    if labelled is not None and labelled != rng:
        raise BracketMismatch("%s: label %r says %s but strikes say %s" % (
            ticker, market.get("yes_sub_title"), labelled, rng))
    return rng


def check_partition(ranges):
    """The event's brackets must tile the integers exactly: lower tail, contiguous bands, upper tail."""
    if len(ranges) < 2:
        raise BracketPartitionInvalid("an event needs at least a lower and an upper tail")
    ordered = sorted(ranges, key=lambda r: (r[0] is not None, r[0] if r[0] is not None else 0))
    if ordered[0][0] is not None or ordered[-1][1] is not None:
        raise BracketPartitionInvalid("missing lower or upper tail: %s" % (ordered,))
    for lo, hi in ordered:
        if lo is not None and hi is not None and lo > hi:
            raise BracketPartitionInvalid("empty band %s" % ((lo, hi),))
    for (_, prev_hi), (lo, _) in zip(ordered, ordered[1:]):
        if prev_hi is None or lo is None or lo != prev_hi + 1:
            raise BracketPartitionInvalid("gap or overlap between %s and %s" % (prev_hi, lo))


def _event_rows(event, watch, now_iso):
    """Validate one event and build its rows, or raise a DiscoveryError subclass."""
    if event.get("mutually_exclusive") is not True:
        raise EventNotExclusive("%s is not marked mutually exclusive" % event["event_ticker"])
    markets = event.get("markets") or []
    ranges = [bracket_range(m) for m in markets]
    check_partition(ranges)
    ev = {
        "ticker": event["event_ticker"], "watch_id": watch["id"],
        "local_date": event_date(event["event_ticker"]).isoformat(),
        "open_time": min((m.get("open_time") or "" for m in markets), default="") or None,
        "close_time": max((m.get("close_time") or "" for m in markets), default="") or None,
        "expected_expiration": max((m.get("expected_expiration_time") or "" for m in markets), default="") or None,
        "status": "open", "first_seen_at": now_iso,
    }
    mk = []
    for m, (lo, hi) in zip(markets, ranges):
        mk.append({
            "ticker": m["ticker"], "event_ticker": event["event_ticker"], "strike_type": m["strike_type"],
            "floor_strike": m.get("floor_strike"), "cap_strike": m.get("cap_strike"),
            "int_low": lo, "int_high": hi, "rules_hash": rules_hash(m), "rules_text": rules_text(m),
            "status": m.get("status") or "unknown",
        })
    return ev, mk


def discover_watch(con, client, watch, now):
    """Discover one watch's events for market today/tomorrow. Network errors propagate (KalshiSkip)."""
    now_iso = to_utc_iso(now)
    wanted = set(wanted_dates(now, watch["tz"]))
    res = {"series": watch["series_ticker"], "events_seen": 0, "events_new": 0, "markets_new": 0,
           "rules_changed": 0, "skipped": []}
    for event in client.events(watch["series_ticker"], status="open"):
        try:
            if event_date(event["event_ticker"]) not in wanted:
                continue
            res["events_seen"] += 1
            ev, markets = _event_rows(event, watch, now_iso)
        except DiscoveryError as e:
            res["skipped"].append({"code": e.code, "detail": str(e), "event": event.get("event_ticker")})
            continue
        with con:
            if store.insert_or_ignore(con, "events", ev):
                res["events_new"] += 1
            else:
                con.execute("UPDATE events SET close_time=?, expected_expiration=?, status='open' WHERE ticker=?",
                            (ev["close_time"], ev["expected_expiration"], ev["ticker"]))
            for m in markets:
                if store.insert_or_ignore(con, "markets", m):
                    res["markets_new"] += 1
                    continue
                old = con.execute("SELECT rules_hash FROM markets WHERE ticker=?", (m["ticker"],)).fetchone()
                if old["rules_hash"] != m["rules_hash"]:
                    res["rules_changed"] += 1
                con.execute("UPDATE markets SET status=?, rules_hash=?, rules_text=? WHERE ticker=?",
                            (m["status"], m["rules_hash"], m["rules_text"], m["ticker"]))
    return res


def discover_all(con, client, now, run_id=None):
    """Discover every active watch. Per-watch outages become recorded skips; a spent call budget stops the loop."""
    total = {"watches": 0, "events_new": 0, "markets_new": 0, "rules_changed": 0, "skipped": [], "partial": False}

    def skip(code, detail, watch, event=None, level="skip"):
        total["skipped"].append({"code": code, "detail": detail, "series": watch["series_ticker"], "event": event})
        total["partial"] = True
        if run_id is not None:
            run_ledger.record_event(con, run_id, level, code, detail, watch_id=watch["id"], now=now)

    for watch in watches.evaluable_watches(con):
        try:
            res = discover_watch(con, client, watch, now)
        except kalshi_client.BudgetExhausted as e:
            skip(e.code, str(e), watch)
            break
        except kalshi_client.KalshiSkip as e:
            skip(e.code, str(e), watch)
            continue
        except kalshi_client.KalshiError as e:
            skip("kalshi_error", str(e), watch, level="error")
            continue
        total["watches"] += 1
        for k in ("events_new", "markets_new", "rules_changed"):
            total[k] += res[k]
        for s in res["skipped"]:
            skip(s["code"], s["detail"], watch, event=s["event"])
    return total
