import json
import os
import tempfile
import unittest
from pathlib import Path

from lib.kalshi_paper import config
from tests.helpers import temp_hermes_home


class HomeResolutionTest(unittest.TestCase):
    def test_hermes_home_from_env(self):
        with temp_hermes_home() as (root, home):
            self.assertEqual(config.hermes_home(), home)

    def test_default_when_unset(self):
        old = os.environ.pop("HERMES_HOME", None)
        try:
            self.assertEqual(config.hermes_home(), Path.home() / ".hermes")
        finally:
            if old is not None:
                os.environ["HERMES_HOME"] = old

    def test_profile_home_derives_root(self):
        with temp_hermes_home("kalshi-bot") as (root, home):
            self.assertEqual(config.root_home(), root)
            self.assertEqual(config.profile_name(), "kalshi-bot")

    def test_root_home_is_its_own_root(self):
        with temp_hermes_home() as (root, home):
            self.assertEqual(config.root_home(), root)
            self.assertEqual(config.profile_name(), "default")

    def test_only_a_profiles_parent_counts_as_root_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            odd = Path(tmp) / "something" / "kalshi-bot"
            odd.mkdir(parents=True)
            self.assertEqual(config.root_home(odd), odd)


class PathsTest(unittest.TestCase):
    def test_db_path_is_under_profile_plugin_data(self):
        with temp_hermes_home("kalshi-bot") as (root, home):
            self.assertEqual(config.db_path(), home / "plugin-data" / "hermes-kalshi" / "data.db")

    def test_profiles_get_separate_databases(self):
        with temp_hermes_home("kalshi-bot") as (root, home):
            a = config.db_path()
            b = config.db_path(root / "profiles" / "kalshi-bot-a")
            self.assertNotEqual(a, b)

    def test_snapshot_dir_is_shared_under_root(self):
        with temp_hermes_home("kalshi-bot") as (root, home):
            expected = root / "plugin-data" / "hermes-kalshi" / "snapshots"
            self.assertEqual(config.shared_snapshot_dir(), expected)
            other = root / "profiles" / "kalshi-bot-b"
            self.assertEqual(config.shared_snapshot_dir(other), expected)

    def test_db_override_wins(self):
        with temp_hermes_home("kalshi-bot"):
            self.assertEqual(config.resolve_db("/tmp/x/test.db"), Path("/tmp/x/test.db"))
            self.assertEqual(config.resolve_db(None), config.db_path())

    def test_plugin_root_contains_plugin_yaml(self):
        self.assertTrue((config.plugin_root() / "plugin.yaml").is_file())


class WatchesTest(unittest.TestCase):
    def test_default_file_has_eight_watches(self):
        watches = config.load_watches()
        self.assertEqual(len(watches), 8)
        self.assertEqual({w["kind"] for w in watches}, {"high", "low"})
        self.assertEqual(len({w["series_ticker"] for w in watches}), 8)
        self.assertEqual(
            {w["series_ticker"] for w in watches},
            {"KXHIGHNY", "KXHIGHCHI", "KXHIGHLAX", "KXHIGHTBOS",
             "KXLOWTNYC", "KXLOWTCHI", "KXLOWTLAX", "KXLOWTBOS"})

    def test_chicago_settles_on_midway(self):
        chi = {w["series_ticker"]: w for w in config.load_watches()}["KXHIGHCHI"]
        self.assertEqual((chi["cli_code"], chi["obs_station"]), ("CLIMDW", "KMDW"))

    def test_high_and_low_share_a_station(self):
        by = {w["series_ticker"]: w for w in config.load_watches()}
        for hi, lo in (("KXHIGHNY", "KXLOWTNYC"), ("KXHIGHCHI", "KXLOWTCHI"),
                       ("KXHIGHLAX", "KXLOWTLAX"), ("KXHIGHTBOS", "KXLOWTBOS")):
            for k in ("cli_code", "obs_station", "lat", "lon", "tz"):
                self.assertEqual(by[hi][k], by[lo][k])

    def _write(self, tmp, payload):
        p = Path(tmp) / "w.json"
        p.write_text(json.dumps(payload))
        return p

    def test_missing_field_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = config.load_watches()[0]
            bad = {k: v for k, v in good.items() if k != "tz"}
            with self.assertRaises(config.ConfigError):
                config.load_watches(self._write(tmp, {"watches": [bad]}))

    def test_bad_kind_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = config.load_watches()[0]
            with self.assertRaises(config.ConfigError):
                config.load_watches(self._write(tmp, {"watches": [{**good, "kind": "mid"}]}))
            with self.assertRaises(config.ConfigError):
                config.load_watches(self._write(tmp, {"watches": [good, good]}))

    def test_unknown_timezone_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = config.load_watches()[0]
            with self.assertRaises(config.ConfigError):
                config.load_watches(self._write(tmp, {"watches": [{**good, "tz": "Mars/Olympus"}]}))


if __name__ == "__main__":
    unittest.main()
