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

The dispatcher replaces only the six placeholders, with a regular expression: PromQL and LogQL
hold braces, so `str.format` cannot fill them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
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
PLACEHOLDERS: Final = ("start", "end", "range", "base", "head", "repo")
# The names that a jq program of a fact reads: the window times in Unix seconds and the repository.
PROGRAM_ARGUMENTS: Final = ("start", "end", "repo")
_PLACEHOLDER: Final = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")
_TIME: Final = "%Y-%m-%dT%H:%M:%SZ"
_FACTS: Final = "facts"


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
    none only when that metric has a series in the window."""

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
    )


def _cross_checked(source: Path, catalog: Catalog) -> Catalog:
    """Refuse two facts with one id, an unlisted section and a pair that names no fact."""
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


def window_placeholders(window: ReviewWindow, repo: str) -> dict[str, str]:
    """The value of each placeholder for `window` of `repo`: the UTC times, the length of the
    window in whole seconds, the two commits and the repository as `owner/name`."""
    seconds = int((window.end - window.start).total_seconds())
    return {
        "start": utc_text(window.start),
        "end": utc_text(window.end),
        "range": f"{seconds}s",
        "base": window.base_sha,
        "head": window.head_sha,
        "repo": repo,
    }


def render_query(template: str, values: Mapping[str, str]) -> str:
    """`template` with each of the six placeholders replaced by its value in `values`; every
    other brace stays."""
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)
