import os
import tempfile
import unittest
from pathlib import Path

from skill_cleaner.scanner import scan_roots
from tests.helpers import make_skill, make_skill_no_frontmatter


class TestScanner(unittest.TestCase):
    def test_finds_skill_and_parses_name_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "react-dev",
                       "Build React components with hooks and tests")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            self.assertEqual(len(skills), 1)
            s = skills[0]
            self.assertEqual(s.name, "react-dev")
            self.assertIn("React", s.description)
            self.assertEqual(s.tool, "claude")
            self.assertGreater(s.size_bytes, 0)

    def test_directory_without_skill_md_is_not_a_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "claude" / "not-a-skill"
            d.mkdir(parents=True)
            (d / "README.md").write_text("hello\n")
            self.assertEqual(scan_roots({"claude": os.path.join(tmp, "claude")}), [])

    def test_missing_description_is_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "claude" / "no-desc"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text("---\nname: no-desc\n---\nBody.\n")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            self.assertEqual(len(skills), 1)
            self.assertIn("missing-description", skills[0].issues)

    def test_no_frontmatter_falls_back_to_dir_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill_no_frontmatter(tmp, "claude", "plain-skill")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            self.assertEqual(skills[0].name, "plain-skill")
            self.assertIn("First line body", skills[0].description)

    def test_managed_plugin_path_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "plug-skill", "A plugin skill",
                       subdir="plugins")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            self.assertTrue(skills[0].managed)

    def test_missing_root_is_skipped_not_error(self):
        self.assertEqual(scan_roots({"claude": "/nonexistent-xyz-123"}), [])


if __name__ == "__main__":
    unittest.main()
