"""Offline measurement of the deterministic suppression layer against recorded verdicts.

This replays `_deterministic_pre_verification` over the feedback dataset and reports how
its decisions compare with the verdict each finding was eventually recorded with. No model
is called, so a run is deterministic, free, and reproducible.

The command previously reported `accuracy_score` 1.0 and `false_positive_rate` 0.0 on
every invocation. It counted the dataset's own labels and then assigned those two
constants without evaluating anything, so it reported a flawless loop on 1311 cases while
two calibration sessions were measuring false positive rates among high-severity findings
near 40% and 85%. A tool whose purpose is to detect exactly that failure was reporting its
absence by construction.

Benchmarking prompt *variations* requires a model in the loop and is tracked on the
roadmap; this measures the layer that runs before any model is asked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.run_store import digest
from devops_cli.config.constants import CONST_STATUS_INVALIDATED, CONST_STATUS_VERIFIED
from devops_cli.config.settings import load_settings
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.exceptions import SecurityError

_MAX_DATASET_BYTES = 50 * 1024 * 1024


class PromptEvalBenchmarkResult(BaseModel):
    """How the deterministic layer's decisions compare with recorded verdicts."""

    persona: str
    total_cases: int
    labelled_invalidated: int
    labelled_verified: int
    caught_invalidations: int
    contested_verifications: int
    # Equal for evaluations of the same recorded verdicts.
    dataset_digest: str = ""
    details: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def catch_rate(self) -> float:
        """Share of recorded invalidations the deterministic layer reaches on its own.

        Each one is a finding the model verifier never has to be asked about, so this is
        the figure that rises when a mechanical oracle replaces a round trip.
        """
        if not self.labelled_invalidated:
            return 0.0
        return self.caught_invalidations / self.labelled_invalidated

    @property
    def contested_rate(self) -> float:
        """Share of recorded verifications the deterministic layer overrides.

        This is the direction that buries real defects. It is reported separately rather
        than folded into one accuracy figure, where a gain on the other side would hide it.
        """
        if not self.labelled_verified:
            return 0.0
        return self.contested_verifications / self.labelled_verified

    def to_dict(self) -> dict[str, Any]:
        """Render the measurement for `--json`."""
        return {
            "persona": self.persona,
            "total_cases": self.total_cases,
            "labelled_invalidated": self.labelled_invalidated,
            "labelled_verified": self.labelled_verified,
            "caught_invalidations": self.caught_invalidations,
            "contested_verifications": self.contested_verifications,
            "catch_rate": round(self.catch_rate, 4),
            "contested_rate": round(self.contested_rate, 4),
            "dataset_digest": self.dataset_digest,
            "details": self.details,
        }


def _resolve_dataset_path(dataset_path: Path | None, main_root: Path) -> Path:
    """Resolve the dataset location, refusing anything outside the repository."""
    from devops_cli.core.repo import resolve_data_path

    if dataset_path is None:
        configured = load_settings().data.feedback_dataset_path
        target = resolve_data_path(configured, main_root)
    else:
        from devops_cli.core.paths import validate_no_path_traversal

        validate_no_path_traversal(dataset_path, label="dataset_path")
        target = (
            dataset_path
            if dataset_path.is_absolute()
            else resolve_data_path(dataset_path, main_root)
        )

    if target.is_symlink():
        raise SecurityError(f"dataset_path must not be a symbolic link: {target}")

    from devops_cli.core.paths import is_forbidden_system_path

    resolved = target.resolve()
    if is_forbidden_system_path(resolved):
        raise SecurityError(f"dataset_path must not resolve to forbidden system path: {resolved}")
    return resolved


def _load_records(path: Path, persona: str) -> list[dict[str, Any]]:
    """Read the feedback dataset, keeping only the records for one persona."""
    if not path.is_file() or path.stat().st_size > _MAX_DATASET_BYTES:
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("persona") in (persona, None):
            records.append(record)
    return records


def _deterministic_verdict(record: dict[str, Any], repo_root: Path) -> str | None:
    """Return the status the deterministic layer assigns, or None if it cannot build one."""
    from devops_cli.ai.review.common_hallucinations import catalog_learning_disabled
    from devops_cli.ai.review.verification import _deterministic_pre_verification
    from devops_cli.ai.review_schema import Finding

    try:
        finding = Finding(
            title=str(record.get("title") or ""),
            location=str(record.get("location") or ""),
            description=str(record.get("description") or ""),
            severity=str(record.get("severity") or "MEDIUM"),
        )
    except Exception:
        return None
    # Replaying a recorded finding is not new evidence, so it must not teach the catalog.
    with catalog_learning_disabled():
        return str(_deterministic_pre_verification(finding, repo_root=repo_root).status)


def evaluate_persona_prompts(
    persona: str = "devsecops",
    dataset_path: Path | None = None,
) -> PromptEvalBenchmarkResult:
    """Measure the deterministic layer against the verdicts the dataset recorded.

    A record the layer invalidates that was recorded `INVALIDATED` is a round trip saved. A
    record it invalidates that was recorded `VERIFIED` is contested: either the layer
    over-suppresses, or that verdict was itself a false positive. Both counts are reported
    rather than netted, because they are not interchangeable.
    """
    from devops_cli.core.repo import main_worktree_root

    worktree_root = find_top_level_repo_root(Path.cwd())
    main_root = main_worktree_root(worktree_root)
    records = _load_records(_resolve_dataset_path(dataset_path, main_root), persona)

    labelled_invalidated = 0
    labelled_verified = 0
    caught = 0
    contested: list[dict[str, Any]] = []

    for record in records:
        label = str(record.get("status") or "")
        verdict = _deterministic_verdict(record, worktree_root)
        suppressed = verdict == CONST_STATUS_INVALIDATED
        if label == CONST_STATUS_INVALIDATED:
            labelled_invalidated += 1
            caught += int(suppressed)
        elif label == CONST_STATUS_VERIFIED:
            labelled_verified += 1
            if suppressed:
                contested.append(
                    {
                        "title": record.get("title"),
                        "location": record.get("location"),
                        "severity": record.get("severity"),
                        "session_id": record.get("session_id"),
                    }
                )

    return PromptEvalBenchmarkResult(
        persona=persona,
        total_cases=len(records),
        labelled_invalidated=labelled_invalidated,
        labelled_verified=labelled_verified,
        caught_invalidations=caught,
        contested_verifications=len(contested),
        dataset_digest=digest(records),
        details=contested[:10],
    )
