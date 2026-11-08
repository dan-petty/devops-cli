"""`devops roadmap` dry runs make no request, and list the requests a run makes (#412, #1125).

Each job's `--dry-run` returns its real result type marked as a dry run, holding the ordered
`PlannedRequest`s the store's own argument builders give, so a real run's `gh` argv sequence
matches its plan. The guards here fail the test on any store, runner, process or socket a dry
run opens; one probe runs each job's dry run through the real entry point with connections,
DNS and process starts refused, and fake `gh`, `git` and `kubectl` on PATH that log each call.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Iterator
from typing import Any, Final

import pytest

from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.request_plan import StoreRequests
from devops_cli.roadmap.stores.github_store import (
    comments_endpoint,
    issue_args,
    issues_endpoint,
    listing_path,
    milestones_endpoint,
)
from devops_cli.roadmap.stores.store import install_roadmap_store
from tests.support.fakes.github import API
from tests.support.fakes.http import WebFake
from tests.support.fakes.model import ModelFake
from tests.support.fakes.process import ProcessFake

REPO = "dan-petty/devops-cli"
JOBS = ("intake", "refine", "alternatives", "stage", "implement")

REGISTRY_COUNTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("name", "stage_requests", "src/devops_cli/roadmap/request_plan.py"),
    ("name", "implement_requests", "src/devops_cli/roadmap/request_plan.py"),
)


# ── No request ────────────────────────────────────────────────────────────────


def _fail(what: str) -> Callable[..., Any]:
    def fail(*args: object, **_: object) -> Any:
        raise AssertionError(f"the dry run {what}: {str(args[:1])[:120]}")

    return fail


@pytest.fixture
def no_requests(
    process_fake: ProcessFake,
    web: WebFake,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """A roadmap store, a process, an HTTP request, a model call and a socket that fail the test
    when a dry run opens, starts, sends, calls or connects one; the session's socket guard covers
    the rest."""
    install_roadmap_store(_fail("opened a store"))
    monkeypatch.setattr(socket.socket, "connect", _fail("connected"))
    monkeypatch.setattr(socket, "getaddrinfo", _fail("resolved a name"))
    yield
    assert (process_fake.calls, web.recorded, model_fake.call_count) == ([], [], 0)


@pytest.mark.parametrize("job", JOBS)
def test_every_jobs_dry_run_makes_no_request_and_lists_the_requests_a_run_makes(
    no_requests: None, job: str, cli: Callable[..., Any]
) -> None:
    result = cli(["roadmap", job, "--repo", REPO, "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "projectV2" in result.output,
        "roadmap.toml" in result.output,
    ) == (0, True, False, False), result.output


def test_refine_dry_run_with_item_makes_no_requests(
    no_requests: None, cli: Callable[..., Any]
) -> None:
    """Refining a single item under dry-run makes no GitHub, process, or model call."""
    result = cli(["roadmap", "refine", "--repo", REPO, "--item", "123", "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "api repos/dan-petty/devops-cli/issues/123" in result.output,
    ) == (0, True, True), result.output


def test_the_explain_dry_run_makes_no_request_and_lists_reads_only(
    no_requests: None, cli: Callable[..., Any]
) -> None:
    """`explain` reads GitHub and git and writes nothing, so its plan holds the reads of a run and
    no write (#2911)."""
    result = cli(["roadmap", "explain", "7", "--repo", REPO, "--dry-run"])
    assert (
        result.exit_code,
        "Dry run: no request was made" in result.output,
        "api repos/dan-petty/devops-cli/issues/7" in result.output,
        MESSAGES.roadmap.plan_dry_run_writes in result.output,
    ) == (0, True, True, False), result.output


@pytest.mark.parametrize("job", JOBS)
def test_an_exported_dry_run_with_confirm_is_refused_and_makes_no_request(
    no_requests: None, job: str, cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`devops` turns an exported dry run into the `--dry-run` flag before the command runs, so
    the command refuses `--confirm` as a second mode and makes no request."""
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")
    result = cli(["roadmap", job, "--repo", REPO, "--confirm"])
    assert (result.exit_code, "Pass one of" in result.output) == (1, True)


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
def test_more_than_one_mode_flag_is_refused(
    no_requests: None, job: str, mode: str, cli: Callable[..., Any]
) -> None:
    result = cli(["roadmap", job, "--repo", REPO, "--dry-run", mode])
    assert (result.exit_code, "Pass one of --dry-run" in result.output) == (1, True)


def test_each_dry_run_returns_its_jobs_result_type_marked_as_a_dry_run() -> None:
    from devops_cli.roadmap.intake.intake import IntakePlan, dry_run_intake
    from devops_cli.roadmap.refine.refine import RefinePlan, dry_run_refine

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
    from devops_cli.roadmap.refine.refine import dry_run_refine

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


def test_a_refine_round_plans_the_record_of_the_comments_it_read_of_a_waiting_item() -> None:
    """A round records, on a waiting item whose comments it read, what they gave: a read of the
    issue, then one `PATCH` of its job record. `--item` refines its item, so its plan records no
    wait (#3667)."""
    from devops_cli.roadmap.request_plan import refine_requests

    _, writes = refine_requests(REPO, None)
    _, single = refine_requests(REPO, None, item=7)
    unrecorded = MESSAGES.roadmap.plan_conditions["wait_unrecorded"]
    assert (
        [_shape(r) for r in writes if r.condition == unrecorded],
        [r for r in single if r.condition == unrecorded],
    ) == ([f"api repos/{REPO}/issues/<item>", "issue patch"], [])


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


def test_a_refine_round_plans_the_read_and_the_notice_for_an_item_of_an_untrusted_author() -> None:
    """A round reads the comments of each item that an account that the jobs do not trust opened,
    and writes one comment on it when none tells its author yet. `--item` refines its item whoever
    opened it, so its plan holds neither (#3502)."""
    from devops_cli.roadmap.request_plan import refine_requests

    reads, writes = refine_requests(REPO, None)
    single_reads, single_writes = refine_requests(REPO, None, item=7)
    texts = MESSAGES.roadmap
    read, notice = texts.plan_conditions["outside_author"], texts.plan_conditions["outside_notice"]
    repeat = texts.plan_repeat["outside_item"]
    paged = f"{repeat}; {texts.plan_repeat_page}"
    assert (
        [(r.argv[1:], r.repeat) for r in reads if r.condition == read],
        [(_shape(r), r.repeat) for r in writes if r.condition == notice],
        [r for r in [*single_reads, *single_writes] if r.condition in {read, notice}],
    ) == (
        [((f"{API}{listing_path(comments_endpoint(REPO, '<item>'))}",), paged)],
        [("api -X POST", repeat)],
        [],
    )


def test_a_refine_plan_lists_the_intake_requests_of_a_deferred_part() -> None:
    """A round and a refine of one item each list the requests of one new intake candidate, and
    the record of its number, when the proposal defers a part (#2423)."""
    from devops_cli.roadmap.intake.intake_requests import planned_requests
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


def test_body_with_marks_a_refine_plan_lists_one_patch_for_the_body_the_labels_and_the_record() -> (
    None
):
    """A refined item costs one read of its issue and one `PATCH` that carries its body, its
    labels and its job record, in a round and for `--item`. The plan lists no separate write of
    the body (#4049)."""
    from devops_cli.roadmap.request_plan import refine_requests

    _, round_writes = refine_requests(REPO, None)
    _, item_writes = refine_requests(REPO, None, item=7)

    def result(writes: tuple[PlannedRequest, ...]) -> tuple[list[str], list[str]]:
        planned = [r for r in writes if not r.condition and "issue" in " ".join(r.argv)]
        patch = next(r for r in planned if _shape(r) == "issue patch")
        return [_shape(r) for r in planned], sorted(json.loads(patch.stdin or "{}"))

    assert (result(round_writes), result(item_writes)) == (
        ([f"api repos/{REPO}/issues/<item>", "issue patch"], ["body", "labels"]),
        ([f"api repos/{REPO}/issues/7", "issue patch"], ["body", "labels"]),
    )


def test_body_with_marks_an_alternatives_plan_lists_one_patch_for_the_block_and_the_marks() -> None:
    """A check costs one read of its issue, one `PATCH` that carries its new body and its marks,
    and one comment. The plan lists no separate write of the body (#4049)."""
    from devops_cli.roadmap.request_plan import alternatives_requests

    _, writes = alternatives_requests(REPO, item=7)

    patches = [r for r in writes if _shape(r) == "issue patch"]
    assert (
        [_shape(r) for r in writes],
        [sorted(json.loads(r.stdin or "{}")) for r in patches],
    ) == ([f"api repos/{REPO}/issues/7", "issue patch", "api -X POST"], [["body"]])


def test_an_alternatives_plan_lists_the_comment_for_a_first_or_changed_check() -> None:
    """The write of a check is planned for every check. The comment is planned with the condition
    that the check is a first one, or that its verdict or its tool differs from the record
    (#4054). A dry run makes no request, so the plan cannot know which case an item is."""
    from devops_cli.roadmap.request_plan import alternatives_requests

    _, writes = alternatives_requests(REPO, item=7)
    texts = MESSAGES.roadmap

    comment = writes[-1]
    assert (_shape(comment), comment.condition) == (
        "api -X POST",
        f"{texts.plan_conditions['check_on']} and {texts.plan_conditions['check_changed']}",
    )
    assert all(texts.plan_conditions["check_changed"] not in w.condition for w in writes[:-1])


def test_no_roadmap_plan_lists_a_request_to_a_project_board() -> None:
    """Every job's plan: intake, a refine round, a refine of one item and a return. No request
    is a `gh project` command, names `projectV2` or reads `.github/roadmap.toml` (ADR 0016)."""
    from devops_cli.roadmap.intake.intake import dry_run_intake
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
    from devops_cli.roadmap.intake.intake import dry_run_intake

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
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    process_fake: ProcessFake,
    web: WebFake,
    job: str,
) -> None:
    """`devops_cli.entry.main` runs each job's `--dry-run`, as the `devops` script does, with
    connections and DNS recorded and refused, and the process and HTTP fakes recording any
    start or request. The run succeeds, prints its plan, and nothing is recorded. It runs in
    this process, so the CLI's import cost is paid once."""
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
    try:
        main(["roadmap", job, "--dry-run", "--repo", REPO])
        code: object = 0
    except SystemExit as exited:
        code = exited.code or 0
    assert (
        code,
        "Dry run: no request was made" in capsys.readouterr().out,
        attempts,
        process_fake.calls,
        web.recorded,
    ) == (0, True, [], [], [])


def test_intakes_dry_run_shows_the_exact_gh_command_of_every_store_request() -> None:
    """Only the embedding and model calls, which run no `gh`, have no argv (#742, #1125)."""
    from devops_cli.roadmap.intake.intake import dry_run_intake

    plan = dry_run_intake(REPO, ref="main")
    bare = {request.method for request in plan.requests + plan.writes if not request.argv}
    assert bare == {"embedding", "model"}


def test_the_alternatives_dry_run_lists_the_gh_command_and_the_url_of_each_request() -> None:
    """The plan names the exact `gh` command of each GitHub request, and the method and the URL
    of the web search of the first configured provider and of each PyPI request (#2650, #3925)."""
    from devops_cli.roadmap.alternatives import AlternativesPlan, dry_run_alternatives

    plan = dry_run_alternatives(REPO, item=7)
    argvs = [request.argv for request in plan.requests + plan.write_requests if request.argv]
    assert (
        type(plan),
        plan.dry_run,
        plan.has_writes,
        ("POST", "https://html.duckduckgo.com/html/") in argvs,
        ("GET", "https://pypi.org/pypi/<package>/json") in argvs,
        ("gh", "api", "repos/<owner/name>") in argvs,
        ("gh", "api", "repos/<owner/name>/releases/latest") in argvs,
        ("gh", "api", f"repos/{REPO}/issues/7") in argvs,
        {request.method for request in plan.requests if not request.argv},
    ) == (AlternativesPlan, True, True, True, True, True, True, True, {"model call"})


def test_the_alternatives_dry_run_lists_the_get_of_the_searxng_search_when_it_is_first(
    config: Callable[..., Any],
) -> None:
    """The method of the request comes from the provider: SearXNG searches with GET (#3927)."""
    from devops_cli.roadmap.alternatives import dry_run_alternatives

    config(search={"providers": ["searxng", "duckduckgo"], "searxng_url": "http://127.0.0.1:8080"})

    plan = dry_run_alternatives(REPO, item=7)

    argvs = [request.argv for request in plan.requests]
    assert (
        ("GET", "http://127.0.0.1:8080/search") in argvs,
        ("POST", "https://html.duckduckgo.com/html/") in argvs,
    ) == (True, False)


def test_the_alternatives_dry_run_lists_the_reads_of_the_adrs() -> None:
    """The run lists `docs/adr` and each file of it once for the run, when it checks an item that
    is no skip class (#3505)."""
    from devops_cli.roadmap.alternatives import dry_run_alternatives

    raw = ("gh", "api", "-H", "Accept: application/vnd.github.raw+json")
    plan = dry_run_alternatives(REPO)
    reads = {request.argv: request for request in plan.requests}

    directory = reads[(*raw, f"repos/{REPO}/contents/docs/adr")]
    adr_file = reads[(*raw, f"repos/{REPO}/contents/docs/adr/NNNN-name.md")]
    assert [(r.condition, r.repeat) for r in (directory, adr_file)] == [
        ("the run checks an item that is no skip class", ""),
        (
            "the run checks an item that is no skip class",
            "for each file of the directory, once a run",
        ),
    ]


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


def test_the_stage_plan_moves_the_clone_to_the_staged_commit_and_starts_each_branch_there() -> None:
    from devops_cli.roadmap.request_plan import stage_requests

    reads, writes = stage_requests(REPO)

    read_lines = [" ".join(request.argv) for request in reads]
    write_lines = [" ".join(request.argv) for request in writes]
    move = "git -C <model-clone> merge --ff-only -q <staged commit>"
    assert read_lines.index(move) < next(
        index for index, line in enumerate(read_lines) if "ls-files" in line
    )
    assert any(
        line.endswith("worktree add --no-track -b <branch> <worktree> <staged commit>")
        for line in write_lines
    )


def test_the_stage_plan_reads_the_tracked_files_of_the_clone_once_for_the_round() -> None:
    from devops_cli.roadmap.request_plan import stage_requests

    reads, _ = stage_requests(REPO)

    (listing,) = [request for request in reads if "ls-files" in request.argv]
    assert listing.argv == ("git", "-C", "<model-clone>", "ls-files", "-z")
    assert listing.repeat == ""
    assert listing.condition


def test_the_stage_plan_reads_the_tasks_of_each_open_plan_once_for_the_round() -> None:
    from devops_cli.roadmap.request_plan import stage_requests

    reads, _ = stage_requests(REPO)

    (plans,) = [request for request in reads if request.argv[3:4] == ("show",)]
    assert plans.argv == (
        "git",
        "-C",
        "<model-clone>",
        "show",
        "origin/main:openspec/changes/<change>/tasks.md",
    )
    assert plans.repeat
    assert plans.condition


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


def test_the_stage_plan_lists_the_read_of_the_labels_file_and_the_label_request() -> None:
    from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
    from devops_cli.roadmap.request_plan import stage_requests

    _, writes = stage_requests(REPO)

    write_lines = [" ".join(request.argv) for request in writes]
    assert any(
        CONST_ROADMAP_LABELS_PATH in line or ".github%2Flabels.yml" in line for line in write_lines
    )
    assert any(
        line.startswith(f"gh api -X POST repos/{REPO}/issues/<pull request>/labels")
        for line in write_lines
    )


def test_the_implement_plan_reads_the_labels_file_and_lists_the_label_writes() -> None:
    from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
    from devops_cli.roadmap.request_plan import implement_requests

    reads, writes = implement_requests(REPO)

    read_lines = [" ".join(request.argv) for request in reads]
    assert any(line == f"GET {API}/repos/{REPO}/pulls/<pull request>" for line in read_lines)
    assert any(
        CONST_ROADMAP_LABELS_PATH in line or ".github%2Flabels.yml" in line for line in read_lines
    )

    write_lines = [" ".join(request.argv) for request in writes]
    assert any(
        line.startswith(f"gh api -X POST repos/{REPO}/issues/<pull request>/labels")
        for line in write_lines
    )
    unlabel = next(
        request
        for request in writes
        if request.argv[:5]
        == ("gh", "api", "-X", "DELETE", f"repos/{REPO}/issues/<pull request>/labels/<label>")
    )
    assert unlabel.condition != ""


def test_the_implement_plan_lists_amendment_commit_split_and_return_with_conditions() -> None:
    from devops_cli.lang import MESSAGES
    from devops_cli.roadmap.request_plan import implement_requests

    _, writes = implement_requests(REPO)

    cond = MESSAGES.roadmap.implement_request_conditions
    amend = next(
        request
        for request in writes
        if request.argv[3:5] == ("commit", "-m") and request.condition == cond["amend"]
    )
    split = next(
        request
        for request in writes
        if request.method == "model" and request.condition == cond["split"]
    )
    return_comment = next(
        request
        for request in writes
        if request.condition == cond["return"] and any("comments" in arg for arg in request.argv)
    )
    return_status = next(
        request
        for request in writes
        if request.condition == cond["return"] and "Status" in request.target
    )
    assert amend.condition != ""
    assert split.condition != ""
    assert return_comment.condition != ""
    assert return_status.condition != ""


def test_the_stage_plan_lists_the_reads_and_the_writes_of_a_rejected_plan() -> None:
    from devops_cli.roadmap.request_plan import stage_requests

    reads, writes = stage_requests(REPO)

    texts = MESSAGES.roadmap
    (state,) = [r for r in reads if r.target == texts.stage_requests["plan_state"]]
    assert state.argv == ("GET", f"{API}/repos/{REPO}/pulls/<pull request>")
    assert state.repeat == texts.plan_repeat["stage_plan"]
    comment_reads = [r for r in reads if "<pull request>/comments" in " ".join(r.argv)]
    assert [r.condition for r in comment_reads] == [
        texts.stage_request_conditions["rejected_comments"]
    ]
    deletes = [w for w in writes if w.target == texts.stage_requests["delete_rejected"]]
    assert [w.argv[-4:] for w in deletes] == [
        (
            "push",
            "--force-with-lease=refs/heads/<branch>:<remote tip>",
            "origin",
            ":refs/heads/<branch>",
        )
    ]
    of_a_rejection = [w for w in writes if w.repeat == texts.plan_repeat["stage_rejected"]]
    assert len(of_a_rejection) == 4
