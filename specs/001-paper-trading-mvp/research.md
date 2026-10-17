# Phase 0 Research: Kalshi Paper-Trading MVP

Date: 2026-10-17. Sources: Hermes docs (plugins, desktop, dashboard extension, cron, profiles, profile distributions), Kalshi docs and help center, Open-Meteo ensemble docs, live probes run from the user's machine on 2026-10-16/17, and the reference repo `kalshi-plugin-x`.

Items marked **[SPIKE]** could not be settled from documentation and become the first tasks (see plan.md, Phase 0 Spikes).

## R1. Packaging: one Hermes "unified package"
- **Decision**: one plugin directory `hermes-kalshi/` containing `plugin.yaml`, `__init__.py` (`register(ctx)`), bundled skills, `dashboard/` (manifest + `plugin_api.py`), `desktop/plugin.js`, plus a separate profile distribution for `kalshi-bot`.
- **Rationale**: docs confirm `ctx.register_skill(name, path_to_SKILL.md)` bundles skills (loaded as `hermes-kalshi:<skill>`), `ctx.register_tool` adds agent tools, `ctx.register_command` adds slash commands, and a unified package carries the Desktop half at `$HERMES_HOME/plugins/<id>/desktop/plugin.js`. This supersedes the interview answer "skills bundle + separate desktop plugin" only in delivery shape: it is still two logical pieces (skills/scripts, desktop pane) but installs and versions together. User confirmed (2026-10-17).
- **Alternatives**: hub-installed skills tap + separate `desktop-plugins/<id>/plugin.js` (two installs, version skew); MCP server (extra process, not needed).
- **Caveats**: registered skills are read-only and not in the system-prompt index; cron jobs must attach them explicitly (`--skill hermes-kalshi:kalshi-evaluator`). **[SPIKE S1]** confirm `plugin.yaml` need not declare the desktop half and `hermes plugins validate` passes.

## R2. Runtime state and per-profile databases
- **Decision**: each profile's database lives at `$HERMES_HOME/plugin-data/hermes-kalshi/data.db` (SQLite, WAL). Core code resolves the path from `HERMES_HOME` (set by the profile wrapper), so it works from scripts, cron, tools, and tests. Inside plugin code `plugin_db("hermes-kalshi")` resolves to the same file.
- **Rationale**: docs say plugin state goes under `<hermes home>/plugin-data/<name>/`, profile-scoped; runtime state must never be written into the plugin directory. This gives `kalshi-bot`, `kalshi-bot-a`, `kalshi-bot-b` separate databases with no extra work.
- **Alternatives**: one shared DB with a profile column (breaks "each profile owns its DB", complicates A/B isolation).

## R3. Dashboard data path (user-verified)
- **Decision**: `dashboard/plugin_api.py` exposes a module-level FastAPI `router`; routes mount at `/api/plugins/hermes-kalshi/*`; the Desktop pane calls them with `ctx.rest(path)`. The API opens each profile DB read-only (`file:...?mode=ro`, WAL) and returns JSON.
- **Rationale**: matches the mechanism the user verified on the backend (gateway runs as the user that owns all profile dirs). Docs: routes mount once at dashboard startup (restart after route changes) and sit behind the dashboard auth gate.
- **Caveats**: docs do not say which `HERMES_HOME` the dashboard process sees, so the API enumerates `<root>/profiles/*` from the root home explicitly. **[SPIKE S6]** confirm read-only access during a concurrent write.
- **Decision (read-only)**: the API has no write routes in the MVP (FR-026). Approving proposals, enabling/pausing watches, and running slots happen through slash commands/tools and the CLI; the pane shows the exact command to run. User confirmed for the MVP (2026-10-17); dashboard actions are wanted in a later phase.

