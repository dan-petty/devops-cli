"""Tests for `devops research advisories` (#3898)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from devops_cli.research.advisories import find_advisories
from devops_cli.research.inventory import read_inventory
from devops_cli.security.vulnerability_lookup import OSVClient
from tests.research.test_advisories import RECORDED_REPO, serve_recorded_osv
from tests.support.fakes.http import WebFake


def test_advisories_json_is_the_report_of_the_root(cli: Callable[..., Any], web: WebFake) -> None:
    serve_recorded_osv(web)

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
