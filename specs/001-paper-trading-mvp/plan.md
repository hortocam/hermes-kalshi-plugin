# Implementation Plan: Kalshi Paper-Trading MVP (Climate: Daily High/Low Temperature)

**Branch**: `001-paper-trading-mvp` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-paper-trading-mvp/spec.md`

## Summary

Build a Hermes unified plugin (`hermes-kalshi`) that, three times a day, captures a frozen snapshot (Open-Meteo ensemble forecast, observed temperatures, Kalshi brackets and orderbooks) for 8 watches (NYC, Chicago, LA, Boston, each high and low), computes calibrated probabilities per bracket, lets an LLM adjust them within a bounded cap, then deterministic code computes edge, fees, sizing, and simulated orderbook fills for two paper bankrolls per watch. Settled markets settle positions and score every bracket (traded or not) for the final, raw-ensemble, and market-implied predictors. A read-only API plus a Desktop pane present results across the profiles `kalshi-bot`, `kalshi-bot-a`, and `kalshi-bot-b`. Threshold changes are proposed with evidence and applied only on user approval. Real-money trading is out of scope; the paper path uses an order-intent shape a real executor could later reuse.

Technical approach: a pure-Python stdlib core library (`kalshi_paper`) with SQLite per profile; deterministic work runs as Hermes script-only cron jobs, and only the LLM adjustment step is an agent job. See [research.md](research.md) for decisions and alternatives.

## Technical Context

**Language/Version**: Python 3.10+ compatible (backend version confirmed in spike S1); JavaScript ESM for the Desktop pane
**Primary Dependencies**: Python standard library only for core, CLI, tools; `fastapi` (provided by the Hermes dashboard environment) only in `dashboard/plugin_api.py`; `@hermes/plugin-sdk` and `react` only in `desktop/plugin.js`
**Storage**: SQLite (WAL) per profile at `$HERMES_HOME/plugin-data/hermes-kalshi/data.db`; shared immutable snapshot files under `<root>/plugin-data/hermes-kalshi/snapshots/`
**Testing**: `python3 -m unittest discover -s tests` (stdlib); hand-computed fixtures; recorded API fixtures; a no-auth contract test
**Target Platform**: Hermes Agent backend on the homelab (Linux, always-on); Hermes Desktop (Electron, macOS) as remote client
**Project Type**: Hermes plugin (agent plugin + bundled skills + dashboard API + desktop pane + profile distribution)
**Performance Goals**: a slot covering 8 watches finishes in under 10 minutes including the LLM step (SC-002); dashboard sections under 3 s for 30 days of data (SC-007)
**Constraints**: unattended cron runs; no secrets in repo/logs; no authenticated Kalshi calls; ~30 Kalshi calls per slot under a client-side token bucket; read-only dashboard API; runtime data never in git
**Scale/Scope**: 8 watches x 3 slots/day x 3 profiles; about 48 scored brackets per day per profile; ~2 MB of snapshots per day

## Constitution Check

*GATE: passes before Phase 0; re-checked after Phase 1 design (below).*

| Principle | Check | Status |
|---|---|---|
| I. Spec-First | spec.md accepted; plan and tasks derive from it; FR traceability table below | PASS |
| II. TDD | every module lists tests first in tasks; money math has hand-computed fixtures | PASS (enforced in tasks) |
| III. Paper Before Real Money | no auth code, no key handling, `KalshiClient` has no signing surface; contract test SC-009; trading only as `order_intent` seam | PASS |
| IV. Builder/Reviewer Differ | process rule; PRs wait for the user's go and a different-lineage review | PASS (process) |
| V. Evidence Over Assertion | quickstart.md gives runnable validation with expected output; tasks end with command + output evidence | PASS |
| VI. Reproducible Inputs/Provenance | content-hashed snapshots, per-profile compressed copies, `asof`/`fetched_at` on facts, recompute test (SC-003) | PASS |
| VII. Secrets/Data Out of Git | DB, snapshots, caches under Hermes homes; `.gitignore` covers `plugin-data/`; no secrets handled in MVP | PASS |
| VIII. Unattended and Simple | stdlib-first; script-only cron for deterministic steps; every upstream failure becomes a recorded skip | PASS |

**Post-design re-check**: no violations. The only dependency beyond stdlib is `fastapi`, supplied by Hermes for dashboard routes and not added by us. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-paper-trading-mvp/
├── plan.md                  # this file
├── research.md              # Phase 0 decisions and spikes
├── data-model.md            # Phase 1: SQLite schema, entities, state machines
├── quickstart.md            # Phase 1: runnable validation scenarios
├── contracts/
│   ├── cli.md               # `kalshi-paper` CLI commands and exit codes
│   ├── agent-tools.md       # LLM-facing tools, slash commands, packet/response shapes
│   ├── dashboard-api.md     # read-only REST routes for the Desktop pane
│   ├── snapshot-format.md   # frozen snapshot JSON and slot pointers
│   ├── strategy-config.md   # strategy version parameters and defaults
│   └── order-intent.md      # trading seam (paper executor; real executor deferred)
└── tasks.md                 # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
plugin.yaml                          # name hermes-kalshi, config_schema, capabilities
__init__.py                          # register(ctx): tools, commands, skills
lib/kalshi_paper/                    # pure-Python core (no Hermes imports)
├── config.py                        # paths from HERMES_HOME, watch/series config loading
├── kalshi_client.py                 # keyless public client, token bucket, backoff, quirks
├── weather.py                       # Open-Meteo ensemble + NWS observation clients
├── snapshot.py                      # build, hash, atomic slot pointer, load
├── model.py                         # LST-day extremes, nowcast clamp, bracket probabilities
├── fees.py, orderbook.py            # fee formula, ask/bid derivation, level walking
├── sizing.py                        # net edge, fractional Kelly, caps, gates
├── executor.py                      # order intent + paper fill (seam for a future real executor)
├── store.py                         # SQLite schema/migrations, idempotent writers
├── settle.py, scoring.py            # settlement, P&L, Brier/log loss, calibration bins
├── learn.py                         # bucket analysis, proposals, versioned approval
├── adjust.py                        # packet build, bounded LLM adjustment, normalization
├── compare.py                       # A/B comparison over common slots
└── cli.py                           # `python -m kalshi_paper ...` entrypoint
skills/
├── kalshi-market-data/SKILL.md      # keyless data skill (+ scripts/ thin wrappers)
├── kalshi-evaluator/SKILL.md        # evaluation workflow for the agent step
└── kalshi-ops/SKILL.md              # watch management, approvals, health, A/B setup
scripts/                             # shims installed into $HERMES_HOME/scripts/ for script-only cron
dashboard/
├── manifest.json                    # {"name": "hermes-kalshi", "api": "plugin_api.py", ...}
└── plugin_api.py                    # read-only FastAPI router
desktop/plugin.js                    # Desktop pane (ESM, jsx via react/jsx-runtime)
profiles/kalshi-bot/                 # profile distribution: distribution.yaml, SOUL.md, config.yaml, cron/jobs.json
config/watches.default.json          # 8 watches: series, kind, CLI code, station, lat/lon, tz
tests/                               # unit, contract, integration (fixtures in tests/fixtures/)
docs/                                # requirements briefs (already present)
```

