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
import re
import socket
import subprocess
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.config.constants import CONST_ROADMAP_RENDER_BOARD_FILTER
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store_module
from devops_cli.roadmap.board_read import board_budget_args, board_items_args
from devops_cli.roadmap.config import open_roadmap
from devops_cli.roadmap.github_store import (
    board_fields_args,
    default_branch_args,
    issues_endpoint,
    listing_page_args,
)
from devops_cli.roadmap.migrate import MigrationPlan, dry_run_migration
from devops_cli.roadmap.render import RenderedRoadmap, dry_run_render, render
from devops_cli.roadmap.reprioritize import (
    ReprioritizationPlan,
    dry_run_reprioritization,
    plan_reprioritization,
)
from devops_cli.roadmap.request_plan import (
    StoreRequests,
    close_requests,
    is_page_repeat,
    migrate_requests,
    render_requests,
    reprioritize_requests,
)
from tests.roadmap_board_fake import BOARD_READ, BoardServer, budget_reply
from tests.test_roadmap_board_read import _fields_reply, _rest_pages, board_of, issues_of

REPO = "dan-petty/devops-cli"
OWNER = "dan-petty"
NOW = datetime(2026, 10, 4, tzinfo=UTC)
runner = CliRunner()
JOBS = ("reprioritize", "migrate", "render", "intake", "close")


# ── No request ────────────────────────────────────────────────────────────────


def _fail(what: str) -> Callable[..., Any]:
    def fail(*args: object, **_: object) -> Any:
        raise AssertionError(f"the dry run {what}: {str(args[:1])[:120]}")

    return fail


@pytest.fixture
def no_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """A roadmap store, a `gh` runner, a process and a socket that fail the test when a dry run
    opens, runs, starts or connects one; the session's socket guard covers the rest."""
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


@pytest.mark.parametrize("job", ["reprioritize", "migrate"])
def test_an_exported_dry_run_wins_over_confirm(no_requests: None, job: str) -> None:
    with patch("devops_cli.commands.roadmap.is_dry_run", return_value=True):
        result = runner.invoke(app, [job, "--repo", REPO, "--confirm"])
    assert (result.exit_code, "Dry run: no request was made" in result.output) == (0, True)


@pytest.mark.parametrize("job", ["reprioritize", "migrate", "render"])
def test_more_than_one_mode_flag_is_refused(no_requests: None, job: str) -> None:
    result = runner.invoke(app, [job, "--repo", REPO, "--dry-run", "--plan"])
    assert (result.exit_code, "Pass one of --dry-run" in result.output) == (1, True)


def test_each_dry_run_returns_its_jobs_result_type_marked_as_a_dry_run() -> None:
    reprioritized = dry_run_reprioritization(REPO, ref="main", now=NOW)
    migrated = dry_run_migration(REPO, ref=None)
    rendered = dry_run_render(REPO, ref=None)
    results: list[Any] = [reprioritized, migrated, rendered]
    planned = [r.requests + getattr(r, "write_requests", ()) for r in results]
    assert (
        [type(result) for result in results],
        [result.dry_run for result in results],
        (reprioritized.has_writes, migrated.writes, rendered.text),
        [all(request.argv[:1] == ("gh",) for request in requests) for requests in planned],
        [bool(result.write_requests) for result in results[:2]],
        [
            requests[-1].argv[-1].endswith("rateLimit { cost limit remaining used resetAt } }")
            for requests in (r.requests for r in results)
        ],
    ) == (
        [ReprioritizationPlan, MigrationPlan, RenderedRoadmap],
        [True, True, True],
        (False, (), ""),
        [True, True, True],
        [True, True],
        [True, True, True],
    )


