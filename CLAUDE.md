# CLAUDE.md — hermes-kalshi-plugin

Guidance for Claude Code working in this repo. Read this first, then the constitution.

## What this project is

A Hermes Agent plugin ("hermes-kalshi") that reviews Kalshi **climate markets (daily high/low temperature for NYC, Chicago, LA, Boston)**, builds probability predictions, and places **paper trades only** with fake bankrolls, so prediction quality can be proven before any real money is considered. Owner: Cameron. The MVP is `specs/001-paper-trading-mvp`.

**Hard line: no authenticated Kalshi access, no real orders, anywhere, in this MVP.** No signing libraries, no API keys, no `portfolio/balance`. A test (`verify-no-auth`) enforces this. Real trading is a later, separate spec.

## Read before coding

1. `.specify/memory/constitution.md` — eight principles; they override everything below. (If `.specify/` is missing, regenerate the scaffold: `specify init --here --integration claude --script sh --force`.)
2. `specs/001-paper-trading-mvp/spec.md` — what and why (US1..US10, FR-001..029, SC-001..009).
3. `plan.md`, `research.md`, `data-model.md`, `contracts/*`, `quickstart.md` — how.
4. `tasks.md` — **the work queue.** Work tasks in order within a phase; do not skip ahead.
5. `docs/requirements-brief*.md` — original requirements, for intent when the spec is ambiguous.

If code and spec disagree, the spec wins; if the spec is wrong, fix the spec in its own commit first (constitution I), then the code.

## How to work (Spec Kit, lighter process)

- Flow: spec → plan → tasks → implement. Use `/speckit-implement` for task execution, `/speckit-analyze` and `/speckit-converge` before review gates.
- **TDD is mandatory** (constitution II). Write the test, run it, see it fail for the right reason, then implement. Money math uses hand-computed expected values from `quickstart.md` section A; never derive expected values by running the code under test.
- One short-lived branch per phase or logical group (`NNN-short-name`), small commits, mark tasks `[x]` in `tasks.md` in the same commit that completes them.
- Evidence over assertion (V): after a task, paste real command output (test runs, CLI output) into the PR or `specs/.../evidence/*.md`. "Should work" is not done.
- Never mark a task done if tests fail, work is partial, or a `[NEEDS BACKEND]` step wasn't actually run on the backend.
- Simple and stdlib-first (VIII): core library is stdlib-only Python 3.10+. `fastapi` is allowed only in `dashboard/plugin_api.py`. Adding a dependency needs a written justification in the PR.

## Build/review/merge rules (constitution IV)

- Claude Code builds. A **different-lineage model (Ollama Cloud), launched by Cameron, does adversarial review.** Do not review or approve your own work.
- Open PRs; **Cameron gives the go on every merge.** Never merge, never push to `main`, never force-push shared branches.
- Phase boundaries in `tasks.md` are review gates: stop at each **Checkpoint**, summarize evidence, wait.
- Commit trailers (required):
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```
  (Use the exact attribution lines your session instructs, if different.)

## Commands

- Tests: `python3 -m unittest discover -s tests`
- Init data dir (after US-foundation work): `python3 -m lib.kalshi_paper.cli init` (entry point `kalshi-paper` per `contracts/cli.md`)
- Syntax check desktop code: `node --check desktop/plugin.js`
- Plugin validation (Polish phase): `hermes plugins validate <repo> --install-deps`
- Scaffold regeneration: `specify init --here --integration claude --script sh --force`

## Repo layout (target; see plan.md for the full tree)

```
plugin.yaml  __init__.py           Hermes plugin entry (register tools/skills/commands)
lib/kalshi_paper/                  all logic (store, kalshi_client, weather, snapshot, model,
                                   fees, orderbook, sizing, executor, settle, scoring, learn, ...)
