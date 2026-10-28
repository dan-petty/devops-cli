"""The merge-readiness verdict of a pull request, read from GitHub (#998, #2442).

`assess_merge_readiness` reads a pull request's checks and changed files through the GitHub
session, which `GitHubApiFake` answers, and its review threads, the base's change directory and
the issues it closes through gh, which `process_fake` answers (`github_api_and_gh`). Everything
between runs for real. The item rules themselves are tested in `tests/test_item_grounding.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.github.check_verdict import CheckBucket, read_commit_checks
from devops_cli.github.client import PullRequestFile
from devops_cli.github.merge_readiness import (
    Advisory,
    AdvisoryLevel,
    BlockerKind,
    MergeReadiness,
    ReadinessOptions,
    assess_merge_readiness,
    closing_issues_args,
    read_changed_files,
)
from tests.support.fakes.github import GitHubApiFake, github_json, next_page
from tests.support.fakes.process import ProcessAnswer, ProcessFake

_OWNER, _NAME, _PR = "dan-petty", "devops-cli", 335
_REPO = f"{_OWNER}/{_NAME}"
_HEAD, _BASE = "a" * 40, "b" * 40
_CHECK_RUNS = f"/repos/{_REPO}/commits/{_HEAD}/check-runs?per_page=100"
_CHECK_RUNS_PAGE_2 = f"/repositories/1/commits/{_HEAD}/check-runs?per_page=100&page=2"
_FILES = f"/repos/{_REPO}/pulls/{_PR}/files?per_page=100"
_FILES_PAGE_2 = f"/repositories/1/pulls/{_PR}/files?per_page=100&page=2"
_STATUS = f"repos/{_REPO}/commits/{_HEAD}/status"
_CHANGES_DIR = f"repos/{_REPO}/contents/openspec/changes?ref={_BASE}"
_THREADS = "GetReviewThreads"
_CLOSING = "closingIssuesReferences"
_ARCHIVE_704 = {
    "filename": "openspec/changes/archive/2026-10-23-704-x/proposal.md",
    "status": "added",
}
_SERVER_ERROR = ProcessAnswer(returncode=1, stderr="gh: Server Error (HTTP 500)")
_NOT_FOUND = ProcessAnswer(
    returncode=1, stdout='{"message": "Not Found"}', stderr="gh: Not Found (HTTP 404)"
)


def _pr(**overrides: object) -> dict[str, Any]:
    """PR #335's REST payload: open, mergeable and into the default branch, unless overridden."""
    repo = {"full_name": _REPO, "default_branch": "main"}
    payload: dict[str, Any] = {
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


def _run(name: str, conclusion: str | None = "success", status: str = "completed") -> dict:
    """One check run of the head commit."""
    return {"name": name, "status": status, "conclusion": conclusion}


def _thread(thread_id: str, *authors: str, resolved: bool = False) -> dict[str, Any]:
    """A review thread node whose comments are by `authors`, in order."""
    comments = [
        {"id": f"{thread_id}-{n}", "body": f"Comment {n}", "author": {"login": author}}
        for n, author in enumerate(authors)
    ]
    return {
        "id": thread_id,
        "isResolved": resolved,
        "path": "src/main.py",
        "line": 10,
        "comments": {"nodes": comments, "pageInfo": {"hasNextPage": False}},
    }


def _issue(number: int = 704, labels: tuple[str, ...] = ("priority/p2-medium",)) -> dict:
    """An open issue of the repository that the PR closes; a roadmap Item by default."""
    return {
        "number": number,
        "state": "OPEN",
        "repository": {"nameWithOwner": _REPO},
        "labels": {"nodes": [{"name": label} for label in labels]},
    }


class _GitHub:
    """GitHub as readiness reads it, scripted per test: by default every check passes, no
    review thread is open, the base keeps change folders, the PR archives #704's change and it
    closes open Item #704."""

    def __init__(self, api: GitHubApiFake, gh: ProcessFake) -> None:
        self.api, self.gh = api, gh
        self.checks(_run("CI"))
        self.statuses()
        self.files(_ARCHIVE_704)
        self.threads()
        self.answer(_CHANGES_DIR, ProcessAnswer())
        self.closing(_issue())

    def answer(self, route: str, answer: ProcessAnswer) -> None:
        """Answer each gh command whose arguments contain `route`."""
        self.gh.answer(lambda call, key=route: key in " ".join(call.argv), answer)

    def checks(self, *runs: dict) -> None:
        self.api.route(
            "GET", _CHECK_RUNS, github_json({"total_count": len(runs), "check_runs": runs})
        )

    def statuses(self, *statuses: dict, state: str = "success", total: int | None = None) -> None:
        payload = {
            "state": state,
            "statuses": list(statuses),
            "total_count": len(statuses) if total is None else total,
        }
        self.answer(_STATUS, ProcessAnswer(stdout=json.dumps(payload)))

    def files(self, *files: object) -> None:
        self.api.route("GET", _FILES, github_json(list(files)))

    def threads(self, *threads: dict[str, Any]) -> None:
        page = {"nodes": list(threads), "pageInfo": {"hasNextPage": False, "endCursor": None}}
        payload = {"data": {"repository": {"pullRequest": {"reviewThreads": page}}}}
        self.answer(_THREADS, ProcessAnswer(stdout=json.dumps(payload)))

    def closing(self, *issues: dict[str, Any], total: int | None = None) -> None:
        references = {"totalCount": len(issues) if total is None else total, "nodes": list(issues)}
        payload = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": references}}}}
        self.answer(_CLOSING, ProcessAnswer(stdout=json.dumps(payload)))

    def gh_sent(self) -> list[str]:
        """Each gh command run, as one string."""
        return [" ".join(call.argv) for call in self.gh.calls]


@pytest.fixture
def github(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> _GitHub:
    return _GitHub(*github_api_and_gh)


def _assess(tmp_path: Path, pr: dict[str, Any] | None = None, **options: bool) -> MergeReadiness:
    """PR #335's verdict, with `options` excused, its review.toml read from `tmp_path`."""
    return assess_merge_readiness(
        _pr() if pr is None else pr,
        _OWNER,
        _NAME,
        _PR,
        options=ReadinessOptions(**options),
        review_root=tmp_path,
    )


def _warning(text: str) -> Advisory:
    return Advisory(AdvisoryLevel.WARNING, text)


def test_a_clean_grounded_pull_request_is_ready(github: _GitHub, tmp_path: Path) -> None:
    """Adding rules must not make every pull request unmergeable."""
    verdict = _assess(tmp_path)
    assert (verdict.is_ready, verdict.blockers, verdict.advisories) == (True, (), ())


def test_a_merged_pull_request_is_ready_and_nothing_is_read(
    github: _GitHub, tmp_path: Path
) -> None:
    verdict = _assess(tmp_path, _pr(merged=True, state="closed"))
    assert (verdict, github.gh.calls, github.api.sent) == (MergeReadiness(), [], [])


@pytest.mark.parametrize(
    ("overrides", "options", "blockers", "advisories"),
    [
        (
            {"state": "closed"},
            {},
            ["PR #335 is closed without being merged."],
            [],
        ),
        (
            {"mergeable": False, "mergeable_state": "dirty"},
            {},
            ["PR #335 has merge conflicts with base branch 'main'."],
            [],
        ),
        (
            {"mergeable": None, "mergeable_state": "unknown"},
            {},
            [
                "PR #335 mergeability is unresolved or still calculating on GitHub "
                "(mergeable: None, state: 'unknown')."
            ],
            [],
        ),
        (
            {"mergeable_state": "blocked"},
            {},
            [
                "PR #335 merge state is blocked by GitHub branch protection or checks "
                "(state: 'blocked')."
            ],
            [],
        ),
        (
            {"mergeable_state": "blocked"},
            {"allow_blocked_state": True},
            [],
            [
                _warning(
                    "PR #335 merge state is currently 'blocked' by branch protection or pending "
                    "checks."
                )
            ],
        ),
        (
            {"draft": True},
            {},
            ["PR #335 is in draft status; GitHub refuses to merge a draft."],
            [],
        ),
        (
            {"draft": True},
            {"allow_draft": True},
            [],
            [_warning("PR #335 is in draft status and cannot be merged as-is.")],
        ),
    ],
    ids=[
        "closed",
        "conflicts",
        "mergeability-unknown",
        "blocked",
        "blocked-excused",
        "draft",
        "draft-excused",
    ],
)
def test_the_pull_request_state_blocks_unless_excused(
    github: _GitHub,
    tmp_path: Path,
    overrides: dict[str, object],
    options: dict[str, bool],
    blockers: list[str],
    advisories: list[Advisory],
) -> None:
    """GitHub refuses to merge a closed, conflicting or draft PR, and still reports
    `mergeable_state: clean` for a draft: PR #335 was once called ready while it was a draft."""
    verdict = _assess(tmp_path, _pr(**overrides), **options)
    assert (list(verdict.blockers), list(verdict.advisories)) == (blockers, advisories)


@pytest.mark.parametrize(
    ("runs", "options", "blockers", "advisories", "pending"),
    [
        (
            [_run("CodeQL", "failure"), _run("CI")],
            {},
            ["PR #335 has 1 failing check(s): CodeQL."],
            [],
            [],
        ),
        (
            [_run("Tests & Coverage", None, "in_progress")],
            {},
            ["PR #335 has 1 check(s) still running: Tests & Coverage."],
            [],
            ["Tests & Coverage"],
        ),
        (
            [_run("Tests & Coverage", None, "in_progress")],
            {"allow_pending_checks": True},
            [],
            [_warning("PR #335 has 1 check(s) still running: Tests & Coverage.")],
            ["Tests & Coverage"],
        ),
        (
            [_run("zizmor", "cancelled"), _run("audit", "timed_out")],
            {},
            ["PR #335 has 2 failing check(s): audit, zizmor."],
            [],
            [],
        ),
    ],
    ids=["failing", "running", "running-excused", "cancelled-and-timed-out"],
)
def test_checks_that_failed_or_still_run_block(
    github: _GitHub,
    tmp_path: Path,
    runs: list[dict],
    options: dict[str, bool],
    blockers: list[str],
    advisories: list[Advisory],
    pending: list[str],
) -> None:
    """Branch protection refuses a red pull request, and an unfinished check is not a passing
    one. A CI job checking its own pull request excuses the running ones, since it cannot wait
    for itself."""
    github.checks(*runs)
    verdict = _assess(tmp_path, **options)
    assert (list(verdict.blockers), list(verdict.advisories), list(verdict.pending_checks)) == (
        blockers,
        advisories,
        pending,
    )


@pytest.mark.parametrize(
    ("setup", "overrides", "kinds"),
    [
        (None, {"state": "closed"}, [BlockerKind.CLOSED]),
        (None, {"mergeable": False, "mergeable_state": "dirty"}, [BlockerKind.CONFLICT]),
        (None, {"mergeable": None, "mergeable_state": "unknown"}, [BlockerKind.MERGEABILITY]),
        (None, {"mergeable_state": "blocked"}, [BlockerKind.BRANCH_PROTECTION]),
        (None, {"draft": True}, [BlockerKind.DRAFT]),
        (lambda g: g.checks(_run("CodeQL", "failure")), {}, [BlockerKind.CHECKS_FAILING]),
        (lambda g: g.answer(_STATUS, _SERVER_ERROR), {}, [BlockerKind.CHECKS_UNREAD]),
        (
            lambda g: g.checks(_run("Tests & Coverage", None, "in_progress")),
            {},
            [BlockerKind.CHECKS_PENDING],
        ),
        (lambda g: g.threads(_thread("PRRT_1", "copilot")), {}, [BlockerKind.THREADS]),
        (lambda g: g.answer(_THREADS, _SERVER_ERROR), {}, [BlockerKind.THREADS_UNREAD]),
        (lambda g: g.closing(_issue(labels=())), {}, [BlockerKind.GROUNDING]),
        (None, {"mergeable_state": "behind"}, []),
    ],
    ids=[
        "closed",
        "conflict",
        "mergeability",
        "branch-protection",
        "draft",
        "checks-failing",
        "checks-unread",
        "checks-pending",
        "threads",
        "threads-unread",
        "grounding",
        "behind",
    ],
)
def test_each_blocker_keeps_its_kind(
    github: _GitHub,
    tmp_path: Path,
    setup: Any,
    overrides: dict[str, object],
    kinds: list[BlockerKind],
) -> None:
    """A command maps each kind to its own exit code, and prints the same text check-readiness
    prints. GitHub merges a branch behind its base when the ruleset does not require an
    up-to-date branch, so `behind` blocks nothing."""
    if setup is not None:
        setup(github)
    verdict = _assess(tmp_path, _pr(**overrides))
    assert ([blocker.kind for blocker in verdict.blocking], len(verdict.blockers)) == (
        kinds,
        len(kinds),
    )


def test_the_verdict_keeps_the_checks_it_read(github: _GitHub, tmp_path: Path) -> None:
    """The monitor shows its check table from the verdict's own read, with no second read."""
    github.checks(_run("CodeQL", "failure"), _run("CI"))
    checks = _assess(tmp_path).checks
    assert checks is not None
    assert sorted((item.name, item.bucket) for item in checks.items) == [
        ("CI", CheckBucket.PASS),
        ("CodeQL", CheckBucket.FAIL),
    ]


def test_a_commit_with_no_check_and_no_status_is_still_running(
    github: _GitHub, tmp_path: Path
) -> None:
    github.checks()
    verdict = _assess(tmp_path)
    assert verdict.blockers == ("PR #335 has 1 check(s) still running: no checks reported.",)


def test_a_failed_combined_commit_status_beyond_the_listed_ones_blocks(
    github: _GitHub, tmp_path: Path
) -> None:
    """GitHub lists 100 statuses at most; a failure among the rest shows in the combined state."""
    github.statuses({"context": "ci/a", "state": "success"}, state="failure", total=150)
    verdict = _assess(tmp_path)
    assert verdict.blockers == ("PR #335 has 1 failing check(s): commit status (combined).",)


@pytest.mark.parametrize(
    "second_page",
    [
        pytest.param(
            httpx2.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=b"<html>upstream 502 Bad Gateway</html>",
            ),
            id="html",
        ),
        pytest.param(github_json({"check_runs": "bad"}), id="runs-not-a-list"),
        pytest.param(github_json({"message": "Server Error"}), id="error-object"),
        pytest.param(github_json({"message": "Bad Gateway"}, status=502), id="5xx"),
    ],
)
def test_a_check_runs_page_that_cannot_be_read_fails_closed(
    github: _GitHub, tmp_path: Path, second_page: httpx2.Response
) -> None:
    """A check-runs page readiness can't read is a read failure, never a shorter list of passing
    checks."""
    github.api.route(
        "GET",
        _CHECK_RUNS,
        github_json(
            {"total_count": 2, "check_runs": [_run("ci-lint")]},
            headers=next_page(_CHECK_RUNS_PAGE_2),
        ),
    )
    github.api.route("GET", _CHECK_RUNS_PAGE_2, second_page)
    blockers = _assess(tmp_path).blockers
    assert (
        len(blockers),
        blockers[0].startswith("PR #335 check verification failed closed: "),
        any(cause in blockers[0] for cause in ("page 2", "HTTP 502")),
    ) == (1, True, True)


def test_a_commit_status_read_that_fails_fails_closed(github: _GitHub, tmp_path: Path) -> None:
    github.answer(_STATUS, _SERVER_ERROR)
    assert _assess(tmp_path).blockers == (
        "PR #335 check verification failed closed: GitHub commit status API error: "
        "gh: Server Error (HTTP 500)",
    )


def test_the_check_runs_of_a_commit_are_read_from_every_page(github: _GitHub) -> None:
    """The check-runs listing is read through the session, page after linked page."""
    github.api.route(
        "GET",
        _CHECK_RUNS,
        github_json(
            {"total_count": 2, "check_runs": [_run("ci-lint")]},
            headers=next_page(_CHECK_RUNS_PAGE_2),
        ),
    )
    github.api.route(
        "GET", _CHECK_RUNS_PAGE_2, github_json({"total_count": 2, "check_runs": [_run("ci-test")]})
    )
    checks = read_commit_checks(_OWNER, _NAME, _HEAD)
    assert [(item.name, item.bucket) for item in checks.items] == [
        ("ci-lint", CheckBucket.PASS),
        ("ci-test", CheckBucket.PASS),
    ]


def test_unresolved_review_threads_block_and_are_shown(github: _GitHub, tmp_path: Path) -> None:
    github.threads(_thread("T1", "copilot"), _thread("T2", "copilot", resolved=True))
    verdict = _assess(tmp_path)
    assert (verdict.blockers, [thread.id for thread in verdict.threads_to_show]) == (
        ("PR #335 has 1 unresolved review discussion thread(s).",),
        ["T1"],
    )


def test_with_replied_threads_allowed_only_unreplied_threads_block(
    github: _GitHub, tmp_path: Path
) -> None:
    """A reply by someone other than the opener awaits the reviewer; a follow-up by the opener
    alone, as a review probe posts, is still unreplied."""
    github.threads(
        _thread("T1", "copilot", "developer"),
        _thread("T2", "copilot"),
        _thread("T3", "copilot", "copilot"),
    )
    verdict = _assess(tmp_path, allow_replied_threads=True)
    assert (
        verdict.blockers,
        verdict.advisories,
        [thread.id for thread in verdict.threads_to_show],
    ) == (
        ("PR #335 has 2 unreplied review discussion thread(s).",),
        (
            Advisory(
                AdvisoryLevel.INFO,
                "PR #335 has 1 review discussion thread(s) with replies awaiting reviewer "
                "resolution.",
            ),
        ),
        ["T2", "T3"],
    )


def test_replied_threads_alone_do_not_block_when_allowed(github: _GitHub, tmp_path: Path) -> None:
    github.threads(_thread("T1", "copilot", "developer"))
    verdict = _assess(tmp_path, allow_replied_threads=True)
    assert (verdict.is_ready, verdict.threads_to_show) == (True, ())


def test_review_threads_that_cannot_be_read_block_naming_the_error(
    github: _GitHub, tmp_path: Path
) -> None:
    """A failed thread read is no proof that no thread is open (#797)."""
    github.answer(_THREADS, ProcessAnswer(returncode=1, stderr="GraphQL 502 Bad Gateway"))
    assert _assess(tmp_path).blockers == (
        "Could not retrieve review threads for PR #335: GitHub GraphQL query failed: "
        "GraphQL 502 Bad Gateway",
    )


def test_readiness_reads_the_files_the_base_and_the_closing_issues_once_each(
    github: _GitHub, tmp_path: Path
) -> None:
    """The files are one session listing at `per_page=100` (GitHub's default page is 30), then gh
    reads the base's change directory and the issues the PR closes, with their labels, in one
    GraphQL request. No project board is read."""
    verdict = _assess(tmp_path)
    sent = github.gh_sent()
    assert (
        [request for request in github.api.requested if "/files" in request],
        [command for command in sent if "contents/openspec" in command],
        [command for command in sent if _CLOSING in command],
        any("projectItems" in command for command in sent),
        verdict.grounding is not None and verdict.grounding.own_issue is not None,
    ) == (
        [f"GET https://api.github.com{_FILES}"],
        [f"gh api --silent {_CHANGES_DIR}"],
        [" ".join(closing_issues_args(_OWNER, _NAME, _PR))],
        False,
        True,
    )


def test_a_pr_into_another_branch_reads_no_closing_issues(github: _GitHub, tmp_path: Path) -> None:
    """GitHub closes an issue only when its PR merges into the default branch."""
    base = {
        "ref": "feat/stacked",
        "sha": _BASE,
        "repo": {"full_name": _REPO, "default_branch": "main"},
    }
    verdict = _assess(tmp_path, _pr(base=base))
    assert (verdict.blockers, any(_CLOSING in command for command in github.gh_sent())) == (
        (
            "PR #335 is not grounded: it targets feat/stacked, not the default branch main. "
            "Change its base with devops pr edit 335 --base main.",
        ),
        False,
    )


def test_a_base_without_change_folders_holds_no_item_rule(github: _GitHub, tmp_path: Path) -> None:
    """A 404 for `openspec/changes` means the repository keeps none, so nothing is required, and
    a file list that can't be read there is a warning, not a blocker."""
    github.answer(_CHANGES_DIR, _NOT_FOUND)
    github.api.route("GET", _FILES, github_json({"message": "Server Error"}, status=500))
    verdict = _assess(tmp_path)
    assert (
        verdict.blockers,
        verdict.grounding,
        [
            advisory.text.startswith("Could not read the files PR #335 changes")
            for advisory in verdict.advisories
        ],
    ) == ((), None, [True])


def test_a_change_directory_lookup_that_fails_blocks_naming_it(
    github: _GitHub, tmp_path: Path
) -> None:
    """Only a 404 rules the item rules out; any other failure is a blocker that names it."""
    github.answer(_CHANGES_DIR, _SERVER_ERROR)
    assert _assess(tmp_path).blockers == (
        "PR #335 is not grounded: openspec/changes/ could not be read at its base "
        "(gh: Server Error (HTTP 500)).",
    )


@pytest.mark.parametrize(
    ("answer", "cause"),
    [
        (_SERVER_ERROR, "(gh: Server Error (HTTP 500))"),
        (
            ProcessAnswer(stdout=json.dumps({"errors": [{"message": "Something went wrong"}]})),
            "(Something went wrong)",
        ),
        (ProcessAnswer(stdout=json.dumps({"data": {"repository": None}})), "(malformed reply:"),
        (ProcessAnswer(stdout="not json"), "(malformed reply:"),
    ],
    ids=["gh-failure", "graphql-error", "no-pull-request", "not-json"],
)
def test_closing_issues_that_cannot_be_read_are_one_blocker(
    github: _GitHub, tmp_path: Path, answer: ProcessAnswer, cause: str
) -> None:
    github.answer(_CLOSING, answer)
    blockers = _assess(tmp_path).blockers
    assert [
        blocker.startswith("PR #335 is not grounded: the issues it closes could not be read ")
        and cause in blocker
        for blocker in blockers
    ] == [True], blockers


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param("not an object", id="non-object"),
        pytest.param({"filename": "a.py"}, id="no-status"),
    ],
)
def test_a_malformed_files_entry_is_a_read_failure(
    github: _GitHub, tmp_path: Path, entry: object
) -> None:
    github.files(entry)
    blockers = _assess(tmp_path).blockers
    assert ["is no PullRequestFile: 1 invalid field(s)" in blocker for blocker in blockers] == [
        True
    ], blockers


