"""Usage evidence: search supplied history files for skill mentions."""

from __future__ import annotations

import glob
import os
import re


def _read_text(path: str):
    try:
        if os.path.getsize(path) > 200 * 1024:
            return None
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None
    # Whole size-limited file, not just the first chunk: a NUL anywhere
    # means binary, even if it appears after 8,192 bytes.
    if "\x00" in text:
        return None
    return text


def _mentioned(name: str, text: str) -> bool:
    """Word-boundary match: 'used-skill' must not match 'unused-skill',
    and 'react' must not match 'react-dev'. Hyphens and underscores
    count as name characters for this purpose."""
    if not name:
        return False
    pattern = r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def attach_usage(skills: list, history_patterns: list) -> int:
    """Attach usage to each skill; return number of history files
    actually searched (read successfully, not skipped as binary/large).

    With no patterns, every skill stays "unknown". With patterns, a
    skill mentioned (word-boundary match, directory name or
    frontmatter name) in at least one searched file is "used",
    otherwise "unused-candidate".
    """
    if not history_patterns:
        for skill in skills:
            skill.usage = "unknown"
        return 0
    files = []
    for pattern in history_patterns:
        files.extend(sorted(glob.glob(pattern, recursive=True)))
    files = [f for f in files if os.path.isfile(f)]
    texts = []
    for path in files:
        text = _read_text(path)
        if text is not None:
            texts.append(text)
    for skill in skills:
        names = {skill.name, os.path.basename(skill.path)}
        skill.usage = "used" if any(_mentioned(n, t) for n in names for t in texts) else "unused-candidate"
    return len(texts)
