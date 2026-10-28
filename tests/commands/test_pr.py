"""`devops pr check-readiness` renders the merge-readiness verdict and exits on it (#2442).

The command reads the pull request, resolves replied threads when asked, and prints the
verdict's advisories, the review threads that block it, and its blockers or the success line.
GitHub is faked at both edges it is read through (`github_api_and_gh`); the verdict's rules are
tested in `tests/test_merge_readiness.py` and `tests/test_item_grounding.py`.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_REPO = "dan-petty/devops-cli"
_HEAD, _BASE = "a" * 40, "b" * 40
_ARCHIVE_704 = {
    "filename": "openspec/changes/archive/2026-10-23-704-x/proposal.md",
    "status": "added",
}
_PULL = f"api repos/{_REPO}/pulls/335"
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
        issue = {
            "number": 704,
            "state": "OPEN",
            "repository": {"nameWithOwner": _REPO},
            "labels": {"nodes": [{"name": "priority/p2-medium"}]},
        }
        references = {"totalCount": 1, "nodes": [issue]}
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
