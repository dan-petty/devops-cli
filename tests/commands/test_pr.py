"""`devops pr check-readiness`, `pr ready` and `pr monitor` read one merge-readiness verdict
(#2442, #2443).

`check-readiness` reads the pull request, resolves replied threads when asked, and prints the
verdict's advisories, the review threads that block it, and its blockers or the success line.
`pr ready` blocks on the verdict's checks and warns of the rest. `pr monitor` waits until the
checks settle, adds its review gate, and names every blocker.
GitHub is faked at both edges it is read through (`github_api_and_gh`); the verdict's rules are
tested in `tests/test_merge_readiness.py` and `tests/test_item_grounding.py`.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tests.copilot_review_payloads import (
    CHANGES_RECOMMENDED,
    FIRST_REVIEW_ID,
    MAINTAINER,
    NO_CHANGES,
    SECOND_REVIEW_ID,
    copilot_pass,
    copilot_review,
    work_started,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_REPO = "dan-petty/devops-cli"
_HEAD, _BASE = "a" * 40, "b" * 40
_ARCHIVE_704 = {
    "filename": "openspec/changes/archive/2026-10-23-704-x/proposal.md",
    "status": "added",
}
_PULL = f"api repos/{_REPO}/pulls/335"
_ISSUE_704 = {
    "number": 704,
    "state": "OPEN",
    "repository": {"nameWithOwner": _REPO},
    "labels": {"nodes": [{"name": "priority/p2-medium"}]},
}
_THREADS = "GetReviewThreads"


def _pr(**overrides: object) -> dict[str, Any]:
    repo = {"full_name": _REPO, "default_branch": "main"}
    payload: dict[str, Any] = {
        "number": 335,
        "merged": False,
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "base": {"ref": "main", "sha": _BASE, "repo": repo},
        "head": {"ref": "feat/x", "sha": _HEAD, "repo": repo},
    }
    payload.update(overrides)
    return payload


def _threads_page(*threads: dict[str, Any]) -> str:
    page = {"nodes": list(threads), "pageInfo": {"hasNextPage": False, "endCursor": None}}
    return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": page}}}})


def _thread(thread_id: str, *authors: str) -> dict[str, Any]:
    comments = [
        {"id": f"{thread_id}-{n}", "body": "Fix this bug", "author": {"login": author}}
        for n, author in enumerate(authors)
    ]
    return {
        "id": thread_id,
        "isResolved": False,
        "path": "src/main.py",
        "line": 10,
        "comments": {"nodes": comments, "pageInfo": {"hasNextPage": False}},
    }


class _GitHub:
    """PR #335 as GitHub answers it: open, clean, every check passed, no open thread, and
    grounded in open Item #704, unless a test says otherwise."""

    def __init__(self, api: GitHubApiFake, gh: ProcessFake) -> None:
        self.api, self.gh = api, gh
        self.pull(_pr())
        self.checks({"name": "CI", "status": "completed", "conclusion": "success"})
        self.answer(
            "/status", ProcessAnswer(stdout=json.dumps({"state": "success", "statuses": []}))
        )
        self.files(_ARCHIVE_704)
        self.answer(_THREADS, ProcessAnswer(stdout=_threads_page()))
        self.answer("contents/openspec/changes", ProcessAnswer())
        references = {"totalCount": 1, "nodes": [_ISSUE_704]}
        closing = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": references}}}}
        self.answer("closingIssuesReferences", ProcessAnswer(stdout=json.dumps(closing)))

    def answer(self, route: str, answer: ProcessAnswer) -> None:
        self.gh.answer(lambda call, key=route: key in " ".join(call.argv), answer)

    def pull(self, payload: dict[str, Any]) -> None:
        self.gh.answer(
            lambda call: " ".join(call.argv).endswith(_PULL),
            ProcessAnswer(stdout=json.dumps(payload)),
        )

    def checks(self, *runs: dict[str, Any]) -> None:
        self.api.route(
            "GET",
            f"/repos/{_REPO}/commits/{_HEAD}/check-runs?per_page=100",
            github_json({"total_count": len(runs), "check_runs": list(runs)}),
        )

    def files(self, *files: dict[str, str]) -> None:
        self.api.route(
            "GET", f"/repos/{_REPO}/pulls/335/files?per_page=100", github_json(list(files))
        )

    def threads(self, *threads: dict[str, Any]) -> None:
        self.answer(_THREADS, ProcessAnswer(stdout=_threads_page(*threads)))


