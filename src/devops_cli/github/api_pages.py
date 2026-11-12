"""The pages of a `devops gh api --paginate` read (#4737).

gh walks every `Link` page of `gh api --paginate` in one process, so `run_gh` counts the walk as
one request with the status `none`. A REST GET listing is read through the GitHub session instead.
The session paces each page, counts each attempt with the status of its answer (#3497) and sends
a page it holds an answer for with `If-None-Match`. `reads_through_session` names the reads that
the session sends. gh keeps the others, because the session does not send them as gh does:

- a GraphQL listing, which pages by a cursor in its query;
- a write;
- an endpoint with a gh placeholder, such as `{owner}` or `:repo`, which gh fills from its own
  base repository;
- a full URL, which can name another host;
- a Go template (`--template`);
- a read that `--cache` keeps in the response cache of `run_gh`;
- any other gh flag, such as `--slurp`, `-H` or `-f`.

`session_path` asks for pages of 100 items when the endpoint does not set `per_page`, as gh
asks for them (#5100). So the session reads the pages that gh reads, in the same number of
requests.

`printed_pages` prints the pages as gh 2.103.1 prints them. With no filter, the items of array
pages print as one JSON array, and each object page prints whole, on its own line. A `--jq`
filter runs on each page through jq.py, the Python binding of jq, and each value prints on its
own line: a string as text, null as an empty line, a boolean as `true` or `false`, a whole number
with no decimals and any other number with two, and an array or an object as compact JSON with
sorted keys. A filter that does not compile raises `ValidationError` before the first page is
read, and a filter that fails on a page raises it naming the page.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Final
from urllib.parse import parse_qs, urlencode, urlsplit

from devops_cli.config.constants import CONST_GH_API_DEFAULT_METHOD, CONST_GH_API_GRAPHQL_ENDPOINT
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.validation import ValidationError

_GH_PLACEHOLDER: Final = re.compile(r":(?:owner|repo|branch)\b|\{[a-z]+\}")
"""The placeholders gh fills from its base repository (gh 2.103.1, `fillPlaceholders`)."""

_PER_PAGE: Final = "per_page"

# gh prints a number that a filter selects with no decimals when it is whole, else with two.
_WHOLE_NUMBER_FORMAT: Final = ".0f"
_FRACTION_FORMAT: Final = ".2f"

_JQ_OPTION: Final = "jq"


def reads_through_session(
    endpoint: str,
    *,
    method: str | None,
    template: str | None,
    cache: bool,
    gh_flags: Sequence[str],
) -> bool:
    """Whether the GitHub session sends the `devops gh api --paginate` read of `endpoint`: a REST
    GET of a path, with no Go template, no `--cache` and no other gh flag."""
    return (
        (method is None or method.upper() == CONST_GH_API_DEFAULT_METHOD)
        and endpoint != CONST_GH_API_GRAPHQL_ENDPOINT
        and _GH_PLACEHOLDER.search(endpoint) is None
        and not urlsplit(endpoint).scheme
        and template is None
        and not cache
        and not gh_flags
    )


def session_path(endpoint: str) -> str:
    """The path of `endpoint` under GitHub's API, with or without its leading slash, as gh
    reads it, with the page size gh asks for.

    gh 2.103.1 adds `per_page=100` to a paginated REST read when the first `per_page` of its
    query has no value (`addPerPage` in `pkg/cmd/api/pagination.go`, #5100): after `&` when the
    endpoint has a `?`, else after `?`. gh also keeps a `per_page` given with `-f` or `-F`, but
    such a read has a gh flag, so gh sends it.
    """
    path = "/" + endpoint.lstrip("/")
    _, question_mark, query = path.partition("?")
    # The first value, as Go's `url.Values.Get` gives it to gh.
    if parse_qs(query, keep_blank_values=True).get(_PER_PAGE, [""])[0]:
        return path
    page_size = urlencode({_PER_PAGE: DEFAULT_GH_REST_PER_PAGE})
    return f"{path}{'&' if question_mark else '?'}{page_size}"


def listing_text(endpoint: str, jq_filter: str | None) -> Iterator[str]:
    """What `devops gh api --paginate` prints for `endpoint`, read through the GitHub session."""
    from devops_cli.github.session import get_github_session

    return printed_pages(get_github_session().pages(session_path(endpoint)), jq_filter)


def printed_pages(pages: Iterable[Any], jq_filter: str | None) -> Iterator[str]:
    """The text of `pages` as gh prints it: with `jq_filter`, the values it gives for each page,
    the text of one page at a time; else the pages whole."""
    if jq_filter is None:
        yield from _whole_pages(pages)
        return
    import jq

    try:
        program = jq.compile(jq_filter)
    except ValueError as error:
        raise ValidationError(
            f"The --jq filter does not compile: {error}", field=_JQ_OPTION
        ) from error
    for number, page in enumerate(pages, start=1):
        try:
            values = program.input_value(page).all()
        except ValueError as error:
            raise ValidationError(
                f"The --jq filter failed on page {number}: {error}", field=_JQ_OPTION
            ) from error
        yield "".join(f"{_value_text(value)}\n" for value in values)


def _whole_pages(pages: Iterable[Any]) -> Iterator[str]:
    """The items of the array pages as one JSON array, after each object page on its own line."""
    items: list[Any] = []
    arrays = False
    for page in pages:
        if isinstance(page, list):
            arrays = True
            items.extend(page)
        else:
            yield f"{_compact(page)}\n"
    if arrays:
        yield f"{_compact(items)}\n"


def _value_text(value: Any) -> str:
    """One value a filter selects, as gh prints it."""
    match value:
        case str():
            return value
        case None:
            return ""
        case bool():
            return json.dumps(value)
        case int():
            return str(value)
        case float():
            return format(value, _WHOLE_NUMBER_FORMAT if value.is_integer() else _FRACTION_FORMAT)
        case _:
            return _compact(value, sort_keys=True)


def _compact(value: Any, *, sort_keys: bool = False) -> str:
    """`value` as compact JSON, with its text kept as it is."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)
