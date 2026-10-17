"""JSON shapes of the kalshi-market-data script wrappers, replayed from recorded fixtures (no network)."""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.test_kalshi_client import Clock, FakeTransport, fixture, ok

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "kalshi-market-data" / "scripts" / "kalshi_data.py"


def load_script():
    spec = importlib.util.spec_from_file_location("kalshi_data", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kalshi_data = load_script()


def run(argv, transport):
    # Build the client from the script's own import of kalshi_paper (a different module object
    # than lib.kalshi_paper), so the script's exception handling sees the exceptions it expects.
    clock = Clock()
    client = kalshi_data.kalshi_client.KalshiClient(transport=transport, rps=1000, rng=lambda: 0.5,
                                                    clock=clock.now, sleep=clock.sleep)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = kalshi_data.main(argv, client=client)
    return code, out.getvalue(), err.getvalue(), client


class ShapeTest(unittest.TestCase):
    def test_series(self):
        code, out, _, c = run(["series", "KXHIGHNY"], FakeTransport(ok(fixture("kalshi_series_KXHIGHNY.json"))))
        body = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(set(body), {"series"})
        self.assertEqual({k: body["series"][k] for k in ("ticker", "fee_type", "fee_multiplier")},
                         {"ticker": "KXHIGHNY", "fee_type": "quadratic", "fee_multiplier": 1})
        self.assertEqual(c.calls, 1)

    def test_events_lists_compact_brackets(self):
        code, out, _, _ = run(["events", "KXHIGHNY"], FakeTransport(ok(fixture("kalshi_events_open_KXHIGHNY.json"))))
        body = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual((body["series"], body["status"]), ("KXHIGHNY", "open"))
        ev = body["events"][0]
        self.assertEqual(ev["event_ticker"], "KXHIGHNY-26OCT17")
        self.assertEqual(len(ev["markets"]), 6)
        m = ev["markets"][0]
        self.assertEqual(set(m), {"ticker", "label", "strike_type", "floor_strike", "cap_strike", "status",
                                  "yes_bid", "yes_ask", "no_bid", "no_ask", "last_price", "volume",
                                  "open_interest", "close_time"})
        self.assertEqual((m["ticker"], m["label"], m["strike_type"], m["cap_strike"], m["yes_bid"], m["yes_ask"]),
                         ("KXHIGHNY-26OCT17-T62", "61° or below", "less", 62, "0.0800", "0.0900"))

    def test_markets(self):
        ev = fixture("kalshi_events_open_KXHIGHNY.json")["events"][0]
        code, out, _, _ = run(["markets", "KXHIGHNY-26OCT17"], FakeTransport(ok({"markets": ev["markets"]})))
        body = json.loads(out)
        self.assertEqual((code, body["event_ticker"], len(body["markets"])), (0, "KXHIGHNY-26OCT17", 6))

    def test_book_shape_and_depth_limit(self):
        ob = fixture("kalshi_orderbooks_KXHIGHNY.json")
        code, out, _, _ = run(["book", "KXHIGHNY-26OCT17-T62", "--depth", "2"], FakeTransport(ok(ob)))
        body = json.loads(out)
        self.assertEqual(code, 0)
        b = body["books"][0]
        self.assertEqual(set(b), {"ticker", "yes_bids", "no_bids", "yes_asks", "no_asks", "yes_ask", "no_ask"})
        for side in ("yes_bids", "no_bids", "yes_asks", "no_asks"):
            self.assertLessEqual(len(b[side]), 2)
            for lvl in b[side]:
                self.assertEqual(set(lvl), {"price", "size"})
                self.assertIsInstance(lvl["price"], str)
        # best-first ordering: bids descending, asks ascending
        self.assertEqual(b["yes_bids"], sorted(b["yes_bids"], key=lambda l: -float(l["price"])))
        self.assertEqual(b["yes_asks"], sorted(b["yes_asks"], key=lambda l: float(l["price"])))
        self.assertEqual(b["yes_ask"], b["yes_asks"][0]["price"])

    def test_book_requests_repeated_tickers(self):
        t = FakeTransport(ok({"orderbooks": []}))
        run(["book", "A", "B", "C"], t)
        self.assertEqual(t.requests[0][0].count("tickers="), 3)

    def test_settled_reports_results(self):
        ev = fixture("kalshi_events_settled_KXHIGHNY.json")["events"][0]
        code, out, _, _ = run(["settled", "KXHIGHNY"], FakeTransport(ok({"events": [ev]})))
        body = json.loads(out)
        self.assertEqual(code, 0)
        e = body["events"][0]
        self.assertEqual(e["event_ticker"], "KXHIGHNY-26OCT16")
        self.assertEqual(set(e["markets"][0]), {"ticker", "label", "status", "result", "expiration_value"})
        by = {m["ticker"]: m for m in e["markets"]}
        self.assertEqual((by["KXHIGHNY-26OCT16-T75"]["result"], by["KXHIGHNY-26OCT16-T75"]["expiration_value"]),
                         ("yes", "72.00"))
        self.assertEqual(sum(m["result"] == "yes" for m in e["markets"]), 1)


class OverviewTest(unittest.TestCase):
    """The US1 checkpoint: one series, brackets plus books, at most 4 Kalshi calls."""

    def test_overview_uses_at_most_four_calls_and_joins_books_to_brackets(self):
        t = FakeTransport(ok(fixture("kalshi_series_KXHIGHNY.json")),
                          ok(fixture("kalshi_events_open_KXHIGHNY.json")),
                          ok(fixture("kalshi_orderbooks_KXHIGHNY.json")))
        code, out, _, c = run(["overview", "KXHIGHNY"], t)
        body = json.loads(out)
        self.assertEqual(code, 0)
        self.assertLessEqual(body["kalshi_calls"], 4)
        self.assertEqual(body["kalshi_calls"], c.calls)
        ev = body["events"][0]
        self.assertEqual(len(ev["brackets"]), 6)
        for b in ev["brackets"]:
            self.assertIn("book", b)
            self.assertIn("yes_ask", b["book"])
        self.assertEqual(body["series"]["fee_multiplier"], 1)


class FailureTest(unittest.TestCase):
    def test_rate_limit_exhaustion_exits_3_with_skip_code(self):
        t = FakeTransport((429, {}, fixture("kalshi_429.json")))
        code, out, err, _ = run(["series", "KXHIGHNY"], t)
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out), {"error": "kalshi_429_budget", "skipped": True})

    def test_http_error_exits_4(self):
        code, out, err, _ = run(["series", "NOPE"], FakeTransport((404, {}, {"error": "not found"})))
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["error"], "http_404")

    def test_usage_error_exits_2(self):
        code, _, _, _ = run([], FakeTransport(ok({})))
        self.assertEqual(code, 2)
        code, _, _, _ = run(["bogus"], FakeTransport(ok({})))
        self.assertEqual(code, 2)

    def test_series_list_is_not_a_command(self):
        code, _, _, _ = run(["list-series"], FakeTransport(ok({})))
        self.assertEqual(code, 2)


class ScriptEntryTest(unittest.TestCase):
    def test_script_runs_standalone_and_prints_help(self):
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("overview", r.stdout)


if __name__ == "__main__":
    unittest.main()
