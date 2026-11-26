"""The gates and the rank of the reference step, in code (#4672).

**Gates.** The step keeps a hit only when it is a code hit, and its repository is not this
repository, not linked already in the item, public, not archived, not a fork, pushed within
`CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS` days and under a license that the OSI approved. A code
hit names a file that is no prose: a Markdown or a text file is documentation of a repository, and
no implementation. Its path holds no empty segment, no `.` and no `..`. GitHub's search token can read private repositories, so the gate `private` keeps
a path of one out of an issue.

**Rank.** The score of a candidate is the sum of four facts: the base-10 logarithm of its stars,
the base-10 logarithm of the direct dependents that deps.dev counts for its PyPI package, the
number of PyPI packages of the SBOM whose source it is, and 1 when it holds tests. The order of the
hits breaks a tie, so the rank is the same for the same facts.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS
from devops_cli.github.repo_ref import is_repository_name
from devops_cli.roadmap.inventory import project_of
from devops_cli.roadmap.references.providers import Hit, HitKind

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import ReferenceFacts

# The SPDX identifiers of the licenses that the OSI approved, among the licenses that GitHub
# detects in a repository (https://opensource.org/licenses, read 2026-11-26). GitHub writes the
# GNU licenses without `-only` or `-or-later`. `NOASSERTION`, CC0-1.0, WTFPL and BSD-4-Clause are
# not approved, so they are not in the table.
_OSI_LICENSES: Final[frozenset[str]] = frozenset(
    {
        "0BSD",
        "AFL-3.0",
        "AGPL-3.0",
        "Apache-2.0",
        "Artistic-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSL-1.0",
        "CECILL-2.1",
        "ECL-2.0",
        "EPL-1.0",
        "EPL-2.0",
        "EUPL-1.1",
        "EUPL-1.2",
        "GPL-2.0",
        "GPL-3.0",
        "ISC",
        "LGPL-2.1",
        "LGPL-3.0",
        "LPPL-1.3c",
        "MIT",
        "MIT-0",
        "MPL-2.0",
        "MS-PL",
        "MS-RL",
        "MulanPSL-2.0",
        "NCSA",
        "OFL-1.1",
        "OSL-3.0",
        "PostgreSQL",
        "UPL-1.0",
        "Unlicense",
        "Zlib",
    }
)
_OSI_KEYS: Final[frozenset[str]] = frozenset(name.casefold() for name in _OSI_LICENSES)
# The suffixes of an SPDX identifier of a GNU license that GitHub leaves out.
_GNU_SUFFIXES: Final[tuple[str, ...]] = ("-only", "-or-later")
# The suffixes of a prose file, which is no code, in lower case. The table of media types of the
# standard library is no test for prose: it reads `.c`, `.h`, `.pl`, `.bat` and `.ksh` as
# `text/plain`.
_PROSE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".adoc", ".htm", ".html", ".markdown", ".md", ".mdx", ".rst", ".txt"}
)
# The segments that a path of a file in a repository does not hold: an empty one, and the two
# that name a directory and its parent.
_NO_SEGMENTS: Final[frozenset[str]] = frozenset({"", ".", ".."})


class Gate(StrEnum):
    """The gate that dropped a hit, which the log names."""

    NOT_CODE = "not-code"
    OWN = "own-repository"
    LINKED = "linked"
    PRIVATE = "private"
    ARCHIVED = "archived"
    FORK = "fork"
    STALE = "stale"
    LICENSE = "license"


def is_osi_license(spdx: str | None) -> bool:
    """Whether `spdx` is the SPDX identifier of a license that the OSI approved."""
    name = (spdx or "").casefold()
    for suffix in _GNU_SUFFIXES:
        name = name.removesuffix(suffix)
    return name in _OSI_KEYS


def _is_code(hit: Hit) -> bool:
    """Whether `hit` names a file of a repository that is no prose. A repository whose name is
    not `owner/name` is no repository, and a path with an empty segment, `.` or `..` is no path
    of a file: each provider can give one, and no contents read and no link takes it."""
    if hit.kind is not HitKind.CODE or not is_repository_name(hit.repository):
        return False
    path = PurePosixPath(hit.path)
    whole = bool(hit.path) and not _NO_SEGMENTS.intersection(hit.path.split("/"))
    return whole and path.suffix.lower() not in _PROSE_SUFFIXES


def hit_gate(hit: Hit, *, own: str, linked: Collection[str]) -> Gate | None:
    """The gate that drops `hit` with no read, or None: no code hit, a hit of the repository `own`,
    or a repository that the item links already. `linked` holds the project keys of the
    repositories that the item names."""
    if not _is_code(hit):
        return Gate.NOT_CODE
    if hit.repository.casefold() == own.casefold():
        return Gate.OWN
    if project_of(f"https://github.com/{hit.repository}") in linked:
        return Gate.LINKED
    return None


def facts_gate(facts: ReferenceFacts, now: datetime) -> Gate | None:
    """The gate that the facts of a repository fail, or None."""
    maintained = timedelta(days=CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS)
    checks = (
        (Gate.PRIVATE, facts.private),
        (Gate.ARCHIVED, facts.archived),
        (Gate.FORK, facts.fork),
        (Gate.STALE, facts.pushed_at is None or now - facts.pushed_at > maintained),
        (Gate.LICENSE, not is_osi_license(facts.license)),
    )
    return next((gate for gate, fails in checks if fails), None)


@dataclass(frozen=True)
class Candidate:
    """A code hit that passed the gates, with the facts of its rank: the facts of its repository,
    the direct dependents of its PyPI package and the PyPI packages of the SBOM whose source it
    is."""

    hit: Hit
    facts: ReferenceFacts
    dependents: int = 0
    shared: int = 0

    @property
    def score(self) -> float:
        """The rank score: higher is better."""
        return (
            math.log10(1 + max(self.facts.stars, 0))
            + math.log10(1 + max(self.dependents, 0))
            + self.shared
            + (1 if self.facts.has_tests else 0)
        )


def ranked(candidates: Sequence[Candidate]) -> list[Candidate]:
    """`candidates` by score, the best first. Two candidates of one score keep their order."""
    return sorted(candidates, key=lambda candidate: -candidate.score)


__all__ = ["Candidate", "Gate", "facts_gate", "hit_gate", "is_osi_license", "ranked"]
