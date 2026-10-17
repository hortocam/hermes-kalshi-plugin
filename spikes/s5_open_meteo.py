"""S5 (throwaway): one Open-Meteo ensemble request for the four stations, 3 repeats.
Usage: python3 spikes/s5_open_meteo.py   (network, read-only, no secrets)"""
import json
import time
import urllib.request

STATIONS = {"NYC": (40.78333, -73.96667), "CHI": (41.78417, -87.75528),
            "LAX": (33.93806, -118.38889), "BOS": (42.36056, -71.01056)}
URL = ("https://ensemble-api.open-meteo.com/v1/ensemble?latitude=%s&longitude=%s"
       "&hourly=temperature_2m&models=gfs025,ecmwf_ifs025&temperature_unit=fahrenheit"
       "&forecast_days=2&timezone=auto")


def once():
    lats = ",".join(str(v[0]) for v in STATIONS.values())
    lons = ",".join(str(v[1]) for v in STATIONS.values())
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(URL % (lats, lons), headers={"User-Agent": "hermes-kalshi-spike"})) as r:
        body = r.read()
        headers = dict(r.headers)
        status = r.status
    return status, headers, body, time.time() - t


for i in range(3):
    status, headers, body, secs = once()
    data = json.loads(body)
    locs = data if isinstance(data, list) else [data]
    summary = []
    for name, loc in zip(STATIONS, locs):
        cols = [k for k in loc["hourly"] if k.startswith("temperature_2m")]
        gfs = [k for k in cols if "gefs" in k or "ncep" in k]
        ecm = [k for k in cols if "ecmwf" in k]
        summary.append((name, loc.get("timezone"), len(loc["hourly"]["time"]), len(gfs), len(ecm)))
    print("call", i + 1, "status", status, "bytes", len(body), "secs %.2f" % secs)
    print("  locations:", summary)
    print("  headers:", {k: v for k, v in headers.items() if k.lower() in ("content-encoding", "content-type", "retry-after") or "ratelimit" in k.lower() or "x-" in k.lower()})
    if i == 0:
        print("  sample columns:", [k for k in locs[0]["hourly"]][:3], "...", [k for k in locs[0]["hourly"]][-2:])
        print("  first/last time:", locs[0]["hourly"]["time"][0], locs[0]["hourly"]["time"][-1])
    time.sleep(2)
