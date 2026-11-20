"""The helpers of `devops_cli.core.binaries`: the version line that a command prints (#5107)."""

from __future__ import annotations


def test_version_line_is_the_first_non_empty_line() -> None:
    """Leading blank and space-only lines are skipped, and the line is stripped."""
    from devops_cli.core.binaries import version_line

    assert version_line("\n   \n  1.17.0  \n") == "1.17.0"


def test_version_line_is_none_when_the_output_holds_no_line() -> None:
    """An empty output, and one of blank lines, name no version."""
    from devops_cli.core.binaries import version_line

    assert (version_line(""), version_line("\n  \n")) == (None, None)
