"""Diff slicing, source code windowing, file discovery, and segment chunking."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.sanitization import _unique_preserve_order
from devops_cli.config.constants import (
    CONST_BINARY_EXTENSIONS,
    CONST_GITIGNORE_DIRS,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_REVIEW_GENERATED_FILES,
    CONST_REVIEW_MAX_DIFF_CHARS,
)
from devops_cli.config.defaults import (
    DEFAULT_REVIEW_OVERLAP_FACTOR,
    DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
)

_CODE_LINE_SKIP_PREFIXES = ("diff --git", "index ", "--- ", "+++ ", "@@ ", "### File: ", "```")


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


def _extract_diff_filenames(segment: str) -> list[str]:
    """Extract filenames from git diff headers."""
    return _extract_header_filenames(segment, header_type="diff")


def _extract_path_filenames(segment: str) -> list[str]:
    """Extract filenames from file block headers."""
    return _extract_header_filenames(segment, header_type="path")


def _extract_segment_filenames(segment: str) -> list[str]:
    """Extract filenames from either git diff headers or file block headers."""
    return _extract_header_filenames(segment, header_type="all")


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

    lines = text.splitlines(keepends=True)
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
    return f"{title}\n```{suffix}\n{text}\n```"


def _split_source_file_blocks(
    rel: Path,
    suffix: str,
    text: str,
    max_chars: int = CONST_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Split a single source file into individual review windows with top and bottom overlap."""
    block = _render_source_block(rel, suffix, text)
    if len(block) <= max_chars:
        return [block]

    overhead = len(_render_source_block(rel, suffix, "", 1, 9999))
    payload_budget = max_chars - overhead
    if payload_budget <= 0:
        return _split_text_lines(block, max_chars)

    window_cap = max(100, int(payload_budget * window_size_factor))
    overlap_cap = max(10, int(payload_budget * overlap_factor))

    lines = text.splitlines(keepends=True)
    line_counts = len(lines)
    start_idx = 0

    slices: list[tuple[int, int]] = []
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

    total_parts = len(slices)
    windows: list[str] = []
    for part_idx, (s_idx, e_idx) in enumerate(slices, 1):
        core_text = "".join(lines[s_idx:e_idx])
        top_overlap = ""
        if s_idx > 0:
            top_lines: list[str] = []
            top_len = 0
            for idx in range(s_idx - 1, -1, -1):
                if top_len + len(lines[idx]) > overlap_cap:
                    break
                top_lines.insert(0, lines[idx])
                top_len += len(lines[idx])
            if top_lines:
                top_overlap = "".join(top_lines)

        bottom_overlap = ""
        if e_idx < line_counts:
            bot_lines: list[str] = []
            bot_len = 0
            for idx in range(e_idx, line_counts):
                if bot_len + len(lines[idx]) > overlap_cap:
                    break
                bot_lines.append(lines[idx])
                bot_len += len(lines[idx])
            if bot_lines:
                bottom_overlap = "".join(bot_lines)

        window_body = f"{top_overlap}{core_text}{bottom_overlap}"
        rendered = _render_source_block(rel, suffix, window_body, part_idx, total_parts)
        if len(rendered) <= max_chars:
            windows.append(rendered)
        else:
            for sub_chunk in _split_text_lines(window_body, payload_budget):
                windows.append(_render_source_block(rel, suffix, sub_chunk, part_idx, total_parts))

    return windows


def _split_diff_into_file_blocks(diff: str) -> list[str]:
    """Split a unified diff into one block per file, without cutting through a hunk."""
    marker = "diff --git "
    blocks: list[str] = []
    current: list[str] = []

    for line in diff.splitlines(keepends=True):
        if line.startswith(marker) and current:
            blocks.append("".join(current))
            current = []
        current.append(line)

    if current:
        blocks.append("".join(current))
    return blocks or [diff]


