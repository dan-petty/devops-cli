"""Tests for the client of the GitHub advisories API, from recorded answers (#3987)."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest

from devops_cli.config.defaults import (
    DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX,
    DEFAULT_GITHUB_ADVISORIES_MAX_PAGES,
    DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES,
)
from devops_cli.http.client import user_agent
from devops_cli.research.github_advisories import GhsaLookup, GitHubAdvisoryClient
from tests.research.github_recording import (
    ACTIONS_URL,
    QDRANT_URL,
    recorded,
    serve_recorded_github,
)
from tests.support.fakes.http import WebFake

CHANGED_FILES = "tj-actions/changed-files"


def test_the_advisories_of_an_action_are_those_that_name_its_package(web: WebFake) -> None:
    serve_recorded_github(web)

    found = GitHubAdvisoryClient().for_packages("actions", [CHANGED_FILES, "actions/checkout"])

    assert (
        sorted(a.ghsa_id for a in found[CHANGED_FILES].advisories),
        found["actions/checkout"].advisories,
    ) == (["GHSA-mcph-m25j-8j63", "GHSA-mrrh-fwg8-r2c3"], [])


def test_the_request_names_the_ecosystem_and_the_packages(web: WebFake) -> None:
    serve_recorded_github(web)

    GitHubAdvisoryClient().for_packages("actions", [CHANGED_FILES, "actions/checkout"])

    [request] = web.recorded
    assert (request.method, request.url.split("?")[0]) == ("GET", ACTIONS_URL)
    params = httpx2.URL(request.url).params
    assert (params["ecosystem"], params["affects"], params["per_page"]) == (
        "actions",
        f"{CHANGED_FILES},actions/checkout",
        "100",
    )


def test_the_advisories_of_a_repository_are_those_it_published(web: WebFake) -> None:
    serve_recorded_github(web)

    found = GitHubAdvisoryClient().for_repository("qdrant/qdrant")

    assert (found.status, [a.ghsa_id for a in found.advisories]) == (
        "ok",
        ["GHSA-frc7-44gm-99qq", "GHSA-3gph-6c29-p29v", "GHSA-f632-vm87-2m2f"],
    )
    [server] = [v for a in found.advisories for v in a.vulnerabilities][0:1]
    assert (server.vulnerable_version_range, server.fixed_version) == ("< 1.20.0", "1.20.0")


def test_a_list_with_more_names_than_a_request_takes_is_read_in_chunks(web: WebFake) -> None:
    web.serve(lambda request: httpx2.Response(200, json=[]))
    names = [f"owner/action-{n}" for n in range(DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX + 1)]

    found = GitHubAdvisoryClient().for_packages("actions", names)

    sizes = [len(httpx2.URL(r.url).params["affects"].split(",")) for r in web.recorded]
    assert (sizes, len(found)) == ([DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX, 1], len(names))


def test_a_chunk_that_fails_fails_its_own_packages_only(web: WebFake) -> None:
    def server(request: httpx2.Request) -> httpx2.Response:
        named = request.url.params["affects"]
        return httpx2.Response(503 if "owner/action-0" in named else 200, json=[])

    web.serve(server)
    names = [f"owner/action-{n}" for n in range(DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX + 1)]

    found = GitHubAdvisoryClient().for_packages("actions", names)

    assert ({found[n].status for n in names[:-1]}, found[names[-1]].status) == ({"failed"}, "ok")


def test_the_token_is_sent_to_api_github_com_only_when_there_is_one(web: WebFake) -> None:
    serve_recorded_github(web)

    GitHubAdvisoryClient(token="token-value").for_repository("qdrant/qdrant")
    GitHubAdvisoryClient().for_repository("qdrant/qdrant")

    with_token, without = (r.headers for r in web.recorded)
    assert (with_token["authorization"], "authorization" in without) == (
        "Bearer token-value",
        False,
    )


def test_the_client_names_itself_without_contact_data(web: WebFake) -> None:
    serve_recorded_github(web)

    GitHubAdvisoryClient(token="token-value").for_repository("qdrant/qdrant")

    [request] = web.recorded
    agent = request.headers["user-agent"]
    assert (agent, "@" in agent, "mailto" in agent.lower()) == (user_agent(), False, False)


def test_a_next_page_is_followed(web: WebFake) -> None:
    pages = recorded("qdrant_security_advisories.json")
    second = f"{QDRANT_URL}?per_page=100&after=cursor"

    def server(request: httpx2.Request) -> httpx2.Response:
        if "after" in request.url.params:
            return httpx2.Response(200, json=pages[2:])
        return httpx2.Response(200, json=pages[:2], headers={"link": f'<{second}>; rel="next"'})

    web.serve(server)

    found = GitHubAdvisoryClient().for_repository("qdrant/qdrant")

    assert (found.status, len(found.advisories), len(web.recorded)) == ("ok", 3, 2)


def test_a_next_page_on_another_host_is_a_failed_read_and_gets_no_request(
    web: WebFake,
) -> None:
    other = "https://evil.example.net/repos/qdrant/qdrant/security-advisories"
    web.serve(
        lambda request: httpx2.Response(200, json=[], headers={"link": f'<{other}>; rel="next"'})
    )

    found = GitHubAdvisoryClient(token="token-value").for_repository("qdrant/qdrant")

    assert (found.status, found.reason, web.requested) == (
        "failed",
        "GitHub named a next page on another host",
        [f"{QDRANT_URL}?per_page=100"],
    )


def test_a_list_over_the_page_limit_is_a_failed_read(web: WebFake) -> None:
    web.serve(
        lambda request: httpx2.Response(
            200, json=[], headers={"link": f'<{QDRANT_URL}?page=next>; rel="next"'}
        )
    )

    found = GitHubAdvisoryClient().for_repository("qdrant/qdrant")

    assert (found.status, found.reason, len(web.recorded)) == (
        "failed",
        f"GitHub listed more than {DEFAULT_GITHUB_ADVISORIES_MAX_PAGES} pages of advisories",
        DEFAULT_GITHUB_ADVISORIES_MAX_PAGES,
    )


_READS: dict[str, Callable[[GitHubAdvisoryClient], GhsaLookup]] = {
    "packages": lambda c: c.for_packages("actions", [CHANGED_FILES])[CHANGED_FILES],
    "repository": lambda c: c.for_repository("qdrant/qdrant"),
}


@pytest.mark.parametrize("read", list(_READS))
def test_a_reply_over_the_byte_cap_is_a_failed_read(web: WebFake, read: str) -> None:
    body = b" " * (DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES + 1)
    web.serve(
        lambda request: httpx2.Response(
            200, headers={"content-type": "application/json"}, content=body
        )
    )

    found = _READS[read](GitHubAdvisoryClient())

    assert (found.status, found.advisories, found.reason) == (
        "failed",
        [],
        f"GitHub answered with more than {DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES} bytes",
    )


@pytest.mark.parametrize("read", list(_READS))
@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example.net/advisories",
        "http://10.0.0.5/advisories",
        "http://169.254.169.254/latest/meta-data/",
    ],
    ids=["other-host", "private-address", "metadata-address"],
)
def test_a_redirect_is_a_failed_read_and_the_token_goes_nowhere_else(
    web: WebFake, read: str, location: str
) -> None:
    web.serve(lambda request: httpx2.Response(302, headers={"location": location}))

    found = _READS[read](GitHubAdvisoryClient(token="token-value"))

    assert (found.status, found.reason, len(web.recorded)) == (
        "failed",
        "GitHub returned status 302",
        1,
    )


def test_a_rate_limited_read_is_a_failed_read_and_no_clean_package(web: WebFake) -> None:
    web.serve(
        lambda request: httpx2.Response(
            403, headers={"x-ratelimit-remaining": "0"}, json={"message": "rate limit"}
        )
    )

    found = GitHubAdvisoryClient().for_packages("actions", [CHANGED_FILES])[CHANGED_FILES]

    assert (found.status, found.reason, found.advisories) == (
        "failed",
        "GitHub returned status 403",
        [],
    )


def test_a_reply_that_is_no_list_of_advisories_is_a_failed_read(web: WebFake) -> None:
    web.serve(lambda request: httpx2.Response(200, content=json.dumps({"message": "x"})))

    found = GitHubAdvisoryClient().for_repository("qdrant/qdrant")

    assert found.status == "failed"
