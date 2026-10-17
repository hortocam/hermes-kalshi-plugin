# Data Model: Kalshi Paper-Trading MVP

One SQLite database per profile (`$HERMES_HOME/plugin-data/hermes-kalshi/data.db`, WAL, foreign keys on). Schema version tracked in `schema_version`; migrations are idempotent and append-only. Money is stored as integer **micro-dollars** (1e-6 USD) to avoid float drift; probabilities as REAL in [0,1]; contract counts as INTEGER; timestamps as UTC ISO-8601 TEXT. Every fact table carries `asof` (true in the world) and `fetched_at` (when learned) where applicable.

## Entity overview

```
watches 1─* accounts 1─* positions
watches 1─* events 1─* markets
snapshots 1─* predictions *─1 markets
predictions 1─* scores
predictions 1─* recommendations *─1 accounts
recommendations 1─1 order_intents 1─* fills
strategy_versions 1─* watches(current) / recommendations(used)
proposals *─1 strategy_versions(new)
runs 1─* run_events
```

## Tables

### schema_version
`version INTEGER PK, applied_at TEXT, note TEXT`

### watches  (test-mode unit; FR-004..006)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| series_ticker | TEXT UNIQUE | e.g. KXHIGHTBOS |
| kind | TEXT CHECK in ('high','low') | |
| city | TEXT | display |
| cli_code | TEXT | e.g. CLIBOS, from market rules |
| obs_station | TEXT | NWS observation station, e.g. KBOS |
| lat, lon | REAL | forecast point (station coordinates) |
| tz | TEXT | IANA zone for the station |
| status | TEXT CHECK in ('active','paused','disabled') | |
| strategy_version_id | INTEGER FK | current version |
| created_at, updated_at | TEXT | |

### strategy_versions  (FR-021)
`id PK, parent_id FK NULL, params_json TEXT (see contracts/strategy-config.md), source TEXT ('default' | 'proposal:<id>' | 'manual'), created_at, note`. Immutable; a change creates a new row. Scope: global default row plus optional per-watch rows referenced by `watches.strategy_version_id`.

### accounts  (two per watch; FR-005)
`id PK, watch_id FK, scale TEXT CHECK in ('real','test'), starting_cash_micro INTEGER, created_at, UNIQUE(watch_id, scale)`. Cash and equity are **derived** from `fills`, `positions`, and `settlements` (no mutable balance column), so recomputation is always possible. A view `v_account_ledger` exposes running cash/equity per account.

### snapshots  (frozen inputs; FR-007)
`id TEXT PK (sha256 of canonical JSON), slot_key TEXT (YYYY-MM-DD-<slot>), fetched_at TEXT, schema TEXT, sources_json TEXT (versions/models/urls), blob BLOB (zlib JSON, full copy), created_by_profile TEXT`. Index on `slot_key`. Format in contracts/snapshot-format.md.

### events / markets  (discovered brackets)
**events**: `ticker PK, watch_id FK, local_date TEXT, open_time, close_time, expected_expiration, status, first_seen_at`.
**markets**: `ticker PK, event_ticker FK, strike_type TEXT ('greater','less','between'), floor_strike REAL NULL, cap_strike REAL NULL, int_low INTEGER NULL, int_high INTEGER NULL (inclusive whole-degree set, derived), rules_hash TEXT, rules_text TEXT, status TEXT, result TEXT NULL ('yes','no'), settled_value REAL NULL, settled_at TEXT NULL, settle_asof, settle_fetched_at`. `int_low/int_high` encode the rounding-aware set (tail `>94` = 95..+inf; `<87` = -inf..86; band `93-94` = 93..94).

### runs / run_events  (ledger; FR-015, FR-024)
**runs**: `id PK, profile TEXT, slot_key TEXT, job TEXT ('snapshot'|'evaluate'|'finalize'|'settle'|'learn'), started_at, finished_at, status ('ok'|'partial'|'skipped'|'failed'), model_id TEXT NULL, UNIQUE(profile, slot_key, job)`.
**run_events**: `id PK, run_id FK, at, level ('info'|'skip'|'error'), watch_id NULL, code TEXT, detail TEXT`. Skips (forecast outage, 429 budget, stale snapshot, empty book) are recorded here, never fabricated.

### predictions  (one row per bracket per snapshot per model; FR-008)
| Column | Notes |
|---|---|
| id PK | |
| snapshot_id FK, market_ticker FK, model_id TEXT | UNIQUE(snapshot_id, market_ticker, model_id) (idempotency) |
| p_ensemble | calibrated ensemble probability (control predictor) |
| p_llm_proposed | NULL if no adjustment |
| p_final | after clip + renormalize (or = p_ensemble when `llm_failed`) |
| p_market | market-implied at snapshot (mid of yes bid and derived ask; documented fallback to last price) |
| p_used | `w*p_final + (1-w)*p_market` per strategy |
| clipped INTEGER, llm_status TEXT ('ok','failed','timeout','invalid','none') | |
| rationale_id FK NULL | |
| strategy_version_id FK | version in force |
| calib_bias, calib_sigma REAL | calibration used |
| created_at | |

