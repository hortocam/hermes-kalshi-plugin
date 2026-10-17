"""Keyless Kalshi client (FR-001, FR-002). No network: a fake transport replays recorded fixtures."""
import json
import unittest
import urllib.error
import urllib.parse
from decimal import Decimal
from pathlib import Path

from lib.kalshi_paper import kalshi_client as kc
from lib.kalshi_paper import orderbook

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIX / name).read_text())


class FakeTransport:
    """Replays queued (status, headers, body) tuples (or raises queued exceptions); records requests."""

    def __init__(self, *responses):
        self.queue = list(responses)
        self.requests = []

    def __call__(self, url, headers, timeout):
        self.requests.append((url, dict(headers)))
        item = self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]
        if isinstance(item, Exception):
            raise item
        status, hdrs, body = item
        return status, hdrs, json.dumps(body).encode() if not isinstance(body, bytes) else body


def ok(body):
    return (200, {}, body)


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def make_client(transport, *, rps=1000, budget=None, rng=lambda: 0.5, max_retries=3, clock=None):
    clock = clock or Clock()
    c = kc.KalshiClient(transport=transport, rps=rps, budget=budget, rng=rng, max_retries=max_retries,
                        clock=clock.now, sleep=clock.sleep)
    return c, clock


def query(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


class OrderbookBatchTest(unittest.TestCase):
    def test_tickers_param_is_repeated_not_comma_joined(self):
        t = FakeTransport(ok({"orderbooks": []}))
        c, _ = make_client(t)
        c.orderbooks(["KXHIGHNY-26OCT17-T62", "KXHIGHNY-26OCT17-B62.5", "KXHIGHNY-26OCT17-T69"])
        url = t.requests[0][0]
        self.assertEqual(urllib.parse.urlsplit(url).path, "/trade-api/v2/markets/orderbooks")
        self.assertEqual(query(url)["tickers"],
                         ["KXHIGHNY-26OCT17-T62", "KXHIGHNY-26OCT17-B62.5", "KXHIGHNY-26OCT17-T69"])
        self.assertNotIn("%2C", url)
        self.assertNotIn(",", urllib.parse.urlsplit(url).query)

    def test_large_batches_are_chunked(self):
        t = FakeTransport(ok({"orderbooks": []}))
        c, _ = make_client(t)
        c.orderbooks(["T%d" % i for i in range(kc.ORDERBOOK_CHUNK + 1)])
        self.assertEqual(len(t.requests), 2)
        self.assertEqual(len(query(t.requests[0][0])["tickers"]), kc.ORDERBOOK_CHUNK)

    def test_recorded_fixture_parses_to_books_by_ticker(self):
        body = fixture("kalshi_orderbooks_KXHIGHNY.json")
        c, _ = make_client(FakeTransport(ok(body)))
        books = c.orderbooks([b["ticker"] for b in body["orderbooks"]])
        self.assertEqual(len(books), 6)
        self.assertIn("KXHIGHNY-26OCT17-T62", books)

    def test_asks_derived_from_opposite_best_bid_on_recorded_book(self):
        body = fixture("kalshi_orderbooks_KXHIGHNY.json")
        raw = next(b for b in body["orderbooks"] if b["ticker"] == "KXHIGHNY-26OCT17-T62")["orderbook_fp"]
        best_no = max(Decimal(p) for p, _ in raw["no_dollars"])
        best_yes = max(Decimal(p) for p, _ in raw["yes_dollars"])
        c, _ = make_client(FakeTransport(ok(body)))
        book = c.orderbooks(["KXHIGHNY-26OCT17-T62"])["KXHIGHNY-26OCT17-T62"]
        self.assertEqual(Decimal(book.yes_ask_micro) / 1_000_000, 1 - best_no)
        self.assertEqual(Decimal(book.no_ask_micro) / 1_000_000, 1 - best_yes)

    def test_requested_ticker_missing_from_response_is_absent_not_empty(self):
        c, _ = make_client(FakeTransport(ok({"orderbooks": []})))
        self.assertEqual(c.orderbooks(["NOPE"]), {})


class BookDerivationTest(unittest.TestCase):
    """Hand-computed (quickstart A2): NO bids 0.72x40 and 0.71x100 give YES asks 0.28x40 and 0.29x100."""

    def raw(self, yes, no):
        return {"orderbook_fp": {"yes_dollars": yes, "no_dollars": no}}

    def test_yes_asks_come_from_no_bids(self):
        b = orderbook.parse_book("T", self.raw([["0.2500", "10.00"]], [["0.7100", "100.00"], ["0.7200", "40.00"]]))
        self.assertEqual([(l.price, l.size) for l in b.yes_asks], [("0.2800", "40.00"), ("0.2900", "100.00")])
        self.assertEqual(b.yes_ask_micro, 280_000)
        self.assertEqual(b.no_ask_micro, 750_000)  # 1 - best YES bid 0.25
        self.assertEqual(b.best_yes_bid_micro, 250_000)
        self.assertEqual(b.best_no_bid_micro, 720_000)

    def test_ladders_are_sorted_explicitly_best_first_whatever_the_arrival_order(self):
        scrambled = self.raw([["0.20", "1"], ["0.31", "2"], ["0.25", "3"]], [["0.10", "1"], ["0.60", "2"], ["0.50", "3"]])
        b = orderbook.parse_book("T", scrambled)
        self.assertEqual([l.price_micro for l in b.yes_bids], [310_000, 250_000, 200_000])
        self.assertEqual([l.price_micro for l in b.no_bids], [600_000, 500_000, 100_000])
        self.assertEqual([l.price_micro for l in b.yes_asks], [400_000, 500_000, 900_000])  # 1 - no bids, ascending

    def test_strings_preserved_and_sizes_are_exact_decimals(self):
        b = orderbook.parse_book("T", self.raw([["0.3600", "83.35"]], [["0.6300", "1455.99"]]))
        lvl = b.yes_bids[0]
        self.assertEqual((lvl.price, lvl.size), ("0.3600", "83.35"))
        self.assertEqual(lvl.size_decimal, Decimal("83.35"))
        self.assertIsInstance(lvl.price_micro, int)

    def test_empty_sides(self):
        b = orderbook.parse_book("T", self.raw([], []))
        self.assertEqual((b.yes_ask_micro, b.no_ask_micro, b.best_yes_bid_micro, b.yes_asks), (None, None, None, []))
        one = orderbook.parse_book("T", self.raw([["0.40", "5"]], []))
        self.assertIsNone(one.yes_ask_micro)
        self.assertEqual(one.no_ask_micro, 600_000)

    def test_malformed_level_raises_rather_than_dropping(self):
        with self.assertRaises(orderbook.BookError):
            orderbook.parse_book("T", self.raw([["abc", "5"]], []))
        with self.assertRaises(orderbook.BookError):
            orderbook.parse_book("T", self.raw([["0.40"]], []))
        with self.assertRaises(orderbook.BookError):
            orderbook.parse_book("T", {"nope": 1})

    def test_prices_outside_open_unit_interval_rejected(self):
        for bad in ("0", "0.0000", "1.0000", "1.5"):
            with self.assertRaises(orderbook.BookError, msg=bad):
                orderbook.parse_book("T", self.raw([[bad, "5"]], []))


class DataShapeTest(unittest.TestCase):
    def test_series_requests_one_series_and_unwraps(self):
        body = fixture("kalshi_series_KXHIGHNY.json")
        t = FakeTransport(ok(body))
        c, _ = make_client(t)
        s = c.series("KXHIGHNY")
        self.assertEqual(urllib.parse.urlsplit(t.requests[0][0]).path, "/trade-api/v2/series/KXHIGHNY")
        self.assertEqual((s["ticker"], s["fee_multiplier"], s["fee_type"]), ("KXHIGHNY", 1, "quadratic"))

    def test_there_is_no_series_list_call(self):
        c, _ = make_client(FakeTransport(ok({})))
        self.assertFalse(hasattr(c, "list_series"))
        with self.assertRaises(ValueError):
            c._get("/series")
        with self.assertRaises(ValueError):
            c._get("/series/")

    def test_events_filter_uses_open_but_market_status_stays_active(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        t = FakeTransport(ok(body))
        c, _ = make_client(t)
        events = c.events("KXHIGHNY")
        q = query(t.requests[0][0])
        self.assertEqual((q["series_ticker"], q["status"], q["with_nested_markets"]), (["KXHIGHNY"], ["open"], ["true"]))
        m = events[0]["markets"][0]
        self.assertEqual(m["status"], "active")  # lowercase lifecycle value, not the 'open' filter word
        self.assertTrue(kc.is_tradable(m))

    def test_deprecated_liquidity_is_dropped_from_markets(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        body["events"][0]["markets"][0]["liquidity_dollars"] = "123.0000"
        c, _ = make_client(FakeTransport(ok(body)))
        for m in c.events("KXHIGHNY")[0]["markets"]:
            self.assertNotIn("liquidity_dollars", m)

    def test_dollar_and_fp_strings_are_preserved(self):
        body = fixture("kalshi_events_open_KXHIGHNY.json")
        c, _ = make_client(FakeTransport(ok(body)))
        m = c.events("KXHIGHNY")[0]["markets"][0]
        for key in ("yes_bid_dollars", "yes_ask_dollars", "yes_bid_size_fp", "volume_fp", "open_interest_fp"):
            self.assertIsInstance(m[key], str, key)
        self.assertEqual(m["yes_bid_dollars"], "0.0800")

    def test_markets_and_single_market(self):
        ev = fixture("kalshi_events_open_KXHIGHNY.json")["events"][0]
        t = FakeTransport(ok({"markets": ev["markets"]}), ok({"market": ev["markets"][0]}))
        c, _ = make_client(t)
        self.assertEqual(len(c.markets("KXHIGHNY-26OCT17")), 6)
        self.assertEqual(query(t.requests[0][0])["event_ticker"], ["KXHIGHNY-26OCT17"])
        self.assertEqual(c.market("KXHIGHNY-26OCT17-T62")["ticker"], "KXHIGHNY-26OCT17-T62")
        self.assertEqual(urllib.parse.urlsplit(t.requests[1][0]).path, "/trade-api/v2/markets/KXHIGHNY-26OCT17-T62")

    def test_settled_result_from_recorded_settled_day(self):
        ev = fixture("kalshi_events_settled_KXHIGHNY.json")["events"][0]
        c, _ = make_client(FakeTransport(ok({"events": [ev]})))
        markets = c.events("KXHIGHNY", status="settled")[0]["markets"]
        results = {m["ticker"]: kc.settled_result(m) for m in markets}
        self.assertTrue(all(v in ("yes", "no") for v in results.values()))
        self.assertEqual(results["KXHIGHNY-26OCT16-T75"], "yes")  # observed 72 < 75
        # exactly one bracket of a mutually exclusive, exhaustive set resolves yes
        self.assertEqual(sum(v == "yes" for v in results.values()), 1)

    def test_unsettled_market_has_no_result(self):
        m = fixture("kalshi_events_open_KXHIGHNY.json")["events"][0]["markets"][0]
        self.assertIsNone(kc.settled_result(m))

    def test_no_auth_headers_are_ever_sent(self):
        t = FakeTransport(ok({"series": {}}))
        c, _ = make_client(t)
        c.series("KXHIGHNY")
        names = {k.lower() for k in t.requests[0][1]}
        self.assertFalse(names & {"authorization", "kalshi-access-key", "kalshi-access-signature",
                                  "kalshi-access-timestamp"})
        self.assertIn("user-agent", names)


class TokenBucketTest(unittest.TestCase):
    def test_burst_then_paced(self):
        clock = Clock()
        bucket = kc.TokenBucket(rps=5, clock=clock.now, sleep=clock.sleep)
        for _ in range(5):  # capacity == rps: the first five are immediate
            bucket.acquire()
        self.assertEqual(clock.sleeps, [])
        bucket.acquire()  # sixth must wait for one token: 1/5 s
        self.assertEqual(len(clock.sleeps), 1)
        self.assertAlmostEqual(clock.sleeps[0], 0.2, places=6)

    def test_sustained_rate_never_exceeds_rps(self):
        clock = Clock()
        bucket = kc.TokenBucket(rps=5, clock=clock.now, sleep=clock.sleep)
        for _ in range(55):
            bucket.acquire()
        # 55 calls: 5 burst + 50 paced at 5/s = 10 s
        self.assertAlmostEqual(clock.t, 10.0, places=6)

    def test_idle_time_refills_up_to_capacity_only(self):
        clock = Clock()
        bucket = kc.TokenBucket(rps=5, clock=clock.now, sleep=clock.sleep)
        for _ in range(5):
            bucket.acquire()
        clock.t += 100  # long idle: refill caps at 5
        for _ in range(5):
            bucket.acquire()
        self.assertEqual(clock.sleeps, [])
        bucket.acquire()
        self.assertEqual(len(clock.sleeps), 1)

    def test_client_paces_requests_through_the_bucket(self):
        t = FakeTransport(ok({"series": {}}))
        c, clock = make_client(t, rps=2)
        for _ in range(4):
            c.series("KXHIGHNY")
        self.assertAlmostEqual(clock.t, 1.0, places=6)  # 2 burst, then 2 paced at 0.5 s

    def test_rps_from_env(self):
        self.assertEqual(kc.rps_from_env({"KALSHI_CLIENT_RPS": "50"}), 50.0)
        self.assertEqual(kc.rps_from_env({}), 5.0)
        for bad in ("0", "-3", "fast", ""):
            self.assertEqual(kc.rps_from_env({"KALSHI_CLIENT_RPS": bad}), 5.0, bad)


class BackoffTest(unittest.TestCase):
    TOO_MANY = (429, {}, fixture("kalshi_429.json"))

    def test_recorded_429_is_retried_with_exponential_backoff(self):
        t = FakeTransport(self.TOO_MANY, self.TOO_MANY, self.TOO_MANY, ok({"series": {"ticker": "X"}}))
        c, clock = make_client(t, rng=lambda: 0.5, max_retries=4)
        self.assertEqual(c.series("X")["ticker"], "X")
        self.assertEqual(len(t.requests), 4)
        # jitter factor (0.5 + rng) == 1.0: delays are exactly base * 2**n
        self.assertEqual(clock.sleeps, [1.0, 2.0, 4.0])

    def test_jitter_scales_delay_between_half_and_one_and_a_half(self):
        for rng, factor in ((lambda: 0.0, 0.5), (lambda: 1.0, 1.5)):
            t = FakeTransport(self.TOO_MANY, ok({"series": {}}))
            c, clock = make_client(t, rng=rng)
            c.series("X")
            self.assertAlmostEqual(clock.sleeps[0], 1.0 * factor)

    def test_backoff_is_capped(self):
        self.assertEqual(kc.backoff_delay(attempt=20, rng=lambda: 0.5), kc.BACKOFF_CAP_SECONDS)

    def test_persistent_429_becomes_a_skip_not_a_raw_error(self):
        t = FakeTransport(self.TOO_MANY)
        c, _ = make_client(t, max_retries=3)
        with self.assertRaises(kc.RateLimited) as cm:
            c.series("X")
        self.assertEqual(cm.exception.code, "kalshi_429_budget")
        self.assertEqual(len(t.requests), 4)  # first try + 3 retries

    def test_5xx_and_network_errors_retry(self):
        boom = urllib.error.URLError("connection reset")
        t = FakeTransport((503, {}, {"error": "unavailable"}), boom, ok({"series": {"ticker": "X"}}))
        c, clock = make_client(t)
        self.assertEqual(c.series("X")["ticker"], "X")
        self.assertEqual(len(clock.sleeps), 2)

    def test_persistent_5xx_raises_unavailable_with_skip_code(self):
        c, _ = make_client(FakeTransport((502, {}, {"error": "bad gateway"})), max_retries=2)
        with self.assertRaises(kc.KalshiUnavailable) as cm:
            c.series("X")
        self.assertEqual(cm.exception.code, "kalshi_unavailable")

    def test_4xx_other_than_429_is_not_retried(self):
        t = FakeTransport((404, {}, {"error": "not found"}))
        c, clock = make_client(t)
        with self.assertRaises(kc.KalshiHTTPError) as cm:
            c.series("NOPE")
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual((len(t.requests), clock.sleeps), (1, []))

    def test_retry_after_header_is_honored_when_present(self):
        t = FakeTransport((429, {"Retry-After": "7"}, {"error": "too many requests"}), ok({"series": {}}))
        c, clock = make_client(t)
        c.series("X")
        self.assertEqual(clock.sleeps, [7.0])

    def test_non_json_body_is_a_clear_error(self):
        c, _ = make_client(FakeTransport((200, {}, b"<html>blocked</html>")))
        with self.assertRaises(kc.KalshiError):
            c.series("X")


class CallBudgetTest(unittest.TestCase):
    def test_exhaustion_is_a_recorded_skip_and_makes_no_call(self):
        t = FakeTransport(ok({"series": {}}))
        budget = kc.CallBudget(3)
        c, _ = make_client(t, budget=budget)
        for _ in range(3):
            c.series("X")
        with self.assertRaises(kc.BudgetExhausted) as cm:
            c.series("X")
        self.assertEqual(cm.exception.code, "kalshi_call_budget")
        self.assertEqual(len(t.requests), 3)
        self.assertEqual((budget.used, budget.remaining), (3, 0))

    def test_retries_consume_budget(self):
        t = FakeTransport((429, {}, fixture("kalshi_429.json")), ok({"series": {}}))
        budget = kc.CallBudget(5)
        c, _ = make_client(t, budget=budget)
        c.series("X")
        self.assertEqual(budget.used, 2)

    def test_no_budget_means_unlimited(self):
        c, _ = make_client(FakeTransport(ok({"series": {}})))
        for _ in range(50):
            c.series("X")
        self.assertEqual(c.calls, 50)

    def test_calls_and_log_are_recorded_for_run_events(self):
        c, _ = make_client(FakeTransport(ok({"series": {}})))
        c.series("KXHIGHNY")
        self.assertEqual(c.calls, 1)
        self.assertEqual(c.call_log[0][:2], ("GET", "/series/KXHIGHNY"))
        self.assertEqual(c.call_log[0][2], 200)


if __name__ == "__main__":
    unittest.main()
