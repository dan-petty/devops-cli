"""Fixtures that the agent-audit test files share."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest


def write_transcript(path: Path, records: Sequence[Mapping[str, Any]]) -> Path:
    """Write `records` as one JSON object per line, and make the directory of `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


@pytest.fixture
def transcript_writer() -> Callable[[Path, Sequence[Mapping[str, Any]]], Path]:
    """Write a Claude Code transcript of `records` at `path`, for the reader to read."""
    return write_transcript
