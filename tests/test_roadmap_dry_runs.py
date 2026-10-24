"""`devops roadmap` dry runs make no request, and list the requests a run makes (#412, #1125).

Each job's `--dry-run` returns its real result type marked as a dry run, holding the ordered
`PlannedRequest`s the store's own argument builders give, so a real run's `gh` argv sequence
matches its plan. The guards here fail the test on any store, runner, process or socket a dry
run opens; one probe runs each job's dry run through the real entry point with connections,
DNS and process starts refused, and fake `gh`, `git` and `kubectl` on PATH that log each call.
"""

from __future__ import annotations

import os
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store_module
from devops_cli.roadmap.board_read import board_budget_args, board_items_args
from devops_cli.roadmap.github_store import (
    board_fields_args,
    comments_endpoint,
    issue_args,
    issues_endpoint,
    listing_path,
    milestones_endpoint,
)
from devops_cli.roadmap.request_plan import StoreRequests
from tests.support.fakes.github import API

REPO = "dan-petty/devops-cli"
OWNER = "dan-petty"
runner = CliRunner()
JOBS = ("intake", "refine")


# ── No request ────────────────────────────────────────────────────────────────


def _fail(what: str) -> Callable[..., Any]:
    def fail(*args: object, **_: object) -> Any:
        raise AssertionError(f"the dry run {what}: {str(args[:1])[:120]}")

    return fail


@pytest.fixture
def no_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """A roadmap store, a `gh` runner, a process and a socket that fail the test when a dry run
    opens, runs, starts or connects one; the session's socket guard covers the rest."""
    from devops_cli.ai import client as ai_client
    from devops_cli.github import rate_limiter
    from devops_cli.roadmap import github_store

    monkeypatch.setattr(roadmap_store_module, "get_roadmap_store", _fail("opened a store"))
    monkeypatch.setattr(github_store.GitHubRoadmapStore, "_run", _fail("ran gh"))
    monkeypatch.setattr(rate_limiter, "run_gh", _fail("ran gh"))
    monkeypatch.setattr(rate_limiter, "run_subprocess", _fail("started gh"))
    monkeypatch.setattr(rate_limiter, "_burst_protected_subprocess", _fail("started gh"))
    monkeypatch.setattr(subprocess, "Popen", _fail("started a process"))
    monkeypatch.setattr(socket.socket, "connect", _fail("connected"))
    monkeypatch.setattr(socket, "getaddrinfo", _fail("resolved a name"))
    monkeypatch.setattr(ai_client, "get_llm_client", _fail("called LLM"))
    monkeypatch.setattr("devops_cli.roadmap.refine.get_llm_client", _fail("called LLM"))
    monkeypatch.setattr("devops_cli.roadmap.refine.tavily_search", _fail("called search"))


