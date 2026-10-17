"""Capture recorded read-only responses into tests/fixtures/ (T026). Developer tool, not a test.

Keyless public endpoints only (Kalshi public API, Open-Meteo, api.weather.gov). No secrets
are involved. Paced at ~2.5 requests/s, well under the client budget. Run from the repo root:

    python3 -I tests/fixtures/capture.py

Each fixture is the raw JSON body; manifest.json records url, status, bytes, sha256, and
fetched_at so provenance travels with the data. Re-running reuses fixtures already captured; pass --refresh to re-fetch all.
"""
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "hermes-kalshi-fixture-capture (paper trading research)"}
PACE_SECONDS = 0.4

REFRESH = "--refresh" in sys.argv
manifest = json.loads((HERE / "manifest.json").read_text()) if (HERE / "manifest.json").exists() else {}


def fetch(name, url):
    """Fetch one fixture. Existing fixtures are reused unless --refresh. One retry, after a
    pause, for a 5xx; anything else stops the run."""
    path = HERE / name
    if path.exists() and not REFRESH and name in manifest:
        return json.loads(path.read_text())
    for attempt in (1, 2):
        time.sleep(PACE_SECONDS if attempt == 1 else 10)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                body, status = r.read(), r.status
            break
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt == 1:
                continue
            sys.exit("capture failed for %s: HTTP %s (%s). Stop and investigate; do not hammer." % (name, e.code, url))
    data = json.loads(body)
    (HERE / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    manifest[name] = {"url": url, "status": status, "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(),
                      "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return data


def main():
    watches = json.loads((ROOT / "config" / "watches.default.json").read_text())["watches"]
    for w in watches:
        s = w["series_ticker"]
        fetch("kalshi_series_%s.json" % s, "%s/series/%s" % (KALSHI, s))
        opened = fetch("kalshi_events_open_%s.json" % s,
                       "%s/events?series_ticker=%s&status=open&limit=2&with_nested_markets=true" % (KALSHI, s))
        fetch("kalshi_events_settled_%s.json" % s,
              "%s/events?series_ticker=%s&status=settled&limit=1&with_nested_markets=true" % (KALSHI, s))
        tickers = [m["ticker"] for e in opened["events"][:1] for m in e["markets"]]
        qs = "&".join("tickers=%s" % urllib.parse.quote(t) for t in tickers)  # repeated params, not comma-joined
        fetch("kalshi_orderbooks_%s.json" % s, "%s/markets/orderbooks?%s" % (KALSHI, qs))

    stations = {}
    for w in watches:
        stations.setdefault(w["obs_station"], (w["lat"], w["lon"]))
    order = sorted(stations)  # one Open-Meteo request, locations in this order
    lat = ",".join(str(stations[s][0]) for s in order)
    lon = ",".join(str(stations[s][1]) for s in order)
    fetch("openmeteo_ensemble_4pts.json",
          "https://ensemble-api.open-meteo.com/v1/ensemble?latitude=%s&longitude=%s&hourly=temperature_2m"
          "&models=gfs025,ecmwf_ifs025&temperature_unit=fahrenheit&forecast_days=3&timezone=auto" % (lat, lon))
    manifest["openmeteo_ensemble_4pts.json"]["locations_in_order"] = order
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    for st in order:
        fetch("nws_obs_%s.json" % st, "https://api.weather.gov/stations/%s/observations?limit=30" % st)

    # Observed 429 body from the reference tool (research.md R7). Recorded, not provoked.
    (HERE / "kalshi_429.json").write_text(json.dumps({"error": "too many requests"}) + "\n")
    manifest["kalshi_429.json"] = {"url": "(observed in reference tool; not re-triggered)", "status": 429,
                                   "note": "body only; no Retry-After header was present"}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print("captured %d fixtures" % len(manifest))


if __name__ == "__main__":
    main()
