"""Tests for `devops research advisories` (#3898, #3987)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.research.advisories import find_advisories
from devops_cli.research.inventory import read_inventory
from devops_cli.research.kev import KevClient
from devops_cli.security.vulnerability_lookup import OSVClient
from tests.research.github_recording import (
    GITHUB_REPO,
    serve_recorded_github,
    serve_recorded_kev,
)
from tests.research.osv_recording import RECORDED_REPO, serve_recorded_osv
from tests.support.fakes.http import WebFake
from tests.support.github_identity import PINNED_GITHUB_TOKEN


def test_advisories_json_is_the_report_of_the_root(cli: Callable[..., Any], web: WebFake) -> None:
    serve_recorded_osv(web)
    serve_recorded_kev(web)

    result = cli("research", "advisories", "--root", RECORDED_REPO, "--json")

    expected = find_advisories(read_inventory(RECORDED_REPO), OSVClient())
    assert (result.exit_code, json.loads(result.output)) == (
        0,
        json.loads(expected.model_dump_json()),
    )


def test_advisories_table_lists_each_finding_and_the_coverage(
    cli: Callable[..., Any], web: WebFake
) -> None:
    serve_recorded_osv(web)
    serve_recorded_kev(web)

    result = cli("research", "advisories", "--root", RECORDED_REPO)

    assert result.exit_code == 0
    for text in ("GHSA-8q59-q68h-6hv4", "pyyaml", "5.3", "CRITICAL", "5.4", "8 advisories"):
        assert text in result.output


def test_advisories_exits_1_after_it_prints_a_failed_lookup(
    cli: Callable[..., Any], web: WebFake
) -> None:
    web.respond("POST", OSVClient.BATCH_URL, 503, {})

    result = cli("research", "advisories", "--root", RECORDED_REPO, "--json")

    report = json.loads(result.output)
    assert (result.exit_code, report["summary"]["failed"], report["findings"]) == (1, 3, [])


def test_advisories_dry_run_lists_the_requests_and_sends_none(
    cli: Callable[..., Any], web: WebFake
) -> None:
    result = cli("research", "advisories", "--root", RECORDED_REPO, "--dry-run")

    assert result.exit_code == 0
    assert (OSVClient.BATCH_URL in result.output, web.recorded) == (True, [])


def test_advisories_table_flags_an_exploited_finding(cli: Callable[..., Any], web: WebFake) -> None:
    serve_recorded_github(web)
    serve_recorded_kev(web)

    result = cli("research", "advisories", "--root", GITHUB_REPO)

    assert result.exit_code == 0
    for text in ("GHSA-mrrh-fwg8-r2c3", "yes", "GHSA-3gph-6c29-p29v", "1 are in the CISA KEV list"):
        assert text in result.output


def test_advisories_sends_the_token_to_api_github_com_only(
    cli: Callable[..., Any], web: WebFake
) -> None:
    serve_recorded_github(web)
    serve_recorded_kev(web)

    cli("research", "advisories", "--root", GITHUB_REPO, "--json")

    sent = {
        request.url.split("/")[2]: request.headers.get("authorization") for request in web.recorded
    }
    assert sent == {"api.github.com": f"Bearer {PINNED_GITHUB_TOKEN}", "www.cisa.gov": None}


@pytest.mark.usefixtures("no_github_identity")
def test_advisories_runs_without_a_token_and_sends_none(
    cli: Callable[..., Any], web: WebFake
) -> None:
    serve_recorded_github(web)
    serve_recorded_kev(web)

    result = cli("research", "advisories", "--root", GITHUB_REPO, "--json")

    assert (
        result.exit_code,
        len(json.loads(result.output)["findings"]),
        [r for r in web.recorded if "authorization" in r.headers],
    ) == (0, 3, [])


def test_advisories_exits_1_after_it_prints_a_kev_list_it_cannot_read(
    cli: Callable[..., Any], web: WebFake
) -> None:
    serve_recorded_github(web)
    web.respond("GET", KevClient.URL, 503, {})

    result = cli("research", "advisories", "--root", GITHUB_REPO, "--json")

    report = json.loads(result.output)
    assert (result.exit_code, report["kev_failure"], len(report["findings"])) == (
        1,
        "CISA KEV returned status 503",
        3,
    )


def test_advisories_dry_run_lists_the_github_and_kev_requests(
    cli: Callable[..., Any], web: WebFake
) -> None:
    result = cli("research", "advisories", "--root", GITHUB_REPO, "--dry-run")

    assert result.exit_code == 0
    for text in ("api.github.com/advisories", "qdrant/qdrant/security-advisories", KevClient.URL):
        assert text in result.output
    assert web.recorded == []