## R4. Profiles and scheduling
- **Decision**: ship `kalshi-bot` as a Hermes profile distribution (`hermes profile install <repo>`): `distribution.yaml`, `SOUL.md`, `config.yaml`, `cron/jobs.json`. `kalshi-bot-a` and `kalshi-bot-b` are created by a setup command that clones `kalshi-bot` (`hermes profile create --clone`) and sets each model. Shipped cron jobs install **paused** and are resumed after review.
- **Cron facts**: `hermes cron create "<schedule>" "<prompt>" --skill ... --name ... --deliver ...`; script-only jobs `--no-agent --script <file>` (scripts must live in `$HERMES_HOME/scripts/`, empty stdout = silent, non-zero exit alerts); overlapping manual runs are refused; scheduler ticks every 60 s with a file lock; run history in `cron/executions.db`; fresh session per run with no memory, so prompts must be self-contained.
- **Decision**: deterministic steps (snapshot, settle, score, learn, health) are **script-only jobs** (no LLM cost, no flakiness). Only the evaluation step uses an agent job. A script-only `finalize` job runs a few minutes later and completes any slot where the agent failed, using ensemble-only probabilities flagged `llm_failed`.
- **Open**: timezone handling for schedules is undocumented. **[SPIKE S3]** test cron expressions with an explicit timezone; fallback is UTC expressions regenerated at DST changes by a setup command. Also confirm `hermes -p <profile> cron create` targets that profile, and how the plugin installs shim scripts into `$HERMES_HOME/scripts/` (symlink or copy at setup).

## R5. Forecast base: Open-Meteo ensembles
- **Verified live (2026-10-17)**: `https://ensemble-api.open-meteo.com/v1/ensemble?latitude=..&longitude=..&hourly=temperature_2m&models=gfs025,ecmwf_ifs025&temperature_unit=fahrenheit&forecast_days=2&timezone=America/New_York` returns 200; 82 member series plus time for two models (GFS: control + 30 members = 31; ECMWF IFS: control + 50 members = 51), column names like `temperature_2m_member01_ncep_gefs025`, `temperature_2m_member48_ecmwf_ifs025_ensemble`; hourly resolution.
- **Decision**: base = pooled GFS (0.25°) + ECMWF IFS (0.25°) members, hourly 2 m temperature in °F, local timezone; daily max/min computed by code over the **local standard-time day** (the market window, 1:00 AM to 12:59 AM next day during DST), not by the API's calendar-day `daily` aggregation.
- **Free tier**: documented as non-commercial; call weight grows with locations x variables x models x time range; exact limits not on the docs page. One request per slot for all 4 cities (comma-separated coordinates) keeps usage tiny. **[SPIKE S5]** record real call weights and headers.
- **Known weaknesses (design response)**: 0.25° grid, not the station; hourly sampling understates the true peak; members are overconfident. Response: a **calibration layer** (per station, per run slot): bias `b` and spread `sigma`, starting from conservative priors (sigma 2.5 F, bias 0) and updated only through approved proposals from settled data. A `burn_in_days` gate (default 3 settled days per watch) blocks paper trades until the calibration has any evidence; predictions are still recorded and scored from day 1.
- **Alternatives**: single deterministic NWS forecast (no distribution); paid providers (no account; not needed yet).

