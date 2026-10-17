"""Shared test helpers: temp Hermes homes, fixture loading, frozen clock."""
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


@contextmanager
def temp_hermes_home(profile=None):
    """Yield (root_home, profile_home). HERMES_HOME points at the profile home
    (or the root when profile is None) for the duration of the block."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        home = root / "profiles" / profile if profile else root
        home.mkdir(parents=True, exist_ok=True)
        old = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(home)
        try:
            yield root, home
        finally:
            if old is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = old


def load_fixture(name):
    """Load a recorded fixture; parse JSON when the name ends in .json."""
    path = FIXTURES / name
    text = path.read_text()
    return json.loads(text) if path.suffix == ".json" else text


class FrozenClock:
    """Callable returning a fixed aware UTC datetime; advance() moves it."""

    def __init__(self, iso="2026-01-15T12:00:00+00:00"):
        self.now = datetime.fromisoformat(iso).astimezone(timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now = self.now + delta


class IsolatedHomeCase(unittest.TestCase):
    """Points HERMES_HOME at a throwaway directory for every test, so nothing can reach a
    real Hermes home (CLAUDE.md: unit tests never touch a real $HERMES_HOME)."""

    def setUp(self):
        super().setUp()
        self._home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._home_tmp.cleanup)
        self._old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self._home_tmp.name
        self.addCleanup(self._restore_home)

    def _restore_home(self):
        if self._old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._old_home
