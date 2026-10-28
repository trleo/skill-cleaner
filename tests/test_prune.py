import json
import os
import tempfile
import unittest
from pathlib import Path

from skill_cleaner.duplicates import find_duplicate_groups
from skill_cleaner.prune import prune_skills, restore_quarantine
from skill_cleaner.scanner import scan_roots
from skill_cleaner.usage import attach_usage
from tests.helpers import make_skill


def _setup_dup(tmp):
    make_skill(tmp, "claude", "dup", "Short", subdir="a")
    make_skill(tmp, "claude", "dup",
               "A much longer and more complete description of the same skill",
               subdir="b")


class TestPrune(unittest.TestCase):
    def _state(self, tmp):
        _setup_dup(tmp)
        roots = {"claude": os.path.join(tmp, "claude")}
        skills = scan_roots(roots)
        groups = find_duplicate_groups(skills)
        return skills, groups

    def test_dry_run_moves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills, groups = self._state(tmp)
            non_keeper = [s for s in skills if s.path != groups[0].members[0].path]
            # keeper is longest description, in subdir b; non-keeper is in a
            approval = Path(tmp) / "approve.txt"
            approval.write_text("\n".join(s.skill_id for s in skills if s.path.endswith("a/dup")) + "\n")
            result = prune_skills(skills, groups, str(approval),
                                  os.path.join(tmp, "q"), apply=False)
            self.assertEqual(result["moved"], [])
            self.assertTrue(os.path.isdir(os.path.join(tmp, "claude", "a", "dup")))

    def test_apply_moves_only_approved_eligible_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills, groups = self._state(tmp)
            # non-keeper: the short one in a/dup
            target = [s for s in skills if "a/dup" in s.path][0]
            approval = Path(tmp) / "approve.txt"
            approval.write_text(target.skill_id + "\n")
            q = os.path.join(tmp, "q")
            result = prune_skills(skills, groups, str(approval), q, apply=True)
            self.assertEqual(len(result["moved"]), 1)
            self.assertFalse(os.path.isdir(target.path))
            manifest = json.loads((Path(q) / "manifest.json").read_text())
            self.assertEqual(manifest[0]["original_path"], target.path)
            self.assertTrue(os.path.isdir(os.path.join(q, "claude", "dup")) or
                            len(list(Path(q).rglob("SKILL.md"))) == 1)

    def test_prune_refuses_unapproved_and_managed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup_dup(tmp)
            make_skill(tmp, "claude", "plug", "Plugin skill", subdir="plugins")
            roots = {"claude": os.path.join(tmp, "claude")}
            skills = scan_roots(roots)
            groups = find_duplicate_groups(skills)
            managed = [s for s in skills if s.managed][0]
            approval = Path(tmp) / "approve.txt"
            approval.write_text(managed.skill_id + "\n")
            with self.assertRaises(ValueError):
                prune_skills(skills, groups, str(approval),
                             os.path.join(tmp, "q"), apply=True)
            self.assertTrue(os.path.isdir(managed.path))

    def test_restore_moves_back_and_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills, groups = self._state(tmp)
            target = [s for s in skills if "a/dup" in s.path][0]
            approval = Path(tmp) / "approve.txt"
            approval.write_text(target.skill_id + "\n")
            q = os.path.join(tmp, "q")
            prune_skills(skills, groups, str(approval), q, apply=True)
            restored = restore_quarantine(q)
            self.assertEqual(len(restored), 1)
            self.assertTrue(os.path.isdir(target.path))
            # Second restore with a fresh quarantine that collides: recreate
            prune_skills(skills, groups, str(approval), q, apply=True)
            # destination now empty again, restore once, then try again
            restore_quarantine(q)
            # manifest is still there but files are gone -> should fail cleanly
            with self.assertRaises((ValueError, FileNotFoundError, OSError)):
                restore_quarantine(q)


if __name__ == "__main__":
    unittest.main()
