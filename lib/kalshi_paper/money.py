"""Integer micro-dollar helpers. Money is never a float (constitution; data-model.md)."""
from decimal import Decimal, InvalidOperation

MICRO = 1_000_000
CENT_MICRO = 10_000


def dollars_to_micro(value):
    """Parse a dollar string such as "0.5600" into integer micro-dollars, exactly."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("dollars must be a str (or int), not %s" % type(value).__name__)
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError("not a dollar amount: %r" % (value,))
    if not d.is_finite():
        raise ValueError("not a finite dollar amount: %r" % (value,))
    micro = d * MICRO
    if micro != micro.to_integral_value():
        raise ValueError("finer than a micro-dollar: %r" % (value,))
    return int(micro)


def micro_to_dollars(micro):
    """Format micro-dollars as a dollar string with at least two decimals."""
    if isinstance(micro, bool) or not isinstance(micro, int):
        raise TypeError("micro-dollars must be an int, not %s" % type(micro).__name__)
    sign = "-" if micro < 0 else ""
    whole, frac = divmod(abs(micro), MICRO)
    digits = ("%06d" % frac).rstrip("0").ljust(2, "0")
    return "%s%d.%s" % (sign, whole, digits)


def ceil_to_cent_micro(micro):
    """Round a non-negative micro-dollar amount up to a whole cent."""
    if isinstance(micro, bool) or not isinstance(micro, int):
        raise TypeError("micro-dollars must be an int")
    return -(-micro // CENT_MICRO) * CENT_MICRO


def validate_fill_price(micro):
    """A fill price must lie strictly inside (0, 1 dollar)."""
    if isinstance(micro, bool) or not isinstance(micro, int):
        raise TypeError("price must be integer micro-dollars")
    if not 0 < micro < MICRO:
        raise ValueError("fill price must be in (0, 1): %d micro-dollars" % micro)
    return micro
