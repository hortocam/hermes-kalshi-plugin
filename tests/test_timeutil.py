import unittest
from datetime import date, datetime, timedelta, timezone

from lib.kalshi_paper import timeutil

UTC = timezone.utc


def utc(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC)


class LstWindowTest(unittest.TestCase):
    """The market day is the local STANDARD-time day: midnight to midnight at the
    zone's standard offset. Standard offsets: NY/Boston -5, Chicago -6, LA -8."""

    def test_new_york_winter(self):
        start, end = timeutil.lst_day_window(date(2026, 1, 15), "America/New_York")
        self.assertEqual(start, utc(2026, 1, 15, 5))
        self.assertEqual(end, utc(2026, 1, 16, 5))

    def test_new_york_summer_is_still_standard_time(self):
        start, end = timeutil.lst_day_window(date(2026, 7, 15), "America/New_York")
        self.assertEqual(start, utc(2026, 7, 15, 5))
        self.assertEqual(end, utc(2026, 7, 16, 5))

    def test_summer_window_is_1am_to_1259am_local_wall_time(self):
        start, end = timeutil.lst_day_window_local(date(2026, 7, 15), "America/New_York")
        self.assertEqual((start.hour, start.minute), (1, 0))
        self.assertEqual(start.date(), date(2026, 7, 15))
        last_minute = end - timedelta(minutes=1)
        self.assertEqual((last_minute.hour, last_minute.minute), (0, 59))
        self.assertEqual(last_minute.date(), date(2026, 7, 16))

    def test_winter_window_is_midnight_to_midnight_local(self):
        start, end = timeutil.lst_day_window_local(date(2026, 1, 15), "America/New_York")
        self.assertEqual((start.hour, start.minute), (0, 0))
        self.assertEqual((end.hour, end.minute), (0, 0))
        self.assertEqual(end.date(), date(2026, 1, 16))

    def test_other_cities(self):
        self.assertEqual(timeutil.lst_day_window(date(2026, 7, 15), "America/Chicago")[0], utc(2026, 7, 15, 6))
        self.assertEqual(timeutil.lst_day_window(date(2026, 7, 15), "America/Los_Angeles")[0], utc(2026, 7, 15, 8))
        self.assertEqual(timeutil.lst_day_window(date(2026, 7, 15), "America/New_York")[0], utc(2026, 7, 15, 5))  # Boston shares NY zone

    def test_always_24_hours_spring_forward_day(self):
        # US DST began 2026-03-08 (2:00 AM local jumps to 3:00 AM).
        start, end = timeutil.lst_day_window(date(2026, 3, 8), "America/New_York")
        self.assertEqual(start, utc(2026, 3, 8, 5))
        self.assertEqual(end - start, timedelta(hours=24))

    def test_always_24_hours_fall_back_day(self):
        # US DST ended 2026-11-01 (2:00 AM local repeats 1:00 AM).
        start, end = timeutil.lst_day_window(date(2026, 11, 1), "America/New_York")
        self.assertEqual(start, utc(2026, 11, 1, 5))
        self.assertEqual(end, utc(2026, 11, 2, 5))
        self.assertEqual(end - start, timedelta(hours=24))

    def test_consecutive_days_tile_without_gaps_across_dst(self):
        d = date(2026, 3, 6)
        prev_end = None
        for _ in range(5):
            start, end = timeutil.lst_day_window(d, "America/Chicago")
            if prev_end is not None:
                self.assertEqual(start, prev_end)
            prev_end = end
            d += timedelta(days=1)


class MarketDateTest(unittest.TestCase):
    def test_instant_maps_to_standard_time_date(self):
        # 2026-07-16 00:30 EDT is 04:30Z, still 07-15 in standard time (23:30 EST).
        self.assertEqual(timeutil.market_date(utc(2026, 7, 16, 4, 30), "America/New_York"), date(2026, 7, 15))
        # 00:59 EDT 07-16 is 04:59Z -> still 07-15; 01:00 EDT is 05:00Z -> 07-16.
        self.assertEqual(timeutil.market_date(utc(2026, 7, 16, 4, 59), "America/New_York"), date(2026, 7, 15))
        self.assertEqual(timeutil.market_date(utc(2026, 7, 16, 5, 0), "America/New_York"), date(2026, 7, 16))

    def test_winter_matches_wall_clock(self):
        self.assertEqual(timeutil.market_date(utc(2026, 1, 16, 4, 59), "America/New_York"), date(2026, 1, 15))
        self.assertEqual(timeutil.market_date(utc(2026, 1, 16, 5, 0), "America/New_York"), date(2026, 1, 16))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            timeutil.market_date(datetime(2026, 1, 1), "America/New_York")


class UtcHelpersTest(unittest.TestCase):
    def test_iso_round_trip(self):
        dt = utc(2026, 10, 17, 12, 30)
        self.assertEqual(timeutil.to_utc_iso(dt), "2026-10-17T12:30:00Z")
        self.assertEqual(timeutil.parse_utc_iso("2026-10-17T12:30:00Z"), dt)

    def test_offset_input_converted_to_utc(self):
        et = datetime.fromisoformat("2026-10-17T08:30:00-04:00")
        self.assertEqual(timeutil.to_utc_iso(et), "2026-10-17T12:30:00Z")

    def test_naive_rejected(self):
        with self.assertRaises(ValueError):
            timeutil.to_utc_iso(datetime(2026, 10, 17, 12, 30))
        with self.assertRaises(ValueError):
            timeutil.parse_utc_iso("2026-10-17T12:30:00")

    def test_local_to_utc(self):
        local = datetime(2026, 7, 15, 8, 0, tzinfo=timeutil.zone("America/New_York"))
        self.assertEqual(timeutil.to_utc_iso(local), "2026-07-15T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
