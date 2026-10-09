"""Offline tally of the verdicts the feedback dataset records, for each labeller.

It used to replay the deterministic suppression layer, `_deterministic_pre_verification`, over
the dataset and compare its decisions with the recorded verdicts. #1150 deleted that layer with
the model verifier, so what is left counts the recorded INVALIDATED and VERIFIED verdicts of one
persona's findings, for each labeller. No model is called, so a run is deterministic, free and
reproducible.

Every label says who wrote it. A label a deterministic check wrote (`deterministic:*`) is a
machine's, not a person's, and is counted as excluded unless `include_deterministic` asks for it.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.run_store import digest
from devops_cli.config.constants import (
    CONST_STATUS_INVALIDATED,
    CONST_STATUS_VERIFIED,
    CONST_VERIFIED_BY_DETERMINISTIC_PREFIX,
    CONST_VERIFIED_BY_UNKNOWN,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.repo import review_data_root
from devops_cli.exceptions import SecurityError

_MAX_DATASET_BYTES = 50 * 1024 * 1024

# What each labeller's counts hold, in the order they are reported.
_LABELLER_FIELDS = ("invalidated", "verified")
# The count each recorded verdict adds to.
_COUNTED_LABELS = {CONST_STATUS_INVALIDATED: "invalidated", CONST_STATUS_VERIFIED: "verified"}


class PromptEvalBenchmarkResult(BaseModel):
    """The verdicts the feedback dataset records for one persona's findings."""

    persona: str
    total_cases: int
    labelled_invalidated: int
    labelled_verified: int
    # Equal for evaluations of the same recorded verdicts.
    dataset_digest: str = ""
    # The counts above for each labeller: invalidated and verified.
    by_labeller: dict[str, dict[str, int]] = Field(default_factory=dict)
    # Records left out because a deterministic check wrote their label, by labeller.
    excluded_labels: dict[str, int] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Render the tally for `--json`."""
        return self.model_dump()


def _resolve_dataset_path(dataset_path: Path | None, data_root: Path) -> Path:
    """Resolve the dataset location, a relative one under `data_root`, refusing system paths."""
    if dataset_path is None:
        configured = load_settings().data.feedback_dataset_path
        target = configured if configured.is_absolute() else (data_root / configured)
    else:
        from devops_cli.core.paths import validate_no_path_traversal

        validate_no_path_traversal(dataset_path, label="dataset_path")
        target = dataset_path if dataset_path.is_absolute() else (data_root / dataset_path)

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


def _labeller(record: dict[str, Any]) -> str:
    """Who wrote a record's label: a person, an agent, a model or a check; unknown if unsaid."""
    return str(record.get("verified_by") or CONST_VERIFIED_BY_UNKNOWN)


def evaluate_persona_prompts(
    persona: str = "devsecops",
    dataset_path: Path | None = None,
    include_deterministic: bool = False,
) -> PromptEvalBenchmarkResult:
    """Count the INVALIDATED and VERIFIED verdicts the dataset records for `persona`'s findings.

    The counts are reported for each labeller, and a record a deterministic check labelled is
    excluded unless `include_deterministic`. The dataset is the one `devops review
    export-feedback` appends to, a relative one under the review data root (`review_data_root`,
    #972).
    """
    records = _load_records(_resolve_dataset_path(dataset_path, review_data_root()), persona)

    excluded: Counter[str] = Counter()
    by_labeller: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        labeller = _labeller(record)
        if (
            labeller.startswith(CONST_VERIFIED_BY_DETERMINISTIC_PREFIX)
            and not include_deterministic
        ):
            excluded[labeller] += 1
            continue
        counts = by_labeller[labeller]
        if (label := _COUNTED_LABELS.get(str(record.get("status") or ""))) is not None:
            counts[label] += 1

    totals: Counter[str] = sum(by_labeller.values(), Counter())
    return PromptEvalBenchmarkResult(
        persona=persona,
        total_cases=len(records) - excluded.total(),
        labelled_invalidated=totals["invalidated"],
        labelled_verified=totals["verified"],
        dataset_digest=digest(records),
        by_labeller={
            labeller: {field: counts[field] for field in _LABELLER_FIELDS}
            for labeller, counts in sorted(by_labeller.items())
        },
        excluded_labels=dict(sorted(excluded.items())),
    )
