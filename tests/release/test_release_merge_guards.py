"""The guards of the scheduled merge: which release pull request may merge by itself (#3921)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import PullRequestFile
from devops_cli.release.merge_candidate import (
    HOLD_LABEL,
    RELEASE_FILES,
    RELEASE_LABEL,
    ReleaseFacts,
    ReleasePull,
    refusals,
)

APP = "example-release[bot]"
REPOSITORY = "example/project"
REQUIRED = ("Static Analysis", "Tests & Coverage", "Semantic PR title")


def _pull(**changes: Any) -> ReleasePull:
    """A release pull request as GitHub's REST API answers it, with `changes` applied."""
    payload: dict[str, Any] = {
        "number": 41,
        "title": "chore(main): release 1.4.0",
        "state": "open",
        "draft": False,
        "user": {"login": APP},
        "head": {
            "ref": "release-please--branches--main--components--project",
            "sha": "a" * 40,
            "repo": {"full_name": REPOSITORY},
        },
        "base": {"ref": "main"},
        "labels": [{"name": RELEASE_LABEL}],
        "mergeable": True,
        "mergeable_state": "clean",
    }
    payload.update(changes)
    return ReleasePull.model_validate(payload)


def _checks(**states: str) -> CheckVerdictSummary:
    """A summary with one check for each name of `states`, in the state it gives."""
    buckets = {
        "success": CheckBucket.PASS,
        "failure": CheckBucket.FAIL,
        "cancelled": CheckBucket.CANCEL,
        "in_progress": CheckBucket.PENDING,
        "skipped": CheckBucket.SKIPPING,
    }
    return CheckVerdictSummary(
        items=[PRCheckItem(name=n, state=s, bucket=buckets[s]) for n, s in states.items()]
    )


def _green(*extra: str) -> CheckVerdictSummary:
    return _checks(**{name: "success" for name in (*REQUIRED, *extra)})


def _modified(*paths: str) -> tuple[PullRequestFile, ...]:
    return tuple(PullRequestFile(filename=path, status="modified") for path in paths)


def _facts(**changes: Any) -> ReleaseFacts:
    """Facts under which the pull request may merge, with `changes` applied."""
    facts: dict[str, Any] = {
        "pull": _pull(),
        "repository": REPOSITORY,
        "app_login": APP,
        "files": _modified(*sorted(RELEASE_FILES)),
        "required_checks": REQUIRED,
        "pull_checks": _green("Docs Site Build"),
        "base_checks": _green(),
    }
    facts.update(changes)
    return ReleaseFacts(**facts)


def test_a_release_pull_request_that_passes_every_guard_may_merge() -> None:
    assert refusals(_facts()) == []


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"state": "closed"}, "is not open"),
        ({"draft": True}, "is a draft"),
        ({"user": {"login": "someone-else"}}, "not by the release App"),
        ({"labels": []}, f"no label `{RELEASE_LABEL}`"),
        ({"labels": [{"name": RELEASE_LABEL}, {"name": HOLD_LABEL}]}, "holds the release"),
        ({"title": "chore(main): release latest"}, "is not `chore(main): release <version>`"),
        ({"title": "fix(cli): release 1.4.0"}, "is not `chore(main): release <version>`"),
        ({"base": {"ref": "develop"}}, "not from a release-please branch"),
        ({"mergeable": None, "mergeable_state": "unknown"}, "does not report"),
        ({"mergeable": False, "mergeable_state": "dirty"}, "does not report"),
        ({"mergeable_state": "blocked"}, "does not report"),
    ],
)
def test_a_pull_request_fact_that_fails_a_guard_keeps_the_release_from_merging(
    changes: dict[str, Any], reason: str
) -> None:
    found = refusals(_facts(pull=_pull(**changes)))

    assert len(found) == 1
    assert reason in found[0]


@pytest.mark.parametrize(
    "head",
    [
        {"ref": "feature/release", "sha": "a" * 40, "repo": {"full_name": REPOSITORY}},
        {
            "ref": "release-please--branches--main",
            "sha": "a" * 40,
            "repo": {"full_name": "fork/project"},
        },
        {"ref": "release-please--branches--main", "sha": "a" * 40, "repo": None},
    ],
)
def test_a_head_outside_the_release_please_branch_of_this_repository_is_refused(
    head: dict[str, Any],
) -> None:
    found = refusals(_facts(pull=_pull(head=head)))

    assert len(found) == 1
    assert "not from a release-please branch" in found[0]


def test_the_author_is_compared_without_regard_to_case() -> None:
    assert refusals(_facts(pull=_pull(user={"login": APP.upper()}))) == []


