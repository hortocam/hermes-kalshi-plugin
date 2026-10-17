---

description: "Task list for the Kalshi Paper-Trading MVP"
---

# Tasks: Kalshi Paper-Trading MVP (Climate: Daily High/Low Temperature)

**Input**: Design documents from `specs/001-paper-trading-mvp/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED. Constitution II (TDD) applies: within every story, tests are written first, must fail for the right reason, then the implementation makes them pass. Money math tests use hand-computed expected values (see quickstart.md section A).

**Organization**: grouped by user story; each story is independently testable. Paths are relative to the repository root (the plugin root), per plan.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1..US10 (maps to spec.md); none in Setup, Foundational, Polish
- **[NEEDS BACKEND]**: requires the user's Hermes backend or Desktop app; I cannot complete it alone
- Test command: `python3 -m unittest discover -s tests`

## Review and merge gates (Constitution IV)

Each phase ends with a checkpoint: tests green with command output captured, a PR from a short-lived branch, a different-lineage review by the user, and the user's go before merge. The builder never approves its own work.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: repository skeleton and the Phase 0 spikes that de-risk the Hermes assumptions.

- [ ] T001 Create the directory layout from plan.md with empty package files: `lib/kalshi_paper/__init__.py`, `tests/__init__.py`, `tests/fixtures/`, `skills/kalshi-market-data/`, `skills/kalshi-evaluator/`, `skills/kalshi-ops/`, `scripts/`, `dashboard/`, `desktop/`, `profiles/kalshi-bot/cron/`, `config/`, `spikes/`
- [ ] T002 [P] Create `plugin.yaml` (name `hermes-kalshi`, version `0.1.0`, description, `config_schema` for `slot_times` and `kalshi_rps`, `capabilities: []`) and an `__init__.py` whose `register(ctx)` registers nothing yet
- [ ] T003 [P] Update `.gitignore`: `plugin-data/`, `*.db`, `*.db-wal`, `*.db-shm`, `snapshots/`, `.venv/`, `.worktrees/`, `__pycache__/` (Constitution VII)
- [ ] T004 [P] Write `README.md`: purpose, status, layout, how to regenerate the Spec Kit scaffold (`specify init --here --integration claude --script sh --force`), test command, link to spec
- [ ] T005 [P] Create `tests/helpers.py`: temp `HERMES_HOME` factory (with `profiles/<name>` homes under a temp root), fixture loader, frozen-clock helper; confirm `python3 -m unittest discover -s tests` runs with zero tests and exits 0
- [ ] T006 [P] [NEEDS BACKEND] Spike S1 in `specs/001-paper-trading-mvp/spikes/S1-unified-package.md`: install a stub of the plugin on the backend; verify `hermes plugins validate`, `register_skill`/`skill_view("hermes-kalshi:<skill>")`, a stub tool, dashboard manifest + `plugin_api.py` route via `ctx.rest`, desktop half at `desktop/plugin.js`, slash-command handler signature, and record the backend Python version. Pass criterion: all listed items work and results are written to the note
- [ ] T007 [P] [NEEDS BACKEND] Spike S2 in `specs/001-paper-trading-mvp/spikes/S2-profile-distribution.md`: install a stub `profiles/kalshi-bot` distribution; verify the profile is created, cron jobs arrive paused, the plugin shows as enabled for that profile, and `--clone` for `kalshi-bot-a`/`-b` works
- [ ] T008 [P] [NEEDS BACKEND] Spike S3 in `specs/001-paper-trading-mvp/spikes/S3-cron.md`: verify a script-only job from `$HERMES_HOME/scripts/`, `hermes -p <profile> cron create`, and timezone behavior of schedule expressions across a DST boundary (or document the UTC-regeneration fallback)
- [ ] T009 [P] [NEEDS BACKEND] Spike S4 in `specs/001-paper-trading-mvp/spikes/S4-shared-snapshot-dir.md`: two profiles race to create one slot pointer in `<root>/plugin-data/hermes-kalshi/snapshots/slots/`; exactly one snapshot results and both read the same hash
- [ ] T010 [P] Spike S5 in `specs/001-paper-trading-mvp/spikes/S5-open-meteo.md` with throwaway script `spikes/s5_open_meteo.py`: one request for the four station coordinates with `models=gfs025,ecmwf_ifs025`; record response size, headers, latency, member counts, and behavior on 3 repeated calls
- [ ] T011 [P] [NEEDS BACKEND] Spike S6 in `specs/001-paper-trading-mvp/spikes/S6-readonly-sqlite.md` with `spikes/s6_readonly.py`: a writer loop plus 100 read-only reads (`file:...?mode=ro`, WAL, busy timeout 2 s) from the gateway process context; zero errors
- [ ] T012 Spike S7 in `specs/001-paper-trading-mvp/spikes/S7-obs-vs-settlement.md`: start-of-collection note only; the discrepancy table is filled by settlement data once US5 runs (observation extreme stored beside Kalshi settled value); closes after 10+ settled days per station
- [ ] T013 [P] Spike S8 in `specs/001-paper-trading-mvp/spikes/S8-fees.md`: compare the fee formula (`ceil_to_cent(M x 0.07 x C x P x (1-P))`, `M` from series `fee_multiplier`) with Kalshi's published schedule for these series on 5 hand cases; decide per-level vs per-order rounding
- [ ] T014 Confirm station mapping against live market rules for all 8 series (`rules_primary` CLI codes CLINYC, CLICHI, CLILAX, CLIBOS) and write verified station, lat/lon, tz into `config/watches.default.json`: KXHIGHNY/KXLOWTNYC, KXHIGHCHI/KXLOWTCHI, KXHIGHLAX/KXLOWTLAX, KXHIGHTBOS/KXLOWTBOS

**Checkpoint**: spike notes S1-S6 and S8 written; plan amended where a spike failed (a failed spike changes plan.md before Phase 2 proceeds).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: money, time, store, config, run ledger, CLI skeleton, recorded fixtures. No user story starts before this checkpoint.

### Tests first
- [ ] T015 [P] Write `tests/test_money.py`: dollars-string to micro-dollars and back, no float drift, half-cent cases, "`fill_price` in (0,1)" validation
- [ ] T016 [P] Write `tests/test_timeutil.py`: local standard-time day window for NYC/Chicago/LA/Boston, including DST (window is 1:00 AM to 12:59 AM next day during DST), spring-forward and fall-back dates, UTC conversion
- [ ] T017 [P] Write `tests/test_store.py`: schema creation is idempotent; every CHECK/UNIQUE in data-model.md is enforced (`kind IN ('high','low')`, `scale IN ('real','test')`, `mode` constrained to `'paper'`, `UNIQUE(snapshot_id, market_ticker, model_id)`, `UNIQUE(prediction_id, account_id)`, `UNIQUE(intent_id, level_index)`, `UNIQUE(profile, slot_key, job)`); WAL on; read-only open cannot write
- [ ] T018 [P] Write `tests/test_config.py`: `HERMES_HOME` resolution; root home derived from `<root>/profiles/<name>`; DB path `plugin-data/hermes-kalshi/data.db`; shared snapshot dir under the root; `--db` override
- [ ] T019 [P] Write `tests/test_run_ledger.py`: `begin_run`/`finish_run`; second begin after `ok` returns `already_done`; skips recorded in `run_events`; concurrent begin yields one runner

### Implementation
- [ ] T020 [P] Implement `lib/kalshi_paper/money.py` (micro-dollar integer helpers) to pass T015
- [ ] T021 [P] Implement `lib/kalshi_paper/timeutil.py` (`zoneinfo`; LST-day window) to pass T016
- [ ] T022 Implement `lib/kalshi_paper/store.py`: full DDL from data-model.md (all tables, constraints, indexes), `schema_version`, idempotent migration runner, WAL pragma, read-only connector, `insert ... on conflict` helpers
- [ ] T023 [P] Implement `lib/kalshi_paper/config.py` and finish `config/watches.default.json` loading (depends on T014, T022)
- [ ] T024 Implement `lib/kalshi_paper/run_ledger.py` with `runs`/`run_events` semantics from data-model.md (depends on T022)
- [ ] T025 Implement `lib/kalshi_paper/cli.py` skeleton: argparse dispatcher, `--json`, exit codes 0/2/3/4, never prints secrets; command `init` seeds watches, default strategy version (contracts/strategy-config.md), and two accounts per watch ($100.00 real, $1,000.00 test) idempotently; test in `tests/test_cli_init.py` written first (quickstart A1)
- [ ] T026 [P] Write `tests/fixtures/capture.py` and capture recorded read-only responses into `tests/fixtures/` (Kalshi series/events/markets/orderbooks for all 8 series including a settled day, Open-Meteo ensemble for 4 points, NWS observations for 4 stations, and a recorded 429 body); no secrets are involved

**Checkpoint**: `python3 -m unittest discover -s tests` green; `kalshi-paper init` creates 8 watches and 16 accounts; second run changes nothing.

---

## Phase 3: User Story 1 - Public Market Data Skill (Priority: P1) 🎯

**Goal**: keyless scripts and a skill to read series, events, markets, quotes, orderbooks and settled results, encoding Kalshi quirks.

**Independent Test**: run the discovery and orderbook commands for one series against fixtures and live; brackets, derived YES asks, depth, and a settled result parse correctly (quickstart B1).

### Tests for User Story 1
- [ ] T027 [P] [US1] Write `tests/test_kalshi_client.py`: repeated `tickers` params for `/markets/orderbooks` (not comma-separated), derived `yes_ask = 1 - best_no_bid` and `no_ask = 1 - best_yes_bid`, ladders sorted explicitly, `_dollars`/`_fp` strings preserved, deprecated `liquidity_dollars` ignored, lowercase `status` vs filter `open`, token-bucket pacing, exponential backoff with jitter on the recorded 429 fixture, call-budget exhaustion yields a recorded skip (FR-001, FR-002)
- [ ] T028 [P] [US1] Write `tests/test_market_data_cli.py` for the `kalshi-market-data` script wrappers (JSON shape of `series`, `events`, `markets`, `book`, `settled`)

### Implementation for User Story 1
- [ ] T029 [US1] Implement `lib/kalshi_paper/kalshi_client.py`: keyless client for `https://api.elections.kalshi.com/trade-api/v2` (`/series/{t}`, `/events?series_ticker=`, `/markets?event_ticker=`, `/markets/orderbooks`, `/markets/{t}`), global token bucket (`KALSHI_CLIENT_RPS`, default 5), backoff, per-slot call budget, no `/series` list calls, no auth surface
- [ ] T030 [P] [US1] Create `skills/kalshi-market-data/SKILL.md` (frontmatter, when to use, quirks, verification) and `skills/kalshi-market-data/scripts/kalshi_data.py` thin wrapper; port the proven gotchas from the reference `kalshi-plugin-x` and credit it in `skills/kalshi-market-data/references/api-notes.md`
- [ ] T031 [US1] Register the skill in `__init__.py` via `ctx.register_skill("kalshi-market-data", .../SKILL.md)` (dir-iterating loop that only registers directories containing `SKILL.md`)

