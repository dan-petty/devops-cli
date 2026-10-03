"""Unit tests for fitting release notes into GitHub's body limits (#1097)."""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS,
    CONST_GITHUB_RELEASE_BODY_MAX_CHARS,
)
from devops_cli.release.notes_compaction import fit_release_notes
from tests.release_notes_examples import (
    SYNTHETIC_CATEGORIES,
    SYNTHETIC_ENTRY_COUNT,
    synthetic_entry_detail,
    synthetic_entry_title,
    synthetic_release_section,
)

_FULL = (
    "[`CHANGELOG.md` at v1.2.3](https://github.com/o/r/blob/v1.2.3/CHANGELOG.md#123---2026-10-03)"
)
_FULL_NOTES = f"The full notes are in {_FULL}."
_POINTER = f"Each entry's details are left out to fit GitHub's size limit. {_FULL_NOTES}"
_LONG = "x" * 400


def test_the_limits_are_githubs() -> None:
    """GitHub refuses a Release body over 125,000 characters and a PR body over 65,536."""
    assert (CONST_GITHUB_RELEASE_BODY_MAX_CHARS, CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS) == (
        125_000,
        65_536,
    )


def test_notes_that_fit_are_returned_unchanged() -> None:
    """Up to and including the budget, not a character changes."""
    notes = "### Added\n- **A**:\n  - detail.\n\n### Fixed\n- B."
    assert fit_release_notes(notes, len(notes), _FULL) == notes


def test_notes_over_the_budget_keep_each_category_and_title_and_end_with_the_full_notes() -> None:
    """Sub-bullets go; headings, titles (a wrapped title whole) and entries without details stay."""
    notes = (
        f"### Added\n- **A**:\n  - {_LONG}\n- **B** wraps\n  over two lines:\n  - {_LONG}\n\n"
        f"### Fixed\n- C, a single-line entry.\n- **D**:\n  - {_LONG}\n    - {_LONG}"
    )
    assert fit_release_notes(notes, 1_000, _FULL) == (
        "### Added\n- **A**:\n- **B** wraps\n  over two lines:\n\n"
        "### Fixed\n- C, a single-line entry.\n- **D**:\n\n" + _POINTER
    )


def test_a_200000_character_section_fits_the_release_limit_with_every_title() -> None:
    """The v0.2.25 shape: 210 entries, every category and title kept, no sub-bullet, the link."""
    section = synthetic_release_section()
    fitted = fit_release_notes(section, CONST_GITHUB_RELEASE_BODY_MAX_CHARS, _FULL)
    titles = [synthetic_entry_title(number) for number in range(1, SYNTHETIC_ENTRY_COUNT + 1)]
    assert len(section) > 200_000
    assert len(fitted) < CONST_GITHUB_RELEASE_BODY_MAX_CHARS
    assert [title for title in titles if title not in fitted] == []
    assert [cat for cat in SYNTHETIC_CATEGORIES if f"### {cat}\n" not in fitted] == []
    assert synthetic_entry_detail(1, 1) not in fitted
    assert fitted.endswith(_POINTER)


def test_titles_that_do_not_fit_are_cut_at_the_last_whole_entry_and_counted() -> None:
    """Later headings go with their entries; a line says how many entries were left out."""
    section = synthetic_release_section()
    budget = 12_000
    fitted = fit_release_notes(section, budget, _FULL)
    kept = [
        number
        for number in range(1, SYNTHETIC_ENTRY_COUNT + 1)
        if synthetic_entry_title(number) in fitted
    ]
    assert len(fitted) <= budget
    assert kept == list(range(1, len(kept) + 1))
    assert len(kept) > 100
    assert fitted.endswith(
        f"\n\nEntries left out to fit: {SYNTHETIC_ENTRY_COUNT - len(kept)}.\n\n{_POINTER}"
    )
    assert "### Security" not in fitted
    one_more = fit_release_notes(section, budget + len(synthetic_entry_title(1)) + 1, _FULL)
    assert synthetic_entry_title(len(kept) + 1) in one_more


def test_notes_the_changelog_parser_cannot_read_are_fitted_by_their_headings_and_blocks() -> None:
    """Commit-log notes carry headings no changelog category has; headings are not entries."""
    commits = "\n".join(f"- feat(x): change number {number} (#{number})" for number in range(1000))
    notes = f"### Changes in v1.2.3\n\n### Added\n{commits}"
    fitted = fit_release_notes(notes, 30_000, _FULL)
    kept = sum(f"change number {number} (#" in fitted for number in range(1000))
    assert len(fitted) <= 30_000
    assert fitted.startswith("### Changes in v1.2.3\n\n### Added\n- feat(x): change number 0 (#0)")
    assert fitted.endswith(f"\n\nEntries left out to fit: {1000 - kept}.\n\n{_FULL_NOTES}")


def test_a_block_after_a_list_item_stays_out_of_the_item() -> None:
    """Items run on as one list; a paragraph between them keeps its blank lines around it."""
    notes = f"Intro paragraph.\n\n- a\n  - {_LONG}\n\nOutro paragraph.\n\n- b\n- c"
    assert fit_release_notes(notes, 200, "X") == (
        "Intro paragraph.\n\n- a\n\nOutro paragraph.\n\n- b\n- c\n\n"
        "Each entry's details are left out to fit GitHub's size limit. The full notes are in X."
    )


def test_notes_without_details_are_cut_with_a_pointer_that_only_says_where_the_notes_are() -> None:
    """No entry had details to drop, so the pointer does not say any were."""
    notes = "### Added\n" + "\n".join(f"- Entry {number}." for number in range(100))
    fitted = fit_release_notes(notes, 200, _FULL)
    assert len(fitted) <= 200
    assert fitted == (
        "### Added\n- Entry 0.\n- Entry 1.\n- Entry 2.\n- Entry 3.\n\n"
        f"Entries left out to fit: 96.\n\n{_FULL_NOTES}"
    )


def test_a_budget_too_small_for_the_pointer_still_gets_the_count_and_the_pointer() -> None:
    """No entry is worth more than the way to the full notes, which is never cut."""
    fitted = fit_release_notes(f"### Added\n- **A**:\n  - {_LONG}", 50, _FULL)
    assert fitted == f"Entries left out to fit: 1.\n\n{_POINTER}"
