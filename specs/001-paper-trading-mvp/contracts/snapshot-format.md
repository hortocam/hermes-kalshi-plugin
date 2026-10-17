# Contract: Frozen Snapshot

A snapshot is an immutable JSON document (canonical form: UTF-8, sorted keys, no whitespace) identified by `sha256` of that canonical text. One snapshot per slot covers all active watches of all profiles that share the slot.

```json
{
  "schema": "hermes-kalshi.snapshot/1",
  "slot_key": "2026-10-17-midday",
  "fetched_at": "2026-10-17T16:30:04Z",
  "sources": {
    "ensemble": {"url": "https://ensemble-api.open-meteo.com/v1/ensemble", "models": ["gfs025","ecmwf_ifs025"], "unit": "fahrenheit", "fetched_at": "...", "request_hash": "..."},
    "observations": {"station": "KBOS", "source": "api.weather.gov", "fetched_at": "..."},
    "kalshi": {"base": "https://api.elections.kalshi.com/trade-api/v2", "fetched_at": "..."}
  },
  "watches": [{
    "series_ticker": "KXHIGHTBOS", "kind": "high", "cli_code": "CLIBOS", "tz": "America/New_York",
    "ensemble_hourly": {"times_local": ["..."], "members": {"gfs025:control": [..], "gfs025:m01": [..]}},
    "observations": [{"at": "...", "temp_f": 61.0, "temp_c_raw": 16}],
    "events": [{
      "event_ticker": "KXHIGHTBOS-26OCT17", "local_date": "2026-10-17", "close_time": "...",
      "markets": [{
        "ticker": "KXHIGHTBOS-26OCT17-B64.5", "strike_type": "between", "floor_strike": 64, "cap_strike": 65,
        "rules_hash": "...", "status": "active",
        "yes_bid": "0.2600", "yes_ask": "0.2800", "no_bid": "0.7200", "no_ask": "0.7400",
        "orderbook": {"yes": [["0.2600","83.35"]], "no": [["0.7200","1455.99"]]}
      }]
    }]
  }],
  "skips": [{"watch": "KXLOWTBOS", "code": "kalshi_429_budget"}]
}
```

## Rules
- Prices and sizes are kept as the strings Kalshi returned (no float conversion before hashing).
- Hourly member arrays are rounded to 0.1 F before hashing so identical forecasts hash identically.
- `skips` records watches that could not be captured; their absence never blocks other watches.
- **Slot pointer**: `<root>/plugin-data/hermes-kalshi/snapshots/slots/<slot_key>.json` containing `{"snapshot_id": ..., "path": ..., "created_by": ...}`. Created atomically (write temp file, then `os.link`/exclusive create); if it exists, the existing snapshot is used. Snapshot files live at `snapshots/by-hash/<first2>/<sha256>.json` and are never modified.
- Age gate: `finalize` refuses a snapshot older than `max_snapshot_age_min` (default 20) at decision time, recording `stale_snapshot`.
- Retention: files kept 90 days by a cleanup command; per-profile DB copies kept for the life of the DB.
