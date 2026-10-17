"""S1 stub. Signatures verified against Hermes v0.22.2 on the backend; see the
handoff (specs/001-paper-trading-mvp/handoff/phase1-backend-spikes.md) for the
evidence and for every change made to the original guess.
"""
import json
import os
import sys
from pathlib import Path


def _ping(args=None, **kwargs):
    # Tool handlers must return a STRING; the registry rejects a dict with
    # "Tool handler returned unsupported result type: dict".
    return json.dumps({"ok": True, "python": sys.version, "hermes_home": os.environ.get("HERMES_HOME")})


def _command(raw_args="", **kwargs):
    # Slash-command handlers are called as handler(raw_args: str) -> str|None.
    return "hermes-kalshi stub command ok; args=%r kwargs=%r" % ((raw_args,), kwargs)


def register(ctx):
    here = Path(__file__).parent
    ctx.register_tool(
        name="kalshi_stub_ping",
        toolset="hermes_kalshi",  # REQUIRED positional; omitting it aborts register()
        description="S1 spike: returns python version and HERMES_HOME.",
        handler=_ping,
        schema={"type": "object", "properties": {}},
    )
    ctx.register_skill("stub", here / "skills" / "stub" / "SKILL.md")
    ctx.register_command("kalshi-stub", _command, description="S1 spike command")