@pytest.fixture(autouse=True)
def no_status_write() -> Iterator[None]:
    """`pr create` and `pr ready` set the Status of the item the pull request closes (#2717);
    tests/test_pr_status.py holds that. These cases leave the roadmap alone."""
    with patch("devops_cli.commands.pr.set_delivered_status"):
        yield


@pytest.fixture
def github(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> _GitHub:
    return _GitHub(*github_api_and_gh)


def _readiness(cli: Callable[..., Any], *flags: str) -> tuple[int, str]:
    """Run `devops pr check-readiness 335` and return its exit code and its output on one line."""
    result = cli("pr", "check-readiness", "335", "--repo", _REPO, *flags)
    return result.exit_code, " ".join(result.output.split())


def _running(github: _GitHub) -> None:
    github.checks({"name": "Tests & Coverage", "status": "in_progress", "conclusion": None})


@pytest.mark.parametrize(
    ("setup", "flags", "code", "line"),
    [
        (
            lambda g: None,
            (),
            0,
            "PR #335 satisfies merge readiness: 0 conflicts, 0 unresolved threads.",
        ),
        (
            lambda g: g.pull(_pr(merged=True, state="closed")),
            (),
            0,
            "already merged into base branch",
        ),
        (lambda g: g.pull(_pr(state="closed")), (), 1, "closed without being merged"),
        (
            lambda g: g.pull(_pr(mergeable=False, mergeable_state="dirty")),
            (),
            1,
            "PR #335 has merge conflicts with base branch 'main'.",
        ),
        (
            lambda g: g.pull(_pr(mergeable=None, mergeable_state="unknown")),
            (),
            1,
            "PR #335 mergeability is unresolved or still calculating on GitHub",
        ),
        (
            lambda g: g.pull(_pr(mergeable_state="blocked")),
            (),
            1,
            "PR #335 merge state is blocked by GitHub branch protection or checks",
        ),
        (
            lambda g: g.pull(_pr(mergeable_state="blocked")),
            ("--allow-blocked-state",),
            0,
            "PR #335 merge state is currently 'blocked' by branch protection or pending checks.",
        ),
        (
            lambda g: g.pull(_pr(draft=True)),
            (),
            1,
            "PR #335 is in draft status; GitHub refuses to merge a draft.",
        ),
        (
            lambda g: g.pull(_pr(draft=True)),
            ("--allow-draft",),
            0,
            "PR #335 is in draft status and cannot be merged as-is.",
        ),
        (
            lambda g: g.checks({"name": "CodeQL", "status": "completed", "conclusion": "failure"}),
            (),
            1,
            "PR #335 has 1 failing check(s): CodeQL.",
        ),
        (_running, (), 1, "PR #335 has 1 check(s) still running: Tests & Coverage."),
        (
            _running,
            ("--allow-pending-checks",),
            0,
            "PR #335 has 1 check(s) still running: Tests & Coverage.",
        ),
        (
            lambda g: g.answer(
                "/status", ProcessAnswer(returncode=1, stderr="HTTP 500: Server Error")
            ),
            (),
            1,
            "PR #335 check verification failed closed",
        ),
        (
            lambda g: g.threads(_thread("T1", "copilot")),
            (),
            1,
            "PR Review Discussion Threads",
        ),
        (
            lambda g: g.threads(_thread("T1", "copilot", "developer")),
            ("--allow-replied-threads",),
            0,
            "PR #335 has 1 review discussion thread(s) with replies awaiting reviewer resolution.",
        ),
        (
            lambda g: g.threads(_thread("T1", "copilot", "developer"), _thread("T2", "copilot")),
            ("--allow-replied-threads",),
            1,
            "PR #335 has 1 unreplied review discussion thread(s).",
        ),
        (
            lambda g: g.answer(
                _THREADS, ProcessAnswer(returncode=1, stderr="GraphQL 502 Bad Gateway")
            ),
            (),
            1,
            "Could not retrieve review threads for PR #335",
        ),
        (
            lambda g: g.files({"filename": "src/x.py", "status": "modified"}),
            (),
            1,
            "PR #335 is not grounded: it adds no openspec/changes/archive/<date>-704-<slug>/ for #704.",
        ),
    ],
    ids=[
        "ready",
        "merged",
        "closed",
        "conflicts",
        "mergeability-unknown",
        "blocked",
        "blocked-excused",
        "draft",
        "draft-excused",
        "failing-check",
        "running-check",
        "running-check-excused",
        "checks-unread",
        "unresolved-thread",
        "replied-thread-excused",
        "unreplied-thread",
        "threads-unread",
        "not-grounded",
    ],
)
def test_check_readiness_prints_the_verdict_and_exits_on_it(
    cli: Callable[..., Any],
    github: _GitHub,
    setup: Callable[[_GitHub], None],
    flags: tuple[str, ...],
    code: int,
    line: str,
) -> None:
    """Exit 0 when nothing blocks, 1 on any blocker; each case prints the line that says why."""
    setup(github)
    exit_code, output = _readiness(cli, *flags)
    assert (exit_code, line in output) == (code, True), output


def test_a_blocked_pull_request_never_prints_the_success_line(
    cli: Callable[..., Any], github: _GitHub
) -> None:
    github.threads(_thread("T1", "copilot"))
    exit_code, output = _readiness(cli)
    assert (exit_code, "satisfies merge readiness" in output) == (1, False)


def test_auto_resolve_resolves_replied_threads_before_the_verdict(
    cli: Callable[..., Any], github: _GitHub
) -> None:
    """`--auto-resolve` resolves each thread someone other than its opener answered, and the
    verdict then reads the threads as they are after it."""
    pages = [_threads_page(_thread("PRRT_1", "copilot", "developer")), _threads_page()]

    def threads(_call: ProcessCall) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [], 0, stdout=pages.pop(0) if len(pages) > 1 else pages[0]
        )

    github.answer(_THREADS, ProcessAnswer(side_effect=threads))
    resolved = {"data": {"resolveReviewThread": {"thread": {"id": "PRRT_1", "isResolved": True}}}}
    github.answer("resolveReviewThread", ProcessAnswer(stdout=json.dumps(resolved)))
    exit_code, output = _readiness(cli, "--auto-resolve")
    assert (
        exit_code,
        "Auto-resolved 1 replied review discussion thread(s)." in output,
        "satisfies merge readiness" in output,
    ) == (0, True, True)


