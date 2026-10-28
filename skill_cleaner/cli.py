"""Command-line interface for Skill Cleaner."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .duplicates import find_duplicate_groups
from .prune import prune_skills, restore_quarantine
from .report import build_report, write_report
from .scanner import scan_roots
from .usage import attach_usage

DEFAULT_ROOTS = {
    "claude": os.path.join(os.path.expanduser("~"), ".claude", "skills"),
    "cursor": os.path.join(os.path.expanduser("~"), ".cursor", "skills"),
    "antigravity": os.path.join(os.path.expanduser("~"), ".gemini",
                                "antigravity", "skills"),
}


def _infer_tool(path: str) -> str:
    parts = {p for p in path.replace(os.sep, "/").lower().split("/") if p}
    if "antigravity" in parts or ".gemini" in parts:
        return "antigravity"
    if "cursor" in parts or ".cursor" in parts:
        return "cursor"
    if "claude" in parts or ".claude" in parts:
        return "claude"
    return "custom"


def _collect_roots(args) -> dict:
    roots = {}
    for tool_path in getattr(args, "tool_root", []) or []:
        if "=" not in tool_path:
            raise ValueError(f"--tool-root must be tool=path, got {tool_path!r}")
        tool, path = tool_path.split("=", 1)
        roots[tool.strip()] = path.strip()
    for path in getattr(args, "root", []) or []:
        roots.setdefault(_infer_tool(path), path)
    if not roots:
        roots = {tool: path for tool, path in DEFAULT_ROOTS.items()
                 if os.path.isdir(path)}
    return roots


def _scan(args):
    try:
        roots = _collect_roots(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    skills = scan_roots(roots)
    if not skills and not any(os.path.isdir(p) for p in roots.values()):
        print("error: no skill roots found", file=sys.stderr)
        return 2
    history_n = attach_usage(skills, getattr(args, "history_glob", []) or [])
    groups = find_duplicate_groups(skills)
    report = build_report(skills, groups, history_n)
    try:
        write_report(report, args.out)
    except OSError as exc:
        print(f"error: cannot write report to {args.out!r}: {exc}", file=sys.stderr)
        return 2
    s = report["summary"]
    print(f"Skills: {s['total_skills']}  Duplicate groups: {s['duplicate_groups']}  "
          f"Prune-eligible: {s['prune_eligible']}")
    print(f"Report: {args.out}/report.md, {args.out}/report.json")
    return 0


def _prune(args):
    try:
        roots = _collect_roots(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    skills = scan_roots(roots)
    if not skills:
        print("error: no skills found under the given roots", file=sys.stderr)
        return 2
    attach_usage(skills, getattr(args, "history_glob", []) or [])
    groups = find_duplicate_groups(skills)
    try:
        result = prune_skills(skills, groups, args.approve,
                              args.quarantine, apply=args.apply)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.apply:
        print(f"Moved to quarantine: {len(result['moved'])}")
        for skill_id in result["moved"]:
            print(f"  - {skill_id}")
    else:
        print("Dry run — nothing moved. Add --apply to move these:")
        for skill_id in result["would_move"]:
            print(f"  - {skill_id}")
    return 0


def _restore(args):
    try:
        restored = restore_quarantine(args.quarantine)
    except (ValueError, FileNotFoundError, OSError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Restored: {len(restored)}")
    for skill_id in restored:
        print(f"  - {skill_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-cleaner",
        description="Audit, deduplicate, and prune AI agent skills across tools.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Scan roots and write a report")
    scan.add_argument("--root", action="append", default=None)
    scan.add_argument("--tool-root", action="append", default=None)
    scan.add_argument("--history-glob", action="append", default=None)
    scan.add_argument("--out", default="skill-cleaner-report")

    prune = sub.add_parser("prune", help="Prune approved skills to quarantine")
    prune.add_argument("--root", action="append", default=None)
    prune.add_argument("--tool-root", action="append", default=None)
    prune.add_argument("--history-glob", action="append", default=None)
    prune.add_argument("--approve", required=True)
    prune.add_argument("--quarantine", required=True)
    prune.add_argument("--apply", action="store_true")
    prune.add_argument("--out", default="skill-cleaner-report")

    restore = sub.add_parser("restore", help="Restore from quarantine")
    restore.add_argument("--quarantine", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _scan(args)
    if args.command == "prune":
        return _prune(args)
    if args.command == "restore":
        return _restore(args)
    print("error: a subcommand is required: scan, prune, or restore",
          file=sys.stderr)
    return 2
