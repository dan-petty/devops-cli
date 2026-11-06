"""Integration tests for devops pr hardening-report command (#697)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.support.fakes.process import ProcessAnswer, ProcessFake


def _answer_gh(process_fake: ProcessFake, payload: object) -> None:
    """Answer every `gh pr` command with `payload` as JSON."""
    process_fake.answer(
        lambda call: Path(call.argv[0]).name == "gh" and call.argv[1] == "pr",
        ProcessAnswer(stdout=json.dumps(payload)),
    )


def test_hardening_report_single_pr_hardened(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """Audit single defect PR that includes additions on docs/TESTING.md."""
    pr_payload = {
        "number": 101,
        "title": "fix(cli): resolve option crash",
        "labels": [{"name": "type/bug"}],
        "state": "MERGED",
        "files": [
            {"path": "src/devops_cli/commands/pr.py", "additions": 20, "deletions": 5},
            {"path": "docs/TESTING.md", "additions": 5, "deletions": 0},
        ],
    }

    _answer_gh(process_fake, pr_payload)
    res = cli(["pr", "hardening-report", "--pr", "101"])

    assert (res.exit_code, "Hardened" in res.stdout, "#101" in res.stdout) == (
        0,
        True,
        True,
    )


def test_hardening_report_single_pr_missing_hardening(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """Audit single defect PR lacking additions on declared surfaces."""
    pr_payload = {
        "number": 102,
        "title": "fix(ai): repair model prompt parsing",
        "labels": [{"name": "type/bug"}],
        "state": "MERGED",
        "files": [
            {"path": "src/devops_cli/ai/prompt.py", "additions": 15, "deletions": 2},
            {"path": "docs/SDLC.md", "additions": 10, "deletions": 0},  # not a surface
        ],
    }

    _answer_gh(process_fake, pr_payload)

    # Default run succeeds and shows status Missing
    res_default = cli(["pr", "hardening-report", "--pr", "102"])
    assert (res_default.exit_code, "Missing" in res_default.stdout) == (0, True)

    # --fail-on-missing exits with code 1
    res_fail = cli(["pr", "hardening-report", "--pr", "102", "--fail-on-missing"])
    assert (res_fail.exit_code, "failed hardening audit" in res_fail.output) == (1, True)


def test_hardening_report_single_pr_not_defect(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """Audit single feature PR: reports not a defect and succeeds."""
    pr_payload = {
        "number": 103,
        "title": "feat(cli): add new inspection subcommand",
        "labels": [{"name": "type/feature"}],
        "state": "MERGED",
        "files": [{"path": "src/devops_cli/commands/inspect.py", "additions": 80, "deletions": 0}],
    }

    _answer_gh(process_fake, pr_payload)
    res = cli(["pr", "hardening-report", "--pr", "103", "--fail-on-missing"])

    assert (res.exit_code, "not classified as a defect PR" in res.output) == (0, True)


def test_hardening_report_single_pr_empty_files_fails(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """Audit single PR returning empty files list triggers error state."""
    pr_payload = {
        "number": 104,
        "title": "fix(k8s): defect fix",
        "labels": [{"name": "type/bug"}],
        "state": "MERGED",
        "files": [],
    }

    _answer_gh(process_fake, pr_payload)
    res = cli(["pr", "hardening-report", "--pr", "104", "--fail-on-missing"])

    assert (res.exit_code, "empty file list" in res.output) == (1, True)


def test_hardening_report_json_format(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """Format hardening audit results as structured JSON."""
    pr_payload = {
        "number": 105,
        "title": "fix: resolve deadlock",
        "labels": [],
        "state": "MERGED",
        "files": [
            {"path": "src/devops_cli/lock.py", "additions": 10, "deletions": 1},
            {"path": "docs/TESTING.md", "additions": 4, "deletions": 0},
        ],
    }

    _answer_gh(process_fake, pr_payload)
    res = cli(["pr", "hardening-report", "--pr", "105", "--format", "json"])

    assert res.exit_code == 0
    parsed = json.loads(res.stdout)
    assert (
        len(parsed),
        parsed[0]["pr_number"],
        parsed[0]["is_defect"],
        parsed[0]["is_hardened"],
        parsed[0]["surfaces"]["docs/TESTING.md"],
    ) == (
        1,
        105,
        True,
        True,
        4,
    )


def test_hardening_report_list_merged_prs(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """List and audit multiple merged defect PRs from repository."""
    list_payload = [
        {
            "number": 201,
            "title": "fix(ci): fix flaky runner",
            "labels": [{"name": "type/bug"}],
            "files": [
                {"path": "ci.sh", "additions": 10, "deletions": 2},
                {"path": "docs/TESTING.md", "additions": 2, "deletions": 0},
            ],
        },
        {
            "number": 202,
            "title": "feat(github): new feature",
            "labels": [{"name": "type/feature"}],
            "files": [{"path": "feat.py", "additions": 50, "deletions": 0}],
        },
        {
            "number": 203,
            "title": "fix(sec): credential leak prevention",
            "labels": [{"name": "type/security"}],
            "files": [
                {"path": "src/devops_cli/secrets.py", "additions": 12, "deletions": 3},
                {"path": ".devops/review.toml", "additions": 6, "deletions": 0},
            ],
        },
        {
            "number": 204,
            "title": "fix: unhardened patch",
            "labels": [],
            "files": [
                {"path": "patch.py", "additions": 5, "deletions": 1},
                {"path": "AGENTS.md", "additions": 6, "deletions": 0},
            ],
        },
    ]

    _answer_gh(process_fake, list_payload)

    # Table mode
    res_table = cli(["pr", "hardening-report"])
    assert (
        res_table.exit_code,
        "#201" in res_table.stdout,
        "#202" not in res_table.stdout,  # filtered out: not defect
        "#203" in res_table.stdout,
        "#204" in res_table.stdout,
        "1 of 3 defect PRs lack additions" in res_table.stdout,
    ) == (0, True, True, True, True, True)

    # Fail on missing
    res_fail = cli(["pr", "hardening-report", "--fail-on-missing"])
    assert res_fail.exit_code == 1

    # JSON mode
    res_json = cli(["pr", "hardening-report", "--format", "json"])
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.stdout)
    assert len(parsed) == 3


def test_hardening_report_list_no_defects(cli: Any, github_api_and_gh: Any) -> None:
    process_fake = github_api_and_gh[1]
    """Report information when no merged defect PRs exist."""
    list_payload = [
        {
            "number": 301,
            "title": "feat: feature 1",
            "labels": [{"name": "type/feature"}],
            "files": [],
        },
        {
            "number": 302,
            "title": "chore: deps bump",
            "labels": [{"name": "type/chore"}],
            "files": [],
        },
    ]

    _answer_gh(process_fake, list_payload)
    res = cli(["pr", "hardening-report"])

    assert (res.exit_code, "No merged defect pull requests found" in res.stdout) == (0, True)
