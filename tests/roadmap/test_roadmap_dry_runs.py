"""`devops roadmap` dry runs make no request, and list the requests a run makes (#412, #1125).

Each job's `--dry-run` returns its real result type marked as a dry run, holding the ordered
`PlannedRequest`s the store's own argument builders give, so a real run's `gh` argv sequence
matches its plan. The guards here fail the test on any store, runner, process or socket a dry
run opens; one probe runs each job's dry run through the real entry point with connections,
DNS and process starts refused, and fake `gh`, `git` and `kubectl` on PATH that log each call.
"""

from __future__ import annotations

import json
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
from devops_cli.roadmap.github_store import (
    comments_endpoint,
    issue_args,
    issues_endpoint,
    listing_path,
    milestones_endpoint,
)
from devops_cli.roadmap.request_plan import StoreRequests
from tests.support.fakes.github import API

REPO = "dan-petty/devops-cli"
runner = CliRunner()
JOBS = ("intake", "refine", "alternatives", "stage", "implement")


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
    monkeypatch.setattr(subprocess, "Popen", _fail("started a process"))
    monkeypatch.setattr(socket.socket, "connect", _fail("connected"))
    monkeypatch.setattr(socket, "getaddrinfo", _fail("resolved a name"))
    monkeypatch.setattr(ai_client, "get_llm_client", _fail("called LLM"))
    monkeypatch.setattr("devops_cli.roadmap.refine.get_llm_client", _fail("called LLM"))
    monkeypatch.setattr("devops_cli.roadmap.refine.get_task_model", _fail("called LLM"))
    monkeypatch.setattr("devops_cli.roadmap.stage.get_llm_client", _fail("called LLM"))
    monkeypatch.setattr(
        "devops_cli.roadmap.refine_investigation.firecrawl_search", _fail("called search")
    )
    monkeypatch.setattr("devops_cli.roadmap.alternatives.get_task_model", _fail("called LLM"))


