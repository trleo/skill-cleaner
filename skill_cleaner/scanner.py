"""Scan skill roots and parse SKILL.md frontmatter (stdlib only)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

MANAGED_PARTS = {"plugins", "marketplace", "node_modules"}


@dataclass
class Skill:
    tool: str
    name: str
    description: str
    path: str
    skill_md: str
    size_bytes: int = 0
    managed: bool = False
    issues: list = field(default_factory=list)
    usage: str = "unknown"
    content_hash: str = ""

    @property
    def skill_id(self) -> str:
        """Stable ID shown in reports and approval files: tool/rel-path."""
        # skill_id is tool + path relative to its tool root's parent,
        # falling back to the directory name if that cannot be derived.
        return f"{self.tool}/{self._rel}"

    # Set by scan_roots; not part of the public constructor contract.
    _rel: str = ""


def _parse_frontmatter(text: str):
    """Return (name, description) from YAML frontmatter, or (None, None).

    Handles folded (`>`) and literal (`|`) block scalars for the
    description, which are common in real SKILL.md files.
    """
    if not text.startswith("---"):
        return None, None
    lines = text.splitlines()
    # Find closing --- on its own line.
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, None
    name = None
    description = None
    i = 1
    while i < end:
        line = lines[i]
        if ":" not in line:
            i += 1
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if value in (">", "|", ">-", "|-", ">+", "|+"):
            # Collect following indented lines as the scalar.
            collected = []
            j = i + 1
            while j < end and (lines[j].startswith(" ") or lines[j].startswith("\t") or not lines[j].strip()):
                if lines[j].strip():
                    collected.append(lines[j].strip())
                j += 1
            value = " ".join(collected) if value.startswith(">") else "\n".join(collected)
            i = j
        else:
            value = value.strip('"').strip("'")
            i += 1
        if key == "name":
            name = value or None
        elif key == "description":
            description = value or None
    return name, description


def _is_managed(path: str) -> bool:
    parts = {p.lower() for p in path.replace(os.sep, "/").split("/")}
    return bool(parts & MANAGED_PARTS)


def _body_text(text: str) -> str:
    """SKILL.md body after the frontmatter block, or the whole text."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1:])
    return text


def _normalised_hash(text: str) -> str:
    body = _body_text(text)
    norm = "\n".join(line.rstrip() for line in body.replace("\r\n", "\n").split("\n"))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def scan_roots(roots: dict) -> list:
    """Scan {tool: root_dir} and return a list of Skill objects.

    A skill is any directory under a root that contains a SKILL.md
    file, at any depth (e.g. plugins/<plugin>/skills/<skill>/).
    Once a directory is recognised as a skill, its subdirectories
    are not searched for further skills. Directories without
    SKILL.md are ignored, not reported as broken.
    """
    skills = []
    for tool, root in sorted(roots.items()):
        if not os.path.isdir(root):
            continue
        candidates = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Deterministic order, and skip version-control/cache dirs.
            dirnames[:] = sorted(d for d in dirnames
                                 if d not in {".git", "__pycache__"})
            if "SKILL.md" in filenames:
                rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
                if rel != ".":
                    candidates.append((rel, dirpath,
                                       os.path.join(dirpath, "SKILL.md")))
                    dirnames[:] = []  # do not descend into a skill dir
        candidates.sort(key=lambda c: c[0])
        for rel, skill_dir, md_path in candidates:
                try:
                    with open(md_path, encoding="utf-8", errors="replace") as handle:
                        text = handle.read()
                except OSError:
                    continue
                name, description = _parse_frontmatter(text)
                issues = []
                if name is None:
                    if text.startswith("---"):
                        issues.append("missing-name")
                    name = os.path.basename(skill_dir)
                if text.startswith("---") and not description:
                    issues.append("missing-description")
                if not description:
                    # Fallback: first non-empty body line.
                    body_lines = [l.strip() for l in text.splitlines()
                                  if l.strip() and l.strip() != "---"
                                  and not l.strip().startswith("name:")
                                  and not l.strip().startswith("description:")]
                    description = body_lines[0] if body_lines else ""
                    if not description:
                        issues.append("missing-description")
                size = 0
                for dirpath, _dirs, files in os.walk(skill_dir):
                    for fname in files:
                        try:
                            size += os.path.getsize(os.path.join(dirpath, fname))
                        except OSError:
                            pass
                skill = Skill(
                    tool=tool, name=name, description=description,
                    path=skill_dir, skill_md=md_path, size_bytes=size,
                    managed=_is_managed(skill_dir), issues=issues,
                    content_hash=_normalised_hash(text),
                )
                skill._rel = rel
                skills.append(skill)
    return skills
