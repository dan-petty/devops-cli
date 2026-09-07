"""Pure-Python RESP2 and RESP3 wire protocol encoder and parser."""

from __future__ import annotations

import io
from typing import Any

from devops_cli.exceptions.valkey import (
    ValkeyCommandError,
    ValkeyConnectionError,
)


def encode_command(*parts: Any) -> bytes:
    """Encode command and arguments into standard RESP wire protocol array."""
    out = io.BytesIO()
    out.write(f"*{len(parts)}\r\n".encode())
    for p in parts:
        if isinstance(p, bytes):
            b_val = p
        elif isinstance(p, bool):
            b_val = b"true" if p else b"false"
        else:
            b_val = str(p).encode("utf-8")
        out.write(f"${len(b_val)}\r\n".encode())
        out.write(b_val)
        out.write(b"\r\n")
    return out.getvalue()


def _parse_bulk_string(reader: io.BufferedIOBase, length: int) -> str | None:
    """Read bulk string payload of exact length."""
    if length == -1:
        return None
    raw = reader.read(length)
    reader.read(2)  # Consume trailing \r\n
    return raw.decode("utf-8", errors="replace")


def _parse_array(reader: io.BufferedIOBase, length: int) -> list[Any] | None:
    """Read array elements recursively."""
    if length == -1:
        return None
    return [parse_resp(reader) for _ in range(length)]


def _parse_map(reader: io.BufferedIOBase, length: int) -> dict[Any, Any]:
    """Read RESP3 key-value map."""
    result: dict[Any, Any] = {}
    for _ in range(length):
        k = parse_resp(reader)
        v = parse_resp(reader)
        result[k] = v
    return result


def _parse_set(reader: io.BufferedIOBase, length: int) -> set[Any]:
    """Read RESP3 set elements."""
    return {parse_resp(reader) for _ in range(length)}


def _dispatch_prefix_payload(prefix: bytes, line: str, reader: io.BufferedIOBase) -> Any:
    """Dispatch decoding based on RESP protocol prefix byte."""
    if prefix == b"+":
        return line
    if prefix == b":":
        return int(line)
    if prefix == b"$":
        return _parse_bulk_string(reader, int(line))
    if prefix == b"*":
        return _parse_array(reader, int(line))
    if prefix == b"#":
        return line.lower() == "t"
    if prefix == b",":
        return float(line)
    if prefix == b"%":
        return _parse_map(reader, int(line))
    if prefix == b"~":
        return _parse_set(reader, int(line))
    if prefix == b"_":
        return None
    raise ValkeyCommandError(
        f"Unknown RESP type prefix: {prefix.decode('latin1', errors='replace')!r}"
    )


def parse_resp(reader: io.BufferedIOBase) -> Any:
    """Parse next RESP response token or structure from buffered socket reader."""
    prefix = reader.read(1)
    if not prefix:
        raise ValkeyConnectionError("Unexpected end of stream while reading from Valkey socket.")

    raw_line = reader.readline()
    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")

    if prefix == b"-":
        raise ValkeyCommandError(line, command=line.split()[0] if line else None)

    return _dispatch_prefix_payload(prefix, line, reader)
