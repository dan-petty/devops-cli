"""In-process PromQL structural validation.

Invalid queries previously travelled to the server before failing, so a typo cost a
network round trip and returned an error phrased in the server's terms rather than
pointing at the offending character.

**Design constraint: this validator must never reject a valid query.** A false rejection
blocks work the server would happily have served, which is strictly worse than forwarding
a malformed query the server would have rejected anyway. So it verifies only what is
unambiguously malformed — bracket balance, string termination, duration literal shape —
and deliberately does not police function names, which vary by Prometheus version.

It also reads which series an expression selects, which labels it groups by and whether it
falls back to a constant (`selectors`, `grouping_labels`, `falls_back_to_constant`), so a
dashboard's queries can be checked against what its exporters serve without a server.
Function names are told apart by their structure, a name followed by `(` or by
`by`/`without`, never by a list of names.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from devops_cli.config.constants import (
    CONST_PROMQL_AGGREGATION_MODIFIERS,
    CONST_PROMQL_BRACKET_PAIRS,
    CONST_PROMQL_DURATION_UNITS,
    CONST_PROMQL_GROUPING_KEYWORDS,
    CONST_PROMQL_KEYWORDS,
    CONST_PROMQL_QUOTE_CHARS,
)

# A duration literal is one or more <number><unit> components, e.g. 5m, 1h30m, 500ms.
_DURATION_REGEX = re.compile(
    rf"^(?:\d+(?:{'|'.join(sorted(CONST_PROMQL_DURATION_UNITS, key=len, reverse=True))}))+$"
)
# Range/offset selectors: the bracketed part of metric[5m] or metric[1h:5m].
_RANGE_SELECTOR_REGEX = re.compile(r"\[([^\]]*)\]")
# Tokens of an expression. A string literal or a `#` comment is one token, so nothing inside
# either is read as syntax. A number or duration is read before a name, so `5m` never yields
# the name `m`, and a Grafana variable (`$job`, `${__rate_interval}`) is one token, so its
# name is never read as a metric.
_TOKEN_REGEX = re.compile(
    r"(?P<string>\"(?:\\.|[^\\\"])*\"|'(?:\\.|[^\\'])*'|`[^`]*`)"
    r"|(?P<comment>#[^\n]*)"
    r"|(?P<variable>\$\{[^}]*\}|\$\w+)"
    r"|(?P<number>\d[\w.]*)"
    r"|(?P<name>[A-Za-z_:][\w:]*)"
    r"|(?P<matcher>[=!]~|!=|=)"
    r"|(?P<separator>,)"
    r"|(?P<bracket>[(){}\[\]])"
)


@dataclass
class PromQLValidation:
    """The outcome of validating a PromQL expression."""

    expression: str
    valid: bool = True
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """A validation is truthy when the expression is well-formed."""
        return self.valid

    @property
    def summary(self) -> str:
        """Render the failure reasons as a single line."""
        return "; ".join(self.errors)


def _strip_strings(expression: str) -> tuple[str, str | None]:
    """Blank out string literals so their contents cannot affect structural checks.

    Returns the masked expression and an error when a literal is left unterminated. Label
    matchers routinely contain brackets and braces — `{path=~"/a[0-9]+"}` — which would
    otherwise be miscounted as structural delimiters.
    """
    masked: list[str] = []
    quote: str | None = None
    escaped = False

    for char in expression:
        if quote is None:
            if char in CONST_PROMQL_QUOTE_CHARS:
                quote = char
                masked.append(" ")
                continue
            masked.append(char)
            continue

        # Inside a literal: preserve length, drop content.
        masked.append(" ")
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            quote = None

    if quote is not None:
        return "".join(masked), f"Unterminated string literal opened with {quote!r}"
    return "".join(masked), None


def _close_bracket(
    stack: list[tuple[str, int]], char: str, position: int, expected_opener: str
) -> str | None:
    """Pop the matching opener for a closing bracket, describing any mismatch."""
    if not stack:
        return f"Unmatched closing {char!r} at position {position}"

    opener, opener_pos = stack.pop()
    if opener != expected_opener:
        return (
            f"Mismatched {opener!r} at position {opener_pos} closed by {char!r} "
            f"at position {position}"
        )
    return None


def _check_brackets(masked: str) -> list[str]:
    """Verify that every bracket is balanced and correctly nested."""
    errors: list[str] = []
    closing = {close: open_ for open_, close in CONST_PROMQL_BRACKET_PAIRS.items()}
    stack: list[tuple[str, int]] = []

    for position, char in enumerate(masked):
        if char in CONST_PROMQL_BRACKET_PAIRS:
            stack.append((char, position))
            continue
        if char not in closing:
            continue
        error = _close_bracket(stack, char, position, closing[char])
        if error:
            errors.append(error)

    errors.extend(f"Unclosed {opener!r} at position {position}" for opener, position in stack)
    return errors


def _check_durations(expression: str, masked: str) -> list[str]:
    """Verify that range selector contents are valid duration literals.

    Only selectors whose content looks like a duration attempt are checked. A subquery
    (`[1h:5m]`) or a label-value index is left alone, since misjudging those would risk
    rejecting a valid query.
    """
    errors: list[str] = []
    for match in _RANGE_SELECTOR_REGEX.finditer(masked):
        raw = expression[match.start(1) : match.end(1)].strip()
        if not raw:
            errors.append("Empty range selector '[]'")
            continue
        if ":" in raw:
            # Subquery form; each side is optional so only non-empty parts are checked.
            parts = [part.strip() for part in raw.split(":", 1)]
            errors.extend(
                f"Invalid duration {part!r} in subquery selector '[{raw}]'"
                for part in parts
                if part and not part.startswith("$") and not _DURATION_REGEX.match(part)
            )
            continue
        if not raw.startswith("$") and not _DURATION_REGEX.match(raw):
            errors.append(f"Invalid duration literal {raw!r} in range selector")
    return errors


def validate_promql(expression: str) -> PromQLValidation:
    """Validate a PromQL expression's structure without contacting a server."""
    result = PromQLValidation(expression=expression)

    if not expression.strip():
        result.valid = False
        result.errors.append("Expression is empty")
        return result

    masked, string_error = _strip_strings(expression)
    errors: list[str] = [string_error] if string_error else []
    errors.extend(_check_brackets(masked))
    # Duration checks depend on balanced brackets; running them on a malformed
    # expression would report confusing positions derived from the wrong selector.
    if not errors:
        errors.extend(_check_durations(expression, masked))

    result.errors = errors
    result.valid = not errors
    return result