@pytest.mark.parametrize("job", JOBS)
def test_every_jobs_dry_run_makes_no_request_and_lists_the_requests_a_run_makes(
    no_requests: None, job: str
) -> None:
    result = runner.invoke(app, [job, "--repo", REPO, "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "gh api graphql -f 'query=query RoadmapGraphQLBudget" in result.output,
    ) == (0, True, True), result.output


def test_refine_dry_run_with_item_makes_no_requests(no_requests: None) -> None:
    """Refining a single item under dry-run makes no GitHub, process, or model call."""
    result = runner.invoke(app, ["refine", "--repo", REPO, "--item", "123", "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "api repos/dan-petty/devops-cli/issues/123" in result.output,
    ) == (0, True, True), result.output


@pytest.mark.parametrize("job", JOBS)
def test_an_exported_dry_run_wins_over_confirm(no_requests: None, job: str) -> None:
    with patch("devops_cli.commands.roadmap.is_dry_run", return_value=True):
        result = runner.invoke(app, [job, "--repo", REPO, "--confirm"])
    assert (result.exit_code, "Dry run: no request was made" in result.output) == (0, True)


@pytest.mark.parametrize(("job", "mode"), [("intake", "--plan"), ("refine", "--confirm")])
def test_more_than_one_mode_flag_is_refused(no_requests: None, job: str, mode: str) -> None:
    result = runner.invoke(app, [job, "--repo", REPO, "--dry-run", mode])
    assert (result.exit_code, "Pass one of --dry-run" in result.output) == (1, True)


def test_each_dry_run_returns_its_jobs_result_type_marked_as_a_dry_run() -> None:
    from devops_cli.roadmap.intake import IntakePlan, dry_run_intake
    from devops_cli.roadmap.refine import RefinePlan, dry_run_refine

    refined = dry_run_refine(REPO, ref=None)
    taken = dry_run_intake(REPO, ref=None)
    planned = [refined.requests + refined.write_requests, taken.requests + taken.writes]
    assert (
        [type(refined), type(taken)],
        [refined.dry_run, taken.dry_run],
        (refined.has_writes, bool(taken.writes)),
        [
            all(request.argv[:1] in (("gh",), ("GET",)) for request in requests if request.argv)
            for requests in planned
        ],
        [
            requests[-1].argv[-1].endswith("rateLimit { cost limit remaining used resetAt } }")
            for requests in (refined.requests, taken.requests)
        ],
    ) == ([RefinePlan, IntakePlan], [True, True], (True, True), [True, True], [True, True])


def test_a_plan_is_built_by_the_stores_own_argument_builders() -> None:
    """The reads a refine plan lists are the argv the store's builders give, with placeholders
    where a read gives the value: the milestones once, then each open milestone's issues."""
    from devops_cli.roadmap.refine import dry_run_refine

    planned = [request.argv[1:] for request in dry_run_refine(REPO, ref=None).requests]
    expected = [
        board_fields_args(OWNER, "<board>"),
        board_budget_args(OWNER, "<board>", ""),
        board_items_args(OWNER, "<board>", ""),
        board_items_args(OWNER, "<board>", "", after="<cursor>"),
        (f"{API}{listing_path(milestones_endpoint(REPO))}",),
        (f"{API}{listing_path(issues_endpoint(REPO, 'milestone=<milestone>&state=all'))}",),
        (f"{API}{listing_path(issues_endpoint(REPO, 'milestone=none&state=open'))}",),
    ]
    assert [tuple(args) in planned for args in expected] == [True] * len(expected)


@pytest.mark.parametrize(("item", "subject"), [(None, "<item>"), (7, "7")], ids=["round", "item"])
def test_a_refine_plan_reads_each_items_comments_and_each_open_blocker(
    item: int | None, subject: str
) -> None:
    """A refine plan lists the read of each item's comments, which finds a reply since refine's
    last comment, and the read of each open item a blocked item waits on (#1758)."""
    from devops_cli.roadmap.request_plan import refine_requests

    reads, _writes = refine_requests(REPO, None, item=item)
    planned = [request.argv[1:] for request in reads]
    assert (
        (f"{API}{listing_path(comments_endpoint(REPO, subject))}",) in planned,
        tuple(issue_args(REPO, "<blocking item>")) in planned,
    ) == (True, True)


def test_a_refine_round_plans_a_read_of_each_cited_path_and_an_item_plan_none() -> None:
    """A round reads the newest commit that changed each path the block of a waiting item
    cites, when no reply follows refine's last comment. `--item` refines its item whatever
    changed, so its plan reads no path (#2005)."""
    from devops_cli.roadmap.request_plan import refine_requests

    reads, _ = refine_requests(REPO, None)
    single, _ = refine_requests(REPO, None, item=7)
    path_read = ("api", f"repos/{REPO}/commits?path=<cited path>&per_page=1")
    texts = MESSAGES.roadmap
    assert (
        [(r.condition, r.repeat) for r in reads if r.argv[1:] == path_read],
        [r for r in single if r.argv[1:] == path_read],
    ) == ([(texts.plan_conditions["still_waiting"], texts.plan_repeat["block_path"])], [])


def _shape(request: PlannedRequest) -> str:
    """What a planned `gh` command is: a board, card or fields read, an edit by ids, or its
    first arguments."""
    args = list(request.argv[1:])
    query = next((a for a in args if a.startswith("query=")), "")
    names = ("RoadmapBoardCard", "RoadmapBoardBudget", "RoadmapBoardItems", "fields(first")
    found = next((name for name in names if name in query), None)
    if found:
        return found
    if args[:2] == ["project", "item-edit"]:
        return "item-edit by id" if "--id" in args else "item-edit by name"
    return " ".join(args[:2]) if args[0] == "project" else " ".join(args[:3])


def test_a_board_write_plans_its_card_read_and_an_edit_by_node_ids() -> None:
    """A write lists the fields read it makes once a run, then its one card and the edits by
    node ids; never `field-list`, a board page or an edit by URL or field name (#1361)."""
    store = StoreRequests(REPO)
    plans = {
        "set_field": store.set_field("#7", "Value"),
        "any_field": store.set_field("#7"),
        "set_marks": store.set_marks("#7"),
        "add_item": store.add_item("#7"),
    }
    assert {name: [_shape(r) for r in plan] for name, plan in plans.items()} == {
        "set_field": ["fields(first", "RoadmapBoardCard", "item-edit by id", "item-edit by id"],
        "any_field": ["fields(first", "RoadmapBoardCard", "item-edit by id", "item-edit by id"],
        "set_marks": ["fields(first", "RoadmapBoardCard", "item-edit by id"],
        "add_item": [
            "api repos/dan-petty/devops-cli/issues/7",
            "project item-add",
            "RoadmapBoardCard",
            "project item-archive",
        ],
    }


def test_an_add_plans_the_restore_of_the_card_it_names_only_when_that_card_is_archived(
    no_requests: None,
) -> None:
    """The restore is `item-archive --undo` of the card the add names, a GraphQL write under
    its own condition; intake's placement lists it under its add, and the dry run that lists it
    makes no request (#1403)."""
    from devops_cli.roadmap.intake import dry_run_intake

    restore = StoreRequests(REPO).add_item("#7")[-1]
    writes = dry_run_intake(REPO, ref="main", issues=(7,)).writes
    added = next(i for i, r in enumerate(writes) if "item-add" in r.argv)
    archived = MESSAGES.roadmap.plan_conditions["card_archived"]
    assert (
        restore.argv[1:],
        (restore.method, restore.condition),
        _shape(writes[added + 2]),
        archived in writes[added + 2].condition,
        writes[added + 2].target == writes[added].target,
    ) == (
        ("project", "item-archive", "<board>", "--owner", "dan-petty", "--id", "<card id>")
        + ("--undo", "--format", "json"),
        ("GraphQL write", archived),
        "project item-archive",
        True,
        True,
    )


def test_no_roadmap_plan_lists_a_board_command_gh_resolves_by_reading_the_board_first() -> None:
    """Every job's plan: no `field-list`, and every `item-edit` by node ids."""
    from devops_cli.roadmap.intake import dry_run_intake
    from devops_cli.roadmap.request_plan import refine_requests

    intake = dry_run_intake(REPO, ref="main")
    reads, writes = refine_requests(REPO, None)
    single_reads, single_writes = refine_requests(REPO, None, item=7)
    plans = [*reads, *writes, *single_reads, *single_writes, *intake.requests, *intake.writes]
    shapes = {_shape(request) for request in plans if request.argv}
    assert (
        "project field-list" in shapes,
        "item-edit by name" in shapes,
        "item-edit by id" in shapes,
    ) == (
        False,
        False,
        True,
    )


def test_intakes_placement_plans_no_board_read_after_its_add() -> None:
    """A placement writes to the card the add names: after the add, its plan lists that card's
    read, then for each field the card and the edits, and no board page or budget probe."""
    from devops_cli.roadmap.intake import dry_run_intake

    writes = dry_run_intake(REPO, ref="main", issues=(7,)).writes
    added = next(i for i, r in enumerate(writes) if "item-add" in r.argv)
    after = [_shape(r) for r in writes[added:] if r.argv and r.argv[1] in ("api", "project")]
    assert (
        after.count("RoadmapBoardCard"),
        {"RoadmapBoardBudget", "RoadmapBoardItems"} & set(after),
        [t for t in MESSAGES.roadmap.intake_requests if t == "item"],
    ) == (5, set(), [])


# ── Through the real entry point ──────────────────────────────────────────────


@pytest.mark.parametrize("job", JOBS)
def test_a_dry_run_through_the_entry_point_starts_no_process_and_opens_no_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    job: str,
) -> None:
    """`devops_cli.entry.main` runs each job's `--dry-run`, as the `devops` script does, with
    connections, DNS and process starts recorded and refused, and fake `gh`, `git` and
    `kubectl` first on PATH logging any call. The run succeeds, prints its plan, and nothing
    is recorded or logged. It runs in this process, so the CLI's import cost is paid once."""
    from devops_cli.entry import main

    attempts: list[str] = []

    def refuse(what: str) -> Callable[..., Any]:
        def refused(*args: object, **_: object) -> Any:
            attempts.append(f"{what}: {str(args[:2])[:120]}")
            raise OSError(f"the dry-run probe refuses {what}")

        return refused

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, refuse(name))
    monkeypatch.setattr(socket, "getaddrinfo", refuse("getaddrinfo"))
    monkeypatch.setattr(socket, "create_connection", refuse("create_connection"))
    monkeypatch.setattr(subprocess, "Popen", refuse("a process"))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    for tool in ("gh", "git", "kubectl"):
        fake = bin_dir / tool
        fake.write_text(f'#!/bin/sh\necho "{tool} $@" >> {log}\nexit 1\n', encoding="utf-8")
        fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin")
    try:
        main(["roadmap", job, "--dry-run", "--repo", REPO])
        code: object = 0
    except SystemExit as exited:
        code = exited.code or 0
    assert (
        code,
        "Dry run: no request was made" in capsys.readouterr().out,
        attempts,
        log.exists(),
    ) == (0, True, [], False)


def test_intakes_dry_run_shows_the_exact_gh_command_of_every_store_request() -> None:
    """Only the embedding and model calls, which run no `gh`, have no argv (#742, #1125)."""
    from devops_cli.roadmap.intake import dry_run_intake

    plan = dry_run_intake(REPO, ref="main")
    bare = {request.method for request in plan.requests + plan.writes if not request.argv}
    assert bare == {"embedding", "model"}
