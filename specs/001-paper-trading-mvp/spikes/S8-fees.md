# S8: fee formula vs published schedule (T013)

**Status: PARTIAL.** Kalshi's official schedule (`kalshi.com/docs/kalshi-fee-schedule.pdf`) returned HTTP 429 to both curl and WebFetch on 2026-10-17, and was not retried. Everything below is reconciled against the series metadata plus secondary sources only. **Needs Cameron or Jarvis to read the official PDF** (see the checklist at the end) before T013 is ticked.

## What the live API says
`GET /series/{ticker}` for all 8 series: `fee_type: "quadratic"`, `fee_multiplier: 1`. So `M = 1` for every watched series. (Source: live calls, 2026-10-17.)

## Formula under test
`fee = ceil_to_cent(M x 0.07 x C x P x (1-P))`, C contracts, P price in dollars. Hand-computed (not by the code under test):

| # | C | P | 0.07 x C x P x (1-P) | Fee |
|---|---|---|---|---|
| 1 | 100 | 0.50 | 0.07 x 100 x 0.25 = 1.75 | $1.75 |
| 2 | 100 | 0.10 | 0.07 x 100 x 0.09 = 0.63 | $0.63 |
| 3 | 100 | 0.55 | 0.07 x 100 x 0.2475 = 1.7325 | $1.74 |
| 4 | 1 | 0.50 | 0.0175 | $0.02 |
| 5 | 10 | 0.95 | 0.07 x 10 x 0.0475 = 0.03325 | $0.04 |

Secondary sources (not authoritative) quote cases 1, 2 and 3 with the same results ($1.75, $0.63, $1.74): allium.so, sailgp.com fee page, pm.wiki. They also state a maker rate of 0.0175 (a quarter of taker); the MVP assumes taker fills only (walking the visible book), so maker fees are out of scope.

## Per-level vs per-order rounding (still open)
Ten 1-lot fills at $0.50: per-level rounding = 10 x $0.02 = **$0.20**; one 10-lot order = ceil(0.175) = **$0.18**. The working assumption stays **per-level, rounded up** (conservative; research.md R7). Cases 4 and 5 are the ones to compare with the official worked examples.

## Checklist for the official read (Cameron / Jarvis)
1. Confirm the 0.07 taker coefficient and that climate/weather series use the general schedule (no separate rate).
2. Confirm the rounding unit: per order vs per fill, and whether it is rounded up or to nearest.
3. Confirm any rounding-refund or minimum-fee rule.
4. Paste the relevant worked examples here and amend `research.md` R7 / `plan.md` only if they disagree.
