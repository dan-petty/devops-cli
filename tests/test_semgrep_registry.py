"""The Semgrep registry ruleset cache: `devops review rules fetch` and its conditional refetch (#1144).

The registry is served by the shared web stub with synthetic rulesets in the shape of its own, so
no test reaches the network. A request's `If-None-Match` is read from the requests the stub
recorded; the stub answers what a route says, so a test that wants a 304 sets the route to one.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml

from devops_cli.config.defaults import DEFAULT_SEMGREP_REGISTRY_TIMEOUT_SECONDS
from devops_cli.exceptions import ToolDownloadError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.security.semgrep_registry import fetch_registry_ruleset, registry_cache_paths
from tests.web_fakes import StubWeb

DEFAULT_RULESET_URL = "https://semgrep.dev/c/p/default"
FIRST_RULESET = (
    b"rules:\n"
    b"- id: example.lang.security.first.first\n"
    b"  pattern: first(...)\n"
    b"- id: example.lang.security.second.second\n"
    b"  pattern: second(...)\n"
)
SECOND_RULESET = b"rules:\n- id: example.lang.security.third.third\n  pattern: third(...)\n"
FIRST_ETAG = 'W/"first-ruleset"'
SECOND_ETAG = 'W/"second-ruleset"'
NOT_A_RULESET = (
    "The answer from https://semgrep.dev/c/p/default is not a Semgrep ruleset: it needs a `rules` "
    "list of at least one rule, each with an id."
)


def serve(
    web: StubWeb,
    body: bytes,
    etag: str | None = FIRST_ETAG,
    url: str = DEFAULT_RULESET_URL,
) -> None:
    """Make the registry answer `url` with `body` and, when given, the validator `etag`."""
    web.routes[url] = (200, {"etag": etag} if etag else {}, body)


def validators_sent(web: StubWeb) -> list[str | None]:
    """The `If-None-Match` each request the registry received carried, in order."""
    return [request.headers.get("if-none-match") for request in web.sent]


def test_a_fetch_caches_the_ruleset_byte_for_byte_with_its_etag(stub_web: StubWeb) -> None:
    serve(stub_web, FIRST_RULESET)

    cached = fetch_registry_ruleset("p/default")

    paths = registry_cache_paths("p/default")
    assert cached == 2
    assert stub_web.requested == [DEFAULT_RULESET_URL]
    assert validators_sent(stub_web) == [None]
    assert (
        stub_web.sent[0].extensions["timeout"]["read"] == DEFAULT_SEMGREP_REGISTRY_TIMEOUT_SECONDS
    )
    assert paths.rules.read_bytes() == FIRST_RULESET
    assert paths.etag.read_text(encoding="utf-8") == FIRST_ETAG
    assert sorted(path.name for path in paths.rules.parent.iterdir()) == [
        "p-default.etag",
        "p-default.yaml",
    ]


def test_a_ruleset_the_registry_serves_as_json_is_cached_as_it_came(stub_web: StubWeb) -> None:
    """The registry answers a client that accepts gzip with the ruleset as JSON, a YAML document."""
    as_json = json.dumps(yaml.safe_load(FIRST_RULESET)).encode()
    serve(stub_web, as_json)

    assert fetch_registry_ruleset("p/default") == 2
    assert registry_cache_paths("p/default").rules.read_bytes() == as_json


def test_the_cache_paths_map_a_ruleset_name_to_files_under_the_user_data_root(
    isolate_user_data_root: Path,
) -> None:
    paths = registry_cache_paths("r/python.lang.security.audit.eval-detected.eval-detected")

    cache_dir = isolate_user_data_root / "semgrep"
    assert (
        paths.rules == cache_dir / "r-python.lang.security.audit.eval-detected.eval-detected.yaml"
    )
    assert paths.etag == cache_dir / "r-python.lang.security.audit.eval-detected.eval-detected.etag"


@pytest.mark.parametrize(
    "ruleset",
    [
        "",
        "default",
        "p",
        "p/",
        "x/default",
        "p/..",
        "p/.",
        "p/../default",
        "p/a/b",
        "p//default",
        "../p/default",
        "p/de fault",
        "p/default?x=1",
        "p/default#frag",
        "p/default%2F..",
        "p/dé",
        "https://example.com/p/default",
    ],
)
def test_a_ruleset_name_outside_the_registry_grammar_is_refused_before_any_request(
    ruleset: str, stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    with pytest.raises(ValidationError) as refused:
        fetch_registry_ruleset(ruleset)

    assert refused.value.error_code == "VALIDATION_ERROR"
    assert refused.value.exit_code == 1
    assert stub_web.requested == []
    assert not (isolate_user_data_root / "semgrep").exists()


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(404, id="registry-refuses-the-name"),
        pytest.param(500, id="registry-fails"),
        pytest.param(304, id="registry-says-unchanged-to-a-fetch-that-held-nothing"),
    ],
)
def test_a_refused_download_names_the_url_and_caches_nothing(
    status: int, stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    stub_web.routes[DEFAULT_RULESET_URL] = (status, {}, b"")

    with pytest.raises(ToolDownloadError) as refused:
        fetch_registry_ruleset("p/default")

    assert refused.value.error_code == "TOOL_DOWNLOAD_ERROR"
    assert refused.value.details["url"] == DEFAULT_RULESET_URL
    assert refused.value.details["reason"] == f"the registry answered HTTP {status}"
    assert not (isolate_user_data_root / "semgrep").exists()


def test_a_redirect_is_refused_and_not_followed(
    stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    elsewhere = "https://example.com/rules.yaml"
    stub_web.redirect(DEFAULT_RULESET_URL, elsewhere)
    serve(stub_web, FIRST_RULESET, url=elsewhere)

    with pytest.raises(ToolDownloadError) as refused:
        fetch_registry_ruleset("p/default")

    assert refused.value.details["reason"] == "the registry answered HTTP 302"
    assert stub_web.requested == [DEFAULT_RULESET_URL]
    assert not (isolate_user_data_root / "semgrep").exists()


@pytest.mark.parametrize("failure", [httpx2.ReadTimeout, httpx2.ConnectError])
def test_a_transport_failure_is_a_refused_download_that_caches_nothing(
    failure: type[httpx2.TransportError],
    stub_web: StubWeb,
    isolate_user_data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise failure("no answer", request=request)

    monkeypatch.setattr(stub_web, "handle", fail)

    with pytest.raises(ToolDownloadError) as refused:
        fetch_registry_ruleset("p/default")

    assert refused.value.details["url"] == DEFAULT_RULESET_URL
    assert refused.value.details["reason"] == f"{failure.__name__}: no answer"
    assert not (isolate_user_data_root / "semgrep").exists()


def test_a_ruleset_over_the_size_cap_is_refused_and_caches_nothing(
    stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    serve(stub_web, FIRST_RULESET)

    with pytest.raises(ToolDownloadError) as refused:
        fetch_registry_ruleset("p/default", max_bytes=len(FIRST_RULESET) - 1)

    assert refused.value.details["reason"] == (
        f"the ruleset is larger than {len(FIRST_RULESET) - 1} bytes"
    )
    assert not (isolate_user_data_root / "semgrep").exists()


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"<html><body>Sign in</body></html>", id="html-page"),
        pytest.param(b"rules: [", id="broken-yaml"),
        pytest.param(b"- id: not-a-mapping\n", id="a-list"),
        pytest.param(b"rules: []\n", id="no-rules"),
        pytest.param(b"rules: {id: not-a-list}\n", id="rules-that-are-not-a-list"),
        pytest.param(b"rules:\n- pattern: no_id(...)\n", id="rule-without-id"),
        pytest.param(b"rules:\n- id: 7\n", id="rule-with-a-number-for-an-id"),
        pytest.param(b"rules:\n- just a string\n", id="rule-that-is-not-a-mapping"),
        pytest.param(b"\xff\xfe", id="not-text"),
        pytest.param(b"rules: " + b"[" * 100_000 + b"]" * 100_000, id="nested-past-the-loader"),
    ],
)
def test_a_body_that_is_not_a_ruleset_is_refused_and_caches_nothing(
    body: bytes, stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    serve(stub_web, body)

    with pytest.raises(ValidationError) as refused:
        fetch_registry_ruleset("p/default")

    assert refused.value.error_code == "VALIDATION_ERROR"
    assert refused.value.message == NOT_A_RULESET
    assert refused.value.details["url"] == DEFAULT_RULESET_URL
    assert not (isolate_user_data_root / "semgrep").exists()


def test_a_body_nested_past_the_loader_leaves_the_earlier_cache_and_exits_with_the_refusal(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """The loader overflows its stack on 200 KB of brackets, far under the size cap."""
    serve(stub_web, FIRST_RULESET)
    fetch_registry_ruleset("p/default")
    paths = registry_cache_paths("p/default")
    serve(stub_web, b"rules: " + b"[" * 100_000 + b"]" * 100_000, etag=SECOND_ETAG)

    result = cli("review", "rules", "fetch")

    assert result.exit_code == 1
    assert result.output == f"✗ {NOT_A_RULESET}\n"
    assert (paths.rules.read_bytes(), paths.etag.read_text(encoding="utf-8")) == (
        FIRST_RULESET,
        FIRST_ETAG,
    )


def test_a_refused_download_leaves_the_earlier_cache_as_it_was(stub_web: StubWeb) -> None:
    serve(stub_web, FIRST_RULESET)
    fetch_registry_ruleset("p/default")
    paths = registry_cache_paths("p/default")
    stub_web.routes[DEFAULT_RULESET_URL] = (503, {}, b"")

    with pytest.raises(ToolDownloadError):
        fetch_registry_ruleset("p/default")

    assert (paths.rules.read_bytes(), paths.etag.read_text(encoding="utf-8")) == (
        FIRST_RULESET,
        FIRST_ETAG,
    )


def test_a_refetch_asks_whether_the_cached_ruleset_changed_and_replaces_it_when_it_did(
    stub_web: StubWeb,
) -> None:
    serve(stub_web, FIRST_RULESET)
    fetch_registry_ruleset("p/default")
    serve(stub_web, SECOND_RULESET, SECOND_ETAG)

    cached = fetch_registry_ruleset("p/default")

    paths = registry_cache_paths("p/default")
    assert cached == 1
    assert validators_sent(stub_web) == [None, FIRST_ETAG]
    assert paths.rules.read_bytes() == SECOND_RULESET
    assert paths.etag.read_text(encoding="utf-8") == SECOND_ETAG


def test_an_unchanged_ruleset_answers_not_modified_and_nothing_is_rewritten(
    stub_web: StubWeb,
) -> None:
    serve(stub_web, FIRST_RULESET)
    fetch_registry_ruleset("p/default")
    paths = registry_cache_paths("p/default")
    written = [(path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
    stub_web.routes[DEFAULT_RULESET_URL] = (304, {"etag": FIRST_ETAG}, b"")

    cached = fetch_registry_ruleset("p/default")

    assert cached is None
    assert validators_sent(stub_web) == [None, FIRST_ETAG]
    assert [(path.stat().st_ino, path.stat().st_mtime_ns) for path in paths] == written
    assert (paths.rules.read_bytes(), paths.etag.read_text(encoding="utf-8")) == (
        FIRST_RULESET,
        FIRST_ETAG,
    )


def test_an_etag_without_its_ruleset_is_not_sent_since_not_modified_would_leave_nothing(
    stub_web: StubWeb,
) -> None:
    serve(stub_web, FIRST_RULESET)
    fetch_registry_ruleset("p/default")
    paths = registry_cache_paths("p/default")
    paths.rules.unlink()

    assert fetch_registry_ruleset("p/default") == 2
    assert validators_sent(stub_web) == [None, None]
    assert paths.rules.read_bytes() == FIRST_RULESET


def test_a_ruleset_the_registry_serves_without_an_etag_drops_the_earlier_one(
    stub_web: StubWeb,
) -> None:
    serve(stub_web, FIRST_RULESET)
    fetch_registry_ruleset("p/default")
    serve(stub_web, SECOND_RULESET, etag=None)

    fetch_registry_ruleset("p/default")

    paths = registry_cache_paths("p/default")
    assert paths.rules.read_bytes() == SECOND_RULESET
    assert not paths.etag.exists()


def test_the_ruleset_is_written_before_its_etag_so_an_interrupted_fetch_costs_a_refetch(
    stub_web: StubWeb,
) -> None:
    """A directory where the etag goes stands for the write that stops after the ruleset."""
    serve(stub_web, FIRST_RULESET)
    paths = registry_cache_paths("p/default")
    paths.etag.mkdir(parents=True)

    with pytest.raises(OSError, match="Is a directory"):
        fetch_registry_ruleset("p/default")

    assert paths.rules.read_bytes() == FIRST_RULESET
    paths.etag.rmdir()
    assert fetch_registry_ruleset("p/default") == 2
    assert validators_sent(stub_web) == [None, None]
    assert paths.etag.read_text(encoding="utf-8") == FIRST_ETAG


def test_the_dry_run_of_a_fetch_lists_the_request_and_both_paths_and_makes_none(
    cli: Callable[..., Any], stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    result = cli("review", "rules", "fetch", "--dry-run")

    cache_dir = isolate_user_data_root / "semgrep"
    assert result.exit_code == 0
    assert result.output == (
        "Dry run: no request was made. rules fetch would make these requests, in order:\n"
        f"  1. GET {DEFAULT_RULESET_URL}\n"
        f"It would then write the ruleset to {cache_dir / 'p-default.yaml'} "
        f"and its ETag to {cache_dir / 'p-default.etag'}.\n"
    )
    assert stub_web.requested == []
    assert not cache_dir.exists()


def test_the_fetch_command_caches_the_named_ruleset_and_reports_what_it_holds(
    cli: Callable[..., Any], stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    url = "https://semgrep.dev/c/p/python"
    serve(stub_web, FIRST_RULESET, url=url)

    result = cli("review", "rules", "fetch", "--ruleset", "p/python")

    cache_dir = isolate_user_data_root / "semgrep"
    assert result.exit_code == 0
    assert result.output == f"✓ Cached 2 rule(s) of p/python in {cache_dir / 'p-python.yaml'}.\n"
    assert stub_web.requested == [url]
    assert (cache_dir / "p-python.yaml").read_bytes() == FIRST_RULESET


def test_the_fetch_command_reports_a_cached_ruleset_the_registry_says_is_unchanged(
    cli: Callable[..., Any], stub_web: StubWeb, isolate_user_data_root: Path
) -> None:
    serve(stub_web, FIRST_RULESET)
    cli("review", "rules", "fetch")
    stub_web.routes[DEFAULT_RULESET_URL] = (304, {"etag": FIRST_ETAG}, b"")

    result = cli("review", "rules", "fetch")

    cache_dir = isolate_user_data_root / "semgrep"
    assert result.exit_code == 0
    assert (
        result.output == f"✓ The cached p/default in {cache_dir / 'p-default.yaml'} is current.\n"
    )
    assert validators_sent(stub_web) == [None, FIRST_ETAG]


def test_the_fetch_command_exits_with_the_error_of_a_refused_download(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    result = cli("review", "rules", "fetch")

    assert result.exit_code == 1
    assert result.output == (
        f"✗ Tool download failed for '{DEFAULT_RULESET_URL}': the registry answered HTTP 404\n"
    )


def test_the_fetch_command_refuses_a_ruleset_outside_the_registry_grammar(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    result = cli("review", "rules", "fetch", "--ruleset", "p/..")

    assert result.exit_code == 1
    assert result.output == (
        "✗ 'p/..' is not a Semgrep registry id. Write the kind (p, r, s), a slash and one name "
        "with no path, query or fragment in it, such as p/default.\n"
    )
    assert stub_web.requested == []
