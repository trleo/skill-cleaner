"""Approval-gated quarantine prune, and restore."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from .duplicates import keeper_for


def eligible_skills(skills: list, groups: list) -> dict:
    """Return {skill_id: reason} for prune-eligible skills.

    Eligible = non-keeper in a within-tool duplicate pair, or an
    unused candidate. Managed skills are never eligible. A cross-tool
    group alone does not make a skill eligible.
    """
    eligible = {}
    keeper_paths = {keeper_for(g).path for g in groups}
    for group in groups:
        for skill in group.members:
            if skill.path in keeper_paths:
                continue
            # Within-tool pair? Another member with the same tool.
            if any(other.tool == skill.tool and other.path != skill.path
                   for other in group.members):
                eligible[skill.skill_id] = "duplicate-non-keeper"
    for skill in skills:
        if skill.usage == "unused-candidate" and not skill.managed:
            eligible.setdefault(skill.skill_id, "unused-candidate")
    # Managed skills are never eligible, even if unused.
    for skill in skills:
        if skill.managed:
            eligible.pop(skill.skill_id, None)
    return eligible


def _read_approval(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read approval file {path!r}: {exc}") from exc
    ids = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line)
    if not ids:
        raise ValueError("approval file contains no skill IDs")
    return ids


def _is_within(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(parent)]) == os.path.realpath(parent)
    except ValueError:
        return False


def _overlaps(a: str, b: str) -> bool:
    """True if either path is equal to, inside, or containing the other."""
    ra, rb = os.path.realpath(a), os.path.realpath(b)
    return ra == rb or _is_within(a, b) or _is_within(b, a)


def prune_skills(skills: list, groups: list, approval_path: str,
                 quarantine_dir: str, apply: bool = False) -> dict:
    """Prune approved, eligible skills. Dry-run unless apply=True.

    Returns {"would_move": [...], "moved": [...], "eligible": {...}}.
    Raises ValueError for unapproved, ineligible, managed, missing,
    ambiguous, colliding, or overlapping IDs — before moving anything.
    """
    eligible = eligible_skills(skills, groups)
    approved = _read_approval(approval_path)
    by_id = {}
    for skill in skills:
        by_id.setdefault(skill.skill_id, []).append(skill)
    targets = []
    for skill_id in approved:
        matches = by_id.get(skill_id, [])
        if not matches:
            raise ValueError(f"approval ID not found: {skill_id}")
        if len(matches) > 1:
            raise ValueError(f"approval ID is ambiguous: {skill_id}")
        skill = matches[0]
        if skill_id not in eligible:
            raise ValueError(f"skill is not prune-eligible: {skill_id}")
        targets.append(skill)

    # Pre-validate everything before moving anything (Bug 1, Bug 6):
    # quarantine must not overlap any target, and every destination
    # must be free. Destination includes the skill's relative path,
    # so two same-named skills in different subdirs do not collide.
    destinations = []
    for skill in targets:
        if _overlaps(quarantine_dir, skill.path):
            raise ValueError(
                f"quarantine directory overlaps skill path: {quarantine_dir!r} vs {skill.path!r}")
        dest = os.path.join(quarantine_dir, skill.tool, skill._rel)
        if os.path.exists(dest):
            raise ValueError(f"quarantine destination already exists: {dest}")
        destinations.append(dest)

    result = {"would_move": [s.skill_id for s in targets],
              "moved": [], "eligible": eligible}
    if not apply:
        return result

    os.makedirs(quarantine_dir, exist_ok=True)
    manifest_path = os.path.join(quarantine_dir, "manifest.json")
    existing = []
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ValueError(f"cannot read existing manifest {manifest_path!r}: {exc}") from exc
        if not isinstance(existing, list):
            raise ValueError("existing manifest is not a list")
    # Drop stale entries whose quarantined skill is no longer there
    # (e.g. already restored): otherwise a later restore would try
    # to move the same skill twice from one manifest.
    manifest = [e for e in existing
                if isinstance(e, dict) and e.get("quarantine_path")
                and os.path.isdir(e["quarantine_path"])]
    try:
        for skill, dest in zip(targets, destinations):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(skill.path, dest)
            manifest.append({
                "skill_id": skill.skill_id,
                "tool": skill.tool,
                "name": skill.name,
                "original_path": skill.path,
                "quarantine_path": dest,
                "moved_at": datetime.now(timezone.utc).isoformat(),
                "reason": eligible[skill.skill_id],
            })
            result["moved"].append(skill.skill_id)
    except (OSError, shutil.Error) as exc:
        raise ValueError(f"failed to move a skill to quarantine: {exc}") from exc
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return result


def restore_quarantine(quarantine_dir: str) -> list:
    """Move quarantined skills back to their original paths.

    Validates the whole manifest before moving anything: it must be
    a list of dicts with all required string fields, and every
    quarantine_path must lie inside the quarantine directory.
    """
    manifest_path = os.path.join(quarantine_dir, "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except OSError as exc:
        raise ValueError(f"cannot read manifest in {quarantine_dir!r}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"manifest is not valid JSON: {exc}") from exc
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("manifest is empty or not a list; nothing to restore")
    required = {"skill_id", "tool", "name", "original_path", "quarantine_path"}
    for entry in manifest:
        if not isinstance(entry, dict) or not required.issubset(entry.keys()):
            raise ValueError("manifest entry is missing required fields")
        if not all(isinstance(entry[k], str) and entry[k] for k in required):
            raise ValueError("manifest entry has non-string or empty required fields")
        if not _is_within(entry["quarantine_path"], quarantine_dir):
            raise ValueError(
                f"manifest quarantine_path is outside the quarantine directory: {entry['quarantine_path']!r}")
    # Duplicate entries for the same skill/path would make restore
    # move the same directory twice; refuse them up front.
    seen_q = set()
    seen_o = set()
    for entry in manifest:
        if entry["quarantine_path"] in seen_q or entry["original_path"] in seen_o:
            raise ValueError("manifest contains duplicate entries")
        seen_q.add(entry["quarantine_path"])
        seen_o.add(entry["original_path"])
    # Pre-validate all moves before moving anything.
    for entry in manifest:
        if not os.path.isdir(entry["quarantine_path"]):
            raise FileNotFoundError(
                f"quarantined skill not found: {entry['quarantine_path']}")
        if os.path.exists(entry["original_path"]):
            raise ValueError(f"destination already exists: {entry['original_path']}")
    restored = []
    for entry in manifest:
        os.makedirs(os.path.dirname(entry["original_path"]), exist_ok=True)
        shutil.move(entry["quarantine_path"], entry["original_path"])
        restored.append(entry["skill_id"])
    return restored
