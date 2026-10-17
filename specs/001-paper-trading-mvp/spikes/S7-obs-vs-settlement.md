# S7: observation vs settlement discrepancy (T012, start-of-collection note)

Opened 2026-10-17. Closes after 10+ settled days per station (per plan.md).

## Setup facts (verified live 2026-10-17)
- Settlement source on all 8 series: **The Weather Company** (`settlement_sources`: `https://weather.com/kalshi`), station keyed by CLI code in `rules_primary`: CLINYC, **CLIMDW** (Chicago is Midway, not O'Hare), CLILAX, CLIBOS.
- Rules warn that preliminary readings "may be subject to rounding and conversion differences from the final reported value", and that expiration can be held for a revision.
- Nowcast observations come from `api.weather.gov` stations KNYC, KMDW, KLAX, KBOS (whole-degree-C METAR), per `config/watches.default.json`.

## How the table gets filled
Once US5 settlement runs, each settled day stores the observation extreme (LST day, converted to F) beside the Kalshi settled value; the difference per station is recorded below.

| Date | Station | Kind | Obs extreme (F) | Settled value (F) | Diff |
|---|---|---|---|---|---|
| (empty until US5 runs) | | | | | |

## Open questions
- Does the Weather Company daily value follow the same LST-day window as the observation feed?
- NYC: Central Park (KNYC) assumed for CLINYC; confirm against settled values.
