# Hermes Kalshi Plugin Constitution
<!-- Ratified: 2026-10-15 | Lighter charter than the kalshi-skill reference repo. Amendments EXTEND with a recorded Why. -->

## Core Principles

### I. Spec-First
Every feature beyond a trivial fix starts as a spec (what and why) before code. When code and
spec disagree, the spec wins or is amended on purpose. Plans and tasks derive from the spec.

### II. Test-Driven Development
Red-Green-Refactor. A task is not done until its tests are green. Anything that touches money
math (edge, fees, sizing, fills, P&L, scoring) needs tests with hand-computed expected values.

### III. Paper Before Real Money
No code path in this plugin places a real order or reads a real balance until a spec explicitly
admits it and the user approves that spec. The MVP is paper trading only. Authenticated trading is
designed as seams (interfaces, limits, approval gate), not behavior.

**Why**: the point of the MVP is to prove the system finds real opportunities and takes smart
risks. Real-money work before that proof is premature and risky.

### IV. Builder and Reviewer Are Different
Claude Code is the primary builder. Adversarial review is done by a model from a different
lineage (Ollama Cloud), launched by the user. The builder never approves its own work. The user
gives the go on merging PRs.

### V. Evidence Over Assertion
A claim of "done" carries a command, its real output, and the artifact it produced. Predictions,
trades, and scores must be reproducible from stored inputs.

### VI. Reproducible Inputs and Provenance
Every prediction and paper trade records the frozen input snapshot it used (forecast data,
orderbook, timestamps). Every ingested fact carries `asof` (true in the world) and `fetched_at`
(when we learned it). Missing data is recorded as missing, never invented.

### VII. Secrets and Runtime Data Stay Out of Git
Databases, caches, snapshots, and logs live under the owning Hermes profile, never in the repo.
Secrets come from the environment or the profile's credential store, never from argv, logs, or
files in the repo.

### VIII. Unattended and Simple
Scripts run unattended under Hermes cron. Prefer the Python standard library; add a dependency
(declared in `pyproject.toml`) only when a step truly needs it and say why in the plan. Degrade
gracefully: a failed upstream call produces a recorded skip, not a crash or a guess.

## Workflow
- Specs, plans, tasks live in `specs/NNN-name/` (Spec Kit). Work is built in the planning folder
  until the spec is accepted; then a new repo is created and everything is checked in.
- Short-lived feature branches; PRs into `main`; main stays green.
- Quality gate: the project's test command passes, plus the reviewer's findings are resolved.

## Governance
- Amendments extend, never replace; each records a Why. User approval adopts a change.
- Versioning: MAJOR = removal/redefinition; MINOR = new/expanded principle; PATCH = wording.

**Version**: 1.0.0 | **Ratified**: 2026-10-15 | **Last Amended**: 2026-10-15
