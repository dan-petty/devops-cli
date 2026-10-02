"""Tracked ledger and perimeter change auditing for mitigated review findings.

Provides persistent tracking of human-accepted mitigations, perimeter file mappings,
and diff-intersection warnings to detect perimeter decay during branch/PR reviews.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.review_schema import Finding
from devops_cli.core.repo import resolve_data_path

logger = logging.getLogger(__name__)

_CANONICAL_LEDGER_PATH = Path("mitigated_findings.json")
DEFAULT_MITIGATIONS_LEDGER_PATH = _CANONICAL_LEDGER_PATH


def resolve_ledger_path(path: Path | None = None, start_path: Path | str | None = None) -> Path:
    """Resolve the effective ledger path, resolving under the data directory."""
    if path is not None:
        return path
    if DEFAULT_MITIGATIONS_LEDGER_PATH != _CANONICAL_LEDGER_PATH:
        return DEFAULT_MITIGATIONS_LEDGER_PATH
    custom = os.environ.get("DEVOPS_CLI_MITIGATIONS_LEDGER")
    if custom:
        return Path(custom)
    from devops_cli.config.settings import load_settings

    try:
        data_dir = load_settings().data.dir
    except Exception:
        data_dir = Path(".data")
    return resolve_data_path(data_dir / DEFAULT_MITIGATIONS_LEDGER_PATH, start_path)


class MitigatedFindingEntry(BaseModel):
    """Structured record for a human-accepted mitigated review finding."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = ""
    location: str = ""
    mitigating_mechanism: str = ""
    perimeter_files: list[str] = Field(default_factory=list)
    regression_test: str | None = None
    reason: str = ""
    recorded_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    recorded_by: str = "human"
    # The person's verdicts that recorded or updated this mitigation. Resetting one of them to
    # UNVERIFIED withdraws it, and the entry goes with the last (#949).
    verdict_count: int = 1


def load_mitigated_findings(ledger_path: Path | None = None) -> list[MitigatedFindingEntry]:
    """Load human-accepted mitigated findings from the tracked ledger."""
    path = resolve_ledger_path(ledger_path)
    if not path.is_file():
        return []

    try:
        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return []
        data = json.loads(raw_text)
        if not isinstance(data, list):
            return []
        entries: list[MitigatedFindingEntry] = []
        for item in data:
            if isinstance(item, dict):
                try:
                    entries.append(MitigatedFindingEntry.model_validate(item))
                except Exception as exc:
                    logger.debug("Skipping invalid mitigated finding entry %r: %s", item, exc)
        return entries
    except Exception as exc:
        logger.warning("Failed to load mitigated findings ledger from %s: %s", path, exc)
        return []


def save_mitigated_findings(
    entries: Sequence[MitigatedFindingEntry], ledger_path: Path | None = None
) -> None:
    """Save mitigated findings entries to the tracked ledger."""
    path = resolve_ledger_path(ledger_path)
    data = [entry.model_dump(mode="json") for entry in entries]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def record_mitigated_finding(
    finding: Finding,
    reason: str = "",
    perimeter_files: list[str] | None = None,
    regression_test: str | None = None,
    ledger_path: Path | None = None,
) -> MitigatedFindingEntry:
    """Record or update a human-accepted mitigation in the tracked ledger."""
    entries = load_mitigated_findings(ledger_path)
    loc_file = finding.location.split(":")[0].strip() if finding.location else ""
    effective_perimeter = list(
        dict.fromkeys(
            p.strip().replace("\\", "/")
            for p in (
                perimeter_files or finding.perimeter_files or ([loc_file] if loc_file else [])
            )
            if p.strip()
        )
    )

    clean_title = finding.title.strip()
    norm_title = clean_title.lower()
    norm_loc = loc_file.lower()

    existing: MitigatedFindingEntry | None = None
    for e in entries:
        if (
            e.title.strip().lower() == norm_title
            and e.location.split(":")[0].strip().lower() == norm_loc
        ):
            existing = e
            break

    mechanism = (
        finding.mitigating_mechanism
        or reason
        or (existing.mitigating_mechanism if existing else "")
        or "human accepted"
    )
    test_path = (
        regression_test
        or finding.regression_test
        or (existing.regression_test if existing else None)
    )

    if existing is not None:
        existing.mitigating_mechanism = mechanism
        existing.perimeter_files = effective_perimeter
        existing.regression_test = test_path
        existing.reason = reason or existing.reason
        existing.recorded_at = datetime.now(UTC).isoformat()
        existing.verdict_count += 1
        entry = existing
    else:
        entry = MitigatedFindingEntry(
            title=clean_title,
            location=finding.location.strip(),
            mitigating_mechanism=mechanism,
            perimeter_files=effective_perimeter,
            regression_test=test_path,
            reason=reason,
        )
        entries.append(entry)

    save_mitigated_findings(entries, ledger_path)
    return entry


def _normalize_path(path_str: str) -> str:
    """Normalize file path for consistent prefix and separator matching."""
    return path_str.replace("\\", "/").strip().lstrip("./")


def _is_path_matching(changed: str, perimeter: str) -> bool:
    """Check if changed file path matches a perimeter path exactly or as child."""
    if changed == perimeter:
        return True
    if changed.endswith("/" + perimeter) or perimeter.endswith("/" + changed):
        return True
    return False


def find_perimeter_changes(
    changed_files: Iterable[str], ledger_path: Path | None = None
) -> list[tuple[MitigatedFindingEntry, list[str]]]:
    """Find mitigated findings whose perimeter files intersect with changed files."""
    entries = load_mitigated_findings(ledger_path)
    if not entries:
        return []

    norm_changed = {_normalize_path(f) for f in changed_files if f.strip()}
    if not norm_changed:
        return []

    matches: list[tuple[MitigatedFindingEntry, list[str]]] = []
    for entry in entries:
        matched_perimeters: list[str] = []
        for perim in entry.perimeter_files:
            norm_perim = _normalize_path(perim)
            if any(_is_path_matching(ch, norm_perim) for ch in norm_changed):
                matched_perimeters.append(perim)
        if matched_perimeters:
            matches.append((entry, sorted(list(dict.fromkeys(matched_perimeters)))))

    return matches


def format_perimeter_warning(
    matches: Sequence[tuple[MitigatedFindingEntry, Sequence[str]]],
) -> str:
    """Format warning message for mitigated findings whose perimeter files changed."""
    n = len(matches)
    plural = "s" if n != 1 else ""
    header = f"{n} mitigated finding{plural} whose perimeter changed"
    lines = [f"[bold yellow]Warning: {header}:[/bold yellow]"]
    for entry, perim_list in matches:
        files_str = ", ".join(perim_list)
        lines.append(f"  • [yellow]'{entry.title}'[/yellow] (perimeter: [cyan]{files_str}[/cyan])")
    return "\n".join(lines)
