"""The brain digest that the alternatives check reads before its one model call (#4682, ADR 0023
section 1).

The digest gives the model the decisions of the near items of an item, so the check of one item
can agree with the checks of the items that named the same tool. It comes from the entry of the
item in the brain index of `valkey-roadmap` (`devops_cli.roadmap.brain_index`):

- **The near items.** The `near` field of the entry: at most `CONST_ROADMAP_BRAIN_ITEM_MAX_NEAR`
  other items of the repository whose check named the same tool, the newest check first. A near
  item with no entry is left out.
- **Each near item** gives the date of its check, its verdict, the canonical id of its tool and the
  name that its tool entry holds. The date of the check is the date of its verdict and its tool.
- **The ADR status of a tool.** The ADRs in force that the check reads, and that reject the tool
  under a rejected option (`devops_cli.roadmap.adr.rejects`).
- **The bound.** The digest holds whole entries in the order of the near items, and its JSON text
  holds at most `CONST_ROADMAP_BRAIN_DIGEST_MAX_TOKENS` tokens. An entry that does not fit is left
  out, and a later entry that fits stays.
- **No ring and no area verdict.** The brain index holds no ring of a tool and no area check, so
  the digest holds neither. The aggregate and improve tasks of #4693 add them to the brain.

The check adds the digest to its one request under the key `brain`, and makes no other model call.
A written check records the id of each entry that the digest used in `alternatives.brain_used`:
the entry of the item, then each near item and its tool, at most
`CONST_ROADMAP_BRAIN_ITEM_MAX_USES`.

**Fail soft.** With `roadmap.brain.digest` `off`, the run reads no brain. With no
`roadmap.state.url`, as on a workstation, while the store does not answer, and for an item that
the index holds no entry or no near item for, the digest is empty: the request holds no `brain`,
and the check runs as before.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import (
    CONST_ROADMAP_BRAIN_DIGEST_MAX_TOKENS,
    CONST_ROADMAP_BRAIN_ITEM_MAX_NEAR,
    CONST_ROADMAP_BRAIN_ITEM_MAX_USES,
)
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.adr import Adr, rejects
from devops_cli.roadmap.brain_index import (
    BrainIndex,
    HeldItem,
    HeldTool,
    item_entry_id,
    tool_entry_id,
)
from devops_cli.valkey.cache import roadmap_state_tier

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DigestEntry:
    """One near item of the digest: the item, its check, its tool with the name of its tool entry
    (empty when the index holds no tool entry), the numbers of the ADRs that reject the tool, and
    the ids of the brain entries that it took."""

    item: HeldItem
    tool: HeldTool | None
    rejected_by: tuple[int, ...]
    used: tuple[str, ...]

    def value(self) -> dict[str, Any]:
        """The entry as the request of the model holds it. An entry with no tool holds no tool
        keys, and a tool with no tool entry holds no name."""
        held = self.item
        tool: dict[str, Any] = {}
        if held.tool_id:
            name = {"tool_name": self.tool.name} if self.tool and self.tool.name else {}
            rejected = [f"ADR {number:04d}" for number in self.rejected_by]
            tool = {"tool": held.tool_id, **name, "rejected_by": rejected}
        return {
            "item": held.number,
            "checked": held.checked_at.date().isoformat(),
            "verdict": held.verdict.value,
            **tool,
        }


@dataclass(frozen=True)
class BrainDigest:
    """The digest of one item: its entries, and the ids of the brain entries that they used. It
    is empty when the brain gives nothing."""

    entries: tuple[DigestEntry, ...] = ()
    used: tuple[str, ...] = ()

    def value(self) -> list[dict[str, Any]]:
        """The entries as the request of the model holds them, under the key `brain`."""
        return [entry.value() for entry in self.entries]


def _text(values: Sequence[dict[str, Any]]) -> str:
    """The JSON text of the digest entries `values`, as the request writes it."""
    return json.dumps(list(values), ensure_ascii=False, indent=1)


def _fitted(entries: Sequence[DigestEntry]) -> tuple[DigestEntry, ...]:
    """The entries of `entries`, in their order, whose JSON text holds at most
    `CONST_ROADMAP_BRAIN_DIGEST_MAX_TOKENS` tokens. The cut takes whole entries."""
    kept: list[DigestEntry] = []
    for entry in entries:
        values = [*(held.value() for held in kept), entry.value()]
        if count_tokens(_text(values)) <= CONST_ROADMAP_BRAIN_DIGEST_MAX_TOKENS:
            kept.append(entry)
    return tuple(kept)


def _entry(item: HeldItem, tool: HeldTool | None, adrs: Sequence[Adr]) -> DigestEntry:
    """The digest entry of the near item `item`, whose tool entry is `tool`."""
    if not item.tool_id:
        return DigestEntry(item, None, (), (item_entry_id(item.number),))
    names = (item.tool_id, tool.name if tool else "")
    rejected_by = tuple(adr.number for adr in adrs if rejects(adr, *names))
    used = (item_entry_id(item.number), *((tool_entry_id(item.tool_id),) if tool else ()))
    return DigestEntry(item, tool, rejected_by, used)


def _near_items(index: BrainIndex, number: int) -> list[HeldItem] | None:
    """The entry of each near item of the entry of item `number`, in the order of the entry; none
    when the index holds no entry of the item. None when the store does not answer."""
    own = index.items([number])
    if own is None:
        return None
    near = own[number].near[:CONST_ROADMAP_BRAIN_ITEM_MAX_NEAR] if number in own else ()
    held = index.items(near)
    if held is None:
        return None
    return [held[near_number] for near_number in near if near_number in held]


def read_digest(index: BrainIndex | None, number: int, adrs: Sequence[Adr]) -> BrainDigest:
    """The digest of item `number` from `index`, with the ADR status of each tool from `adrs`, the
    ADRs in force that the check reads; empty with no index, while the store does not answer, and
    when the index holds no entry or no near item of the item."""
    if index is None:
        return BrainDigest()
    items = _near_items(index, number)
    tools = None if items is None else index.tools({item.tool_id for item in items} - {""})
    if items is None or tools is None:
        logger.info("The brain digest of #%d is empty: the brain index did not answer.", number)
        return BrainDigest()
    entries = _fitted([_entry(item, tools.get(item.tool_id), adrs) for item in items])
    if not entries:
        return BrainDigest()
    used = dict.fromkeys(
        [item_entry_id(number), *(entry_id for entry in entries for entry_id in entry.used)]
    )
    return BrainDigest(entries, tuple(used)[:CONST_ROADMAP_BRAIN_ITEM_MAX_USES])


def digest_index(repo: str, settings: Settings) -> BrainIndex | None:
    """The brain index that the checks of a run of `repo` read their digest from; None when
    `roadmap.brain.digest` is `off`, so the run reads no brain, and when the process has no tier of
    the roadmap state, as on a workstation."""
    if settings.roadmap.brain.digest == "off":
        return None
    tier = roadmap_state_tier()
    return None if tier is None else BrainIndex(tier, RepoRef(repo))


__all__ = ["BrainDigest", "DigestEntry", "digest_index", "read_digest"]
