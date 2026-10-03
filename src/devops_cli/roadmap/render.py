"""`devops roadmap render`: the roadmap as Markdown, read from GitHub through the roadmap store.

The view lists the current release, the planned releases within the planning horizon, and the
backlog, each item on one line with its Status, Priority, Value and Effort. Items are ordered by
the board's Priority options, unset last, then by issue number. The text names no time and
reads nothing local, so two runs on the same GitHub state give the same bytes. It is rendered
in full before anything is written, so a failed read leaves the file as it was.
"""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.config.constants import CONST_ROADMAP_RENDER_MARKER
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.store import (
    GitHubState,
    Item,
    ItemField,
    Release,
    RoadmapStore,
    field_options,
)

_UNSET = "—"


def _release_heading(release: Release) -> str:
    return f"{release.title} — {release.description}" if release.description else release.title


def _item_line(item: Item) -> str:
    """One item: its checkbox, number, title, Status, Priority, Value and Effort."""
    mark = "x" if item.state is GitHubState.CLOSED else " "
    values = " · ".join(
        f"{board_field.value}: {item.field_value(board_field) or _UNSET}"
        for board_field in (ItemField.STATUS, ItemField.PRIORITY, ItemField.VALUE, ItemField.EFFORT)
    )
    return f"- [{mark}] #{item.number} {item.title} — {values}"


def _ordered(items: Sequence[Item], priorities: Sequence[str]) -> list[Item]:
    """Items by Priority in the board's option order, unset last, then by issue number."""
    rank = {name: index for index, name in enumerate(priorities)}

    def key(item: Item) -> tuple[int, int]:
        unknown = len(priorities) if item.priority else len(priorities) + 1
        return rank.get(item.priority or "", unknown), item.number

    return sorted(items, key=key)


def render_roadmap(store: RoadmapStore, *, repo: str, config: RoadmapConfig) -> str:
    """The roadmap's Markdown view: the current and planned releases, then the backlog."""
    messages = MESSAGES.roadmap
    priorities = field_options(store.board_fields()).get(ItemField.PRIORITY.value, ())
    open_releases = [r for r in store.releases() if r.state is GitHubState.OPEN]
    kept = open_releases[: 1 + config.planning_horizon]
    sections = [
        (
            (messages.render_planned if index else messages.render_current).format(
                title=_release_heading(release)
            ),
            store.items(release=release.title),
        )
        for index, release in enumerate(kept)
    ]
    sections.append((messages.render_backlog, store.backlog()))
    lines = [CONST_ROADMAP_RENDER_MARKER, "", f"# Roadmap — {repo}", ""]
    for heading, items in sections:
        rows = [_item_line(item) for item in _ordered(items, priorities)]
        lines.extend([heading, "", *(rows or [messages.render_empty]), ""])
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["render_roadmap"]
