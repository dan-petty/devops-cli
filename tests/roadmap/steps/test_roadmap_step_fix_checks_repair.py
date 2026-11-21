"""The repair of the step `fix-checks` in a runner Job (#5971): the checkout of the head branch,
tier 1 (the fixers of a lint failure, their commit, and their checks again), the model fix, and
the push.

Git runs for real on a clone with an `origin`. GitHub's REST API and `gh` are faked at their edges,
the model is scripted, and the fixers of tier 1 and their checks are answered at the process edge:
a ruff fix rewrites the file it names.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from devops_cli.ai.client import factory
from devops_cli.exceptions import GitOperationError, RoadmapImplementError
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.steps.fix_checks import Fixed, run_fix_checks
from devops_cli.roadmap.steps.fix_checks_repair import job_repair, pull_checkout, tier1_fix
from devops_cli.roadmap.stores.store import FixChecksRecordKey, FixChecksResult, ImplementRecordKey
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import command_text, git_for_real
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHECK_LINK,
    FAIL,
    PULL,
    STALE_LOCK_COMMANDS,
    STEPS_DECLARATION,
    STEPS_FILE,
    TASKS,
    a_fix,
    push_staged_branch,
    seed_staged,
    stale_lock_effect,
)
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

SAMPLE = "src/devops_cli/sample.py"
LINT_LOG = f"{SAMPLE}:1:8: F401 [*] `os` imported but unused\nFound 1 error.\n"
TYPE_LOG = f'{SAMPLE}:2: error: Incompatible types in assignment (got "str")  [assignment]\n'
STATIC = "Static Analysis"
# What `uv sync --locked` (uv 0.13) says when `uv.lock` does not match `pyproject.toml`.
LOCK_LOG = (
    "error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.\n\n"
    "hint: To update the lockfile, run `uv lock`.\n"
)
DOCS = "docs/commands/roadmap.md"
# A `devops ci --check` log: mypy passes, and `devops docs check` finds a document out of date.
DOCS_LOG = (
    "✓ mypy type check\n"
    f"✗ Documentation is out of date: {DOCS} has uncommitted changes or differs.\n"
    "Documentation check failed. Run 'devops docs generate' to refresh documentation.\n"
)


@pytest.fixture
def branch(stage_repo: StageRepo, process_fake: ProcessFake) -> StageRepo:
    """The clone on the branch of item 1, with one commit that adds an unused import."""
    stage_repo.track({STEPS_FILE: STEPS_DECLARATION})
    stage_repo.git("switch", "-q", "-c", "fix/1-sample")
    (stage_repo.clone / SAMPLE).write_text("import os\nVALUE = 1\n", encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "fix(roadmap): add the value")
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    process_fake.answer(lambda call: command_text(call).startswith("uv "), ProcessAnswer())
    return stage_repo


def _ruff_fix(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `ruff check --fix` does to the file: it drops the unused import."""
    assert call.cwd is not None
    (call.cwd / SAMPLE).write_text("VALUE = 1\n", encoding="utf-8")
    return subprocess.CompletedProcess(call.argv, 0, stdout="Found 1 error (1 fixed).")


def _uv_commands(fake: ProcessFake) -> list[str]:
    return [command_text(call) for call in fake.calls if call.argv[0] == "uv"]


def _fixes(fake: ProcessFake) -> None:
    fake.answer(
        lambda call: command_text(call).startswith("uv run ruff check --fix"),
        ProcessAnswer(side_effect=_ruff_fix),
    )