**Structure Decision**: single plugin tree; logic lives in `lib/kalshi_paper` so CLI, tools, cron scripts, tests, and the dashboard API share one tested implementation. Skills and scripts are thin wrappers. No `src/` split because Hermes loads the plugin directory directly.

## Runtime Design

### Slot pipeline (per profile; times are defaults, configurable)

| Step | Job type | Slots (ET) | What it does |
|---|---|---|---|
| 1 snapshot | script-only | 07:00, 12:30, 16:30 | create-or-reuse the shared slot snapshot (idempotent) |
| 2 evaluate | agent (per profile model) | +2 min | `get_packet` -> LLM adjustments -> `submit_adjustments`; code finalizes, sizes, paper-trades |
| 3 finalize | script-only | +12 min | completes any unfinished slot ensemble-only, flagged `llm_failed` |
| 4 settle+score | script-only | 09:30 daily, plus after each slot | settle markets, positions, scores |
| 5 learn | script-only | daily 10:00 | bucket analysis; create proposals only above sample minimums |
| 6 health | script-only | with each step | record run status; dashboard reads it |

Events considered per slot: each city's local-date today and tomorrow events (markets open the prior day). Overlap protection: slot key `(date, slot, profile)` unique in `runs`; re-runs are idempotent.

### Calculations (details in research.md R8, data-model.md, contracts/strategy-config.md)
- Daily extreme per member over the local standard-time day, nowcast clamp with observed extremes, rounding-aware bracket probabilities, calibrated by `(bias, sigma)` per station/slot.
- `p_final` = LLM-adjusted within the cap, renormalized per event; `p_used = w*p_final + (1-w)*p_market` (w default 0.5).
- Net edge per contract: BUY YES `p_used - ask - fee`, BUY NO `bid_yes - p_used - fee`; levels included only while marginal net edge >= min edge (default 4 cents).
- Size: contracts = min(Kelly contracts at fraction 0.25, per-trade 5%, per-event 10%, per-day 20% of bankroll equity, book depth); binding constraint recorded.
- Gates: price in [0.05, 0.95], depth, snapshot age <= 20 min, `burn_in_days` (default 3 settled days per watch), liquidity.