@dataclass(frozen=True)
class SeriesSelector:
    """One series selector: the metric it names and the label names its matchers use.

    `metric` is None when the selector names no metric, as `{job="api"}` or
    `{__name__=~"node_.+"}` do; an `{__name__="..."}` equality matcher names it, and so does
    a quoted name standing alone among the matchers, as in `{"utf8.name", job="api"}`.
    """

    metric: str | None
    labels: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _Token:
    """One token of an expression: its kind, named by the regex group that read it, and its text."""

    kind: str
    text: str


@dataclass
class _SelectorScan:
    """The series selectors and grouping labels one pass over an expression found."""

    selectors: list[SeriesSelector] = field(default_factory=list)
    grouping: set[str] = field(default_factory=set)


def _index_after(tokens: list[_Token], index: int, closer: str) -> int:
    """Return the index just past the first `closer` at or after `index`."""
    return next(
        (position + 1 for position in range(index, len(tokens)) if tokens[position].text == closer),
        len(tokens),
    )


def _text_at(tokens: list[_Token], index: int) -> str:
    """Return the text of the token at `index`, or an empty string past the end."""
    return tokens[index].text if index < len(tokens) else ""


def _tokens(expression: str) -> list[_Token]:
    """Split an expression into tokens, dropping its comments."""
    return [
        _Token(str(match.lastgroup), match.group())
        for match in _TOKEN_REGEX.finditer(expression)
        if match.lastgroup != "comment"
    ]


def _unquoted(token: _Token) -> str:
    """Return a name as written, or a string literal's contents without its quotes."""
    return token.text[1:-1] if token.kind == "string" else token.text


def _read_matcher(matcher: list[_Token]) -> tuple[str | None, str | None]:
    """Return the metric one matcher names and the label it matches on, each possibly None.

    A label name may be quoted, as Prometheus 3 allows. `__name__="..."` names the metric
    rather than a label, as does a quoted name standing alone.
    """
    first = matcher[0]
    if len(matcher) == 1 and first.kind == "string":
        return _unquoted(first), None
    if first.kind not in {"name", "string"}:
        return None, None
    if _unquoted(first) != "__name__":
        return None, _unquoted(first)
    is_equality = len(matcher) == 3 and matcher[1].text == "="
    return (_unquoted(matcher[2]) if is_equality else None), None


