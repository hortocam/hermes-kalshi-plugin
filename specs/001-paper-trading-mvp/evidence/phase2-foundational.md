# Phase 2 (Foundational) evidence

Branch `004-foundational`. Captured 2026-10-17T18:50:24Z on the builder's Mac, Python 3.14.3. HERMES_HOME pointed at a throwaway temp dir for every command below.

## Test suite (`python3 -m unittest discover -s tests`)
```
----------------------------------------------------------------------
Ran 120 tests in 0.345s

OK
```

Tests per module:
```
test_money         Ran 16 tests in 0.000s
test_timeutil      Ran 15 tests in 0.001s
test_store         Ran 30 tests in 0.071s
test_config        Ran 16 tests in 0.006s
test_run_ledger    Ran 16 tests in 0.110s
test_cli_init      Ran 19 tests in 0.147s
test_fixtures      Ran 6 tests in 0.007s
test_helpers       Ran 2 tests in 0.001s
```

## Checkpoint: `kalshi-paper init` creates 8 watches and 16 accounts; second run changes nothing
```
$ python3 -I lib/kalshi_paper/cli.py init
init: created 8 watches, 16 accounts, 1 strategy version (db: $HERMES_HOME/plugin-data/hermes-kalshi/data.db)
(exit 0; also asserted in tests/test_cli_init.py)
$ python3 -I lib/kalshi_paper/cli.py init --json    # second run
{"created": {"accounts": 0, "strategy_versions": 0, "watches": 0}, "db": "$HERMES_HOME/plugin-data/hermes-kalshi/data.db", "schema_version": 1, "totals": {"accounts": 16, "strategy_versions": 1, "watches": 8}}

$ sqlite3 $DB "select count(*) from watches; select scale, starting_cash_micro, count(*) from accounts group by 1,2; select count(*) from strategy_versions; pragma journal_mode;"
8
real|100000000|8
test|1000000000|8
1
wal
```

Starting cash: 100000000 micro = $100.00 (real), 1000000000 micro = $1,000.00 (test), one of each per watch.

## Fixtures (T026)
```
39 JSON files, 1.2M total; provenance in tests/fixtures/manifest.json
```
