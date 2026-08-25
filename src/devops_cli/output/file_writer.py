"""Secure, defensive, and atomic file output generation utilities."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


def write_text_file(
    path: Path | str,
    content: str,
    *,
    atomic: bool = True,
    encoding: str = "utf-8",
    mode: int | None = None,
) -> Path:
    """Write text content to a file with directory creation and optional atomic replacement.

    Args:
        path: Target file path.
        content: String content to write.
        atomic: If True, writes via temporary file and atomic replace to prevent partial writes.
        encoding: File character encoding (default utf-8).
        mode: Optional octal file permission mode (e.g. 0o600 for secrets, 0o644 for public docs).

    Returns:
        The resolved Path to the written file.
    """
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    file_mode = mode if mode is not None else 0o644

    if atomic:
        temp_dir = target_path.parent
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=temp_dir,
            encoding=encoding,
            delete=False,
            prefix=f".tmp_{target_path.name}_",
        ) as tmp:
            if mode is not None:
                os.chmod(tmp.name, mode)
            tmp.write(content)
            tmp_path = Path(tmp.name)

        if mode is not None:
            tmp_path.chmod(mode)
        os.replace(tmp_path, target_path)
    else:
        fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
        if mode is not None:
            target_path.chmod(mode)

    return target_path


def write_serialized_file(
    path: Path | str,
    data: Any,
    format_type: str = "json",
    *,
    indent: int = 2,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Serialize data as JSON or YAML and write to file with optional atomic replacement."""
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, list):
        data = [item.model_dump() if hasattr(item, "model_dump") else item for item in data]

    fmt = format_type.lower()
    if fmt in ("yaml", "yml"):
        content = yaml.dump(data, sort_keys=False, default_flow_style=False)
    else:
        content = json.dumps(data, indent=indent, default=str) + "\n"

    return write_text_file(path, content, atomic=atomic, mode=mode)


def write_json_file(
    path: Path | str,
    data: Any,
    *,
    indent: int = 2,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Serialize data as structured JSON and write to file."""
    return write_serialized_file(
        path, data, format_type="json", indent=indent, atomic=atomic, mode=mode
    )


def write_yaml_file(
    path: Path | str,
    data: Any,
    *,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Serialize data as YAML and write to file."""
    return write_serialized_file(path, data, format_type="yaml", atomic=atomic, mode=mode)


def write_bytes_file(
    path: Path | str,
    data: bytes,
    *,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Write binary data to file with directory creation and optional atomic replacement."""
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    file_mode = mode if mode is not None else 0o644

    if atomic:
        temp_dir = target_path.parent
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=temp_dir,
            delete=False,
            prefix=f".tmp_{target_path.name}_",
        ) as tmp:
            if mode is not None:
                os.chmod(tmp.name, mode)
            tmp.write(data)
            tmp_path = Path(tmp.name)

        if mode is not None:
            tmp_path.chmod(mode)
        os.replace(tmp_path, target_path)
    else:
        fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        if mode is not None:
            target_path.chmod(mode)

    return target_path
