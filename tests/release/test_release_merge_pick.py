"""The pick of the release pull request that the scheduled merge merges (#3921)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.github.session import get_github_session
from devops_cli.release.merge_candidate import (
    HOLD_LABEL,
    RELEASE_FILES,
    RELEASE_LABEL,
    Candidate,
    main,
    pick,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.paths import REPO_ROOT

APP = "example-release[bot]"
REPO = "example/project"
RELEASE_HEAD = "a" * 40
BASE_HEAD = "b" * 40
REQUIRED = ("Static Analysis", "Tests & Coverage", "Semantic PR title")


def _runs(sha: str) -> str:
    return f"/repos/{REPO}/commits/{sha}/check-runs?per_page=100"


def _check_runs(*names: str, failing: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "total_count": len(names),
        "check_runs": [
            {
                "name": name,
                "status": "completed",
                "conclusion": "failure" if name in failing else "success",
            }
            for name in names
        ],
    }


def _detail(
    number: int, *, labels: tuple[str, ...] = (RELEASE_LABEL,), sha: str = RELEASE_HEAD
) -> dict[str, Any]:
    return {
        "number": number,
        "title": "chore(main): release 1.4.0",
        "state": "open",
        "draft": False,
        "user": {"login": APP},
        "head": {
            "ref": "release-please--branches--main--components--project",
            "sha": sha,
            "repo": {"full_name": REPO},
        },
        "base": {"ref": "main"},
        "labels": [{"name": label} for label in labels],
        "mergeable": True,
        "mergeable_state": "clean",
    }


def _serve_repository(api: GitHubApiFake, *, pulls: dict[int, dict[str, Any]]) -> None:
    """Route the reads of the pick: the open pull requests, the rules, `main`, and the checks,
    files and detail of each pull request."""
    api.route(
        "GET",
        f"/repos/{REPO}/pulls?state=open&base=main&per_page=100",
        github_json(
            [{"number": number, "labels": detail["labels"]} for number, detail in pulls.items()]
        ),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/rules/branches/main?per_page=100",
        github_json(
            [
                {"type": "deletion"},
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [{"context": name} for name in REQUIRED]
                    },
                },
            ]
        ),
    )
    api.route("GET", f"/repos/{REPO}/branches/main", github_json({"commit": {"sha": BASE_HEAD}}))
    api.route("GET", _runs(BASE_HEAD), github_json(_check_runs(*REQUIRED)))
    for number, detail in pulls.items():
        api.route("GET", f"/repos/{REPO}/pulls/{number}", github_json(detail))
        api.route(
            "GET",
            f"/repos/{REPO}/pulls/{number}/files?per_page=100",
            github_json(
                [{"filename": path, "status": "modified"} for path in sorted(RELEASE_FILES)]
            ),
        )
        api.route("GET", _runs(detail["head"]["sha"]), github_json(_check_runs(*REQUIRED, "Docs")))


def test_the_pick_returns_the_release_pull_request_that_passes_every_guard(
    github_api: GitHubApiFake,
) -> None:
    _serve_repository(github_api, pulls={41: _detail(41)})
    lines: list[str] = []

    picked = pick(get_github_session(), REPO, APP, lines.append)

    assert picked == Candidate(number=41, head_sha=RELEASE_HEAD)
    assert lines == []


def test_the_pick_skips_a_pull_request_without_the_release_label_and_does_not_read_it(
    github_api: GitHubApiFake,
) -> None:
    _serve_repository(github_api, pulls={7: _detail(7, labels=("bug",)), 41: _detail(41)})

    picked = pick(get_github_session(), REPO, APP, lambda line: None)

    assert picked == Candidate(number=41, head_sha=RELEASE_HEAD)
    assert not any(url.endswith("/pulls/7") for url in github_api.requested)


def test_the_pick_returns_nothing_and_says_why_when_a_guard_refuses(
    github_api: GitHubApiFake,
) -> None:
    _serve_repository(github_api, pulls={41: _detail(41, labels=(RELEASE_LABEL, HOLD_LABEL))})
    lines: list[str] = []

    assert pick(get_github_session(), REPO, APP, lines.append) is None
    assert lines == [
        f"Pull request 41 does not merge: Pull request 41 has the label `{HOLD_LABEL}`: "
        "a person holds the release.\n"
    ]


def test_the_pick_returns_at_most_one_pull_request(github_api: GitHubApiFake) -> None:
    _serve_repository(github_api, pulls={52: _detail(52, sha="c" * 40), 41: _detail(41)})

    picked = pick(get_github_session(), REPO, APP, lambda line: None)

    assert picked == Candidate(number=41, head_sha=RELEASE_HEAD)
    assert not any("/pulls/52" in url for url in github_api.requested)


def test_the_pick_returns_nothing_when_no_pull_request_has_the_release_label(
    github_api: GitHubApiFake,
) -> None:
    _serve_repository(github_api, pulls={7: _detail(7, labels=("bug",))})
    lines: list[str] = []

    assert pick(get_github_session(), REPO, APP, lines.append) is None
    assert lines == [f"No open pull request has the label `{RELEASE_LABEL}`.\n"]


def test_main_prints_the_pull_request_for_the_output_file_of_the_workflow(
    github_api: GitHubApiFake, capsys: pytest.CaptureFixture[str]
) -> None:
    _serve_repository(github_api, pulls={41: _detail(41)})

    assert main(["--repo", REPO, "--app-login", APP]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"number=41\nsha={RELEASE_HEAD}\n"
    assert f"Pull request 41 may merge at {RELEASE_HEAD}." in captured.err


def test_main_prints_nothing_on_standard_output_when_no_pull_request_may_merge(
    github_api: GitHubApiFake, capsys: pytest.CaptureFixture[str]
) -> None:
    _serve_repository(github_api, pulls={41: _detail(41, labels=(RELEASE_LABEL, HOLD_LABEL))})

    assert main(["--repo", REPO, "--app-login", APP]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No release pull request may merge now." in captured.err


def test_main_fails_when_github_cannot_be_read_so_a_failed_read_never_looks_like_a_refusal(
    github_api: GitHubApiFake, capsys: pytest.CaptureFixture[str]
) -> None:
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?state=open&base=main&per_page=100",
        github_json({"message": "Server Error"}, status=500),
    )

    assert main(["--repo", REPO, "--app-login", APP]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "The release pull request could not be read" in captured.err


def test_the_files_that_release_please_writes_are_the_ones_its_configuration_names() -> None:
    """The guard on files names the manifest, the changelog and the version of the package, and
    the extra files of the configuration. A new extra file of release-please joins the guard."""
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    package = config["packages"]["."]
    extra = {entry["path"] for entry in package["extra-files"]}
    manifest = Path(config.get("manifest-file", ".release-please-manifest.json")).name

    assert RELEASE_FILES == {manifest, "CHANGELOG.md", "pyproject.toml", *extra}
    assert config["release-type"] == "python"
