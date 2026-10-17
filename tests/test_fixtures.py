"""Guards the recorded fixtures: complete, parseable, and shaped as the later tests expect."""
import json
import unittest
from pathlib import Path

from lib.kalshi_paper import config

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


class FixtureSetTest(unittest.TestCase):
    def test_manifest_matches_files(self):
        manifest = load("manifest.json")
        on_disk = {p.name for p in FIX.glob("*.json")} - {"manifest.json"}
        self.assertEqual(set(manifest), on_disk)
        for name, meta in manifest.items():
            if meta["status"] == 200:
                self.assertIn("fetched_at", meta, name)

    def test_every_watch_has_its_kalshi_fixtures(self):
        for w in config.load_watches():
            s = w["series_ticker"]
            series = load("kalshi_series_%s.json" % s)["series"]
            self.assertEqual((series["ticker"], series["fee_type"], series["fee_multiplier"]), (s, "quadratic", 1))
            self.assertTrue(load("kalshi_events_open_%s.json" % s)["events"], s)
            self.assertEqual(len(load("kalshi_orderbooks_%s.json" % s)["orderbooks"]),
                             len(load("kalshi_events_open_%s.json" % s)["events"][0]["markets"]))

    def test_settled_day_is_finalized_with_a_result(self):
        for w in config.load_watches():
            event = load("kalshi_events_settled_%s.json" % w["series_ticker"])["events"][0]
            for m in event["markets"]:
                self.assertEqual(m["status"], "finalized", m["ticker"])
                self.assertIn(m["result"], ("yes", "no"), m["ticker"])

    def test_ensemble_has_four_locations_with_31_and_51_members(self):
        data = load("openmeteo_ensemble_4pts.json")
        order = load("manifest.json")["openmeteo_ensemble_4pts.json"]["locations_in_order"]
        self.assertEqual(len(data), 4)
        self.assertEqual(sorted(order), ["KBOS", "KLAX", "KMDW", "KNYC"])
        for loc in data:
            cols = [k for k in loc["hourly"] if k.startswith("temperature_2m")]
            self.assertEqual(sum("ncep_gefs025" in c for c in cols), 31)
            self.assertEqual(sum("ecmwf_ifs025" in c for c in cols), 51)
            self.assertEqual(len(loc["hourly"]["time"]), 72)  # forecast_days=3

    def test_observations_for_each_station(self):
        for st in ("KBOS", "KLAX", "KMDW", "KNYC"):
            self.assertTrue(load("nws_obs_%s.json" % st)["features"], st)

    def test_429_body(self):
        self.assertEqual(load("kalshi_429.json"), {"error": "too many requests"})


if __name__ == "__main__":
    unittest.main()