def _paginate_file_diff_block(
    block: str,
    max_chars: int = CONST_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Paginate a file's diff block using rolling windows with top/bottom overlap."""
    if len(block) <= max_chars:
        return [block]

    window_cap = max(100, int(max_chars * window_size_factor))
    overlap_cap = max(10, int(max_chars * overlap_factor))

    lines = block.splitlines(keepends=True)
    hunk_start = next((i for i, line in enumerate(lines) if line.startswith("@@ ")), len(lines))
    preamble = "".join(lines[:hunk_start])
    body_lines = lines[hunk_start:]

    if not body_lines or len(preamble) >= max_chars:
        return _split_text_lines(block, max_chars)

    effective_cap = max(50, window_cap - len(preamble))
    windows: list[str] = []
    line_counts = len(body_lines)
    start_idx = 0

    while start_idx < line_counts:
        curr_len = 0
        end_idx = start_idx
        while end_idx < line_counts and curr_len + len(body_lines[end_idx]) <= effective_cap:
            curr_len += len(body_lines[end_idx])
            end_idx += 1

        if end_idx == start_idx:
            end_idx = start_idx + 1

        core_text = "".join(body_lines[start_idx:end_idx])

        top_overlap = ""
        if start_idx > 0:
            top_lines: list[str] = []
            top_len = 0
            for idx in range(start_idx - 1, -1, -1):
                if top_len + len(body_lines[idx]) > overlap_cap:
                    break
                top_lines.insert(0, body_lines[idx])
                top_len += len(body_lines[idx])
            if top_lines:
                top_overlap = "".join(top_lines)

        bottom_overlap = ""
        if end_idx < line_counts:
            bot_lines: list[str] = []
            bot_len = 0
            for idx in range(end_idx, line_counts):
                if bot_len + len(body_lines[idx]) > overlap_cap:
                    break
                bot_lines.append(body_lines[idx])
                bot_len += len(body_lines[idx])
            if bot_lines:
                bottom_overlap = "".join(bot_lines)

        window_content = f"{preamble}{top_overlap}{core_text}{bottom_overlap}"
        windows.append(window_content)
        start_idx = end_idx

    return windows


def _is_generated_diff_block(block: str) -> bool:
    """Return True if the block's diff header names a known autogenerated file."""
    first = block.splitlines()[0] if block else ""
    if not first.startswith("diff --git "):
        return False
    parts = first.split()
    filename = parts[2].removeprefix("a/") if len(parts) >= 4 else ""
    return Path(filename).name in CONST_REVIEW_GENERATED_FILES


def _diff_pages(
    diff: str,
    max_chars: int = CONST_REVIEW_MAX_DIFF_CHARS,
    window_size_factor: float = DEFAULT_REVIEW_WINDOW_SIZE_FACTOR,
    overlap_factor: float = DEFAULT_REVIEW_OVERLAP_FACTOR,
) -> list[str]:
    """Paginate a unified diff file-by-file into individual review pages using rolling windows."""
    pages: list[str] = []
    for block in _split_diff_into_file_blocks(diff):
        if _is_generated_diff_block(block):
            continue
        file_pages = _paginate_file_diff_block(
            block,
            max_chars=max_chars,
            window_size_factor=window_size_factor,
            overlap_factor=overlap_factor,
        )
        pages.extend(file_pages)
    return pages or [""]


def _find_repo_files(
    target: Path,
    pattern: str = "*",
    max_file_size: int = CONST_MAX_FILE_SIZE_BYTES,
    excluded_dirs: set[str] | None = None,
    repo_root: Path | None = None,
) -> list[Path]:
    """Discover reviewable source files under target, skipping binary and symlinked paths."""
    root = (repo_root or target).resolve()
    target_resolved = target.resolve()
    if not target_resolved.is_relative_to(root):
        raise ValueError("target must be a sub-path of the repository root")

    ignore_set = excluded_dirs or set(CONST_GITIGNORE_DIRS)
    files: list[Path] = []
    if target.is_file():
        if target.is_symlink() or not target_resolved.is_relative_to(root):
            return []
        return [target]

    for p in sorted(target.rglob(pattern)):
        if p.is_symlink() or not p.is_file():
            continue
        try:
            if not p.resolve().is_relative_to(root):
                continue
        except Exception:
            continue
        if any(part in ignore_set for part in p.parts):
            continue
        if p.suffix.lower() in CONST_BINARY_EXTENSIONS:
            continue
        try:
            if p.stat().st_size > max_file_size:
                continue
        except OSError:
            continue
        files.append(p)
    return files
