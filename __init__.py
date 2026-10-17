"""Hermes plugin entry point for hermes-kalshi (paper trading only)."""
import logging
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


def register(ctx):
    _register_skills(ctx)
