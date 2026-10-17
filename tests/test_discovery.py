"""FR-003, FR-006: events/markets are discovered from the API (never hardcoded) for each active watch's
local today and tomorrow, with rounding-aware integer bracket sets and stable rules hashes."""
import copy
import hashlib
import json
import tempfile
import unittest
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path

from lib.kalshi_paper import bootstrap, config, discovery, kalshi_client, run_ledger, store, watches
from tests.test_kalshi_client import Clock, fixture

NOW = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)   # 12:00 EDT, Oct 17


class Routing:
    """Transport that serves recorded `events` fixtures by series_ticker; per-series overrides allowed."""

    def __init__(self, overrides=None, statuses=None):
        self.overrides = overrides or {}
        self.statuses = statuses or {}
        self.requests = []

    def __call__(self, url, headers, timeout):
        self.requests.append(url)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        series = q["series_ticker"][0]
        status = self.statuses.get(series, 200)
        if status != 200:
            return status, {}, json.dumps(fixture("kalshi_429.json")).encode()
        body = self.overrides.get(series) or fixture("kalshi_events_open_%s.json" % series)
        return 200, {}, json.dumps(body).encode()


def make_client(transport):
    clock = Clock()
    return kalshi_client.KalshiClient(transport=transport, rps=1000, rng=lambda: 0.5, max_retries=1,
                                      clock=clock.now, sleep=clock.sleep)


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.con = store.connect(Path(self._tmp.name) / "data.db")
        self.addCleanup(self.con.close)
        bootstrap.initialize(self.con, now=NOW)

    def count(self, table):
        return self.con.execute("SELECT count(*) FROM %s" % table).fetchone()[0]


class BracketRangeTest(unittest.TestCase):
    """Whole-degree sets. Hand-derived from the contract: tail `T94 greater` = 95..+inf; tail `T87 less` =
    -inf..86; band `B93.5` (93-94) = 93..94."""

    def m(self, strike_type, floor=None, cap=None, label=""):
        return {"strike_type": strike_type, "floor_strike": floor, "cap_strike": cap, "yes_sub_title": label,
                "ticker": "T"}

    def test_greater_tail(self):
        self.assertEqual(discovery.bracket_range(self.m("greater", floor=94, label="95° or above")), (95, None))

    def test_less_tail(self):
        self.assertEqual(discovery.bracket_range(self.m("less", cap=87, label="86° or below")), (None, 86))

    def test_band(self):
        self.assertEqual(discovery.bracket_range(self.m("between", floor=93, cap=94, label="93° to 94°")), (93, 94))

    def test_float_strikes_that_are_whole_numbers_are_accepted(self):
        self.assertEqual(discovery.bracket_range(self.m("between", floor=93.0, cap=94.0, label="93° to 94°")), (93, 94))

    def test_fractional_strikes_rejected(self):
        with self.assertRaises(discovery.DiscoveryError):
            discovery.bracket_range(self.m("between", floor=93.5, cap=94.5, label="93° to 94°"))

    def test_label_must_agree_with_strikes(self):
        with self.assertRaises(discovery.BracketMismatch):
            discovery.bracket_range(self.m("greater", floor=94, label="94° or above"))  # label says >=94, strike says >=95

    def test_unknown_strike_type_rejected(self):
        with self.assertRaises(discovery.DiscoveryError):
            discovery.bracket_range(self.m("structured", floor=1, cap=2))

    def test_label_parsing(self):
        self.assertEqual(discovery.label_range("61° or below"), (None, 61))
        self.assertEqual(discovery.label_range("70° or above"), (70, None))
        self.assertEqual(discovery.label_range("62° to 63°"), (62, 63))
        self.assertEqual(discovery.label_range("-3° or below"), (None, -3))
        self.assertIsNone(discovery.label_range("Will it rain?"))

    def test_partition_checks(self):
        discovery.check_partition([(None, 61), (62, 63), (64, 65), (66, 67), (68, 69), (70, None)])
        for bad in ([(None, 61), (63, 64), (65, None)],            # gap at 62
                    [(None, 61), (61, 63), (64, None)],            # overlap at 61
                    [(62, 63), (64, None)],                         # no lower tail
                    [(None, 61), (62, 63)],                         # no upper tail
                    []):
            with self.assertRaises(discovery.BracketPartitionInvalid, msg=str(bad)):
                discovery.check_partition(bad)

    def test_recorded_ny_event_ranges_by_hand(self):
        markets = fixture("kalshi_events_open_KXHIGHNY.json")["events"][0]["markets"]
        got = {m["ticker"].split("-")[-1]: discovery.bracket_range(m) for m in markets}
        self.assertEqual(got, {"T62": (None, 61), "B62.5": (62, 63), "B64.5": (64, 65),
                               "B66.5": (66, 67), "B68.5": (68, 69), "T69": (70, None)})


