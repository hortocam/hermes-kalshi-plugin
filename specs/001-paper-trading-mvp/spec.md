# Feature Specification: Kalshi Paper-Trading MVP (Climate: Daily High/Low Temperature)

**Feature Branch**: `001-paper-trading-mvp`
**Created**: 2026-10-15
**Status**: Draft (clarifications resolved 2026-10-15; ready for planning)
**Input**: Requirements interview (2026-10-15). Source docs: Project "Hermes Kalshi Plugin" → `requirements-brief.md`, `requirements-brief-addendum-1.md`.

## Summary

A Hermes plugin that reviews Kalshi daily high/low temperature markets for four cities, produces a
probability for every bracket, and places **paper trades** against fake bankrolls, then scores every
prediction once markets settle. Its purpose is to prove, with evidence, that the system identifies
real opportunities and takes smart risks before any real money is used. The plugin also provides a
Desktop dashboard, A/B comparison of different models, and a human-approved threshold-learning loop.
Real-money trading is **out of scope**; only its interfaces are defined.

## Scope

**In scope (MVP)**
- Public Kalshi market-data skill (keyless) with reusable scripts.
- Evaluation skill: snapshot → probabilities → recommendations → paper trades → settlement → scoring.
- Per-series "watch" in test mode, each with two paper bankrolls.
- Series: NYC, Chicago, LA, Boston; high and low temperature (8 watches).
- Hermes profiles `kalshi-bot` (normal operations), `kalshi-bot-a`, `kalshi-bot-b` (A/B models), each with its own database.
- Scheduled routines, 3 runs per day.
- Desktop plugin dashboard reading data via the plugin's backend API.
- Threshold-learning proposals with human approval.
- Authenticated-trading *seams* (order intent, risk limits, approval gate), no real orders.

**Out of scope (MVP)**
- Any authenticated Kalshi call, real orders, or real balances.
- Early exits / selling paper positions before settlement.
- Categories other than daily temperature; other cities.
- Auto-applied threshold changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Public Market Data Skill (Priority: P1)
An agent or user can discover and read Kalshi temperature markets (series → events → markets, quotes,
orderbooks, settled results) through scripts that need no API key and handle Kalshi's known quirks.

**Why this priority**: every other story consumes this data.

**Independent Test**: run the discovery and orderbook commands for one series and confirm brackets,
derived YES asks, and a settled result are returned and parse cleanly.

**Acceptance Scenarios**:
1. **Given** a watched series, **When** discovery runs, **Then** it returns today's and tomorrow's events with every bracket (two tails, bands) and its quote.
2. **Given** a market's orderbook, **When** read, **Then** YES ask is derived as 1 − best NO bid and depth per price level is returned.
3. **Given** Kalshi returns a rate-limit error, **When** a call is made, **Then** it backs off and retries within a budget, and reports a recorded failure if the budget is exhausted.

---

### User Story 2 - Watch a Series in Test Mode (Priority: P1)
The user (or the agent on request) puts a series (e.g. NYC high) in test mode. From then on every new
daily market in it is evaluated and paper-traded automatically, using that watch's thresholds and its
own two bankrolls.

**Why this priority**: this is the core "test mode" requirement.

**Independent Test**: create a watch, run one evaluation cycle, confirm bankrolls exist and new markets were picked up without further input.

**Acceptance Scenarios**:
1. **Given** no watch for a series, **When** the user enables test mode, **Then** a watch exists with a $100 real-scale bankroll, a $1,000 test-scale bankroll, and default strategy settings.
2. **Given** a watch, **When** a new daily event is listed, **Then** it is evaluated in the next run without manual enrollment.
3. **Given** a paused watch, **When** a run happens, **Then** it evaluates nothing for that series and open positions still settle.

---

