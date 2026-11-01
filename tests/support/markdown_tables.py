"""The tables of a Markdown document, read with markdown-it (#3097).

`AGENTS.md` routes each kind of task to a document in a table with the header `When you | Read`.
Tests read that table here, so no test parses Markdown by hand.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from markdown_it import MarkdownIt

_MARKDOWN = MarkdownIt("commonmark").enable("table")
ROUTING_HEADER = ["When you", "Read"]


def tables(document: Path) -> list[list[list[str]]]:
    """Each table of the Markdown document, as rows of the source text of each cell, the header
    row first."""
    found: list[list[list[str]]] = []
    for token, following in pairwise(_MARKDOWN.parse(document.read_text(encoding="utf-8"))):
        match token.type:
            case "table_open":
                found.append([])
            case "tr_open":
                found[-1].append([])
            case "th_open" | "td_open":
                found[-1][-1].append(following.content)
    return found


def inline_hrefs(text: str) -> list[str]:
    """The target of every link in a fragment of Markdown, such as the text of a table cell."""
    return [
        str(token.attrs["href"])
        for block in _MARKDOWN.parse(text)
        for token in block.children or ()
        if token.type == "link_open"
    ]


def routing_rows(document: Path) -> list[list[str]]:
    """The body rows of the routing table of an `AGENTS.md`: the kind of task, then what to read."""
    [rows] = [rows for header, *rows in tables(document) if header == ROUTING_HEADER]
    return rows


def where_to_look(document: Path) -> dict[str, list[str]]:
    """The link targets of each row of the routing table of an `AGENTS.md`, by the kind of task."""
    return {task: inline_hrefs(read) for task, read in routing_rows(document)}
