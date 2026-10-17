"""Path and watch-list configuration. All Hermes paths resolve through here.

HERMES_HOME is the active profile's home (the root home itself for the default
profile). The root home is the parent of `profiles/` when HERMES_HOME is a profile.
"""
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

PLUGIN_NAME = "hermes-kalshi"

_WATCH_FIELDS = ("series_ticker", "kind", "city", "cli_code", "obs_station", "lat", "lon", "tz")


class ConfigError(Exception):
    pass


def plugin_root():
    return Path(__file__).resolve().parents[2]


def hermes_home():
    env = os.environ.get("HERMES_HOME")
    return Path(env).expanduser() if env else Path.home() / ".hermes"


def _is_profile_home(home):
    return home.parent.name == "profiles"


def root_home(home=None):
    home = Path(home) if home is not None else hermes_home()
    return home.parent.parent if _is_profile_home(home) else home


def profile_name(home=None):
    home = Path(home) if home is not None else hermes_home()
    return home.name if _is_profile_home(home) else "default"


def _data_dir(base):
    return Path(base) / "plugin-data" / PLUGIN_NAME


def db_path(home=None):
    return _data_dir(Path(home) if home is not None else hermes_home()) / "data.db"


def shared_snapshot_dir(home=None):
    return _data_dir(root_home(home)) / "snapshots"


def resolve_db(override=None):
    return Path(override) if override else db_path()


def load_watches(path=None):
    """Load and validate the watch list (default: config/watches.default.json)."""
    path = Path(path) if path else plugin_root() / "config" / "watches.default.json"
    try:
        watches = json.loads(path.read_text())["watches"]
    except (OSError, ValueError, KeyError) as e:
        raise ConfigError("cannot read watches from %s: %s" % (path, e))
    seen = set()
    for w in watches:
        missing = [f for f in _WATCH_FIELDS if f not in w]
        if missing:
            raise ConfigError("watch %r missing fields: %s" % (w.get("series_ticker"), ", ".join(missing)))
        if w["kind"] not in ("high", "low"):
            raise ConfigError("watch %s: kind must be high or low" % w["series_ticker"])
        if w["series_ticker"] in seen:
            raise ConfigError("duplicate series_ticker %s" % w["series_ticker"])
        seen.add(w["series_ticker"])
        try:
            ZoneInfo(w["tz"])
        except Exception:
            raise ConfigError("watch %s: unknown timezone %r" % (w["series_ticker"], w["tz"]))
    return watches
