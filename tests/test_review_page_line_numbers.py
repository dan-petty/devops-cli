"""Review pages number their source lines, parts of split files included (#499).

Without numbers every reported line range was the model's own count, and a later part of a
split file started mid-file with no offset: an injected defect at line 248 was reported at lines
106-108. Split pages also lost their file header and overlap when the pipeline re-split them.
"""

from __future__ import annotations

import re
from pathlib import Path

from devops_cli.ai.review.chunker import (
    _split_source_file_blocks,
    diff_pages,
    number_diff_lines,
    number_source_lines,
    page_line_number,
    split_review_pages,
    strip_line_numbers,
)
from devops_cli.ai.review.classification import FileContextType, build_context_review_prompt
from devops_cli.ai.review.pipeline import _page_imports
from devops_cli.ai.review.verification import _extract_location_context
from devops_cli.ai.task_loader import load_task_prompt

_DEFECT = "    path.parent.mkdir(mode=0o777, parents=True, exist_ok=True)"


def _source(lines: int = 300, defect_at: int = 248) -> str:
    """A long file with one recognisable line at a known line number."""
    return "".join(
        f"{_DEFECT}\n" if n == defect_at else f"value_{n} = compute({n})\n"
        for n in range(1, lines + 1)
    )


def _numbers(page: str) -> list[int]:
    return [n for line in page.splitlines() if (n := page_line_number(line)) is not None]


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


def test_every_part_of_a_split_file_keeps_its_file_line_numbers() -> None:
    """Verify a later part of a split file shows the defect at its line number in the file."""
    text = _source()

    parts = _split_source_file_blocks(Path("crypto/known_hosts.py"), "py", text, max_chars=4000)

    assert len(parts) > 2
    assert all(p.startswith("### File: crypto/known_hosts.py (part ") for p in parts)
    for part in parts:
        for line in part.splitlines()[2:-1]:
            number = page_line_number(line)
            assert number is not None
            assert line.split("\t", 1)[1] == text.splitlines()[number - 1]
    holding = [i for i, p in enumerate(parts) if f"248\t{_DEFECT}" in p]
    assert holding and holding[0] > 0


def test_split_parts_overlap_and_cover_the_file() -> None:
    """Verify neighbouring parts share lines and together cover every line of the file."""
    parts = _split_source_file_blocks(Path("a.py"), "py", _source(), max_chars=4000)
    spans = [_numbers(p) for p in parts]

    assert all(a[-1] >= b[0] for a, b in zip(spans, spans[1:]))
    assert sorted({n for span in spans for n in span}) == list(range(1, 301))


def test_the_pipeline_split_repeats_the_header_and_keeps_the_numbers() -> None:
    """Verify re-splitting a file's page for a smaller window keeps header, fence and numbers.

    The pipeline cut pages at arbitrary lines, so a later page had no file header, no fence and
    no overlap with the page before it.
    """
    (page,) = _split_source_file_blocks(Path("known_hosts.py"), "py", _source(), max_chars=10**6)

    pages = split_review_pages(page, max_chars=3000)

    assert len(pages) > 2
    assert all(p.startswith("### File: known_hosts.py\n```py\n") for p in pages)
    assert all(p.endswith("```") and len(p) <= 3000 for p in pages)
    spans = [_numbers(p) for p in pages]
    assert all(a[-1] >= b[0] for a, b in zip(spans, spans[1:]))
    assert sorted({n for span in spans for n in span}) == list(range(1, 301))
    assert any(f"248\t{_DEFECT}" in p for p in pages[1:])


def test_a_page_within_the_window_is_not_split() -> None:
    """Verify a page that fits is passed through unchanged."""
    page = "### File: a.py\n```py\n1\tx = 1\n```"

    assert split_review_pages(page, max_chars=1000) == [page]


def test_diff_pages_number_lines_and_keep_them_when_split() -> None:
    """Verify a split diff keeps new-file numbers on every page and its preamble on each."""
    diff = (
        "diff --git a/big.py b/big.py\n--- a/big.py\n+++ b/big.py\n@@ -200,0 +201,100 @@\n"
        + "".join(f"+line {n}\n" for n in range(201, 301))
    )

    pages = diff_pages(diff, max_chars=600)

    assert len(pages) > 2
    assert all(p.startswith("diff --git a/big.py b/big.py\n") for p in pages)
    for page in pages:
        for line in page.splitlines()[4:]:
            assert line == f"{page_line_number(line)}\t+line {page_line_number(line)}"
    resplit = split_review_pages("\n".join(pages), max_chars=400)
    assert all(p.startswith("diff --git a/big.py b/big.py\n") for p in resplit)
    assert "248\t+line 248" in "".join(resplit)


def test_the_verifier_excerpt_is_found_by_line_number_in_a_later_part() -> None:
    """Verify the excerpt for a finding at line 248 is line 248, whichever part holds it.

    Excerpts counted lines from the top of the first part naming the file, so a finding in a
    later part was shown other code or none.
    """
    parts = _split_source_file_blocks(Path("known_hosts.py"), "py", _source(), max_chars=4000)
    segment = "\n".join(parts)

    excerpt = _extract_location_context(segment, "known_hosts.py:248", context_lines=1)

    assert excerpt.splitlines() == [
        "247\tvalue_247 = compute(247)",
        f"248\t{_DEFECT}",
        "249\tvalue_249 = compute(249)",
    ]


def test_the_verifier_excerpt_still_counts_unnumbered_code() -> None:
    """Verify code without numbers is still counted from its first line."""
    segment = "### File: src/app.py\n```python\nl1\nl2\nl3\nl4\n```\n"

    assert _extract_location_context(segment, "src/app.py:2-3", context_lines=0) == "l2\nl3"


def test_the_verifier_excerpt_does_not_mix_files_sharing_a_name() -> None:
    """Verify a location naming one path is not filled with another file's lines."""
    segment = (
        "### File: a/__init__.py\n```py\n1\tfrom a import x\n```\n"
        "### File: b/__init__.py\n```py\n1\tfrom b import y\n```\n"
    )

    assert _extract_location_context(segment, "b/__init__.py:1", context_lines=0) == (
        "1\tfrom b import y"
    )


def test_imports_are_read_through_the_number_column() -> None:
    """Verify contract grounding still finds imports on numbered source and diff pages."""
    source_page = _split_source_file_blocks(Path("m.py"), "py", "import os\nfrom a import b\n")[0]
    diff_page = diff_pages("diff --git a/m.py b/m.py\n@@ -1 +1,2 @@\n x\n+import json\n")[0]

    assert (_page_imports(source_page), _page_imports(diff_page)) == (
        [("os", None), ("a", "b")],
        [("json", None)],
    )


def test_persona_prompts_ask_for_the_shown_line_numbers() -> None:
    """Verify every page prompt, of any file kind, tells the persona to cite the numbers."""
    prompts = [
        build_context_review_prompt(kind, "a.py", 2, 3, "1\tx = 1\n")
        for kind in (
            FileContextType.CODE,
            FileContextType.CONFIGURATION,
            FileContextType.DOCUMENTATION,
        )
    ]
    protocol = load_task_prompt("paginated_review_protocol.md")

    assert all(re.search(r"line number.*never copy them", p, re.S) for p in prompts)
    assert "never copy them" in protocol
    assert "number in the file" in load_task_prompt("verify_finding_system.md")