_REVIEW_TOML = """\
[[suppressions]]
rule = "B602"
path = "src/a.py"
reason = "The argv is a constant list"
expiry = "2099-12-31"
"""


def test_a_pr_touching_a_suppressed_file_warns_and_still_passes(
    cli: Callable[..., Any], github: _GitHub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The warning names the review.toml suppression of the working directory's repository that
    the PR touches (#1150), for a person to re-check its reason, and blocks nothing."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.toml").write_text(_REVIEW_TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    github.files(_ARCHIVE_704, {"filename": "src/a.py", "status": "modified"})
    exit_code, output = _readiness(cli)
    assert (
        exit_code,
        "B602" in output and "src/a.py" in output and "The argv is a constant list" in output,
    ) == (0, True)


# ── devops pr ready and devops pr monitor read the same verdict (#2443) ───────────────────────────

_REVIEWS = f"/repos/{_REPO}/pulls/335/reviews?per_page=100"
_TIMELINE = f"/repos/{_REPO}/issues/335/timeline?per_page=100"
_CHECK_RUNS = f"/repos/{_REPO}/commits/{_HEAD}/check-runs?per_page=100"
_APPROVAL = {"id": 1, "user": {"login": "maintainer"}, "state": "APPROVED", "commit_id": _HEAD}


@pytest.fixture
def monitored(github: _GitHub, clock: ClockFake) -> _GitHub:
    """PR #335 as the monitor reads it: approved at its head, with no Copilot event, on a clock
    that a poll interval moves on at once."""
    github.api.route("GET", _REVIEWS, github_json([_APPROVAL]))
    github.api.route("GET", _TIMELINE, github_json([]))
    return github


def _monitor(cli: Callable[..., Any], *flags: str) -> tuple[int, str]:
    """Run `devops pr monitor 335` and return its exit code and its output on one line."""
    result = cli(
        "pr", "monitor", "335", "--repo", _REPO, "--interval", "60", "--settle-timeout", "0", *flags
    )
    return result.exit_code, " ".join(result.output.split())


def _failing(github: _GitHub) -> None:
    github.checks({"name": "CodeQL", "status": "completed", "conclusion": "failure"})


def _unread(github: _GitHub) -> None:
    github.answer("/status", ProcessAnswer(returncode=1, stderr="HTTP 500: Server Error"))


def _open_thread(github: _GitHub) -> None:
    github.threads(_thread("T1", "copilot"))


def _draft(github: _GitHub) -> None:
    github.pull(_pr(draft=True))


def _readied(github: _GitHub) -> bool:
    """Whether `gh pr ready` has run."""
    return any(call.argv[1:3] == ("pr", "ready") for call in github.gh.calls)


@pytest.fixture
def draft(github: _GitHub) -> _GitHub:
    """PR #335 as `pr ready` finds it: a draft until `gh pr ready` runs, then ready."""

    def pull(_call: ProcessCall) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(_pr(draft=not _readied(github)))
        )

    github.gh.answer(
        lambda call: " ".join(call.argv).endswith(_PULL), ProcessAnswer(side_effect=pull)
    )
    github.answer("pr ready", ProcessAnswer())
    return github


def _ready(cli: Callable[..., Any], *flags: str) -> tuple[int, str]:
    """Run `devops pr ready 335` and return its exit code and its output on one line."""
    result = cli("pr", "ready", "335", "--repo", _REPO, *flags)
    return result.exit_code, " ".join(result.output.split())


_SCENARIOS = {
    "ready": None,
    "running-check": _running,
    "failing-check": _failing,
    "checks-unread": _unread,
    "unresolved-thread": _open_thread,
}


@pytest.mark.parametrize(
    ("scenario", "code", "marked"),
    [
        ("ready", 0, True),
        ("running-check", 8, False),
        ("failing-check", 1, False),
        ("checks-unread", 1, False),
        ("unresolved-thread", 0, True),
    ],
)
def test_pr_ready_exits_on_the_checks_of_the_verdict(
    cli: Callable[..., Any], draft: _GitHub, scenario: str, code: int, marked: bool
) -> None:
    """`pr ready` blocks only on the checks: 1 when one failed or could not be read, 8 while one
    runs. A draft is what it marks ready, and an open thread is a warning."""
    setup = _SCENARIOS[scenario]
    if setup is not None:
        setup(draft)
    exit_code, output = _ready(cli)
    assert (exit_code, _readied(draft)) == (code, marked), output


@pytest.mark.parametrize(
    ("scenario", "code"),
    [
        ("ready", 0),
        ("running-check", 3),
        ("failing-check", 1),
        ("checks-unread", 1),
        ("unresolved-thread", 2),
        ("draft", 2),
    ],
)
def test_pr_monitor_exits_on_the_verdict_once_the_checks_settle(
    cli: Callable[..., Any], monitored: _GitHub, scenario: str, code: int
) -> None:
    """0 with no blocker, 1 when a check failed or could not be read, 2 for any other blocker,
    and 3 when the timeout passes while a check still runs."""
    setup = {**_SCENARIOS, "draft": _draft}[scenario]
    if setup is not None:
        setup(monitored)
    exit_code, output = _monitor(cli, "--timeout", "120")
    assert exit_code == code, output


def test_the_monitor_waits_for_the_checks_and_names_every_blocker(
    cli: Callable[..., Any], monitored: _GitHub
) -> None:
    """Two checks run and a thread is open on the first poll; on the next, one check passed and
    the other failed. The monitor returns once, after the checks settle, and names both: it no
    longer stops on the first blocker while a check still runs (#998)."""
    running = [
        {"name": "Tests & Coverage", "status": "in_progress", "conclusion": None},
        {"name": "CodeQL", "status": "in_progress", "conclusion": None},
    ]
    settled = [
        {"name": "Tests & Coverage", "status": "completed", "conclusion": "success"},
        {"name": "CodeQL", "status": "completed", "conclusion": "failure"},
    ]
    monitored.api.route(
        "GET",
        _CHECK_RUNS,
        github_json({"total_count": 2, "check_runs": running}),
        github_json({"total_count": 2, "check_runs": settled}),
    )
    _open_thread(monitored)
    exit_code, output = _monitor(cli, "--timeout", "600")
    pull_reads = sum(" ".join(call.argv).endswith(_PULL) for call in monitored.gh.calls)
    assert (
        exit_code,
        pull_reads,
        "PR #335 has 1 failing check(s): CodeQL." in output,
        "PR #335 has 1 unresolved review discussion thread(s)." in output,
    ) == (1, 2, True, True), output


def test_a_missing_priority_label_warns_and_pr_ready_still_marks_it(
    cli: Callable[..., Any], draft: _GitHub
) -> None:
    """The item rules block the merge, not the review: agents set no priority label, and intake
    labels the issue later."""
    references = {"totalCount": 1, "nodes": [{**_ISSUE_704, "labels": {"nodes": []}}]}
    closing = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": references}}}}
    draft.answer("closingIssuesReferences", ProcessAnswer(stdout=json.dumps(closing)))
    exit_code, output = _ready(cli)
    assert (
        exit_code,
        _readied(draft),
        "Still blocks the merge: PR #335 is not grounded" in output,
        "holds no priority label" in output,
    ) == (0, True, True, True), output


def test_pr_ready_stops_when_the_pull_request_cannot_be_read(
    cli: Callable[..., Any], github: _GitHub
) -> None:
    """A failed read is no proof that the checks pass, so nothing is marked ready (#769)."""
    github.gh.answer(
        lambda call: " ".join(call.argv).endswith(_PULL),
        ProcessAnswer(returncode=1, stderr="gh: Not Found (HTTP 404)"),
    )
    exit_code, output = _ready(cli)
    assert (exit_code, _readied(github), "HTTP 404" in output) == (1, False, True), output


def test_pr_ready_reports_a_draft_that_is_already_ready(
    cli: Callable[..., Any], github: _GitHub
) -> None:
    exit_code, output = _ready(cli)
    assert (exit_code, _readied(github), "already marked ready for review" in output) == (
        0,
        False,
        True,
    ), output


@pytest.mark.parametrize(
    ("said", "details"),
    [
        pytest.param(
            "GraphQL error: API rate limit exceeded",
            "GraphQL error: API rate limit exceeded",
            id="rate-limit",
        ),
        pytest.param(
            "gh: Too Many Requests (HTTP 429)", "gh: Too Many Requests (HTTP 429)", id="429"
        ),
        pytest.param(
            "gh: Please retry your request again later. (HTTP 403)",
            "gh: Please retry your request again later. (HTTP 403)",
            id="secondary",
        ),
        pytest.param(
            "GraphQL: API rate limit already exceeded for user ID 1.",
            "GraphQL: API rate limit already exceeded for user ID 1",
            id="ends-with-a-period",
        ),
    ],
)
def test_pr_ready_names_a_rate_limit_only_the_gh_table_names(
    cli: Callable[..., Any], draft: _GitHub, said: str, details: str
) -> None:
    """A rate limit gh writes without the words "rate limit" is still named one (#983). The
    message is one paragraph, and gh's own closing period is not doubled."""
    draft.answer("pr ready", ProcessAnswer(returncode=1, stderr=said))
    result = cli("pr", "ready", "335", "--repo", _REPO)
    assert (
        result.exit_code,
        f"GitHub GraphQL rate limit exceeded. Details: {details}. Note:" in result.output,
        result.output.count("\n"),
    ) == (1, True, 1), result.output


_TOKEN = "ghp_1234567890abcdefghij"


@pytest.mark.parametrize("output_format", ["json", "yaml", "markdown"])
def test_the_monitor_prints_its_result_in_each_format_with_thread_bodies_masked(
    cli: Callable[..., Any], monitored: _GitHub, output_format: str
) -> None:
    """A JSON result is pure JSON; each format masks a secret a review comment quotes."""
    thread = _thread("PRRT_kw1", "copilot")
    thread["comments"]["nodes"][0]["body"] = f"Token leaked: {_TOKEN} in config"
    monitored.threads(thread)
    result = cli(
        "pr", "monitor", "335", "--repo", _REPO, "--settle-timeout", "0", "--format", output_format
    )
    exit_code = json.loads(result.output)["exit_code"] if output_format == "json" else None
    assert (
        result.exit_code,
        exit_code in (None, 2),
        _TOKEN in result.output,
        "<masked-github-token>" in result.output,
    ) == (2, True, False, True), result.output


def test_the_monitor_finds_the_pull_request_of_the_current_branch(
    cli: Callable[..., Any], monitored: _GitHub
) -> None:
    monitored.gh.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/x\n"))
    monitored.answer("pulls?head=dan-petty:feat/x", ProcessAnswer(stdout="335\n"))
    result = cli("pr", "monitor", "--repo", _REPO, "--settle-timeout", "0")
    assert (result.exit_code, "PR #335" in result.output) == (0, True), result.output


def test_an_unreadable_copilot_state_is_a_blocker_once_the_checks_settle(
    cli: Callable[..., Any], monitored: _GitHub
) -> None:
    """A Copilot state the monitor cannot read is no proof that Copilot asked for nothing."""
    monitored.api.route("GET", _TIMELINE, github_json({"message": "rate limit"}, status=403))
    result = cli(
        "pr", "monitor", "335", "--repo", _REPO, "--settle-timeout", "0", "--format", "json"
    )
    copilot = json.loads(result.output)["status"]["copilot_status"]
    assert (result.exit_code, copilot["state"], bool(copilot["unread_reason"])) == (
        2,
        "unread",
        True,
    ), result.output


def _copilot_passes(github: _GitHub, *, second_body: str, then: list[object]) -> None:
    """#1283's first two Copilot passes, the second with `second_body`, a person's approval of
    the head, and the timeline events in `then` after them (#1345)."""
    reviews = [
        copilot_review(FIRST_REVIEW_ID),
        copilot_review(SECOND_REVIEW_ID, body=second_body, submitted_at="2026-10-07T15:35:57Z"),
        {**_APPROVAL, "id": 5444999999, "user": MAINTAINER},
    ]
    timeline = [*copilot_pass(FIRST_REVIEW_ID), *copilot_pass(SECOND_REVIEW_ID), *then]
    github.api.route("GET", _REVIEWS, github_json(reviews))
    github.api.route("GET", _TIMELINE, github_json(timeline))


@pytest.mark.parametrize(
    ("second_body", "then", "thread", "code", "says"),
    [
        pytest.param(NO_CHANGES, [], False, 0, "READY FOR MERGING", id="ready"),
        pytest.param(
            NO_CHANGES, [work_started()], False, 3, "Copilot review still active", id="third-pass"
        ),
        pytest.param(
            CHANGES_RECOMMENDED,
            [],
            True,
            2,
            "Copilot review requested changes",
            id="unresolved-thread",
        ),
        pytest.param(CHANGES_RECOMMENDED, [], False, 0, "READY FOR MERGING", id="changes-resolved"),
    ],
)
def test_the_monitor_reads_1283s_recorded_copilot_passes(
    cli: Callable[..., Any],
    monitored: _GitHub,
    second_body: str,
    then: list[object],
    thread: bool,
    code: int,
    says: str,
) -> None:
    """The monitor passes once Copilot's two passes have ended, waits while a third runs, stops
    on a change Copilot asked for while its thread is open, and passes once the thread is
    resolved."""
    _copilot_passes(monitored, second_body=second_body, then=then)
    if thread:
        monitored.threads(_thread("PRRT_1283", "Copilot"))
    exit_code, output = _monitor(cli, "--timeout", "120")
    assert (exit_code, says in output) == (code, True), output


@pytest.mark.parametrize(
    ("reviews", "flags", "code", "says"),
    [
        pytest.param(
            [],
            (),
            2,
            "requires review approval before merging: current review decision is 'NONE'",
            id="no-review",
        ),
        pytest.param([], ("--no-require-reviews",), 0, "READY FOR MERGING", id="not-required"),
        pytest.param(
            [{**_APPROVAL, "state": "CHANGES_REQUESTED"}],
            (),
            2,
            "PR #335 has review changes requested.",
            id="changes-requested",
        ),
        pytest.param(
            [{**_APPROVAL, "commit_id": "c" * 40}],
            (),
            2,
            "current review decision is 'REVIEW_REQUIRED'",
            id="stale-approval",
        ),
    ],
)
def test_the_monitor_holds_the_pull_request_to_its_review_gate(
    cli: Callable[..., Any],
    monitored: _GitHub,
    reviews: list[dict[str, Any]],
    flags: tuple[str, ...],
    code: int,
    says: str,
) -> None:
    """`check-readiness` reads no review, so the monitor's review gate adds its blockers: an
    approval of the head commit, unless `--no-require-reviews`, and no requested change."""
    monitored.api.route("GET", _REVIEWS, github_json(reviews))
    exit_code, output = _monitor(cli, "--timeout", "120", *flags)
    assert (exit_code, says in output) == (code, True), output
