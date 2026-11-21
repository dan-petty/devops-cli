"""The fact catalog of the project review (#4692): `catalog.yaml`, its JSON Schema, and the
placeholders of a window.

The catalog names each fact that a reader other than git gives: its id, its reader kind, its
section, its query template, its unit and its definition, with optional `requires` conditions and
a retention. It also names the sections, the retention of each reader kind and the pairs of facts
that must agree. A new fact is data and needs no code.

`catalog.schema.json` (Draft 2020-12) is the one definition of the form, and `jsonschema`
validates each catalog against it before any read. JSON Schema cannot compare two values of one
document, so the loader also refuses two facts with one id, a section that `sections` does not
list and a disagreement that names an unknown fact. Each refusal raises `RoadmapReviewError` with
a message that names the fact, or its index when it has no id, and the field. The message does
not quote the refused value.

The schema refuses a query of a Service metric (`devops_cli_service_`) with no `{repo}`, and the
loader also refuses each selector of a Service metric, in `query` or `base`, whose own braces hold
no matcher `repo="{repo}"`: a ratio whose numerator has no such matcher adds the repositories
together.

A review gives no name of a workload outside the project namespaces (#6615). The loader refuses a
`rows` fact whose query names `namespace` or `pod` in a `by (...)` or `on (...)` clause and holds
no positive namespace matcher, `namespace="..."` or `namespace=~"..."`, such as
`namespace=~"{namespaces}"`, in the query and in its `base`: the probe of the base tells whether an
empty answer is "none", so a base of all namespaces makes an empty answer of the project `ok`. A
negative matcher still reads every other namespace, so it does not scope the fact. A `scalar` fact
is one number with no label, so the rule does not apply to it. The rule reads only the clauses;
the dispatcher also checks the labels of each row that a `rows` fact gives.

The base metric of a fact, the leading metric name of its `base` selector, is a metric of its
query (#6612): the loader refuses a fact whose query does not name the base metric as a whole
metric name, unless the fact gives `base_reason`, a text that says why its base is another metric.
A probe of another metric makes an empty answer `ok` for a window in which the queried metric did
not exist.

The dispatcher replaces only the eight placeholders, with a regular expression: PromQL and LogQL
hold braces, so `str.format` cannot fill them. `{name_slug}` is the slug of the repository name
in the Job names of the Service (`RepoRef.name_slug`), because kube-state-metrics exports no Job
label. `{namespaces}` is the project namespaces of the setting `roadmap.project_review.namespaces`
joined with `|`, the value of a matcher `namespace=~"{namespaces}"` (#6615).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

import yaml

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.project_review.data import ReviewWindow

CATALOG_FILE: Final[Path] = Path(__file__).with_name("catalog.yaml")
SCHEMA_FILE: Final[Path] = Path(__file__).with_name("catalog.schema.json")
PLACEHOLDERS: Final = ("start", "end", "range", "base", "head", "repo", "name_slug", "namespaces")
# The names that a jq program of a fact reads: the window times in Unix seconds and the repository.
PROGRAM_ARGUMENTS: Final = ("start", "end", "repo")
_PLACEHOLDER: Final = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")
_TIME: Final = "%Y-%m-%dT%H:%M:%SZ"
_FACTS: Final = "facts"
# A metric of the Service: its value is the value of one repository only with `repo="{repo}"`.
_SERVICE_METRIC: Final = re.compile(r"\bdevops_cli_service_[a-z_]+")
_REPO_MATCHER: Final = re.compile(r'(?:^|,)\s*repo\s*=\s*"\{repo\}"\s*(?:,|$)')
# The labels that name a workload, the label list of a `by (...)` or `on (...)` clause, and a
# positive matcher of the label namespace: `namespace!="..."` does not match.
_WORKLOAD_LABELS: Final = frozenset({"namespace", "pod"})
_GROUPING: Final = re.compile(r"\b(?:by|on)\s*\(([^)]*)\)")
_NAMESPACE_MATCHER: Final = re.compile(r'\bnamespace\s*=~?\s*"')
# The leading metric name of a selector, and the characters of a metric name.
_METRIC_NAME: Final = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:]*")
_NAME_CHAR: Final = "[a-zA-Z0-9_:]"


class ReaderKind(StrEnum):
    """A reader of the dispatcher, and the source that it reads."""

    LISTING = "listing"
    GITHUB = "github"
    GITHUB_RUNS = "github_runs"
    PROMETHEUS = "prometheus"
    LOKI = "loki"
    OPENSPEC = "openspec"


class Shape(StrEnum):
    """How an answer of Prometheus or Loki gives its value: one sample, or a row of each sample."""

    SCALAR = "scalar"
    ROWS = "rows"


@dataclass(frozen=True)
class Section:
    """A section of the review."""

    id: str
    title: str


@dataclass(frozen=True)
class ReaderRules:
    """The retention in days and the conditions of a reader kind, or of one fact."""

    retention_days: int | None = None
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogFact:
    """One fact of the catalog. `value` and `n` are jq programs over the answer of the read.
    `base` is a selector of the metric that a `prometheus` fact reads: an answer with no series is
    none only when that metric has a series in the time scope of the query, the window for a query
    that holds `{range}`, else the window end. Its metric is a metric of the query, else
    `base_reason` says why the base is another metric."""

    id: str
    reader: ReaderKind
    section: str
    query: str
    unit: str
    definition: str
    value: str | None = None
    n: str | None = None
    shape: Shape | None = None
    requires: tuple[str, ...] = ()
    retention_days: int | None = None
    newest_first: str | None = None
    base: str | None = None
    base_reason: str | None = None


@dataclass(frozen=True)
class Agreement:
    """Two facts that must agree within `tolerance`, a relative difference."""

    id: str
    left: str
    right: str
    tolerance: float
    definition: str


@dataclass(frozen=True)
class Catalog:
    """The sections, the rules of each reader kind, the facts and the pairs that must agree."""

    sections: tuple[Section, ...]
    readers: Mapping[str, ReaderRules]
    facts: tuple[CatalogFact, ...]
    disagreements: tuple[Agreement, ...]

    def rules(self, fact: CatalogFact) -> ReaderRules:
        """The retention and the conditions of `fact`: its own retention over the one of its
        reader kind, and the conditions of both."""
        kind = self.readers.get(fact.reader, ReaderRules())
        retention = fact.retention_days if fact.retention_days is not None else kind.retention_days
        return ReaderRules(retention, (*kind.requires, *fact.requires))


def _days(text: str | None) -> int | None:
    return None if text is None else int(text.removesuffix("d"))


def _subject(document: Any, path: Sequence[Any]) -> str:
    """The fact at `path` by its id, or by its index when it has no id; else the path itself."""
    if len(path) >= 2 and path[0] == _FACTS and isinstance(path[1], int):
        fact = document[_FACTS][path[1]]
        found = fact.get("id") if isinstance(fact, Mapping) else None
        if isinstance(found, str):
            return MESSAGES.roadmap.review_catalog_fact.format(id=found)
        return MESSAGES.roadmap.review_catalog_fact_index.format(index=path[1] + 1)
    return "/".join(str(part) for part in path) or MESSAGES.roadmap.review_catalog_root


def _schema_refusal(source: Path, document: Any, error: Any) -> RoadmapReviewError:
    """The refusal of the first schema error, with no quote of the refused value."""
    texts = MESSAGES.roadmap
    path = list(error.absolute_path)
    subject = _subject(document, path)
    if error.validator == "required":
        absent = [name for name in error.validator_value if name not in error.instance]
        text = texts.review_catalog_missing.format(subject=subject, field=absent[0])
    elif error.validator == "additionalProperties":
        named = error.schema.get("properties", {})
        extra = sorted(name for name in error.instance if name not in named)
        text = texts.review_catalog_unknown_field.format(subject=subject, field=extra[0])
    else:
        field = next((part for part in reversed(path) if isinstance(part, str)), "")
        rule = error.schema.get("description") or texts.review_catalog_see_schema
        text = texts.review_catalog_bad_field.format(subject=subject, field=field, rule=rule)
    return RoadmapReviewError(texts.review_catalog_refused.format(path=source, reason=text))


def _validate(source: Path, document: Any) -> None:
    """Validate `document` against the schema, raising on the first error."""
    # jsonschema ships no type information.
    from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
    from jsonschema.exceptions import best_match  # type: ignore[import-untyped]

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    error = best_match(Draft202012Validator(schema).iter_errors(document))
    if error is not None:
        raise _schema_refusal(source, document, error)


def _check_programs(source: Path, fact: CatalogFact) -> None:
    """Refuse a jq program of `fact` that does not compile."""
    import jq

    for field, program in (("value", fact.value), ("n", fact.n)):
        if program is None:
            continue
        try:
            jq.compile(program, args=dict.fromkeys(PROGRAM_ARGUMENTS, ""))
        except ValueError as error:
            reason = MESSAGES.roadmap.review_catalog_bad_program.format(
                subject=MESSAGES.roadmap.review_catalog_fact.format(id=fact.id),
                field=field,
                error=str(error).splitlines()[0],
            )
            raise RoadmapReviewError(
                MESSAGES.roadmap.review_catalog_refused.format(path=source, reason=reason)
            ) from error


def _matchers(query: str, at: int) -> str | None:
    """The label matchers in the braces at `at` (after spaces), or None when no braces are there.
    A brace in a quoted label value does not end the selector."""
    at = len(query) - len(query[at:].lstrip())
    if not query.startswith("{", at):
        return None
    quoted = escaped = False
    for index in range(at + 1, len(query)):
        char = query[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = quoted
        elif char == '"':
            quoted = not quoted
        elif char == "}" and not quoted:
            return query[at + 1 : index]
    return None


def unscoped_service_metric(query: str) -> str | None:
    """The first Service metric of `query` whose own selector holds no `repo="{repo}"`, or None."""
    for found in _SERVICE_METRIC.finditer(query):
        matchers = _matchers(query, found.end())
        if matchers is None or not _REPO_MATCHER.search(matchers):
            return found.group()
    return None


def unscoped_workload_metric(query: str, base: str | None = None) -> tuple[str, str] | None:
    """The field, `query` or `base`, that holds no positive namespace matcher, and the first label
    `namespace` or `pod` that a `by (...)` or `on (...)` clause of `query` names; or None. The
    probe of `base` tells whether an empty answer of `query` is "none", so it reads the same
    namespaces."""
    labels = (
        label.strip()
        for clause in _GROUPING.finditer(query)
        for label in clause.group(1).split(",")
    )
    label = next((label for label in labels if label in _WORKLOAD_LABELS), None)
    if label is None:
        return None
    for field, text in (("query", query), ("base", base)):
        if text is not None and not _NAMESPACE_MATCHER.search(text):
            return field, label
    return None


def unqueried_base(query: str, base: str) -> str | None:
    """The base metric, the leading metric name of `base`, when `query` does not name it as a
    whole metric name; else None. A name inside a longer name, such as `x_total_bucket` for
    `x_total`, does not count."""
    found = _METRIC_NAME.match(base)
    metric = found.group() if found else base
    whole = re.compile(f"(?<!{_NAME_CHAR}){re.escape(metric)}(?!{_NAME_CHAR})")
    return None if whole.search(query) else metric


def _fact(entry: Mapping[str, Any]) -> CatalogFact:
    shape = entry.get("shape")
    return CatalogFact(
        id=entry["id"],
        reader=ReaderKind(entry["reader"]),
        section=entry["section"],
        query=entry["query"],
        unit=entry["unit"],
        definition=entry["definition"],
        value=entry.get("value"),
        n=entry.get("n"),
        shape=None if shape is None else Shape(shape),
        requires=tuple(entry.get("requires", ())),
        retention_days=_days(entry.get("retention")),
        newest_first=entry.get("newest_first"),
        base=entry.get("base"),
        base_reason=entry.get("base_reason"),
    )


def _scope_refusal(fact: CatalogFact) -> str | None:
    """The reason to refuse `fact` for its scope, or None: a Service metric with no repository
    matcher, or a `rows` fact that names the workloads of all namespaces."""
    texts = MESSAGES.roadmap
    subject = texts.review_catalog_fact.format(id=fact.id)
    for field, text in (("query", fact.query), ("base", fact.base)):
        if text is not None and (metric := unscoped_service_metric(text)) is not None:
            return texts.review_catalog_unscoped_metric.format(
                subject=subject, field=field, metric=metric
            )
    if fact.shape is Shape.ROWS and (found := unscoped_workload_metric(fact.query, fact.base)):
        field, label = found
        return texts.review_catalog_unscoped_workload.format(
            subject=subject, field=field, label=label
        )
    return None


def _base_refusal(fact: CatalogFact) -> str | None:
    """The reason to refuse `fact` when its base metric is not a metric of its query and the fact
    gives no `base_reason`, or None."""
    if fact.base is None or fact.base_reason is not None:
        return None
    if (metric := unqueried_base(fact.query, fact.base)) is None:
        return None
    return MESSAGES.roadmap.review_catalog_base_not_queried.format(
        subject=MESSAGES.roadmap.review_catalog_fact.format(id=fact.id), metric=metric
    )


def _cross_checked(source: Path, catalog: Catalog) -> Catalog:
    """Refuse two facts with one id, an unlisted section, a pair that names no fact, a Service
    metric of no repository, a `rows` fact of the workloads of all namespaces and a base metric
    that the query does not read."""
    texts = MESSAGES.roadmap
    sections = {section.id for section in catalog.sections}
    seen: set[str] = set()
    for fact in catalog.facts:
        subject = texts.review_catalog_fact.format(id=fact.id)
        if fact.id in seen:
            reason = texts.review_catalog_duplicate.format(subject=subject)
        elif fact.section not in sections:
            reason = texts.review_catalog_unknown_section.format(
                subject=subject, section=fact.section
            )
        else:
            seen.add(fact.id)
            continue
        raise RoadmapReviewError(texts.review_catalog_refused.format(path=source, reason=reason))
    for pair in catalog.disagreements:
        for named in (pair.left, pair.right):
            if named not in seen:
                reason = texts.review_catalog_unknown_fact.format(pair=pair.id, fact=named)
                raise RoadmapReviewError(
                    texts.review_catalog_refused.format(path=source, reason=reason)
                )
    for fact in catalog.facts:
        _check_programs(source, fact)
        if (refusal := _scope_refusal(fact) or _base_refusal(fact)) is not None:
            raise RoadmapReviewError(
                texts.review_catalog_refused.format(path=source, reason=refusal)
            )
    return catalog


def load_catalog(path: Path = CATALOG_FILE) -> Catalog:
    """The catalog at `path`, validated against its schema and its cross references."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        reason = str(error).splitlines()[0] if str(error) else type(error).__name__
        raise RoadmapReviewError(
            MESSAGES.roadmap.review_catalog_refused.format(path=path, reason=reason)
        ) from error
    _validate(path, document)
    catalog = Catalog(
        sections=tuple(Section(**entry) for entry in document["sections"]),
        readers={
            kind: ReaderRules(_days(rules.get("retention")), tuple(rules.get("requires", ())))
            for kind, rules in document["readers"].items()
        },
        facts=tuple(_fact(entry) for entry in document[_FACTS]),
        disagreements=tuple(Agreement(**entry) for entry in document["disagreements"]),
    )
    return _cross_checked(path, catalog)


