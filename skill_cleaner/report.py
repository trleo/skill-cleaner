"""Report rendering: JSON (machine) and Markdown (human)."""

from __future__ import annotations

import json
import os

from .duplicates import keeper_for
from .prune import eligible_skills


def build_report(skills, groups, history_files_searched: int) -> dict:
    eligible = eligible_skills(skills, groups)
    return {
        "summary": {
            "total_skills": len(skills),
            "tools": sorted({s.tool for s in skills}),
            "duplicate_groups": len(groups),
            "within_tool_groups": sum(1 for g in groups if g.has_within_tool_pair),
            "cross_tool_groups": sum(1 for g in groups if g.cross_tool),
            "broken_skills": sum(1 for s in skills if s.issues),
            "managed_skills": sum(1 for s in skills if s.managed),
            "used": sum(1 for s in skills if s.usage == "used"),
            "unused_candidates": sum(1 for s in skills if s.usage == "unused-candidate"),
            "unknown_usage": sum(1 for s in skills if s.usage == "unknown"),
            "prune_eligible": len(eligible),
            "total_size_bytes": sum(s.size_bytes for s in skills),
            "history_files_searched": history_files_searched,
        },
        "skills": [{
            "skill_id": s.skill_id, "tool": s.tool, "name": s.name,
            "description": s.description, "path": s.path,
            "size_bytes": s.size_bytes, "managed": s.managed,
            "issues": s.issues, "usage": s.usage,
            "prune_eligible": s.skill_id in eligible,
            "prune_reason": eligible.get(s.skill_id, ""),
        } for s in sorted(skills, key=lambda x: x.path)],
        "duplicate_groups": [{
            "kind": g.kind, "within_tool": g.has_within_tool_pair,
            "cross_tool": g.cross_tool,
            "keeper": keeper_for(g).skill_id,
            "members": [m.skill_id for m in g.members],
        } for g in groups],
    }


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = ["# Skill Cleaner report", "",
             f"**Total skills:** {s['total_skills']}  |  "
             f"**Duplicate groups:** {s['duplicate_groups']}  |  "
             f"**Prune-eligible:** {s['prune_eligible']}  |  "
             f"**History files searched:** {s['history_files_searched']}", "",
             "## What to do next",
             "",
             "1. Review the duplicate groups and unused candidates below.",
             "2. Write the skill IDs you approve into an approval file, one per line.",
             "3. Run `prune` without `--apply` first (dry run), then with `--apply`.",
             "4. Removed skills go to quarantine, not delete — `restore` brings them back.",
             ""]
    if report["duplicate_groups"]:
        lines += ["## Duplicate groups", ""]
        for g in report["duplicate_groups"]:
            if g["within_tool"] and g["cross_tool"]:
                scope = "within one tool and across tools"
            elif g["within_tool"]:
                scope = "within one tool"
            else:
                scope = "across tools only (shared, not a removal candidate on its own)"
            lines.append(f"- **{g['kind']}** ({scope}) — keep `{g['keeper']}`, members: " +
                         ", ".join(f"`{m}`" for m in g["members"]))
        lines.append("")
    unused = [x for x in report["skills"] if x["usage"] == "unused-candidate"]
    if unused:
        lines += ["## Unused candidates (history supplied, zero mentions)", ""]
        for x in unused:
            lines.append(f"- `{x['skill_id']}` — {x['description']}")
        lines.append("")
    eligible = [x for x in report["skills"] if x["prune_eligible"]]
    if eligible:
        lines += ["## Approval list (copy the IDs you want to prune)", ""]
        for x in eligible:
            lines.append(f"- `{x['skill_id']}` ({x['prune_reason']})")
        lines.append("")
    lines += ["## All skills", "",
              "| Skill | Tool | Usage | Size | Managed | Issues |",
              "|---|---|---|---|---|---|"]
    for x in report["skills"]:
        lines.append(f"| `{x['skill_id']}` | {x['tool']} | {x['usage']} | "
                     f"{x['size_bytes']} | {x['managed']} | {', '.join(x['issues']) or '-'} |")
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as handle:
        handle.write(render_markdown(report))