def _record_selector(
    tokens: list[_Token], open_index: int, metric: str | None, scan: _SelectorScan
) -> int:
    """Record the selector whose matchers open at `open_index`; return the index past them."""
    close_index = _index_after(tokens, open_index, "}")
    inside = [token for token in tokens[open_index + 1 : close_index] if token.text != "}"]
    matchers = [
        _read_matcher(list(matcher))
        for is_separator, matcher in itertools.groupby(inside, lambda token: token.text == ",")
        if not is_separator
    ]
    named = [name for name, _ in matchers if name]
    labels = frozenset(label for _, label in matchers if label)
    scan.selectors.append(SeriesSelector(metric or next(iter(named), None), labels))
    return close_index


def _record_grouping(tokens: list[_Token], open_index: int, scan: _SelectorScan) -> int:
    """Record the label list that opens at `open_index`; return the index past it."""
    close_index = _index_after(tokens, open_index, ")")
    scan.grouping.update(
        _unquoted(token)
        for token in tokens[open_index:close_index]
        if token.kind in {"name", "string"}
    )
    return close_index


def _selects_no_series(word: str, following: str) -> bool:
    """Whether a name is a keyword, a function or an aggregation rather than a metric.

    A function or aggregation name is followed by its argument list or, for an
    aggregation, by `by` or `without`; a metric name never is.
    """
    return (
        word.lower() in CONST_PROMQL_KEYWORDS
        or following == "("
        or following.lower() in CONST_PROMQL_AGGREGATION_MODIFIERS
    )


def _scan_name(tokens: list[_Token], index: int, scan: _SelectorScan) -> int:
    """Read the name at `index` as a grouping list, syntax or a metric; return the next index."""
    word = tokens[index].text
    following = _text_at(tokens, index + 1)
    if word.lower() in CONST_PROMQL_GROUPING_KEYWORDS and following == "(":
        return _record_grouping(tokens, index + 1, scan)
    if _selects_no_series(word, following):
        return index + 1
    if following == "{":
        return _record_selector(tokens, index + 1, word, scan)
    scan.selectors.append(SeriesSelector(word))
    return index + 1


def _scan_token(tokens: list[_Token], index: int, scan: _SelectorScan) -> int:
    """Record what the token at `index` starts; return the index of the next token to read."""
    token = tokens[index]
    if token.text == "[":
        # Range and subquery brackets hold durations and variables, never series.
        return _index_after(tokens, index, "]")
    if token.text == "{":
        return _record_selector(tokens, index, None, scan)
    if token.kind == "name":
        return _scan_name(tokens, index, scan)
    return index + 1


def _scan(expression: str) -> _SelectorScan:
    """Walk an expression once, collecting its series selectors and grouping labels."""
    tokens = _tokens(expression)
    scan = _SelectorScan()
    index = 0
    while index < len(tokens):
        index = _scan_token(tokens, index, scan)
    return scan


def _operand_start(tokens: list[_Token], index: int) -> int:
    """Return where the right operand of a binary operator at `index - 1` begins.

    A vector-matching modifier with its label list, and any opening parentheses, are skipped.
    """
    if _text_at(tokens, index).lower() in CONST_PROMQL_GROUPING_KEYWORDS:
        index = _index_after(tokens, index + 1, ")")
    return next(
        (position for position in range(index, len(tokens)) if tokens[position].text != "("),
        len(tokens),
    )


def _opens_with_constant(tokens: list[_Token], index: int) -> bool:
    """Whether the token at `index` starts a number or a `vector(...)` call."""
    return index < len(tokens) and (
        tokens[index].kind == "number"
        or (tokens[index].text == "vector" and _text_at(tokens, index + 1) == "(")
    )


def selectors(expression: str) -> list[SeriesSelector]:
    """Return every series selector in an expression, in the order they appear.

    Function and aggregation names, keywords, grouping label lists, string contents,
    comments, numbers, durations and Grafana variables are skipped.
    """
    return _scan(expression).selectors


def grouping_labels(expression: str) -> frozenset[str]:
    """Return the labels named after by, without, on, ignoring, group_left and group_right."""
    return frozenset(_scan(expression).grouping)


def falls_back_to_constant(expression: str) -> bool:
    """Whether an `or` in the expression falls back to a constant.

    `or` fills in its right operand wherever its left one has no series, so `x or vector(0)`,
    `x or on () vector(0)` and `x or 0 * up` turn an empty result into a zero that reads as a
    measurement. The right operand is a constant when it opens with `vector(...)` or a number.
    `or` is matched in any case, as the lexer matches keywords.
    """
    tokens = _tokens(expression)
    return any(
        _opens_with_constant(tokens, _operand_start(tokens, index + 1))
        for index, token in enumerate(tokens)
        if token.kind == "name" and token.text.lower() == "or"
    )


__all__ = [
    "PromQLValidation",
    "SeriesSelector",
    "falls_back_to_constant",
    "grouping_labels",
    "selectors",
    "validate_promql",
]
