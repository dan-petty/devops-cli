"""The GitHub read snapshot that `--phase prepare` hands to `--phase agent` (#6831). It holds the
text of an account that the jobs trust only (`roadmap/trust.py`)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
import time_machine
from pydantic_ai import Agent
from pydantic_ai.capabilities import LocalWorkspace
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai_harness.coder import Coder

from devops_cli.config.constants import (
    CONST_ROADMAP_ACTIONS_BOT_LOGIN,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stage.stage_job import run_stage_job
from devops_cli.roadmap.stage.stage_job_phases import prepare_stage_job, run_stage_agent
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json, next_page
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.github_identity import fail_the_github_lookup
from tests.support.model_script import ModelScript, say
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)
from tests.support.roadmap_stage_phases import PHASE_CHANGE, gate_files

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
_SECRET = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
_MAX_INDEX_ISSUES = 1000
_MAX_INDEX_BODY_CHARS = 500
_APP = "devops-cli-service[bot]"
_OWNER: dict[str, Any] = {"author_association": "OWNER", "user": {"login": "a-person"}}
_STRANGER: dict[str, Any] = {"author_association": "NONE", "user": {"login": "a-stranger"}}
_LEFT_OUT = (
    "An account with no write access opened this item. "
    "Its title, its body and its comments are left out."
)
_PATCH_LEFT_OUT = (
    "An account with no write access opened this pull request. Its patch text is left out."
)
_TITLE_LEFT_OUT = "(title left out: an account with no write access opened the item)"
_PULL_OWNER: dict[str, Any] = {
    "authorAssociation": "OWNER",
    "author": {"__typename": "User", "login": "a-person"},
}


def _route_open_pulls(api: GitHubApiFake, nodes: list[dict[str, Any]]) -> None:
    """Answer the GraphQL read of the open pull requests with one page of `nodes`."""
    page = {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}
    api.route("POST", "/graphql", github_json({"data": {"repository": {"pullRequests": page}}}))


@pytest.fixture
def fake_github(github_api: GitHubApiFake) -> GitHubApiFake:
    """Seed GraphQL and default empty listings on `github_api` unless overridden by a test."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    github_api.route("GET", f"/repos/{STAGE_REPO}/issues?state=open&per_page=100", github_json([]))
    github_api.route(
        "POST",
        "/graphql",
        github_json({"data": {"repository": {"pullRequests": {"nodes": [], "pageInfo": {}}}}}),
    )
    return github_api


@pytest.fixture
def app_login(config: Callable[..., Path]) -> str:
    """The slug of the Service App, so that `_APP` is the login of its bot."""
    config(service={"github_app": {"slug": _APP.removesuffix("[bot]")}})
    return _APP


def _route_issue(api: GitHubApiFake, number: int, **fields: Any) -> None:
    """Answer the read of the item `number`: an open issue of the owner unless `fields` say more."""
    payload = {
        "number": number,
        "title": f"title of {number}",
        "state": "open",
        "body": "The body.",
        "comments": 0,
        "labels": [],
        **_OWNER,
        **fields,
    }
    api.route("GET", f"/repos/{STAGE_REPO}/issues/{number}", github_json(payload))


def _route_comments(api: GitHubApiFake, number: int, comments: list[dict[str, Any]]) -> None:
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues/{number}/comments?per_page=100&page=1",
        github_json(comments),
    )


def _route_pull_files(api: GitHubApiFake, number: int, patch: str) -> None:
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{number}/files?per_page=100",
        github_json(
            [
                {
                    "filename": "src/app.py",
                    "status": "modified",
                    "additions": 1,
                    "changes": 2,
                    "patch": patch,
                }
            ]
        ),
    )


def _issue_file(folders: RunFolders, number: int) -> dict[str, Any]:
    path = folders.work / "github" / "issues" / f"{number}.json"
    found: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return found


def _prepare(
    store: InMemoryRoadmapStore, repo: StageRepo, tmp_path: Path, body: str
) -> tuple[RunFolders, int]:
    folders = RunFolders(tmp_path / "run").make()
    number = seed_stageable(store, body=body)
    ended = prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=NOW
    )
    assert ended is None
    return folders, number