def test_the_changed_files_are_read_from_every_linked_page(github: _GitHub) -> None:
    """PR #738 changed 51 files; a read stopping at GitHub's default page of 30 missed the rest."""
    first = [{"filename": f"src/m{n}.py", "status": "modified"} for n in range(100)]
    github.api.route("GET", _FILES, github_json(first, headers=next_page(_FILES_PAGE_2)))
    github.api.route("GET", _FILES_PAGE_2, github_json([_ARCHIVE_704]))
    read = read_changed_files(_OWNER, _NAME, _PR)
    assert (len(read.files), read.files[-1], read.error) == (
        101,
        PullRequestFile(filename=_ARCHIVE_704["filename"], status="added"),
        "",
    )


def test_a_changed_files_page_that_is_no_list_is_a_read_failure(github: _GitHub) -> None:
    """A malformed second page is the read's failure, not a shorter file list."""
    github.api.route("GET", _FILES, github_json([_ARCHIVE_704], headers=next_page(_FILES_PAGE_2)))
    github.api.route(
        "GET",
        _FILES_PAGE_2,
        httpx2.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>"),
    )
    read = read_changed_files(_OWNER, _NAME, _PR)
    assert (read.files, "page 2" in read.error) == ([], True)


def test_the_closing_issues_read_asks_for_the_pr_and_both_page_sizes() -> None:
    argv = closing_issues_args(_OWNER, _NAME, _PR)
    assert (argv[:3], argv[-10:], "projectItems" in " ".join(argv)) == (
        ["gh", "api", "graphql"],
        [
            "-f",
            "owner=dan-petty",
            "-f",
            "name=devops-cli",
            "-F",
            "number=335",
            "-F",
            "issues=10",
            "-F",
            "labels=100",
        ],
        False,
    )


