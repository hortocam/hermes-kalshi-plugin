# Contract: `kalshi-paper` CLI

Invocation: `python3 <plugin>/lib/kalshi_paper/cli.py <command>` (also `python3 -m kalshi_paper` with `PYTHONPATH=<plugin>/lib`). Script-only cron shims in `$HERMES_HOME/scripts/` call the same commands. Stdlib only. Resolves its database from `HERMES_HOME`; `--db` overrides for tests. Every command accepts `--json` (machine output on stdout, diagnostics on stderr) and is **idempotent**.

Exit codes: `0` ok or `already_done`; `2` usage error; `3` partial (some watches skipped, details in run_events); `4` fatal (store unavailable, schema mismatch). Never prints secrets.

| Command | Purpose | Notes |
|---|---|---|
| `init` | create/migrate the DB, seed watches from `config/watches.default.json`, create the default strategy version and both accounts per watch | safe to re-run |
| `watch list|enable|pause|disable <series>` | manage watches; `enable` creates accounts ($100 real, $1,000 test defaults, overridable) | FR-004, FR-005 |
| `snapshot --slot <YYYY-MM-DD-slot>` | create-or-reuse the shared slot snapshot; store a copy in the DB | reuse prints the existing hash; FR-007, FR-023 |
| `packet --slot <slot> [--watch <series>]` | build the LLM evaluation packet from the stored snapshot | used by the agent tool |
| `finalize --slot <slot> [--ensemble-only]` | compute `p_final`, `p_used`, recommendations, paper fills for all brackets; `--ensemble-only` marks `llm_failed` | idempotent per (snapshot, market, model) |
| `settle [--since <date>]` | fetch settled results, settle positions, write scores | FR-017, FR-018 |
| `learn [--watch <series>]` | analyze buckets and create proposals if sample minimums are met | FR-020 |
| `proposal list|show <id>|approve <id>|reject <id>` | human decision; `approve` creates a new strategy version | the only write path for thresholds |
| `report [--profile P] [--since D] [--format text|json]` | scores, calibration, edge realization, P&L | |
| `compare --profiles a,b [--since D]` | A/B over slots both completed | FR-023, US8 |
| `health` | last run per job/slot, skips, errors | |
| `ops setup-ab` | create `kalshi-bot-a`/`-b` by cloning `kalshi-bot`, set models, install paused routines | calls `hermes` CLI; dry-run by default |
| `verify-no-auth` | static check that no signing/auth code or headers exist | SC-009 |

## Behavioral guarantees
- Re-running a command for a completed (profile, slot, job) returns `already_done` with the original result summary and creates no rows.
- Upstream failure (Kalshi 429/5xx, Open-Meteo outage, NWS failure) never raises past the command boundary: it writes a `run_events` skip with a code and returns exit 3 if some work completed, 0 if the skip is the whole expected outcome.
- All timestamps UTC; local-day logic only inside `model.py` via the watch's `tz`.
