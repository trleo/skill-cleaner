import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import make_skill


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "skill_cleaner", *args],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )


class TestCLI(unittest.TestCase):
    def test_version(self):
        proc = run_cli("--version")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "0.1.0")

    def test_scan_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "react-dev", "Build React components")
            out = os.path.join(tmp, "report")
            proc = run_cli("scan", "--root", os.path.join(tmp, "claude"),
                           "--out", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads((Path(out) / "report.json").read_text())
            self.assertEqual(data["summary"]["total_skills"], 1)
            self.assertTrue((Path(out) / "report.md").exists())

    def test_scan_no_roots_exits_2(self):
        proc = run_cli("scan", "--root", "/nonexistent-xyz-123")
        self.assertEqual(proc.returncode, 2)

    def test_prune_dry_run_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_skill(tmp, "claude", "dup", "Short", subdir="a")
            make_skill(tmp, "claude", "dup",
                       "A much longer and more complete description",
                       subdir="b")
            approval = Path(tmp) / "approve.txt"
            approval.write_text("claude/a/dup\n")
            proc = run_cli("prune", "--root", os.path.join(tmp, "claude"),
                           "--approve", str(approval),
                           "--quarantine", os.path.join(tmp, "q"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "claude", "a", "dup")))


if __name__ == "__main__":
    unittest.main()
