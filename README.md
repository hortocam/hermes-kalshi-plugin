# hermes-kalshi-plugin

A Hermes Agent plugin that reviews Kalshi climate markets (daily high/low temperature for NYC, Chicago, LA, Boston), builds probability predictions, and places **paper trades only** with fake bankrolls, so prediction quality can be proven before any real money is considered.

**Status:** early build of the MVP (`specs/001-paper-trading-mvp`). No authenticated Kalshi access exists or will exist in this MVP.

## Layout

- `plugin.yaml`, `__init__.py`: Hermes plugin entry
- `lib/kalshi_paper/`: all logic (stdlib-only Python 3.10+)
- `skills/`, `scripts/`, `dashboard/`, `desktop/`, `profiles/kalshi-bot/`, `config/`
- `tests/`, `tests/fixtures/`: offline tests with recorded fixtures
- `specs/001-paper-trading-mvp/`: spec, plan, tasks, contracts, evidence, spikes

## Develop

```sh
python3 -m unittest discover -s tests
```

Read `CLAUDE.md` and `.specify/memory/constitution.md` first; work follows `specs/001-paper-trading-mvp/tasks.md`.

Regenerate the Spec Kit scaffold if `.specify/` is missing:

```sh
specify init --here --integration claude --script sh --force
```
