# Skill Cleaner

**Find the duplicate and unused AI agent skills hiding in Claude Code, Cursor, and Google Antigravity — and remove only the ones you approve, by quarantine, never by delete.**

> **Short answer:** Skill Cleaner scans your skill roots, groups duplicates by exact name, exact content, and keyword overlap, flags unused candidates only when you supply history to check against, recommends one keeper per group, and prunes approved skills to a quarantine folder you can restore from.

No model call. No API key. No dependencies. Python 3.10+, standard library only.

## Contents

- [Quick answer](#quick-answer)
- [Quickstart](#quickstart)
- [What it finds](#what-it-finds)
- [How to read the report](#how-to-read-the-report)
- [Prune with approval](#prune-with-approval)
- [Restore](#restore)
- [All options](#all-options)
- [What this does not do](#what-this-does-not-do)
- [Frequently asked questions](#frequently-asked-questions)
- [Development](#development)

## Quick answer

**What is Skill Cleaner?**
A command-line tool, plus an agent skill (`skills/skill-cleaner/SKILL.md`) you can install into Claude, Cursor, or Antigravity, that audits the skills already installed on your machine.

**What do I get?**
A report in two formats with the same results:

- `report.md` — human-readable, with duplicate groups, unused candidates, and an approval list
- `report.json` — machine-readable, for further tooling

**Does it delete anything?**
No. There is no delete flag. Pruning moves approved skills to a quarantine directory with a manifest, and `restore` moves them back.

**Who is it for?**
Anyone whose skill list has grown over time — the same skill installed under several names, near-duplicates that do the same job, and skills that are never used.

## Quickstart

**1. Scan your default roots (Claude, Cursor, Antigravity under your home):**

```bash
python -m skill_cleaner scan --out ./skill-cleaner-report
```

**2. Read the report:**

```bash
cat skill-cleaner-report/report.md
```

**3. Try it on the demo roots in this repo:**

```bash
python -m skill_cleaner scan --root /tmp/demo-claude --out /tmp/demo-report
```

See [Prune with approval](#prune-with-approval) before removing anything.

## What it finds

| Signal | How it is detected | What it means |
|---|---|---|
| Exact-name duplicate | Same normalised name in the same tool | Same skill, twice |
| Exact-content duplicate | Same SKILL.md body, different names | Same instructions, different label |
| Keyword-overlap duplicate | Jaccard ≥ 0.30 on name + description tokens, stopwords removed | Same purpose, different wording — a candidate, not proof |
| Broken skill | Missing description, or invalid frontmatter | Will not trigger reliably |
| Managed skill | Path under `plugins/`, `marketplace/`, or similar | Report only, never a prune candidate |
| Used / unused candidate / unknown | Skill name mentioned in supplied history files | Without history, usage is always "unknown" |

**Within-tool vs cross-tool — the important distinction:**

- **Within one tool** (two copies in `~/.claude/skills`): a duplicate is waste. Non-keepers are prune candidates.
- **Across tools** (the same skill in Claude *and* Cursor): that is normally expected, because each tool needs its own copy. Cross-tool groups are reported as "shared" and are **not** candidates on their own. They only become candidates if they are also unused candidates and you explicitly approve them.

**Keeper rule (deterministic):** not managed, then longest description, then most recently modified SKILL.md, then alphabetical path.

## How to read the report

| Field | Meaning |
|---|---|
| Total skills | Skills found across all scanned roots |
| Duplicate groups | Groups of 2+ skills flagged by any duplicate signal |
| Prune-eligible | Skills that are non-keepers in a within-tool group, or unused candidates, and not managed |
| History files searched | How many history files usage was checked against — 0 means all usage is "unknown" |

## Prune with approval

**Step 1 — Write an approval file, one skill ID per line:**

```
# skills I approve for quarantine
claude/a/old-seo-audit
claude/unused-helper
```

Skill IDs are exactly as shown in the report (`tool/relative-path`).

**Step 2 — Dry run first (nothing moves):**

```bash
python -m skill_cleaner prune --approve approve.txt --quarantine ./skill-quarantine
```

**Step 3 — Apply, only after you confirm the dry-run list:**

```bash
python -m skill_cleaner prune --approve approve.txt --quarantine ./skill-quarantine --apply
```

Prune refuses, before moving anything, if an approval ID is not found, ambiguous, managed, or not prune-eligible. Fix the approval file and re-run.

## Restore

```bash
python -m skill_cleaner restore --quarantine ./skill-quarantine
```

This moves every quarantined skill back to its original path from `manifest.json`, and refuses if a destination already exists.

## All options

| Command | Key options |
|---|---|
| `scan` | `--root <dir>` (repeatable, tool inferred), `--tool-root <tool>=<dir>` (repeatable), `--history-glob <pattern>` (repeatable), `--out <dir>` (default: `./skill-cleaner-report`) |
| `prune` | Same root/history options, plus `--approve <file>` (required), `--quarantine <dir>` (required), `--apply` (without it, dry run only) |
| `restore` | `--quarantine <dir>` (required) |
| (global) | `--version` |

Default roots, when no `--root`/`--tool-root` is given:

- Claude: `~/.claude/skills`
- Cursor: `~/.cursor/skills`
- Antigravity: `~/.gemini/antigravity/skills`

Missing default roots are skipped, not an error. Exit codes: `0` = success, `1` = prune/restore failure, `2` = usage error.

## What this does not do

- It does not delete skills, install skills, or sync one skill into every tool.
- It does not prove two keyword-overlap skills are interchangeable — you decide per group.
- It does not know a skill is unused without history. "Unknown" is not "unused".
- It does not touch plugin/marketplace-managed skills, which would be reinstalled or overwritten anyway.

## Frequently asked questions

### Will it delete a skill I still need?

No, in two ways: it only moves skills you explicitly list in an approval file, and it moves them to quarantine, not delete. `restore` brings them back.

### I have the same skill in Claude and Cursor. Will it tell me to remove one?

No, not on its own. That is reported as a shared cross-tool group. It only becomes a candidate if it is also unused in your supplied history and you approve it.

### How does it know a skill is unused?

Only if you supply history, e.g. `--history-glob "~/.claude/projects/**/*.jsonl"`. It searches those files for the skill's name. With no history, every skill is "unknown".

### Can I use it as an agent skill, not just a CLI?

Yes. Install `skills/skill-cleaner/SKILL.md` into your tool, then ask the agent to clean up your skills. The skill tells the agent to run the CLI, ask for approval per group, dry-run first, and never delete by hand.

### What if I approve the wrong skill?

Run `restore --quarantine <dir>` before you install anything over its original path. The manifest records the exact original path.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests use the standard library `unittest` only, and follow TDD: every feature started as a failing test. The suite covers scanning and frontmatter, all three duplicate signals, keeper selection, usage with and without history, cross-tool sharing, dry-run vs apply, managed-skill refusal, and restore.
