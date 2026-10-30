"""The words of the command that `subprocess.Popen(args)` starts, for the guards that refuse a
program by name: the one of the root conftest and the one of the git fake (#2146)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def started_words(args: Any) -> list[str]:
    """The tokenized argv words that `subprocess.Popen(args)` starts: a command line (a string,
    bytes or path, as `shell=True` takes it) is split on white space, and bytes are decoded."""
    if isinstance(args, (str, bytes, os.PathLike)):
        return os.fsdecode(args).split()
    return [os.fsdecode(word) for word in args] if args else []


def started_program(args: Any) -> str:
    """The name of the program that `subprocess.Popen(args)` starts, or an empty text."""
    words = started_words(args)
    return Path(words[0]).name if words else ""
