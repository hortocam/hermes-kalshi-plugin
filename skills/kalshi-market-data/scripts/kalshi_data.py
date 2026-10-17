#!/usr/bin/env python3
"""kalshi-market-data: read-only Kalshi market data as JSON. Thin wrapper over lib/kalshi_paper.

Commands: series, events, markets, book, settled, overview. Keyless, public endpoints only;
no portfolio, no orders, no signing. Exit codes: 0 ok, 2 usage, 3 skipped (rate limit,
budget, outage; stdout names the skip code), 4 fatal (HTTP error, bad data).
"""
import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[3] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from kalshi_paper import kalshi_client, orderbook  # noqa: E402

DEFAULT_CALL_BUDGET = 40
DEFAULT_DEPTH = 5


def compact_market(m):
    return {
        "ticker": m["ticker"], "label": m.get("yes_sub_title"), "strike_type": m.get("strike_type"),
        "floor_strike": m.get("floor_strike"), "cap_strike": m.get("cap_strike"), "status": m.get("status"),
        "yes_bid": m.get("yes_bid_dollars"), "yes_ask": m.get("yes_ask_dollars"),
        "no_bid": m.get("no_bid_dollars"), "no_ask": m.get("no_ask_dollars"),
        "last_price": m.get("last_price_dollars"), "volume": m.get("volume_fp"),
        "open_interest": m.get("open_interest_fp"), "close_time": m.get("close_time"),
    }


def compact_settled(m):
    return {"ticker": m["ticker"], "label": m.get("yes_sub_title"), "status": m.get("status"),
            "result": kalshi_client.settled_result(m), "expiration_value": m.get("expiration_value")}


def book_json(book, depth):
    def levels(ls):
        return [{"price": l.price, "size": l.size} for l in ls[:depth]]
    return {"ticker": book.ticker, "yes_bids": levels(book.yes_bids), "no_bids": levels(book.no_bids),
            "yes_asks": levels(book.yes_asks), "no_asks": levels(book.no_asks),
            "yes_ask": book.yes_asks[0].price if book.yes_asks else None,
            "no_ask": book.no_asks[0].price if book.no_asks else None}


def _event(e, market_fn):
    return {"event_ticker": e["event_ticker"], "title": e.get("title"), "strike_date": e.get("strike_date"),
            "markets": [market_fn(m) for m in e.get("markets", [])]}


def cmd_series(client, a):
    s = client.series(a.ticker)
    keys = ("ticker", "title", "frequency", "category", "fee_type", "fee_multiplier", "settlement_sources")
    return {"series": {k: s.get(k) for k in keys}}


def cmd_events(client, a):
    events = client.events(a.series, status=a.status)
    return {"series": a.series, "status": a.status, "events": [_event(e, compact_market) for e in events]}


def cmd_markets(client, a):
    return {"event_ticker": a.event, "markets": [compact_market(m) for m in client.markets(a.event)]}


def cmd_book(client, a):
    books = client.orderbooks(a.tickers)
    return {"books": [book_json(books[t], a.depth) for t in a.tickers if t in books]}


def cmd_settled(client, a):
    events = client.events(a.series, status="settled", limit=a.limit)
    return {"series": a.series, "events": [_event(e, compact_settled) for e in events]}


def cmd_overview(client, a):
    """Series metadata + open events + one batched orderbook call: 3 Kalshi calls."""
    series = cmd_series(client, argparse.Namespace(ticker=a.series))["series"]
    events = client.events(a.series, status="open")
    tickers = [m["ticker"] for e in events for m in e.get("markets", [])]
    books = client.orderbooks(tickers)
    out = []
    for e in events:
        brackets = []
        for m in e.get("markets", []):
            b = compact_market(m)
            if m["ticker"] in books:
                b["book"] = book_json(books[m["ticker"]], a.depth)
            brackets.append(b)
        out.append({"event_ticker": e["event_ticker"], "title": e.get("title"),
                    "strike_date": e.get("strike_date"), "brackets": brackets})
    return {"series": series, "events": out, "kalshi_calls": client.calls}


COMMANDS = {"series": cmd_series, "events": cmd_events, "markets": cmd_markets, "book": cmd_book,
            "settled": cmd_settled, "overview": cmd_overview}


def build_parser():
    p = argparse.ArgumentParser(prog="kalshi_data", description=__doc__.strip().splitlines()[0])
    sub = p.add_subparsers(dest="command")
    sub.add_parser("series", help="series metadata (fee multiplier, settlement source)").add_argument("ticker")
    e = sub.add_parser("events", help="events with compact bracket quotes")
    e.add_argument("series")
    e.add_argument("--status", default="open", choices=["open", "closed", "settled"])
    sub.add_parser("markets", help="markets of one event").add_argument("event")
    b = sub.add_parser("book", help="orderbooks with derived asks (one batched call)")
    b.add_argument("tickers", nargs="+")
    b.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    s = sub.add_parser("settled", help="most recent settled events with results")
    s.add_argument("series")
    s.add_argument("--limit", type=int, default=1)
    o = sub.add_parser("overview", help="series + open events + books in 3 calls")
    o.add_argument("series")
    o.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    return p


def main(argv=None, client=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not args.command:
        build_parser().print_usage(sys.stderr)
        return 2
    client = client or kalshi_client.KalshiClient(budget=kalshi_client.CallBudget(DEFAULT_CALL_BUDGET))
    try:
        result = COMMANDS[args.command](client, args)
    except kalshi_client.KalshiSkip as e:
        print(json.dumps({"error": e.code, "skipped": True}))
        return 3
    except kalshi_client.KalshiHTTPError as e:
        print(json.dumps({"error": "http_%d" % e.status, "detail": str(e)}))
        return 4
    except (kalshi_client.KalshiError, orderbook.BookError) as e:
        print(json.dumps({"error": "bad_response", "detail": str(e)}))
        return 4
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
