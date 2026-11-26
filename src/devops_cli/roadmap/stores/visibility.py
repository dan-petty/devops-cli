"""The visibility check of the shared cache tier: which repositories it holds (#6611, #7292).

The shared tier of the cache Valkey `valkey-devops` holds the data of a public repository. It
holds the data of a private repository only for the process that sends the `sweep` ACL user, which
holds `~valkey:roadmap:*` (#4704, ADR 0023 section 8). The listing snapshot (`listing_shared`) and
the issue cache (`brain_issues`) use this one check, so the two stores give one answer for a
repository and send one read of GitHub for it.

- `visibility_of` gives the answer that the process holds for a repository. When it holds none, it
  reads GitHub through the read that its caller gives, and keeps the answer. A public or a private
  answer lives `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (30 min). A failed read gives
  `Visibility.UNKNOWN`, which lives `DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` (60 s), so a
  process that is out of GitHub quota sends no visibility read for each round.
- `held_visibility` gives only the answer that the process holds, for a caller that must send no
  request.
- `for_user` gives an answer as the shared tier takes it for an ACL user: a private repository is
  public to `SWEEP_USER`, and to no other user.

The answers use the casefolded name of `RepoRef.key`, so each spelling of a name has one answer.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import StrEnum
from typing import Final

from cachetools import TLRUCache

from devops_cli.config.defaults import (
    DEFAULT_BRAIN_MEMORY_ENTRIES,
    DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS,
    DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import clock
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.repo_ref import RepoRef

logger = logging.getLogger(__name__)


class Visibility(StrEnum):
    """The answer of the visibility check of a repository: public, private, or unknown when the
    read of GitHub failed or no read was possible. The shared tier holds the data of a public
    repository, and of a private one while the process sends the `sweep` ACL user (ADR 0023
    section 8)."""

    PUBLIC = "public"
    PRIVATE = "private"
    UNKNOWN = "unknown"


SWEEP_USER: Final[str] = "sweep"
"""The ACL user of the role that writes the data of a private repository to the shared tier
(#4704). The `sweep` user holds `~valkey:roadmap:*`, so its process reads and writes the shared
copy of a private repository; no other role does."""


def configured_valkey_user() -> str | None:
    """The ACL user that this process sends, from `valkey.username`; None when it names none."""
    return load_settings().valkey.username or None


def for_user(visibility: Visibility, user: str | None) -> Visibility:
    """`visibility` as the shared tier takes it for the ACL user `user`: a private repository is
    public to `SWEEP_USER`, whose process reads and writes the shared data of a private repository
    (#4704). Each other answer, and each other user or none, keeps the answer."""
    if visibility is Visibility.PRIVATE and user == SWEEP_USER:
        return Visibility.PUBLIC
    return visibility


def _monotonic() -> float:
    """The clock of the visibility answers: the clock seam, which the `clock` fixture moves."""
    return clock.monotonic()


def _expiry(name: str, answer: Visibility, now: float) -> float:
    """When the process reads the visibility of a repository again: after
    `DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` for an unknown answer, else after
    `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS`."""
    if answer is Visibility.UNKNOWN:
        return now + DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS
    return now + DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS


_LOCK = threading.Lock()
# The visibility answers of this process, by `RepoRef.key`. A `TLRUCache` is not thread-safe, so
# each use holds the lock.
_answers: TLRUCache[str, Visibility] = TLRUCache(
    maxsize=DEFAULT_BRAIN_MEMORY_ENTRIES, ttu=_expiry, timer=_monotonic
)


def held_visibility(repo: str) -> Visibility | None:
    """The answer that the process holds for `repo`, or None when it holds none or the answer is
    past its time to live. It sends no request."""
    with _LOCK:
        return _answers.get(RepoRef(repo).key)


def visibility_of(repo: str, is_private: Callable[[], bool]) -> Visibility:
    """The visibility of `repo`: the answer that the process holds, else the answer of
    `is_private`, the read of GitHub of the caller, which the process then keeps for its time to
    live (`_expiry`). A read that fails with a `DevOpsCLIError` gives `Visibility.UNKNOWN`: the
    shared tier gets no data that could be private (ADR 0023 section 8)."""
    held = held_visibility(repo)
    if held is not None:
        return held
    try:
        answer = Visibility.PRIVATE if is_private() else Visibility.PUBLIC
    except DevOpsCLIError as exc:
        logger.warning(
            "The visibility of %s is not known, so the process does not use or write its data in "
            "the shared tier, and reads the visibility again after %s s: %s",
            repo,
            DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS,
            exc,
        )
        answer = Visibility.UNKNOWN
    with _LOCK:
        _answers[RepoRef(repo).key] = answer
    return answer


def reset_visibility() -> None:
    """Drop the visibility answers of the process, as a new process starts."""
    with _LOCK:
        _answers.clear()


__all__ = [
    "SWEEP_USER",
    "Visibility",
    "configured_valkey_user",
    "for_user",
    "held_visibility",
    "reset_visibility",
    "visibility_of",
]
