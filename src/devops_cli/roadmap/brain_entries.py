"""The entry of the brain index that one issue gives (#4676, ADR 0023 section 3).

The alternatives check keeps its result in two places of an issue: the block between the two
markers of the job in the body, and the keys `alternatives.*` of the job record. They are the
durable copy of the brain index, so an entry is read from them with no request and no model call,
and a lost index is built again from the listing snapshot.

- The record gives the verdict, the time of the check, the hash of the body and of the ADRs that
  the check read, the URL of the tool and its canonical id (`devops_cli.roadmap.inventory`). A
  check from before the canonical id recorded only the URL, and the entry takes the id of that URL.
- The block gives the name that the check wrote for the tool, which stays an alias of the id. A
  record with no block is no check, since a person deleted the block. The block of the reference
  step (#4672) has two more sections, which change no field that the block gives.
- `alternatives.refs` gives the links of the reference step. A reference of the index is the
  GitHub repository of a link, one time for each repository, and at most
  `CONST_ROADMAP_BRAIN_ITEM_MAX_REFS`. A link to a page outside GitHub names no repository.
- `alternatives.brain_used` gives the entries that the check used, at most
  `CONST_ROADMAP_BRAIN_ITEM_MAX_USES`.

The record is read by the text of its keys, so a key that another version of the record writes
is read when the record holds it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_BRAIN_ITEM_MAX_REFS,
    CONST_ROADMAP_BRAIN_ITEM_MAX_USES,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.inventory import canonical_id, project_of
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    GitHubState,
    IssueRecord,
    Verdict,
)

# The keys of the record that a later version of the record declares: the links of the reference
# step (#4672) and the entries that the check used (#4682).
_REFS_KEY: Final[str] = "alternatives.refs"
_USES_KEY: Final[str] = "alternatives.brain_used"
_KEY_ID_SIZE: Final[int] = 16


@dataclass(frozen=True)
class BrainEntry:
    """What the brain index holds of the check of one issue. `tool_id` is the canonical id of the
    tool, and `tool_url` and `tool_name` are the URL and the name that the check wrote for it;
    each is empty for a check with no tool. `refs` holds the repository URL of each reference,
    and `uses` the entries that the check used."""

    number: int
    state: GitHubState
    verdict: Verdict
    checked_at: datetime
    body_hash: str
    adr_hash: str
    tool_id: str
    tool_url: str
    tool_name: str
    refs: tuple[str, ...]
    uses: tuple[str, ...]


def _key_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_KEY_ID_SIZE]


def tool_key_id(tool_id: str) -> str:
    """The id of a tool in a key of the index: 16 hex characters of the hash of its canonical id
    (ADR 0023 section 6), which holds no `/` and no glob character."""
    return _key_id(tool_id)


def reference_key_id(repository_url: str) -> str:
    """The id of a reference in a key of the index: 16 hex characters of the hash of the URL of
    its repository."""
    return _key_id(repository_url)


def _verdict(recorded: str | None) -> Verdict | None:
    try:
        return Verdict(recorded) if recorded else None
    except ValueError:
        return None


def _time(recorded: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(recorded) if recorded else None
    except ValueError:
        return None


def _tool_name(block: str, url: str) -> str:
    """The name of the tool on the tool line of `block`: the text between the start of the line
    and the URL of the tool, as `alternatives_block_tool` writes it. Empty when no line names
    `url`."""
    head, _, tail = MESSAGES.roadmap.alternatives_block_tool.partition("{name}")
    anchor = tail.partition("{url}")[0] + url
    for line in block.splitlines():
        if line.startswith(head) and anchor in line[len(head) :]:
            return line[len(head) : line.index(anchor, len(head))]
    return ""


def _repositories(links: str) -> tuple[str, ...]:
    """The URL of the GitHub repository of each link of `links`, each one time, in order."""
    projects = (project_of(link) for link in links.split())
    urls = dict.fromkeys(f"https://{project}" for project in projects if project)
    return tuple(urls)[:CONST_ROADMAP_BRAIN_ITEM_MAX_REFS]


def checked_entry(
    number: int, state: GitHubState, body: str, record: Mapping[str, str | None]
) -> BrainEntry | None:
    """The entry of issue `number` with the state `state`, from its body and from its job record
    by the text of its keys; None when the body holds no block of the job or the record holds no
    verdict and no time of a check."""
    verdict = _verdict(record.get(AlternativesRecordKey.VERDICT))
    checked_at = _time(record.get(AlternativesRecordKey.CHECKED_AT))
    if verdict is None or checked_at is None:
        return None
    _, block = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    if block is None:
        return None
    url = record.get(AlternativesRecordKey.TOOL) or ""
    return BrainEntry(
        number=number,
        state=state,
        verdict=verdict,
        checked_at=checked_at,
        body_hash=record.get(AlternativesRecordKey.BODY_HASH) or "",
        adr_hash=record.get(AlternativesRecordKey.ADR_HASH) or "",
        tool_id=record.get(AlternativesRecordKey.TOOL_ID)
        or (canonical_id(url, None) if url else ""),
        tool_url=url,
        tool_name=_tool_name(block, url) if url else "",
        refs=_repositories(record.get(_REFS_KEY) or ""),
        uses=tuple((record.get(_USES_KEY) or "").split())[:CONST_ROADMAP_BRAIN_ITEM_MAX_USES],
    )


def entry_of(issue: IssueRecord) -> BrainEntry | None:
    """The entry of `issue`, an issue of the listing snapshot; None for a pull request and for an
    issue that holds no check."""
    if issue.pull_request:
        return None
    record = {str(key): value for key, value in issue.job_record.items()}
    return checked_entry(issue.number, issue.state, issue.body, record)


__all__ = ["BrainEntry", "checked_entry", "entry_of", "reference_key_id", "tool_key_id"]
