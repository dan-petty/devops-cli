"""In-process PromQL structural validation.

Invalid queries previously travelled to the server before failing, so a typo cost a
network round trip and returned an error phrased in the server's terms rather than
pointing at the offending character.

**Design constraint: this validator must never reject a valid query.** A false rejection
blocks work the server would happily have served, which is strictly worse than forwarding
a malformed query the server would have rejected anyway. So it verifies only what is
unambiguously malformed — bracket balance, string termination, duration literal shape —
and deliberately does not police function names, which vary by Prometheus version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from devops_cli.config.constants import (
    CONST_PROMQL_BRACKET_PAIRS,
    CONST_PROMQL_DURATION_UNITS,
    CONST_PROMQL_QUOTE_CHARS,
)

# A duration literal is one or more <number><unit> components, e.g. 5m, 1h30m, 500ms.
_DURATION_REGEX = re.compile(
    rf"^(?:\d+(?:{'|'.join(sorted(CONST_PROMQL_DURATION_UNITS, key=len, reverse=True))}))+$"
)
# Range/offset selectors: the bracketed part of metric[5m] or metric[1h:5m].
_RANGE_SELECTOR_REGEX = re.compile(r"\[([^\]]*)\]")


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
                if part and not _DURATION_REGEX.match(part)
            )
            continue
        if not _DURATION_REGEX.match(raw):
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


__all__ = [
    "PromQLValidation",
    "validate_promql",
]
