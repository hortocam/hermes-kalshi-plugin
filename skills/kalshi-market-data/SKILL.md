---
name: kalshi-market-data
description: Read Kalshi climate-market data (daily high/low temperature brackets, quotes, orderbooks, settled results) through the public, keyless API. Read-only; never trades.
---

# kalshi-market-data

Use this skill to look at Kalshi's daily high/low temperature markets for NYC, Chicago, Los Angeles and Boston: which brackets exist, what they cost, how deep the books are, and how a finished day settled. Everything here is **public and read-only**. There is no login, no API key, no portfolio, and no way to place an order. If a task seems to need any of those, stop and tell the user.

Series: highs `KXHIGHNY, KXHIGHCHI, KXHIGHLAX, KXHIGHTBOS`; lows `KXLOWTNYC, KXLOWTCHI, KXLOWTLAX, KXLOWTBOS`.

## Commands

Run from the plugin root (the wrapper finds `lib/` itself). Output is JSON on stdout.

```sh
python3 skills/kalshi-market-data/scripts/kalshi_data.py overview KXHIGHTBOS   # series + open events + books, 3 calls
python3 skills/kalshi-market-data/scripts/kalshi_data.py series KXHIGHTBOS     # fee multiplier, settlement source
python3 skills/kalshi-market-data/scripts/kalshi_data.py events KXHIGHTBOS     # brackets and quotes (--status open|closed|settled)
python3 skills/kalshi-market-data/scripts/kalshi_data.py markets KXHIGHTBOS-26OCT17
python3 skills/kalshi-market-data/scripts/kalshi_data.py book TICKER [TICKER ...] --depth 5
python3 skills/kalshi-market-data/scripts/kalshi_data.py settled KXHIGHTBOS    # latest settled day with results
```

Exit codes: `0` ok, `2` usage, `3` skipped (rate limit, call budget, outage: stdout names the skip code), `4` fatal. A skip is a normal outcome: report it, do not retry in a loop, and never invent numbers to fill the gap.

## Quirks that matter (details in `references/api-notes.md`)

- **Orderbooks list bids only.** `yes_ask = 1 - best NO bid` and `no_ask = 1 - best YES bid`. The wrapper derives asks and sorts ladders best-first; do not trust arrival order.
- **Batched books repeat the `tickers` parameter**; a comma list silently returns one book and looks like "empty markets". The client does this correctly, so use `book A B C`, not one call per ticker.
- **Never list all series** (`/series` is ~18 MB and triggers 429). Only per-series lookups.
- **Prices are dollar strings** (`"0.3600"`) and sizes are fixed-point strings (`"83.35"`, fractional). Keep them as strings; do not do money math in floats.
- **Market `status` is lowercase** lifecycle (`active`, `finalized`), while the query filter says `open`/`settled`.
- **`liquidity_dollars` is deprecated** and always zero. Judge depth from the orderbook.
- **Bracket meaning**: a `less` market with `cap_strike 62` is "61° or below"; `greater` with `floor_strike 69` is "70° or above"; `between` 64..65 covers 64° and 65°. The labels (`label` field) are authoritative for humans.
- **Settlement**: the rules name The Weather Company and a CLI station code (Chicago is `CLIMDW`, Midway). A finalized market carries `result` (`yes`/`no`) and `expiration_value`.
- The client paces itself (about 5 requests/second), backs off on 429/5xx, and has a per-run call budget; expect `overview` to use 3 calls.

## Verify

`python3 -m unittest tests.test_kalshi_client tests.test_market_data_cli` (offline, recorded fixtures). Live check: `overview KXHIGHTBOS` should print brackets with books and `kalshi_calls` of 4 or fewer.