### User Story 3 - Probabilities from a Frozen Snapshot (Priority: P1)
For each run, the system captures a frozen input snapshot (ensemble forecast for the settlement station,
observed temperatures so far, every bracket's quote and orderbook, timestamps). From it, it produces
for every bracket: the raw ensemble probability, the final probability (after any LLM adjustment, with
rationale), and the market-implied probability. All three are stored.

**Why this priority**: honest prediction records are the foundation for judging quality.

**Independent Test**: for a stored snapshot, recompute probabilities and edge; results match the stored values.

**Acceptance Scenarios**:
1. **Given** an ensemble forecast, **When** probabilities are computed, **Then** bracket probabilities for a city-day sum to 1 (±0.001) and each is stored with the snapshot id.
2. **Given** the LLM adjustment layer, **When** it proposes changes, **Then** the proposal and rationale are stored separately from the raw ensemble value, and deviations beyond the configured cap are clipped and flagged.
3. **Given** the forecast source is unavailable, **When** a run happens, **Then** the run records a skip for the affected watches and fabricates nothing.
4. **Given** the midday run, **When** observed temperatures exist, **Then** the snapshot includes them and the probabilities reflect the running observed max/min.

---

### User Story 4 - Recommendations and Paper Trades (Priority: P1)
For each bracket, the system computes net edge after fees, decides whether to recommend a trade
(YES or NO), sizes it per bankroll, and executes a simulated fill against the recorded orderbook.

**Why this priority**: this is the experiment itself.

**Independent Test**: given a fixed snapshot and settings, the recommendations, fills, fees and sizes equal hand-computed expected values.

**Acceptance Scenarios**:
1. **Given** model probability p and YES ask a, **When** net edge (p − a − fee per contract) ≥ the watch's minimum, **Then** a BUY YES recommendation is created.
2. **Given** a recommendation, **When** filled, **Then** the fill walks the orderbook levels, charges the Kalshi taker fee (rounded up to the cent), and rejects the trade (recorded with reason) if depth is insufficient at the limit price.
3. **Given** per-trade (5%), per-event (10%) and per-day (20%) exposure caps, **When** sizing, **Then** no bankroll exceeds any cap and the binding cap is recorded.
4. **Given** a later run on the same event, **When** edge reappears, **Then** an additional entry may be made within caps; no position is ever sold early.
5. **Given** a slot already processed, **When** it is re-run, **Then** no duplicate trades or predictions are created.

---

### User Story 5 - Settlement and Scoring (Priority: P1)
After Kalshi settles a market, the system settles paper positions, computes realized P&L per bankroll,
and scores **every evaluated bracket** (traded or not) against the outcome.

**Why this priority**: scoring all brackets gives enough data to judge calibration in weeks, not months.

**Independent Test**: settle a day with known outcomes and verify P&L, Brier score, and log loss against hand calculations.

**Acceptance Scenarios**:
1. **Given** a settled market and open positions, **When** settlement runs, **Then** P&L = contracts × (1 − fill price) − fees on a win, −(contracts × fill price) − fees on a loss, idempotently.
2. **Given** scored brackets, **When** metrics are computed, **Then** they are reported for three predictors side by side: final probability, raw ensemble, and market-implied baseline.
3. **Given** a voided or undetermined market, **When** settlement runs, **Then** positions are refunded or left pending per recorded Kalshi status and excluded from scoring, with the reason stored.

---

### User Story 6 - Desktop Dashboard (Priority: P2)
In the Hermes Desktop app, the user opens a dashboard pane showing watches, today's recommendations,
open and settled paper positions, bankroll curves, calibration, edge-realization stats, and A/B model
comparison, across `kalshi-bot`, `kalshi-bot-a`, and `kalshi-bot-b`.

**Why this priority**: it is how the user judges the experiment, but data capture works without it.

**Independent Test**: with a populated database, the pane renders every section from the backend API, read-only.

**Acceptance Scenarios**:
1. **Given** data in several profile databases, **When** the pane loads, **Then** the user can view one profile or compare them.
2. **Given** a run is writing, **When** the pane refreshes, **Then** it still renders (no lock errors) and never modifies data.
3. **Given** the backend is unreachable, **When** the pane loads, **Then** it shows a clear offline state.

---

### User Story 7 - Threshold Learning with Approval (Priority: P2)
The system analyzes settled results by threshold bucket (edge size, price range, city, high/low, run slot)
and proposes new settings (minimum edge, probability shrinkage toward market, caps) with supporting
evidence and a minimum sample size. The user approves or rejects. Approved changes create a new,
versioned strategy configuration; history is preserved.

**Why this priority**: refining thresholds is a stated project goal, but needs settled data first.

**Independent Test**: from a fixture dataset, a proposal is generated with evidence; approving it creates a new version that later runs use; rejecting changes nothing.

**Acceptance Scenarios**:
1. **Given** fewer settled samples than the minimum, **When** analysis runs, **Then** no proposal is made and the reason is shown.
2. **Given** an approved proposal, **When** the next run happens, **Then** it uses the new version and every trade records which version it used.
3. **Given** a proposal, **When** it is rejected, **Then** it is archived with the decision and settings are unchanged.

---

### User Story 8 - A/B Model Comparison (Priority: P2)
Two profiles, `kalshi-bot-a` and `kalshi-bot-b`, are each configured with a different model and keep their own
databases. For a given run slot, both evaluate the **same frozen snapshot**, so differences come from the model,
not from timing.

**Why this priority**: the user wants to test which models are suited to the task.

**Independent Test**: run one slot for both profiles; confirm they reference the same snapshot id and that a comparison report lists each model's scores.

**Acceptance Scenarios**:
1. **Given** a slot, **When** both profiles run, **Then** both predictions reference the identical snapshot id.
2. **Given** both profiles' results, **When** compared, **Then** the report shows log loss, Brier, calibration, and P&L per model over the same set of brackets, plus the no-LLM ensemble baseline.
3. **Given** one profile fails to run, **When** compared, **Then** only slots both completed are compared and the gap is reported.

---

### User Story 9 - Operations Profile and Scheduling (Priority: P2)
Installing/setting up the plugin creates (or guides creating) the `kalshi-bot` profile (persona, skills, toolsets),
and schedules three runs per day per profile as Hermes routines. A health view shows last-run status.

**Why this priority**: unattended operation is how data accumulates.

**Independent Test**: after setup, the profile exists with the skills enabled and routines appear in the cron list; one manual run completes.

**Acceptance Scenarios**:
1. **Given** a fresh install, **When** setup completes, **Then** `kalshi-bot` exists with the plugin skills enabled and 3 routines scheduled.
2. **Given** overlapping runs, **When** a second starts while one is active, **Then** it exits without duplicating work and records why.
3. **Given** a failed run, **When** the next starts, **Then** it processes any missed settlements and records the failure.

---

### User Story 10 - Trading Seams for Later (Priority: P3)
The design defines, but does not implement, interfaces for an authenticated skill: an order-intent record,
risk limits, an approval gate, and a place for key material. Paper trading uses the same order-intent shape
so a real executor could later replace the simulated one.

**Why this priority**: avoids rework when real trading is specced later.

**Independent Test**: a paper trade is expressed as an order intent that passes through the same risk-limit check a real order would.

**Acceptance Scenarios**:
1. **Given** a recommendation, **When** executed in paper mode, **Then** it passes through an order-intent record and risk checks before the simulated fill.
2. **Given** any code path, **When** reviewed, **Then** none performs an authenticated Kalshi request.

### Edge Cases
- Forecast provider outage or rate limit: record skip per watch; never reuse a stale snapshot older than the configured age.
- Kalshi 429 or errors: bounded retry, then recorded skip.
- Empty or one-sided orderbook; zero-quote brackets: no trade; recorded reason.
- Market closes or settles before the run's decision time: skip.
- Bracket structure differs by series (tails `T` and bands `B`, series naming variants like `KXHIGHNY` vs `KXHIGHTBOS`): handled via discovery, not hardcoded.
- Settlement day boundaries and daylight-saving transitions in each station's local time.
- Settlement source corrections or delays (rules-named source revised after first print): Kalshi's final result is authoritative; discrepancies are logged.
- LLM output malformed, timed out, or out of bounds: fall back to ensemble-only and flag.
- Probabilities do not sum to 1 after adjustment: renormalize or reject, recorded.
- Fee rounding at very small contract counts (1–5): fee modeled exactly; trades whose net edge is negative after rounding are rejected.
- Database locked or missing for a profile: dashboard reports it per profile.
- Same slot executed twice or concurrently: idempotent, no duplicates.
- Low-temperature series are far less liquid than highs: liquidity gate rejects thin books.

## Requirements *(mandatory)*

### Functional Requirements

**Public data skill**
- **FR-001**: The plugin MUST provide a keyless skill with scripts to discover series/events/markets, read quotes, orderbooks, candlesticks, and settled results from Kalshi's public API.
- **FR-002**: The skill MUST encode Kalshi's known quirks (derived YES ask from NO bids, repeated vs comma-separated batch parameters, deprecated liquidity field, lowercase status vs filter status, rate-limit handling).
- **FR-003**: Series codes and station mappings MUST be configuration, not hardcoded in logic.

**Watches and test mode**
- **FR-004**: The system MUST let a series be enabled/paused/disabled as a watch in test mode, with per-watch strategy settings.
- **FR-005**: Each watch MUST have two independent paper bankrolls (real-scale default $100; test-scale default $1,000), sized and tracked separately.
- **FR-006**: New markets in a watched series MUST be discovered and evaluated without manual enrollment.

**Snapshots and predictions**
- **FR-007**: Each run MUST capture a frozen, content-identified input snapshot (ensemble forecast, observations so far, bracket quotes/orderbooks, timestamps) before any prediction.
- **FR-008**: The system MUST compute, for every bracket, raw ensemble probability, final probability, and market-implied probability, and store all three with the snapshot id, model identity, and rationale.
- **FR-009**: The LLM adjustment layer MUST be bounded: its change from the ensemble probability is capped at 15 probability points by default (configurable per strategy version) and every clip is recorded.
- **FR-010**: Every ingested fact MUST carry `asof` and `fetched_at`; missing data MUST be recorded as missing.

**Recommendations and paper trading**
- **FR-011**: The system MUST compute net edge for BUY YES (p − ask − fee/contract) and BUY NO (yes bid − p − fee/contract) and recommend only when it meets the watch minimum (default 4¢) and gates pass (price between 5¢ and 95¢, depth, snapshot age).
- **FR-012**: Sizing MUST use fractional Kelly (default 0.25) with probability shrunk toward the market (default weight 0.5), subject to per-trade (5%), per-event (10%), and per-day cross-city (20%) caps; the binding constraint MUST be recorded.
- **FR-013**: Paper fills MUST walk the recorded orderbook, apply Kalshi's taker fee (0.07 × contracts × P × (1−P), rounded up to the cent), and reject when depth is insufficient.
- **FR-014**: Positions MUST be held to settlement; additional entries are allowed within caps; early exits are not supported.
- **FR-015**: Re-running a slot MUST NOT create duplicate predictions, recommendations, or trades.
- **FR-016**: Paper trades MUST flow through an order-intent record and risk-limit check shaped for a future real executor.

**Settlement and scoring**
- **FR-017**: The system MUST settle positions from Kalshi's settled result, idempotently, computing realized P&L net of fees per bankroll.
- **FR-018**: The system MUST score every evaluated bracket (traded or not) with Brier score and log loss for final, raw-ensemble, and market-implied predictors.
- **FR-019**: The system MUST report calibration by probability bin, realized vs claimed edge, hit rate and P&L by edge bucket, drawdown, and breakdowns by city, high/low, run slot, and model.

**Learning loop**
- **FR-020**: The system MUST propose threshold changes with evidence and a minimum sample size, and MUST NOT apply any change without user approval.
- **FR-021**: Strategy settings MUST be versioned; each prediction and trade MUST record the version in force; history MUST be retained.

**A/B and profiles**
- **FR-022**: Each profile (`kalshi-bot`, `kalshi-bot-a`, `kalshi-bot-b`) MUST own its database and model configuration.
- **FR-023**: For a run slot, profiles under comparison MUST evaluate the same snapshot id.
- **FR-024**: The plugin MUST create or guide creation of the `kalshi-bot` profile with its persona and skills, and schedule 3 runs/day per profile as Hermes routines.

**Dashboard**
- **FR-025**: The plugin MUST ship a Desktop pane and a backend read-only API that reads profile databases and returns JSON; the pane MUST NOT access databases directly.
- **FR-026**: The API MUST be read-only and tolerate concurrent writes.
- **FR-027**: The dashboard MUST show watches, recommendations, positions, bankroll curves, scoring and calibration, proposals awaiting approval, A/B comparison, and run health.

**Safety**
- **FR-028**: No code path MAY perform an authenticated Kalshi request or place a real order.
- **FR-029**: Secrets MUST NOT be written to logs, databases, or the repository; runtime data MUST live under the owning profile.

### Key Entities
- **Watch**: a series in test mode: series, side (high/low), city/station, status, strategy version, bankrolls.
- **Bankroll account**: paper cash and equity for one watch and scale (real-scale or test-scale).
- **Snapshot**: frozen inputs for a run slot, content-identified, with timestamps.
- **Run**: one scheduled execution slot per profile, with status, skips, and failures.
- **Prediction**: per bracket per snapshot per model: raw ensemble, final, market-implied probability; rationale.
- **Recommendation**: a decision for a bracket: side, edge, size, binding cap, reason if none.
- **Order intent / Paper fill**: the intent and the simulated execution with levels walked and fees.
- **Position**: contracts held for a bracket, side, cost, fees, settlement result.
- **Settlement / Score**: the outcome and per-prediction scores.
- **Strategy version**: thresholds, shrinkage, Kelly fraction, caps, gates.
- **Proposal**: suggested strategy change with evidence and decision.
- **Model profile**: profile name, model identity, and its database.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: Enabling test mode for a series takes one command or one chat request and under 2 minutes.
- **SC-002**: A scheduled run covers all 8 watches and completes in under 10 minutes, with no unhandled errors across 7 consecutive days.
- **SC-003**: 100% of recorded recommendations and paper trades are reproducible from their stored snapshot (recomputation matches stored edge, size, fill, fee).
- **SC-004**: Re-running any completed slot creates zero duplicate rows.
- **SC-005**: Within 14 days of continuous running, at least 600 brackets are scored.
- **SC-006**: Settled paper P&L matches hand-calculated P&L on a fixture day to the cent, for both bankrolls.
- **SC-007**: The dashboard loads all sections in under 3 seconds for 30 days of data and stays usable while a run is writing.
- **SC-008 (graduation evidence, informational for MVP)**: after at least 21 days and 1,000 scored brackets, the final predictor's log loss beats the market-implied baseline with a bootstrap interval excluding zero; net P&L after fees is positive on both bankrolls; and realized edge by bucket tracks claimed edge within a stated tolerance. The user decides whether this evidence justifies a real-money spec.
- **SC-009**: No authenticated request is ever made (verified by code review and an automated check).

## Assumptions
- Settlement ground truth is Kalshi's settled result. Each market's rules text names the source and location (observed 2026-10-16: "maximum temperature recorded at Boston (CLIBOS) ... according to The Weather Company"); the rules text is captured per market and treated as authoritative. Kalshi's help article describes the NWS Daily Climate Report; the two may differ, so any observation feed used for nowcasting is an approximation whose discrepancy from settlement is measured.
- Forecast base is Open-Meteo ensemble data (free, keyless); the LLM only adjusts it.
- Jarvis (the Hermes backend) runs always-on in the homelab; the Desktop app is a remote client; routines run on the backend. Models are served via Ollama Cloud.
- Desktop pane reads data through `ctx.rest` to a plugin-shipped `dashboard/plugin_api.py` running in the gateway as the same user that owns the profile directories (verified by the user).
- Run times are configurable; default slots are morning, midday (with observed temperatures), and late afternoon, Eastern time. Cities in other time zones use their station's local day for settlement.
- Single writer per database; the API opens it read-only.
- Fee schedule and bracket structure are discovered from Kalshi data at runtime, not assumed.

## Dependencies
- Kalshi public API (`https://api.elections.kalshi.com/trade-api/v2`), subject to rate limits (429s observed).
- Open-Meteo ensemble API; NWS/Kalshi settlement.
- Hermes: skills, profiles, cron/routines, desktop plugin SDK (`@hermes/plugin-sdk`, `react`), plugin backend API.
- Ollama Cloud models for the adjustment layer.

## Risks to resolve in planning
- How a plugin ships skills and creates profiles (docs unclear).
- How profiles A and B share one frozen snapshot while owning separate databases.
- Request budget across 4 cities × high/low × 3 runs × 3 profiles against Kalshi and Open-Meteo limits.
- Concurrent read-only access to SQLite during writes.
- Quality of Open-Meteo ensemble data per station and its lead-time behavior.
