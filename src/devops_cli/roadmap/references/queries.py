"""The queries of the reference step (#4672): the rule queries of an item body, and their merge
with the `reference_queries` of the model reply.

A rule query is, in this order: a Python import statement of the body, the name of a package that
a URL of the body names (a PyPI project or a GitHub repository), and a code span of the body. An
import statement is a line of a code block or the text of a code span that `ast` reads as one
import. The step sends at most `CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_CODE_SEARCHES` queries
for an item. The merge takes a rule query first and then a query of the model in turn, so a body
with many code spans leaves a place for a query of the model. A skip-class item has no model reply
and sends the rule queries only.

A query is plain words. A colon and a quote leave it, so no text of an item names a search
qualifier such as `repo:` of another repository.

Each query passes the guard of the web search (`devops_cli.ai.web_search`) before it reaches a
provider or the decision point: the guard refuses a secret, an e-mail address, a private address
and an internal host name. The guard reads the text of the item and also the plain words, because
the words are what leaves the process, and a host of a URL is a word of its own only there. A
refused query is dropped, and it adds 1 to `devops_cli_brain_references_total` with the provider
`step` and the result `refused`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Sequence
from itertools import chain, zip_longest

from devops_cli.ai.web_search import _guard
from devops_cli.config.constants import CONST_ROADMAP_ALTERNATIVES_REFERENCE_QUERY_CHARS
from devops_cli.exceptions.ai import SearchQueryRefused
from devops_cli.roadmap.inventory import tool_names
from devops_cli.roadmap.markdown import commonmark_parser
from devops_cli.roadmap.page_fetch import named_urls
from devops_cli.roadmap.references.providers import STEP, Result, count

# The token types of CommonMark that hold code: a block gives its lines, and a span its text.
_CODE_BLOCKS = frozenset({"fence", "code_block"})
_CODE_SPAN = "code_inline"
# The two words that start an import statement of Python (the language grammar).
_IMPORT_STARTS = ("import ", "from ")
_MIN_QUERY_CHARS = 3


def _plain(text: str) -> str:
    """`text` as the words of one query: one line, with no colon and no quote."""
    return " ".join(text.replace(":", " ").replace('"', " ").split())


def _is_import(line: str) -> bool:
    """Whether `line` is one import statement of Python, as `ast` reads it."""
    if not line.startswith(_IMPORT_STARTS):
        return False
    try:
        statements = ast.parse(line).body
    except SyntaxError, ValueError:
        return False
    return len(statements) == 1 and isinstance(statements[0], (ast.Import, ast.ImportFrom))


def _code_texts(body: str) -> tuple[list[str], list[str]]:
    """The lines of the code blocks of `body`, and the texts of its code spans, in order."""
    lines: list[str] = []
    spans: list[str] = []
    for token in commonmark_parser().parse(body):
        if token.type in _CODE_BLOCKS:
            lines.extend(token.content.splitlines())
        spans.extend(child.content for child in token.children or () if child.type == _CODE_SPAN)
    return lines, spans


def _refused(text: str) -> bool:
    """Whether the guard of the web search refuses `text` as a query."""
    try:
        _guard(text)
    except SearchQueryRefused:
        return True
    return False


def _usable(queries: Iterable[str]) -> Iterator[str]:
    """Each of `queries` once, as plain words, in order. A query with no letter or digit, a query
    shorter than 3 characters and a query over the length cap are left out. So is a query that
    the guard of the web search refuses, as its text or as its plain words, and it is counted."""
    seen: set[str] = set()
    for text in queries:
        query = _plain(text)
        key = query.casefold()
        fits = _MIN_QUERY_CHARS <= len(query) <= CONST_ROADMAP_ALTERNATIVES_REFERENCE_QUERY_CHARS
        if not fits or key in seen or not any(char.isalnum() for char in query):
            continue
        seen.add(key)
        if _refused(text) or _refused(query):
            count(STEP, Result.REFUSED)
            continue
        yield query


def rule_queries(body: str) -> list[str]:
    """The rule queries of the item text `body`: its import statements, then the package names of
    its URLs, then its other code spans."""
    lines, spans = _code_texts(body)
    cap = CONST_ROADMAP_ALTERNATIVES_REFERENCE_QUERY_CHARS
    texts = [" ".join(text.split()) for text in (*lines, *spans)]
    imports = [text for text in texts if len(text) <= cap and _is_import(text)]
    packages = [name for url in sorted(named_urls(body)) for name in tool_names(url)]
    others = [span for span in spans if " ".join(span.split()) not in imports]
    return list(_usable(chain(imports, packages, others)))


def merged_queries(rules: Sequence[str], model: Sequence[str], *, limit: int) -> tuple[str, ...]:
    """At most `limit` queries of one item: a rule query, then a query of the model, in turn."""
    turns = chain.from_iterable(zip_longest(rules, model))
    merged = list(_usable(query for query in turns if query is not None))
    return tuple(merged[:limit])


__all__ = ["merged_queries", "rule_queries"]