def test_a_plan_is_built_by_the_stores_own_argument_builders() -> None:
    """The reads a reprioritize plan lists are the argv the store's builders give, with
    placeholders where a read gives the value."""
    planned = [
        request.argv[1:] for request in dry_run_reprioritization(REPO, ref=None, now=NOW).requests
    ]
    expected = [
        board_fields_args(OWNER, "<board>"),
        board_budget_args(OWNER, "<board>", ""),
        board_items_args(OWNER, "<board>", ""),
        board_items_args(OWNER, "<board>", "", after="<cursor>"),
        listing_page_args(issues_endpoint(REPO), "<n>"),
        default_branch_args(REPO),
    ]
    assert all(tuple(args) in planned for args in expected)


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
        "release": store.set_field("#7", "Release"),
        "set_marks": store.set_marks("#7"),
        "add_item": store.add_item("#7"),
        "set_card_field": store.set_card_field(),
        "remove_card": store.remove_card(),
    }
    assert {name: [_shape(r) for r in plan] for name, plan in plans.items()} == {
        "set_field": ["fields(first", "RoadmapBoardCard", "item-edit by id", "item-edit by id"],
        "release": [
            "fields(first",
            "api repos/dan-petty/devops-cli/milestones?state=all&per_page=100&page=<n>",
            "RoadmapBoardCard",
            "item-edit by id",
            "api -X PATCH",
        ],
        "set_marks": ["fields(first", "RoadmapBoardCard", "item-edit by id"],
        "add_item": [
            "api repos/dan-petty/devops-cli/issues/7",
            "project item-add",
            "RoadmapBoardCard",
        ],
        "set_card_field": [
            "fields(first",
            "RoadmapBoardCard",
            "item-edit by id",
            "item-edit by id",
        ],
        "remove_card": ["RoadmapBoardCard", "project item-delete"],
    }


def test_the_run_record_card_a_run_creates_is_written_with_no_read_after_its_create() -> None:
    plan = StoreRequests(REPO).set_run_record()
    create = next(i for i, r in enumerate(plan) if "item-create" in r.argv)
    assert (
        [_shape(r) for r in plan[create:]],
        plan[create].argv[-2:],
        [bool(r.condition) for r in plan[: create + 1]],
    ) == (
        ["project item-create", "item-edit by id"],
        ("--format", "json"),
        [True] * (create + 1),
    )


def test_no_roadmap_plan_lists_a_board_command_gh_resolves_by_reading_the_board_first() -> None:
    """Every job's plan: no `field-list`, and every `item-edit` by node ids."""
    from devops_cli.roadmap.intake import dry_run_intake

    intake = dry_run_intake(REPO, ref="main")
    plans = [
        *render_requests(REPO, None),
        *(
            r
            for pair in (reprioritize_requests(REPO, None), migrate_requests(REPO, None))
            for r in (*pair[0], *pair[1])
        ),
        *(r for r in (*close_requests(REPO, None)[0], *close_requests(REPO, None)[1])),
        *intake.requests,
        *intake.writes,
    ]
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
    ) == (6, set(), [])


# ── A real run's argv is its plan ─────────────────────────────────────────────

_REQUEST, _ARG, _BODY = "\x1e", "\x1f", "\x1d"
_PLACEHOLDER = re.compile(r"<[^<>]+>")


def _template(text: str) -> str:
    """`text` as a pattern: each placeholder stands for any value within one argument."""
    parts = _PLACEHOLDER.split(text)
    return f"[^{_REQUEST}{_ARG}{_BODY}]*?".join(re.escape(part) for part in parts)


def _pattern(request: PlannedRequest) -> str:
    """One planned request as a pattern over the calls: a page repeat runs once or more, any
    other repeat any number of times, and a condition at most once."""
    body = _ARG.join(_template(arg) for arg in request.argv[1:])
    one = f"(?:{_REQUEST}{body}{_BODY}{_template(request.stdin or '')})"
    if request.repeat:
        return one + ("+" if is_page_repeat(request.repeat) and not request.condition else "*")
    return one + ("?" if request.condition else "")


def follows(plan: Sequence[PlannedRequest], calls: Sequence[tuple[list[str], str | None]]) -> bool:
    """Whether the calls a run made, in order, are exactly the plan's requests."""
    pattern = "".join(_pattern(request) for request in plan)
    ran = "".join(f"{_REQUEST}{_ARG.join(args)}{_BODY}{stdin or ''}" for args, stdin in calls)
    return re.fullmatch(pattern, ran, re.DOTALL) is not None


