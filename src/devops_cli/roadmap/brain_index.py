"""The brain index of one repository in `valkey-roadmap`: its keys, its writes and its reads
(#4676, ADR 0023 section 3).

`RepoRef` builds each key (ADR 0022 section 5), so each holds the schema version `v1` and the
repository, and the ACL pattern `roadmap:v1:brain-*` of the user `brain` matches each:

| Key | Type | Holds | Ends |
| :--- | :--- | :--- | :--- |
| `roadmap:v1:brain-item:<owner>/<name>:<n>` | hash | the check of item `<n>` | TTL 45 days |
| `roadmap:v1:brain-tool:<owner>/<name>:<h16>` | hash | a tool and the items that name it | TTL 45 days |
| `roadmap:v1:brain-ref:<owner>/<name>:<h16>` | hash | a reference repository and its items | TTL 45 days |
| `roadmap:v1:brain-events:<owner>/<name>` | stream | one entry for each write, about 10,000 | TTL 45 days |
| `roadmap:v1:brain-sync:<owner>/<name>` | hash | the watermark of the sync | one owner, the sync |

`<h16>` is 16 hex characters of the hash of the canonical id of the tool, or of the URL of the
reference repository. Each write of a hash or of the stream sets its TTL again, so an entry that
no sync writes for 45 days goes. The stream is an audit trail only, and no job reads it as a
trigger.

**One item, one transaction.** `write` sends the item hash, the tool hash, each reference hash and
the stream entry in one WATCH/MULTI/EXEC through `watch_and_write` of the tier, so an entry is
whole, old or new. Each hash is written whole, so no field of an older check stays.

**The newer check wins.** The transaction watches the item key and reads the `checked_at` of the
entry that the index holds. When that time is newer than the one of the block, `write` sends no
command and the entry stays: a late copy of an issue from before its last check drops no check.
GitHub holds the durable copy, so in each other case the block replaces the entry.

**Fail soft.** Each command goes through the breaker of the tier. While the store does not
answer, a read gives None and a write does not occur, with no error (ADR 0023 section 2).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from itertools import chain
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_BRAIN_EVENTS_MAX_ENTRIES,
    CONST_ROADMAP_BRAIN_INDEX_TTL_SECONDS,
)
from devops_cli.roadmap.brain_entries import BrainEntry, reference_key_id, tool_key_id

if TYPE_CHECKING:
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.valkey.cache import ValkeyCacheTier

# The version of the fields of each hash. A hash of another version is written again.
SCHEMA: Final[str] = "1"

_KIND_ITEM: Final[str] = "brain-item"
_KIND_TOOL: Final[str] = "brain-tool"
_KIND_REFERENCE: Final[str] = "brain-ref"
_KIND_EVENTS: Final[str] = "brain-events"
_KIND_SYNC: Final[str] = "brain-sync"
_CHECKED_AT: Final[str] = "checked_at"
# How many fields or keys one step of a scan asks the server for.
_SCAN_COUNT: Final[int] = 500

Command = tuple[Any, ...]


class Written(StrEnum):
    """What the write of one item did: `NEW` when the index held no entry of the item,
    `REPLACED` when the block replaced the entry, and `KEPT` when the index holds the entry of a
    newer check, or another writer changed the item during the write."""

    NEW = "new"
    REPLACED = "replaced"
    KEPT = "kept"


@dataclass(frozen=True)
class Related:
    """What the other checks of the repository say of one entry: its near items, the items that
    name its tool, and the items that link each of its reference repositories."""

    near: tuple[int, ...] = ()
    tool_items: tuple[int, ...] = ()
    reference_items: Mapping[str, tuple[int, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Watermark:
    """Where the sync of a repository is: `changed` and `number` are the `updated_at` and the
    number of the last issue that it examined, and `synced_at` is when it last ended. Each is
    empty before the first sync."""

    changed: datetime | None = None
    number: int = 0
    synced_at: datetime | None = None


def _numbers(numbers: Sequence[int]) -> str:
    return " ".join(str(number) for number in numbers)


def _time(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def _is_newer(held: bytes | None, checked_at: datetime) -> bool:
    """Whether the `checked_at` that the index holds is a time after `checked_at`."""
    held_at = _time(held.decode("utf-8", "replace")) if held else None
    return held_at is not None and held_at > checked_at


def _watermark_of(fields: Mapping[str, str]) -> Watermark:
    """The watermark that the fields of its hash give; empty for a hash of another schema or
    with a number that is no number."""
    number = fields.get("number", "0")
    if fields.get("schema") != SCHEMA or not number.isdecimal():
        return Watermark()
    return Watermark(
        changed=_time(fields.get("changed")),
        number=int(number),
        synced_at=_time(fields.get("synced_at")),
    )


class BrainIndex:
    """The brain index of the repository `repo` through `tier`, the tier of `valkey-roadmap`."""

    def __init__(self, tier: ValkeyCacheTier, repo: RepoRef) -> None:
        self._tier = tier
        self._repo = repo

    def write(self, entry: BrainEntry, related: Related) -> Written | None:
        """Write the keys of the item of `entry` and its stream entry in one transaction, unless
        the index holds the entry of a newer check; None when the store does not answer."""
        held: list[bytes | None] = []

        def decide(checked_at: bytes | None) -> Sequence[Command]:
            held.append(checked_at)
            return [] if _is_newer(checked_at, entry.checked_at) else self._commands(entry, related)

        written = self._tier.watch_and_write(self._item_key(entry.number), _CHECKED_AT, decide)
        if written is None:
            return None
        if not written:
            return Written.KEPT
        return Written.NEW if held[0] is None else Written.REPLACED

    def watermark(self) -> Watermark | None:
        """The watermark of the sync, empty before the first sync; None when the store does not
        answer."""
        fields: dict[str, bytes] = {}
        cursor = 0
        while True:
            step = self._tier.hscan(self._sync_key, cursor, _SCAN_COUNT)
            if step is None:
                return None
            cursor, found = step
            fields |= found
            if cursor == 0:
                break
        return _watermark_of(
            {name: value.decode("utf-8", "replace") for name, value in fields.items()}
        )

    def advance(self, watermark: Watermark) -> bool:
        """Write `watermark`; False when the store does not answer. A watermark with no place
        writes the time of the sync only, and the place of the earlier write stays. The key has no
        TTL: the sync is its one owner."""
        fields = {"schema": SCHEMA}
        if watermark.changed is not None:
            fields |= {"changed": watermark.changed.isoformat(), "number": str(watermark.number)}
        if watermark.synced_at is not None:
            fields["synced_at"] = watermark.synced_at.isoformat()
        return self._tier.hset(self._sync_key, fields) is not None

    def item_keys(self) -> list[str] | None:
        """The key of each item entry of the repository, in order; None when the store does not
        answer. The pattern holds the whole repository part and the `:` after it, so it finds no
        key of a repository with a longer name."""
        pattern = f"{self._repo.valkey_key(_KIND_ITEM)}:*"
        keys: set[str] = set()
        cursor = 0
        while True:
            step = self._tier.scan(cursor, pattern, _SCAN_COUNT)
            if step is None:
                return None
            cursor, found = step
            keys.update(found)
            if cursor == 0:
                return sorted(keys)

    @property
    def _sync_key(self) -> str:
        return self._repo.valkey_key(_KIND_SYNC)

    def _item_key(self, number: int) -> str:
        return self._repo.valkey_key(_KIND_ITEM, str(number))

    def _commands(self, entry: BrainEntry, related: Related) -> list[Command]:
        """The commands of the transaction of `entry`: each hash with its TTL, then the entry of
        the stream with its bound and its TTL."""
        checked_at = entry.checked_at.isoformat()
        item = {
            "schema": SCHEMA,
            "verdict": entry.verdict.value,
            "tool_id": entry.tool_id,
            "refs": " ".join(reference_key_id(url) for url in entry.refs),
            "near": _numbers(related.near),
            _CHECKED_AT: checked_at,
            "body_hash": entry.body_hash,
            "adr_hash": entry.adr_hash,
            "state": entry.state.value,
            "uses": " ".join(entry.uses),
        }
        hashes = [(self._item_key(entry.number), item)]
        if entry.tool_id:
            tool = {
                "schema": SCHEMA,
                "id": entry.tool_id,
                "url": entry.tool_url,
                "name": entry.tool_name,
                _CHECKED_AT: checked_at,
                "items": _numbers(related.tool_items),
            }
            hashes.append((self._repo.valkey_key(_KIND_TOOL, tool_key_id(entry.tool_id)), tool))
        for url in entry.refs:
            reference = {
                "schema": SCHEMA,
                "url": url,
                _CHECKED_AT: checked_at,
                "items": _numbers(related.reference_items.get(url, ())),
            }
            hashes.append(
                (self._repo.valkey_key(_KIND_REFERENCE, reference_key_id(url)), reference)
            )
        event = {
            "item": str(entry.number),
            "verdict": entry.verdict.value,
            "tool_id": entry.tool_id,
            _CHECKED_AT: checked_at,
        }
        events_key = self._repo.valkey_key(_KIND_EVENTS)
        bound = ("MAXLEN", "~", CONST_ROADMAP_BRAIN_EVENTS_MAX_ENTRIES, "*")
        return [
            *chain.from_iterable(_hash_write(key, fields) for key, fields in hashes),
            ("XADD", events_key, *bound, *chain.from_iterable(event.items())),
            ("EXPIRE", events_key, CONST_ROADMAP_BRAIN_INDEX_TTL_SECONDS),
        ]


def _hash_write(key: str, fields: Mapping[str, str]) -> list[Command]:
    """The two commands that write the hash at `key` whole and set its TTL again."""
    return [
        ("HSET", key, *chain.from_iterable(fields.items())),
        ("EXPIRE", key, CONST_ROADMAP_BRAIN_INDEX_TTL_SECONDS),
    ]


__all__ = ["SCHEMA", "BrainIndex", "Related", "Watermark", "Written"]
