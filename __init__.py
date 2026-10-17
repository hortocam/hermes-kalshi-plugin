"""Hermes plugin entry point for hermes-kalshi (paper trading only)."""
import logging
import sys
from pathlib import Path

log = logging.getLogger("hermes_kalshi")

_ROOT = Path(__file__).resolve().parent


def _guarded(label, fn):
    """Run one registration. Hermes aborts register() at the first exception and silently
    drops every later registration (spike S1), so each call is isolated and logged."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - one bad registration must not cost the rest
        log.warning("hermes-kalshi: could not register %s: %s", label, e)


def _register_skills(ctx):
    skills = _ROOT / "skills"
    if not skills.is_dir():
        return
    for skill_md in sorted(skills.glob("*/SKILL.md")):
        name = skill_md.parent.name
        _guarded("skill %s" % name, lambda n=name, p=skill_md: ctx.register_skill(n, p))


_WATCH_USAGE = ("Usage: /kalshi-watch list | enable <series> | pause <series> | disable <series>\n"
                "Series look like KXHIGHNY, KXLOWTBOS. Paused or disabled watches evaluate nothing; "
                "their open positions still settle.")


def _lib():
    path = str(_ROOT / "lib")
    if path not in sys.path:
        sys.path.insert(0, path)
    from kalshi_paper import config, store, watches
    return config, store, watches


def _watch_command(raw_args="", *_ignored, **_kwargs):
    """/kalshi-watch handler. Slash commands receive ONE raw-args string (spike S1) and return text."""
    try:
        config, store, watches = _lib()
        parts = (raw_args or "").split()
        action = parts[0].lower() if parts else ""
        if action == "list" and len(parts) == 1:
            need_series = False
        elif action in ("enable", "pause", "disable") and len(parts) == 2:
            need_series = True
        else:
            return _WATCH_USAGE
        db = config.resolve_db()
        if not db.exists():
            return "No Kalshi database for this profile yet. Run `kalshi-paper init` first."
        con = store.connect(db)
        try:
            store.migrate(con)
            if not need_series:
                return "\n".join(watches.format_line(w) for w in watches.list_watches(con)) or "No watches."
            result = getattr(watches, action)(con, parts[1])
            return watches.describe(result)
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001 - a chat command must answer, not raise
        return "kalshi-watch: %s" % e


def _register_commands(ctx):
    _guarded("command kalshi-watch", lambda: ctx.register_command(
        "kalshi-watch", _watch_command, description="List, enable, pause or disable a Kalshi watch",
        args_hint="<list|enable|pause|disable> [series]"))


def register(ctx):
    _register_skills(ctx)
    _register_commands(ctx)
