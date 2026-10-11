"""Active marginalia and epistemic scratchpad storage and retrieval."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from devops_cli.ai.research.models import MarginaliaRecord
from devops_cli.config.constants import CONST_MARGINALIA_TYPES
from devops_cli.config.settings import load_settings
from devops_cli.core.repo import find_repo_root, find_worktree_root


def compute_file_hash(rel_path: str) -> str:
    """Compute deterministic SHA-256 digest for relative file path."""
    return hashlib.sha256(rel_path.strip().encode("utf-8")).hexdigest()


def _resolve_repo_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root
    return find_worktree_root(Path.cwd()) or find_repo_root(Path.cwd()) or Path.cwd()


def resolve_marginalia_dir(repo_root: Path | None = None) -> Path:
    """Resolve active marginalia directory honoring DEVOPS_CLI_DATA_DIR and settings."""
    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_data_dir:
        base_dir = Path(env_data_dir)
    else:
        base_dir = Path(load_settings().data.dir)

    if not base_dir.is_absolute():
        root = _resolve_repo_root(repo_root)
        base_dir = root / base_dir

    return base_dir / "marginalia"


def resolve_relative_path(file_path: str | Path, repo_root: Path | None = None) -> str:
    """Normalize file path to POSIX relative path from repository root."""
    root = _resolve_repo_root(repo_root)
    p = Path(file_path)
    if p.is_absolute() and p.is_relative_to(root):
        return p.relative_to(root).as_posix()
    return p.as_posix()


def get_marginalia_path(file_path: str | Path, repo_root: Path | None = None) -> Path:
    """Get destination JSONL file path for marginalia associated with target file."""
    rel_path = resolve_relative_path(file_path, repo_root)
    file_hash = compute_file_hash(rel_path)
    return resolve_marginalia_dir(repo_root) / f"{file_hash}.jsonl"


def read_marginalia(file_path: str | Path, repo_root: Path | None = None) -> list[MarginaliaRecord]:
    """Read all persistent marginalia records for a given file."""
    jsonl_path = get_marginalia_path(file_path, repo_root)
    if not jsonl_path.is_file():
        return []

    records: list[MarginaliaRecord] = []
    try:
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line_str = line.strip()
            if line_str:
                records.append(MarginaliaRecord.model_validate_json(line_str))
    except OSError, ValueError:
        return []

    return records


def write_marginalia(record: MarginaliaRecord, repo_root: Path | None = None) -> Path:
    """Append a marginalia record to target file's persistent JSONL log."""
    jsonl_path = get_marginalia_path(record.file_path, repo_root)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return jsonl_path


def annotate_file(
    file_path: str | Path,
    type: str,
    content: str,
    anchor: str | None = None,
    session_id: str | None = None,
    repo_root: Path | None = None,
) -> MarginaliaRecord:
    """Create and persist a typed marginalia annotation anchored to a file, AST node, or range."""
    type_norm = type.strip().upper()
    if type_norm not in CONST_MARGINALIA_TYPES:
        raise ValueError(
            f"Invalid marginalia type '{type}'. Must be one of {CONST_MARGINALIA_TYPES}"
        )

    rel_path = resolve_relative_path(file_path, repo_root)
    file_hash = compute_file_hash(rel_path)
    anchor_str = anchor if anchor else rel_path
    now_str = datetime.now(UTC).isoformat()

    record = MarginaliaRecord(
        file_path=rel_path,
        file_hash=file_hash,
        type=type_norm,
        content=content.strip(),
        anchor=anchor_str,
        created_at=now_str,
        session_id=session_id,
    )
    write_marginalia(record, repo_root)
    return record
