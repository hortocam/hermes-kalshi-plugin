# US2 (Watch a Series in Test Mode) evidence

Branch `006-watch-discovery` (stacked on `005-market-data`, PR #5). Captured 2026-10-17T19:42:42Z, Python 3.14.3. HERMES_HOME was a throwaway temp dir.

## Tests (`python3 -m unittest discover -s tests`)
```
----------------------------------------------------------------------
Ran 234 tests in 0.615s

OK
test_watches           Ran 15 tests in 0.044s
test_discovery         Ran 29 tests in 0.103s
test_cli_watch         Ran 9 tests in 0.061s
test_plugin_register   Ran 11 tests in 0.023s
```

## Watch CLI (acceptance 1 and 3)
```
init: created 8 watches, 16 accounts, 1 strategy version (db: $HERMES_HOME/...)
$ kalshi-paper watch pause KXHIGHTBOS
KXHIGHTBOS: paused
$ kalshi-paper watch pause KXHIGHTBOS   # repeat
KXHIGHTBOS: already paused, no change
$ kalshi-paper watch list
KXLOWTBOS    low   Boston         active   real $100.00  test $1000.00
KXLOWTCHI    low   Chicago        active   real $100.00  test $1000.00
KXLOWTLAX    low   Los Angeles    active   real $100.00  test $1000.00
KXLOWTNYC    low   New York City  active   real $100.00  test $1000.00
KXHIGHCHI    high  Chicago        active   real $100.00  test $1000.00
KXHIGHLAX    high  Los Angeles    active   real $100.00  test $1000.00
KXHIGHNY     high  New York City  active   real $100.00  test $1000.00
KXHIGHTBOS   high  Boston         paused   real $100.00  test $1000.00
$ kalshi-paper watch enable KXHIGHTBOS
KXHIGHTBOS: active
$ kalshi-paper watch pause KXNOPE   # unknown series
watch: unknown watch 'KXNOPE' (enable it first if it is a supported series)
exit=2
```

## Checkpoint: 8 watches discovered

Against recorded fixtures (`tests.test_discovery.DiscoveryRunTest.test_all_eight_watches_discovered_against_fixtures`): 8 watches, 16 events, 96 markets, no skips. Live, read-only, public API, 8 Kalshi calls:
```
discover_all: {'watches': 8, 'events_new': 16, 'markets_new': 96, 'rules_changed': 0, 'partial': False} skipped: [] kalshi_calls: 8
  KXHIGHCHI   events=2 markets=12 dates=2026-10-17,2026-10-18
  KXHIGHLAX   events=2 markets=12 dates=2026-10-17,2026-10-18
  KXHIGHNY    events=2 markets=12 dates=2026-10-17,2026-10-18
  KXHIGHTBOS  events=2 markets=12 dates=2026-10-17,2026-10-18
  KXLOWTBOS   events=2 markets=12 dates=2026-10-17,2026-10-18
  KXLOWTCHI   events=2 markets=12 dates=2026-10-17,2026-10-18
  KXLOWTLAX   events=2 markets=12 dates=2026-10-17,2026-10-18
  KXLOWTNYC   events=2 markets=12 dates=2026-10-17,2026-10-18
KXHIGHCHI whole-degree sets (int_low, int_high), Oct 17:
  KXHIGHCHI-26OCT17-T53      -inf .. 52
  KXHIGHCHI-26OCT17-B53.5    53 .. 54
  KXHIGHCHI-26OCT17-B55.5    55 .. 56
  KXHIGHCHI-26OCT17-B57.5    57 .. 58
  KXHIGHCHI-26OCT17-B59.5    59 .. 60
  KXHIGHCHI-26OCT17-T60      61 .. +inf
```
