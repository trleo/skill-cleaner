import json
import os
import tempfile
import unittest
from pathlib import Path

from skill_cleaner.duplicates import find_duplicate_groups
from skill_cleaner.prune import prune_skills, restore_quarantine
from skill_cleaner.scanner import scan_roots, _parse_frontmatter
from skill_cleaner.usage import attach_usage
from tests.helpers import make_skill


class TestRegressions(unittest.TestCase):
    def test_quarantine_collision_two_same_basename_both_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "dup", "Short", subdir="a")
            make_skill(tmp, "claude", "dup",
                       "A much longer and more complete description", subdir="b")
            make_skill(tmp, "claude", "dup", "Short2", subdir="c")
            roots = {"claude": os.path.join(tmp, "claude")}
            skills = scan_roots(roots)
            groups = find_duplicate_groups(skills)
            approval = Path(tmp) / "approve.txt"
            approval.write_text("claude/a/dup\nclaude/c/dup\n")
            q = os.path.join(tmp, "q")
            result = prune_skills(skills, groups, str(approval), q, apply=True)
            self.assertEqual(len(result["moved"]), 2)
            manifest = json.loads((Path(q) / "manifest.json").read_text())
            self.assertEqual(len(manifest), 2)
            self.assertEqual(len(list(Path(q).rglob("SKILL.md"))), 2)

    def test_second_prune_appends_manifest_not_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "dup", "Short", subdir="a")
            make_skill(tmp, "claude", "dup",
                       "A much longer and more complete description", subdir="b")
            make_skill(tmp, "claude", "other", "Other skill body here")
            roots = {"claude": os.path.join(tmp, "claude")}
            skills = scan_roots(roots)
            groups = find_duplicate_groups(skills)
            q = os.path.join(tmp, "q")
            approval = Path(tmp) / "approve.txt"
            approval.write_text("claude/a/dup\n")
            prune_skills(skills, groups, str(approval), q, apply=True)
            # Second prune: unused-candidate via history, for "other"
            hist = Path(tmp) / "hist.txt"
            hist.write_text("nothing relevant here\n")
            skills2 = scan_roots(roots)
            attach_usage(skills2, [str(hist)])
            groups2 = find_duplicate_groups(skills2)
            approval.write_text("claude/other\n")
            prune_skills(skills2, groups2, str(approval), q, apply=True)
            manifest = json.loads((Path(q) / "manifest.json").read_text())
            self.assertEqual(len(manifest), 2)
            restored = restore_quarantine(q)
            self.assertEqual(len(restored), 2)

    def test_usage_word_boundary_not_substring(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "used-skill", "Used skill body")
            make_skill(tmp, "claude", "unused-skill", "Unused skill body")
            hist = Path(tmp) / "hist.txt"
            hist.write_text("I used unused-skill only\n")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            attach_usage(skills, [str(hist)])
            by_name = {s.name: s.usage for s in skills}
            self.assertEqual(by_name["unused-skill"], "used")
            self.assertEqual(by_name["used-skill"], "unused-candidate")

    def test_usage_binary_after_8192_and_large_file_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "bigskill", "Big skill body")
            hist = Path(tmp) / "hist.txt"
            hist.write_text("A" * 9000 + "\x00" + "bigskill\n")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            n = attach_usage(skills, [str(hist)])
            self.assertEqual(n, 0)
            self.assertEqual(skills[0].usage, "unused-candidate")

    def test_restore_rejects_manifest_outside_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "q"
            q.mkdir()
            victim = Path(tmp) / "victim"
            victim.mkdir()
            (victim / "SKILL.md").write_text("x\n")
            manifest = [{"skill_id": "evil", "tool": "claude", "name": "evil",
                         "original_path": str(Path(tmp) / "stolen"),
                         "quarantine_path": str(victim)}]
            (q / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                restore_quarantine(str(q))
            self.assertTrue(victim.is_dir())

    def test_restore_malformed_manifest_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "q"
            q.mkdir()
            (q / "manifest.json").write_text(json.dumps({"not": "a list"}))
            with self.assertRaises(ValueError):
                restore_quarantine(str(q))

    def test_prune_refuses_quarantine_overlapping_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "dup", "Short", subdir="a")
            make_skill(tmp, "claude", "dup",
                       "A much longer and more complete description", subdir="b")
            roots = {"claude": os.path.join(tmp, "claude")}
            skills = scan_roots(roots)
            groups = find_duplicate_groups(skills)
            approval = Path(tmp) / "approve.txt"
            approval.write_text("claude/a/dup\n")
            target = [s for s in skills if "a/dup" in s.path][0]
            with self.assertRaises(ValueError):
                prune_skills(skills, groups, str(approval), target.path, apply=True)

    def test_missing_name_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "claude" / "no-name"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text("---\ndescription: Has desc, no name\n---\nBody.\n")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            self.assertIn("missing-name", skills[0].issues)

    def test_deep_plugin_skill_found_and_managed(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "deep-skill", "Deep plugin skill",
                       subdir="plugins/vendor/deep")
            skills = scan_roots({"claude": os.path.join(tmp, "claude")})
            self.assertEqual(len(skills), 1)
            self.assertTrue(skills[0].managed)

    def test_folded_description_parsed(self):
        name, desc = _parse_frontmatter(
            "---\nname: x\ndescription: >\n  folded line one\n  folded line two\n---\nBody\n")
        self.assertIn("folded line one", desc)
        self.assertIn("folded line two", desc)


if __name__ == "__main__":
    unittest.main()
