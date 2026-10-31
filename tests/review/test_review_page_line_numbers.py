"""Review blocks number their source lines and diff lines (#499, #1151).

Without numbers every reported line range was the model's own count. Line numbers are part
of each block so any excerpt from the file or diff still shows where it is.
"""

from __future__ import annotations

from devops_cli.review.diff import (
    diff_blocks,
    extract_added_diff_lines,
    number_diff_lines,
    number_source_lines,
    page_line_number,
    strip_line_numbers,
)


def test_source_lines_are_numbered_from_one() -> None:
    """Verify each source line carries its number and a tab, counted at newlines only."""
    numbered = number_source_lines("a = 1\n\tb = 2\nc = '\x0c'\n")

    assert numbered == "1\ta = 1\n2\t\tb = 2\n3\tc = '\x0c'\n"


def test_diff_lines_carry_their_new_file_numbers() -> None:
    """Verify context and added lines carry new-file numbers and removed lines none."""
    diff = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -10,4 +10,4 @@ def f():\n keep\n-old\n--- looks like a header\n+new\n+added\n tail\n"
        "@@ -40 +41 @@\n-gone\n+here\n"
    )

    numbered = number_diff_lines(diff).splitlines()

    assert numbered[:4] == [
        "diff --git a/x.py b/x.py",
        "--- a/x.py",
        "+++ b/x.py",
        "@@ -10,4 +10,4 @@ def f():",
    ]
    assert numbered[4:] == [
        "10\t keep",
        "\t-old",
        "\t--- looks like a header",
        "11\t+new",
        "12\t+added",
        "13\t tail",
        "@@ -40 +41 @@",
        "\t-gone",
        "41\t+here",
    ]


def test_numbers_strip_back_to_the_original_text() -> None:
    """Verify removing the number column restores source and diff text exactly."""
    source = "def f():\n\treturn 1\n"
    diff = "diff --git a/x b/x\n@@ -1,2 +1,2 @@\n a\n-b\n+c\n"

    restored = (
        strip_line_numbers(number_source_lines(source)),
        strip_line_numbers(number_diff_lines(diff)),
    )

    assert restored == (source, diff)


def test_diff_blocks_number_lines() -> None:
    """Verify diff_blocks keeps new-file numbers on every line and its preamble."""
    diff = (
        "diff --git a/big.py b/big.py\n--- a/big.py\n+++ b/big.py\n@@ -200,0 +201,100 @@\n"
        + "".join(f"+line {n}\n" for n in range(201, 301))
    )

    blocks = diff_blocks(diff)

    assert len(blocks) == 1
    assert blocks[0].startswith("diff --git a/big.py b/big.py\n")
    for line in blocks[0].splitlines()[4:]:
        assert line == f"{page_line_number(line)}\t+line {page_line_number(line)}"
    assert "248\t+line 248" in blocks[0]


def test_extract_added_diff_lines_raw_and_numbered() -> None:
    """extract_added_diff_lines maps added line coordinates across raw diffs and numbered pages."""
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
    numbered_page = (
        "### File: test.py (part 1 of 1)\n"
        "@@ -1,3 +1,4 @@\n"
        "1\t a = 1\n"
        "\t-b = 2\n"
        "2\t+b = 3  # noqa: E501\n"
        "3\t+c = 4\n"
    )

    assert (
        extract_added_diff_lines(raw_diff),
        extract_added_diff_lines(numbered_page),
    ) == (
        {("test.py", 2), ("test.py", 3)},
        {("test.py", 2), ("test.py", 3)},
    )