def utc_text(moment: datetime) -> str:
    """`moment` in UTC, as `2026-11-11T14:51:23Z`."""
    return moment.astimezone(UTC).strftime(_TIME)


def namespaces_value(namespaces: Iterable[str]) -> str:
    """The value of `{namespaces}`: the project namespaces joined with `|`, the alternation of a
    matcher `namespace=~"{namespaces}"`."""
    return "|".join(namespaces)


def window_placeholders(
    window: ReviewWindow, repo: str, namespaces: Iterable[str]
) -> dict[str, str]:
    """The value of each placeholder for `window` of `repo`: the UTC times, the length of the
    window in whole seconds, the two commits, the repository as `owner/name`, the slug of its
    name in the Job names of the Service, and the project `namespaces` joined with `|`."""
    from devops_cli.github.repo_ref import RepoRef

    seconds = int((window.end - window.start).total_seconds())
    return {
        "start": utc_text(window.start),
        "end": utc_text(window.end),
        "range": f"{seconds}s",
        "base": window.base_sha,
        "head": window.head_sha,
        "repo": repo,
        "name_slug": RepoRef(repo).name_slug,
        "namespaces": namespaces_value(namespaces),
    }


def render_query(template: str, values: Mapping[str, str]) -> str:
    """`template` with each of the eight placeholders replaced by its value in `values`; every
    other brace stays."""
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)