skills/{kalshi-market-data,kalshi-evaluator,kalshi-ops}/
scripts/                           thin shell shims installed into $HERMES_HOME/scripts/
dashboard/{manifest.json,plugin_api.py}   READ-ONLY API
desktop/plugin.js                  Hermes Desktop pane
profiles/kalshi-bot/               profile distribution (SOUL.md, config.yaml, cron/jobs.json)
config/watches.default.json
tests/  tests/fixtures/            recorded responses; no network in unit tests
specs/001-paper-trading-mvp/       spec, plan, tasks, contracts, evidence/, spikes/
```

Business logic lives in `lib/kalshi_paper`. Tools, slash commands, CLI, and the dashboard API are thin wrappers so every behavior is testable offline and future dashboard actions can reuse the same functions.

## Key facts and conventions (don't re-derive; they are decided)

- Kalshi public API base: `https://api.elections.kalshi.com/trade-api/v2`, no auth. Series: `KXHIGHNY, KXHIGHCHI, KXHIGHLAX, KXHIGHTBOS` and `KXLOWTNYC, KXLOWTCHI, KXLOWTLAX, KXLOWTBOS`. Naming varies, so discover via the API, never hardcode event tickers. Do **not** call the huge `/series` list (18 MB, triggers 429). Rate limits are undocumented: use a token bucket (default 5 rps), backoff with jitter, per-slot call budgets, and record skips.
- Orderbooks: `/markets/orderbooks` with **repeated** `tickers` params. Orderbooks show bids only: `yes_ask = 1 − best NO bid`, `no_ask = 1 − best YES bid`. Prices are dollar strings; keep them as strings/integers, never floats for money.
- Money: integer **micro-dollars** in the DB. Fee: `ceil_to_cent(M × 0.07 × C × P × (1−P))`, `M` from the series `fee_multiplier`; per-level rounding is the working assumption until spike S8 settles it.
- Forecast: Open-Meteo ensembles (`gfs025` 31 members + `ecmwf_ifs025` 51, hourly °F, local tz) → daily extreme over the **local standard-time day** → nowcast clamp using NWS observed extreme so far → rounding-aware bracket probabilities (normal CDF via `math.erf`) → calibration (bias, sigma; prior sigma 2.5°F; `burn_in_days=3` gate).
- LLM role: adjusts ensemble probabilities within ±15 points (configurable per strategy version), renormalized per event; code does all scoring/sizing. LLM failure → ensemble-only fallback, flagged, never a stall.
- Defaults: min net edge 0.04, price gate [0.05, 0.95], Kelly fraction 0.25, caps 5% per trade / 10% per event / 20% per day, snapshot max age 20 min, bankrolls $100 (`real`) and $1,000 (`test`) per watch, slots 07:00 / 12:30 / 16:30 ET. All live in the versioned strategy config (`contracts/strategy-config.md`); changes arrive only through the proposal-and-approval flow, never silently.
- Positions are held to settlement (additional entries allowed; no early exit in MVP).
- Everything evaluated is scored (Brier/log loss for ensemble, final, market) whether or not traded.
- State: SQLite per profile at `$HERMES_HOME/plugin-data/hermes-kalshi/data.db` (WAL). Shared content-addressed snapshots live under the **root** Hermes home so profiles `kalshi-bot-a`/`-b` (A/B model comparison) see identical inputs. Schema and constraints: `data-model.md` — quote constraints verbatim into tests.
- Dashboard is **read-only** in the MVP (actions come later). It opens SQLite read-only; no write route may exist.
- Hermes plugin API details (register_tool/skill/command, dashboard `plugin_api.py` mounting, cron script-only jobs in `$HERMES_HOME/scripts/`) are in `research.md`; spikes S1–S8 verify them. **Spikes come first** and a failed spike amends `plan.md` before building on it.

## Environment notes

- Cameron's Hermes backend ("Jarvis") runs on a homelab (Linux, always-on); the Desktop app connects remotely. Tasks tagged `[NEEDS BACKEND]` need that environment or Cameron; ask rather than faking results.
- `../kalshi-plugin-x` (on Cameron's Mac, not in this repo) is a **reference** implementation. Port proven pieces deliberately with credit; don't assume it is correct or copy its structure.
- Unit tests must not touch the network or a real `$HERMES_HOME`; use `tests/helpers.py` temp homes and recorded fixtures. Live read-only checks are the quickstart B scenarios only.

## Do not

- Add any Kalshi authentication, order placement, or portfolio endpoint.
- Commit secrets, `.env`, DB files, `plugin-data/`, snapshots, or tokens (VII). Never print tokens.
- Invent weather or market data when a source fails; record a skip with a reason.
- Change thresholds, caps, or model parameters in code to "improve results"; use a new strategy version via proposal.
- Edit `specs/` casually; spec changes are their own commits with a reason.
- Hardcode paths; resolve `HERMES_HOME` and the root home through `lib/kalshi_paper/config.py`.

## When stuck

State what you tried and what you need, in the PR or to Cameron. Don't loop on a failing approach. Prefer asking over guessing when a decision is irreversible or changes scope.
