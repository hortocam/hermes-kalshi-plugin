# Kalshi public API notes

Credit: the endpoint behavior and gotchas below were first collected in the reference tool
`kalshi-plugin-x` (`skills/kalshi/references/api-endpoints.md`, Cameron Horton) and re-verified against the
live API for this project on 2026-10-16/17. Ported deliberately and checked, not copied wholesale.

Base URL: `https://api.elections.kalshi.com/trade-api/v2` (no authentication for any call this plugin makes).

## Calls used

| Call | Use |
|---|---|
| `GET /series/{ticker}` | metadata: `fee_type`, `fee_multiplier`, settlement sources |
| `GET /events?series_ticker=&status=open&limit=&with_nested_markets=true` | events and their bracket markets in one call |
| `GET /markets?event_ticker=` | markets of one event |
| `GET /markets/{ticker}` | one market (result after settlement) |
| `GET /markets/orderbooks?tickers=A&tickers=B` | batched orderbooks; **repeat** `tickers` |

Not used, on purpose: `GET /series` (the full list: ~18 MB, 429s), anything under `portfolio/`, `account/`,
`api_keys/` (signed endpoints; out of scope for the paper MVP, enforced by the `verify-no-auth` test).

## Quirks

1. **Bids only.** Books return `yes_dollars` and `no_dollars` ladders of `[price, size]` strings.
   `yes_ask = 1 - best NO bid`; `no_ask = 1 - best YES bid`. Example: NO bids `0.72 x 40`, `0.71 x 100`
   give YES asks `0.28 x 40`, `0.29 x 100`.
2. **Ladder order is not guaranteed.** Sort explicitly (bids descending, derived asks ascending).
3. **Repeated `tickers`.** `?tickers=A,B` returns HTTP 200 with a single book. A silent failure that looks
   like empty markets.
4. **Strings, not numbers.** Prices `"0.3600"` (2-4 decimals), counts `_fp` strings that can be fractional.
5. **Status vocabularies differ.** Market `status` values are lowercase lifecycle words (`active`,
   `finalized`); query filters use `open`, `closed`, `settled`.
6. **Deprecated:** `liquidity_dollars` (always `"0.0000"`); cent-denominated twins are gone.
7. **Settled markets** have `status: finalized`, `result: yes|no`, `expiration_value` (the observed
   temperature, e.g. `"72.00"`), `settlement_ts`.
8. **Rate limits are undocumented** for unauthenticated reads. A 429 body is `{"error":"too many requests"}`
   with no `Retry-After`. The client uses a token bucket (5 req/s default, `KALSHI_CLIENT_RPS`), exponential
   backoff with jitter (1 s base, 30 s cap), and a per-run call budget, and reports exhaustion as a skip.

## Climate-series facts (verified 2026-10-17)

- All eight series: `fee_type: quadratic`, `fee_multiplier: 1`, settlement source The Weather Company.
- CLI station codes from `rules_primary`: CLINYC, **CLIMDW** (Chicago = Midway), CLILAX, CLIBOS.
- Markets open the day before (~14:00Z) and close ~05:00Z the next day; six brackets per event
  (two tails `T`, four bands `B`).