def test_prepare_writes_named_issues_with_comments(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues/12",
        github_json(
            {
                "number": 12,
                "title": "feat: first issue",
                "state": "open",
                "body": f"Body with {_SECRET}",
                "comments": 1,
                "labels": [{"name": "status/ready"}, {"name": "P2-Medium"}],
                **_OWNER,
            }
        ),
    )
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues/12/comments?per_page=100&page=1",
        github_json([{"body": "Keep the API small.", **_OWNER}]),
    )
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues/34",
        github_json(
            {
                "number": 34,
                "title": "fix: second issue",
                "state": "closed",
                "state_reason": "completed",
                "body": "Closed earlier.",
                "comments": 0,
                "labels": [{"name": "type/fix"}],
                **_OWNER,
            }
        ),
    )
    fake_github.route("GET", f"/repos/{STAGE_REPO}/issues/34/events?per_page=100", github_json([]))

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Follows #12 and #34.")

    issue_12 = json.loads((folders.work / "github" / "issues" / "12.json").read_text("utf-8"))
    issue_34 = folders.work / "github" / "issues" / "34.json"
    assert issue_34.is_file()
    assert issue_12["state"] == "open"
    assert issue_12["title"] == "feat: first issue"
    assert issue_12["labels"] == ["status/ready", "P2-Medium"]
    assert _SECRET not in issue_12["body"]
    assert issue_12["comments"] == ["Keep the API small."]


def test_prepare_writes_open_pull_requests_with_paths(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    fake_github.route(
        "POST",
        "/graphql",
        github_json(
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": [
                                {
                                    "number": 101,
                                    "title": "docs(openspec): plan #11",
                                    "state": "OPEN",
                                    "files": {
                                        "nodes": [{"path": "openspec/changes/11/proposal.md"}]
                                    },
                                    **_PULL_OWNER,
                                },
                                {
                                    "number": 102,
                                    "title": "fix: update handler",
                                    "state": "OPEN",
                                    "files": {"nodes": [{"path": "src/app.py"}]},
                                    **_PULL_OWNER,
                                },
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        ),
    )

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Update the command.")

    pulls = json.loads((folders.work / "github" / "pulls.json").read_text("utf-8"))
    assert [(p["number"], p["title"]) for p in pulls] == [
        (101, "docs(openspec): plan #11"),
        (102, "fix: update handler"),
    ]
    assert "src/app.py" in pulls[1]["files"]


def test_prepare_writes_files_of_named_pull_request(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues/56",
        github_json(
            {
                "number": 56,
                "title": "fix: prior change",
                "state": "closed",
                "body": "Merged earlier.",
                "comments": 0,
                "labels": [],
                "pull_request": {"merged_at": "2026-11-20T10:00:00Z"},
                **_OWNER,
            }
        ),
    )
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/56/files?per_page=100",
        github_json(
            [
                {
                    "filename": "src/app.py",
                    "status": "modified",
                    "additions": 1,
                    "changes": 2,
                    "patch": f"@@ -1 +1 @@\n-token={_SECRET}\n+pass",
                }
            ]
        ),
    )

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="See #56 for context.")

    saved = json.loads((folders.work / "github" / "pull-files" / "56.json").read_text("utf-8"))
    assert saved["number"] == 56
    assert saved["files"][0]["filename"] == "src/app.py"
    assert _SECRET not in saved["files"][0]["patch"]
    assert "@@ -1 +1 @@" in saved["files"][0]["patch"]


