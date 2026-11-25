"""The shared CommonMark parser of the roadmap.

Plain CommonMark readers share one parser through `commonmark_parser()` so reads
do not build a parser on each call.
"""

from __future__ import annotations

from functools import cache

from markdown_it import MarkdownIt


@cache
def commonmark_parser() -> MarkdownIt:
    """Return the cached CommonMark parser."""
    return MarkdownIt("commonmark")


def reset_commonmark_parser() -> None:
    """Clear the cached parser so the next call builds a parser again."""
    commonmark_parser.cache_clear()
