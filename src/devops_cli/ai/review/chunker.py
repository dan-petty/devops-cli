"""Diff slicing, source code windowing, file discovery, and segment chunking."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from devops_cli.ai.review.sanitization import _unique_preserve_order
from devops_cli.config.constants import (
    CONST_BINARY_EXTENSIONS,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_REVIEW_CHARS_PER_TOKEN,
    CONST_REVIEW_GENERATED_FILES,
    CONST_REVIEW_PAGE_WINDOW_SHARE,
)
from devops_cli.config.defaults import (
    DEFAULT_MATCH_ALL_PATTERN,
    DEFAULT_REVIEW_MAX_DIFF_CHARS,
    DEFAULT_REVIEW_MIN_DIFF_CHARS,
    DEFAULT_REVIEW_OVERLAP_FACTOR,
    DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
)
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.exceptions import SecurityError

_CODE_LINE_SKIP_PREFIXES = ("diff --git", "index ", "--- ", "+++ ", "@@ ", "### File: ", "```")
_BLOCK_HEADERS = ("diff --git ", "### File: ")
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_HUNK_MARKERS = (" ", "+", "-", "\\")
# A review page line's number column: digits, or none on a removed diff line, then a tab.
_LINE_NUMBER_COLUMN = re.compile(r"^(\d*)\t", re.MULTILINE)


def _lines_with_ends(text: str) -> list[str]:
    """Split text at newlines only, as git and editors count lines; form feeds stay inside."""
    parts = text.split("\n")
    return [f"{part}\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def number_source_lines(text: str) -> str:
    """Prefix every line with its line number in the file and a tab.

    The number is part of the line, so any page cut from the file still shows where it is.
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
    """Remove the line-number column that review pages carry."""
    return _LINE_NUMBER_COLUMN.sub("", text)


def _is_numbered(line: str) -> bool:
    """Whether a review page line carries the number column, empty or not."""
    return _LINE_NUMBER_COLUMN.match(line) is not None


def page_line_number(line: str) -> int | None:
    """The file line number a review page line carries, or None when it carries none."""
    match = _LINE_NUMBER_COLUMN.match(line)
    return int(match[1]) if match and match[1] else None


def _extract_header_filenames(segment: str, header_type: str = "all") -> list[str]:
    """Extract filenames from git diff ('diff --git') or file ('### File:') headers."""
    items: list[str] = []
    for line in segment.splitlines():
        if header_type in ("diff", "all") and line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                items.append(parts[2].removeprefix("a/"))
        elif header_type in ("path", "file", "all") and line.startswith("### File: "):
            item = line.removeprefix("### File: ").strip()
            item = item.split(" (part ", 1)[0].strip()
            if item:
                items.append(item)
    return _unique_preserve_order(items)


def _extract_code_lines(segment: str, n: int) -> tuple[list[str], list[str]]:
    """Extract the first and last N non-header code lines from a segment."""
    lines = [
        line.rstrip()
        for line in segment.splitlines()
        if line.strip() and not any(line.startswith(p) for p in _CODE_LINE_SKIP_PREFIXES)
    ]
    return lines[:n], lines[-n:] if len(lines) > n else []


