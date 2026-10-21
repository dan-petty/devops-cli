"""Diff parsing, line numbering, hunk extraction, and file block preparation (#1151)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_HUNK_MARKERS = (" ", "+", "-", "\\")
# A review line's number column: digits, or none on a removed diff line, then a tab.
_LINE_NUMBER_COLUMN = re.compile(r"^(\d*)\t", re.MULTILINE)


def _lines_with_ends(text: str) -> list[str]:
    """Split text at newlines only, as git and editors count lines; form feeds stay inside."""
    parts = text.split("\n")
    return [f"{part}\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def number_source_lines(text: str) -> str:
    """Prefix every line with its line number in the file and a tab.

    The number is part of the line, so any block cut from the file still shows where it is.
    """
    return "".join(f"{n}\t{line}" for n, line in enumerate(_lines_with_ends(text), 1))


def number_diff_lines(diff: str) -> str:
    """Prefix each hunk line of a unified diff with its line number in the new file and a tab.

    A removed line has no number in the new file and gets the tab alone. Hunk lengths from the
    `@@` headers decide where a hunk ends, so a removed line reading `--- x` stays a hunk line.
    """
    numbered: list[str] = []
    new_no = old_left = new_left = 0
    for line in _lines_with_ends(diff):
        in_hunk = (old_left > 0 or new_left > 0) and line.startswith(_HUNK_MARKERS)
        if not in_hunk and (match := _HUNK_HEADER.match(line)):
            old_left, new_no, new_left = int(match[1] or 1), int(match[2]), int(match[3] or 1)
        if not in_hunk:
            numbered.append(line)
            continue
        if line.startswith("-"):
            old_left -= 1
            numbered.append(f"\t{line}")
            continue
        if line.startswith("\\"):
            numbered.append(f"\t{line}")
            continue
        old_left -= line.startswith(" ")
        new_left -= 1
        numbered.append(f"{new_no}\t{line}")
        new_no += 1
    return "".join(numbered)


def strip_line_numbers(text: str) -> str:
    """Remove the line-number column that review blocks carry."""
    return _LINE_NUMBER_COLUMN.sub("", text)


def page_line_number(line: str) -> int | None:
    """The file line number a review line carries, or None when it carries none."""
    match = _LINE_NUMBER_COLUMN.match(line)
    return int(match[1]) if match and match[1] else None


def _is_numbered(line: str) -> bool:
    """Whether a review line carries the number column, empty or not."""
    return _LINE_NUMBER_COLUMN.match(line) is not None


def _parse_hunk_header_range(line: str) -> tuple[int, int] | None:
    """Parse (start, end) line range from diff @@ hunk header."""
    match = _HUNK_HEADER.match(line)
    if not match:
        return None
    start = int(match.group(2))
    count_str = match.group(3)
    count = int(count_str) if count_str is not None else 1
    end = start if count == 0 else start + count - 1
    return start, end


def extract_diff_hunks(diff_text: str) -> list[tuple[int, int]]:
    """Extract (start_line, end_line) ranges in the head file from unified diff hunk headers."""
    hunks: list[tuple[int, int]] = []
    for line in diff_text.splitlines():
        hunk_range = _parse_hunk_header_range(line)
        if hunk_range is not None:
            hunks.append(hunk_range)
    return hunks


def _parse_diff_header_filename(line: str) -> str | None:
    """Parse target file path from diff --git or ### File: line."""
    if line.startswith("diff --git "):
        parts = line.split()
        if len(parts) >= 4:
            return parts[3].removeprefix("b/")
    elif line.startswith("### File: "):
        fname = line.removeprefix("### File: ").split(" (part ", 1)[0].strip()
        if fname:
            return fname
    return None


def _process_diff_segment_lines(
    segment: str,
    current_file: str | None,
    file_hunks: dict[str, list[tuple[int, int]]],
) -> str | None:
    """Process lines in a single diff segment, appending hunk ranges."""
    for line in segment.splitlines():
        parsed_fn = _parse_diff_header_filename(line)
        if parsed_fn:
            current_file = parsed_fn
            file_hunks.setdefault(current_file, [])
            continue
        if current_file is not None:
            hunk_range = _parse_hunk_header_range(line)
            if hunk_range is not None:
                file_hunks[current_file].append(hunk_range)
    return current_file