def test_an_unstable_state_does_not_refuse_a_pull_request_whose_guards_pass() -> None:
    """`unstable` means that a check which no rule requires is not green. The guards read the
    checks themselves, so the state alone refuses nothing."""
    assert refusals(_facts(pull=_pull(mergeable_state="unstable"))) == []


@pytest.mark.parametrize(
    "files",
    [
        _modified("CHANGELOG.md", "src/devops_cli/main.py"),
        _modified("README.md"),
        (PullRequestFile(filename="CHANGELOG.md", status="removed"),),
        (PullRequestFile(filename="uv.lock", status="added"),),
        (PullRequestFile(filename="uv.lock", status="renamed", previous_filename="old.lock"),),
        (PullRequestFile(filename="CHANGELOG.md", status="renamed", previous_filename="uv.lock"),),
    ],
)
def test_a_file_that_release_please_does_not_write_keeps_the_release_from_merging(
    files: tuple[PullRequestFile, ...],
) -> None:
    found = refusals(_facts(files=files))

    assert found
    assert all("which release-please does not write" in reason for reason in found)


def test_a_pull_request_that_changes_a_subset_of_the_release_files_may_merge() -> None:
    assert refusals(_facts(files=_modified("CHANGELOG.md", "pyproject.toml"))) == []


def test_a_required_check_that_did_not_pass_keeps_the_release_from_merging() -> None:
    checks = _checks(
        **{
            "Static Analysis": "failure",
            "Tests & Coverage": "success",
            "Semantic PR title": "in_progress",
        }
    )

    found = refusals(_facts(pull_checks=checks))

    assert sorted(found) == [
        "The required check `Semantic PR title` is in_progress on the head of pull request 41.",
        "The required check `Static Analysis` is failure on the head of pull request 41.",
    ]


def test_a_required_check_that_was_skipped_does_not_count_as_a_pass() -> None:
    checks = _checks(
        **{
            "Static Analysis": "skipped",
            "Tests & Coverage": "success",
            "Semantic PR title": "success",
        }
    )

    assert refusals(_facts(pull_checks=checks)) == [
        "The required check `Static Analysis` is skipped on the head of pull request 41."
    ]


def test_a_required_check_that_has_not_run_keeps_the_release_from_merging() -> None:
    checks = _checks(**{"Static Analysis": "success", "Tests & Coverage": "success"})

    assert refusals(_facts(pull_checks=checks)) == [
        "The required check `Semantic PR title` has not run on the head of pull request 41."
    ]


def test_a_check_that_no_rule_requires_and_failed_keeps_the_release_from_merging() -> None:
    """The publish jobs of the release run the same scans as these checks, so a release whose
    scan fails here would tag a version and publish no image."""
    found = refusals(_facts(pull_checks=_green("Service Image")))
    assert found == []

    states = {name: "success" for name in REQUIRED} | {"Service Image": "failure"}
    assert refusals(_facts(pull_checks=_checks(**states))) == [
        "The check `Service Image` failed on the head of pull request 41."
    ]


def test_a_check_that_no_rule_requires_and_is_skipped_or_running_does_not_refuse() -> None:
    states = {name: "success" for name in REQUIRED} | {
        "Plan Check": "skipped",
        "Docs": "in_progress",
    }

    assert refusals(_facts(pull_checks=_checks(**states))) == []


def test_a_required_check_that_failed_on_the_head_of_main_keeps_the_release_from_merging() -> None:
    base = _checks(
        **{
            "Static Analysis": "failure",
            "Tests & Coverage": "success",
            "Semantic PR title": "success",
        }
    )

    assert refusals(_facts(base_checks=base)) == [
        "The required check `Static Analysis` failed on the head of main."
    ]


def test_a_required_check_that_still_runs_on_the_head_of_main_does_not_refuse() -> None:
    base = _checks(**{"Static Analysis": "in_progress", "Tests & Coverage": "success"})

    assert refusals(_facts(base_checks=base)) == []


def test_a_check_that_is_not_required_and_failed_on_main_does_not_refuse() -> None:
    base = _green()
    base.items.append(PRCheckItem(name="Image Pins", state="failure", bucket=CheckBucket.FAIL))

    assert refusals(_facts(base_checks=base)) == []


def test_rules_that_require_no_check_refuse_the_merge() -> None:
    assert refusals(_facts(required_checks=())) == ["The rules of main name no required check."]


def test_checks_that_could_not_be_read_refuse_the_merge() -> None:
    unread = CheckVerdictSummary(unread_reason="GitHub check-runs API error: boom")

    found = refusals(_facts(pull_checks=unread, base_checks=unread))

    assert found == [
        "The checks of the head of pull request 41 could not be read: "
        "GitHub check-runs API error: boom.",
        "The checks of the head of main could not be read: GitHub check-runs API error: boom.",
    ]
