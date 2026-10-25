"""Syntax highlighters for terminal inputs and viewers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from devops_cli.output import RegexHighlighter


class LogQLHighlighter(RegexHighlighter):
    """Syntax highlighter for LogQL query input fields."""

    highlights: ClassVar[Sequence[str]] = [
        r"(?P<brace>[{}])",
        r'(?P<str>"[^"]*")',
        r"(?P<number>\b\d+(?:ms|s|m|h|d)?\b)",
        r"(?P<call>\|\s*(?:json|logfmt|unpack|pattern|regexp))",
        r"(?P<tag>[a-zA-Z_][a-zA-Z0-9_-]*(?=\s*(=|!=|=~|!~)))",
        r"(?P<operator>\|=|\|~|!=|!~|=~|=)",
    ]


__all__ = ["LogQLHighlighter"]
