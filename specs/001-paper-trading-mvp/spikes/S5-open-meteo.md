# S5: Open-Meteo real call weight (T010)

Run 2026-10-17 from the builder's Mac with `spikes/s5_open_meteo.py` (stdlib, no key). One request for all four stations, `models=gfs025,ecmwf_ifs025`, `hourly=temperature_2m`, `temperature_unit=fahrenheit`, `forecast_days=2`, `timezone=auto`; three repeats 2 s apart.

| Call | Status | Bytes | Latency |
|---|---|---|---|
| 1 | 200 | 115,103 | 0.84 s |
| 2 | 200 | 115,102 | 0.79 s |
| 3 | 200 | 115,103 | 0.79 s |

- Response is a JSON list, one object per location in request order; each has `timezone` (`timezone=auto` gave America/New_York, Chicago, Los_Angeles, New_York) and 48 hourly rows, local time, `2026-10-17T00:00` to `2026-10-18T23:00`.
- Members per location: GFS 31 (`temperature_2m_ncep_gefs025` control + `member01..30`), ECMWF IFS 51 (control + `member01..50_ecmwf_ifs025_ensemble`): matches research.md R5.
- **No rate-limit or Retry-After headers**; only `Content-Type`. No throttling in three calls. The "no throttling over 3 days" criterion in plan.md remains to be observed once slots run.
- Cost: about 115 KB and under 1 s per slot request for all 4 cities, so 3 slots/day is trivial.

## Finding that affects the model (not in plan.md yet)
The market day is the local standard-time day: during DST it runs 1:00 AM to 12:59 AM next day, so it needs the hour **00:00 of the following calendar day**. `forecast_days=2` returned data only through 23:00 of day 2. For an event dated *tomorrow*, evaluated today, the window ends at 00:59 two calendar days out, so use `forecast_days=3` (cheap) to cover it. Carry into T-tasks for weather.py/model.py (US3) and the snapshot contract.

Status: **PASS** for T010 (call weight and headers recorded).
