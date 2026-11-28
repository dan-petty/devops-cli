"""Match a pinned version to the version range of a GitHub advisory (#3987).

A GitHub advisory writes a range as comma-separated comparators: `>= 1.18.0, < 1.19.2`, `<= 45.0.7`
or `= 1.2.3`, and joins ranges of several release lines with `||`:
`>= 3.0.0, < 3.3.15 || >= 3.4.0, < 3.4.10`. `packaging` reads the comparators and compares the
versions, as it does for pip, so this module holds no comparison of its own. OSV matches the version on its server; GitHub does not
match a version for an Action, an image or a release, so the client does.
"""

from __future__ import annotations

from collections.abc import Iterable

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


def full_release(text: str) -> Version | None:
    """The `Version` of a tag that names a full release, or None when it names no one release.

    A full release has three release numbers and no prerelease, dev, local or post part, so an
    advisory range compares it. A major tag (`v7`) and a tag with a variant (`v7.2.1-rc1`) give None.
    """
    version = pinned_version(text)
    if version is None:
        return None
    if version.pre or version.dev or version.local or version.post:
        return None
    return version


def release_for_commit(tags: Iterable[tuple[str, str]], commit: str) -> str | None:
    """The name of the highest full release tag that points at `commit`, or None when no tag does.

    `tags` holds a pair of tag name and commit sha. A major tag, a prerelease tag and a tag at
    another commit name no release of this commit.
    """
    releases: dict[Version, str] = {}
    for name, sha in tags:
        version = full_release(name)
        if sha != commit or version is None:
            continue
        releases[version] = name
    if not releases:
        return None
    return releases[max(releases)]


_OPERATORS = ("===", "==", "!=", "<=", ">=", "~=", "=", "<", ">")
_UPPER_BOUND_OPERATORS = frozenset({"<", "<=", "==", "==="})


def _normalize_version(text: str) -> str:
    """Drop a leading `v` prefix and a trailing `-stable` release tag suffix."""
    return text.removeprefix("v").removesuffix("-stable")


def _normalize_comparator(part: str) -> str:
    """Normalize a comparator: map a bare version or `=` to `==` and normalize its version."""
    for operator in _OPERATORS:
        if part.startswith(operator):
            mapped = "==" if operator == "=" else operator
            return f"{mapped}{_normalize_version(part[len(operator) :].strip())}"
    return f"=={_normalize_version(part)}"


def _specifier_set(comparators: str, patched_version: str = "") -> SpecifierSet:
    parts = [part.strip() for part in comparators.split(",") if part.strip()]
    if not parts:
        raise ValueError("the advisory names an empty range of versions")
    spec_set = SpecifierSet(",".join(_normalize_comparator(part) for part in parts))
    patched = patched_version.strip()
    if patched and not any(spec.operator in _UPPER_BOUND_OPERATORS for spec in spec_set):
        spec_set = SpecifierSet(f"{spec_set},<{_normalize_version(patched)}")
    return spec_set


def in_range(version: Version, range_text: str, *, patched_version: str | None = None) -> bool:
    """Whether `version` is in the range of an advisory: in any of the ranges that `||` joins.

    When `patched_version` is given, each open lower-bound alternative without an upper comparator
    (`<=`, `<`, `==`, `===`) is bounded below `<patched_version>`. A range that is empty or that
    `packaging` cannot read raises `ValueError`: the caller reports the advisory as unread, and
    never as one that does not apply.
    """
    if not range_text.strip():
        raise ValueError("the advisory names no range of versions")
    patched = patched_version or ""
    return any(
        _specifier_set(alternative, patched).contains(version, prereleases=True)
        for alternative in range_text.split("||")
    )
