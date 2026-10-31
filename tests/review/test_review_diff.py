"""Tests for unified diff parsing, hunk extraction, and diff blocks (#1151)."""

from __future__ import annotations

from devops_cli.config.defaults import DEFAULT_REVIEW_MAX_DIFF_CHARS
from devops_cli.review.diff import (
    diff_blocks,
    diff_file_names,
    extract_added_diff_lines,
    extract_diff_hunks,
    extract_file_diff_hunks,
    number_source_lines,
)


def test_extract_diff_hunks() -> None:
    """Verify that extract_diff_hunks accurately parses various unified diff headers."""
    diff_sample = """
--- a/app.py
+++ b/app.py
@@ -1,5 +1,10 @@
@@ -10,3 +20 @@
@@ -30,5 +40,0 @@
"""
    hunks = extract_diff_hunks(diff_sample)
    assert hunks == [(1, 10), (20, 20), (40, 40)]


def test_extract_file_diff_hunks() -> None:
    """Verify that extract_file_diff_hunks associates hunks with respective files."""
    segments = [
        """diff --git a/pkg/mod1.py b/pkg/mod1.py
--- a/pkg/mod1.py
+++ b/pkg/mod1.py
@@ -5,2 +5,4 @@
def foo(): pass
""",
        """diff --git a/pkg/mod2.py b/pkg/mod2.py
--- a/pkg/mod2.py
+++ b/pkg/mod2.py
@@ -10,5 +15,0 @@
""",
    ]
    file_hunks = extract_file_diff_hunks(segments)
    assert (
        file_hunks.get("pkg/mod1.py"),
        file_hunks.get("pkg/mod2.py"),
    ) == (
        [(5, 8)],
        [(15, 15)],
    )


def test_source_lines_are_numbered_from_one() -> None:
    """Verify each source line carries its number and a tab, counted at newlines only."""
    numbered = number_source_lines("a = 1\n\tb = 2\nc = '\x0c'\n")
    assert numbered == "1\ta = 1\n2\t\tb = 2\n3\tc = '\x0c'\n"


def test_extract_added_diff_lines_raw_and_numbered() -> None:
    """extract_added_diff_lines maps added line coordinates across raw diffs and numbered blocks."""
    raw_diff = (
        "diff --git a/test.py b/test.py\n"
        "--- a/test.py\n"
        "+++ b/test.py\n"
        "@@ -1,3 +1,4 @@\n"
        " a = 1\n"
        "-b = 2\n"
        "+b = 3  # noqa: E501\n"
        "+c = 4\n"
    )
    numbered_block = (
        "diff --git a/test.py b/test.py\n"
        "--- a/test.py\n"
        "+++ b/test.py\n"
        "@@ -1,3 +1,4 @@\n"
        "1\t a = 1\n"
        "\t-b = 2\n"
        "2\t+b = 3  # noqa: E501\n"
        "3\t+c = 4\n"
    )
    assert (
        extract_added_diff_lines(raw_diff),
        extract_added_diff_lines(numbered_block),
    ) == (
        {("test.py", 2), ("test.py", 3)},
        {("test.py", 2), ("test.py", 3)},
    )


def test_diff_file_names() -> None:
    """diff_file_names extracts unique target filenames from unified diff or file headers."""
    text = (
        "diff --git a/mod1.py b/mod1.py\n"
        "--- a/mod1.py\n"
        "+++ b/mod1.py\n"
        "### File: docs/guide.md\n"
        "diff --git a/old.py b/renamed.py\n"
    )
    assert diff_file_names(text) == ["mod1.py", "docs/guide.md", "renamed.py"]


def test_diff_blocks_large_diff_yields_one_block_per_changed_file() -> None:
    """A branch diff larger than DEFAULT_REVIEW_MAX_DIFF_CHARS yields one block per changed file
    with the same added lines and hunks (#1151)."""
    # Create diff for file 1 with size exceeding DEFAULT_REVIEW_MAX_DIFF_CHARS
    line_count = (DEFAULT_REVIEW_MAX_DIFF_CHARS // 20) + 100
    file1_body = "".join(f"+added_line_{i} = {i}\n" for i in range(1, line_count + 1))
    file1_diff = (
        f"diff --git a/big.py b/big.py\n"
        f"--- a/big.py\n"
        f"+++ b/big.py\n"
        f"@@ -0,0 +1,{line_count} @@\n"
        f"{file1_body}"
    )
    file2_diff = (
        "diff --git a/small.py b/small.py\n"
        "--- a/small.py\n"
        "+++ b/small.py\n"
        "@@ -1,2 +1,3 @@\n"
        " x = 1\n"
        "-y = 2\n"
        "+y = 3\n"
        "+z = 4\n"
    )
    combined = file1_diff + file2_diff
    assert len(combined) > DEFAULT_REVIEW_MAX_DIFF_CHARS

    blocks = diff_blocks(combined)
    assert len(blocks) == 2
    assert blocks[0].startswith("diff --git a/big.py b/big.py\n")
    assert blocks[1].startswith("diff --git a/small.py b/small.py\n")

    # Verify added lines and hunks are identical to raw extraction
    assert extract_added_diff_lines(blocks[0]) == extract_added_diff_lines(file1_diff)
    assert extract_diff_hunks(blocks[0]) == extract_diff_hunks(file1_diff)
    assert extract_added_diff_lines(blocks[1]) == extract_added_diff_lines(file2_diff)
    assert extract_diff_hunks(blocks[1]) == extract_diff_hunks(file2_diff)


def test_diff_blocks_skips_secret_scan_only_files() -> None:
    """diff_blocks filters out lockfiles and planning docs that are secret-scan only."""
    diff = (
        "diff --git a/uv.lock b/uv.lock\n"
        "+# lockfile\n"
        "diff --git a/docs/adr/0001-x.md b/docs/adr/0001-x.md\n"
        "+# decision\n"
        "diff --git a/src/main.py b/src/main.py\n"
        "+print('hello')\n"
    )
    blocks = diff_blocks(diff)
    assert len(blocks) == 1
    assert "src/main.py" in blocks[0]
