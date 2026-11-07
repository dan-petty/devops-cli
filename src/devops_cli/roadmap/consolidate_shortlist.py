"""The shortlists of the consolidation job (#1127).

Open items that share a root cause are filed one at a time. The consolidation job looks for them,
and a model judges what it finds. This module is the step before the model: for each open item,
as an anchor, it lists the other open items that may share its cause, and keeps the evidence for
each. Three signals give the members, and no model is called:

- citations: the paths and the backticked identifiers that two bodies both cite, read as refine
  reads them (`cited_paths`, `cited_identifiers`), from the text of a person only. A citation
  that more than `DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION` open items share, such as
  `CONTEXT.md`, shows no shared cause and is left out;
- links: blocked-by, sub-issue and parent, the lines "Depends on", "Related", "Split from",
  "Split off" and "Merged into", and the section "Dependencies" of refine;
- embeddings: the `DEFAULT_ROADMAP_INTAKE_SHORTLIST` nearest items, ranked by `nearest`, the
  function that intake uses too. Embeddings are cached by the hash of the text of a person.

`assign_groups` then puts each item in at most one group, as the anchor or as a member. The
stronger evidence wins, and a tie goes to the lower anchor number. A member does not anchor a
group, so no group joins another: the code makes no transitive join and builds no graph.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.config.constants import (
    CONST_ROADMAP_CONSOLIDATE_DIR,
    CONST_ROADMAP_CONSOLIDATE_EMBEDDINGS_FILE,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION,
    DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS,
    DEFAULT_ROADMAP_INTAKE_SHORTLIST,
)
from devops_cli.roadmap.body_hash import hash_text, text_of_a_person
from devops_cli.roadmap.nearest import embedding_text, nearest
from devops_cli.roadmap.refine.refine import body_dependencies, cited_identifiers, cited_paths
from devops_cli.roadmap.stores.store import GitHubState, IssueRecord, RoadmapStore

logger = logging.getLogger(__name__)

# A line that names the issues it relates the item to: a label at the start of the line, after an
# optional list mark and optional bold. The issues of nested list lines under it belong to it.
_RELATION: Final[re.Pattern[str]] = re.compile(
    r"^(?P<indent>\s*)(?:[-*+]\s+)?(?:\*\*|__)?"
    r"(?P<label>depends on|related|split from|split off|merged into)\b",
    re.IGNORECASE,
)
_ISSUE_NUMBER: Final[re.Pattern[str]] = re.compile(r"(?<![\w/])#(\d+)\b")
# The most identifiers and paths that the evidence of one member names.
_EVIDENCE_NAMES: Final[int] = 3


class Signal(StrEnum):
    """What put an item on a shortlist, from the strongest to the weakest."""

    PATH_AND_IDENTIFIER = "shared path and identifier"
    PATH = "shared path"
    IDENTIFIER = "shared identifier"
    LINK = "link"
    EMBEDDING = "embedding rank"


_STRENGTH: Final[dict[Signal, int]] = {
    signal: len(Signal) - place for place, signal in enumerate(Signal)
}


class Evidence(BaseModel):
    """One reason for a member: its signal, and what the signal found, such as the path, the
    identifier or the link. `detail` is for display. An embedding signal also holds its `rank`,
    the place of the member among the nearest items: the ordering reads that, not the text."""

    model_config = ConfigDict(frozen=True)

    signal: Signal
    detail: str
    rank: int | None = None


class Member(BaseModel):
    """An item on the shortlist of an anchor, with all the evidence that put it there."""

    model_config = ConfigDict(frozen=True)

    number: int
    evidence: tuple[Evidence, ...]

    @property
    def weight(self) -> tuple[int, int]:
        """How strong the evidence is: the strength of its best signal, and for an embedding
        rank, the nearer the better. A higher weight is stronger."""
        best = max(self.evidence, key=lambda item: _STRENGTH[item.signal])
        return _STRENGTH[best.signal], -(best.rank or 0)


class Shortlist(BaseModel):
    """An anchor and the members that may share its cause, the strongest first."""

    model_config = ConfigDict(frozen=True)

    anchor: int
    members: tuple[Member, ...]


# ── Citations ──


def _is_file(path: str) -> bool:
    """Whether a cited word is a file: its extension starts with a letter, so a version such as
    `0.2.26` is none."""
    return PurePosixPath(path).suffix[1:2].isalpha()


def _citations(issues: Sequence[IssueRecord]) -> tuple[dict[int, set[str]], dict[int, set[str]]]:
    """The files and the identifiers each issue cites, without those that more than
    `DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION` issues cite. Only the text of a person is read:
    a section that a job writes shows no shared cause."""
    texts = {issue.number: text_of_a_person(issue.body) for issue in issues}
    paths = {n: {p for p in cited_paths(text) if _is_file(p)} for n, text in texts.items()}
    names = {n: set(cited_identifiers(text)) for n, text in texts.items()}
    return _rare(paths), _rare(names)


def _rare(cited: Mapping[int, set[str]]) -> dict[int, set[str]]:
    """`cited` without the citations that too many issues share."""
    holders: dict[str, int] = defaultdict(int)
    for held in cited.values():
        for citation in held:
            holders[citation] += 1
    common = DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION
    return {
        number: {citation for citation in held if holders[citation] <= common}
        for number, held in cited.items()
    }


def _sharing(cited: Mapping[int, set[str]]) -> dict[tuple[int, int], set[str]]:
    """The citations that each pair of issues share, for both orders of the pair."""
    holders: dict[str, list[int]] = defaultdict(list)
    for number, held in cited.items():
        for citation in held:
            holders[citation].append(number)
    shared: dict[tuple[int, int], set[str]] = defaultdict(set)
    for citation, numbers in holders.items():
        for first in numbers:
            for second in numbers:
                if first != second:
                    shared[first, second].add(citation)
    return shared


# ── Links ──


def _body_links(body: str) -> list[tuple[str, int]]:
    """The relation and the issue number of each issue that a person names in `body` after one
    of the labels of `_RELATION`, or that `body` names under the heading "Dependencies", which
    refine writes too. A nested list line counts for the line it is under."""
    found: list[tuple[str, int]] = []
    label = ""
    depth = -1
    for line in text_of_a_person(body).splitlines():
        match = _RELATION.match(line)
        indent = len(line) - len(line.lstrip())
        if match is not None:
            label, depth = match.group("label").capitalize(), len(match.group("indent"))
        elif not line.strip() or indent <= depth:
            label, depth = "", -1
        if label:
            found += [(label, int(number)) for number in _ISSUE_NUMBER.findall(line)]
    found += [("Dependencies", number) for number in body_dependencies(body)]
    return found


def _links(
    issues: Sequence[IssueRecord], blockers: Mapping[int, Sequence[int]]
) -> dict[tuple[int, int], list[str]]:
    """The links between issues, for both orders of each pair, as text such as `#4 Related #9`."""
    open_numbers = {issue.number for issue in issues}
    found: dict[tuple[int, int], list[str]] = defaultdict(list)

    def link(source: int, target: int, relation: str) -> None:
        if source != target and target in open_numbers:
            text = f"#{source} {relation} #{target}"
            for pair in ((source, target), (target, source)):
                if text not in found[pair]:
                    found[pair].append(text)

    for issue in issues:
        for relation, number in _body_links(issue.body):
            link(issue.number, number, relation)
        if issue.parent is not None:
            link(issue.parent, issue.number, "has the sub-issue")
        for blocker in blockers.get(issue.number, ()):
            link(issue.number, blocker, "is blocked by")
    return found


def read_blockers(store: RoadmapStore, issues: Iterable[IssueRecord]) -> dict[int, list[int]]:
    """The issues that block each issue, read for the issues whose listing counts a blocker
    only: a board with few links makes few requests."""
    return {issue.number: store.blocked_by(issue.number) for issue in issues if issue.blocked_by}


# ── Embeddings ──


class _EmbeddingFile(BaseModel):
    """The cache file: the name of the model that made the vectors, and a vector for the hash of
    each text. Vectors of two models do not compare, so a file of another model is no cache."""

    model: str
    vectors: dict[str, list[float]]


def embeddings_path(directory: Path) -> Path:
    """The cache file of the embeddings, in `directory`, the data directory."""
    return directory / CONST_ROADMAP_CONSOLIDATE_DIR / CONST_ROADMAP_CONSOLIDATE_EMBEDDINGS_FILE


def _read_cache(path: Path, model: str) -> dict[str, list[float]]:
    """The cached vectors of `model`. A missing file, a file of another model and a file that
    can't be read give none; the last is logged, as a run then embeds every item again."""
    if not path.is_file():
        return {}
    try:
        held = _EmbeddingFile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        logger.warning("The embedding cache %s can't be read, so it is built again: %s", path, exc)
        return {}
    return held.vectors if held.model == model else {}