class _Gh:
    """Answers each command by the first key its argv contains; keeps every argv and stdin."""

    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = replies
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs.get("input")))
        command = " ".join(args)
        key = next(key for key in self.replies if key in command)
        reply = self.replies[key]
        reply = reply(args) if callable(reply) else reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return subprocess.CompletedProcess(args, 0, text, "")


def _github(board: dict[str, Any], milestones: list[dict[str, Any]]) -> _Gh:
    server = BoardServer(board)
    branch = {"name": "main", "target": {"oid": "a" * 40}}
    return _Gh(
        {
            "contents/.github/roadmap.toml": "board = 2\n",
            "fields(first": _fields_reply(),
            "RoadmapGraphQLBudget": lambda _: budget_reply(server.remaining - 1),
            BOARD_READ: server,
            "issues?": _rest_pages(issues_of(board)),
            "milestones?state=all": milestones,
            "defaultBranchRef": {"data": {"repository": {"defaultBranchRef": branch}}},
        }
    )


@pytest.fixture
def github_stores(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Each store a job opens is the GitHub store over the runner the test passes; nothing
    sleeps."""
    from devops_cli.roadmap.github_store import GitHubRoadmapStore

    monkeypatch.setattr(
        roadmap_store_module,
        "get_roadmap_store",
        lambda repo, **options: GitHubRoadmapStore(repo, **options),
    )
    with patch("time.sleep", side_effect=AssertionError("slept")):
        yield


def test_a_reprioritize_runs_gh_argv_sequence_is_its_plan(github_stores: None) -> None:
    gh = _github(board_of(280, 651, archived=1), [])
    config, store = open_roadmap(REPO, ref="main", runner=gh)
    plan_reprioritization(store, repo=REPO, config=config, now=NOW)
    store.graphql_spend()
    planned = dry_run_reprioritization(REPO, ref="main", now=NOW).requests
    assert (len(gh.calls) > 20, follows(planned, gh.calls)) == (True, True)


def test_a_render_runs_gh_argv_sequence_is_its_plan(github_stores: None) -> None:
    release = {"number": 5, "title": "v0.2.26", "state": "open"}
    gh = _github(board_of(150, 20), [release])
    config, store = open_roadmap(
        REPO, ref=None, runner=gh, board_filter=CONST_ROADMAP_RENDER_BOARD_FILTER
    )
    rendered = render(store, repo=REPO, config=config)
    store.graphql_spend()
    planned = dry_run_render(REPO, ref=None).requests
    assert (
        rendered.dry_run,
        "## Current release: v0.2.26" in rendered.text,
        follows(planned, gh.calls),
    ) == (
        False,
        True,
        True,
    )


def test_a_plan_does_not_match_a_run_it_does_not_describe() -> None:
    """The matcher is strict: a run with a request the plan lacks, or missing one it always
    makes, does not follow it."""
    planned = dry_run_render(REPO, ref=None).requests
    config = (list(planned[0].argv[1:]), None)
    extra = (["api", "repos/x/y/issues/1"], None)
    assert (follows(planned, [config]), follows(planned, [config, extra])) == (False, False)


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


@pytest.mark.parametrize("flags", [("--plan",), ()], ids=["plan", "no-flag"])
def test_a_reprioritize_preview_reads_github_and_ends_with_the_spend_line(
    monkeypatch: pytest.MonkeyPatch, flags: tuple[str, ...]
) -> None:
    from devops_cli.roadmap.github_store import GitHubRoadmapStore

    gh = _github(board_of(3, 1), [])
    monkeypatch.setattr(
        roadmap_store_module,
        "get_roadmap_store",
        lambda repo, **options: GitHubRoadmapStore(repo, **{**options, "runner": gh}),
    )
    result = runner.invoke(app, ["reprioritize", "--repo", REPO, *flags])
    last = result.output.strip().splitlines()[-1]
    assert (
        result.exit_code,
        last.lstrip("ℹ ").startswith("GraphQL: "),
        "points spent" in last,
    ) == (
        0,
        True,
        True,
    ), result.output
