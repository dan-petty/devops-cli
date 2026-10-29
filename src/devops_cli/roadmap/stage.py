"""`devops roadmap stage`: a Ready item becomes Staged (#2654).

The job turns each item that a label filter names into a branch `<type>/<issue>-<slug>` at the
fetched default branch, with the OpenSpec change `openspec/changes/<issue>-<slug>/` written from
the refined body, one commit by the identity of the session, and a draft pull request whose body
starts with `Plans #<issue>`. It never marks the pull request ready and never changes the item's
Status. The staged branch and the draft are the record.

**Selection.** `--filter family=value` is repeatable over the label families `status`,
`priority`, `type`, `value` and `effort`. The values of one family are alternatives, and the
families all apply. With no filter the job takes the Ready P0 and P1 bugs. It leaves out an item
that is Blocked, In Progress or In Review, an item with the label `needs-split`, an item whose
author has no write access (the model reads the body), an item whose "Dependencies" section names
an open issue, a held item (`worktree_add.issue_holder`), an item whose title gives no branch name,
an item whose text looks like a secret, and an item whose record holds `stage.needs_split`. A run
takes at most `--limit` items, highest priority first. `--item` takes the one item it names when
that item is open and Ready.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from devops_cli.config.constants import (
    CONST_BRANCH_TYPES,
    CONST_ROADMAP_PRIORITY_VALUES,
    CONST_ROADMAP_STATUS_BLOCKED,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_STAGE_LIMIT
from devops_cli.exceptions import ValidationError
from devops_cli.git.branch_form import branch_name
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine import body_dependencies
from devops_cli.roadmap.store import GitHubState, Item, RoadmapStore, StageRecordKey
from devops_cli.security.sanitizer import redact_text

# ── The filter ────────────────────────────────────────────────────────────────

_FILTER_FAMILIES: Final[tuple[str, ...]] = ("status", "priority", "type", "value", "effort")
# What the job stages without a `--filter`: the Ready P0 and P1 bugs.
_DEFAULT_FILTERS: Final[tuple[str, ...]] = (
    "status=ready",
    "priority=p0-critical",
    "priority=p1-high",
    "type=bug",
)
_NEEDS_SPLIT_LABEL: Final[str] = "needs-split"
# The Status values of an item that someone started or that waits on another item.
_STARTED_STATUSES: Final[frozenset[str]] = frozenset(
    {CONST_ROADMAP_STATUS_IN_PROGRESS, CONST_ROADMAP_STATUS_IN_REVIEW, CONST_ROADMAP_STATUS_BLOCKED}
)
# The words of a title's summary that make the slug of the branch.
_SLUG_WORDS: Final[int] = 6


@dataclass(frozen=True)
class StageFilter:
    """The labels an item must hold: for each family, one of the labels of its alternatives."""

    families: Mapping[str, frozenset[str]]

    def matches(self, item: Item) -> bool:
        """Whether `item` holds a label of every family of the filter."""
        return all(not wanted.isdisjoint(item.labels) for wanted in self.families.values())


def parse_filters(options: Iterable[str]) -> StageFilter:
    """The filter that the `family=value` options give, or the default filter with none.

    A value is the label's name after the family: `priority=p1-high` is the label
    `priority/p1-high`. A family outside the label families, and an option that is not
    `family=value`, raise `ValidationError`.
    """
    texts = MESSAGES.roadmap
    families: dict[str, set[str]] = {}
    for option in tuple(options) or _DEFAULT_FILTERS:
        family, _, value = option.partition("=")
        family, value = family.strip().lower(), value.strip().lower()
        if not family or not value:
            raise ValidationError(texts.stage_filter_form.format(option=option), field="filter")
        if family not in _FILTER_FAMILIES:
            raise ValidationError(
                texts.stage_filter_family.format(
                    family=family, families=", ".join(_FILTER_FAMILIES)
                ),
                field="filter",
            )
        families.setdefault(family, set()).add(f"{family}/{value}")
    return StageFilter({family: frozenset(labels) for family, labels in families.items()})


# ── The branch of an item ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageTarget:
    """An item to stage with the type and the slug of its branch."""

    item: Item
    type_: str
    slug: str

    @property
    def change(self) -> str:
        """The name of the change folder: `<issue>-<slug>`."""
        return f"{self.item.number}-{self.slug}"

    @property
    def branch(self) -> str:
        """The branch: `<type>/<issue>-<slug>`."""
        return branch_name(self.item.number, self.type_, self.slug)


def _commit_type(title: str) -> str | None:
    """The Conventional Commit type of `title`, or None when it has none."""
    head, colon, _ = title.partition(":")
    kind = head.partition("(")[0].removesuffix("!")
    return kind if colon and kind in CONST_BRANCH_TYPES else None


def _slug_of(title: str) -> str:
    """The slug of `title`'s summary: its first words of ASCII letters and digits, lower case,
    joined by hyphens. It is empty when the summary holds no such word."""
    summary = title.partition(":")[2].lower()
    words = "".join(ch if ch.isascii() and ch.isalnum() else " " for ch in summary).split()
    return "-".join(words[:_SLUG_WORDS])


# ── The selection ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LeftOut:
    """An issue the job did not stage, and why. `title` is empty for an issue that is no item."""

    number: int
    reason: str
    title: str = ""


@dataclass(frozen=True)
class StageSelection:
    """The items one run stages, and those it leaves out with their reasons."""

    selected: tuple[StageTarget, ...] = ()
    left_out: tuple[LeftOut, ...] = ()


class _Judge:
    """Decides, for one item, whether the job may stage it. The checks run from the cheapest to
    the dearest: the labels and the text first, then the issues it depends on, then the git
    holders."""

    def __init__(self, store: RoadmapStore, holder_of: Callable[[int], str | None]) -> None:
        self._store = store
        self._holder_of = holder_of

    def reason(self, item: Item, *, named: bool) -> str | None:
        """Why the job leaves `item` out, or None when it may stage it. A person who names the
        item (`--item`) overrules the record of an earlier split."""
        checks = [
            self._started,
            self._needs_split,
            self._author,
            self._title,
            self._dependency,
            self._held,
            self._secret,
        ]
        if not named:
            checks.append(self._recorded_split)
        return next((why for check in checks if (why := check(item)) is not None), None)

    def _started(self, item: Item) -> str | None:
        if item.status in _STARTED_STATUSES:
            return MESSAGES.roadmap.stage_left_started.format(status=item.status)
        return None

    def _needs_split(self, item: Item) -> str | None:
        return (
            MESSAGES.roadmap.stage_left_needs_split if _NEEDS_SPLIT_LABEL in item.labels else None
        )

    def _author(self, item: Item) -> str | None:
        if item.author_association in CONST_ROADMAP_TRUSTED_AUTHORS:
            return None
        texts = MESSAGES.roadmap
        return texts.stage_left_author.format(
            association=item.author_association or texts.refine_author_unknown
        )

    def _title(self, item: Item) -> str | None:
        if _commit_type(item.title) is None:
            return MESSAGES.roadmap.stage_left_title_type
        return None if _slug_of(item.title) else MESSAGES.roadmap.stage_left_title_slug

    def _dependency(self, item: Item) -> str | None:
        open_issues = [
            f"#{number}"
            for number in body_dependencies(item.body)
            if (found := self._store.item(number)) is not None and found.state is GitHubState.OPEN
        ]
        if not open_issues:
            return None
        return MESSAGES.roadmap.stage_left_dependency.format(issues=", ".join(open_issues))

    def _held(self, item: Item) -> str | None:
        return self._holder_of(item.number)

    def _secret(self, item: Item) -> str | None:
        looks_secret = any(redact_text(text) != text for text in (item.title, item.body))
        return MESSAGES.roadmap.stage_left_secret if looks_secret else None

    def _recorded_split(self, item: Item) -> str | None:
        detail = item.job_record.get(StageRecordKey.NEEDS_SPLIT)
        if not detail:
            return None
        return MESSAGES.roadmap.stage_left_recorded_split.format(detail=detail, number=item.number)


def _target_of(item: Item) -> StageTarget:
    """The target of an item whose title gives a branch name (`_Judge._title`)."""
    return StageTarget(item, _commit_type(item.title) or "", _slug_of(item.title))


def _priority_order(item: Item) -> tuple[int, int]:
    """Highest priority first, then the lowest number."""
    values = CONST_ROADMAP_PRIORITY_VALUES
    rank = values.index(item.priority) if item.priority in values else len(values)
    return rank, item.number


def _named_item(judge: _Judge, store: RoadmapStore, number: int) -> StageSelection:
    """The selection of `--item`: the item when it is open and Ready, else why not."""
    texts = MESSAGES.roadmap
    item = store.item(number)
    why: str | None
    if item is None:
        why = texts.stage_left_not_item
    elif item.state is not GitHubState.OPEN:
        why = texts.stage_left_closed
    elif item.status != CONST_ROADMAP_STATUS_READY:
        why = texts.stage_left_not_ready.format(status=item.status or texts.stage_status_none)
    else:
        why = judge.reason(item, named=True)
    if item is not None and why is None:
        return StageSelection(selected=(_target_of(item),))
    return StageSelection(left_out=(LeftOut(number, why or "", item.title if item else ""),))


def select_stageable(
    store: RoadmapStore,
    *,
    filters: StageFilter,
    holder_of: Callable[[int], str | None],
    item_number: int | None = None,
    limit: int = DEFAULT_ROADMAP_STAGE_LIMIT,
) -> StageSelection:
    """The items to stage, up to `limit`, and those the filter names that the job leaves out.

    `holder_of` tells who holds an issue (`worktree_add.issue_holder`), or None. With
    `item_number` the filter and the limit do not apply.
    """
    judge = _Judge(store, holder_of)
    if item_number is not None:
        return _named_item(judge, store, item_number)
    named = sorted(
        (
            item
            for item in store.items()
            if item.state is GitHubState.OPEN and filters.matches(item)
        ),
        key=_priority_order,
    )
    selected: list[StageTarget] = []
    left_out: list[LeftOut] = []
    for item in named:
        if len(selected) >= limit:
            break
        why = judge.reason(item, named=False)
        if why is None:
            selected.append(_target_of(item))
        else:
            left_out.append(LeftOut(item.number, why, item.title))
    return StageSelection(tuple(selected), tuple(left_out))


__all__ = [
    "LeftOut",
    "StageFilter",
    "StageSelection",
    "StageTarget",
    "parse_filters",
    "select_stageable",
]