@pytest.mark.parametrize("job", JOBS)
def test_every_jobs_dry_run_makes_no_request_and_lists_the_requests_a_run_makes(
    no_requests: None, job: str
) -> None:
    result = runner.invoke(app, [job, "--repo", REPO, "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "projectV2" in result.output,
        "roadmap.toml" in result.output,
    ) == (0, True, False, False), result.output


def test_refine_dry_run_with_item_makes_no_requests(no_requests: None) -> None:
    """Refining a single item under dry-run makes no GitHub, process, or model call."""
    result = runner.invoke(app, ["refine", "--repo", REPO, "--item", "123", "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "api repos/dan-petty/devops-cli/issues/123" in result.output,
    ) == (0, True, True), result.output


def test_the_explain_dry_run_makes_no_request_and_lists_reads_only(no_requests: None) -> None:
    """`explain` reads GitHub and git and writes nothing, so its plan holds the reads of a run and
    no write (#2911)."""
    result = runner.invoke(app, ["explain", "7", "--repo", REPO, "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "api repos/dan-petty/devops-cli/issues/7" in result.output,
        MESSAGES.roadmap.plan_dry_run_writes in result.output,
    ) == (0, True, True, False), result.output


@pytest.mark.parametrize("job", JOBS)
def test_an_exported_dry_run_wins_over_confirm(no_requests: None, job: str) -> None:
    with patch("devops_cli.commands.roadmap.is_dry_run", return_value=True):
        result = runner.invoke(app, [job, "--repo", REPO, "--confirm"])
    assert (result.exit_code, "Dry run: no request was made" in result.output) == (0, True)


@pytest.mark.parametrize(
    ("job", "mode"),
    [
        ("intake", "--plan"),
        ("refine", "--confirm"),
        ("alternatives", "--plan"),
        ("stage", "--plan"),
        ("implement", "--plan"),
    ],
)
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
    ) == ([RefinePlan, IntakePlan], [True, True], (True, True), [True, True])


def test_a_plan_is_built_by_the_stores_own_argument_builders() -> None:
    """The reads a refine plan lists are the argv the store's builders give, with placeholders
    where a read gives the value: the milestones once, then each open milestone's issues, the
    backlog, and every issue for the dependencies a proposal names."""
    from devops_cli.roadmap.refine import dry_run_refine

    planned = [request.argv[1:] for request in dry_run_refine(REPO, ref=None).requests]
    expected = [
        (f"{API}{listing_path(milestones_endpoint(REPO))}",),
        (f"{API}{listing_path(issues_endpoint(REPO, 'milestone=<milestone>&state=all'))}",),
        (f"{API}{listing_path(issues_endpoint(REPO, 'milestone=none&state=open'))}",),
        (f"{API}{listing_path(issues_endpoint(REPO, 'state=all'))}",),
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


def test_a_refine_round_plans_the_record_of_a_comment_the_cap_stops_and_an_item_plan_none() -> None:
    """A round records, on an item that the cap on refine's comments leaves alone, when its
    newest comment was made: a read of the issue, then one `PATCH` of its job record. `--item`
    refines its item at the cap, so its plan records none (#2475)."""
    from devops_cli.roadmap.request_plan import refine_requests

    _, writes = refine_requests(REPO, None)
    _, single = refine_requests(REPO, None, item=7)
    capped = MESSAGES.roadmap.plan_conditions["capped"]
    assert (
        [_shape(r) for r in writes if r.condition == capped],
        [r for r in single if r.condition == capped],
    ) == ([f"api repos/{REPO}/issues/<item>", "issue patch"], [])


def test_a_refine_plan_lists_the_intake_requests_of_a_deferred_part() -> None:
    """A round and a refine of one item each list the requests of one new intake candidate, and
    the record of its number, when the proposal defers a part (#2423)."""
    from devops_cli.roadmap.intake_requests import planned_requests
    from devops_cli.roadmap.request_plan import refine_requests

    deferred = MESSAGES.roadmap.plan_conditions["deferred"]
    part_reads, part_writes = planned_requests(["<deferred part>"], repo=REPO, ref=None, new=True)
    shapes = []
    for item in (None, 7):
        reads, writes = refine_requests(REPO, None, item=item)
        shapes.append(
            (
                [r.argv for r in reads if deferred in r.condition],
                [r.argv for r in writes if deferred in r.condition],
            )
        )
    target = f"api repos/{REPO}/issues/<item>"
    assert (
        [listed for listed, _ in shapes],
        [listed[: len(part_writes)] for _, listed in shapes],
        [_shape(r) for r in refine_requests(REPO, None)[1] if r.condition == deferred][-2:],
    ) == (
        [[r.argv for r in part_reads]] * 2,
        [[r.argv for r in part_writes]] * 2,
        [target, "issue patch"],
    )


def _shape(request: PlannedRequest) -> str:
    """What a planned request is: a `PATCH` of an issue, or its first arguments."""
    args = list(request.argv[1:])
    if args[:3] == ["api", "-X", "PATCH"]:
        return "issue patch"
    return " ".join(args[:3])


def test_a_field_write_plans_one_read_of_its_issue_and_one_patch() -> None:
    """A field or mark write lists the read of its issue, then one `PATCH` of the issue's labels
    and body, its stdin the JSON that `gh api --input -` sends (ADR 0016)."""
    store = StoreRequests(REPO)
    plans = {
        "set_field": store.set_field("#7", "Value"),
        "any_field": store.set_field("#7"),
        "set_marks": store.set_marks("#7"),
    }
    read = f"api repos/{REPO}/issues/7"
    assert (
        {name: [_shape(r) for r in plan] for name, plan in plans.items()},
        [plan[-1].argv[-2:] for plan in plans.values()],
        [sorted(json.loads(plan[-1].stdin or "{}")) for plan in plans.values()],
    ) == (
        {
            "set_field": [read, "issue patch"],
            "any_field": [read, "issue patch"],
            "set_marks": [read, "issue patch"],
        },
        [("--input", "-")] * 3,
        [["body", "labels"], ["body", "labels"], ["body"]],
    )


def test_no_roadmap_plan_lists_a_request_to_a_project_board() -> None:
    """Every job's plan: intake, a refine round, a refine of one item and a return. No request
    is a `gh project` command, names `projectV2` or reads `.github/roadmap.toml` (ADR 0016)."""
    from devops_cli.roadmap.intake import dry_run_intake
    from devops_cli.roadmap.request_plan import refine_requests
    from devops_cli.roadmap.return_item import dry_run_return

    intake = dry_run_intake(REPO, ref="main")
    reads, writes = refine_requests(REPO, None)
    single_reads, single_writes = refine_requests(REPO, None, item=7)
    returned = dry_run_return(REPO, 7)
    plans = [
        *reads,
        *writes,
        *single_reads,
        *single_writes,
        *intake.requests,
        *intake.writes,
        *returned[0],
        *returned[1],
    ]
    named = [
        request.argv
        for request in plans
        if request.argv[1:2] == ("project",)
        or any(word in " ".join(request.argv) for word in ("projectV2", "roadmap.toml"))
    ]
    assert named == []


def test_each_field_write_of_a_placement_reads_its_issue_first() -> None:
    """A placement writes Status, Value, Effort and Priority, each a read of the issue and then
    one `PATCH`, and reads no listing between them."""
    from devops_cli.roadmap.intake import dry_run_intake

    writes = [r for r in dry_run_intake(REPO, ref="main", issues=(7,)).writes if r.argv]
    patches = [i for i, r in enumerate(writes) if _shape(r) == "issue patch"]
    assert (
        len(patches),
        [_shape(writes[i - 1]) for i in patches],
        [r for r in writes if r.argv[:1] == ("GET",)],
    ) == (4, [f"api repos/{REPO}/issues/7"] * 4, [])


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


def test_the_alternatives_dry_run_lists_the_gh_command_and_the_url_of_each_request() -> None:
    """The plan names the exact `gh` command of each GitHub request, and the method and the URL
    of each Firecrawl and PyPI request (#2650)."""
    from devops_cli.roadmap.alternatives import AlternativesPlan, dry_run_alternatives

    plan = dry_run_alternatives(REPO, item=7)
    argvs = [request.argv for request in plan.requests + plan.write_requests if request.argv]
    assert (
        type(plan),
        plan.dry_run,
        plan.has_writes,
        ("POST", "https://api.firecrawl.dev/v2/search") in argvs,
        ("GET", "https://pypi.org/pypi/<package>/json") in argvs,
        ("gh", "api", "repos/<owner/name>") in argvs,
        ("gh", "api", "repos/<owner/name>/releases/latest") in argvs,
        ("gh", "api", f"repos/{REPO}/issues/7") in argvs,
        {request.method for request in plan.requests if not request.argv},
    ) == (AlternativesPlan, True, True, True, True, True, True, True, {"model call"})


def test_the_alternatives_dry_run_names_no_project_board() -> None:
    from devops_cli.roadmap.request_plan import alternatives_requests

    reads, writes = alternatives_requests(REPO)
    named = [
        request.argv
        for request in (*reads, *writes)
        if request.argv[1:2] == ("project",)
        or any(word in " ".join(request.argv) for word in ("projectV2", "roadmap.toml"))
    ]
    assert named == []


def test_the_implement_plan_names_the_comment_endpoint_and_the_lease_that_the_job_uses() -> None:
    from devops_cli.roadmap.request_plan import implement_requests

    _, writes = implement_requests(REPO)

    comment = next(
        request
        for request in writes
        if request.argv[:1] == ("POST",) and request.argv[1].endswith("/comments")
    )
    push = next(
        request
        for request in writes
        if request.argv[3:4] == ("push",)
        and "--force-with-lease=<branch>:<remote tip>" in request.argv
    )
    assert (comment.argv[1], push.argv[4:]) == (
        f"{API}/repos/{REPO}/issues/<pull request>/comments",
        ("--force-with-lease=<branch>:<remote tip>", "origin", "<branch>"),
    )


def test_the_stage_plan_reads_the_change_folders_of_the_default_branch_with_one_ls_tree() -> None:
    from devops_cli.roadmap.request_plan import stage_requests

    reads, _ = stage_requests(REPO)

    trees = [request.argv for request in reads if "ls-tree" in request.argv]
    assert trees == [
        (
            "git",
            "-C",
            "<model-clone>",
            "ls-tree",
            "--name-only",
            "origin/main",
            "openspec/changes/",
            "openspec/changes/archive/",
        )
    ]


def test_the_stage_plan_reads_the_tracked_files_of_the_clone_once_for_the_round() -> None:
    from devops_cli.roadmap.request_plan import stage_requests

    reads, _ = stage_requests(REPO)

    (listing,) = [request for request in reads if "ls-files" in request.argv]
    assert listing.argv == ("git", "-C", "<model-clone>", "ls-files", "-z")
    assert listing.repeat == ""
    assert listing.condition


def test_the_implement_plan_reads_the_default_branch_and_lists_the_writes_of_a_planned_item() -> (
    None
):
    from devops_cli.roadmap.request_plan import implement_requests

    reads, writes = implement_requests(REPO)

    read_lines = [" ".join(request.argv) for request in reads]
    write_lines = [" ".join(request.argv) for request in writes]
    assert any("ls-tree --name-only origin/main openspec/changes/" in line for line in read_lines)
    assert any("show origin/main:openspec/changes/<change>/tasks.md" in line for line in read_lines)
    assert any(
        "worktree add --no-track -b <new branch> <worktree> origin/main" in line
        for line in write_lines
    )
    assert any("push -u origin <new branch>" in line for line in write_lines)
    assert f"POST {API}/repos/{REPO}/pulls" in write_lines
