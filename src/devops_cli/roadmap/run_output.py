"""The output of one planner run: masked, capped and quoted for the `## Feasibility` section
(#4006, ADR 0018).

A command that the planner runs can print more text than a plan holds, and it can print a
credential. The mask runs first, so the cap never cuts a private-key block before its end marker,
which would leave key material that no pattern masks. The cap keeps the first whole lines, and its
trailer names the omitted bytes and lines.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from devops_cli.security.sanitizer import mask_secrets

# The cap of ADR 0018 for the text of one run, the trailer line included.
MAX_RUN_OUTPUT_BYTES: Final[int] = 8 * 1024
MAX_RUN_OUTPUT_LINES: Final[int] = 120


@dataclass(frozen=True)
class CappedOutput:
    """The masked and capped text of a run, and the counts that the trailer states."""

    text: str
    omitted_bytes: int = 0
    omitted_lines: int = 0


def _trailer(omitted_bytes: int, omitted_lines: int) -> str:
    return f"[truncated: {omitted_bytes} bytes and {omitted_lines} lines omitted]"


def cap_run_output(
    text: str,
    *,
    limit_bytes: int = MAX_RUN_OUTPUT_BYTES,
    limit_lines: int = MAX_RUN_OUTPUT_LINES,
) -> CappedOutput:
    """Mask `text`, cut it at a line boundary to the caps, and add the trailer when it cuts.

    The caps cover the trailer line. `omitted_bytes` and `omitted_lines` count the masked input
    that the kept body does not hold.
    """
    masked = mask_secrets(text)
    data = masked.encode("utf-8")
    lines = masked.splitlines(keepends=True)
    total_lines = len(masked.splitlines())
    if len(data) <= limit_bytes and total_lines <= limit_lines:
        return CappedOutput(masked)

    kept: list[str] = []
    kept_bytes = 0
    for line in lines:
        if len(kept) + 1 >= limit_lines:
            break
        size = len(line.encode("utf-8"))
        if kept_bytes + size + len(_trailer(0, 0)) + 1 > limit_bytes:
            break
        kept.append(line)
        kept_bytes += size

    while True:
        omitted_bytes = len(data) - kept_bytes
        omitted_lines = total_lines - len(kept)
        candidate = "".join(kept) + _trailer(omitted_bytes, omitted_lines) + "\n"
        if (
            len(candidate.encode("utf-8")) <= limit_bytes
            and len(candidate.splitlines()) <= limit_lines
        ):
            return CappedOutput(candidate, omitted_bytes, omitted_lines)
        if not kept:
            return CappedOutput(
                _trailer(omitted_bytes, omitted_lines) + "\n", omitted_bytes, omitted_lines
            )
        kept_bytes -= len(kept.pop().encode("utf-8"))


def _longest_backtick_run(text: str) -> int:
    return max((len(run.group(0)) for run in re.finditer(r"`+", text)), default=0)


def quote_run(
    command: Sequence[str],
    exit_code: int,
    stdout: str,
    stderr: str,
) -> str:
    """The capped text in a fenced block that holds the command line, the exit code and the text.

    The fence is one backtick longer than the longest backtick run in the text, so no line of the
    text closes the block.
    """
    text = stdout
    if stderr:
        if text and not text.endswith("\n"):
            text += "\n"
        text += stderr
    capped = cap_run_output(text)
    fence = "`" * max(3, _longest_backtick_run(capped.text) + 1)
    return f"{fence}\n$ {' '.join(command)}\nexit {exit_code}\n{capped.text}{fence}\n"