## R6. Observed temperatures for the midday/afternoon nowcast
- **Verified live**: `https://api.weather.gov/stations/KBOS/observations?limit=3` returns 200 with a keyless request (needs a `User-Agent`), 5–10 minute METAR observations in whole °C.
- **Decision**: nowcast = for each ensemble member, daily extreme = max(observed max so far, member's max over remaining hours). Observed values are converted to °F and treated as lower bounds with a small tolerance, because whole-degree-C METAR and the settlement source can differ.
- **Settlement source note**: market rules read "maximum temperature recorded at Boston (CLIBOS) ... according to The Weather Company" (verified 2026-10-16), while Kalshi's help article says the NWS Daily Climate Report. The rules text is captured per market (hash stored) and treated as authoritative; the CLI code (CLIBOS, CLINYC, ...) is the station key, mapped to an NWS observation station in config. **[SPIKE S7]** measure observation-vs-settlement discrepancy over the first weeks.
- **Alternatives**: Open-Meteo current/past-day data (model analysis, not station obs).

## R7. Kalshi public API usage and rate limits
- **Facts**: base `https://api.elections.kalshi.com/trade-api/v2`; useful keyless calls: `GET /series/{ticker}`, `GET /events?series_ticker=&status=open`, `GET /markets?event_ticker=`, `GET /markets/orderbooks` (repeated `tickers` params), `GET /markets/{ticker}` (settled `result`). Orderbook shape: `orderbook_fp.yes_dollars`/`no_dollars` as `[price, size]` strings. Kalshi docs publish per-second budgets for authenticated tiers only (Basic: 200 read/s); 429 body is `{"error":"too many requests"}` with no `Retry-After`; guidance is exponential backoff, batch calls cost per item.
- **Observed**: 429 after repeated `/series`-dump searches in the reference tool; the dump is avoided entirely here.
- **Decision**: never call `/series` list; per slot use ~3 calls per series (series metadata cached daily, events, batched orderbooks) = about 30 calls per slot for 8 watches; client has a global token-bucket (default 5 req/s), exponential backoff with jitter, and a per-slot call budget. Unauthenticated limits are undocumented, so values are config.
- **Fees**: formula `ceil_to_cent(M x 0.07 x C x P x (1-P))` with `M` read from the series' `fee_multiplier`/`fee_type` (reference repo). Multi-level fills compute fees per price-level fill, rounded up (conservative). Reconciled in spike S8 (2026-10-17): formula and `M = 1` confirmed against the official schedule; the schedule's "round up to a centicent" wording vs its cent-rounded table is unresolved, so the MVP keeps ceil-to-cent per level (conservative).
- **Tradable window**: markets open the day before (the Oct 17 Boston market opened 2026-10-16 14:00Z) and close at about 05:00Z the next day; so the morning slot can evaluate today's and tomorrow's events.

## R8. Probability model (deterministic core)
- **Decision**: for each member i, daily extreme `X_i` (max for high, min for low, with nowcast clamp). Settlement values are whole degrees, so with calibrated mean `X_i + b` and spread `sigma`, `P(value = k) = Phi((k+0.5-mu)/sigma) - Phi((k-0.5-mu)/sigma)`, averaged over members. Bracket probability = sum over integer values in the bracket (band `B93.5` = {93, 94}; tail `T94` greater = {95,...}; tail `T87` less = {...,86}). Normal CDF via `math.erf` (stdlib).
- **Rationale**: handles rounding, smooth member discreteness, no numpy.
- **Calibration proposal**: closed-form from settled data (bias = mean residual; sigma^2 = variance of residuals about the bias-corrected member mean, with a floor); needs minimum samples per station/slot before proposing.

## R9. LLM adjustment layer
- **Decision**: agent receives an "evaluation packet" (per event: bracket probabilities from ensemble, market prices, ensemble summary, observations, optional fetched forecast discussion) via a tool, returns per-bracket deltas and a rationale via a second tool; code clips to the cap (15 points default), renormalizes within each event (brackets are mutually exclusive and exhaustive), stores raw response hash, model id, and clip flags. On timeout/invalid output: ensemble-only, flagged.
- **Alternatives**: LLM outputs absolute probabilities (harder to bound/audit); LLM picks trades (breaks the "code scores" principle).

## R10. A/B on a shared frozen snapshot
- **Decision**: snapshots are content-addressed JSON written once to a shared directory under the **root** Hermes home (`<root>/plugin-data/hermes-kalshi/snapshots/`), with a per-slot pointer file created atomically (create-if-absent). Any profile running `snapshot --slot <date>-<slot>` either creates it or reuses it, so there is no scheduling dependency between profiles. Each profile also stores a compressed copy in its own DB (portable, reproducible). Evaluations require snapshot age under a limit (default 20 min).
- **Open**: **[SPIKE S4]** confirm profiles can read/write the shared directory (same OS user) and the atomic pointer works on the homelab filesystem.

## R11. Dependencies and runtime
- **Decision**: Python 3.10+ compatible, stdlib only for core, CLI, and tools (`sqlite3`, `urllib`, `json`, `math`, `zlib`, `hashlib`, `argparse`, `datetime`/`zoneinfo`). `fastapi` comes from the Hermes dashboard environment and is only imported in `plugin_api.py`. Desktop code uses only `@hermes/plugin-sdk` and `react`; charts are hand-drawn SVG (docs show no chart kit). **[SPIKE S1]** confirms the backend's Python version.

## R12. Testing
- **Decision**: `unittest`/`pytest`-compatible tests with hand-computed fixtures for fees, orderbook walks, Kelly sizing, bracket probabilities, P&L, scores; recorded-response fixtures for Kalshi/Open-Meteo/NWS; a contract test that no module imports signing code or sends auth headers (SC-009).
