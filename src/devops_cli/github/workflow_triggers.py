"""Whether a GitHub Actions workflow file can start a check on a pull request (#5144, #5408).

GitHub starts a workflow for a pull request when its `on:` key lists `pull_request` or
`pull_request_target` and the filters of that event take the pull request: `branches` or
`branches-ignore` for the branch that the pull request targets, and `paths` or `paths-ignore` for
the files of its three-dot diff. The rules are those of GitHub's workflow syntax reference, and
wcmatch matches each glob. A filter that this module cannot judge takes the pull request, so its
caller keeps the wait for a check rather than call the pull request one with no CI.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, NamedTuple

import yaml
from wcmatch import glob

from devops_cli.exceptions.git import GitHubUnreadError

_PULL_REQUEST_TRIGGERS: Final[frozenset[str]] = frozenset({"pull_request", "pull_request_target"})
"""The workflow events that GitHub starts for activity on a pull request."""

_GLOB_FLAGS: Final[int] = glob.GLOBSTAR | glob.DOTMATCH | glob.FORCEUNIX
"""`*` stops at `/` and a `**` segment crosses folders, as in GitHub's filters. GitHub has no
hidden files, so a name that starts with `.` matches too, and `/` is the separator on each host."""

_GITHUB_QUANTIFIERS: Final[frozenset[str]] = frozenset({"?", "+"})
"""The characters that GitHub reads as a quantifier of the character before them, and wcmatch
reads as one character (`?`) or as itself (`+`)."""

_GLOBSTAR: Final[str] = "**"


class PullRequestChange(NamedTuple):
    """What the filters of a workflow judge: the branch that the pull request targets, and the
    paths that it changes. `files` is None when the list is unknown, because the read failed or
    holds GitHub's limit of files of one comparison. `base` is empty when the payload names none."""

    base: str
    files: tuple[str, ...] | None


def starts_on_pull_request(text: str, change: PullRequestChange) -> bool:
    """Whether workflow `text` can start a check on the pull request that `change` describes.

    YAML 1.1 reads a bare `on` key as the boolean `True`, so both keys are read. A string or a list
    under `on:` names events with no filter. A document that is no mapping, and a trigger that is
    absent or malformed, starts no check. A file that is not valid YAML raises `GitHubUnreadError`.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise GitHubUnreadError(f"GitHub's workflow file is not valid YAML: {exc}") from exc
    if not isinstance(document, dict):
        return False
    triggers = document.get("on", document.get(True))
    if isinstance(triggers, str):
        return triggers in _PULL_REQUEST_TRIGGERS
    if isinstance(triggers, list):
        return any(
            trigger in _PULL_REQUEST_TRIGGERS for trigger in triggers if isinstance(trigger, str)
        )
    if isinstance(triggers, dict):
        return any(
            _event_takes(triggers[event], change)
            for event in _PULL_REQUEST_TRIGGERS
            if event in triggers
        )
    return False


def _event_takes(event: object, change: PullRequestChange) -> bool:
    """Whether every filter of one pull request event takes the pull request. An event with no
    mapping under it has no filter. The `types` key is not judged, so an event that lists only
    other activity types still counts as one that can start a check."""
    if not isinstance(event, dict):
        return True
    branches = (change.base,) if change.base else None
    return _filter_takes(event, "branches", branches) and _filter_takes(
        event, "paths", change.files
    )


def _filter_takes(event: dict[object, object], key: str, values: Sequence[str] | None) -> bool:
    """Whether the `key` filter of `event`, or its `-ignore` form, takes the pull request whose
    branch or paths are `values`.

    The plain form takes it when one value is included, and the `-ignore` form when one value is
    not, so neither form takes a pull request with no changed path. An event with no such filter
    takes each pull request. A filter that cannot be judged takes it too: unknown values, both
    forms together (GitHub refuses the workflow), or patterns that `_patterns` gives no answer for.
    """
    ignore = f"{key}-ignore"
    if key in event and ignore in event:
        return True
    name = key if key in event else ignore if ignore in event else None
    if name is None:
        return True
    patterns = _patterns(event[name])
    if patterns is None or values is None:
        return True
    included = [_included(value, patterns) for value in values]
    return any(included) if name == key else not all(included)


def _patterns(value: object) -> tuple[str, ...] | None:
    """The patterns of a filter, or None when wcmatch cannot match them as GitHub does: a value
    that is no list of strings, or a pattern with a GitHub quantifier or with a `**` that shares
    a path segment with other characters, which GitHub reads as any characters, `/` included."""
    if not isinstance(value, list) or not all(isinstance(pattern, str) for pattern in value):
        return None
    for pattern in value:
        if _GITHUB_QUANTIFIERS & set(pattern) or any(
            _GLOBSTAR in segment and segment != _GLOBSTAR for segment in pattern.split("/")
        ):
            return None
    return tuple(value)


def _included(value: str, patterns: Sequence[str]) -> bool:
    """Whether `patterns` include `value` by GitHub's ordered rule: each pattern that matches sets
    the answer, a pattern that starts with `!` to excluded, so the last match decides."""
    included = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if glob.globmatch(value, pattern.removeprefix("!"), flags=_GLOB_FLAGS):
            included = not negated
    return included
