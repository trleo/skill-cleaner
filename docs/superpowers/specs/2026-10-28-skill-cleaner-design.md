# Skill Cleaner — Design

## Intent

People install AI agent skills over time into Claude Code, Cursor, and
Google Antigravity. The result is sprawl: the same skill under several
names, near-duplicates that do the same job, and skills that are never
used. Skill Cleaner finds that sprawl, shows it with evidence, and
removes only what the user explicitly approves — by quarantine, never
by permanent delete.

Approved by the user on 2026-10-28: build as a new GitHub project,
named "Skill Cleaner".

## Goals

- Scan skill roots for Claude, Cursor, and Antigravity, plus any custom
  root the user names.
- Inventory every skill: tool, path, name, description, size, and
  whether it is managed (plugin/marketplace) or user-installed.
- Find duplicates: exact name, exact SKILL.md content, and keyword
  overlap (Jaccard >= 0.30 on name + description tokens, stopwords
  removed) — the last one catches same-purpose skills with different
  names, which hash-only tools miss.
- Find unused skills only when the user supplies history to check
  against. Without history, usage is "unknown", never "unused".
- Recommend one keeper per duplicate group, by a deterministic rule.
- Prune only with explicit approval, and only by moving to quarantine
  with a manifest, so every removal is reversible with `restore`.
- Work offline, with the Python standard library only, no API key,
  no model call, no network.

## Non-goals / anti-goals

- Not a skill marketplace, not a skill installer, not a sync tool.
  It does not copy one skill into every tool.
- Not a permanent deleter. There is no `--delete` flag. Quarantine
  plus restore is the whole removal model.
- Not a semantic judge. Keyword overlap is a candidate signal, not a
  proof that two skills are interchangeable; the user decides per group.
- Not a token-cost optimiser for model sessions. Size and description
  length are reported as context, not as a score to maximise.

## Key distinction: within-tool vs cross-tool duplicates

This is the decision that makes the tool honest, and it is easy to
get wrong:

- **Within one tool** (e.g. two copies of a React skill in
  `~/.claude/skills`): a duplicate is waste. Non-keepers are removal
  candidates.
- **Across tools** (the same skill in Claude *and* Cursor): that is
  normally *expected*, because each tool needs its own copy. A
  cross-tool group is reported as "shared", and is **not** a removal
  candidate on its own. It only becomes eligible if it is also an
  unused candidate (history supplied, zero mentions) and the user
  explicitly approves that skill.

## Keeper rule (deterministic)

For each duplicate group, the keeper is the first skill after sorting
by: (1) not managed, (2) longest description, (3) most recently
modified SKILL.md, (4) alphabetical path. No randomness, no model.

## Usage evidence

- `--history-glob <pattern>` (repeatable): text files to search for
  skill-name mentions, e.g. Claude project history `*.jsonl`.
  Files over 200 KB are skipped for content, binary files are skipped.
- A skill is `used` if its directory name or frontmatter name appears
  (case-insensitive substring) in at least one searched file.
- Otherwise, with history supplied, it is `unused-candidate`.
- Without history, it is `unknown`. The report always states how many
  history files were searched, so "unused" is never overstated.

## Prune safety rules

A skill is prune-eligible only if it is: (a) a non-keeper in a
within-tool duplicate group, or (b) an unused candidate — and it is
never managed, and never a path that is a scan root itself.

Prune works in two steps, always:

1. `scan` writes a report with skill IDs (`tool/relative-name`).
2. `prune` reads an approval file (one skill ID per line, comments
   with `#` allowed), refuses any ID that is not eligible, not found,
   or ambiguous, and — unless `--apply` is given — only prints what
   it *would* move. With `--apply`, it moves approved skills to
   `--quarantine` and writes `manifest.json` there.

`restore --quarantine <dir>` moves skills back to their original
paths from the manifest, and refuses if a destination already exists.

## CLI contract

```
python -m skill_cleaner scan --root <dir> [--root ...]
    [--tool-root <tool>=<dir> ...] [--history-glob <pattern> ...]
    [--out <dir>] [--include-cross-tool]
python -m skill_cleaner prune --root ... [--approve <file>]
    [--quarantine <dir>] [--apply] [--out <dir>]
python -m skill_cleaner restore --quarantine <dir>
python -m skill_cleaner --version
```

- Default roots, when no `--root`/`--tool-root` is given: the
  Claude, Cursor, and Antigravity roots under the user's home, if
  they exist. Missing default roots are skipped, not an error.
- Default `--out` is `./skill-cleaner-report`.
- Exit codes: 0 = success (scan always succeeds if at least one root
  was scanned; prune dry-run is success), 1 = prune/restore failure
  (e.g. a move failed), 2 = usage error (no roots found, bad
  approval file, destination already exists on restore, etc.).

## Agent skill

The repo also ships `skills/skill-cleaner/SKILL.md`, the agent
playbook for this workflow, so a user can install *this* skill into
Claude, Cursor, or Antigravity and then invoke it to clean their
other skills. The skill tells the agent to run the CLI, never to
delete by hand, and to stop and ask for approval before `--apply`.

## Prior art (researched 2026-10-28)

Skills Janitor (Claude Code, keyword Jaccard duplicates, dry-run,
confirmation before removal) is the closest prior tool, but it is
not cross-tool for Antigravity + Cursor, and its duplicate signal is
keyword-only. Skill Proof and Skills Hub solve cross-tool *sync*,
not unused-skill pruning. Skill Cleaner is the gap between them:
cross-tool inventory, duplicate + unused candidates, approval-gated
quarantine, and restore.
