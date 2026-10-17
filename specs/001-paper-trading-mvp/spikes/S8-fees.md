# S8: fee formula vs published schedule (T013)

**Status: PASS with one open sub-question (rounding unit, see below).**

Source: Kalshi's official fee schedule PDF, saved by Cameron as `docs/kalshi-fee-schedule.pdf` ("Last updated and effective: July 7, 2026"). The site download returned HTTP 429 to the builder, so Cameron supplied the file. The PDF's text is glyph-encoded; the builder decoded it from its embedded ToUnicode maps (no tool installed). The PDF also points to `https://kalshi.com/fee-schedule` for scheduled upcoming fee changes: re-check before real trading.

## Confirmed
- General taker fee: `fees = round up(M x 0.07 x C x P x (1-P))`, P in dollars, C contracts, `M` default 1.
- Maker fee: `round up(M x 0.0175 x C x P x (1-P))`, charged only for resting orders that later execute; **maker `M` defaults to 0** unless a series says otherwise. MVP paper fills are taker fills against visible asks (no resting orders), so maker fees do not apply.
- No settlement, membership, or ACH fees.
- Weather series are **not** in the "Non-Standard Fees" series list (decoded pages 6-11 contain no `KXHIGH*`/`KXLOWT*`), so they use the general schedule. This agrees with the live API (`fee_type: quadratic`, `fee_multiplier: 1` on all 8 series).

## Hand cases vs the published table (page 4-5)
| C | P | Hand value | Published |
|---|---|---|---|
| 100 | 0.50 | 0.07 x 100 x 0.25 = 1.75 -> $1.75 | $1.75 |
| 100 | 0.10 | 0.63 -> $0.63 | $0.63 |
| 100 | 0.55 | 1.7325 -> $1.74 | $1.74 |
| 100 | 0.05 | 0.07 x 100 x 0.0475 = 0.3325 -> $0.34 | $0.34 |
| 1 | 0.50 | 0.0175 -> $0.02 | $0.02 |
| 1 | 0.95 | 0.07 x 0.0475 = 0.003325 -> $0.01 | $0.01 |

All six match the published table (it prints whole cents).

## Rounding: what the text says vs what the table shows
- The PDF defines "round up" as "rounds up such that the fee + positionCost is rounded to a **centicent**" ($0.0001).
- The published table, however, shows fees rounded up to whole **cents** (e.g. 100 @ $0.05 = $0.34, where centicent rounding would give $0.3325 -> $0.3325).
- Reading: the table is a cent-rounded display; the exchange's internal charge may be at centicent resolution on the order total. It cannot be resolved from the PDF alone.

**Decision for the MVP (unchanged, conservative):** ceil to the cent, applied per price-level fill (never lower than either reading, and slightly pessimistic for multi-level fills). Impact is a few cents per trade at most; the paper P&L stays slightly conservative. Record this in `research.md` R7 as settled for the MVP; revisit with real fill fee data before any real-money spec (`fee_cost` on real fills would settle it, but that needs authenticated access, out of scope).

## Per-level vs per-order (quantified)
Ten 1-lot fills at $0.50: per-level cent rounding = $0.20; one 10-lot order = ceil(0.175) = $0.18; centicent on the total = $0.0175 x 10 = $0.175. The spread across readings is about 2 cents on a 10-lot, small against the 0.04 min net edge gate.
