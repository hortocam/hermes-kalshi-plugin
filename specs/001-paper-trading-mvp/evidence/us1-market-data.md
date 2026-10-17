# US1 (Public Market Data Skill) evidence

Branch `005-market-data`. Captured 2026-10-17T19:10:34Z, Python 3.14.3. HERMES_HOME was a throwaway temp dir.

## Tests (`python3 -m unittest discover -s tests`)
```
----------------------------------------------------------------------
Ran 175 tests in 0.400s

OK
test_kalshi_client         Ran 38 tests in 0.006s
test_market_data_cli       Ran 12 tests in 0.070s
test_plugin_register       Ran 5 tests in 0.001s
```

## Checkpoint: live read of one series, brackets and books, <= 4 Kalshi calls
```
$ python3 -I skills/kalshi-market-data/scripts/kalshi_data.py overview KXHIGHTBOS --depth 2   # exit 0
series KXHIGHTBOS fee_multiplier=1 kalshi_calls=3
KXHIGHTBOS-26OCT17
  KXHIGHTBOS-26OCT17-T59     58° or below  market bid/ask 0.0000/0.0100  book-derived yes_ask 0.0100 no_ask None
  KXHIGHTBOS-26OCT17-B59.5   59° to 60°    market bid/ask 0.0000/0.0100  book-derived yes_ask 0.0100 no_ask None
  KXHIGHTBOS-26OCT17-B61.5   61° to 62°    market bid/ask 0.9800/0.9900  book-derived yes_ask 0.9900 no_ask 0.0200
  KXHIGHTBOS-26OCT17-B63.5   63° to 64°    market bid/ask 0.0000/0.0100  book-derived yes_ask 0.0100 no_ask None
  KXHIGHTBOS-26OCT17-B65.5   65° to 66°    market bid/ask 0.0000/0.0100  book-derived yes_ask 0.0100 no_ask None
  KXHIGHTBOS-26OCT17-T66     67° or above  market bid/ask 0.0000/0.0100  book-derived yes_ask 0.0100 no_ask None
KXHIGHTBOS-26OCT18
  KXHIGHTBOS-26OCT18-T49     48° or below  market bid/ask 0.0100/0.0200  book-derived yes_ask 0.0200 no_ask 0.9900
  KXHIGHTBOS-26OCT18-B49.5   49° to 50°    market bid/ask 0.0100/0.0200  book-derived yes_ask 0.0200 no_ask 0.9900
  KXHIGHTBOS-26OCT18-B51.5   51° to 52°    market bid/ask 0.0600/0.0800  book-derived yes_ask 0.0800 no_ask 0.9400
  KXHIGHTBOS-26OCT18-B53.5   53° to 54°    market bid/ask 0.3200/0.3300  book-derived yes_ask 0.3300 no_ask 0.6800
  KXHIGHTBOS-26OCT18-B55.5   55° to 56°    market bid/ask 0.4400/0.4500  book-derived yes_ask 0.4500 no_ask 0.5600
  KXHIGHTBOS-26OCT18-T56     57° or above  market bid/ask 0.1300/0.1400  book-derived yes_ask 0.1400 no_ask 0.8700
```

3 Kalshi calls (series, events with nested markets, one batched orderbooks call with repeated `tickers`). The book-derived YES ask (1 - best NO bid) equals the market-level quoted ask on every bracket, which independently cross-checks the derivation.
