"""GitHub declarative Labels schema loading, diffing, synchronization, and PR taxonomy auditing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from devops_cli.exceptions.git import GitHubOperationError


class LabelSpec(BaseModel):
    """Declarative specification for a repository label."""

    name: str
    color: str
    description: str = ""

    @field_validator("color")
    @classmethod
    def normalize_color(cls, v: str) -> str:
        """Strip optional leading hash and uppercase hex string."""
        clean = v.strip().lstrip("#").upper()
        if not clean:
            raise ValueError("Label color cannot be empty")
        return clean


class LabelSyncResult(BaseModel):
    """Outcome summary of a declarative label synchronization operation."""

    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    dry_run: bool = False
    created: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)


class LabelAuditResult(BaseModel):
    """Audit finding for a Pull Request missing required taxonomy labels."""

    pr_number: int
    issue: str
    title: str = ""
    labels: list[str] = Field(default_factory=list)


LabelAuditFinding = LabelAuditResult


def load_label_specs(path: Path = Path(".github/labels.yml")) -> list[LabelSpec]:
    """Load and validate declarative label specifications from YAML."""
    if not path.is_file():
        raise GitHubOperationError(
            f"Label specs file not found: {path}",
            operation="load_label_specs",
            details={"path": str(path)},
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GitHubOperationError(
            f"Failed to parse label specs YAML {path}: {exc}",
            operation="load_label_specs",
            details={"path": str(path), "error": str(exc)},
        ) from exc

    if not isinstance(raw, list):
        raise GitHubOperationError(
            f"Expected list of label specifications in {path}, got {type(raw).__name__}",
            operation="load_label_specs",
            details={"path": str(path)},
        )

    return [LabelSpec(**item) for item in raw if isinstance(item, dict)]


def _normalize_color_val(color: str | None) -> str:
    """Normalize hex color string for case-insensitive comparison."""
    return (color or "").strip().lstrip("#").upper()


def _is_label_equal(spec: LabelSpec, existing: dict[str, Any]) -> bool:
    """Check if existing remote label definition matches the desired spec."""
    remote_color = _normalize_color_val(existing.get("color"))
    remote_desc = (existing.get("description") or "").strip()
    return spec.color == remote_color and spec.description.strip() == remote_desc


def diff_labels(
    desired: list[LabelSpec], existing: list[dict[str, Any]]
) -> tuple[list[LabelSpec], list[LabelSpec], list[LabelSpec]]:
    """Partition desired label specs into (to_create, to_update, unchanged)."""
    existing_map = {item.get("name", ""): item for item in existing if isinstance(item, dict)}

    to_create: list[LabelSpec] = []
    to_update: list[LabelSpec] = []
    unchanged: list[LabelSpec] = []

    for spec in desired:
        if spec.name not in existing_map:
            to_create.append(spec)
        elif not _is_label_equal(spec, existing_map[spec.name]):
            to_update.append(spec)
        else:
            unchanged.append(spec)

    return to_create, to_update, unchanged


def _extract_labels_from_raw(raw_labels: Any) -> list[dict[str, Any]]:
    """Extract standard dictionaries from heterogeneous label objects or dicts."""
    results: list[dict[str, Any]] = []
    for item in raw_labels or []:
        if isinstance(item, dict):
            results.append(item)
        elif hasattr(item, "name"):
            results.append(
                {
                    "name": item.name,
                    "color": getattr(item, "color", ""),
                    "description": getattr(item, "description", "") or "",
                }
            )
    return results


def _apply_label_mutation(client: Any, repo: str, spec: LabelSpec, is_create: bool) -> None:
    """Safely apply create or edit label mutation on client."""
    method_name = "create_label" if is_create else "edit_label"
    func = getattr(client, method_name, None)
    if not callable(func):
        return

    try:
        func(repo, name=spec.name, color=spec.color, description=spec.description)
    except TypeError:
        func(name=spec.name, color=spec.color, description=spec.description)


def sync_repository_labels(
    client: Any, repo: str, desired: list[LabelSpec], dry_run: bool = False
) -> LabelSyncResult:
    """Synchronize remote repository labels with desired declarative specifications."""
    try:
        raw_existing = client.get_labels(repo)
    except TypeError:
        raw_existing = client.get_labels()

    existing = _extract_labels_from_raw(raw_existing)
    to_create, to_update, unchanged = diff_labels(desired, existing)

    result = LabelSyncResult(
        created_count=len(to_create),
        updated_count=len(to_update),
        unchanged_count=len(unchanged),
        dry_run=dry_run,
        created=[s.name for s in to_create],
        updated=[s.name for s in to_update],
    )

    if dry_run:
        return result

    for spec in to_create:
        _apply_label_mutation(client, repo, spec, is_create=True)

    for spec in to_update:
        _apply_label_mutation(client, repo, spec, is_create=False)

    return result


def _check_pr_labels(pr: dict[str, Any]) -> LabelAuditResult | None:
    """Evaluate a single PR for compliance with required taxonomy labels."""
    label_entries = pr.get("labels", [])
    names: list[str] = [
        lbl.get("name", "") if isinstance(lbl, dict) else getattr(lbl, "name", str(lbl))
        for lbl in label_entries
    ]

    has_type = any(n.startswith("type/") for n in names)
    has_scope = any(n.startswith("scope/") for n in names)

    if has_type and has_scope:
        return None

    issue_desc: str
    if not has_type and not has_scope:
        issue_desc = "Missing both type and scope labels (e.g. type/feature, scope/ai)"
    elif not has_type:
        issue_desc = "Missing type label (e.g. type/feature, type/bug, type/chore)"
    else:
        issue_desc = "Missing scope label (e.g. scope/ai, scope/k8s, scope/cli)"

    return LabelAuditResult(
        pr_number=pr.get("number", 0),
        title=pr.get("title", ""),
        issue=issue_desc,
        labels=names,
    )


def audit_repository_labels(prs: list[dict[str, Any]]) -> list[LabelAuditResult]:
    """Audit pull requests for presence of mandatory type/ and scope/ taxonomy labels."""
    findings: list[LabelAuditResult] = []
    for pr in prs:
        finding = _check_pr_labels(pr)
        if finding:
            findings.append(finding)
    return findings
