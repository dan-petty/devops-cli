"""Defect pull request classification and declared hardening surface analysis (#697, #1151, #1979).

A pull request is classified as a defect fix if it carries `type/bug` or `type/security`
labels (as defined in `.github/labels.yml`) or has a Conventional Commits `fix(...)` / `fix:`
title. Defect pull requests must record hardening guardrails or lessons on at least one declared
hardening surface (`docs/TESTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CONTRIBUTING.md`,
`src/devops_cli/ai/tasks/*.md`, `src/devops_cli/ai/knowledge_base/`, `.devops/review.toml`, or
`src/devops_cli/review/rules/`).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from devops_cli.config.constants import (
    CONST_DEFECT_TITLE_PATTERN,
    CONST_HARDENING_SURFACES,
)

_DEFECT_TITLE_RE = re.compile(CONST_DEFECT_TITLE_PATTERN, re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DefectClassification:
    """Classification outcome detailing whether and why a pull request represents a defect fix."""

    is_defect: bool
    has_bug_label: bool = False
    has_security_label: bool = False
    has_fix_title: bool = False
    reasons: tuple[str, ...] = ()


def _extract_label_names(labels: Sequence[str | dict[str, Any]] | None) -> set[str]:
    """Extract normalized label names from string or dict label items."""
    names: set[str] = set()
    for item in labels or ():
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.add(name)
        elif isinstance(item, str):
            clean = item.strip()
            if clean:
                names.add(clean)
        elif hasattr(item, "name"):
            names.add(str(getattr(item, "name", "")).strip())
    return names


def classify_defect_pr(
    title: str,
    labels: Sequence[str | dict[str, Any]] | None = None,
) -> DefectClassification:
    """Classify whether a PR is a defect PR based on labels or title convention.

    A PR is classified as a defect PR if it carries `type/bug` or `type/security` labels,
    or has a Conventional Commits `fix(...)` or `fix:` title prefix.
    """
    clean_title = (title or "").strip()
    label_names = _extract_label_names(labels)

    has_bug = "type/bug" in label_names
    has_sec = "type/security" in label_names
    has_fix = bool(_DEFECT_TITLE_RE.match(clean_title))

    reasons: list[str] = []
    if has_bug:
        reasons.append("label:type/bug")
    if has_sec:
        reasons.append("label:type/security")
    if has_fix:
        reasons.append("title:fix")

    return DefectClassification(
        is_defect=has_bug or has_sec or has_fix,
        has_bug_label=has_bug,
        has_security_label=has_sec,
        has_fix_title=has_fix,
        reasons=tuple(reasons),
    )


def is_defect_pr(
    title: str,
    labels: Sequence[str | dict[str, Any]] | None = None,
) -> bool:
    """Convenience predicate returning True if a PR represents a defect fix."""
    return classify_defect_pr(title, labels).is_defect


def match_hardening_surface(file_path: str) -> str | None:
    """Match a changed file path against the declared hardening surfaces.

    Declared surfaces:
    - `docs/TESTING.md`
    - `ARCHITECTURE.md`
    - `SECURITY.md`
    - `CONTRIBUTING.md`
    - `src/devops_cli/ai/tasks/*.md`
    - `src/devops_cli/ai/knowledge_base/`
    - `.devops/review.toml`
    - `src/devops_cli/review/rules/`
    """
    normalized = file_path.replace("\\", "/").strip().lstrip("/")
    if normalized == "docs/TESTING.md":
        return "docs/TESTING.md"
    if normalized == "ARCHITECTURE.md":
        return "ARCHITECTURE.md"
    if normalized == "SECURITY.md":
        return "SECURITY.md"
    if normalized == "CONTRIBUTING.md":
        return "CONTRIBUTING.md"
    if normalized.startswith("src/devops_cli/ai/tasks/") and normalized.endswith(".md"):
        rel = normalized[len("src/devops_cli/ai/tasks/") :]
        if "/" not in rel:
            return "src/devops_cli/ai/tasks/*.md"
    if normalized.startswith("src/devops_cli/ai/knowledge_base/"):
        return "src/devops_cli/ai/knowledge_base/"
    if normalized == ".devops/review.toml":
        return ".devops/review.toml"
    if (
        normalized.startswith("src/devops_cli/review/rules/")
        and normalized != "src/devops_cli/review/rules/"
    ):
        return "src/devops_cli/review/rules/"
    return None


@dataclass(frozen=True, slots=True)
class PRHardeningAudit:
    """Hardening audit evaluation for a single pull request."""

    number: int
    title: str
    classification: DefectClassification
    surface_additions: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    empty_file_list: bool = False

    @property
    def is_hardened(self) -> bool:
        """Report whether any declared hardening surface gained lines (additions > 0)."""
        return any(count > 0 for count in self.surface_additions.values())

    @property
    def hardened_surfaces(self) -> tuple[str, ...]:
        """Declared surfaces that gained lines (additions > 0)."""
        return tuple(s for s, count in self.surface_additions.items() if count > 0)


def audit_pr_hardening(
    pr_number: int,
    title: str,
    labels: Sequence[str | dict[str, Any]] | None,
    files: Sequence[dict[str, Any]],
) -> PRHardeningAudit:
    """Evaluate whether a defect PR gained additions on any declared hardening surface."""
    classification = classify_defect_pr(title, labels)
    if not files:
        return PRHardeningAudit(
            number=pr_number,
            title=title,
            classification=classification,
            surface_additions={s: 0 for s in CONST_HARDENING_SURFACES},
            total_files=0,
            empty_file_list=True,
        )

    counts: dict[str, int] = {s: 0 for s in CONST_HARDENING_SURFACES}
    for file_info in files:
        path = str(file_info.get("path", "")).strip()
        additions = int(file_info.get("additions", 0))
        surface = match_hardening_surface(path)
        if surface is not None and additions > 0:
            counts[surface] = counts.get(surface, 0) + additions

    return PRHardeningAudit(
        number=pr_number,
        title=title,
        classification=classification,
        surface_additions=counts,
        total_files=len(files),
        empty_file_list=False,
    )
