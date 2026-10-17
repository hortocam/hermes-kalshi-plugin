"""register(ctx) against a STRICT fake ctx with the real signatures found in spike S1.
Lesson from S1: one bad call aborts register() and silently drops everything after it."""
import importlib.util
import logging
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    spec = importlib.util.spec_from_file_location("hermes_kalshi_plugin_under_test", ROOT / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StrictCtx:
    """Mirrors PluginContext signatures confirmed in S1 (register_skill(name, path, description="", frontmatter=None))."""

    BUILTIN_COMMANDS = {"help", "new", "model", "clear"}

    def __init__(self, fail_skills=(), fail_commands=()):
        self.skills = {}
        self.commands = {}
        self.fail_skills = set(fail_skills)
        self.fail_commands = set(fail_commands)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        """S1: handler is called with ONE positional string of raw args; built-in names are refused."""
        if name in self.BUILTIN_COMMANDS:
            raise ValueError("collides with a built-in command")
        if name in self.fail_commands:
            raise RuntimeError("boom registering command %s" % name)
        if not callable(handler):
            raise TypeError("handler must be callable")
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        if ":" in name:
            raise ValueError("a ':' in the registered name is rejected")
        if name in self.fail_skills:
            raise RuntimeError("boom registering %s" % name)
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        self.skills[name] = Path(path)


class SkillRegistrationTest(unittest.TestCase):
    def test_registers_every_skill_directory_that_has_a_skill_md(self):
        ctx = StrictCtx()
        load_plugin().register(ctx)
        expected = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertIn("kalshi-market-data", expected)
        self.assertEqual(set(ctx.skills), expected)

    def test_directories_without_skill_md_are_skipped(self):
        ctx = StrictCtx()
        load_plugin().register(ctx)
        for name in ("kalshi-evaluator", "kalshi-ops"):
            has = (ROOT / "skills" / name / "SKILL.md").exists()
            self.assertEqual(name in ctx.skills, has, name)

    def test_names_have_no_namespace_colon(self):
        ctx = StrictCtx()
        load_plugin().register(ctx)
        self.assertTrue(all(":" not in n for n in ctx.skills))

    def test_one_failing_registration_does_not_drop_the_rest(self):
        ctx = StrictCtx(fail_skills={"kalshi-market-data"})
        with self.assertLogs("hermes_kalshi", level=logging.WARNING) as logs:
            load_plugin().register(ctx)  # must not raise
        self.assertIn("kalshi-market-data", "\n".join(logs.output))

    def test_skill_md_has_frontmatter_name_and_description(self):
        text = (ROOT / "skills" / "kalshi-market-data" / "SKILL.md").read_text()
        head = text.split("---")[1]
        self.assertIn("name: kalshi-market-data", head)
        self.assertIn("description:", head)


class WatchCommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self._tmp.name
        self.addCleanup(self._restore)
        self.ctx = StrictCtx()
        load_plugin().register(self.ctx)
        self.handler = self.ctx.commands["kalshi-watch"]

    def _restore(self):
        if self._old is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._old

    def init_db(self):
        import sys
        sys.path.insert(0, str(ROOT / "lib"))
        import contextlib, io
        from kalshi_paper import cli
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["init"]), 0)

    def test_command_is_registered(self):
        self.assertIn("kalshi-watch", self.ctx.commands)

    def test_before_init_it_says_so_and_creates_nothing(self):
        out = self.handler("list")
        self.assertIsInstance(out, str)
        self.assertIn("init", out)
        self.assertFalse((Path(self._tmp.name) / "plugin-data").exists())

    def test_list_pause_enable_round_trip(self):
        self.init_db()
        listing = self.handler("list")
        self.assertIn("KXHIGHTBOS", listing)
        self.assertEqual(len([l for l in listing.splitlines() if l.startswith("KX")]), 8)
        self.assertIn("paused", self.handler("pause KXHIGHTBOS"))
        self.assertIn("paused", self.handler("list"))
        self.assertIn("active", self.handler("enable KXHIGHTBOS"))
        self.assertIn("no change", self.handler("enable KXHIGHTBOS"))

    def test_bad_input_returns_usage_text_never_raises(self):
        self.init_db()
        for raw in ("", "   ", "explode KXHIGHNY", "pause", "pause KXNOPE", "enable KXHIGHNY extra"):
            out = self.handler(raw)
            self.assertIsInstance(out, str, raw)
            self.assertTrue(out, raw)
        self.assertIn("Usage", self.handler(""))

    def test_failing_command_registration_does_not_drop_skills(self):
        ctx = StrictCtx(fail_commands={"kalshi-watch"})
        with self.assertLogs("hermes_kalshi", level=logging.WARNING):
            load_plugin().register(ctx)
        self.assertIn("kalshi-market-data", ctx.skills)
        self.assertNotIn("kalshi-watch", ctx.commands)

    def test_kalshi_ops_skill_is_registered_and_has_frontmatter(self):
        self.assertIn("kalshi-ops", self.ctx.skills)
        head = (ROOT / "skills" / "kalshi-ops" / "SKILL.md").read_text().split("---")[1]
        self.assertIn("name: kalshi-ops", head)
        self.assertIn("description:", head)


if __name__ == "__main__":
    unittest.main()
