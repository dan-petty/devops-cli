"""A roadmap store whose writes fail as gh calls do part-way through a job's run (#740).

Any gh write can fail: a 502, a timeout, a secondary rate limit. It fails before GitHub applies
it, or after, when GitHub applied it and the call still reports a failure. `StoppingStore`
fails one write of a run, either way. GitHub takes a field write as two calls, the job record
first (with the value and any marks given with it), then the milestone or the board field. The
in-memory store makes both in one step, so with `two_calls` the wrapper makes them as two
writes, `record` and `field`, either of which can fail.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import Item, ItemField, JobMark, RoadmapStore

# The store's writes, any of which a gh call can fail part-way through a run, and the two
# calls GitHub takes a field write as.
WRITES = frozenset(
    {
        "create_release",
        "close_release",
        "create_branch",
        "set_field",
        "set_marks",
        "comment",
        "set_run_record",
    }
)
RECORD, FIELD = "record", "field"


@dataclass(frozen=True)
class Fault:
    """The write that fails: the `at`-th, counted from 1, of the writes named `write` on issue
    `item` (any write, on any item, when None); none when `at` is 0. With `applied`, it applies
    and then reports the failure."""

    at: int = 0
    applied: bool = False
    write: str | None = None
    item: int | None = None


def _number(args: tuple[object, ...]) -> int | None:
    """The issue a write touches: its Item's number, or the number it is given."""
    first = args[0] if args else None
    if isinstance(first, Item):
        return first.number
    return first if isinstance(first, int) else None


@dataclass
class StoppingStore:
    """The store, with the write `fault` names failing once, as a gh call that fails part-way
    through a run. `writes` names every write made or tried, in order."""

    store: InMemoryRoadmapStore
    fault: Fault = Fault()
    two_calls: bool = True
    writes: list[str] = field(default_factory=list)
    _counted: int = 0

    def __getattr__(self, name: str) -> Any:
        found = getattr(self.store, name)
        if name not in WRITES:
            return found
        if name == "set_field" and self.two_calls:
            return self._set_field

        def write(*args: Any, **kwargs: Any) -> object:
            return self._write(name, _number(args), lambda: found(*args, **kwargs))

        return write

    def as_store(self) -> RoadmapStore:
        """The wrapper, as the job takes a store."""
        return cast(RoadmapStore, self)

    def _set_field(
        self,
        item: Item,
        item_field: ItemField,
        value: str | None,
        *,
        marks: Mapping[JobMark, str | None] | None = None,
    ) -> None:
        """GitHub's two calls: the job record with the value and `marks`, then the field."""
        recorded = {item_field: value}
        self._write(
            RECORD,
            item.number,
            lambda: self.store.set_marks(item, marks or {}, recorded=recorded),
        )
        self._write(
            FIELD, item.number, lambda: self.store.set_field(item, item_field, value, marks=marks)
        )

    def _write(self, name: str, number: int | None, apply: Callable[[], object]) -> object:
        self.writes.append(name)
        fault = self.fault
        counted = fault.write in (None, name) and fault.item in (None, number)
        self._counted += counted
        failing = counted and self._counted == fault.at
        if failing and not fault.applied:
            raise GitHubOperationError("HTTP 502", operation="roadmap.write")
        done = apply()
        if failing:
            raise GitHubOperationError(
                "HTTP 502 after the write applied", operation="roadmap.write"
            )
        return done
