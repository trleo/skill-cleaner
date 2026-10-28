---
name: skill-cleaner
description: Audit, deduplicate, and prune installed AI agent skills across Claude Code, Cursor, and Google Antigravity, with user approval and quarantine, never permanent delete. Use when the user mentions cleaning up skills, duplicate skills, unused skills, skill sprawl, or too many skills installed.
---

# Skill Cleaner

Clean up installed agent skills safely. Never delete a skill by hand,
and never prune without explicit approval for each skill.

## When to use this skill

- The user says their skills have grown, duplicated, or are hardly used
- The user asks to find duplicate or unused skills
- The user asks to remove, clean, or prune skills

## Workflow

1. **Scan first, always.** Run the CLI from the repo (or installed copy):
   ```bash
   python -m skill_cleaner scan --out ./skill-cleaner-report
   ```
   With no `--root`, it scans the Claude, Cursor, and Antigravity
   roots under the user's home, if they exist. On the user's PC,
   use their actual home paths, including Windows paths.
   If the user wants history-based unused detection, add
   `--history-glob` with their history files, and say how many
   files were searched — without history, usage is "unknown",
   never "unused".

2. **Read the report, do not guess.** Open `report.md`. Explain:
   - within-tool duplicate groups (removal candidates)
   - cross-tool shared groups (normal, not candidates on their own)
   - unused candidates, if history was supplied
   - managed/plugin skills, which are never candidates

3. **Ask for approval, per group.** Show the keeper and the
   non-keepers, and why each non-keeper was flagged. The user
   approves by editing an approval file (one skill ID per line),
   or by naming the IDs in chat, which you write into that file
   exactly as shown. Do not approve on their behalf, and do not
   bundle a group they did not approve.

4. **Dry run, then apply.** First run `prune` without `--apply`
   and show what would move. Only after the user confirms that
   list, run with `--apply` and a `--quarantine` directory.
   Quarantine is the only removal: no `rm`, no permanent delete.

5. **Verify and offer restore.** After applying, re-run `scan`
   and show what changed. Tell the user `restore --quarantine <dir>`
   brings everything back, and offer to restore any item they
   regret.

## Safety rules

- Managed/plugin/marketplace skills: report only, never prune.
- Cross-tool shared skills: not candidates on their own.
- Unknown usage: never presented as unused.
- If a prune step refuses an ID (ineligible, managed, ambiguous,
  not found), stop, explain that ID, and do not move anything else
  from that batch until the user fixes the approval file.
- If in doubt about a skill's purpose, ask — do not prune it.
