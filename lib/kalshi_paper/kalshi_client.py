"""Keyless client for Kalshi's PUBLIC market-data API (no signing, no auth headers, ever).

Behavior encoded from live probes and the reference tool (see skills/kalshi-market-data/references):
  * `/markets/orderbooks` needs the `tickers` param REPEATED; a comma list silently returns one book.
  * Never call the `/series` list endpoint (18 MB, triggers 429); only `/series/{ticker}`.
  * Rate limits are undocumented: a token bucket (default 5 req/s, env KALSHI_CLIENT_RPS),
    exponential backoff with jitter on 429/5xx/network errors, and a per-slot call budget.
    Exhausted budgets and persistent failures raise skip-coded errors the caller records in
    `run_events`; nothing here fabricates data.
  * Market `status` is lowercase lifecycle (`active`, `finalized`), unlike the `open`/`settled`
    query filters. `liquidity_dollars` is deprecated (always 0): depth comes from the orderbook.
"""
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from . import orderbook

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
USER_AGENT = "hermes-kalshi-paper/0.1 (read-only market data)"
DEFAULT_RPS = 5.0
ORDERBOOK_CHUNK = 50
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 30.0
REQUEST_TIMEOUT = 20
_EPSILON = 1e-9
DEPRECATED_MARKET_FIELDS = ("liquidity_dollars", "liquidity")


class KalshiError(Exception):
    code = "kalshi_error"


class KalshiSkip(KalshiError):
    """A failure the caller should record as a `run_events` skip (with `.code`) and move past."""


class RateLimited(KalshiSkip):
    code = "kalshi_429_budget"


class KalshiUnavailable(KalshiSkip):
    code = "kalshi_unavailable"


class BudgetExhausted(KalshiSkip):
    code = "kalshi_call_budget"


class KalshiHTTPError(KalshiError):
    def __init__(self, status, detail=""):
        super().__init__("HTTP %s %s" % (status, detail))
        self.status = status


def rps_from_env(env=None):
    raw = (env if env is not None else os.environ).get("KALSHI_CLIENT_RPS", "")
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_RPS
    return value if value > 0 else DEFAULT_RPS


def backoff_delay(attempt, rng=random.random):
    """Exponential backoff with +/-50% jitter, capped."""
    return min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** attempt) * (0.5 + rng()))


class TokenBucket:
    """Capacity == rps (a one-second burst), refilled continuously."""

    def __init__(self, rps, clock=time.monotonic, sleep=time.sleep):
        self.rps = float(rps)
        self.capacity = max(1.0, self.rps)
        self.tokens = self.capacity
        self._clock, self._sleep = clock, sleep
        self._last = clock()

    def acquire(self):
        while True:
            now = self._clock()
            self.tokens = min(self.capacity, self.tokens + (now - self._last) * self.rps)
            self._last = now
            if self.tokens >= 1.0 - _EPSILON:  # tolerate float residue so a tiny shortfall cannot spin
                self.tokens = max(0.0, self.tokens - 1.0)
                return
            self._sleep((1.0 - self.tokens) / self.rps)


class CallBudget:
    """Maximum HTTP attempts (retries included) for one slot."""

    def __init__(self, limit):
        self.limit, self.used = limit, 0

    @property
    def remaining(self):
        return self.limit - self.used

    def consume(self):
        if self.used >= self.limit:
            raise BudgetExhausted("call budget of %d exhausted" % self.limit)
        self.used += 1


def _urllib_transport(url, headers, timeout):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def is_tradable(market):
    return market.get("status") == "active"


def settled_result(market):
    """'yes'/'no' once a market is finalized with a result, else None."""
    if market.get("status") in ("finalized", "settled") and market.get("result") in ("yes", "no"):
        return market["result"]
    return None


def clean_market(market):
    return {k: v for k, v in market.items() if k not in DEPRECATED_MARKET_FIELDS}


class KalshiClient:
    def __init__(self, base_url=BASE_URL, rps=None, budget=None, transport=None, rng=random.random,
                 max_retries=3, clock=time.monotonic, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.budget = budget
        self.max_retries = max_retries
        self._transport = transport or _urllib_transport
        self._rng, self._sleep = rng, sleep
        self._bucket = TokenBucket(rps if rps is not None else rps_from_env(), clock=clock, sleep=sleep)
        self.calls = 0
        self.call_log = []  # (method, path, status) per HTTP attempt

    # -- transport ----------------------------------------------------------------
    def _get(self, path, params=None):
        if path.rstrip("/") == "/series":
            raise ValueError("the /series list endpoint is never called (18 MB, triggers 429)")
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        last = None
        for attempt in range(self.max_retries + 1):
            if self.budget is not None:
                self.budget.consume()
            self._bucket.acquire()
            delay = None
            try:
                status, resp_headers, body = self._transport(url, headers, REQUEST_TIMEOUT)
            except (urllib.error.URLError, OSError) as e:
                self.calls += 1
                self.call_log.append(("GET", path, "network"))
                last = KalshiUnavailable("network error: %s" % e)
            else:
                self.calls += 1
                self.call_log.append(("GET", path, status))
                if status == 200:
                    try:
                        return json.loads(body)
                    except ValueError:
                        raise KalshiError("non-JSON response from %s" % path)
                if status == 429:
                    last = RateLimited("HTTP 429 on %s" % path)
                    retry_after = {k.lower(): v for k, v in resp_headers.items()}.get("retry-after")
                    try:
                        delay = min(float(retry_after), BACKOFF_CAP_SECONDS) if retry_after else None
                    except ValueError:
                        delay = None
                elif status >= 500:
                    last = KalshiUnavailable("HTTP %d on %s" % (status, path))
                else:
                    raise KalshiHTTPError(status, path)
            if attempt < self.max_retries:
                self._sleep(delay if delay is not None else backoff_delay(attempt, self._rng))
        raise last

    # -- endpoints ----------------------------------------------------------------
    def series(self, ticker):
        return self._get("/series/%s" % urllib.parse.quote(ticker))["series"]

    def events(self, series_ticker, status="open", limit=20, with_nested_markets=True):
        data = self._get("/events", [("series_ticker", series_ticker), ("status", status), ("limit", limit),
                                     ("with_nested_markets", "true" if with_nested_markets else "false")])
        events = []
        for e in data.get("events", []):
            e = dict(e)
            if "markets" in e:
                e["markets"] = [clean_market(m) for m in e["markets"]]
            events.append(e)
        return events

    def markets(self, event_ticker):
        data = self._get("/markets", [("event_ticker", event_ticker)])
        return [clean_market(m) for m in data.get("markets", [])]

    def market(self, ticker):
        return clean_market(self._get("/markets/%s" % urllib.parse.quote(ticker))["market"])

    def orderbooks(self, tickers):
        """{ticker: Book}. `tickers` is sent as a REPEATED query param, in chunks."""
        books = {}
        tickers = list(tickers)
        for i in range(0, len(tickers), ORDERBOOK_CHUNK):
            chunk = tickers[i:i + ORDERBOOK_CHUNK]
            data = self._get("/markets/orderbooks", [("tickers", t) for t in chunk])
            for item in data.get("orderbooks", []):
                books[item["ticker"]] = orderbook.parse_book(item["ticker"], item)
        return books
