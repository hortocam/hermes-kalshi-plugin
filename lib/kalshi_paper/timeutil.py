"""Time helpers. All stored timestamps are UTC; local-day logic uses the station's
STANDARD-time day (the Kalshi market day), not the wall-clock day."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def zone(name):
    return ZoneInfo(name)


def _standard_offset(tz, local_date):
    """UTC offset of `tz` with DST removed, for the given date."""
    probe = datetime(local_date.year, local_date.month, local_date.day, 12, tzinfo=tz)
    return probe.utcoffset() - (probe.dst() or timedelta(0))


def lst_day_window(local_date, tz_name):
    """(start_utc, end_utc) of the standard-time day `local_date` in `tz_name`."""
    tz = zone(tz_name)
    std = timezone(_standard_offset(tz, local_date))
    start = datetime(local_date.year, local_date.month, local_date.day, tzinfo=std)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def lst_day_window_local(local_date, tz_name):
    """The same window as aware datetimes in the zone's wall-clock time."""
    tz = zone(tz_name)
    start, end = lst_day_window(local_date, tz_name)
    return start.astimezone(tz), end.astimezone(tz)


def market_date(instant, tz_name):
    """The standard-time calendar date an aware instant falls in."""
    if instant.tzinfo is None:
        raise ValueError("instant must be timezone-aware")
    tz = zone(tz_name)
    local = instant.astimezone(tz)
    std = timezone(_standard_offset(tz, local.date()))
    return instant.astimezone(std).date()


def to_utc_iso(dt):
    if dt.tzinfo is None:
        raise ValueError("naive datetime not allowed")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc_iso(text):
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must carry a UTC marker or offset: %r" % text)
    return dt.astimezone(UTC)