def _write_cache(path: Path, model: str, vectors: Mapping[str, list[float]]) -> None:
    from devops_cli.output.file_writer import write_json_file

    held = _EmbeddingFile(model=model, vectors=dict(vectors))
    write_json_file(path, held.model_dump(mode="json"), indent=0, atomic=True)


def _text(issue: IssueRecord) -> str:
    """What is embedded for an issue: its title and the text of a person in its body. The
    sections that the refine job and the alternatives job write are no part of it, so a job
    that writes its section causes no new embedding."""
    return embedding_text(issue.title, text_of_a_person(issue.body))


def embed_issues(
    issues: Sequence[IssueRecord],
    embed: Callable[[Sequence[str]], list[list[float]]],
    *,
    model: str,
    path: Path,
) -> dict[int, list[float]]:
    """One vector for each issue. A vector is cached in `path` under the hash of its text, with
    the name of `model`, so a run over issues with the same text embeds nothing. The file keeps
    the vectors of these issues only."""
    texts = {issue.number: _text(issue) for issue in issues}
    keys = {number: hash_text(text) for number, text in texts.items()}
    cached = _read_cache(path, model)
    missing = {key: texts[number] for number, key in keys.items() if key not in cached}
    if missing:
        vectors = embed(list(missing.values()))
        cached = cached | dict(zip(missing, vectors, strict=True))
    kept = {key: cached[key] for key in keys.values()}
    if missing or len(kept) != len(cached):
        _write_cache(path, model, kept)
    return {number: kept[key] for number, key in keys.items()}


