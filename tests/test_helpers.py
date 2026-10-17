import os
import unittest
from datetime import timedelta

from tests.helpers import FrozenClock, temp_hermes_home


class HelpersTest(unittest.TestCase):
    def test_temp_home_sets_and_restores_env(self):
        before = os.environ.get("HERMES_HOME")
        with temp_hermes_home("kalshi-bot") as (root, home):
            self.assertEqual(home, root / "profiles" / "kalshi-bot")
            self.assertEqual(os.environ["HERMES_HOME"], str(home))
            self.assertTrue(home.is_dir())
        self.assertEqual(os.environ.get("HERMES_HOME"), before)

    def test_frozen_clock_advances(self):
        clock = FrozenClock("2026-01-15T12:00:00+00:00")
        clock.advance(timedelta(minutes=20))
        self.assertEqual(clock().isoformat(), "2026-01-15T12:20:00+00:00")


if __name__ == "__main__":
    unittest.main()
