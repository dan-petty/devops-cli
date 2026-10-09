"""Which review.toml suppressions a change touches (#1150).

A suppression's `path` is the perimeter its reason holds for: a change to a file it covers may
undo that reason, so `devops pr check-readiness` and branch and PR reviews list the suppressions
a change touches for a person to re-check.
"""

from __future__ import annotations

from rich.text import Text

from devops_cli.review.suppression import (
    ReviewSuppression,
    covering_suppressions,
    format_covering_suppressions,
)

_LIVE = ReviewSuppression(rule="B602", path="src/a.py", reason="trusted argv", expiry="2099-12-31")
_EXPIRED = ReviewSuppression(rule="B603", path="src/b.py", reason="old", expiry="2020-01-01")
_GLOB = ReviewSuppression(rule="B101", path="tests/**", reason="pytest asserts")
_FINGERPRINT = ReviewSuppression(fingerprint="abc123", reason="one finding")


def test_a_suppression_covers_the_paths_its_glob_matches() -> None:
    """`covers` is the path half of `matches`: a glob covers the files under it at any depth, as
    `**` reads, and a suppression without a path covers none. `PurePosixPath.match` reads `**`
    as one directory, so `tests/**` missed `tests/ai/review/test_pipeline.py`."""
    assert (
        _GLOB.covers("tests/test_app.py"),
        _GLOB.covers("tests/ai/review/test_pipeline.py"),
        _GLOB.covers("src/app.py"),
        _LIVE.covers("./src/a.py"),
        _LIVE.covers("src/sub/a.py"),
        _FINGERPRINT.covers("src/a.py"),
        _GLOB.matches(rule_id="B101", path="tests/test_app.py", fingerprint=""),
        _GLOB.matches(rule_id="B101", path="tests/ai/review/test_runner.py", fingerprint=""),
        _GLOB.matches(rule_id="B101", path="src/app.py", fingerprint=""),
    ) == (True, True, False, True, False, False, True, True, False)


def test_only_unexpired_suppressions_with_a_path_a_change_touches_are_listed() -> None:
    """Of the suppressions on changed files, the expired one and the fingerprint-only one are
    left out, and so is one whose path the change does not touch."""
    suppressions = [_LIVE, _EXPIRED, _GLOB, _FINGERPRINT]

    assert (
        covering_suppressions(["src/a.py", "src/b.py"], suppressions),
        covering_suppressions(["tests/test_app.py"], suppressions),
        covering_suppressions(["docs/notes.md"], suppressions),
        covering_suppressions([], suppressions),
    ) == ([_LIVE], [_GLOB], [], [])


def test_the_warning_shows_review_toml_text_as_written() -> None:
    """A reason is review.toml text, not Rich markup: `[/b]` once raised a MarkupError and
    `list[str]` vanished from the warning."""
    supp = ReviewSuppression(
        rule="B602", path="src/[a].py", reason="Returns list[str]; see [/b]", expiry="2099-12-31"
    )

    shown = Text.from_markup(format_covering_suppressions([supp])).plain

    assert (
        "src/[a].py" in shown,
        "Returns list[str]; see [/b]" in shown,
    ) == (True, True)
