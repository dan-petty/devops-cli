"""Match a pinned version to the version range of a GitHub advisory (#3987).

A GitHub advisory writes a range as comma-separated comparators: `>= 1.18.0, < 1.19.2`, `<= 45.0.7`
or `= 1.2.3`, and joins ranges of several release lines with `||`:
`>= 3.0.0, < 3.3.15 || >= 3.4.0, < 3.4.10`. `packaging` reads the comparators and compares the
versions, as it does for pip, so this module holds no comparison of its own. OSV matches the version on its server; GitHub does not
match a version for an Action, an image or a release, so the client does.
"""

from __future__ import annotations

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

# A pin names a release when it has a major, a minor and a patch number. A tag with fewer
# (`v7`, `3.14`) moves with each release of its line, so it names no one version.
_RELEASE_PARTS = 3


def pinned_version(text: str) -> Version | None:
    """The version that `text` pins, or None when it names no one release.

    A leading `v` is dropped (`v45.0.0`). A commit, a branch, `latest`, a tag with a variant such as
    `-alpine`, and a tag with fewer than three numbers give None.
    """
    try:
        version = Version(text.removeprefix("v"))
    except InvalidVersion:
        return None
    return version if len(version.release) >= _RELEASE_PARTS else None


def _specifier_set(comparators: str) -> SpecifierSet:
    parts = [part.strip() for part in comparators.split(",") if part.strip()]
    if not parts:
        raise ValueError("the advisory names an empty range of versions")
    return SpecifierSet(
        ",".join(
            f"={part}" if part.startswith("=") and not part.startswith("==") else part
            for part in parts
        )
    )


def in_range(version: Version, range_text: str) -> bool:
    """Whether `version` is in the range of an advisory: in any of the ranges that `||` joins.

    A range that is empty or that `packaging` cannot read raises `ValueError`: the caller reports
    the advisory as unread, and never as one that does not apply.
    """
    if not range_text.strip():
        raise ValueError("the advisory names no range of versions")
    return any(
        _specifier_set(alternative).contains(version, prereleases=True)
        for alternative in range_text.split("||")
    )
