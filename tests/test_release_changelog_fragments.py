"""Unit tests for changelog fragments: reading `changelog.d/` and collecting it into CHANGELOG.md."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions.validation import ValidationError
from devops_cli.release.changelog_fragments import (
    ChangelogFragment,
    collect_changelog_fragments,
    parse_changelog_categories,
    read_changelog_fragments,
)

_HEAD = "# Changelog\n\nIntro.\n\n"
_OLDER = "## [0.1.7] - 2026-08-13\n\n### Added\n- Native DevContainer Lifecycle.\n"


def _fragment(issue: int, text: str) -> ChangelogFragment:
    """A fragment parsed from `text`, as `read_changelog_fragments` would return it."""
    path = Path(f"changelog.d/{issue}.md")
    return ChangelogFragment(path, issue, parse_changelog_categories(text, str(path)))


@pytest.fixture
def fragments_dir(tmp_path: Path) -> Path:
    """An empty `changelog.d/`; `tmp_path` itself holds the test's data directory."""
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    return directory


def _refusal(action: Callable[[], object]) -> str:
    """The message of the ValidationError `action()` raises."""
    with pytest.raises(ValidationError) as caught:
        action()
    return str(caught.value)


# =============================================================================
# Parsing a fragment's categories
# =============================================================================


def test_entries_are_kept_verbatim_under_their_category() -> None:
    """Sub-bullets, inline code and a `#12` at a line start are entry text, not headings."""
    text = (
        "\n### Fixed\n- **A Fix (`devops x`)**:\n  - detail (#12).\n#12 wraps here.\n\n"
        "### Added\n\n- **A Feature**.\n\n"
    )
    assert parse_changelog_categories(text, "changelog.d/12.md") == {
        "Fixed": ["- **A Fix (`devops x`)**:", "  - detail (#12).", "#12 wraps here."],
        "Added": ["- **A Feature**."],
    }


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("### Improvements\n- x.\n", "changelog.d/9.md:1 '### Improvements' is not a changelog"),
        ("### added\n- x.\n", "changelog.d/9.md:1 '### added' is not a changelog category"),
        ("### Added\n- x.\n## Added\n", "changelog.d/9.md:3 '## Added' is not a changelog"),
        ("#### Added\n- x.\n", "changelog.d/9.md:1 '#### Added' is not a changelog category"),
        ("- x.\n### Added\n- y.\n", "changelog.d/9.md:1 is outside a category"),
        ("\n\nA note.\n", "changelog.d/9.md:3 is outside a category"),
    ],
    ids=["unknown", "lower-case", "version-heading", "deeper-heading", "entry-first", "prose"],
)
def test_anything_but_a_category_heading_and_its_entries_is_refused(text: str, reason: str) -> None:
    """A `##` would open a version section of its own once the text is in CHANGELOG.md."""
    message = _refusal(lambda: parse_changelog_categories(text, "changelog.d/9.md"))
    assert (reason in message, "### Added, ### Changed" in message) == (True, True), message


# =============================================================================
# Reading changelog.d/
# =============================================================================


def test_fragments_are_read_in_issue_order_and_the_readme_is_skipped(fragments_dir: Path) -> None:
    """Issue order is numeric: 100 comes after 12, which a name sort would put first."""
    for name in ("100.md", "12.md", "3.md", "README.md"):
        (fragments_dir / name).write_text("### Added\n- x.\n", encoding="utf-8")
    fragments = read_changelog_fragments(fragments_dir)
    assert [(fragment.path.name, fragment.issue) for fragment in fragments] == [
        ("3.md", 3),
        ("12.md", 12),
        ("100.md", 100),
    ]


def test_a_missing_directory_holds_no_fragment(tmp_path: Path) -> None:
    """A repository without `changelog.d/` cuts as it did before."""
    assert read_changelog_fragments(tmp_path / "changelog.d") == ()


@pytest.mark.parametrize(
    "name", ["notes.md", "704.txt", "704-x.md", "v704.md", "704.MD"], ids=lambda name: name
)
def test_a_misnamed_file_is_refused_by_name(fragments_dir: Path, name: str) -> None:
    """Only `<issue>.md`, digits only, and the README belong in `changelog.d/`."""
    (fragments_dir / "1.md").write_text("### Added\n- x.\n", encoding="utf-8")
    (fragments_dir / name).write_text("### Added\n- y.\n", encoding="utf-8")
    message = _refusal(lambda: read_changelog_fragments(fragments_dir))
    assert message.startswith(f"changelog.d/{name} is not a changelog fragment"), message


