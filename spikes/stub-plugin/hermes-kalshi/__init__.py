"""S1 stub. Signatures follow research.md (R1); adapt to the real Hermes API and
record every deviation in the handoff file."""
import os
import sys
from pathlib import Path


def _ping(args=None, **kwargs):
    return {"ok": True, "python": sys.version, "hermes_home": os.environ.get("HERMES_HOME")}


def _command(*args, **kwargs):
    return "hermes-kalshi stub command ok; args=%r kwargs=%r" % (args, kwargs)


def register(ctx):
    here = Path(__file__).parent
    ctx.register_tool(
        name="kalshi_stub_ping",
        description="S1 spike: returns python version and HERMES_HOME.",
        handler=_ping,
        schema={"type": "object", "properties": {}},
    )
    ctx.register_skill("stub", here / "skills" / "stub" / "SKILL.md")
    ctx.register_command("kalshi-stub", _command, description="S1 spike command")