class EventDateTest(unittest.TestCase):
    def test_parsed_from_the_ticker_suffix_for_any_series_naming(self):
        self.assertEqual(discovery.event_date("KXHIGHNY-26OCT17"), date(2026, 10, 17))
        self.assertEqual(discovery.event_date("KXHIGHTBOS-26OCT18"), date(2026, 10, 18))
        self.assertEqual(discovery.event_date("KXLOWTNYC-26JAN05"), date(2026, 1, 5))
        self.assertEqual(discovery.event_date("KXLOWTCHI-27FEB28"), date(2027, 2, 28))

    def test_bad_tickers_rejected(self):
        for bad in ("KXHIGHNY", "KXHIGHNY-26XXX17", "KXHIGHNY-26OCT32", "26OCT17"):
            with self.assertRaises(discovery.DiscoveryError, msg=bad):
                discovery.event_date(bad)


class RulesHashTest(unittest.TestCase):
    def test_documented_construction_and_stability(self):
        m = fixture("kalshi_events_open_KXHIGHNY.json")["events"][0]["markets"][0]
        text = (m["rules_primary"].strip() + "\n\n" + m["rules_secondary"].strip()).strip()
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(discovery.rules_text(m), text)
        self.assertEqual(discovery.rules_hash(m), expected)
        self.assertEqual(discovery.rules_hash(copy.deepcopy(m)), expected)

    def test_changes_when_rules_change(self):
        m = fixture("kalshi_events_open_KXHIGHNY.json")["events"][0]["markets"][0]
        other = {**m, "rules_primary": m["rules_primary"].replace("Weather Company", "Another Source")}
        self.assertNotEqual(discovery.rules_hash(m), discovery.rules_hash(other))

    def test_missing_secondary_is_fine(self):
        self.assertEqual(discovery.rules_text({"rules_primary": "p"}), "p")


