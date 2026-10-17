"""register(ctx) against a STRICT fake ctx with the real signatures found in spike S1.
Lesson from S1: one bad call aborts register() and silently drops everything after it."""
import importlib.util
import logging
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

    def __init__(self, fail_skills=()):
        self.skills = {}
        self.fail_skills = set(fail_skills)

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


if __name__ == "__main__":
    unittest.main()
