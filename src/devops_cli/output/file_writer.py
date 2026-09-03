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
from devops_cli.exceptions import SecurityError

FileFormat = Literal["text", "bytes", "json", "yaml", "yml", "auto"]


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
    target_path = Path(path).resolve()
    if base_dir is not None:
        resolved_base = Path(base_dir).resolve()
        if not target_path.is_relative_to(resolved_base):
            msg = f"Target path {target_path} escapes allowed base directory {resolved_base}"
            raise SecurityError(msg)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    file_mode = mode if mode is not None else 0o644

    fmt = format_type.lower()
    if fmt == "auto":
        if isinstance(content, bytes):
            fmt = "bytes"
        elif isinstance(content, (dict, list)) or hasattr(content, "model_dump"):
            ext = target_path.suffix.lower()
            fmt = "yaml" if ext in (".yaml", ".yml") else "json"
        else:
            fmt = "text"

    is_binary = fmt == "bytes" or isinstance(content, bytes)

    if fmt in ("yaml", "yml"):
        dump_data = content.model_dump() if hasattr(content, "model_dump") else content
        if isinstance(dump_data, list):
            dump_data = [i.model_dump() if hasattr(i, "model_dump") else i for i in dump_data]
        text_payload = yaml.dump(dump_data, sort_keys=False, default_flow_style=False)
    elif fmt == "json":
        dump_data = content.model_dump() if hasattr(content, "model_dump") else content
        if isinstance(dump_data, list):
            dump_data = [i.model_dump() if hasattr(i, "model_dump") else i for i in dump_data]
        text_payload = json.dumps(dump_data, indent=indent, default=str) + "\n"
    elif is_binary:
        byte_payload = content if isinstance(content, bytes) else str(content).encode(encoding)
    else:
        text_payload = str(content)

    if atomic:
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
            if is_binary:
                tmp.write(byte_payload)
            else:
                tmp.write(text_payload)
            tmp_path = Path(tmp.name)

        if mode is not None:
            tmp_path.chmod(mode)
        os.replace(tmp_path, target_path)
    else:
        fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, file_mode)
        if is_binary:
            with os.fdopen(fd, "wb") as fh:
                fh.write(byte_payload)
        else:
            with os.fdopen(fd, "w", encoding=encoding) as fh:
                fh.write(text_payload)
        if mode is not None:
            target_path.chmod(mode)

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
