# Requirements Brief — Addendum 1 (2026-10-15, supersedes conflicting lines in requirements-brief.md)

## Resolved
- Cities: NYC, Chicago, LA, Boston (Miami dropped). Series: KXHIGHNY/KXLOWTNYC, KXHIGHCHI/KXLOWTCHI, KXHIGHLAX/KXLOWTLAX, KXHIGHTBOS/KXLOWTBOS. Low-temp series are far thinner than highs (e.g. Boston low ~1.4M lifetime vs high ~16.7M) — liquidity gate matters.
- Bankrolls: real-scale $100 (replaces $27 assumption), plus $1,000 test bankroll. Both per watch.
- Governance (lighter): spec-first + TDD kept. Claude Code = primary builder. Adversarial review by a different-lineage model (Ollama Cloud) launched by user. User gives go on PR merges. Spec is built in hermes-kalshi-plugin/; new repo created after spec is done, then everything checked in.
- Profiles: `kalshi-bot` (normal operations; spec must create it), `kalshi-bot-a`, `kalshi-bot-b` (A/B models, own DBs). No-LLM control = baseline recorded inside each run (raw ensemble probability scored alongside), not a separate profile (pending user objection).
- Dashboard data path (user-verified): plugin ships `dashboard/plugin_api.py` (manifest `"api": "plugin_api.py"`), imported by the gateway process on the backend as user `hermes`; desktop pane calls `ctx.rest('/<route>')`, scoped to `/api/plugins/<id>`. plugin_api.py reads profile SQLite DBs directly, read-only, returns JSON. Gateway user owns all profile dirs, so cross-profile aggregation is fine. Spike #1 downgraded to a smoke test (WAL + read-only connection while a cron run writes).

## Recommended trading parameters (starting priors; learning loop proposes changes)
- Taker fee: ceil_to_cent(0.07 * C * P * (1-P)). ~1.5c/contract at mid prices; cent rounding hurts at 1–5 contracts.
- Net edge (buy YES at ask a): p - a - fee/contract. Buy NO at yes-bid b: b - p - fee/contract.
- Sizing: fractional Kelly f = 0.25 * (p - c)/(1 - c), c = all-in cost per contract.
- Shrink model probability toward market: p_used = w*p_model + (1-w)*p_market, w starts 0.5, learned.
- Gates: min net edge 4c; skip ask >0.95 or <0.05; depth must cover order at limit; per-trade cap 5% of bankroll; per-event cap 10%; per-day cross-city cap 20%.
- Score every evaluated bracket (traded or not) for calibration; trades alone give too little data.

# Addendum 2 (2026-10-15)
- LLM adjustment cap: 15 probability points from the ensemble value by default (user accepted recommendation).
- Graduation evidence: at least 21 days and 1,000 scored brackets; log loss beats market-implied baseline (bootstrap interval excludes zero); positive net P&L after fees on both bankrolls; realized vs claimed edge within tolerance. Informational; the user decides (user accepted recommendation).
- Spec drafted: `specs/001-paper-trading-mvp/spec.md`; constitution v1.0.0 at `.specify/memory/constitution.md`. Clarification markers resolved. Next: `speckit-plan` after the user hands over the repo.