# ── Shortlists ──


def shortlists(
    issues: Sequence[IssueRecord],
    vectors: Mapping[int, list[float]],
    blockers: Mapping[int, Sequence[int]],
) -> list[Shortlist]:
    """The shortlist of each issue as an anchor, the issues in order of number. `issues` are the
    open items, and the only issues that a shortlist names. An issue with no member has no
    shortlist. A shortlist keeps the `DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS` members with the
    strongest evidence, and a tie goes to the lower number."""
    paths, names = _citations(issues)
    shared_paths, shared_names = _sharing(paths), _sharing(names)
    linked = _links(issues, blockers)
    numbers = sorted(issue.number for issue in issues)
    result: list[Shortlist] = []
    for anchor in numbers:
        found: dict[int, list[Evidence]] = defaultdict(list)
        others = [number for number in numbers if number != anchor]
        for other in others:
            held = (
                shared_paths.get((anchor, other), set()),
                shared_names.get((anchor, other), set()),
            )
            found[other] += _citation_evidence(*held)
            found[other] += [Evidence(signal=Signal.LINK, detail=t) for t in linked[anchor, other]]
        closest = nearest(
            vectors[anchor], [(n, vectors[n]) for n in others], DEFAULT_ROADMAP_INTAKE_SHORTLIST
        )
        for place, other in enumerate(closest, start=1):
            found[other].append(
                Evidence(signal=Signal.EMBEDDING, detail=f"rank {place}", rank=place)
            )
        members = [Member(number=n, evidence=tuple(held)) for n, held in found.items() if held]
        members.sort(key=lambda member: (tuple(-w for w in member.weight), member.number))
        if members:
            result.append(
                Shortlist(
                    anchor=anchor, members=tuple(members[:DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS])
                )
            )
    return result


def _citation_evidence(paths: set[str], names: set[str]) -> list[Evidence]:
    """The evidence of the paths and the identifiers that two issues share: one for each path
    and each identifier, the first few of them, and one that holds both when they share both."""
    shared_paths, shared_names = sorted(paths)[:_EVIDENCE_NAMES], sorted(names)[:_EVIDENCE_NAMES]
    evidence = [Evidence(signal=Signal.PATH, detail=path) for path in shared_paths]
    evidence += [Evidence(signal=Signal.IDENTIFIER, detail=name) for name in shared_names]
    if shared_paths and shared_names:
        both = f"{shared_paths[0]} and {shared_names[0]}"
        evidence.append(Evidence(signal=Signal.PATH_AND_IDENTIFIER, detail=both))
    return evidence


def assign_groups(lists: Iterable[Shortlist]) -> list[Shortlist]:
    """The groups, each an anchor with the members of its shortlist that it keeps. An item is in
    one group at most, as the anchor or as a member. The strongest evidence is placed first, and
    on equal evidence the lower anchor number, then the lower member number. An item that is a
    member of a group does not anchor one, and a member is never placed twice, so no group
    joins another. The groups are in order of the anchor."""
    edges = sorted(
        ((anchor.anchor, member) for anchor in lists for member in anchor.members),
        key=lambda edge: (tuple(-w for w in edge[1].weight), edge[0], edge[1].number),
    )
    owner: dict[int, int] = {}
    kept: dict[int, list[Member]] = defaultdict(list)
    for anchor, member in edges:
        if member.number in owner or owner.get(anchor, anchor) != anchor:
            continue
        owner[anchor] = anchor
        owner[member.number] = anchor
        kept[anchor].append(member)
    return [Shortlist(anchor=anchor, members=tuple(kept[anchor])) for anchor in sorted(kept)]


def consolidation_groups(
    store: RoadmapStore,
    embed: Callable[[Sequence[str]], list[list[float]]],
    *,
    model: str,
    directory: Path,
) -> list[Shortlist]:
    """The groups of the open items of `store`, from tools only. `embed` makes one vector for
    each text, `model` names the model it uses, and `directory` is the data directory that holds
    the cache. The store is read, and nothing is written to it."""
    numbers = {item.number for item in store.open_items()}
    issues = [
        issue
        for issue in store.issues()
        if issue.number in numbers and issue.state is GitHubState.OPEN
    ]
    vectors = embed_issues(issues, embed, model=model, path=embeddings_path(directory))
    return assign_groups(shortlists(issues, vectors, read_blockers(store, issues)))


__all__ = [
    "Evidence",
    "Member",
    "Shortlist",
    "Signal",
    "assign_groups",
    "consolidation_groups",
    "embed_issues",
    "embeddings_path",
    "read_blockers",
    "shortlists",
]