def extract_file_diff_hunks(segments: Iterable[str]) -> dict[str, list[tuple[int, int]]]:
    """Map file paths to lists of (start_line, end_line) diff hunks across diff segments."""
    file_hunks: dict[str, list[tuple[int, int]]] = {}
    current_file: str | None = None
    for segment in segments:
        current_file = _process_diff_segment_lines(segment, current_file, file_hunks)
    return file_hunks


def diff_file_names(segment: str) -> list[str]:
    """Extract unique filenames from git diff ('diff --git') or file ('### File:') headers."""
    items: list[str] = []
    for line in segment.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                items.append(parts[3].removeprefix("b/"))
        elif line.startswith("### File: "):
            item = line.removeprefix("### File: ").strip()
            item = item.split(" (part ", 1)[0].strip()
            if item:
                items.append(item)
    return list(dict.fromkeys(items))


def _resolve_diff_path(line: str, current_path: str | None) -> str | None:
    """Resolve target file path from diff header line or retain existing path."""
    header_path = _parse_diff_header_filename(line)
    if header_path:
        return header_path
    if line.startswith("+++ b/"):
        return line[6:].strip()
    return current_path


def _parse_numbered_diff_line(line: str, path: str | None) -> tuple[str, int] | None:
    """Extract (path, line_number) if line is a numbered added line."""
    match = _LINE_NUMBER_COLUMN.match(line)
    if not (match and match[1]):
        return None
    content = line[match.end() :]
    if content.startswith("+") and not content.startswith("+++") and path:
        return (path, int(match[1]))
    return None


def _step_raw_diff_line(
    line: str, path: str | None, current_line: int
) -> tuple[int, tuple[str, int] | None]:
    """Advance raw unified diff line counter and return added coordinate if applicable."""
    hunk_range = _parse_hunk_header_range(line)
    if hunk_range is not None:
        return hunk_range[0], None
    if line.startswith("+") and not line.startswith("+++"):
        coord = (path, current_line) if (path and current_line > 0) else None
        return current_line + 1, coord
    next_line = current_line + 1 if (line.startswith(" ") or not line) else current_line
    return next_line, None


def extract_added_diff_lines(
    diff_text: str, default_path: str | None = None
) -> set[tuple[str, int]]:
    """Extract set of (file_path, new_line_number) coordinates for added lines in a diff.

    Handles both raw unified diffs and review blocks with prefixed line numbers.
    """
    added_lines: set[tuple[str, int]] = set()
    current_path = default_path
    current_line = 0

    for raw_line in diff_text.splitlines():
        line = raw_line.strip("\r")
        new_path = _resolve_diff_path(line, current_path)
        if new_path != current_path:
            current_path = new_path
            current_line = 0
            continue
        numbered_coord = _parse_numbered_diff_line(line, current_path)
        if numbered_coord:
            added_lines.add(numbered_coord)
            continue
        current_line, raw_coord = _step_raw_diff_line(line, current_path, current_line)
        if raw_coord:
            added_lines.add(raw_coord)

    return added_lines


def _stream_diff_file_blocks(line_iter: Iterator[str]) -> Iterator[str]:
    """Yield unified diff file blocks sequentially from a line iterator."""
    marker = "diff --git "
    current: list[str] = []
    for line in line_iter:
        if line.startswith(marker) and current:
            yield "".join(current)
            current = []
        current.append(line)
    if current:
        yield "".join(current)


def _split_diff_into_file_blocks(diff: str) -> list[str]:
    """Split a unified diff into one block per file, without cutting through a hunk."""
    blocks = list(_stream_diff_file_blocks(iter(_lines_with_ends(diff))))
    return blocks or [diff]


def diff_blocks(
    diff: str,
    path_classes: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Split a unified diff into one numbered block per file, skipping secret-scan-only files."""
    from devops_cli.review.targets import is_secret_scan_only

    blocks: list[str] = []
    for raw_block in _split_diff_into_file_blocks(diff):
        if not raw_block.strip():
            continue
        names = diff_file_names(raw_block.split("\n", 1)[0])
        if names and is_secret_scan_only(names[0], path_classes=path_classes):
            continue
        blocks.append(number_diff_lines(raw_block))
    return blocks


__all__ = [
    "diff_blocks",
    "diff_file_names",
    "extract_added_diff_lines",
    "extract_diff_hunks",
    "extract_file_diff_hunks",
    "number_diff_lines",
    "number_source_lines",
    "page_line_number",
    "strip_line_numbers",
]
