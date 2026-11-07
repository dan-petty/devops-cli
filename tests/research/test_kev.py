"""Tests for the client of the CISA KEV list, from the recorded answer (#3987)."""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.config.defaults import DEFAULT_KEV_MAX_RESPONSE_BYTES
from devops_cli.research.kev import KevClient
from tests.research.github_recording import serve_recorded_kev
from tests.support.fakes.http import WebFake


def test_the_list_gives_the_cve_ids_of_its_entries(web: WebFake) -> None:
    serve_recorded_kev(web)

    found = KevClient().load()

    assert (found.status, sorted(found.cves)) == ("ok", ["CVE-2025-30066", "CVE-2026-19868"])


def test_the_request_carries_no_token_and_no_contact_data(web: WebFake) -> None:
    serve_recorded_kev(web)

    KevClient().load()

    [request] = web.recorded
    assert (request.method, request.url, "authorization" in request.headers) == (
        "GET",
        KevClient.URL,
        False,
    )


def test_a_reply_over_the_byte_cap_is_a_failed_read(web: WebFake) -> None:
    web.answer(
        KevClient.URL,
        200,
        headers={"content-type": "application/json"},
        body=b" " * (DEFAULT_KEV_MAX_RESPONSE_BYTES + 1),
    )

    found = KevClient().load()

    assert (found.status, found.cves, found.reason) == (
        "failed",
        frozenset(),
        f"CISA KEV answered with more than {DEFAULT_KEV_MAX_RESPONSE_BYTES} bytes",
    )


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example.net/kev.json",
        "http://10.0.0.5/kev.json",
        "http://169.254.169.254/latest/meta-data/",
    ],
    ids=["other-host", "private-address", "metadata-address"],
)
def test_a_redirect_is_a_failed_read_and_gets_no_request(web: WebFake, location: str) -> None:
    web.redirect(KevClient.URL, location)

    found = KevClient().load()

    assert (found.status, found.reason, web.requested) == (
        "failed",
        "CISA KEV returned status 302",
        [KevClient.URL],
    )


def test_a_list_that_cannot_be_read_is_a_failed_read(web: WebFake) -> None:
    web.respond("GET", KevClient.URL, 200, {"vulnerabilities": [{"product": "x"}]})

    assert KevClient().load().status == "failed"


def test_an_error_status_is_a_failed_read(web: WebFake) -> None:
    web.serve(lambda request: httpx2.Response(503))

    assert KevClient().load().reason == "CISA KEV returned status 503"