def test_prepare_writes_bounded_issue_index_for_3000_open_issues(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    long_body = "x" * 2000
    per_page = 100
    for page_idx in range(30):
        page_num = page_idx + 1
        start = page_idx * per_page + 100
        payload = [
            {
                "number": start + offset,
                "title": f"Issue {start + offset}",
                "state": "open",
                "body": long_body,
                "comments": 0,
                "labels": [],
                **_OWNER,
            }
            for offset in range(per_page)
        ]
        url = (
            f"/repos/{STAGE_REPO}/issues?state=open&per_page=100"
            if page_num == 1
            else f"/repos/{STAGE_REPO}/issues?state=open&per_page=100&page={page_num}"
        )
        headers = (
            next_page(f"/repos/{STAGE_REPO}/issues?state=open&per_page=100&page={page_num + 1}")
            if page_num < 30
            else {}
        )
        fake_github.route("GET", url, github_json(payload, headers=headers))

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Search open issues.")

    index_path = folders.work / "github" / "issue-index.jsonl"
    raw = index_path.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    assert 0 < len(lines) <= _MAX_INDEX_ISSUES
    assert len(raw) <= CONST_ROADMAP_PHASE_JSON_MAX_BYTES
    for line in lines:
        obj = json.loads(line)
        assert len(obj["body"]) <= _MAX_INDEX_BODY_CHARS
    # Stopped early instead of fetching all 30 pages.
    issue_gets = [r for r in fake_github.requested if "/issues?state=open" in r]
    assert len(issue_gets) == 10


def test_shell_grep_finds_one_issue_in_issue_index(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues?state=open&per_page=100",
        github_json(
            [
                {
                    "number": 4211,
                    "title": "Rollout",
                    "state": "open",
                    "body": "Keep upgrades nondisruptive for workers.",
                    "comments": 0,
                    "labels": [],
                    **_OWNER,
                },
                {
                    "number": 4212,
                    "title": "Unrelated",
                    "state": "open",
                    "body": "Clean logs on shutdown.",
                    "comments": 0,
                    "labels": [],
                    **_OWNER,
                },
            ]
        ),
    )

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Plan rollout.")

    index_path = folders.work / "github" / "issue-index.jsonl"
    assert index_path.is_file()
    out = subprocess.run(
        ["git", "grep", "--no-index", "-i", "nondisruptive", "--", "work/github/issue-index.jsonl"],
        cwd=folders.root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert re.findall(r"#\d+", out) == ["#4211"]


# ── The authors that the jobs trust ───────────────────────────────────────────────────────


def test_prepare_writes_only_the_comments_of_an_account_with_write_access(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    _route_issue(fake_github, 12, comments=2)
    _route_comments(
        fake_github,
        12,
        [
            {
                "body": "Keep the API small.",
                "author_association": "COLLABORATOR",
                "user": {"login": "a-colleague"},
            },
            {"body": "A comment of an outside account.", **_STRANGER},
        ],
    )

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Follows #12.")

    assert _issue_file(folders, 12)["comments"] == ["Keep the API small."]


def test_prepare_leaves_out_the_text_of_an_issue_of_an_outside_account(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    _route_issue(
        fake_github,
        12,
        title="The title of an outside account",
        body="The body of an outside account.",
        comments=1,
        labels=[{"name": "type/bug"}],
        **_STRANGER,
    )
    _route_comments(fake_github, 12, [{"body": "Keep the API small.", **_OWNER}])

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Follows #12.")

    assert (
        _issue_file(folders, 12),
        [r for r in fake_github.requested if "/issues/12/comments" in r],
    ) == (
        {
            "number": 12,
            "state": "open",
            "state_reason": None,
            "title": None,
            "labels": ["type/bug"],
            "body": None,
            "comments": [],
            "is_pull_request": False,
            "merged_at": None,
            "closing_pull": None,
            "note": _LEFT_OUT,
        },
        [],
    )


def test_prepare_leaves_an_open_issue_of_an_outside_account_out_of_the_index(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    listed = {"state": "open", "comments": 0, "labels": []}
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues?state=open&per_page=100",
        github_json(
            [
                {"number": 4211, "title": "Rollout", "body": "Keep upgrades calm.", **listed}
                | _OWNER,
                {
                    "number": 4212,
                    "title": "The title of an outside account",
                    "body": "The body of an outside account.",
                    **listed,
                }
                | _STRANGER,
            ]
        ),
    )

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Plan rollout.")

    index = (folders.work / "github" / "issue-index.jsonl").read_text("utf-8")
    assert [json.loads(line) for line in index.splitlines()] == [
        {
            "ref": "#4211",
            "number": 4211,
            "title": "Rollout",
            "labels": [],
            "body": "Keep upgrades calm.",
        }
    ]


def test_prepare_writes_no_patch_of_a_pull_request_of_an_outside_account(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    _route_issue(
        fake_github,
        56,
        state="closed",
        pull_request={"merged_at": None},
        author_association="CONTRIBUTOR",
        user={"login": "a-stranger"},
    )
    _route_pull_files(fake_github, 56, "@@ -1 +1 @@\n-pass\n+other")

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="See PR #56 for context.")

    saved = json.loads((folders.work / "github" / "pull-files" / "56.json").read_text("utf-8"))
    assert saved == {
        "number": 56,
        "files": [
            {
                "filename": "src/app.py",
                "status": "modified",
                "previous_filename": None,
                "additions": 1,
                "changes": 2,
                "patch": None,
            }
        ],
        "note": _PATCH_LEFT_OUT,
    }


def test_prepare_writes_no_title_of_an_open_pull_request_of_an_outside_account(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path, app_login: str
) -> None:
    _route_open_pulls(
        fake_github,
        [
            {
                "number": 101,
                "title": "docs(spec): plan #11 of an outside account",
                "state": "OPEN",
                "files": {"nodes": [{"path": "src/app.py"}]},
                "authorAssociation": "NONE",
                "author": {"__typename": "User", "login": "a-stranger"},
            },
            {
                "number": 102,
                "title": "docs(spec): plan #12",
                "state": "OPEN",
                "files": {"nodes": [{"path": "src/app.py"}]},
                "authorAssociation": "CONTRIBUTOR",
                "author": {"__typename": "Bot", "login": app_login.removesuffix("[bot]")},
            },
        ],
    )

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Update the command.")

    assert json.loads((folders.work / "github" / "pulls.json").read_text("utf-8")) == [
        {
            "number": 101,
            "title": _TITLE_LEFT_OUT,
            "state": "open",
            "plan": True,
            "files": ["src/app.py"],
        },
        {
            "number": 102,
            "title": "docs(spec): plan #12",
            "state": "open",
            "plan": True,
            "files": ["src/app.py"],
        },
    ]


def test_prepare_writes_no_patch_of_a_pull_request_whose_author_it_could_not_read(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    fake_github.route("GET", f"/repos/{STAGE_REPO}/issues/56", httpx2.ConnectError)
    _route_pull_files(fake_github, 56, "@@ -1 +1 @@\n-pass\n+done")

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="See PR #56 for context.")

    saved = json.loads((folders.work / "github" / "pull-files" / "56.json").read_text("utf-8"))
    assert (saved["files"][0]["patch"], saved["note"]) == (None, _PATCH_LEFT_OUT)


@pytest.mark.parametrize(
    ("login", "title", "patch"),
    [
        (_APP, "title of 56", "@@ -1 +1 @@\n-pass\n+done"),
        (CONST_ROADMAP_ACTIONS_BOT_LOGIN, "title of 56", "@@ -1 +1 @@\n-pass\n+done"),
        ("dependabot[bot]", None, None),
    ],
)
def test_prepare_reads_a_pull_request_of_the_two_trusted_bots_and_of_no_other_bot(
    stage_repo: StageRepo,
    fake_github: GitHubApiFake,
    tmp_path: Path,
    app_login: str,
    login: str,
    title: str | None,
    patch: str | None,
) -> None:
    _route_issue(
        fake_github,
        56,
        comments=2,
        pull_request={"merged_at": None},
        author_association="CONTRIBUTOR",
        user={"login": login},
    )
    bot = {"author_association": "CONTRIBUTOR"}
    _route_comments(
        fake_github,
        56,
        [
            {"body": "The plan of the Service.", "user": {"login": app_login}, **bot},
            {
                "body": "A workflow wrote this.",
                "user": {"login": CONST_ROADMAP_ACTIONS_BOT_LOGIN},
                **bot,
            },
        ],
    )
    _route_pull_files(fake_github, 56, "@@ -1 +1 @@\n-pass\n+done")

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="See #56 for context.")

    issue = _issue_file(folders, 56)
    saved = json.loads((folders.work / "github" / "pull-files" / "56.json").read_text("utf-8"))
    assert (issue["title"], issue["comments"], saved["files"][0]["patch"]) == (
        title,
        ["The plan of the Service."] if title else [],
        patch,
    )


def test_prepare_records_failed_github_read_and_continues(
    stage_repo: StageRepo, fake_github: GitHubApiFake, tmp_path: Path
) -> None:
    fake_github.route(
        "GET",
        f"/repos/{STAGE_REPO}/issues/12",
        github_json(
            {
                "number": 12,
                "title": "Open dependency",
                "state": "open",
                "body": "Ready.",
                "comments": 0,
                "labels": [],
            }
        ),
    )
    fake_github.route("GET", f"/repos/{STAGE_REPO}/issues/34", httpx2.ConnectError)

    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Needs #12 and #34.")

    assert (folders.work / "github" / "issues" / "12.json").is_file()
    assert not (folders.work / "github" / "issues" / "34.json").exists()
    errors_text = (folders.work / "github" / "errors.json").read_text("utf-8")
    assert "#34" in errors_text


def test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues(
    stage_repo: StageRepo,
    fake_github: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    folders, _ = _prepare(store, stage_repo, tmp_path, body="Fix the command.")
    for var in ("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    fail_the_github_lookup(monkeypatch)

    stock = ModelScript(say("done"))
    Agent(
        stock.model(),
        capabilities=[
            LocalWorkspace(folders.work / "model"),
            Coder(repo_context=False, sub_agents=False),
        ],
    ).run_sync("go")

    script = ModelScript(say("done"))
    with time_machine.travel(NOW, tick=False):
        run_stage_agent(folders, model=script.model())

    assert script.tools_offered == stock.tools_offered
    offered_names = {name for call in script.tools_offered for name in call}
    assert "read_issue" not in offered_names
    assert "find_issues" not in offered_names
    first_request = script.seen[0][0]
    assert isinstance(first_request, ModelRequest)
    user_text = next(p.content for p in first_request.parts if isinstance(p, UserPromptPart))
    assert str(folders.work / "github") in str(user_text)


def test_phase_all_keeps_live_reads_and_writes_no_snapshot(
    stage_repo: StageRepo,
    fake_github: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    model_fake: ModelFake,
    tmp_path: Path,
) -> None:
    stage_repo.track(
        {
            **gate_files(openspec_fake.version),
            "tests/test_sample.py": "def test_it() -> None: ...\n",
        }
    )
    openspec_fake.script(validate_args(PHASE_CHANGE), 0, VALID_REPORT)
    fake_github.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"number": 9, "html_url": "https://example.com/pull/9"}, status=201),
    )
    fake_github.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls/9/requested_reviewers",
        github_json({"requested_reviewers": []}),
    )
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    # Citing `src/devops_cli/sample.py` causes `--phase all` to run live `open_pulls` via GraphQL.
    number = seed_stageable(store, body="Update `src/devops_cli/sample.py`.")
    proposal = make_stage_proposal()
    group = proposal.groups[0].model_copy(update={"creates": [], "creates_lines": {}})
    model_fake.answer(proposal.model_copy(update={"groups": [group]}))
    work_root = tmp_path / "run"
    work_root.mkdir()
    old_cwd = Path.cwd()
    os.chdir(work_root)
    try:
        run_stage_job(store, repo=STAGE_REPO, item=number, source=stage_repo.clone, now=NOW)
    finally:
        os.chdir(old_cwd)

    assert any(r.endswith("/graphql") for r in fake_github.requested)
    assert not (work_root / "github").exists()
    assert not (work_root / "work" / "github").exists()