def test_tier1_commits_the_fixes_of_a_lint_failure_and_is_done_when_the_checks_pass(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    _fixes(process_fake)

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is True
    assert branch.git("log", "-1", "--format=%s") == (
        "style: apply the fixers of tier 1 for check Static Analysis (#1)"
    )
    assert branch.git("status", "--porcelain") == ""
    assert _uv_commands(process_fake) == [
        f"uv run ruff check --fix -- {SAMPLE}",
        f"uv run ruff format -- {SAMPLE}",
        "uv run devops docs generate",
        f"uv run ruff check -- {SAMPLE}",
        f"uv run ruff format --check -- {SAMPLE}",
        "uv run devops ci docs",
    ]


def test_a_tier1_commit_whose_check_still_fails_stays_for_the_model_fix(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    _fixes(process_fake)
    process_fake.answer(
        lambda call: command_text(call) == f"uv run ruff check -- {SAMPLE}",
        ProcessAnswer(returncode=1, stdout="E501 Line too long"),
    )

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is False
    assert "ruff check" in fixed.reason
    assert branch.git("log", "-1", "--format=%s").startswith("style: apply the fixers of tier 1")


def _commit(repo: StageRepo, name: str, text: str) -> None:
    (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
    (repo.clone / name).write_text(text, encoding="utf-8")
    repo.git("add", name)
    repo.git("commit", "-q", "-m", f"add {name}")


def _writes(name: str, text: str) -> ProcessAnswer:
    """The answer of a fixer that writes `text` to the tracked file `name` of its checkout."""

    def write(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        (call.cwd / name).write_text(text, encoding="utf-8")
        return subprocess.CompletedProcess(call.argv, 0, stdout="")

    return ProcessAnswer(side_effect=write)


def test_tier1_updates_the_lockfile_for_a_lockfile_failure_in_a_test_check(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    """The case of #5983: `uv sync --locked` fails in the check `Tests`, whose class is test. The
    lockfile failure has its own fixer, and the round needs no model."""
    _commit(branch, "uv.lock", "version = 1\n")
    process_fake.answer(
        lambda call: command_text(call) == "uv lock", _writes("uv.lock", "version = 2\n")
    )

    fixed = tier1_fix(branch.clone, 1, "Tests & Coverage (shard 1 of 4)", LOCK_LOG)

    assert fixed.done is True
    assert _uv_commands(process_fake) == ["uv lock", "uv lock --check"]
    assert branch.git("show", "--name-only", "--format=", "HEAD") == "uv.lock"


def test_tier1_generates_the_documents_for_a_docs_failure_in_any_check(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    """The log of `Static Analysis` names mypy, so its class is types; the docs failure in it still
    gets `devops docs generate` and not ruff (#5983)."""
    _commit(branch, DOCS, "old\n")
    process_fake.answer(
        lambda call: command_text(call) == "uv run devops docs generate", _writes(DOCS, "new\n")
    )

    fixed = tier1_fix(branch.clone, 1, STATIC, DOCS_LOG)

    assert fixed.done is True
    assert _uv_commands(process_fake) == ["uv run devops docs generate", "uv run devops ci docs"]
    assert branch.git("show", "--name-only", "--format=", "HEAD") == DOCS


SNAPSHOT_TEST = "tests/ai/mcp/test_mcp_tool_listing.py"
SNAPSHOT = "tests/ai/mcp/__snapshots__/test_mcp_tool_listing/listing.json"
MCP_DOCS = "docs/MCP_TOOLS.md"
# The log of shard 3 of the tests of #6041: the snapshot of the tool listing differs.
SNAPSHOT_LOG = (
    "1 snapshot failed. 7 snapshots passed.\n"
    f"FAILED {SNAPSHOT_TEST}::test_the_tool_listing_matches_the_snapshot - "
    "assert [+ received] == [- snapshot]\n"
)


def test_tier1_writes_the_snapshot_and_the_documents_again_for_a_snapshot_failure(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    """The case of #6041: a changed tool changes the snapshot of the tool listing and its
    document. Tier 1 writes both again with the project commands, and runs the test and the docs
    check again, with no model request (#6116)."""
    _commit(branch, SNAPSHOT, "{}\n")
    _commit(branch, MCP_DOCS, "old\n")
    update = f"uv run pytest -n 0 --snapshot-update {SNAPSHOT_TEST}"
    process_fake.answer(
        lambda call: command_text(call) == update, _writes(SNAPSHOT, '{"repo": {}}\n')
    )
    process_fake.answer(
        lambda call: command_text(call) == "uv run devops docs generate", _writes(MCP_DOCS, "new\n")
    )

    fixed = tier1_fix(branch.clone, 1, "Tests & Coverage (shard 3 of 4)", SNAPSHOT_LOG)

    assert fixed == Fixed(done=True, files=(MCP_DOCS, SNAPSHOT))
    assert _uv_commands(process_fake) == [
        update,
        "uv run devops docs generate",
        f"uv run devops ci test {SNAPSHOT_TEST}",
        "uv run devops ci docs",
    ]


def test_tier1_runs_no_fixer_for_a_failure_that_is_not_lint(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    head = branch.git("rev-parse", "HEAD")

    fixed = tier1_fix(branch.clone, 1, STATIC, TYPE_LOG)

    assert fixed.done is False
    assert (_uv_commands(process_fake), branch.git("rev-parse", "HEAD")) == ([], head)


def test_tier1_makes_no_commit_when_the_fixers_change_no_file(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    head = branch.git("rev-parse", "HEAD")

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is False
    assert "changed no file" in fixed.reason
    assert branch.git("rev-parse", "HEAD") == head


# ── The round end to end ─────────────────────────────────────────────────────────────────

# A type error in a file that the plan changes (`src/devops_cli/shout.py`): tier 1 has no fixer for
# it, so the model fix runs.
TYPE_ERROR = (
    "src/devops_cli/shout.py:5: error: Incompatible return value type "
    '(got "int", expected "str")  [return-value]\n'
)


SHOUT_FILES = {"src/devops_cli/shout.py": "def shout(text):\n"}


def _failed_draft(
    stage_repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    files: dict[str, str],
) -> tuple[StageRepo, InMemoryRoadmapStore, str]:
    """Pull request 5 of item 1: a bot draft on the staged branch with `files`, whose
    `Static Analysis` check failed on its head with a log that names a file of the plan. The store
    holds the item."""
    push_staged_branch(stage_repo, files=files)
    head = stage_repo.origin_git("rev-parse", BRANCH)
    api, programs = github_api_and_gh
    programs.answer("git", ProcessAnswer(side_effect=git_for_real))
    programs.answer(lambda call: command_text(call).startswith("uv "), ProcessAnswer())
    programs.answer(
        lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=TYPE_ERROR)
    )
    status = {
        "state": "open",
        "draft": True,
        "head": {"ref": BRANCH, "sha": head},
        "base": {"ref": "main"},
        "user": {"login": STAGE_NAME},
        "labels": [],
    }
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(status))
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{head}/check-runs?per_page=100",
        github_json(
            {
                "total_count": 1,
                "check_runs": [{**FAIL, "name": "Static Analysis", "html_url": CHECK_LINK}],
            }
        ),
    )
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_staged(store)
    held = store.item(number)
    assert held is not None
    store.set_marks(held, {ImplementRecordKey.PR: str(PULL)})
    return stage_repo, store, head


@pytest.fixture
def failed_draft(
    stage_repo: StageRepo,
    app_slug: None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> tuple[StageRepo, InMemoryRoadmapStore, str]:
    """The draft of `_failed_draft`, whose branch adds the code that the log names."""
    return _failed_draft(stage_repo, github_api_and_gh, SHOUT_FILES)


@pytest.fixture
def locked_draft(
    stage_repo: StageRepo,
    app_slug: None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> tuple[StageRepo, InMemoryRoadmapStore, str]:
    """The draft of `failed_draft`, whose branch also holds `uv.lock` (#6517)."""
    return _failed_draft(stage_repo, github_api_and_gh, {**SHOUT_FILES, "uv.lock": "version = 1\n"})


def test_a_failed_check_whose_log_names_a_file_of_the_plan_is_repaired_and_pushed(
    failed_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
) -> None:
    """The case of #5971: the round takes over the head branch, runs the model fix of the task
    `fix_checks`, and pushes one commit to the head branch with a lease on the judged head."""
    repo, store, head = failed_draft
    script = ModelScript(*a_fix())
    factory.set_llm_client_override(script.model())

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    new_head = repo.origin_git("rev-parse", BRANCH)
    assert (report.result, report.head, report.reason) == (
        FixChecksResult.REPAIRED,
        new_head,
        "Tier 2 model repaired check",
    )
    assert repo.origin_git("rev-parse", f"{new_head}~1") == head
    assert len(script.seen) == 2
    held = store.item(1)
    assert held is not None
    assert held.job_record.get(FixChecksRecordKey.RESULT) == "repaired"
    assert repo.git("worktree", "list").count("\n") == 0


def test_a_round_whose_model_fix_stops_pushes_nothing(
    failed_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
) -> None:
    repo, store, head = failed_draft
    factory.set_llm_client_override(ModelScript(say("I see no fix.")).model())

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    assert report.result == FixChecksResult.FAILED
    assert report.reason.startswith("Model repair failed")
    assert repo.origin_git("rev-parse", BRANCH) == head
    assert repo.git("worktree", "list").count("\n") == 0


def test_a_push_whose_lease_breaks_is_refused_and_keeps_the_other_writer(
    failed_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
) -> None:
    """Another writer moves the head branch on `origin` after the judgment and before the push.
    The lease on the judged head refuses the push: the commit of the other writer stays, the round
    records no repair, and the worktree goes (#5983)."""
    repo, store, head = failed_draft
    factory.set_llm_client_override(ModelScript(*a_fix()).model())
    real = job_repair(store, STAGE_REPO, source=repo.clone)
    moved: list[str] = []

    def model_then_another_writer(
        path: Path, item: int, check: str, log: str, extra: tuple[str, ...]
    ) -> Fixed:
        fixed = real.model(path, item, check, log, extra)
        tree = repo.git("rev-parse", f"{head}^{{tree}}")
        moved.append(repo.git("commit-tree", tree, "-p", head, "-m", "work of another writer"))
        repo.git("push", "-q", "origin", f"{moved[0]}:refs/heads/{BRANCH}")
        return fixed

    with pytest.raises(GitOperationError, match="push"):
        run_fix_checks(
            store,
            STAGE_REPO,
            PULL,
            confirm=True,
            repair=replace(real, model=model_then_another_writer),
        )

    assert repo.origin_git("rev-parse", BRANCH) == moved[0]
    held = store.item(1)
    assert held is not None
    assert held.job_record.get(FixChecksRecordKey.RESULT) is None
    assert repo.git("worktree", "list").count("\n") == 0


# The case of #6114 in a test world: the plan changes the signature of `run_flow`, and a test that
# the plan does not list calls it without the new argument.
FLOW = "src/devops_cli/flow.py"
FLOW_TEST = "tests/test_flow.py"
FLOW_BASE = "def run_flow(pages: list[str], *, checkout: str) -> list[str]:\n    return pages\n"
FLOW_HEAD = (
    "def run_flow(pages: list[str], *, checkout: str, in_runner: bool) -> list[str]:\n"
    "    return pages if in_runner else []\n"
)
FLOW_CALLER = (
    "from devops_cli.flow import run_flow\n\n\n"
    "def test_flow() -> None:\n"
    '    assert run_flow(["p"], checkout=".") == ["p"]\n'
)
FLOW_TASKS = TASKS.replace(
    "`src/devops_cli/shout.py` (new), `tests/test_shout.py` (new)", f"`{FLOW}`"
).replace("Add `src/devops_cli/shout.py`", f"Add a keyword argument to `{FLOW}`")
FLOW_CHECK = "Tests & Coverage (shard 4 of 4)"
FLOW_LOG = (
    f"FAILED {FLOW_TEST}::test_flow - "
    "TypeError: run_flow() missing 1 required keyword-only argument: 'in_runner'\n"
)


@pytest.fixture
def caller_draft(
    stage_repo: StageRepo,
    app_slug: None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> tuple[StageRepo, InMemoryRoadmapStore, GitHubApiFake, str]:
    """Pull request 5 of item 1: a bot draft whose plan changes `run_flow`, and whose test shard
    failed in a caller that the plan does not list."""
    stage_repo.track({FLOW: FLOW_BASE, FLOW_TEST: FLOW_CALLER})
    push_staged_branch(stage_repo, tasks=FLOW_TASKS, files={FLOW: FLOW_HEAD})
    head = stage_repo.origin_git("rev-parse", BRANCH)
    api, programs = github_api_and_gh
    programs.answer("git", ProcessAnswer(side_effect=git_for_real))
    programs.answer(lambda call: command_text(call).startswith("uv "), ProcessAnswer())
    programs.answer(lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=FLOW_LOG))
    status = {
        "state": "open",
        "draft": True,
        "head": {"ref": BRANCH, "sha": head},
        "base": {"ref": "main"},
        "user": {"login": STAGE_NAME},
        "labels": [],
    }
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(status))
    failed = {**FAIL, "name": FLOW_CHECK, "html_url": CHECK_LINK}
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{head}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [failed]}),
    )
    api.route(
        "POST", f"/repos/{STAGE_REPO}/issues/{PULL}/comments", github_json({"id": 1}, status=201)
    )
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_staged(store)
    held = store.item(number)
    assert held is not None
    store.set_marks(held, {ImplementRecordKey.PR: str(PULL)})
    return stage_repo, store, api, head


def _comments(api: GitHubApiFake) -> list[str]:
    return [
        json.loads(request.content)["body"]
        for request in api.sent
        if request.method == "POST" and request.url.path.endswith("/comments")
    ]


def test_a_failure_in_a_caller_that_the_plan_does_not_list_is_repaired_and_named(
    caller_draft: tuple[StageRepo, InMemoryRoadmapStore, GitHubApiFake, str],
) -> None:
    """The case of #6114: the scope check finds that the failed test calls `run_flow`, whose
    signature the plan changes. The model is told that it may change the test, the step keeps the
    change and pushes it, and the comment names the file (#6116)."""
    repo, store, api, head = caller_draft
    fixed = FLOW_CALLER.replace('checkout=".")', 'checkout=".", in_runner=True)')
    script = ModelScript(
        tool_calls(("write_file", {"path": FLOW_TEST, "content": fixed})), say("Fixed the call.")
    )
    factory.set_llm_client_override(script.model())

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    new_head = repo.origin_git("rev-parse", BRANCH)
    assert (report.result, report.head) == (FixChecksResult.REPAIRED, new_head)
    assert repo.origin_git("diff", "--name-only", head, new_head) == FLOW_TEST
    asked = [str(getattr(part, "content", "")) for part in script.seen[0][-1].parts]
    assert any(f"`{FLOW_TEST}`" in text for text in asked)
    [comment] = _comments(api)
    assert f"`{FLOW_TEST}`: it uses the changed name `run_flow`" in comment


def test_a_failure_in_a_file_that_main_changed_after_the_branch_point_stops_as_main_skew(
    caller_draft: tuple[StageRepo, InMemoryRoadmapStore, GitHubApiFake, str],
) -> None:
    """Main changed the failed test after the branch point: the change of the branch does not
    cause the failure, so the round stops with no model request and says why (#6116)."""
    repo, store, api, head = caller_draft
    repo.track({FLOW_TEST: FLOW_CALLER + "\n\ndef test_more() -> None:\n    assert True\n"})
    script = ModelScript(say("No fix."))
    factory.set_llm_client_override(script.model())

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    assert report.result == FixChecksResult.STOPPED
    assert report.reason.startswith("Failed check log is outside plan scope: ")
    assert f"`{FLOW_TEST}`" in report.reason
    assert "main skew" in report.reason
    assert (script.seen, _comments(api)) == ([], [])
    assert repo.origin_git("rev-parse", BRANCH) == head


@pytest.fixture
def staged(
    stage_repo: StageRepo, app_slug: None, process_fake: ProcessFake
) -> tuple[StageRepo, str]:
    """The branch of item 1 on `origin`, with one commit of the App, and its head."""
    push_staged_branch(stage_repo)
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    return stage_repo, stage_repo.origin_git("rev-parse", BRANCH)


@pytest.mark.parametrize(
    ("ref", "sha", "error"),
    [
        ("fix/1-another-branch", "", "not the head branch"),
        (BRANCH, "0" * 40, "not at the judged head"),
    ],
    ids=["branch", "sha"],
)
def test_the_checkout_refuses_another_branch_or_head_and_removes_its_worktree(
    staged: tuple[StageRepo, str], ref: str, sha: str, error: str
) -> None:
    """The checkout opens only on the head branch of the pull request at the judged head, and its
    worktree and local branch go when it refuses (#5983)."""
    repo, head = staged
    status = PullStatus(state="open", head_ref=ref, head_sha=sha or head)

    with (
        pytest.raises(RoadmapImplementError, match=error),
        pull_checkout(STAGE_REPO, status, 1, source=repo.clone),
    ):
        pytest.fail("The checkout opened.")

    assert repo.git("worktree", "list").count("\n") == 0
    assert repo.git("branch", "--list", BRANCH) == ""


def test_a_stale_lock_opens_the_checkout_and_tier1_locks_it_again(
    stage_repo: StageRepo, app_slug: None, process_fake: ProcessFake
) -> None:
    """A check that failed because `uv.lock` is stale is a case of tier 1, and `uv sync --locked`
    fails on it. The checkout builds no venv, so it opens, and tier 1 locks again with no model
    (#6517)."""
    push_staged_branch(stage_repo, files={"uv.lock": "version = 1\n"})
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    process_fake.answer(
        lambda call: command_text(call).startswith("uv sync"),
        ProcessAnswer(returncode=1, stderr=LOCK_LOG),
    )
    process_fake.answer(
        lambda call: command_text(call) == "uv lock", _writes("uv.lock", "version = 2\n")
    )
    head = stage_repo.origin_git("rev-parse", BRANCH)
    status = PullStatus(state="open", head_ref=BRANCH, head_sha=head)

    with pull_checkout(STAGE_REPO, status, 1, source=stage_repo.clone) as checkout:
        fixed = tier1_fix(checkout.path, 1, "Tests & Coverage (shard 1 of 4)", LOCK_LOG)

    assert (fixed.done, _uv_commands(process_fake)) == (True, ["uv lock", "uv lock --check"])


def test_the_model_fix_bootstraps_the_worktree_before_the_first_model_request(
    locked_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    """The model step runs the dev tools of the venv of the worktree, so the fix builds that venv
    first (#6517). The branch exists, so the sync installs its `uv.lock` as it is and writes no
    tracked file (#6557)."""
    repo, store, _head = locked_draft
    _api, programs = github_api_and_gh
    script = ModelScript(*a_fix())
    factory.set_llm_client_override(script.model())
    synced: list[tuple[Path | None, int]] = []

    def sync(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        synced.append((call.cwd, len(script.seen)))
        return subprocess.CompletedProcess(call.argv, 0, stdout="", stderr="")

    programs.answer(
        lambda call: command_text(call).startswith("uv sync"), ProcessAnswer(side_effect=sync)
    )

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    syncs = [command_text(c) for c in programs.calls if command_text(c).startswith("uv sync")]
    assert (report.result, syncs, [requests for _cwd, requests in synced]) == (
        FixChecksResult.REPAIRED,
        ["uv sync --frozen --group dev"],
        [0],
    )
    assert synced[0][0] not in (None, repo.clone)


def test_a_stale_lock_of_the_head_branch_reaches_the_first_model_request(
    stage_repo: StageRepo,
    app_slug: None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    """The head branch can hold a `uv.lock` and a `package-lock.json` that do not match their
    manifests. The bootstrap writes no lock, and the install of the hook environments locks
    nothing (`uv run --frozen`). So the step finds a clean worktree, and the model fix repairs
    the check (#6557)."""
    _commit(stage_repo, ".pre-commit-config.yaml", "repos: []\n")
    stage_repo.git("push", "-q", "origin", "main")
    locks = {"uv.lock": "version = 1\n", "package-lock.json": "{}\n"}
    repo, store, _head = _failed_draft(stage_repo, github_api_and_gh, {**SHOUT_FILES, **locks})
    _api, programs = github_api_and_gh
    script = ModelScript(*a_fix())
    factory.set_llm_client_override(script.model())
    programs.answer(
        lambda call: command_text(call).startswith(STALE_LOCK_COMMANDS),
        ProcessAnswer(side_effect=stale_lock_effect),
    )

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    installs = [text for call in programs.calls if "install-hooks" in (text := command_text(call))]
    assert (report.result, len(installs), bool(script.seen)) == (
        FixChecksResult.REPAIRED,
        1,
        True,
    )


def test_a_failed_bootstrap_fails_the_model_fix_with_its_output(
    locked_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    repo, store, _head = locked_draft
    _api, programs = github_api_and_gh
    script = ModelScript(*a_fix())
    factory.set_llm_client_override(script.model())
    programs.answer(
        lambda call: command_text(call).startswith("uv sync"),
        ProcessAnswer(returncode=2, stderr="error: Failed to fetch example.com\n"),
    )

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    assert (report.result, script.seen) == (FixChecksResult.FAILED, [])
    assert "error: Failed to fetch example.com" in report.reason
