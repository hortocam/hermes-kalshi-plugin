---
name: kalshi-ops
description: Operate the Kalshi paper-trading watches from chat or the CLI: list, enable, pause or disable a watch, and understand what each state means. Paper trading only.
---

# kalshi-ops

Operate the paper-trading watches. A **watch** is one Kalshi climate series (for example NYC high, `KXHIGHNY`) in test mode. Each watch has two independent fake bankrolls (`real` scale, default $100.00; `test` scale, default $1,000.00). Nothing here touches real money, and there is no way to place a real order.

## Watches (chat)

```
/kalshi-watch list
/kalshi-watch enable KXHIGHTBOS
/kalshi-watch pause KXHIGHTBOS
/kalshi-watch disable KXHIGHTBOS
```

The same actions exist on the CLI (`kalshi-paper watch list|enable|pause|disable <series>`, add `--json` for machine output). Both are idempotent: repeating a command says "no change".

| State | Evaluated each slot | Open positions |
|---|---|---|
| `active` | yes | settle normally |
| `paused` | no | **still settle** |
| `disabled` | no | **still settle** |

Series: highs `KXHIGHNY, KXHIGHCHI, KXHIGHLAX, KXHIGHTBOS`; lows `KXLOWTNYC, KXLOWTCHI, KXLOWTLAX, KXLOWTBOS`. Chicago settles on Midway (`CLIMDW`).

## Notes

- New daily events and their brackets are discovered automatically for each active watch (the station's market today and tomorrow); nothing needs enrolling by hand.
- `enable` on a missing watch recreates it with both accounts. Bankroll overrides (`--real-dollars`, `--test-dollars`) apply only to accounts that do not exist yet; existing accounts are never rewritten.
- Thresholds, caps and model parameters are **not** changed from here. They change only through a reviewed proposal that creates a new strategy version.
- If a command says the database is missing, run `kalshi-paper init` for this profile first.

## Verify

`python3 -m unittest tests.test_watches tests.test_cli_watch tests.test_plugin_register` (offline).