def _split_text_lines(text: str, max_chars: int) -> list[str]:
    """Split text into chunks on line boundaries, avoiding mid-line splits when possible."""
    if not text:
        return [""]

    lines = _lines_with_ends(text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line)
        if line_len > max_chars:
            if current:
                chunks.append("".join(current))
                current, current_len = [], 0
            chunks.extend(line[i : i + max_chars] for i in range(0, line_len, max_chars))
            continue
        if current and current_len + line_len > max_chars:
            chunks.append("".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("".join(current))
    return chunks


def _render_source_block(rel: Path, suffix: str, text: str, index: int = 1, total: int = 1) -> str:
    title = f"### File: {rel}" if total == 1 else f"### File: {rel} (part {index}/{total})"
    return f"{title}\n```{suffix}\n{text.removesuffix('\n')}\n```"


def _compute_line_slices(lines: list[str], window_cap: int) -> list[tuple[int, int]]:
    """Partition lines into slice ranges fitting within window capacity."""
    line_counts = len(lines)
    slices: list[tuple[int, int]] = []
    start_idx = 0
    while start_idx < line_counts:
        curr_len = 0
        end_idx = start_idx
        while end_idx < line_counts and curr_len + len(lines[end_idx]) <= window_cap:
            curr_len += len(lines[end_idx])
            end_idx += 1
        if end_idx == start_idx:
            end_idx = start_idx + 1
        slices.append((start_idx, end_idx))
        start_idx = end_idx
    return slices


def _extract_top_overlap(lines: list[str], start_idx: int, overlap_cap: int) -> str:
    """Extract preceding overlap context lines for a window slice."""
    if start_idx <= 0:
        return ""
    top_lines: list[str] = []
    top_len = 0
    for idx in range(start_idx - 1, -1, -1):
        if top_len + len(lines[idx]) > overlap_cap:
            break
        top_lines.insert(0, lines[idx])
        top_len += len(lines[idx])
    return "".join(top_lines) if top_lines else ""


def _extract_bottom_overlap(lines: list[str], end_idx: int, overlap_cap: int) -> str:
    """Extract succeeding overlap context lines for a window slice."""
    line_counts = len(lines)
    if end_idx >= line_counts:
        return ""
    bot_lines: list[str] = []
    bot_len = 0
    for idx in range(end_idx, line_counts):
        if bot_len + len(lines[idx]) > overlap_cap:
            break
        bot_lines.append(lines[idx])
        bot_len += len(lines[idx])
    return "".join(bot_lines) if bot_lines else ""


def _overlapping_windows(
    lines: list[str],
    budget: int,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[list[str]]:
    """Group lines into windows of at most `budget` characters that overlap their neighbours.

    Each window's core is followed on the next window by a few lines of the previous one, so a
    defect at a boundary is seen whole on one of them. A window still too long is cut into
    pieces of the budget, keeping the whole window's part number.
    """
    window_cap = max(100, int(budget * window_size_factor))
    overlap_cap = max(10, int(budget * overlap_factor))
    windows: list[list[str]] = []
    for s_idx, e_idx in _compute_line_slices(lines, window_cap):
        body = (
            f"{_extract_top_overlap(lines, s_idx, overlap_cap)}{''.join(lines[s_idx:e_idx])}"
            f"{_extract_bottom_overlap(lines, e_idx, overlap_cap)}"
        )
        windows.append(_split_text_lines(body, budget) if len(body) > budget else [body])
    return windows


def _split_source_file_blocks(
    rel: Path,
    suffix: str,
    text: str,
    max_chars: int = DEFAULT_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Split a source file into numbered review windows, overlapping and each with its header."""
    numbered = number_source_lines(text)
    block = _render_source_block(rel, suffix, numbered)
    if len(block) <= max_chars:
        return [block]

    overhead = len(_render_source_block(rel, suffix, "", 1, 9999))
    payload_budget = max_chars - overhead
    if payload_budget <= 0:
        return _split_text_lines(block, max_chars)

    windows = _overlapping_windows(
        _lines_with_ends(numbered), payload_budget, window_size_factor, overlap_factor
    )
    return [
        _render_source_block(rel, suffix, piece, part_idx, len(windows))
        for part_idx, pieces in enumerate(windows, 1)
        for piece in pieces
    ]


def _paginate_source_block(
    block: str,
    max_chars: int = DEFAULT_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Page a rendered source block, repeating its header and fences on every page."""
    lines = _lines_with_ends(block)
    head_end = 2 if len(lines) > 1 and lines[1].startswith("```") else 1
    tail_start = len(lines) - 1 if lines[-1].startswith("```") else len(lines)
    head, tail = "".join(lines[:head_end]), "".join(lines[max(head_end, tail_start) :])
    body = lines[head_end:tail_start]
    budget = max_chars - len(head) - len(tail)
    if not body or budget <= 0:
        return _split_text_lines(block, max_chars)
    windows = _overlapping_windows(body, budget, window_size_factor, overlap_factor)
    return [f"{head}{piece}{tail}" for pieces in windows for piece in pieces]


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


def _paginate_file_diff_block(
    block: str,
    max_chars: int = DEFAULT_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Paginate a file's diff block using rolling windows with top/bottom overlap."""
    if len(block) <= max_chars:
        return [block]

    lines = _lines_with_ends(block)
    # A page cut mid-hunk has no `@@` line; its first numbered line ends the preamble instead.
    hunk_start = next(
        (i for i, line in enumerate(lines) if line.startswith("@@ ") or _is_numbered(line)),
        len(lines),
    )
    preamble = "".join(lines[:hunk_start])
    body_lines = lines[hunk_start:]

    if not body_lines or len(preamble) >= max_chars:
        return _split_text_lines(block, max_chars)

    windows = _overlapping_windows(
        body_lines, max_chars - len(preamble), window_size_factor, overlap_factor
    )
    return [f"{preamble}{piece}" for pieces in windows for piece in pieces]


def _is_generated_diff_block(block: str) -> bool:
    """Return True if the block's diff header names a known autogenerated file."""
    first = block.splitlines()[0] if block else ""
    if not first.startswith("diff --git "):
        return False
    parts = first.split()
    filename = parts[2].removeprefix("a/") if len(parts) >= 4 else ""
    return Path(filename).name in CONST_REVIEW_GENERATED_FILES


def review_page_chars(context_window: int) -> int:
    """Return the diff characters one review page may hold within a model's context window.

    The page fills a fixed share of the window so the persona prompt and the reply still fit,
    bounded below so a small window cannot fragment a diff and above by the historical cap.
    """
    budget = int(context_window * CONST_REVIEW_CHARS_PER_TOKEN * CONST_REVIEW_PAGE_WINDOW_SHARE)
    return max(DEFAULT_REVIEW_MIN_DIFF_CHARS, min(DEFAULT_REVIEW_MAX_DIFF_CHARS, budget))


def diff_stream_chunks(
    diff_stream: Iterable[str] | str,
    max_chars: int = DEFAULT_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> Iterator[str]:
    """Stream unified diff chunks file-by-file with rolling window pagination.

    Consumes diff lines lazily without buffering full diff files in memory,
    reducing peak allocation on resource-constrained containers.
    """
    line_iter = (
        iter(_lines_with_ends(diff_stream)) if isinstance(diff_stream, str) else iter(diff_stream)
    )
    yielded_any = False
    for block in _stream_diff_file_blocks(line_iter):
        if not block.strip() or _is_generated_diff_block(block):
            continue
        file_pages = _paginate_file_diff_block(
            number_diff_lines(block),
            max_chars=max_chars,
            window_size_factor=window_size_factor,
            overlap_factor=overlap_factor,
        )
        for page in file_pages:
            yielded_any = True
            yield page

    if not yielded_any:
        yield ""


def diff_pages(
    diff: str,
    max_chars: int = DEFAULT_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Paginate a unified diff file-by-file into individual review pages using rolling windows."""
    return list(
        diff_stream_chunks(
            diff,
            max_chars=max_chars,
            window_size_factor=window_size_factor,
            overlap_factor=overlap_factor,
        )
    )


def _review_blocks(text: str) -> list[str]:
    """Split one file's review text at each diff or source-file header."""
    blocks: list[list[str]] = []
    for line in _lines_with_ends(text):
        if line.startswith(_BLOCK_HEADERS) or not blocks:
            blocks.append([])
        blocks[-1].append(line)
    return ["".join(block) for block in blocks]


def split_review_pages(
    text: str,
    max_chars: int = DEFAULT_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Split a file's review text into pages of at most `max_chars`.

    Every page repeats its block's header (the `### File:` title and fence, or the diff
    preamble) and overlaps its neighbours. Lines keep the numbers they already carry.
    """
    if len(text) <= max_chars:
        return [text]
    return [
        page
        for block in _review_blocks(text)
        for page in (
            _paginate_source_block if block.startswith("### File: ") else _paginate_file_diff_block
        )(block, max_chars, window_size_factor, overlap_factor)
    ]


def _is_reviewable_candidate_file(
    candidate: Path,
    root: Path,
    max_file_size: int,
    excluded_dirs: set[str] | None = None,
) -> bool:
    """Check if candidate file meets review criteria (non-symlink, within root, text, non-ignored)."""
    if candidate.is_symlink() or not candidate.is_file():
        return False
    try:
        if not candidate.resolve().is_relative_to(root):
            return False
    except OSError, RuntimeError:
        return False
    if excluded_dirs and any(part in excluded_dirs for part in candidate.parts):
        return False
    if is_ignored_by_git(root, candidate):
        return False
    if candidate.suffix.lower() in CONST_BINARY_EXTENSIONS:
        return False
    try:
        if candidate.stat().st_size > max_file_size:
            return False
    except OSError:
        return False
    return True


def find_repo_files(
    target: Path,
    pattern: str = DEFAULT_MATCH_ALL_PATTERN,
    max_file_size: int = CONST_MAX_FILE_SIZE_BYTES,
    excluded_dirs: set[str] | None = None,
    repo_root: Path | None = None,
) -> list[Path]:
    """Discover reviewable source files under target, skipping binary and symlinked paths."""
    root = (repo_root or target).resolve()
    target_resolved = target.resolve()
    if not target_resolved.is_relative_to(root):
        raise SecurityError("target must be a sub-path of the repository root")

    if target.is_file():
        if target.is_symlink() or not target_resolved.is_relative_to(root):
            return []
        return [target]

    return [
        p
        for p in sorted(target.rglob(pattern))
        if _is_reviewable_candidate_file(p, root, max_file_size, excluded_dirs=excluded_dirs)
    ]


__all__ = [
    "diff_pages",
    "diff_stream_chunks",
    "find_repo_files",
    "number_diff_lines",
    "number_source_lines",
    "page_line_number",
    "split_review_pages",
    "strip_line_numbers",
]
