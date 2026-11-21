"""The dispatcher of the project review catalog (#4692): one read for each distinct query, the
value and the status of each fact, the disagreements, and the plan of a dry run.

For each fact in the catalog order the dispatcher fills the placeholders of the window, checks
the `requires` conditions and the retention, and reads the query once: the facts on one answer
share the read. A jq program of the fact gives the value of a listing, GitHub or OpenSpec answer,
with `$start` and `$end` (Unix seconds) and `$repo`. A Prometheus or Loki answer gives one sample
(`scalar`) or a row of each sample (`rows`, the largest value first).

| Condition | Status | Request |
| :--- | :--- | :--- |
| A `requires` condition is false | `skipped`, the reason names it | none |
| The window start is older than the retention, less a grace of 1 hour | `expired`, the reason names the retention | none |
| An earlier read of the reader kind got no answer from the network | `error`, the reason of that read | none |
| The read raises a project error | `error`, the first line of the error | sent |
| A query gives no series, and the fact names no `base` metric or that metric has no series in the window | `skipped` | sent |
| A query gives no series, and the `base` metric of the fact has a series in the window | `ok`, no rows or 0 | sent, and the probe of the base |
| A program gives no value | `skipped` | sent |

A missing value is never 0, and a fact that is not `ok` has a null value. A read that gets no
answer from the network (a `ServiceRequestError` with no HTTP status) ends the reads of its reader
kind, so an address that does not answer costs one read and its retries, not one for each fact.
Each other exception stops the run.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from pydantic import JsonValue

from devops_cli.config.settings import Settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.http import ServiceRequestError
from devops_cli.git.operations import git_argv
from devops_cli.lang import MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.prometheus.client import PrometheusContentTypeError
from devops_cli.roadmap.project_review.catalog import (
    Catalog,
    CatalogFact,
    ReaderKind,
    ReaderRules,
    Shape,
    render_query,
    window_placeholders,
)
from devops_cli.roadmap.project_review.data import (
    Collection,
    Disagreement,
    Fact,
    FactStatus,
    ReviewWindow,
)
from devops_cli.roadmap.project_review.readers import (
    PagedSession,
    Reads,
    read_github,
    read_listing,
    read_loki,
    read_prometheus,
    read_runs,
)
from devops_cli.roadmap.stores.listing_snapshot import (
    FileSnapshotStore,
    SnapshotStore,
    changed_listing,
    snapshot_root,
)

_SETTING: Final = "setting:"
_WINDOW: Final = "window:"
_PATH: Final = "path:"
# The readers that read one answer for every fact of their kind, whatever the query says.
_ONE_READ: Final = frozenset({ReaderKind.LISTING, ReaderKind.OPENSPEC})
# A time that the plan of a dry run replaces with the watermark or the start of the window.
_SHOWN_SINCE: Final = datetime(2000, 1, 1, tzinfo=UTC)
_SHOWN_SINCE_TEXT: Final = "2000-01-01T00:00:00Z"
# A read that fails with one of these marks its facts `error`, and the review reads the others.
_READ_ERRORS: Final = (DevOpsCLIError, PrometheusContentTypeError)
# Prometheus and Loki delete a block of samples only when the whole block is past the retention,
# and a `--last` window starts at the whole minute before the time now less its days. So a start
# up to this grace before the retention limit is still read.
_RETENTION_GRACE: Final = timedelta(hours=1)
# The read that tells whether the base metric of a fact has a series in the window.
_PROBE: Final = "group(last_over_time({base}[{range}]))"


def _github_session() -> PagedSession:
    from devops_cli.github.session import get_github_session

    return get_github_session()


@dataclass(frozen=True)
class ReadContext:
    """What the readers of one review read: the checkout, the repository as `owner/name`, the
    window, the settings and the time now. `snapshots` keeps the listing of intake, and `session`
    gives the GitHub session."""

    checkout: Path
    repo: str
    window: ReviewWindow
    settings: Settings
    now: datetime
    snapshots: SnapshotStore | None = None
    session: Callable[[], PagedSession] = _github_session


@dataclass(frozen=True)
class CatalogResult:
    """The facts of the catalog, the pairs that disagree and the reads of the collection."""

    facts: list[Fact]
    disagreements: list[Disagreement]
    collection: Collection


@dataclass
class _Answer:
    """One read: its answer, or the error that it raised."""

    value: Any = None
    error: str | None = None
    text: str | None = field(default=None, repr=False)

    def json_text(self) -> str:
        """The answer as JSON text, made once for every program that reads it."""
        if self.text is None:
            self.text = json.dumps(self.value)
        return self.text


def _setting(settings: Settings, dotted: str) -> Any:
    value: Any = settings
    for part in dotted.split("."):
        value = getattr(value, part, None)
    return value


def _unmet(requires: Sequence[str], context: ReadContext) -> str | None:
    """The reason of the first condition that does not hold, or None."""
    texts = MESSAGES.roadmap
    for condition in requires:
        if condition.startswith(_SETTING):
            name = condition.removeprefix(_SETTING)
            if not _setting(context.settings, name):
                return texts.review_unset_setting.format(setting=name)
        elif condition.startswith(_WINDOW):
            kind = condition.removeprefix(_WINDOW)
            if context.window.kind != kind:
                return texts.review_other_window.format(kind=context.window.kind, needed=kind)
        elif condition.startswith(_PATH):
            path = condition.removeprefix(_PATH)
            if not (context.checkout / path).exists():
                return texts.review_no_path.format(path=path)
    return None


def _expired(days: int | None, context: ReadContext) -> str | None:
    """The reason when the window starts before the retention of `days` days, or None."""
    if days is None:
        return None
    limit = context.now - timedelta(days=days)
    if context.window.start >= limit - _RETENTION_GRACE:
        return None
    return MESSAGES.roadmap.review_past_retention.format(
        days=days, start=context.window.start.isoformat(), limit=limit.isoformat()
    )


def _read(fact: CatalogFact, query: str, context: ReadContext, reads: Reads) -> Any:
    """The answer of the reader of `fact` to `query`."""
    window = context.window
    match fact.reader:
        case ReaderKind.LISTING:
            snapshots = context.snapshots or FileSnapshotStore(snapshot_root())
            return read_listing(
                context.session(), context.repo, snapshots, reads, start=window.start
            )
        case ReaderKind.GITHUB:
            return read_github(
                context.session(), query, window.start, reads, newest_first=fact.newest_first
            )
        case ReaderKind.GITHUB_RUNS:
            return read_runs(context.session(), query, window.start, window.end, reads)
        case ReaderKind.PROMETHEUS:
            from devops_cli.http.egress import configured_level
            from devops_cli.http.urls import service_base_url

            base = service_base_url(str(context.settings.prometheus.url), "prometheus.url")
            level = configured_level(context.settings.ai)
            return read_prometheus(base, level, query, window.end, reads)
        case ReaderKind.LOKI:
            return read_loki(str(context.settings.loki.url), query, window.end, reads)
        case ReaderKind.OPENSPEC:
            from devops_cli.roadmap.project_review.openspec_read import read_openspec

            return read_openspec(context.checkout, window.base_sha, window.head_sha, reads)


def _number(text: str) -> float | None:
    value = float(text)
    return value if math.isfinite(value) else None


def _vector_value(
    fact: CatalogFact, result: PrometheusQueryResult
) -> tuple[JsonValue, int | None, str | None]:
    """The value, the sample size and the reason of a fact with no value, from a vector."""
    texts = MESSAGES.roadmap
    if not result.series:
        return None, None, texts.review_no_series
    if fact.shape is Shape.SCALAR:
        if len(result.series) > 1:
            return None, None, texts.review_many_series.format(count=len(result.series))
        value = _number(result.series[0].value)
        return (value, None, None) if value is not None else (None, None, texts.review_not_number)
    rows: list[dict[str, JsonValue]] = []
    for series in result.series:
        value = _number(series.value)
        if value is not None:
            labels = {key: text for key, text in series.labels.items() if key != "__name__"}
            rows.append({"labels": dict(labels), "value": value})
    rows.sort(key=lambda row: -float(str(row["value"])))
    return list(rows), len(rows), None


def _program_value(
    fact: CatalogFact, answer: _Answer, arguments: Mapping[str, Any]
) -> tuple[JsonValue, int | None, str | None]:
    """The value and the sample size that the jq programs of `fact` give."""
    import jq

    def run(program: str) -> list[Any]:
        return list(jq.compile(program, args=dict(arguments)).input_text(answer.json_text()).all())

    found = run(fact.value or ".")
    if not found:
        return None, None, MESSAGES.roadmap.review_no_value
    value: JsonValue = found[0] if len(found) == 1 else found
    sizes = run(fact.n) if fact.n else []
    n = sizes[0] if len(sizes) == 1 and isinstance(sizes[0], int) else None
    return value, n, None


def _fact(
    fact: CatalogFact,
    query: str,
    *,
    status: FactStatus = FactStatus.OK,
    value: JsonValue = None,
    n: int | None = None,
    reason: str = "",
) -> Fact:
    return Fact(
        id=fact.id,
        section=fact.section,
        value=value if status is FactStatus.OK else None,
        unit=fact.unit,
        n=n if status is FactStatus.OK else None,
        source=fact.reader,
        query=query,
        definition=fact.definition,
        read_at=datetime.now(UTC),
        status=status,
        reason=reason,
    )


def _numeric(fact: Fact | None) -> float | None:
    if fact is None or fact.status is not FactStatus.OK:
        return None
    value = fact.value
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def disagreements(catalog: Catalog, facts: Sequence[Fact]) -> list[Disagreement]:
    """Each pair of the catalog whose two `ok` numbers differ by more than its tolerance."""
    by_id = {fact.id: fact for fact in facts}
    found: list[Disagreement] = []
    for pair in catalog.disagreements:
        left, right = _numeric(by_id.get(pair.left)), _numeric(by_id.get(pair.right))
        if left is None or right is None:
            continue
        largest = max(abs(left), abs(right))
        difference = abs(left - right) / largest if largest else 0.0
        if difference > pair.tolerance:
            found.append(
                Disagreement(
                    id=pair.id,
                    left=pair.left,
                    right=pair.right,
                    left_value=left,
                    right_value=right,
                    difference=round(difference, 4),
                    tolerance=pair.tolerance,
                    definition=pair.definition,
                )
            )
    return found


def _first_line(error: BaseException) -> str:
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


@dataclass
class _Answers:
    """The answer of each distinct read of one review, and the reason of each reader kind whose
    read got no answer from the network."""

    context: ReadContext
    reads: Reads
    held: dict[tuple[str, ...], _Answer] = field(default_factory=dict)
    down: dict[ReaderKind, str] = field(default_factory=dict)

    def get(self, fact: CatalogFact, query: str) -> _Answer:
        """The answer of the reader of `fact` to `query`, read once for each distinct query."""
        key = (
            (fact.reader,)
            if fact.reader in _ONE_READ
            else (fact.reader, query, str(fact.newest_first))
        )
        if key not in self.held:
            self.held[key] = self._read(fact, query)
        return self.held[key]

    def _read(self, fact: CatalogFact, query: str) -> _Answer:
        if (reason := self.down.get(fact.reader)) is not None:
            return _Answer(error=reason)
        try:
            return _Answer(_read(fact, query, self.context, self.reads))
        except _READ_ERRORS as error:
            reason = _first_line(error)
            if isinstance(error, ServiceRequestError) and error.status_code is None:
                self.down[fact.reader] = reason
            return _Answer(error=reason)


def _probe(fact: CatalogFact, values: Mapping[str, str]) -> str:
    """The read that tells whether the base metric of `fact` has a series in the window."""
    return _PROBE.format(base=render_query(str(fact.base), values), range=values["range"])


def _no_series(fact: CatalogFact, query: str, values: Mapping[str, str], answers: _Answers) -> Fact:
    """`fact` when its answer has no series: none, as no rows or 0, when its base metric has a
    series in the window; else `skipped`, because a missing metric is never 0."""
    probe = answers.get(fact, _probe(fact, values))
    if probe.error is not None:
        return _fact(fact, query, status=FactStatus.ERROR, reason=probe.error)
    if not probe.value.series:
        reason = MESSAGES.roadmap.review_no_base_series.format(
            base=render_query(str(fact.base), values)
        )
        return _fact(fact, query, status=FactStatus.SKIPPED, reason=reason)
    if fact.shape is Shape.ROWS:
        return _fact(fact, query, value=[], n=0)
    return _fact(fact, query, value=0.0)


def _read_fact(
    fact: CatalogFact,
    query: str,
    values: Mapping[str, str],
    arguments: Mapping[str, Any],
    answers: _Answers,
) -> Fact:
    """`fact` from the answer of its query."""
    answer = answers.get(fact, query)
    if answer.error is not None:
        return _fact(fact, query, status=FactStatus.ERROR, reason=answer.error)
    if fact.reader in (ReaderKind.PROMETHEUS, ReaderKind.LOKI):
        if not answer.value.series and fact.base is not None:
            return _no_series(fact, query, values, answers)
        value, n, empty = _vector_value(fact, answer.value)
    else:
        try:
            value, n, empty = _program_value(fact, answer, arguments)
        except ValueError as error:
            return _fact(fact, query, status=FactStatus.ERROR, reason=_first_line(error))
    if empty is not None:
        return _fact(fact, query, status=FactStatus.SKIPPED, reason=empty)
    return _fact(fact, query, value=value, n=n)


def read_catalog(catalog: Catalog, context: ReadContext) -> CatalogResult:
    """Each fact of `catalog` for the window of `context`, in the catalog order."""
    started = time.monotonic()
    values = window_placeholders(context.window, context.repo)
    arguments = {
        "start": int(context.window.start.timestamp()),
        "end": int(context.window.end.timestamp()),
        "repo": context.repo,
    }
    answers = _Answers(context, Reads())
    facts: list[Fact] = []
    for fact in catalog.facts:
        rules = catalog.rules(fact)
        query = render_query(fact.query, values)
        if (reason := _unmet(rules.requires, context)) is not None:
            facts.append(_fact(fact, query, status=FactStatus.SKIPPED, reason=reason))
        elif (reason := _expired(rules.retention_days, context)) is not None:
            facts.append(_fact(fact, query, status=FactStatus.EXPIRED, reason=reason))
        else:
            facts.append(_read_fact(fact, query, values, arguments, answers))
    collection = Collection(
        reads=dict(answers.reads.counts), seconds=round(time.monotonic() - started, 1)
    )
    return CatalogResult(facts, disagreements(catalog, facts), collection)


def _condition(requires: Sequence[str]) -> str:
    texts = MESSAGES.roadmap
    shown = []
    for condition in requires:
        kind, _, name = condition.partition(":")
        shown.append(texts.review_plan_condition[kind].format(name=name))
    return " and ".join(shown)


def plan_catalog(
    catalog: Catalog, values: Mapping[str, str], checkout: Path
) -> list[PlannedRequest]:
    """The reads that a run of `catalog` sends, shared reads first, then each fact with its
    reader kind and its rendered query. A value that only a read gives is a named placeholder."""
    from devops_cli.roadmap.project_review.openspec_read import (
        archived_args,
        batch_args,
        requirement_args,
        show_args,
    )

    texts = MESSAGES.roadmap.review_placeholders
    kinds = {fact.reader for fact in catalog.facts}
    repo, base, head = values["repo"], values["base"], values["head"]
    shared: list[PlannedRequest] = []
    if ReaderKind.LISTING in kinds:
        shown = changed_listing(_SHOWN_SINCE)
        shared.extend(
            PlannedRequest(
                method="GET",
                target=f"repos/{repo}/issues?{shown.replace(_SHOWN_SINCE_TEXT, since)}",
                condition=condition,
            )
            for since, condition in (
                (texts["watermark"], MESSAGES.roadmap.review_plan_snapshot),
                (values["start"], MESSAGES.roadmap.review_plan_no_snapshot),
            )
        )
    if ReaderKind.OPENSPEC in kinds:
        when = _condition(catalog.readers.get(ReaderKind.OPENSPEC, ReaderRules()).requires)
        steps = [archived_args(base, head), batch_args()]
        totals = [requirement_args(base), requirement_args(head)]
        shared.extend(
            [
                *(
                    PlannedRequest(
                        "git", str(checkout), tuple(git_argv(checkout, *args)), condition=when
                    )
                    for args in steps
                ),
                PlannedRequest(
                    "openspec",
                    texts["change"],
                    ("openspec", *show_args(texts["change"])),
                    condition=when,
                    repeat=MESSAGES.roadmap.review_plan_each_change,
                ),
                *(
                    PlannedRequest(
                        "git", str(checkout), tuple(git_argv(checkout, *args)), condition=when
                    )
                    for args in totals
                ),
            ]
        )
    each: list[PlannedRequest] = []
    for fact in catalog.facts:
        condition = _condition(catalog.rules(fact).requires)
        each.append(
            PlannedRequest(
                method=fact.reader,
                target=f"{fact.id}: {render_query(fact.query, values)}",
                condition=condition,
                repeat=(
                    MESSAGES.roadmap.review_plan_each_slice
                    if fact.reader is ReaderKind.GITHUB_RUNS
                    else ""
                ),
            )
        )
        if fact.base is not None:
            empty = MESSAGES.roadmap.review_plan_probe.format(fact=fact.id)
            each.append(
                PlannedRequest(
                    method=fact.reader,
                    target=f"{fact.id}: {_probe(fact, values)}",
                    condition=" and ".join(part for part in (condition, empty) if part),
                )
            )
    return [*shared, *each]
