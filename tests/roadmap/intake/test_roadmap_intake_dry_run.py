"""A dry run of intake makes no request and lists the requests a run makes, in order (#412)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import replace
from itertools import groupby
from pathlib import Path
from typing import Any

import pytest
from fastmcp.exceptions import ToolError

from devops_cli import entry
from devops_cli.ai.mcp import server as mcp_server
from devops_cli.dry_run.state import in_dry_run_invocation
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake.intake import (
    IntakePlan,
    NewCandidate,
    apply_intake,
    dry_run_intake,
    plan_intake,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
)
from devops_cli.telemetry.exporter import OtlpSignal
from devops_cli.telemetry.tracer import get_tracer
from tests.support.fakes.github import API, RunnerSession
from tests.support.fakes.otlp import FakeCollector
from tests.support.roadmap_intake import REGRESSION, REPO, FakeModel, Recorded, Roadmap


def test_dry_run_makes_no_request_and_prints_the_requests_a_run_makes_in_order(
    no_requests: None,
    run_intake: Callable[..., str],
) -> None:
    output = run_intake("--dry-run", "--issue", "7")
    steps = [
        "Dry run: no request was made",
        "REST read every issue, open and closed",
        f"GET '{API}/repos/{REPO}/issues?state=all&per_page=100'",
        f"{REPO}/contents/.github/labels.yml",
        "[only if the run has a candidate]",
        "GraphQL read the closes and reopens on #7's timeline",
        "embedding every item",
        "model the proposal for #7",
        "With --confirm",
        "REST write label #7 with its type/* label",
        f"REST write set Status New on #7: read the issue, then write its labels and its job "
        f"record in one request gh api -X PATCH repos/{REPO}/issues/7 --input -",
        "REST read set Priority <the proposed Priority> on #7",
        "REST write set Priority <the proposed Priority> on #7",
    ]
    positions = [output.find(step) for step in steps]
    assert (
        -1 not in positions,
        positions == sorted(positions),
        "roadmap.toml" in output,
        "board" in output,
    ) == (True, True, False, False), output


def test_a_dry_run_is_an_intake_plan_of_planned_requests_with_placeholders() -> None:
    every = dry_run_intake(REPO, ref="main")
    new = dry_run_intake(REPO, new=NewCandidate(title="feat: idea", body="text"))
    listing = every.requests[0]
    repeated = {
        r.repeat.split("; ")[0]
        for r in every.requests + every.writes
        if r.target.endswith("<the candidate>")
    }
    assert (
        (type(every), every.dry_run, every.decisions, every.has_writes),
        (listing.method, listing.target, listing.argv),
        {"REST read", "GraphQL read", "embedding", "model"} <= {r.method for r in every.requests},
        repeated,
        any("timeline" in r.target for r in new.requests),
        (new.writes[0].method, new.writes[0].target.startswith('file new candidate "feat: idea"')),
        "<the filed issue>" in new.writes[-1].target,
        any(r.repeat for r in new.requests + new.writes if not r.argv),
    ) == (
        (IntakePlan, True, (), False),
        (
            "REST read",
            "the issues changed since the snapshot of the listing, the newest change first, "
            "which replace their records in the snapshot: the candidates and the items",
            (
                "GET",
                f"{API}/repos/{REPO}/issues?state=all&sort=updated&direction=desc"
                "&since=<the watermark of the snapshot>&per_page=100",
            ),
        ),
        True,
        {"for each candidate: an open issue with no Priority"},
        False,
        ("REST write", True),
        True,
        False,
    )


@pytest.mark.parametrize("full", [False, True])
def test_a_dry_run_reads_the_changes_since_the_snapshot_or_else_every_issue(full: bool) -> None:
    """Without `--full`, a run reads the issues changed since a snapshot that it can read from,
    and every issue when it holds none; with `--full`, it reads every issue (#4448)."""
    reads = dry_run_intake(REPO, full=full).requests
    listings = [
        (r.argv[1].split("?")[1], r.condition) for r in reads if "/issues?" in "".join(r.argv)
    ]
    unread = "the run has not read every issue yet"
    changed = (
        "state=all&sort=updated&direction=desc&since=<the watermark of the snapshot>&per_page=100",
        "the data directory holds a snapshot of the listing that this version wrote, and its "
        f"last full read is less than 24 hours old and {unread}",
    )
    whole = (
        "state=all&per_page=100",
        unread
        if full
        else f"the data directory holds no such snapshot of the listing and {unread}",
    )
    assert listings == ([whole] if full else [changed, whole])


# The store operation each planned request stands for.
STORE_OPERATIONS: dict[str, str] = {
    "issues": "issues",
    "changed_issues": "issues",
    "closures": "closures",
    "embed": "embed",
    "embed_new": "embed",
    "labels": "repository_file",
    "propose": "propose",
    "evidence": "evidence_holds",
    "comments": "comments_on",
    "file": "create_issue",
    "label": "label_issue",
    "field": "set_field",
    "comment": "comment",
    "priority": "set_field",
}


def _operations(plan: IntakePlan) -> list[tuple[str, bool]]:
    """The store or model operation of each planned step, and whether it runs every time. A
    step lists each `gh` command its operation runs, all with the step's target, so a run of
    requests with one target is one operation, run every time when any of its commands is."""
    templates = MESSAGES.roadmap.intake_requests
    operations = []
    steps = groupby(plan.requests + plan.writes, key=lambda request: request.target)
    for _, group in steps:
        commands = list(group)
        request = replace(commands[0], condition=min(r.condition for r in commands))
        key = max(
            (
                key
                for key, text in templates.items()
                if request.target.startswith(text.split("{")[0])
            ),
            key=lambda key: len(templates[key].split("{")[0]),
        )
        operations.append((STORE_OPERATIONS[key], not request.condition))
    return operations


def _in_order(ran: list[str], planned: list[tuple[str, bool]]) -> bool:
    """Whether the run's operations follow the plan's, skipping only conditional ones."""
    remaining = iter(ran)
    current = next(remaining, None)
    for operation, always in planned:
        if operation == current:
            current = next(remaining, None)
        elif always:
            return False
    return current is None


@pytest.mark.parametrize("new", [False, True])
def test_a_dry_runs_requests_follow_the_order_a_run_makes_them(roadmap: Roadmap, new: bool) -> None:
    evidence = Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234")
    roadmap.store.seed_evidence(evidence)
    title, body = "fix: crash on start", "Introduced by abc1234."
    candidate = NewCandidate(title=title, body=body, evidence=(evidence,)) if new else None
    number = None if new else roadmap.issue(title, body)
    issues = () if number is None else (number,)
    ran: list[str] = []
    store: Any = Recorded(roadmap.store, ran)
    model: Any = Recorded(FakeModel(proposals={title: REGRESSION}), ran)
    plan = plan_intake(store, repo=REPO, model=model, issues=issues, new=candidate)
    apply_intake(store, plan, repo=REPO)
    planned = _operations(dry_run_intake(REPO, issues=issues, new=candidate))
    assert (plan.decisions[0].priority, _in_order(ran, planned)) == ("P0-Critical", True), (
        ran,
        planned,
    )


def test_a_dry_run_shows_the_exact_commands_the_store_runs() -> None:
    ran: list[tuple[str, ...]] = []

    def gh(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        ran.append(("GET", *args) if args[0].startswith(API) else ("gh", *args))
        return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")

    store = GitHubRoadmapStore(REPO, runner=gh, session=RunnerSession(gh))
    store.issues()
    store.repository_file(".github/labels.yml", ref="feat/topic")
    planned = dry_run_intake(REPO, ref="feat/topic").requests
    shown = {r.argv for r in planned if r.argv}
    assert (len(ran), set(ran) <= shown) == (2, True)


def test_a_dry_run_still_refuses_a_candidate_holding_a_secret(
    no_requests: None, tmp_path: Path, run_intake: Callable[..., str]
) -> None:
    body = tmp_path / "body.md"
    body.write_text("It fails with token=ghp_abcdefghijklmnop1234", encoding="utf-8")
    output = run_intake("--title", "fix: auth", "--body-file", str(body), "--dry-run", exit_code=1)
    assert "secret" in output


def test_a_dry_run_with_a_limit_makes_no_request_and_names_the_limit_per_candidate(
    no_requests: None,
    run_intake: Callable[..., str],
) -> None:
    """`--limit` changes which candidates a run decides, not what a dry run sends (#1360)."""
    output = run_intake("--dry-run", "--limit", "3")
    assert (
        "Dry run: no request was made" in output,
        "[repeated for each of the 3 oldest candidates:" in output,
        "[repeated for each candidate:" in output,
    ) == (True, True, False)


def test_a_limited_plan_decides_the_oldest_candidates_and_names_those_it_leaves(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    """Without a record of earlier runs, the oldest candidates come first (#1360)."""
    numbers = [opened.issue(f"feat: candidate {n}") for n in range(1, 5)]
    preview = run_intake("--plan", "--limit", "2")
    left = ", ".join(f"#{number}" for number in numbers[2:])
    assert (
        [request.title for request in fake_model.requests],
        f"Left for a later run, beyond the limit of 2: {left}." in preview,
    ) == (["feat: candidate 1", "feat: candidate 2"], True)


def test_an_exported_dry_run_with_confirm_is_refused_and_makes_no_request(
    no_requests: None, monkeypatch: pytest.MonkeyPatch, run_intake: Callable[..., str]
) -> None:
    """`devops` turns an exported dry run into the `--dry-run` flag before the command runs, so
    the command refuses `--confirm` as a second mode."""
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")
    assert "Pass one of" in run_intake("--confirm", exit_code=1)


@pytest.fixture
def collector(otlp: FakeCollector, config: Callable[..., Path]) -> FakeCollector:
    """The OTLP fake that receives the telemetry a command exports, with telemetry on."""
    config(telemetry={"enabled": True})
    return otlp


def test_a_dry_run_through_the_entry_point_exports_no_telemetry(
    no_requests: None, collector: FakeCollector, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        entry.main(["roadmap", "intake", "--repo", REPO, "--dry-run", "--issue", "7"])
    get_tracer().shutdown()
    output = capsys.readouterr().out
    assert (exited.value.code, "Dry run: no request was made" in output, collector.exports) == (
        0,
        True,
        [],
    )


def test_the_mcp_mirror_dry_run_dispatched_in_process_exports_no_telemetry(
    no_requests: None, collector: FakeCollector
) -> None:
    output = mcp_server.roadmap_intake(repo=REPO, dry_run=True, issue=[3])
    get_tracer().shutdown()
    after_dry_run = list(collector.exports)
    with pytest.raises(ToolError) as raised:
        mcp_server.roadmap_intake(repo=REPO, plan_only=True)
    assert raised.value is not None
    get_tracer().shutdown()
    assert (
        "Dry run: no request was made" in output,
        after_dry_run,
        OtlpSignal.TRACES in [export.signal for export in collector.exports],
        in_dry_run_invocation(),
    ) == (True, [], True, False)