**Checkpoint**: US1 tests green; live read of one series prints brackets and books with <= 4 Kalshi calls.

---

## Phase 4: User Story 2 - Watch a Series in Test Mode (Priority: P1)

**Goal**: enable/pause/disable watches; new daily events and brackets are discovered automatically; two bankrolls per watch.

**Independent Test**: enable a watch, run discovery; accounts exist and a new event is picked up without manual enrollment (quickstart A1, spec US2).

### Tests for User Story 2
- [ ] T032 [P] [US2] Write `tests/test_watches.py`: enable creates accounts ($100.00 `real`, $1,000.00 `test`, `UNIQUE(watch_id, scale)`); pause/disable semantics; idempotent re-enable; a paused watch evaluates nothing but its open positions still settle (hook point asserted)
- [ ] T033 [P] [US2] Write `tests/test_discovery.py`: parse recorded events/markets into `markets.int_low/int_high` ("tail `T94` greater" = 95..+inf; "tail `T87` less" = -inf..86; "band `B93.5`" = 93..94), `rules_hash` stable, series naming variants (`KXHIGHNY` vs `KXHIGHTBOS`) handled by discovery not hardcoding (FR-003)

### Implementation for User Story 2
- [ ] T034 [US2] Implement `lib/kalshi_paper/watches.py` (create/update watches, accounts, strategy-version binding) and CLI `watch list|enable|pause|disable`
- [ ] T035 [US2] Implement `lib/kalshi_paper/discovery.py` (events for each watch's local today and tomorrow; upsert `events`/`markets`; capture `rules_text` and `rules_hash`)
- [ ] T036 [P] [US2] Create `skills/kalshi-ops/SKILL.md` covering watch management and chat usage; register in `__init__.py`; register `/kalshi-watch` via `ctx.register_command` using the handler signature recorded in spike S1

**Checkpoint**: 8 watches discovered against fixtures; US2 tests green.

---

## Phase 5: User Story 3 - Probabilities from a Frozen Snapshot (Priority: P1)

**Goal**: a content-addressed snapshot per slot; calibrated ensemble probabilities; bounded LLM adjustment; all stored with provenance.

**Independent Test**: for a stored snapshot, recomputation matches stored probabilities; probabilities per event sum to 1 +/- 0.001 (quickstart A3, A8).

### Tests for User Story 3
- [ ] T037 [P] [US3] Write `tests/test_weather.py`: Open-Meteo ensemble parsing (member columns like `temperature_2m_member01_ncep_gefs025`), NWS observation parsing and C-to-F conversion, outage/429 yields a recorded skip, never invented data (FR-010)
- [ ] T038 [P] [US3] Write `tests/test_snapshot.py`: canonical JSON hash is deterministic (hourly members rounded to 0.1 F, prices kept as strings), atomic slot pointer (race produces one snapshot), reuse returns the same hash, `skips` recorded, DB copy stored zlib-compressed (contracts/snapshot-format.md)
- [ ] T039 [P] [US3] Write `tests/test_model.py` (quickstart A3): LST-day extremes for high and low, nowcast clamp (observed extreme so far bounds each member), rounding-aware bracket probabilities `Phi((k+0.5-mu)/sigma) - Phi((k-0.5-mu)/sigma)` summed over the bracket's integer set, event sum 1 +/- 0.001, calibration `(bias, sigma)` applied
- [ ] T040 [P] [US3] Write `tests/test_adjust.py` (quickstart A8): +0.30 delta clipped to +0.15 and flagged, floor 0.001, renormalize per event, raw response hash stored, malformed/timeout leaves `llm_status` failed and falls back to ensemble-only
- [ ] T041 [P] [US3] Write `tests/test_predictions_store.py`: `UNIQUE(snapshot_id, market_ticker, model_id)` idempotency; `asof`/`fetched_at` non-null on provenance-bearing rows

### Implementation for User Story 3
- [ ] T042 [P] [US3] Implement `lib/kalshi_paper/weather.py` (Open-Meteo ensemble client for four points in one request; NWS observations client with `User-Agent`; both obey budgets and record skips)
- [ ] T043 [US3] Implement `lib/kalshi_paper/snapshot.py` (build from kalshi_client + weather, canonical hash, atomic slot pointer, DB copy) and CLI `snapshot --slot`
- [ ] T044 [P] [US3] Implement `lib/kalshi_paper/model.py` (member daily extremes, nowcast clamp, bracket probabilities, calibration lookup)
- [ ] T045 [US3] Implement `lib/kalshi_paper/adjust.py` (packet builder per contracts/agent-tools.md; bounded delta application; renormalization; `rationales` rows) and CLI `packet`
- [ ] T046 [US3] Implement `lib/kalshi_paper/predictions.py` (write `p_ensemble`, `p_llm_proposed`, `p_final`, `p_market`, `p_used` with strategy version and calibration used)
- [ ] T047 [US3] Register tools `kalshi_get_packet` and `kalshi_submit_adjustments` in `__init__.py` (handlers `def handler(args: dict, **kwargs) -> str` returning JSON) and create `skills/kalshi-evaluator/SKILL.md` including the 15-point cap and the "submit zero deltas when no justified view" rule

**Checkpoint**: given the recorded fixtures, a full probability table is produced and stored; US3 tests green.

---

## Phase 6: User Story 4 - Recommendations and Paper Trades (Priority: P1)

**Goal**: net edge, gates, sizing, orderbook-walking paper fills with fees, two bankrolls, hold to settlement, idempotent slots.

**Independent Test**: a fixed snapshot and settings reproduce hand-computed recommendations, fills, fees, sizes (quickstart A2, A4, A5, A6).

### Tests for User Story 4
- [ ] T048 [P] [US4] Write `tests/test_fees.py` (A2): 1 contract at $0.30 = $0.02; 16 at $0.30 = $0.24; 100 at $0.50 = $1.75; `fee_multiplier` applied; per-level rounding up per spike S8
- [ ] T049 [P] [US4] Write `tests/test_orderbook.py` (A2): NO bids `0.72 x 40`, `0.71 x 100` produce YES asks `0.28 x 40`, `0.29 x 100`; walking 60 contracts spans both levels with per-level fees; insufficient depth rejected with `depth`
- [ ] T050 [P] [US4] Write `tests/test_sizing.py` (A4): p_used 0.38, YES ask 0.30, fee 0.015 gives net edge 0.065, Kelly 0.0949, 0.25 fraction on $100 equity gives 7 contracts, binding cap `kelly`; caps per-trade 5%, per-event 10%, per-day 20%; gates `price_gate {"min": 0.05, "max": 0.95}`, `min_net_edge` 0.04, `burn_in_days` 3, `max_snapshot_age_min` 20; BUY NO edge `bid_yes - p_used - fee`
- [ ] T051 [P] [US4] Write `tests/test_executor.py`: order intent shape per contracts/order-intent.md, `mode='paper'` only, risk check recorded even on rejection, fills reference snapshot id, additional entries aggregate into `positions` with `UNIQUE(account_id, market_ticker, side)`, no early exit path exists
- [ ] T052 [P] [US4] Write `tests/test_finalize.py` (A5, A6): running `finalize` twice leaves row counts unchanged (`already_done`); recomputation from the stored snapshot copy reproduces edge, size, fills, fees exactly; `--ensemble-only` marks `llm_failed`; a paused watch is skipped

### Implementation for User Story 4
- [ ] T053 [P] [US4] Implement `lib/kalshi_paper/fees.py` and `lib/kalshi_paper/orderbook.py`
- [ ] T054 [US4] Implement `lib/kalshi_paper/sizing.py` (edge, qualified levels while marginal net edge >= min edge, fractional Kelly, caps, binding constraint, gates)
- [ ] T055 [US4] Implement `lib/kalshi_paper/executor.py` (`RiskChecker`, `Executor` protocol, `PaperExecutor`, `ApprovalGate` returning False for paper) per contracts/order-intent.md
- [ ] T056 [US4] Implement `lib/kalshi_paper/finalize.py` (the slot pipeline: load snapshot, finalize predictions, recommendations per account, intents, fills, positions) and CLI `finalize --slot [--ensemble-only]`; derive account cash/equity from fills/positions (view `v_account_ledger`)

**Checkpoint**: end-to-end offline run from fixtures yields predictions, recommendations, and paper fills; all US4 tests green.

---

## Phase 7: User Story 5 - Settlement and Scoring (Priority: P1)

**Goal**: settle positions, compute P&L, score every evaluated bracket for final/ensemble/market predictors, report calibration and edge realization.

**Independent Test**: a fixture settled day produces P&L to the cent and Brier/log-loss matching hand values (quickstart A7).

### Tests for User Story 5
- [ ] T057 [P] [US5] Write `tests/test_settle.py` (A7): win `contracts*(1.00) - cost - fees`, loss `-(cost) - fees`, idempotent re-run keeps `settled_at` and `realized_pnl_micro`, void markets excluded from scoring with reason, `positions` status transitions
- [ ] T058 [P] [US5] Write `tests/test_scoring.py`: Brier and log loss (p clipped to [1e-4, 1-1e-4]) for `ensemble`, `final`, `market`, `used`; `PRIMARY KEY(prediction_id, predictor)`
- [ ] T059 [P] [US5] Write `tests/test_report.py`: 10-bin calibration, claimed vs realized edge by bucket, hit rate and P&L by edge bucket, drawdown, breakdowns by city/kind/slot/model

### Implementation for User Story 5
- [ ] T060 [US5] Implement `lib/kalshi_paper/settle.py` (fetch `result`/settled value, store `rules_hash` source, store the observed extreme beside the settled value for spike S7) and CLI `settle [--since]`
- [ ] T061 [P] [US5] Implement `lib/kalshi_paper/scoring.py`
- [ ] T062 [P] [US5] Implement `lib/kalshi_paper/report.py` and CLI `report [--profile] [--since] [--format text|json]`; create the derived views `v_score_summary`, `v_calibration_bins`, `v_edge_realization`

**Checkpoint (core pipeline complete)**: fixtures-based full day (snapshot, finalize, settle, report) matches hand totals for both bankrolls; stop and review before scheduling.

---

## Phase 8: User Story 9 - Operations Profile and Scheduling (Priority: P2, scheduled early on purpose)

**Goal**: install the `kalshi-bot` profile and cron routines so data starts accumulating. Execution order moved ahead of US6-US8 because the 21-day evidence window is the project's long pole.

**Independent Test**: after setup, the profile exists with skills enabled and three routines; one manual run completes (quickstart C1, C2).

### Tests for User Story 9
- [ ] T063 [P] [US9] Write `tests/test_ops_jobs.py`: generated job definitions (snapshot, evaluate, finalize, settle, learn, health) match the slot table in plan.md; script-only jobs reference scripts under `$HERMES_HOME/scripts/`; evaluate job attaches `hermes-kalshi:kalshi-evaluator`
- [ ] T064 [P] [US9] Write `tests/test_run_recovery.py`: overlapping runs exit without duplicating work and record why; a failed run's next invocation processes missed settlements; slot-key idempotency across `snapshot`, `finalize`, `settle`
- [ ] T065 [P] [US9] Write `tests/test_health.py`: `health --json` reports last run per job/slot, skips, errors, snapshot age

### Implementation for User Story 9
- [ ] T066 [US9] Implement `lib/kalshi_paper/health.py` and CLI `health`
- [ ] T067 [P] [US9] Create shim scripts in `scripts/` (`kalshi_snapshot.sh`, `kalshi_finalize.sh`, `kalshi_settle.sh`, `kalshi_learn.sh`, `kalshi_health.sh`) and CLI `ops install-scripts` that copies/symlinks them into `$HERMES_HOME/scripts/` (method per spike S3)
- [ ] T068 [P] [US9] Create the `kalshi-bot` distribution under `profiles/kalshi-bot/`: `distribution.yaml` (name, `env_requires` none for MVP), `SOUL.md` (Kalshi research persona, paper-only rules, cap discipline), `config.yaml` (model placeholder, toolset `hermes_kalshi`, plugin enabled), `cron/jobs.json` (all jobs paused, slot times from contracts/strategy-config.md)
- [ ] T069 [US9] Extend `skills/kalshi-ops/SKILL.md` with the setup/runbook (install profile, review paused jobs, resume, health checks)
- [ ] T070 [NEEDS BACKEND] [US9] Install `kalshi-bot` on the backend, resume jobs, and capture evidence for quickstart C1/C2 in `specs/001-paper-trading-mvp/evidence/us9-scheduling.md`

**Checkpoint**: scheduled slots run unattended on the backend for 3 consecutive days with `health` clean; predictions and paper trades accumulate. Start of the evidence clock.

---

## Phase 9: User Story 6 - Desktop Dashboard (Priority: P2)

**Goal**: read-only API and Desktop pane showing overview, today's brackets, positions, performance, A/B compare, proposals, health.

**Independent Test**: with a populated DB, each pane section renders from the API; no write route exists; backend-down shows offline state (quickstart C4).

### Tests for User Story 6
- [ ] T071 [P] [US6] Write `tests/test_readmodels.py`: pure functions returning the JSON shapes in contracts/dashboard-api.md for every route; money as 4-place decimal strings; opening the DB read-only never modifies it
- [ ] T072 [P] [US6] Write `tests/test_dashboard_contract.py`: `dashboard/plugin_api.py` exposes only GET routes under the documented paths; error shapes `{ "error", "detail" }` for 404/503; no write method is registered
- [ ] T073 [P] [US6] Write `tests/test_readonly_concurrency.py`: reads succeed while a writer commits in a loop (WAL), per spike S6

### Implementation for User Story 6
- [ ] T074 [US6] Implement `lib/kalshi_paper/readmodels.py` (all views from data-model.md "Dashboard read models"; profile discovery under the root home)
- [ ] T075 [US6] Implement `dashboard/plugin_api.py` (module-level FastAPI `router`; every route delegates to `readmodels.py`; read-only connections) and `dashboard/manifest.json` (`name`, `label`, `tab`, `api: "plugin_api.py"`)
- [ ] T076 [US6] Implement `desktop/plugin.js` (ESM default export, folder id `hermes-kalshi`, `register(ctx)` adding a main pane/page + sidebar nav; sections Overview, Today, Positions, Performance, A/B Compare, Proposals, Health; data via `ctx.rest`; JSX via `react/jsx-runtime`; inline SVG charts for bankroll curve, calibration, edge realization; offline banner; proposals show the exact approve/reject command, not a button)
- [ ] T077 [P] [US6] Add `desktop/README.md` with load/reload instructions and a `node --check desktop/plugin.js` syntax-check step; run it
- [ ] T078 [NEEDS BACKEND] [US6] Validate in the Desktop app against the backend (quickstart C4) and record screenshots in `specs/001-paper-trading-mvp/evidence/us6-dashboard.md`

**Checkpoint**: dashboard renders from live backend data without errors during a running slot.

---

## Phase 10: User Story 7 - Threshold Learning with Approval (Priority: P2)

**Goal**: evidence-based proposals, human approval, versioned strategies.

**Independent Test**: fixture data yields a proposal with evidence; approving creates a new version used by the next run; rejecting changes nothing (quickstart A9, C5).

### Tests for User Story 7
- [ ] T079 [P] [US7] Write `tests/test_learn.py` (A9): below `proposal_min_samples` (`bucket` 30, `calibration_days` 10) no proposal and the reason is shown; above, a proposal with evidence JSON is created; deduplicated while pending
- [ ] T080 [P] [US7] Write `tests/test_proposals.py`: approve creates an immutable `strategy_versions` row (`source` `proposal:<id>`) and supersedes older pending ones; reject archives; unknown keys in `params_diff_json` rejected; later runs record the new `strategy_version_id`
- [ ] T081 [P] [US7] Write `tests/test_calibration_fit.py`: bias = mean residual, `sigma^2` = variance of residuals about the bias-corrected member mean with a floor; requires minimum samples per station/slot

### Implementation for User Story 7
- [ ] T082 [US7] Implement `lib/kalshi_paper/learn.py` (bucket analysis by edge, price range, city, kind, slot; calibration fit; proposal creation) and CLI `learn`, `proposal list|show|approve|reject`
- [ ] T083 [US7] Register slash commands `/kalshi-proposals`, `/kalshi-approve <id>`, `/kalshi-reject <id>`, `/kalshi-report [days]` and tool `kalshi_status` in `__init__.py`; keep every mutation in `lib/kalshi_paper` functions so future dashboard write routes can reuse them (planned follow-up spec)

**Checkpoint**: a proposal can be created from fixtures, approved in chat, and used by the next fixture run.

---

## Phase 11: User Story 8 - A/B Model Comparison (Priority: P2)

**Goal**: profiles `kalshi-bot-a` and `-b` with different models, separate DBs, identical snapshot per slot, comparison report.

**Independent Test**: one slot produces predictions in both DBs with the same `snapshot_id` and different `model_id`; `compare` reports both plus the ensemble baseline (quickstart C3).

### Tests for User Story 8
- [ ] T084 [P] [US8] Write `tests/test_shared_snapshot.py`: two temp profile homes under one temp root create/reuse one slot snapshot; both DBs reference the same `snapshot_id`
- [ ] T085 [P] [US8] Write `tests/test_compare.py`: only slots both profiles completed are compared; gaps listed; metrics per model and for the ensemble baseline over identical brackets
- [ ] T086 [P] [US8] Write `tests/test_setup_ab.py`: `ops setup-ab` dry-run prints the `hermes profile create --clone` and `config set model.default` commands; nothing executes without `--apply`

### Implementation for User Story 8
- [ ] T087 [US8] Implement `lib/kalshi_paper/compare.py` and CLI `compare --profiles a,b [--since]`
- [ ] T088 [US8] Implement CLI `ops setup-ab` (dry-run default; `--apply` runs the `hermes` CLI) and extend `skills/kalshi-ops/SKILL.md` with the A/B runbook
- [ ] T089 [NEEDS BACKEND] [US8] Create both profiles on the backend, choose two models, run a slot, and capture evidence for quickstart C3 in `specs/001-paper-trading-mvp/evidence/us8-ab.md`

**Checkpoint**: A/B comparison renders in the dashboard (`/compare` route already covered by US6).

---

## Phase 12: User Story 10 - Trading Seams for Later (Priority: P3)

**Goal**: prove nothing authenticated exists and the seam is respected.

**Independent Test**: `verify-no-auth` passes; paper trades pass through the order-intent path (quickstart A10).

### Tests for User Story 10
- [ ] T090 [P] [US10] Write `tests/test_no_auth.py` (A10, SC-009): greps `lib/`, `skills/`, `scripts/`, `dashboard/`, `desktop/` for signing libraries, `Authorization`, `KALSHI-ACCESS-`, private-key patterns, and the string `portfolio/balance`; asserts `order_intents.mode` CHECK is `'paper'`
- [ ] T091 [P] [US10] Write `tests/test_seams.py`: every paper trade has an `order_intents` row with a stored `risk_check`; `ApprovalGate.required` returns False in paper mode; `Executor` protocol has only `PaperExecutor` registered

### Implementation for User Story 10
- [ ] T092 [US10] Implement CLI `verify-no-auth` and wire it into the CI/test command
- [ ] T093 [P] [US10] Write `docs/trading-seams.md` summarizing the contracts/order-intent.md requirements for a future real-money spec (confirmation per order, hard dollar caps, kill switch, key storage in the profile credential store)

---

## Phase 13: Polish & Cross-Cutting Concerns

- [ ] T094 [P] Implement retention command `ops cleanup` (snapshot files older than 90 days; DB copies untouched) with `tests/test_cleanup.py` written first
- [ ] T095 [P] Performance checks: a slot for 8 watches in under 10 minutes including the LLM step (SC-002) and dashboard sections under 3 seconds on 30 days of data (SC-007); record numbers in `specs/001-paper-trading-mvp/evidence/performance.md`
- [ ] T096 Security review: confirm no secrets in logs/DB/repo, no hardcoded paths, `.gitignore` coverage; record in `specs/001-paper-trading-mvp/evidence/security.md`
- [ ] T097 Run the full quickstart (sections A through C) and store outputs in `specs/001-paper-trading-mvp/evidence/quickstart-run.md`
- [ ] T098 Run `speckit-analyze` and `speckit-converge` against spec, plan, tasks; resolve findings; hand to the different-lineage reviewer
- [ ] T099 Run `hermes plugins validate <repo> --install-deps` and fix findings
- [ ] T100 After 21 days and 1,000 scored brackets, generate the SC-008 evidence report (`kalshi-paper report --format json`) and present it to the user for the go/no-go decision

---

## Dependencies & Execution Order

### Phase dependencies
- **Setup (1)**: no dependencies. Spikes T006-T011, T013 run in parallel; a failed spike amends plan.md first.
- **Foundational (2)**: depends on T001-T005 and T014 (station config). Blocks all stories.
- **US1 (3)**: after Foundational. **US2 (4)**: after US1 (uses the client). **US3 (5)**: after US1, US2. **US4 (6)**: after US3. **US5 (7)**: after US4.
- **US9 scheduling (8)**: after US5 and spikes S1-S4. Moved ahead of US6-US8 deliberately to start data collection.
- **US6 (9)**: after US5 (read models need scored data); can start in parallel with US9 for API/UI work.
- **US7 (10)**: after US5 (needs scores) and meaningful settled data in practice.
- **US8 (11)**: after US3 and US9 (needs the shared snapshot path and profiles).
- **US10 (12)**: tests can run from Phase 2 onward; finalize after US4.
- **Polish (13)**: after the desired stories.

### Within each story
Tests written first and failing; then models/stores, services, CLI, tool/skill registration; then evidence capture.

### Parallel opportunities
- Setup: T002-T005, T006-T011, T013.
- Foundational tests T015-T019 together, then T020, T021, T023 together.
- US1: T027 with T028. US3: T037-T041 together, T042 with T044. US4: T048-T052 together, T053 alone first. US5: T057-T059 together, then T061 with T062. US9: T063-T065 together, T067 with T068. US6: T071-T073 together.

### Parallel example: User Story 4 tests
```text
Task: "Write tests/test_fees.py (A2) ..."
Task: "Write tests/test_orderbook.py (A2) ..."
Task: "Write tests/test_sizing.py (A4) ..."
Task: "Write tests/test_executor.py ..."
Task: "Write tests/test_finalize.py (A5, A6) ..."
```

---

## Implementation Strategy

### MVP slice: prove predictions and paper trades
1. Phase 1 (spikes) and Phase 2.
2. US1 to US5 in order: offline, fixture-driven, then one live read-only run.
3. **STOP and VALIDATE**: quickstart sections A and B; review gate.
4. US9: schedule on the backend (prediction and paper trades start accumulating, burn-in gate active).
5. US6 dashboard while data accumulates; US7 once enough days have settled; US8 once two models are chosen; US10 and Polish last.

### Incremental delivery
Each phase ends with a PR, a different-lineage review by the user, and the user's go to merge. The first PR can be the planning artifacts themselves (spec, plan, tasks).

### Key risks to track
- Settlement source vs observation feed (S7).
- Ensemble bias/overconfidence handled by calibration and the burn-in gate; scoring from day 1.
- Rate limits: Kalshi public limits are undocumented, so the client budget is config.
- Dashboard actions are a later phase; keep mutations in `lib/kalshi_paper` for reuse.

---

## Notes
- Task IDs are sequential in execution order within phases; story labels map to spec.md.
- No task introduces authenticated Kalshi access (Constitution III).
- Commit after each task or logical group; evidence files are committed, runtime data is not (Constitution VII).
