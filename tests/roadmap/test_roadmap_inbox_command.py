"""`devops roadmap inbox`: the report, the failure, and the dry run (#2915)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.roadmap.stores.github_store import listing_path, pulls_endpoint
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
    StageRecordKey,
    encode_job_record,
    with_record,
)
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.github import API
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"


def _plan_pull(store: InMemoryRoadmapStore) -> int:
    pull = store.seed_pull("plan", head_ref="feat/1-plan")
    block = encode_job_record({}, {StageRecordKey.PR: str(pull)})
    store.seed_issue("work", body=with_record("", block), fields={ItemField.PRIORITY: "P2-Medium"})
    return pull


def test_the_report_lists_a_ready_plan_pull_request_with_its_step(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    _seed_labels(roadmap_store)
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


def _seed_labels(store: InMemoryRoadmapStore) -> None:
    store.seed_file(CONST_ROADMAP_LABELS_PATH, "- name: scope/cli\n  color: DCDCD6\n")
    store.seed_label("scope/cli", "DCDCD6")
    for spec in WORKFLOW_LABELS:
        store.seed_label(spec.name, spec.color, spec.description)


def test_without_repo_the_inbox_reads_each_service_repo(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    config(service={"repos": ["example/app", "example/roadmap"]})
    _seed_labels(roadmap_store)

    result = cli("roadmap", "inbox")

    assert result.exit_code == 0, result.output
    assert roadmap_store_repos == ["example/app", "example/roadmap"]
    assert "Nothing waits for a person in example/app." in result.stdout
    assert "Nothing waits for a person in example/roadmap." in result.stdout


def test_with_repo_the_inbox_reads_that_repo_only(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    config(service={"repos": ["example/app", "example/roadmap"]})
    _seed_labels(roadmap_store)

    result = cli("roadmap", "inbox", "--repo", REPO)

    assert result.exit_code == 0, result.output
    assert roadmap_store_repos == [REPO]


def test_without_repo_and_no_service_repos_the_inbox_fails_naming_the_setting(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    roadmap_store_repos: list[str],
) -> None:
    config(service={"repos": []})

    result = cli("roadmap", "inbox")

    assert (result.exit_code, "service.repos" in result.output) == (1, True)
    assert roadmap_store_repos == []


def test_a_service_repo_that_is_not_owner_name_fails_before_any_read(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    roadmap_store_repos: list[str],
) -> None:
    config(service={"repos": ["no-owner"]})

    result = cli("roadmap", "inbox")

    assert (result.exit_code, "service.repos" in result.output) == (1, True)
    assert roadmap_store_repos == []


def test_the_kind_option_keeps_the_lines_of_one_class(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    _seed_labels(roadmap_store)
    split = roadmap_store.seed_issue(
        "big",
        body=with_record("", encode_job_record({}, {RefineRecordKey.NEXT_STEP: "split"})),
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P2-Medium"},
    )

    result = cli("roadmap", "inbox", "--repo", REPO, "--kind", "split")

    assert result.exit_code == 0, result.output
    assert f"#{split}" in result.stdout
    assert "Counts by class: split 1." in result.stdout


def test_an_unknown_kind_is_a_usage_error(cli: Callable[..., Any]) -> None:
    result = cli("roadmap", "inbox", "--repo", REPO, "--kind", "nope")
    assert (result.exit_code, "Invalid value for '--kind'" in result.output) == (2, True)
