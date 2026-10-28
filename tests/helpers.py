"""Shared test helpers: build fake skill roots on disk."""

import os
from pathlib import Path


def make_skill(root, tool, name, description, body="Do the thing.\n",
                managed=False, subdir=None):
    """Create root/tool[/subdir]/name/SKILL.md and return its Path."""
    base = Path(root) / tool
    if subdir:
        base = base / subdir
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    front = f"---\nname: {name}\ndescription: {description}\n---\n"
    (skill_dir / "SKILL.md").write_text(front + body, encoding="utf-8")
    return skill_dir


def make_skill_no_frontmatter(root, tool, name, body="First line body.\n"):
    skill_dir = Path(root) / tool / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def roots_from(tmp, tools=("claude",)):
    """Return {tool: root_path} for the given tools under tmp."""
    return {tool: str(Path(tmp) / tool) for tool in tools}
