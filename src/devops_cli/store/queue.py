"""Local pending upload JSONL queue and OTel pending gauge helpers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.config.constants import CONST_STORE_PENDING_RELPATH
from devops_cli.core.repo import resolve_store_path
from devops_cli.exceptions.store import StoreError
from devops_cli.telemetry.instruments import STORE_PENDING_UPLOADS, emit


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PendingUpload:
    """One queued content-store upload persisted under `.data/store/pending.jsonl`."""

    kind: str
    local_path: str
    key: str
    sha256: str
    content_type: str
    replace: bool = False
    queued_at: str = field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        """Serialize one entry as a compact JSON line."""
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> PendingUpload:
        """Reconstruct a `PendingUpload` from parsed JSON object fields."""
        return cls(
            kind=str(raw["kind"]),
            local_path=str(raw["local_path"]),
            key=str(raw["key"]),
            sha256=str(raw["sha256"]),
            content_type=str(raw["content_type"]),
            replace=bool(raw.get("replace", False)),
            queued_at=str(raw.get("queued_at") or _now_iso()),
        )


def pending_queue_path() -> Path:
    """Return the resolved path of `store/pending.jsonl` under the active data directory."""
    return resolve_store_path(CONST_STORE_PENDING_RELPATH)


def set_pending_uploads_gauge(count: int) -> None:
    """Emit the current depth of the pending upload queue on `devops_cli_store_pending_uploads`."""
    emit(STORE_PENDING_UPLOADS, float(max(0, count)))


def read_pending_uploads(queue_path: Path | None = None) -> list[PendingUpload]:
    """Read all queued upload entries from `store/pending.jsonl`."""
    target = queue_path or pending_queue_path()
    if not target.exists():
        return []
    entries: list[PendingUpload] = []
    for line_no, raw_line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise StoreError(
                f"Pending store queue is corrupt at line {line_no} of {target}: {exc.msg}."
            ) from exc
        if not isinstance(parsed, dict):
            raise StoreError(f"Pending store queue entry at line {line_no} must be a JSON object.")
        entries.append(PendingUpload.from_mapping(parsed))
    return entries


def append_pending_upload(entry: PendingUpload, queue_path: Path | None = None) -> int:
    """Append one JSONL line to the pending queue, update the gauge, and return queue length."""
    target = queue_path or pending_queue_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(entry.to_json_line() + "\n")
    count = len(read_pending_uploads(target))
    set_pending_uploads_gauge(count)
    return count


def write_pending_uploads(entries: Sequence[PendingUpload], queue_path: Path | None = None) -> int:
    """Rewrite `pending.jsonl` with remaining entries, update the gauge, and return count."""
    target = queue_path or pending_queue_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(f"{entry.to_json_line()}\n" for entry in entries)
    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(target)
    count = len(entries)
    set_pending_uploads_gauge(count)
    return count
