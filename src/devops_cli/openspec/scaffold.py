"""Scaffold an OpenSpec change folder in project form (#3203)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_OPENSPEC_NON_OBSERVABLE_PREFIXES,
    CONST_OPENSPEC_SCAFFOLD_MARKER,
    CONST_OPENSPEC_SPECS_DIR,
)
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.git.branch_form import branch_name, slug_from_title
from devops_cli.github.issues import get_repository_issue
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import isolated_openspec
from devops_cli.roadmap.commit_title import commit_type


@dataclass(frozen=True)
class ScaffoldResult:
    """The result of scaffolding an OpenSpec change folder."""

    folder: str
    branch: str
    change: str
    dry_run: bool = False


def extract_requirement_from_spec(spec_text: str, requirement_name: str) -> str | None:
    """Extract a requirement section and its scenarios from base spec text."""
    pattern = (
        rf"(### Requirement:\s*{re.escape(requirement_name)}\b.*?)(?=\n### Requirement:|\n## |\Z)"
    )
    match = re.search(pattern, spec_text, re.DOTALL)
    return match.group(1).strip() if match else None


def decide_skip_specs(
    paths: Sequence[str] | None, capabilities: Sequence[str] | None
) -> bool | None:
    """Decide whether skip_specs should be true, false, or omitted."""
    if not paths and not capabilities:
        return None
    if capabilities:
        return False
    if paths:
        if all(
            any(p.startswith(prefix) for prefix in CONST_OPENSPEC_NON_OBSERVABLE_PREFIXES)
            for p in paths
        ):
            return True
        return False
    return None


def scaffold_proposal(issue: int) -> str:
    """Generate the project proposal.md content."""
    marker = CONST_OPENSPEC_SCAFFOLD_MARKER
    return (
        f"# Proposal: #{issue}\n\n"
        "## Why\n"
        f"<!-- State the problem or motivation. Closes #{issue}. --> {marker}\n\n"
        "## What Changes\n"
        f"<!-- Describe what this change adds, changes, or removes. --> {marker}\n\n"
        "## Capabilities\n"
        f"<!-- List the capabilities this change introduces or modifies. --> {marker}\n\n"
        "## Impact\n"
        f"<!-- Describe the impact on users, dependencies, or systems. --> {marker}\n\n"
        "## Feasibility\n"
        f"<!-- Confirm the premise against real system, docs, or command output. --> {marker}\n\n"
        "## Existing Tool Considered\n"
        f"<!-- Name open tool considered, or cost in tokens and time to build. --> {marker}\n"
    )


def scaffold_design() -> str:
    """Generate the project design.md content."""
    marker = CONST_OPENSPEC_SCAFFOLD_MARKER
    return (
        "# Design\n\n"
        "## Decisions\n"
        f"<!-- Record architectural and design decisions. --> {marker}\n\n"
        "## Rejected alternatives\n"
        f"<!-- Record alternatives considered and why they were rejected. --> {marker}\n"
    )


def scaffold_tasks() -> str:
    """Generate the project tasks.md content."""
    marker = CONST_OPENSPEC_SCAFFOLD_MARKER
    return (
        "# Tasks\n\n"
        "## 1. Behavior\n\n"
        f"- [ ] 1.1 Write failing test {marker}\n"
        f"  - Verification: `$ uv run devops ci test tests/test_scaffold.py` {marker}\n"
        f"- [ ] 1.2 Implement the behavior {marker}\n"
        f"  - Verification: `$ uv run devops ci test tests/test_scaffold.py` {marker}\n\n"
        "## 2. Documents\n\n"
        f"- [ ] 2.1 Update documentation {marker}\n"
        f"  - Verification: `$ uv run devops ci docs` {marker}\n"
    )


def scaffold_spec_delta(root: Path, capability: str, requirement: str | None) -> str:
    """Generate the spec delta content for a capability."""
    marker = CONST_OPENSPEC_SCAFFOLD_MARKER
    base_spec_path = root / CONST_OPENSPEC_SPECS_DIR / capability / "spec.md"
    if base_spec_path.is_file():
        base_text = base_spec_path.read_text(encoding="utf-8")
        if requirement:
            extracted = extract_requirement_from_spec(base_text, requirement)
            if extracted:
                return f"## MODIFIED Requirements\n\n{extracted}\n"
        req_name = requirement or "Requirement Name"
        return (
            "## ADDED Requirements\n\n"
            f"### Requirement: {req_name} {marker}\n"
            f"Describe requirement. {marker}\n\n"
            f"#### Scenario: Scenario name {marker}\n"
            f"- **WHEN** condition {marker}\n"
            f"- **THEN** result {marker}\n"
        )
    req_name = requirement or "Requirement Name"
    purpose = f"Purpose of the {capability} capability: explain why it exists."
    return (
        "## Purpose\n"
        f"{purpose} {marker}\n\n"
        "## ADDED Requirements\n\n"
        f"### Requirement: {req_name} {marker}\n"
        f"Describe requirement. {marker}\n\n"
        f"#### Scenario: Scenario name {marker}\n"
        f"- **WHEN** condition {marker}\n"
        f"- **THEN** result {marker}\n"
    )


def scaffold_change(
    root: Path,
    issue: int,
    *,
    title: str | None = None,
    paths: Sequence[str] | None = None,
    capabilities: Sequence[str] | None = None,
    dry_run: bool = False,
    repo: str | None = None,
) -> ScaffoldResult:
    """Scaffold an OpenSpec change folder in project form."""
    if dry_run:
        if title is None:
            raise DevOpsCLIError(MESSAGES.openspec.new_dry_run_needs_title)
        type_ = commit_type(title) or "feat"
        slug = slug_from_title(title)
        change_name = f"{issue}-{slug}"
        branch = branch_name(issue, type_, slug)
        folder = f"{CONST_OPENSPEC_CHANGES_DIR}/{change_name}"
        return ScaffoldResult(folder=folder, branch=branch, change=change_name, dry_run=True)

    if title is None:
        target_repo = repo or get_repo_origin_name(root) or "unknown/repo"
        issue_view = get_repository_issue(target_repo, issue)
        title = issue_view.title

    type_ = commit_type(title) or "feat"
    slug = slug_from_title(title)
    change_name = f"{issue}-{slug}"
    branch = branch_name(issue, type_, slug)
    change_folder = root / CONST_OPENSPEC_CHANGES_DIR / change_name

    if change_folder.exists():
        rel_folder = change_folder.relative_to(root).as_posix()
        raise DevOpsCLIError(MESSAGES.openspec.change_folder_exists.format(path=rel_folder))

    with isolated_openspec() as tool:
        tool.run_checked(["new", "change", change_name], root)

    skip_specs = decide_skip_specs(paths, capabilities)
    if skip_specs is not None:
        yaml_path = change_folder / ".openspec.yaml"
        current_yaml = yaml_path.read_text(encoding="utf-8")
        val = "true" if skip_specs else "false"
        yaml_path.write_text(f"{current_yaml}skip_specs: {val}\n", encoding="utf-8")

    (change_folder / "proposal.md").write_text(scaffold_proposal(issue), encoding="utf-8")
    (change_folder / "design.md").write_text(scaffold_design(), encoding="utf-8")
    (change_folder / "tasks.md").write_text(scaffold_tasks(), encoding="utf-8")

    if capabilities:
        for cap_entry in capabilities:
            cap_name, _, req_name = cap_entry.partition(":")
            cap_name = cap_name.strip()
            req = req_name.strip() if req_name.strip() else None
            spec_file = change_folder / "specs" / cap_name / "spec.md"
            spec_file.parent.mkdir(parents=True, exist_ok=True)
            spec_file.write_text(scaffold_spec_delta(root, cap_name, req), encoding="utf-8")

    return ScaffoldResult(
        folder=change_folder.relative_to(root).as_posix(),
        branch=branch,
        change=change_name,
        dry_run=False,
    )
