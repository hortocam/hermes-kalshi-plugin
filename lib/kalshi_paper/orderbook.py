"""Orderbook parsing and ask derivation.

Kalshi orderbooks list BIDS only, as `[price, size]` dollar/fixed-point strings:
    yes_ask = 1 - best NO bid        no_ask = 1 - best YES bid
Ladders arrive in no guaranteed order, so they are sorted explicitly here. Sizes can be
fractional (`_fp`), so they stay exact Decimals; prices stay strings plus integer micro-dollars.
Level walking and fees are added by the execution stories.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from . import money


class BookError(Exception):
    pass


@dataclass(frozen=True)
class Level:
    price: str          # as received (bids) or formatted to >= 4 decimals (derived asks)
    size: str           # as received
    price_micro: int

    @property
    def size_decimal(self):
        return Decimal(self.size)


@dataclass(frozen=True)
class Book:
    ticker: str
    yes_bids: list = field(default_factory=list)   # best (highest) first
    no_bids: list = field(default_factory=list)    # best (highest) first
    yes_asks: list = field(default_factory=list)   # derived from NO bids; best (lowest) first
    no_asks: list = field(default_factory=list)    # derived from YES bids; best (lowest) first

    @property
    def best_yes_bid_micro(self):
        return self.yes_bids[0].price_micro if self.yes_bids else None

    @property
    def best_no_bid_micro(self):
        return self.no_bids[0].price_micro if self.no_bids else None

    @property
    def yes_ask_micro(self):
        return self.yes_asks[0].price_micro if self.yes_asks else None

    @property
    def no_ask_micro(self):
        return self.no_asks[0].price_micro if self.no_asks else None


def _dollars(micro):
    whole, frac = divmod(micro, money.MICRO)
    return "%d.%s" % (whole, ("%06d" % frac).rstrip("0").ljust(4, "0"))


def _levels(raw_side, ticker, side):
    out = []
    for item in raw_side or []:
        try:
            price, size = item
            micro = money.validate_fill_price(money.dollars_to_micro(price))
            qty = Decimal(size)
        except (ValueError, TypeError, InvalidOperation) as e:
            raise BookError("%s: bad %s level %r (%s)" % (ticker, side, item, e))
        if qty < 0:
            raise BookError("%s: negative size in %s level %r" % (ticker, side, item))
        if qty == 0:
            continue  # an empty level carries no liquidity
        out.append(Level(price=price, size=size, price_micro=micro))
    return sorted(out, key=lambda l: l.price_micro, reverse=True)


def _asks_from(bids):
    asks = [Level(price=_dollars(money.MICRO - b.price_micro), size=b.size,
                  price_micro=money.MICRO - b.price_micro) for b in bids]
    return sorted(asks, key=lambda l: l.price_micro)


def parse_book(ticker, raw):
    """`raw` is `{"orderbook_fp": {"yes_dollars": [...], "no_dollars": [...]}}` (batched element or single)."""
    try:
        fp = raw["orderbook_fp"]
    except (KeyError, TypeError):
        raise BookError("%s: response has no orderbook_fp" % ticker)
    if not isinstance(fp, dict):
        raise BookError("%s: orderbook_fp is not an object" % ticker)
    yes_bids = _levels(fp.get("yes_dollars"), ticker, "yes")
    no_bids = _levels(fp.get("no_dollars"), ticker, "no")
    return Book(ticker=ticker, yes_bids=yes_bids, no_bids=no_bids,
                yes_asks=_asks_from(no_bids), no_asks=_asks_from(yes_bids))
