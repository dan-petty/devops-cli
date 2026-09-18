"""Secure, defensive, and atomic file output generation utilities."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

import yaml

from devops_cli.config.defaults import (
    DEFAULT_FILE_ENCODING,
    DEFAULT_FILE_FORMAT_AUTO,
    DEFAULT_FORMAT_TYPE,
    DEFAULT_JSON_INDENT,
)
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.exceptions import SecurityError

FileFormat = Literal["text", "bytes", "json", "yaml", "yml", "auto"]


def _validate_target_path(path: Path | str, base_dir: Path | str | None) -> Path:
    """Validate path traversal and system path constraints, returning resolved Path."""
    validate_no_path_traversal(path)
    target_path = Path(path).resolve()
    if is_forbidden_system_path(target_path):
        msg = f"Target path {target_path} resolves to a forbidden system directory"
        raise SecurityError(msg)
    if base_dir is not None:
        resolved_base = Path(base_dir).resolve()
        if not target_path.is_relative_to(resolved_base):
            msg = f"Target path {target_path} escapes allowed base directory {resolved_base}"
            raise SecurityError(msg)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def _resolve_format(content: Any, format_type: FileFormat, target_path: Path) -> str:
    """Resolve serialization format string."""
    fmt = format_type.lower()
    if fmt != "auto":
        return fmt
    if isinstance(content, bytes):
        return "bytes"
    if isinstance(content, (dict, list)) or hasattr(content, "model_dump"):
        ext = target_path.suffix.lower()
        return "yaml" if ext in (".yaml", ".yml") else "json"
    return "text"


def _to_serializable_data(content: Any) -> Any:
    """Normalize Pydantic models or lists of models into serializable dict structures."""
    dump_data = content.model_dump() if hasattr(content, "model_dump") else content
    if isinstance(dump_data, list):
        return [i.model_dump() if hasattr(i, "model_dump") else i for i in dump_data]
    return dump_data


def _serialize_content(
    content: Any,
    fmt: str,
    indent: int,
    encoding: str,
) -> tuple[bytes | None, str | None, bool]:
    """Serialize input content into byte or text payload."""
    if fmt in ("yaml", "yml"):
        data = _to_serializable_data(content)
        return None, yaml.dump(data, sort_keys=False, default_flow_style=False), False
    if fmt == "json":
        data = _to_serializable_data(content)
        return None, json.dumps(data, indent=indent, default=str) + "\n", False
    if fmt == "bytes" or isinstance(content, bytes):
        payload = content if isinstance(content, bytes) else str(content).encode(encoding)
        return payload, None, True
    return None, str(content), False


def _write_atomic_payload(
    target_path: Path,
    byte_payload: bytes | None,
    text_payload: str | None,
    is_binary: bool,
    mode: int | None,
    encoding: str,
) -> None:
    """Write payload using temporary file and atomic rename."""
    temp_dir = target_path.parent
    write_mode = "wb" if is_binary else "w"
    open_kwargs: dict[str, Any] = {
        "mode": write_mode,
        "dir": temp_dir,
        "delete": False,
        "prefix": f".tmp_{target_path.name}_",
    }
    if not is_binary:
        open_kwargs["encoding"] = encoding

    with tempfile.NamedTemporaryFile(**open_kwargs) as tmp:
        if mode is not None:
            os.chmod(tmp.name, mode)
        if is_binary and byte_payload is not None:
            tmp.write(byte_payload)
        elif text_payload is not None:
            tmp.write(text_payload)
        tmp_path = Path(tmp.name)

    if mode is not None:
        tmp_path.chmod(mode)
    os.replace(tmp_path, target_path)


def _write_direct_payload(
    target_path: Path,
    byte_payload: bytes | None,
    text_payload: str | None,
    is_binary: bool,
    mode: int | None,
    encoding: str,
) -> None:
    """Write payload directly to target file descriptor."""
    file_mode = mode if mode is not None else 0o644
    fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
    if is_binary and byte_payload is not None:
        with os.fdopen(fd, "wb") as fh:
            fh.write(byte_payload)
    elif text_payload is not None:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text_payload)
    if mode is not None:
        target_path.chmod(mode)


def write_file(
    path: Path | str,
    content: Any,
    *,
    format_type: FileFormat = DEFAULT_FILE_FORMAT_AUTO,
    atomic: bool = True,
    encoding: str = DEFAULT_FILE_ENCODING,
    indent: int = DEFAULT_JSON_INDENT,
    mode: int | None = None,
    base_dir: Path | str | None = None,
) -> Path:
    """Write text, binary, JSON, or YAML content to a file with directory creation and atomic replacement.

    Args:
        path: Target destination file path.
        content: Data content to write (str, bytes, Pydantic model, dict, list, or primitive).
        format_type: Serialization or content format ('text', 'bytes', 'json', 'yaml', or 'auto').
        atomic: If True, writes via temporary file and atomic replace to prevent partial writes.
        encoding: File character encoding for text formats (default utf-8).
        indent: JSON indentation spaces.
        mode: Optional octal file permission mode (e.g. 0o600 for secrets, 0o644 for public files).
        base_dir: Optional root directory boundary that path must reside within.

    Returns:
        The resolved Path to the written file.
    """
    target_path = _validate_target_path(path, base_dir)
    fmt = _resolve_format(content, format_type, target_path)
    byte_payload, text_payload, is_binary = _serialize_content(content, fmt, indent, encoding)

    if atomic:
        _write_atomic_payload(target_path, byte_payload, text_payload, is_binary, mode, encoding)
    else:
        _write_direct_payload(target_path, byte_payload, text_payload, is_binary, mode, encoding)

    return target_path


def write_text_file(
    path: Path | str,
    content: str,
    *,
    atomic: bool = True,
    encoding: str = DEFAULT_FILE_ENCODING,
    mode: int | None = None,
) -> Path:
    """Write text content to a file with directory creation and optional atomic replacement."""
    return write_file(
        path, content, format_type="text", atomic=atomic, encoding=encoding, mode=mode
    )


def write_serialized_file(
    path: Path | str,
    data: Any,
    format_type: str = DEFAULT_FORMAT_TYPE,
    *,
    indent: int = DEFAULT_JSON_INDENT,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Serialize data as JSON or YAML and write to file with optional atomic replacement."""
    fmt: FileFormat = "yaml" if format_type.lower() in ("yaml", "yml") else "json"
    return write_file(path, data, format_type=fmt, indent=indent, atomic=atomic, mode=mode)


def write_json_file(
    path: Path | str,
    data: Any,
    *,
    indent: int = DEFAULT_JSON_INDENT,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Serialize data as structured JSON and write to file."""
    return write_file(path, data, format_type="json", indent=indent, atomic=atomic, mode=mode)


def write_yaml_file(
    path: Path | str,
    data: Any,
    *,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Serialize data as YAML and write to file."""
    return write_file(path, data, format_type="yaml", atomic=atomic, mode=mode)


def write_bytes_file(
    path: Path | str,
    data: bytes,
    *,
    atomic: bool = True,
    mode: int | None = None,
) -> Path:
    """Write binary data to file with directory creation and optional atomic replacement."""
    return write_file(path, data, format_type="bytes", atomic=atomic, mode=mode)
