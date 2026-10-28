"""Duplicate detection: exact name, exact content, keyword overlap."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "with", "in", "on",
    "by", "at", "from", "into", "using", "use", "used", "how", "what",
    "when", "that", "this", "is", "are", "be", "as", "it", "its", "your",
    "you", "we", "our", "skill", "skills", "help", "helps", "guide",
    "best", "practices", "practice", "based", "via", "per", "do", "does",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set:
    return {t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _norm_name(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").replace("-", " ").split())


@dataclass
class DuplicateGroup:
    kind: str  # exact-name | exact-content | keyword-overlap
    members: list = field(default_factory=list)

    @property
    def has_within_tool_pair(self) -> bool:
        tools = [m.tool for m in self.members]
        return len(tools) != len(set(tools))

    @property
    def within_tool(self) -> bool:
        # Backwards-compatible: true only for a purely within-tool group.
        return self.has_within_tool_pair and not self.cross_tool

    @property
    def cross_tool(self) -> bool:
        return len({m.tool for m in self.members}) > 1

    @property
    def score(self) -> float:
        # For keyword groups this is recomputed by the finder; exact = 1.0
        return getattr(self, "_score", 1.0)


def _union_find(n: int):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    return find, union


def find_duplicate_groups(skills: list) -> list:
    """Return duplicate groups, merging transitive pairs (union-find).

    Pair priority: exact-name and exact-content pairs are grouped first;
    keyword-overlap pairs (Jaccard >= 0.30) are added next, but only
    between skills not already in an exact group with each other, to
    avoid merging unrelated exact groups via a weak keyword link.
    """
    n = len(skills)
    find, union = _union_find(n)
    pair_kind = {}

    # Exact name (normalised) and exact content.
    for i in range(n):
        for j in range(i + 1, n):
            if _norm_name(skills[i].name) == _norm_name(skills[j].name):
                union(i, j)
                pair_kind[(i, j)] = "exact-name"
            elif skills[i].content_hash and skills[i].content_hash == skills[j].content_hash:
                union(i, j)
                pair_kind[(i, j)] = "exact-content"

    # Keyword overlap, only for pairs not already exact-grouped.
    token_sets = [tokens(s.name + " " + s.description) for s in skills]
    scores = {}
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            score = jaccard(token_sets[i], token_sets[j])
            scores[(i, j)] = score
            if score >= 0.30:
                union(i, j)
                pair_kind[(i, j)] = "keyword-overlap"

    groups_by_root = {}
    for idx, skill in enumerate(skills):
        groups_by_root.setdefault(find(idx), []).append(idx)

    groups = []
    for root, members_idx in groups_by_root.items():
        if len(members_idx) < 2:
            continue
        kinds = [pair_kind.get((min(a, b), max(a, b)))
                 for a in members_idx for b in members_idx if a < b]
        kinds = [k for k in kinds if k]
        kind = "exact-name" if "exact-name" in kinds else (
            "exact-content" if "exact-content" in kinds else "keyword-overlap")
        group = DuplicateGroup(kind=kind, members=[skills[i] for i in members_idx])
        # Keyword score: max pair score in the group, or 1.0 for exact.
        if kind == "keyword-overlap":
            vals = [scores.get((min(a, b), max(a, b)), 0.0)
                    for a in members_idx for b in members_idx if a < b]
            group._score = max(vals) if vals else 0.0
        else:
            group._score = 1.0
        groups.append(group)
    # Deterministic order: by first member path.
    groups.sort(key=lambda g: g.members[0].path)
    return groups


def keeper_for(group: DuplicateGroup):
    """Deterministic keeper: not managed, longest description, newest
    SKILL.md, then alphabetical path."""
    def key(skill):
        try:
            mtime = os.path.getmtime(skill.skill_md)
        except OSError:
            mtime = 0
        return (0 if not skill.managed else 1,
                -len(skill.description),
                -mtime,
                skill.path)
    return sorted(group.members, key=key)[0]
