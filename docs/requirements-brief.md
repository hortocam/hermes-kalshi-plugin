# Hermes Kalshi Plugin — Requirements Brief (pre-SDD)

Status: interview rounds 1–3 complete (2026-10-15). Input to `speckit-specify`. Open items at bottom.

## Goal
Hermes plugin that reviews Kalshi markets in a category, produces probability predictions, and paper-trades them against a fake bankroll, so we can prove the system finds real opportunities and takes smart risks *before* any real-money trading.

## Decisions made
| Area | Decision |
|---|---|
| Packaging | Skills bundle (Python scripts, installable via skills hub) **+ separate Desktop plugin** (`desktop/plugin.js`). Agent-side plugin exposes read-only tools/API over the store; pane calls them. |
| Runtime | Jarvis = always-on Hermes backend in the homelab; Desktop app is a remote client. Cron/routines run on the homelab. Models: Ollama cloud. |
| MVP category | Climate & Weather: Daily High and Daily Low temperature markets (series like KXHIGHNY, KXHIGHCHI, KXHIGHLAX, KXHIGHMIA; variants such as KXHIGHTSFO exist). |
| MVP scope | ~4 cities, high + low, 3 runs/day (morning forecast, midday with observed temps, late-afternoon). |
| Forecast data | Open-Meteo ensembles as the quantitative base (probability per bracket from ensemble members). LLM = adjustment/reasoning layer, never the base. |
| Prediction method | Hybrid: LLM proposes probability + rationale; deterministic code computes edge, fees, sizing, and records everything. |
| Test mode unit | Per series/city **watch**. All daily markets in a watched series are auto-evaluated and paper-traded. Per-watch thresholds. |
| Bankrolls | Two per watch: larger demo (e.g. $1,000, fractional Kelly) + real-scale (mirrors actual small account and per-trade cap). |
| Fill model | Walk the real orderbook at decision time + Kalshi taker fee formula (round up to cent); reject when depth is insufficient. |
| Positions | Hold to settlement; additional entries allowed on later runs within caps; no early exits in MVP. |
| Learning loop | System computes calibration/P&L by threshold bucket and **proposes** threshold changes with evidence + min sample size; human approves; versioned/auditable. |
| Model evaluation | Separate agent profiles (A, B, optional no-LLM control), each with its own model and its own SQLite DB. Every run must use a **frozen shared input snapshot** (ensemble output + orderbook) so models are compared on identical data. |
| Dashboard data | Agent plugin exposes read-only tools/API; Desktop pane calls via gateway. Must aggregate across profiles/DBs. Needs early spike to confirm SDK capability. |
| Authenticated trading | Out of MVP. Spec defines seams only (order intent, risk limits, approval gate, key storage). |
| Reuse | Fresh data model. Port proven pieces from kalshi-plugin-x: API gotchas (kalshi.py), fee formula, idempotent ingest + asof/fetched_at provenance patterns. Stdlib-first; optional deps via pyproject only if a step truly needs them. |
| Success framing | Calibration + net P&L after fees, plus evidence the system identifies real opportunities and smart risks (realized vs claimed edge, hit-rate by edge bucket, risk-adjusted return, drawdown). N and thresholds to be set in the spec. |

## Reference-repo findings (kalshi-plugin-x)
- Reusable: `kalshi.py` (11-command stdlib public CLI + encoded API gotchas: /series 18MB dump, repeated `tickers` for orderbooks vs comma `market_tickers` for candlesticks, `liquidity_dollars` always 0, derived YES ask = 1 − best NO bid, MVE combo noise, 429s).
- Reusable patterns: `research_store.py` SQLite store (idempotency keys, provenance, staleness contract, digest, positions table + P&L, fee calc).
- Not fit for purpose as-is: schema built around gas/diesel ladders + Yahoo closes; predictions are single rows, no recommendation lifecycle, no test mode/bankroll/threshold calibration, no dashboard, no agent profile. Constitution (read-only, keyless, Jarvis-merge flow) needs amendment.

## Hermes facts (from docs; verify in spikes)
- Plugin tree: `plugin.yaml` + entrypoints (`__init__.py` agent plugin, `desktop/plugin.js`, `plugin.json`, `dashboard/manifest.json`). Desktop plugins import only `@hermes/plugin-sdk` and `react`; full app authority, hot-reload.
- Profiles in `~/.hermes/profiles/<name>/` (config.yaml, SOUL.md, skills, creds); Routines = Hermes cron jobs; cron runs use a fresh agent with attached skills.
- Docs gaps: how a plugin ships skills/profiles, plugin data dir, `ctx.register_*` signatures, SDK backend-call API.

## Open items for the spec phase
1. Final city list and station → series mapping; which low-temp series exist for each.
2. Nowcast method for midday/afternoon runs (observed hourly temps vs. running max).
3. Numeric values: demo bankroll, real-scale bankroll and per-trade cap, Kelly fraction, min edge, N for go/no-go.
4. Profile names (e.g. kalshi-bot-a / -b / -control) and how one skill package is installed into several profiles.
5. Governance: carry over or amend the reference constitution (Jarvis kanban, independent-review, merge authority, stdlib-only).
6. Spikes: agent-plugin → desktop-pane data path; plugin skill/profile shipping; cron + rate limits (429) across ~4 cities × 3 runs × N profiles.