@pytest.mark.parametrize("kind", ["directory", "link"])
def test_a_directory_or_link_named_like_a_fragment_is_refused(
    tmp_path: Path, fragments_dir: Path, kind: str
) -> None:
    """A fragment is a regular file in `changelog.d/`; a link could point anywhere."""
    outside = tmp_path / "outside.md"
    outside.write_text("### Added\n- x.\n", encoding="utf-8")
    if kind == "directory":
        (fragments_dir / "5.md").mkdir()
    else:
        (fragments_dir / "5.md").symlink_to(outside)
    message = _refusal(lambda: read_changelog_fragments(fragments_dir))
    assert message.startswith("changelog.d/5.md is not a changelog fragment"), message


@pytest.mark.parametrize("text", ["", "\n\n", "### Added\n\n"], ids=["empty", "blank", "heading"])
def test_a_fragment_without_an_entry_is_refused(fragments_dir: Path, text: str) -> None:
    """An empty fragment is a mistake, and would leave an empty heading in the release."""
    (fragments_dir / "8.md").write_text(text, encoding="utf-8")
    assert _refusal(lambda: read_changelog_fragments(fragments_dir)).startswith(
        "changelog.d/8.md holds no changelog entry"
    )


# =============================================================================
# Collecting fragments into CHANGELOG.md
# =============================================================================

_FIX_12 = _fragment(12, "### Fixed\n- Twelve fixed (#12).\n")
_ADD_30 = _fragment(30, "### Added\n- Thirty added (#30).\n")


def test_without_unreleased_the_section_opens_above_the_newest_release() -> None:
    """A changelog that never opened `[Unreleased]` still gets the version's section."""
    collected = collect_changelog_fragments(_HEAD + _OLDER, "0.1.8", "2026-10-02", [_FIX_12])
    assert collected == (
        _HEAD + "## [0.1.8] - 2026-10-02\n\n### Fixed\n- Twelve fixed (#12).\n\n" + _OLDER
    )


def test_a_version_section_already_open_keeps_its_entries_first_and_takes_the_date() -> None:
    """Fragments join an open `[X.Y.Z]` section per category; `[Unreleased]` is left alone."""
    changelog = (
        _HEAD
        + "## [Unreleased]\n\n"
        + "## [0.1.8] - 2026-01-01\n\n### Fixed\n- Already here.\n\n"
        + _OLDER
    )
    collected = collect_changelog_fragments(changelog, "0.1.8", "2026-10-02", [_FIX_12, _ADD_30])
    assert collected == (
        _HEAD
        + "## [Unreleased]\n\n"
        + "## [0.1.8] - 2026-10-02\n\n"
        + "### Added\n- Thirty added (#30).\n\n"
        + "### Fixed\n- Already here.\n- Twelve fixed (#12).\n\n"
        + _OLDER
    )


def test_entries_already_under_unreleased_come_first_and_unreleased_empties() -> None:
    """A release-process PR may still write under `[Unreleased]`; its entries are kept."""
    changelog = _HEAD + "## [Unreleased]\n\n### Fixed\n- By hand.\n\n" + _OLDER
    collected = collect_changelog_fragments(changelog, "0.1.8", "2026-10-02", [_FIX_12])
    assert collected == (
        _HEAD
        + "## [Unreleased]\n\n"
        + "## [0.1.8] - 2026-10-02\n\n### Fixed\n- By hand.\n- Twelve fixed (#12).\n\n"
        + _OLDER
    )


def test_the_only_section_ends_the_file_with_one_newline() -> None:
    """Nothing follows the last section, so it closes with a single newline."""
    collected = collect_changelog_fragments(
        _HEAD + "## [Unreleased]\n", "0.1.8", "2026-10-02", [_FIX_12]
    )
    assert collected == (
        _HEAD + "## [Unreleased]\n\n## [0.1.8] - 2026-10-02\n\n### Fixed\n- Twelve fixed (#12).\n"
    )


def test_prose_under_unreleased_names_changelog_and_its_line() -> None:
    """The text a cut would merge is checked as a fragment is, before anything is written."""
    changelog = _HEAD + "## [Unreleased]\n\nNothing yet.\n\n" + _OLDER
    message = _refusal(
        lambda: collect_changelog_fragments(changelog, "0.1.8", "2026-10-02", [_FIX_12])
    )
    assert message.startswith("CHANGELOG.md:7 is outside a category"), message


def test_a_changelog_without_a_release_heading_has_no_place_for_the_section() -> None:
    """The caller then writes the section as before, and keeps the fragments."""
    assert collect_changelog_fragments(_HEAD, "0.1.8", "2026-10-02", [_FIX_12]) is None
