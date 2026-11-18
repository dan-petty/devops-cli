"""The labelled gold set of knowledge base facts, and the marking of its stale entries (#3902).

The set holds one question for each fact that grounds the review loop and the AI commands: the
tool, the library and the project facts. Each entry names the checked-in source that answers it and
the answer text, so `mark_stale_entries` tells an entry that its source no longer answers: the
source is absent, the answer text is gone from it, or a knowledge base article drifted away from
the versions that the caller passes. The marker reads the repository only, so no network call and
no model judgement decides a stale entry.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from devops_cli.ai.kb import load_matched_kb_manuals
from devops_cli.exceptions import ValidationError

FactType = Literal["tool", "library", "project"]

# The kinds of fact that the gold set covers, and so the closed set of a `fact_type` value.
_FACT_TYPES: tuple[str, ...] = ("tool", "library", "project")
# The fields that every entry of the gold set must hold. The entry identifier is one of them, so
# that an error and a score name the same entry.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "question",
    "expected_source",
    "expected_answer",
    "fact_type",
    "reference",
)


class GoldSetEntry(BaseModel):
    """One labelled question of the gold set, with the checked-in source that answers it (#3902)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(description="Stable identifier of the entry in the gold set.")
    question: str = Field(description="The question that the retrieval source must answer.")
    expected_source: str = Field(
        description="The path, relative to the repository root, of the file that holds the answer."
    )
    expected_answer: str = Field(description="The text that the expected source holds.")
    fact_type: FactType = Field(description="The kind of fact: tool, library or project.")
    reference: str = Field(description="The primary web page that the fact comes from.")
    stale: bool = Field(description="Whether the expected source no longer answers the question.")
    stale_reason: str | None = Field(
        description="Why the entry is stale, and None when no check marked it."
    )


class GoldSet(BaseModel):
    """The labelled questions, each with its stale marking (#3902)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: tuple[GoldSetEntry, ...] = Field(description="The entries of the gold set.")


def load_gold_set(path: Path) -> GoldSet:
    """Load the gold set from its JSON file, and refuse an entry that lacks a field (#3902).

    The loader marks no entry stale: only `mark_stale_entries` reads a source, so an entry that
    no check has read reads as unchecked rather than as verified.
    """
    raw = _read_entries(path)
    entries = tuple(_build_entry(index, item) for index, item in enumerate(raw))
    return GoldSet(entries=entries)


def mark_stale_entries(
    gold_set: GoldSet,
    *,
    repo_root: Path,
    kb_dir: Path,
    tool_versions: Mapping[str, str],
) -> GoldSet:
    """Mark each entry whose expected source no longer answers, with the reason (#3902).

    An entry is stale when its expected source is absent, when the expected answer text is no
    longer in that source, or when the source is a knowledge base article of `kb_dir` that
    `load_matched_kb_manuals` reports as drift against `tool_versions`.
    """
    drift = _drift_reasons(kb_dir, tool_versions)
    entries = tuple(_mark_entry(entry, repo_root, drift) for entry in gold_set.entries)
    return GoldSet(entries=entries)


def _read_entries(path: Path) -> list[Any]:
    """The raw entries of the gold set file at `path`."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"gold set {path} cannot be read: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"gold set {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValidationError(f"gold set {path} must hold a list of entries")
    return data


def _build_entry(index: int, item: Any) -> GoldSetEntry:
    """The entry that `item`, the raw entry at `index`, describes."""
    if not isinstance(item, dict):
        raise ValidationError(f"gold set entry {index} is not an object")
    label = item.get("id") if isinstance(item.get("id"), str) and item["id"] else f"entry {index}"
    for name in _REQUIRED_FIELDS:
        value = item.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(
                f"gold set entry {label} is missing the field {name}",
                field=name,
            )
    if item["fact_type"] not in _FACT_TYPES:
        raise ValidationError(
            f"gold set entry {label} has the unknown fact_type {item['fact_type']}, "
            f"which is not one of {', '.join(_FACT_TYPES)}",
            field="fact_type",
        )
    try:
        return GoldSetEntry(**item, stale=False, stale_reason=None)
    except PydanticValidationError as exc:
        raise ValidationError(f"gold set entry {label} is invalid: {exc}") from exc


def _drift_reasons(kb_dir: Path, tool_versions: Mapping[str, str]) -> dict[str, str]:
    """The reason of each knowledge base article of `kb_dir` that drifted, by its relative path."""
    _matched, drift = load_matched_kb_manuals(
        kb_dir=kb_dir,
        tool_versions=dict(tool_versions),
    )
    return {item.path: item.reason for item in drift}


def _mark_entry(
    entry: GoldSetEntry,
    repo_root: Path,
    drift: Mapping[str, str],
) -> GoldSetEntry:
    """`entry`, marked stale when its expected source no longer answers it."""
    reason = _stale_reason(entry, repo_root, drift)
    if reason is None:
        return entry
    return entry.model_copy(update={"stale": True, "stale_reason": reason})


def _stale_reason(
    entry: GoldSetEntry,
    repo_root: Path,
    drift: Mapping[str, str],
) -> str | None:
    """Why `entry` is stale, or None when its expected source still answers it."""
    source = repo_root / entry.expected_source
    if not source.is_file():
        return f"expected source {entry.expected_source} is absent"
    if drift_reason := drift.get(entry.expected_source):
        return f"expected source {entry.expected_source} drifts: {drift_reason}"
    try:
        text = source.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"expected source {entry.expected_source} cannot be read: {exc}"
    if entry.expected_answer not in text:
        return f"expected answer is no longer in {entry.expected_source}"
    return None


__all__ = [
    "GoldSet",
    "GoldSetEntry",
    "load_gold_set",
    "mark_stale_entries",
]