class DiscoveryRunTest(Case):
    def test_all_eight_watches_discovered_against_fixtures(self):
        client = make_client(Routing())
        res = discovery.discover_all(self.con, client, NOW)
        want_events = sum(len(fixture("kalshi_events_open_%s.json" % w["series_ticker"])["events"])
                          for w in config.load_watches())
        want_markets = sum(len(e["markets"]) for w in config.load_watches()
                           for e in fixture("kalshi_events_open_%s.json" % w["series_ticker"])["events"])
        self.assertEqual((want_events, want_markets), (16, 96))
        self.assertEqual((self.count("events"), self.count("markets")), (16, 96))
        self.assertEqual((res["watches"], res["events_new"], res["markets_new"], res["partial"]), (8, 16, 96, False))
        self.assertEqual(res["skipped"], [])

    def test_stored_rows_carry_ranges_hashes_and_rules(self):
        discovery.discover_all(self.con, make_client(Routing()), NOW)
        rows = {r["ticker"]: r for r in self.con.execute("SELECT * FROM markets")}
        t62, t69 = rows["KXHIGHNY-26OCT17-T62"], rows["KXHIGHNY-26OCT17-T69"]
        self.assertEqual((t62["strike_type"], t62["int_low"], t62["int_high"], t62["cap_strike"]), ("less", None, 61, 62.0))
        self.assertEqual((t69["strike_type"], t69["int_low"], t69["int_high"], t69["floor_strike"]), ("greater", 70, None, 69.0))
        self.assertEqual(len(t62["rules_hash"]), 64)
        self.assertIn("CLINYC", t62["rules_text"])
        self.assertEqual(t62["status"], "active")
        ev = self.con.execute("SELECT * FROM events WHERE ticker='KXHIGHNY-26OCT17'").fetchone()
        self.assertEqual((ev["local_date"], ev["status"], ev["first_seen_at"]), ("2026-10-17", "open", "2026-10-17T16:00:00Z"))
        self.assertTrue(ev["close_time"].startswith("2026-10-18T05:00"))

    def test_second_run_adds_nothing(self):
        client = make_client(Routing())
        discovery.discover_all(self.con, client, NOW)
        again = discovery.discover_all(self.con, client, NOW)
        self.assertEqual((again["events_new"], again["markets_new"], again["rules_changed"]), (0, 0, 0))
        self.assertEqual((self.count("events"), self.count("markets")), (16, 96))

    def test_a_new_daily_event_is_picked_up_without_enrollment(self):
        discovery.discover_all(self.con, make_client(Routing()), NOW)
        # Next day: the API now lists Oct 18 and a brand-new Oct 19 event.
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        new = copy.deepcopy(body["events"][1])
        new["event_ticker"] = "KXHIGHNY-26OCT19"
        for m in new["markets"]:
            m["event_ticker"] = "KXHIGHNY-26OCT19"
            m["ticker"] = m["ticker"].replace("26OCT18", "26OCT19")
        body["events"].append(new)
        nxt = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
        watch = self.con.execute("SELECT * FROM watches WHERE series_ticker='KXHIGHNY'").fetchone()
        res = discovery.discover_watch(self.con, make_client(Routing({"KXHIGHNY": body})), watch, nxt)
        self.assertEqual((res["events_new"], res["markets_new"]), (1, 6))
        self.assertIsNotNone(self.con.execute("SELECT 1 FROM events WHERE ticker='KXHIGHNY-26OCT19'").fetchone())

    def test_only_local_today_and_tomorrow_are_discovered(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        far = copy.deepcopy(body["events"][0])
        far["event_ticker"] = "KXHIGHNY-26OCT25"
        for m in far["markets"]:
            m["event_ticker"], m["ticker"] = "KXHIGHNY-26OCT25", m["ticker"].replace("26OCT17", "26OCT25")
        body["events"].append(far)
        watch = self.con.execute("SELECT * FROM watches WHERE series_ticker='KXHIGHNY'").fetchone()
        discovery.discover_watch(self.con, make_client(Routing({"KXHIGHNY": body})), watch, NOW)
        tickers = {r[0] for r in self.con.execute("SELECT ticker FROM events")}
        self.assertEqual(tickers, {"KXHIGHNY-26OCT17", "KXHIGHNY-26OCT18"})

    def test_market_day_uses_standard_time_after_midnight_during_dst(self):
        # 00:30 EDT on Oct 18 is still market day Oct 17 (23:30 EST): today=Oct 17, tomorrow=Oct 18.
        late = datetime(2026, 10, 18, 4, 30, tzinfo=timezone.utc)
        watch = self.con.execute("SELECT * FROM watches WHERE series_ticker='KXHIGHNY'").fetchone()
        res = discovery.discover_watch(self.con, make_client(Routing()), watch, late)
        self.assertEqual(res["events_new"], 2)
        # an hour later (01:30 EDT = 00:30 EST Oct 18) today is Oct 18 and Oct 17 is no longer wanted
        later = datetime(2026, 10, 18, 5, 30, tzinfo=timezone.utc)
        self.assertEqual(discovery.wanted_dates(later, "America/New_York"),
                         (date(2026, 10, 18), date(2026, 10, 19)))

    def test_paused_watch_is_not_discovered(self):
        watches.pause(self.con, "KXHIGHNY", now=NOW)
        transport = Routing()
        res = discovery.discover_all(self.con, make_client(transport), NOW)
        self.assertEqual(res["watches"], 7)
        self.assertFalse(any("KXHIGHNY&" in u or u.endswith("KXHIGHNY") for u in transport.requests))
        self.assertEqual(self.count("events"), 14)

    def test_changed_rules_text_is_recorded(self):
        watch = self.con.execute("SELECT * FROM watches WHERE series_ticker='KXHIGHNY'").fetchone()
        discovery.discover_watch(self.con, make_client(Routing()), watch, NOW)
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        body["events"][0]["markets"][0]["rules_primary"] += " (amended)"
        res = discovery.discover_watch(self.con, make_client(Routing({"KXHIGHNY": body})), watch, NOW)
        self.assertEqual(res["rules_changed"], 1)
        row = self.con.execute("SELECT rules_text FROM markets WHERE ticker='KXHIGHNY-26OCT17-T62'").fetchone()
        self.assertIn("(amended)", row[0])


class BadDataTest(Case):
    def watch(self):
        return self.con.execute("SELECT * FROM watches WHERE series_ticker='KXHIGHNY'").fetchone()

    def test_gap_in_brackets_skips_that_event_only(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        del body["events"][0]["markets"][2]          # drops 64-65: a gap
        res = discovery.discover_watch(self.con, make_client(Routing({"KXHIGHNY": body})), self.watch(), NOW)
        self.assertEqual([s["code"] for s in res["skipped"]], ["bracket_partition_invalid"])
        self.assertEqual(res["skipped"][0]["event"], "KXHIGHNY-26OCT17")
        self.assertEqual(res["events_new"], 1)       # the other day is fine
        self.assertEqual(self.count("events"), 1)
        self.assertEqual(self.count("markets"), 6)   # nothing partial stored for the bad event

    def test_label_disagreeing_with_strikes_skips_the_event(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        body["events"][0]["markets"][0]["yes_sub_title"] = "62° or below"
        res = discovery.discover_watch(self.con, make_client(Routing({"KXHIGHNY": body})), self.watch(), NOW)
        self.assertEqual(res["skipped"][0]["code"], "bracket_label_mismatch")
        self.assertEqual(self.count("events"), 1)

    def test_non_exclusive_events_are_skipped(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        body["events"][0]["mutually_exclusive"] = False
        res = discovery.discover_watch(self.con, make_client(Routing({"KXHIGHNY": body})), self.watch(), NOW)
        self.assertEqual(res["skipped"][0]["code"], "event_not_exclusive")

    def test_rate_limit_is_recorded_per_watch_and_the_rest_continue(self):
        ledger = run_ledger.begin_run(self.con, "kalshi-bot", "2026-10-17-midday", "snapshot", now=NOW)
        res = discovery.discover_all(self.con, make_client(Routing(statuses={"KXHIGHNY": 429})), NOW,
                                     run_id=ledger.run_id)
        self.assertTrue(res["partial"])
        self.assertEqual(res["watches"], 7)
        self.assertEqual(self.count("events"), 14)
        ev = run_ledger.events(self.con, ledger.run_id)
        self.assertEqual([(e["level"], e["code"]) for e in ev], [("skip", "kalshi_429_budget")])
        ny = self.con.execute("SELECT id FROM watches WHERE series_ticker='KXHIGHNY'").fetchone()[0]
        self.assertEqual(ev[0]["watch_id"], ny)

    def test_bracket_skips_are_recorded_in_the_ledger(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        del body["events"][0]["markets"][2]
        ledger = run_ledger.begin_run(self.con, "kalshi-bot", "2026-10-17-midday", "snapshot", now=NOW)
        res = discovery.discover_all(self.con, make_client(Routing({"KXHIGHNY": body})), NOW, run_id=ledger.run_id)
        self.assertTrue(res["partial"])
        codes = [e["code"] for e in run_ledger.events(self.con, ledger.run_id)]
        self.assertEqual(codes, ["bracket_partition_invalid"])

    def test_call_budget_exhaustion_stops_the_loop(self):
        client = kalshi_client.KalshiClient(transport=Routing(), rps=1000, budget=kalshi_client.CallBudget(3),
                                            clock=Clock().now, sleep=Clock().sleep)
        res = discovery.discover_all(self.con, client, NOW)
        self.assertTrue(res["partial"])
        self.assertEqual(res["watches"], 3)
        self.assertEqual(res["skipped"][-1]["code"], "kalshi_call_budget")


if __name__ == "__main__":
    unittest.main()
