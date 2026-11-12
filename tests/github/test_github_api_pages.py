"""The pages of a `devops gh api --paginate` read: which reads the GitHub session sends, and how
their pages print (#4737)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions.validation import ValidationError
from devops_cli.github.api_pages import printed_pages, reads_through_session, session_path

if TYPE_CHECKING:
    from collections.abc import Iterator

_LISTING = "repos/octo/repo/issues?state=open&per_page=100"


@pytest.mark.parametrize("method", [None, "GET", "get"])
def test_a_rest_get_listing_is_read_through_the_session(method: str | None) -> None:
    """A REST GET with no gh flag of its own is a read the session sends."""
    assert (
        reads_through_session(_LISTING, method=method, template=None, cache=False, gh_flags=[])
        is True
    )


@pytest.mark.parametrize(
    ("endpoint", "method", "template", "cache", "gh_flags"),
    [
        pytest.param("graphql", None, None, False, [], id="graphql"),
        pytest.param(_LISTING, "POST", None, False, [], id="write"),
        pytest.param("repos/{owner}/{repo}/issues", None, None, False, [], id="brace-placeholder"),
        pytest.param("repos/:owner/:repo/issues", None, None, False, [], id="colon-placeholder"),
        pytest.param("https://api.github.com/" + _LISTING, None, None, False, [], id="full-url"),
        pytest.param(_LISTING, None, "{{.title}}", False, [], id="template"),
        pytest.param(_LISTING, None, None, True, [], id="cache"),
        pytest.param(_LISTING, None, None, False, ["--slurp"], id="other-gh-flag"),
    ],
)
def test_gh_keeps_a_read_the_session_does_not_send(
    endpoint: str, method: str | None, template: str | None, cache: bool, gh_flags: list[str]
) -> None:
    """GraphQL, a write, a gh placeholder, a full URL, a Go template, `--cache` and every other
    gh flag stay with gh."""
    assert (
        reads_through_session(
            endpoint, method=method, template=template, cache=cache, gh_flags=gh_flags
        )
        is False
    )


def test_a_search_query_with_a_colon_is_read_through_the_session() -> None:
    """A colon in a search query is not a gh placeholder."""
    endpoint = "search/issues?q=repo:octo/repo+is:open"
    assert reads_through_session(endpoint, method=None, template=None, cache=False, gh_flags=[])


@pytest.mark.parametrize("endpoint", [_LISTING, "/" + _LISTING])
def test_the_session_path_of_an_endpoint_starts_at_the_api_root(endpoint: str) -> None:
    """gh reads an endpoint with or without its leading slash as a path under the API."""
    assert session_path(endpoint) == "/" + _LISTING


@pytest.mark.parametrize(
    ("endpoint", "path"),
    [
        pytest.param(
            "repos/octo/repo/labels", "/repos/octo/repo/labels?per_page=100", id="no-query"
        ),
        pytest.param(
            "repos/octo/repo/issues?state=all",
            "/repos/octo/repo/issues?state=all&per_page=100",
            id="query",
        ),
        pytest.param(
            "repos/octo/repo/labels?", "/repos/octo/repo/labels?&per_page=100", id="empty"
        ),
        pytest.param(
            "repos/octo/repo/issues?per_page=",
            "/repos/octo/repo/issues?per_page=&per_page=100",
            id="per-page-empty",
        ),
        pytest.param(
            "repos/octo/repo/issues?per_page&state=all",
            "/repos/octo/repo/issues?per_page&state=all&per_page=100",
            id="per-page-with-no-value",
        ),
        pytest.param(
            "repos/octo/repo/issues?per_page=&per_page=5",
            "/repos/octo/repo/issues?per_page=&per_page=5&per_page=100",
            id="first-per-page-empty",
        ),
    ],
)
def test_a_read_with_no_per_page_asks_for_pages_of_100_as_gh_does(endpoint: str, path: str) -> None:
    """gh adds `per_page=100` to a paginated REST read when the first `per_page` of its query
    has no value, after `&` when the endpoint has a `?`, else after `?` (#5100)."""
    assert session_path(endpoint) == path


@pytest.mark.parametrize(
    "endpoint",
    [
        "/repos/octo/repo/issues?per_page=5",
        "/repos/octo/repo/issues?state=all&per_page=5",
        "/repos/octo/repo/issues?per%5Fpage=5",
        "/search/issues?q=a+b&per_page=5&per_page=",
    ],
)
def test_an_endpoint_that_sets_per_page_keeps_it(endpoint: str) -> None:
    """A query whose first `per_page` has a value, also an escaped name, is sent as it is."""
    assert session_path(endpoint) == endpoint


def test_array_pages_print_as_one_json_array() -> None:
    """With no filter, the items of all array pages print as one compact JSON array, as gh
    joins them."""
    pages = [[{"number": 1, "title": "é"}], [{"number": 2, "title": "b"}]]
    assert list(printed_pages(iter(pages), None)) == [
        '[{"number":1,"title":"é"},{"number":2,"title":"b"}]\n'
    ]


def test_object_pages_print_one_after_another() -> None:
    """With no filter, each page that is an object prints whole, on its own line."""
    pages = [{"total_count": 2, "items": [1]}, {"total_count": 2, "items": [2]}]
    assert list(printed_pages(iter(pages), None)) == [
        '{"total_count":2,"items":[1]}\n',
        '{"total_count":2,"items":[2]}\n',
    ]


def test_each_value_of_a_jq_filter_prints_as_gh_prints_it() -> None:
    """A string prints as text, null as an empty line, a boolean as true or false, a whole
    number with no decimals and any other with two, and a list or an object as compact JSON
    with sorted keys."""
    page = [{"title": "a", "done": True, "score": 0.125, "count": 3, "big": 1e20}]
    jq_filter = ".[] | .title, .missing, .done, .score, .count, .big, {z: .count, a: [.title]}"
    assert list(printed_pages(iter([page]), jq_filter)) == [
        'a\n\ntrue\n0.12\n3\n100000000000000000000\n{"a":["a"],"z":3}\n'
    ]


def test_a_jq_filter_that_does_not_compile_reads_no_page() -> None:
    """A filter that does not compile raises `ValidationError` before the first page is read."""
    read: list[int] = []

    def pages() -> Iterator[Any]:
        read.append(1)
        yield []

    with pytest.raises(ValidationError) as raised:
        list(printed_pages(pages(), ".["))
    assert (raised.value.error_code, raised.value.exit_code, read) == ("VALIDATION_ERROR", 1, [])


def test_a_jq_filter_that_fails_on_a_page_names_the_page() -> None:
    """A filter that fails on a page raises `ValidationError` that names the page, after the
    pages before it printed."""
    printed: list[str] = []
    with pytest.raises(ValidationError) as raised:
        printed.extend(printed_pages(iter([{"a": 1}, [1]]), ".a"))
    assert (printed, "page 2" in raised.value.message) == (["1\n"], True)
