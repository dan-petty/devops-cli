"""A Loki fake that holds log streams and answers the LogQL metric instant queries of devops-cli
(#5556).

`LokiFake` holds streams: a label set and its lines, each with an age. `serve` puts it on the HTTP
fake, where it answers `/loki/api/v1/query` as Loki does: a vector for a query that it can
evaluate, and HTTP 400 with the text of the error for a query that it cannot parse or whose
pipeline leaves an error label. Loki refuses such a metric query, for example a plain line after
`| json` with no `drop __error__` (Loki, 2026-11-13: `pipeline error: 'JSONParserErr'`).

The fake evaluates the subset of LogQL that `roadmap/job_grade_report.py` sends, and refuses each
other form:

- a stream selector with `=`, `!=`, `=~` and `!~`, where a missing label is the empty value;
- the line filters `|=`, `!=`, `|~` and `!~`;
- `| json` with or without fields, `| drop`, `| regexp`, `| unwrap`, and the label filters `=`,
  `!=`, `=~` and `!~`;
- `| line_format` with the templates `{{.<label>}}` and `{{ or .<label> __line__ }}`;
- `sum by (...) (count_over_time(... [<range>]))`, `sum by (...) (sum_over_time(... [<range>]))`,
  and `quantile_over_time(<q>, ... [<range>]) by (...)` and `max_over_time(... [<range>]) by (...)`.

A regular expression is fully anchored in a stream selector and a label filter, and unanchored in a
line filter and in `regexp`, as in Loki. A name of `regexp` that the stream has gets the suffix
`_extracted`, and a line that `regexp` does not match keeps its labels and counts. A line counts in a range when its age is less than the
range. A real Loki needs a container that the test run does not start, and no maintained Python
package evaluates LogQL.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

import httpx2

if TYPE_CHECKING:
    from tests.support.fakes.http import WebFake

QUERY_PATH: Final = "/loki/api/v1/query"
# The time of each answer: an instant query gives the value at the time of the query.
_ANSWER_TIME: Final = 1794528000
_RANGE_UNITS: Final = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_STRING: Final = r'(?:"(?:[^"\\]|\\.)*"|`[^`]*`)'
_SELECTOR: Final = re.compile(r"\s*\{(?P<body>[^}]*)\}")
_MATCHER: Final = re.compile(rf"\s*(?P<name>\w+)\s*(?P<op>=~|!~|!=|=)\s*(?P<value>{_STRING})\s*,?")
_NAMES: Final = r"\w+(?:\s*,\s*\w+)*"
_STAGES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("line", re.compile(rf"\s*(?P<op>\|=|!=|\|~|!~)\s*(?P<arg>{_STRING})")),
    ("json", re.compile(rf"\s*\|\s*json(?:\s+(?P<arg>{_NAMES}))?(?=\s*(?:[|!]|$))")),
    ("drop", re.compile(rf"\s*\|\s*drop\s+(?P<arg>{_NAMES})")),
    ("line_format", re.compile(rf"\s*\|\s*line_format\s+(?P<arg>{_STRING})")),
    ("regexp", re.compile(rf"\s*\|\s*regexp\s+(?P<arg>{_STRING})")),
    ("unwrap", re.compile(r"\s*\|\s*unwrap\s+(?P<arg>\w+)")),
    ("label", re.compile(rf"\s*\|\s*(?P<name>\w+)\s*(?P<op>=~|!~|!=|=)\s*(?P<arg>{_STRING})")),
)
_SUM_BY: Final = re.compile(
    r"sum by \((?P<by>[^)]*)\) \((?P<fn>count_over_time|sum_over_time)\("
    r"(?P<log>.+) \[(?P<range>\d+[smhd])\]\)\)",
    re.DOTALL,
)
_BY_AFTER: Final = re.compile(
    r"(?P<fn>quantile_over_time|max_over_time)\((?:(?P<q>[0-9.]+), )?"
    r"(?P<log>.+) \[(?P<range>\d+[smhd])\]\) by \((?P<by>[^)]*)\)",
    re.DOTALL,
)
_FIELD_TEMPLATE: Final = re.compile(r"\{\{\s*\.(\w+)\s*\}\}")
_OR_LINE_TEMPLATE: Final = re.compile(r"\{\{\s*or\s+\.(\w+)\s+__line__\s*\}\}")
_ERROR: Final = "__error__"


class LogQLError(Exception):
    """A query that Loki refuses with HTTP 400: a parse error or a pipeline error."""


@dataclass(frozen=True)
class LokiLine:
    """One line of a stream, `age` before the time of the query."""

    text: str
    age: timedelta = timedelta(0)


@dataclass(frozen=True)
class _Stream:
    labels: Mapping[str, str]
    lines: tuple[LokiLine, ...]


@dataclass(frozen=True)
class _Stage:
    kind: str
    match: re.Match[str]


def _unquote(token: str) -> str:
    """The text of a LogQL string: a raw string in backticks, or a quoted string with escapes."""
    if token.startswith("`"):
        return token[1:-1]
    try:
        text: str = json.loads(token)
    except ValueError as exc:
        raise LogQLError(f"parse error: invalid string {token}") from exc
    return text


def _matches(op: str, value: str, pattern: str) -> bool:
    """A comparison of a selector or a label filter: a regular expression matches all the value."""
    match op:
        case "=":
            return value == pattern
        case "!=":
            return value != pattern
        case "=~":
            return re.fullmatch(pattern, value) is not None
        case _:
            return re.fullmatch(pattern, value) is None


def _selector(text: str) -> tuple[list[tuple[str, str, str]], str]:
    """The matchers of the stream selector at the start of `text`, and the pipeline after it."""
    found = _SELECTOR.match(text)
    if found is None:
        raise LogQLError("parse error: a log query starts with a stream selector")
    body, matchers, at = found["body"], [], 0
    while at < len(body.rstrip()):
        matcher = _MATCHER.match(body, at)
        if matcher is None:
            raise LogQLError(f"parse error: invalid matcher in {{{body}}}")
        matchers.append((matcher["name"], matcher["op"], _unquote(matcher["value"])))
        at = matcher.end()
    return matchers, text[found.end() :]


def _stages(text: str) -> list[_Stage]:
    """The stages of the pipeline `text`, in order."""
    stages: list[_Stage] = []
    at = 0
    while text[at:].strip():
        for kind, pattern in _STAGES:
            if (match := pattern.match(text, at)) is not None:
                stages.append(_Stage(kind, match))
                at = match.end()
                break
        else:
            raise LogQLError(f"parse error: the fake knows no stage at {text[at:]!r}")
    return stages


def _names(text: str) -> list[str]:
    return [name.strip() for name in text.split(",")]


def _line_format(template: str, line: str, labels: dict[str, str]) -> str:
    if (field_or_line := _OR_LINE_TEMPLATE.fullmatch(template)) is not None:
        return labels.get(field_or_line[1]) or line
    if (only_field := _FIELD_TEMPLATE.fullmatch(template)) is not None:
        return labels.get(only_field[1], "")
    raise LogQLError(f"parse error: the fake knows no template {template}")


def _json(line: str, fields: str | None, labels: dict[str, str]) -> None:
    """Add the fields of a JSON object line as labels, or the error label of another line."""
    try:
        parsed = json.loads(line)
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        labels[_ERROR] = "JSONParserErr"
        labels["__error_details__"] = "the line is no JSON object"
        return
    names = _names(fields) if fields else list(parsed)
    for name in names:
        value = parsed.get(name)
        if value is not None and not isinstance(value, dict | list):
            labels[name] = value if isinstance(value, str) else json.dumps(value)


@dataclass
class _Row:
    """One line in the pipeline: its text, its labels and its unwrapped value."""

    text: str
    stream: Mapping[str, str]
    labels: dict[str, str]
    value: float | None = None


def _line_filter(parsed: re.Match[str], row: _Row) -> bool:
    pattern = _unquote(parsed["arg"])
    match parsed["op"]:
        case "|=":
            return pattern in row.text
        case "!=":
            return pattern not in row.text
        case "|~":
            return re.search(pattern, row.text) is not None
        case _:
            return re.search(pattern, row.text) is None


def _json_stage(parsed: re.Match[str], row: _Row) -> bool:
    _json(row.text, parsed["arg"], row.labels)
    return True


def _drop(parsed: re.Match[str], row: _Row) -> bool:
    for name in _names(parsed["arg"]):
        row.labels.pop(name, None)
    return True


def _line_format_stage(parsed: re.Match[str], row: _Row) -> bool:
    row.text = _line_format(_unquote(parsed["arg"]), row.text, row.labels)
    return True


def _regexp(parsed: re.Match[str], row: _Row) -> bool:
    if (found := re.search(_unquote(parsed["arg"]), row.text)) is not None:
        row.labels |= {
            f"{name}_extracted" if name in row.stream else name: text
            for name, text in found.groupdict().items()
            if text
        }
    return True


def _unwrap(parsed: re.Match[str], row: _Row) -> bool:
    try:
        row.value = float(row.labels.get(parsed["arg"], ""))
    except ValueError:
        row.labels[_ERROR] = "SampleExtractionErr"
    return True


def _label_filter(parsed: re.Match[str], row: _Row) -> bool:
    return _matches(parsed["op"], row.labels.get(parsed["name"], ""), _unquote(parsed["arg"]))


# Each stage, by kind: it changes the row, and gives False when it drops the line.
_RUNS: Final[dict[str, Callable[[re.Match[str], _Row], bool]]] = {
    "line": _line_filter,
    "json": _json_stage,
    "drop": _drop,
    "line_format": _line_format_stage,
    "regexp": _regexp,
    "unwrap": _unwrap,
    "label": _label_filter,
}


def _run(stages: Iterable[_Stage], line: str, stream: Mapping[str, str]) -> _Row | None:
    """The row of one line after the pipeline, or None when a filter drops it."""
    row = _Row(line, stream, dict(stream))
    for stage in stages:
        if not _RUNS[stage.kind](stage.match, row):
            return None
    return row


def _quantile(q: float, values: list[float]) -> float:
    """The `q` quantile of `values` with linear interpolation, as `quantile_over_time` gives."""
    ordered = sorted(values)
    rank = q * (len(ordered) - 1)
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


_AGGREGATES: Final[dict[str, Callable[[float | None, list[float]], float]]] = {
    "count_over_time": lambda _q, values: float(len(values)),
    "sum_over_time": lambda _q, values: math.fsum(values),
    "max_over_time": lambda _q, values: max(values),
    "quantile_over_time": lambda q, values: _quantile(q or 0.0, values),
}


def _text(value: float) -> str:
    return str(int(value)) if value.is_integer() else repr(value)


@dataclass
class LokiFake:
    """Log streams in memory, and the metric instant queries of the report on them. `queries`
    holds each query that reached the fake, in order."""

    streams: list[_Stream] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    def push(self, labels: Mapping[str, str], *lines: str, age: timedelta = timedelta(0)) -> None:
        """Add a stream with `labels` that holds `lines`, each `age` before the query."""
        self.streams.append(_Stream(dict(labels), tuple(LokiLine(text, age) for text in lines)))

    def serve(self, web: WebFake) -> None:
        """Answer the instant queries that reach the HTTP fake."""
        web.serve(self._answer)

    def query(self, expr: str) -> list[dict[str, Any]]:
        """The vector of the metric query `expr`. Raises LogQLError for a query that Loki
        refuses."""
        self.queries.append(expr)
        shape = _SUM_BY.fullmatch(expr.strip()) or _BY_AFTER.fullmatch(expr.strip())
        if shape is None:
            raise LogQLError(f"parse error: the fake knows no metric query {expr}")
        matchers, pipeline = _selector(shape["log"])
        stages = _stages(pipeline)
        window = timedelta(seconds=int(shape["range"][:-1]) * _RANGE_UNITS[shape["range"][-1]])
        by = _names(shape["by"])
        groups: dict[tuple[tuple[str, str], ...], list[float]] = defaultdict(list)
        for stream in self.streams:
            if not all(
                _matches(op, stream.labels.get(name, ""), text) for name, op, text in matchers
            ):
                continue
            for line in stream.lines:
                if line.age >= window or (row := _run(stages, line.text, stream.labels)) is None:
                    continue
                if _ERROR in row.labels:
                    raise LogQLError(
                        f"pipeline error: '{row.labels[_ERROR]}' for series: '{row.labels}'"
                    )
                key = tuple((name, row.labels[name]) for name in by if row.labels.get(name))
                groups[key].append(1.0 if row.value is None else row.value)
        q = float(shape["q"]) if "q" in shape.groupdict() and shape["q"] else None
        aggregate = _AGGREGATES[shape["fn"]]
        return [
            {"metric": dict(key), "value": [_ANSWER_TIME, _text(aggregate(q, values))]}
            for key, values in groups.items()
        ]

    def _answer(self, request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path != QUERY_PATH:
            return None
        try:
            vector = self.query(request.url.params.get("query", ""))
        except LogQLError as error:
            return httpx2.Response(400, text=str(error))
        return httpx2.Response(
            200, json={"status": "success", "data": {"resultType": "vector", "result": vector}}
        )
