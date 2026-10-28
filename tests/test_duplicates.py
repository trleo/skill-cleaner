import os
import tempfile
import unittest

from skill_cleaner.duplicates import find_duplicate_groups, keeper_for
from skill_cleaner.scanner import scan_roots
from skill_cleaner.usage import attach_usage
from tests.helpers import make_skill


class TestDuplicates(unittest.TestCase):
    def _scan(self, tmp, setup):
        setup(tmp)
        roots = {}
        for tool in ("claude", "cursor", "antigravity"):
            p = os.path.join(tmp, tool)
            if os.path.isdir(p):
                roots[tool] = p
        return scan_roots(roots)

    def test_exact_name_within_tool_is_duplicate(self):
        def setup(tmp):
            make_skill(tmp, "claude", "seo-audit", "Audit SEO rankings",
                       subdir="a")
            make_skill(tmp, "claude", "seo-audit", "Audit SEO rankings",
                       subdir="b")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            groups = find_duplicate_groups(skills)
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].kind, "exact-name")
            self.assertTrue(groups[0].within_tool)

    def test_exact_content_different_names_is_duplicate(self):
        def setup(tmp):
            make_skill(tmp, "claude", "skill-one", "Same body skill",
                       body="Identical body text here.\n")
            make_skill(tmp, "claude", "skill-two", "Same body skill",
                       body="Identical body text here.\n")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            groups = find_duplicate_groups(skills)
            self.assertEqual(len(groups), 1)
            # name differs, description same, content same: exact-content wins
            self.assertIn(groups[0].kind, ("exact-content", "exact-name"))

    def test_keyword_overlap_flags_similar_purpose(self):
        def setup(tmp):
            make_skill(tmp, "claude", "marketing-copywriting",
                       "Write marketing copy editing for campaigns")
            make_skill(tmp, "claude", "marketing-copy-editing",
                       "Write marketing copy editing for campaigns")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            groups = find_duplicate_groups(skills)
            self.assertEqual(len(groups), 1)

    def test_unrelated_skills_are_not_grouped(self):
        def setup(tmp):
            make_skill(tmp, "claude", "react-dev",
                       "Build React components with hooks and tests",
                       body="Render components, run hooks, write tests.\n")
            make_skill(tmp, "claude", "postgres-migrate",
                       "Migrate PostgreSQL schemas with zero downtime",
                       body="Plan migrations, apply schema changes, verify data.\n")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            self.assertEqual(find_duplicate_groups(skills), [])

    def test_cross_tool_same_skill_is_shared_not_within_tool(self):
        def setup(tmp):
            make_skill(tmp, "claude", "react-dev", "Build React components")
            make_skill(tmp, "cursor", "react-dev", "Build React components")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            groups = find_duplicate_groups(skills)
            self.assertEqual(len(groups), 1)
            self.assertFalse(groups[0].within_tool)
            self.assertTrue(groups[0].cross_tool)

    def test_mixed_group_has_both_within_and_cross_pairs(self):
        def setup(tmp):
            make_skill(tmp, "claude", "dup", "Short", subdir="a")
            make_skill(tmp, "claude", "dup", "Longer description here", subdir="b")
            make_skill(tmp, "cursor", "dup", "Short", subdir="a")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            groups = find_duplicate_groups(skills)
            self.assertEqual(len(groups), 1)
            self.assertTrue(groups[0].has_within_tool_pair)
            self.assertTrue(groups[0].cross_tool)

    def test_keeper_prefers_longest_description(self):
        def setup(tmp):
            make_skill(tmp, "claude", "dup", "Short", subdir="a")
            make_skill(tmp, "claude", "dup",
                       "A much longer and more complete description of the same skill",
                       subdir="b")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            groups = find_duplicate_groups(skills)
            keeper = keeper_for(groups[0])
            self.assertIn("longer", keeper.description)

    def test_usage_unknown_without_history(self):
        def setup(tmp):
            make_skill(tmp, "claude", "never-used", "Do something rare")
        with tempfile.TemporaryDirectory() as tmp:
            skills = self._scan(tmp, setup)
            attach_usage(skills, [])
            self.assertEqual(skills[0].usage, "unknown")

    def test_usage_used_and_unused_with_history(self):
        def setup(tmp):
            make_skill(tmp, "claude", "used-skill", "Used often")
            make_skill(tmp, "claude", "unused-skill", "Never mentioned")
            hist = os.path.join(tmp, "history.txt")
            with open(hist, "w", encoding="utf-8") as f:
                f.write("yesterday I used used-skill for the task\n")
            self._hist = hist
        with tempfile.TemporaryDirectory() as tmp:
            setup(tmp)
            roots = {"claude": os.path.join(tmp, "claude")}
            skills = scan_roots(roots)
            n = attach_usage(skills, [os.path.join(tmp, "history.txt")])
            self.assertEqual(n, 1)
            by_name = {s.name: s.usage for s in skills}
            self.assertEqual(by_name["used-skill"], "used")
            self.assertEqual(by_name["unused-skill"], "unused-candidate")


if __name__ == "__main__":
    unittest.main()