_REVIEW_TOML = """\
[[suppressions]]
rule = "B602"
path = "src/a.py"
reason = "The argv is a constant list"
expiry = "2099-12-31"

[[suppressions]]
rule = "B603"
path = "src/b.py"
reason = "Expired reason"
expiry = "2020-01-01"
"""


def test_a_pr_touching_a_suppressed_file_names_the_suppression(
    github: _GitHub, tmp_path: Path
) -> None:
    """Of the two suppressions on the changed files, the advisory names the unexpired one's rule,
    path and reason (#1150), and blocks nothing."""
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.toml").write_text(_REVIEW_TOML, encoding="utf-8")
    github.files(
        _ARCHIVE_704,
        {"filename": "src/a.py", "status": "modified"},
        {"filename": "src/b.py", "status": "modified"},
    )
    verdict = _assess(tmp_path)
    text = " ".join(" ".join(advisory.text for advisory in verdict.advisories).split())
    assert (
        verdict.blockers,
        [advisory.level for advisory in verdict.advisories],
        "1 review.toml suppression" in text,
        "B602" in text and "src/a.py" in text and "The argv is a constant list" in text,
        "B603" in text or "Expired reason" in text,
    ) == ((), [AdvisoryLevel.WARNING], True, True, False)


def test_a_pr_touching_no_suppressed_file_has_no_advisory(github: _GitHub, tmp_path: Path) -> None:
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.toml").write_text(_REVIEW_TOML, encoding="utf-8")
    github.files(_ARCHIVE_704, {"filename": "docs/notes.md", "status": "modified"})
    assert _assess(tmp_path).advisories == ()


def test_readiness_runs_every_gh_command_through_the_given_runner(
    github: _GitHub, tmp_path: Path
) -> None:
    """A caller that gives its own runner sees every gh command readiness sends."""
    sent: list[list[str]] = []

    def runner(args: list[str], **kwargs: Any) -> Any:
        from devops_cli.github.rate_limiter import run_gh

        sent.append(list(args))
        return run_gh(args, **kwargs)

    assess_merge_readiness(_pr(), _OWNER, _NAME, _PR, runner=runner, review_root=tmp_path)
    assert (len(sent), len(github.gh.calls)) == (4, 4)