## FR Traceability

| Spec FRs | Delivered by |
|---|---|
| FR-001..003 | `kalshi_client.py`, `kalshi-market-data` skill, `config/watches.default.json` |
| FR-004..006 | `store.py` (watches/accounts), `kalshi-ops` skill, CLI `watch *`, discovery in snapshot step |
| FR-007..010 | `snapshot.py`, `weather.py`, `model.py`, `adjust.py`, provenance columns |
| FR-011..016 | `sizing.py`, `orderbook.py`, `fees.py`, `executor.py`, idempotent writers |
| FR-017..019 | `settle.py`, `scoring.py`, `compare.py` |
| FR-020..021 | `learn.py`, `strategy_versions`, approval command |
| FR-022..024 | profile distribution `profiles/kalshi-bot/`, `ops setup-ab`, cron jobs |
| FR-025..027 | `dashboard/plugin_api.py`, `desktop/plugin.js` |
| FR-028..029 | architecture (no signing), contract test, `.gitignore` |

## Phase 0 Spikes (first tasks; each has a pass criterion)

| ID | Question | Pass criterion |
|---|---|---|
| S1 | Does a unified package install and load (skills, tool, dashboard manifest, desktop half)? Backend Python version? | `hermes plugins validate` passes; `skill_view("hermes-kalshi:...")` works; pane appears; Python version recorded |
| S2 | Does the profile distribution create `kalshi-bot` with paused cron jobs and the plugin enabled? | `hermes profile install` result inspected; jobs paused; plugin listed as enabled for that profile |
| S3 | Cron timezone, `-p <profile>` job creation, script shims in `$HERMES_HOME/scripts/` | a script-only job fires at a local ET time across a DST-aware expression; job belongs to the right profile |
| S4 | Shared snapshot directory across profiles | two profiles race to create one slot; exactly one snapshot, both read the same hash |
| S5 | Open-Meteo real call weight, headers, throttling | one slot's request recorded; no throttling over 3 days |
| S6 | Read-only SQLite from the dashboard during a write | 100 reads during a continuous write loop with zero errors |
| S7 | Observation (METAR) vs Kalshi settlement discrepancy | table of 10+ settled days per station with differences |
| S8 | Kalshi fee schedule vs formula and multi-level fee rounding | formula matches published schedule on 5 hand cases |

## Risks and Open Items
- Settlement source differs from the NWS METAR feed we nowcast with (S7); early nowcast edge may be overstated.
- Open-Meteo free-tier terms are non-commercial; fine for paper trading, revisit before any real-money phase.
- Model quality is unknown until about 3 weeks of scored data; the plan deliberately builds measurement first.
- The unified package changes the interview's "separate desktop plugin" delivery shape (R1); needs user confirmation.
- Dashboard cannot approve proposals (read-only decision, R3, confirmed by the user for the MVP); approvals via slash command/tool. The user wants dashboard actions later (approve/reject proposals, pause watches, run a slot). Design implication: keep all mutations in `lib/kalshi_paper` command functions so future write routes in `plugin_api.py` call the same code with the same idempotency, add an auth/CSRF review, and record the acting user; deferred to a later spec.

## Complexity Tracking

No constitution violations to justify.