### rationales
`id PK, event_ticker, snapshot_id, model_id, text TEXT, raw_hash TEXT, tokens_in/out INTEGER NULL, created_at`.

### recommendations  (decision per prediction per account; FR-011, FR-012)
`id PK, prediction_id FK, account_id FK, decision TEXT ('buy_yes','buy_no','none'), reject_code TEXT NULL (e.g. 'edge_below_min','price_gate','depth','burn_in','stale_snapshot','cap'), net_edge_micro_per_contract INTEGER NULL, kelly_contracts INTEGER NULL, final_contracts INTEGER NULL, binding_cap TEXT NULL ('kelly','trade','event','day','depth'), strategy_version_id FK, UNIQUE(prediction_id, account_id)`.

### order_intents / fills  (seam + paper executor; FR-013, FR-016)
**order_intents**: `id PK, recommendation_id FK UNIQUE, account_id, market_ticker, side ('yes','no'), action 'buy', contracts INTEGER, limit_price_micro INTEGER, tif TEXT 'ioc', mode TEXT CHECK = 'paper', risk_check_json TEXT (limits evaluated), created_at`. `mode` is constrained to `'paper'` in the MVP (CHECK constraint), so no real intent can be stored.
**fills**: `id PK, intent_id FK, level_index INTEGER, price_micro INTEGER, contracts INTEGER, fee_micro INTEGER (per-level, rounded up to cent), book_ref TEXT (snapshot id + side)`; `UNIQUE(intent_id, level_index)`. A rejected intent has zero fills and a `reject_code` on the recommendation.

### positions / settlements  (hold to settlement; FR-014, FR-017)
**positions**: `id PK, account_id FK, market_ticker FK, side, contracts, cost_micro, fees_micro, opened_first_at, opened_last_at, status ('open'|'settled'|'void'), realized_pnl_micro NULL, settled_at NULL, UNIQUE(account_id, market_ticker, side)`. Additional entries increase contracts/cost/fees (idempotent per fill id via `fills`).
**settlements**: `market_ticker PK, result ('yes'|'no'|'void'), settled_value REAL NULL, settled_at, source_rules_hash, asof, fetched_at`.
P&L: win `contracts*(1.00) - cost - fees`; loss `-(cost) - fees`; void: refund cost, fees per Kalshi (policy recorded in settlement note). Computed from fills; re-running never changes stored values (idempotent).

### scores  (every evaluated bracket; FR-018)
`prediction_id FK, predictor TEXT ('ensemble','final','market','used'), outcome INTEGER (1 yes / 0 no), p REAL, brier REAL, log_loss REAL (p clipped to [1e-4, 1-1e-4]), scored_at, PRIMARY KEY(prediction_id, predictor)`. Voided/undetermined markets are excluded (reason on settlement).

### proposals  (FR-020)
`id PK, created_at, scope ('global'|watch_id), evidence_json (sample sizes, bucket tables, metric deltas), params_diff_json, status ('pending'|'approved'|'rejected'|'superseded'), decided_at, decided_by TEXT, resulting_version_id FK NULL, UNIQUE-ish dedupe key on (scope, params_diff hash, status='pending')`.

### cache_meta
`key PK, value TEXT, fetched_at, expires_at` (series metadata daily cache, station mapping).

## State machines
- **Run**: planned -> running -> ok | partial | skipped | failed. A (profile, slot, job) triple has at most one terminal row; re-invocation after `ok` returns `already_done`.
- **Market**: discovered -> open -> closed -> settled | void.
- **Position**: open -> settled | void (terminal, immutable).
- **Proposal**: pending -> approved (creates new strategy version, supersedes older pending) | rejected | superseded.
- **Snapshot slot**: absent -> created (atomic, immutable). Never mutated.

## Validation rules (from the spec)
- Bracket probabilities per event sum to 1 within 0.001 for `p_ensemble` and `p_final`.
- `fill_price` in (0,1); `contracts > 0`; `fee >= 0`; fee formula tested against hand cases.
- No row in provenance-bearing tables has null `asof` or `fetched_at`.
- Caps enforced at decision time using equity derived from fills as of the decision; binding constraint stored.
- `order_intents.mode = 'paper'` always; no table stores credentials.

## Dashboard read models (derived views, not new tables)
`v_account_ledger`, `v_bankroll_curve` (daily equity), `v_open_exposure` (per event/day), `v_score_summary` (by predictor/city/kind/slot/model), `v_calibration_bins` (10 bins), `v_edge_realization` (claimed vs realized by edge bucket), `v_slot_health`.
