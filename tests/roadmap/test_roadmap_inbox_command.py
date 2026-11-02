"""`devops roadmap inbox`: the report, the failure, and the dry run (#2915)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.roadmap.github_store import listing_path, pulls_endpoint
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField, StageRecordKey, encode_job_record, with_record
from tests.support.fakes.github import API

REPO = "example/roadmap"


def _plan_pull(store: InMemoryRoadmapStore) -> int:
    pull = store.seed_pull("plan", head_ref="feat/1-plan")
    block = encode_job_record({}, {StageRecordKey.PR: str(pull)})
    store.seed_issue("work", body=with_record("", block), fields={ItemField.PRIORITY: "P2-Medium"})
    return pull


def test_the_report_lists_a_ready_plan_pull_request_with_its_step(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    roadmap_store.seed_file(CONST_ROADMAP_LABELS_PATH, "- name: type/bug\n  color: D73A4A\n")
    roadmap_store.seed_label("type/bug", "D73A4A")
    pull = _plan_pull(roadmap_store)

    result = cli("roadmap", "inbox", "--repo", REPO)

    assert result.exit_code == 0, result.output
    assert f"#{pull}" in result.stdout
    assert "Review it, then merge it (G1)" in result.stdout
    assert roadmap_store.job_writes() == []


def test_a_repository_without_the_labels_file_exits_1_and_says_so(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli("roadmap", "inbox", "--repo", REPO)
    assert (result.exit_code, "Could not read the inbox" in result.output) == (1, True)
    assert ".github/labels.yml" in result.output


def test_the_dry_run_opens_no_store_and_lists_the_reads_and_no_write(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    result = cli("roadmap", "inbox", "--repo", REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    assert roadmap_store_repos == []
    assert "Dry run: no request was made" in result.output
    assert f"{API}{listing_path(pulls_endpoint(REPO))}" in result.output
    assert "state=all" not in result.output
    assert "PATCH" not in result.output


@pytest.mark.parametrize("flag", ["--confirm", "--plan"])
def test_the_inbox_takes_no_write_option(cli: Callable[..., Any], flag: str) -> None:
    assert cli("roadmap", "inbox", "--repo", REPO, flag).exit_code == 2
