# Contract: Dashboard REST API (read-only)

Served by `dashboard/plugin_api.py` (module-level FastAPI `router`), mounted at `/api/plugins/hermes-kalshi/`. Called from `desktop/plugin.js` via `ctx.rest(path)`. Behind the dashboard auth gate. **No write routes in the MVP.** Each request opens the relevant profile database read-only (`file:<path>?mode=ro`, WAL, busy timeout 2 s) and closes it. Profiles are discovered from `<root>/profiles/*` (+ default) under the root Hermes home; only those with a `plugin-data/hermes-kalshi/data.db` are listed.

Common query params: `profile` (name; default first available), `since` (YYYY-MM-DD), `watch` (series ticker). Errors: `{ "error": "code", "detail": "..." }` with 404 (unknown profile), 503 (database locked/missing, includes `profile`), never a stack trace. Responses are JSON; money fields are decimal dollars (strings with 4 places) derived from micro-dollars.

| Route | Returns |
|---|---|
| `GET /profiles` | profiles with model id, last run status, DB size, schema version |
| `GET /overview` | bankroll equity per account, open exposure, today's recommendations count, last-slot health, scores headline |
| `GET /watches` | watches with status, strategy version, accounts (cash/equity), burn-in progress |
| `GET /events?date=` | events for a date with brackets: p_ensemble, p_final, p_market, p_used, decision, net edge, outcome when settled |
| `GET /recommendations?since=&decision=` | recommendations with rationale text, caps, reject codes |
| `GET /positions?status=open|settled` | positions with cost, fees, P&L |
| `GET /bankroll-curve?scale=real|test` | daily equity series per watch and total |
| `GET /scores/summary?groupby=predictor,city,kind,slot,model` | Brier, log loss, count by group |
| `GET /calibration?predictor=final` | 10-bin reliability data for each predictor |
| `GET /edge-realization` | claimed vs realized edge, hit rate and P&L by edge bucket, drawdown |
| `GET /proposals?status=` | proposals with evidence, plus the exact command to approve/reject (shown, not executed) |
| `GET /compare?profiles=kalshi-bot-a,kalshi-bot-b` | per-model metrics over common slots, plus the ensemble baseline; gaps listed |
| `GET /health` | per job/slot status, skips, errors, last snapshot age |

Pane sections (desktop/plugin.js): Overview, Today (brackets and decisions), Positions, Performance (calibration, edge realization, bankroll curves), A/B Compare, Proposals, Health. Offline state when any call fails: banner with the failing route and retry. Charts are inline SVG drawn with `react/jsx-runtime`.
