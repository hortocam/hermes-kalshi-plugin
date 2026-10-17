# Quickstart: Validation Scenarios

Runnable checks that prove the MVP end to end. Commands use the CLI contract ([contracts/cli.md](contracts/cli.md)); fixtures live in `tests/fixtures/`. Run from the plugin root. Expected outputs are what a correct build prints; mismatches mean a bug, not a flaky check.

## Prerequisites
- Python 3.10+, no third-party packages. Tests: `python3 -m unittest discover -s tests` (all green before any scenario).
- A scratch Hermes home for local runs: `export HERMES_HOME=$(mktemp -d)`; for network scenarios, outbound HTTPS to Kalshi, Open-Meteo, and api.weather.gov.
- Backend scenarios (S-B*) need the plugin installed on the Hermes backend (spike S1) and the `kalshi-bot` profile (spike S2).

## A. Offline scenarios (fixtures, no network)

**A1. Initialize**: `kalshi-paper init --json`. Expect 8 watches, 16 accounts (two per watch: $100.00 and $1,000.00), one default strategy version, exit 0; second run prints no changes (idempotent).

**A2. Fee and fill math**: `python3 -m unittest tests.test_fees tests.test_orderbook`. Hand cases (must pass):
- 1 contract at $0.30: fee $0.02 (0.0147 rounded up); 16 at $0.30: $0.24; 100 at $0.50: $1.75.
- Orderbook with NO bids `0.72 x 40`, `0.71 x 100` gives YES asks `0.28 x 40`, `0.29 x 100`; buying 60 walks both levels with per-level fees.

**A3. Probabilities**: `python3 -m unittest tests.test_model`. For a fixture of 82 identical members at 64.8 F with sigma 2.0, bracket `64-65` equals Phi((65.5-mu)/sigma) - Phi((63.5-mu)/sigma) and matches the hand-computed value to 1e-6 and all event brackets sum to 1 +/- 0.001. Nowcast fixture: observed max so far 66 F forces every member's extreme >= 66.

**A4. Edge and sizing**: `python3 -m unittest tests.test_sizing`. Fixture: p_used 0.38, YES ask 0.30, fee 0.015/contract -> net edge 0.065; all-in cost 0.315; Kelly full fraction 0.0949; at 0.25 fraction and $100 equity -> floor(2.37/0.315) = 7 contracts; binding cap `kelly`.

**A5. Idempotent slot**: `kalshi-paper finalize --slot 2026-10-17-midday --fixture tests/fixtures/slot_midday` twice. Second call prints `already_done`, row counts for predictions, recommendations, fills unchanged (SC-004).

**A6. Reproducibility**: `python3 -m unittest tests.test_recompute`. Recomputing from the stored snapshot copy yields identical `p_ensemble`, edge, size, fills, fees for every recommendation (SC-003).

**A7. Settlement and scores**: `kalshi-paper settle --fixture tests/fixtures/settled_day`. P&L matches the fixture's hand totals to the cent for both bankrolls (SC-006); Brier and log loss for ensemble, final, market match hand values; a voided market is excluded with a reason.

**A8. LLM bounds**: `python3 -m unittest tests.test_adjust`: delta +0.30 is clipped to +0.15 and flagged; event probabilities renormalize to 1; malformed input leaves the slot for ensemble-only finalize, flagged `llm_failed`.

**A9. Learning loop**: `python3 -m unittest tests.test_learn`: below sample minimums no proposal; above, a proposal with evidence is created; approve creates a new strategy version used by the next run; reject changes nothing.

**A10. No auth**: `kalshi-paper verify-no-auth` exits 0; the test greps for signing libraries, `Authorization`/`KALSHI-ACCESS-` headers, and key material patterns (SC-009).

## B. Live read-only scenarios (network, no side effects beyond the scratch DB)

**B1. Public data**: `kalshi-paper snapshot --slot $(date +%F)-morning --dry-run`. Expect brackets for all 8 series (tails `T` plus bands `B`), orderbooks with derived asks, ensemble member count 82 per city, observations present for today; total Kalshi calls <= 40 (check `run_events`).

**B2. Slot twice**: run B1 without `--dry-run` for two different scratch Hermes homes sharing a root; both report the same `snapshot_id` (shared slot, FR-023).

**B3. Rate-limit behavior**: with `KALSHI_CLIENT_RPS=50` and a recorded 429 fixture, the client backs off, then records a `kalshi_429_budget` skip and exits 3 without raising.

## C. Backend scenarios (installed plugin)

**C1. Skills and tools**: in a `kalshi-bot` chat, `skill_view("hermes-kalshi:kalshi-evaluator")` loads; `kalshi_status` returns watches.

**C2. Scheduled slot**: resume the paused jobs; at the next slot, `hermes cron runs` shows snapshot, evaluate, finalize ok; `kalshi-paper health --json` shows the slot; recommendations, intents, and fills exist (or reject codes explaining why none).

**C3. A/B**: after `ops setup-ab`, one slot produces predictions in both profile databases with the **same snapshot_id** and different `model_id`; `kalshi-paper compare --profiles kalshi-bot-a,kalshi-bot-b` reports both plus the ensemble baseline.

**C4. Dashboard**: open the pane; Overview, Today, Positions, Performance, A/B Compare, Proposals, Health render from `/api/plugins/hermes-kalshi/*`; during a running slot no errors appear; with the backend stopped the offline banner shows.

**C5. Proposal approval**: `/kalshi-proposals` lists a pending proposal (after sample minimums are met); `/kalshi-approve <id>` creates a new strategy version; the next recommendation records it.

## D. Success criteria checks (after 14+ days)
- SC-002: 7 consecutive days of slots with no unhandled error (`health`).
- SC-005: at least 600 scored brackets (`report --format json`).
- SC-008 evidence report: `kalshi-paper report --since <start> --format json` shows log loss for final vs market with a bootstrap interval, net P&L on both bankrolls, and realized vs claimed edge by bucket. The user decides.
