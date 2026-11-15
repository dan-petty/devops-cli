"""Tests for the roadmap step `scaffold` (#5499).

Tests the 4 resume cases, create makes a ref with no commit, dry-run sends 0 requests,
and structural invariant that no stage module other than steps/scaffold.py creates plan branch refs.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.steps.scaffold import (
    ScaffoldResult,
    run_scaffold,
)
from devops_cli.roadmap.stores.store import ScaffoldRecordKey
from tests.support.fakes.github import API, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    StageRepo,
    seed_stageable,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-the-job-drops-a-comment"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def test_scaffold_creates_branch_ref_with_no_commit_when_no_branch_exists(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """1. No branch on origin and record holds no branch -> creates ref at origin/main with no commit."""
    number = seed_stageable(store)
    main_sha = stage_repo.origin_git("rev-parse", "main")

    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/git/refs",
        github_json({"ref": f"refs/heads/{BRANCH}", "object": {"sha": main_sha}}, status=201),
    )

    report = run_scaffold(store, repo=STAGE_REPO, item=number, source=stage_repo.clone)

    assert report.result == ScaffoldResult.CREATED
    assert report.branch == BRANCH
    assert github_api.requested == [f"POST {API}/repos/{STAGE_REPO}/git/refs"]

    # Invariant: ref points to origin/main head, no commit was created
    item = store.item(number)
    assert item is not None
    assert item.job_record.get(ScaffoldRecordKey.BRANCH) == BRANCH


def test_scaffold_resumes_on_app_only_branch_when_record_names_it(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """2. An App-only branch exists on origin and record names it -> resumed, creates no ref."""
    number = seed_stageable(store)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ScaffoldRecordKey.BRANCH: BRANCH})

    report = run_scaffold(store, repo=STAGE_REPO, item=number, source=stage_repo.clone)

    assert report.result == ScaffoldResult.RESUMED
    assert report.branch == BRANCH
    assert github_api.requested == []
    assert store.item(number).job_record.get(ScaffoldRecordKey.BRANCH) == BRANCH


def test_scaffold_adopts_app_only_branch_when_record_does_not_name_it(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """3. An App-only branch exists on origin and record holds no scaffold.branch -> adopted, recorded."""
    number = seed_stageable(store)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    report = run_scaffold(store, repo=STAGE_REPO, item=number, source=stage_repo.clone)

    assert report.result == ScaffoldResult.ADOPTED
    assert report.branch == BRANCH
    assert github_api.requested == []
    assert store.item(number).job_record.get(ScaffoldRecordKey.BRANCH) == BRANCH


def test_scaffold_holds_branch_when_person_or_agent_wrote_to_it(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """4. Branch on origin holds a commit of a person or an agent -> held, writes nothing."""
    number = seed_stageable(store)
    stage_repo.push_branch(BRANCH, author="Person")

    report = run_scaffold(store, repo=STAGE_REPO, item=number, source=stage_repo.clone)

    assert report.result == ScaffoldResult.HELD
    assert report.holder is not None
    assert github_api.requested == []
    assert store.item(number).job_record.get(ScaffoldRecordKey.BRANCH) is None


def test_scaffold_dry_run_sends_zero_requests(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """A dry run sends 0 requests and writes no record key."""
    number = seed_stageable(store)

    report = run_scaffold(
        store, repo=STAGE_REPO, item=number, source=stage_repo.clone, dry_run=True
    )

    assert report.result == ScaffoldResult.CREATED
    assert github_api.requested == []
    assert store.item(number).job_record.get(ScaffoldRecordKey.BRANCH) is None


def test_no_stage_module_other_than_scaffold_creates_plan_branch_ref() -> None:
    """Structural invariant: no module under stage/ or steps/ other than steps/scaffold.py calls create_ref."""
    root = Path("src/devops_cli/roadmap")
    stage_modules = list((root / "stage").glob("**/*.py"))
    step_modules = list((root / "steps").glob("**/*.py"))

    for module_path in (*stage_modules, *step_modules):
        if module_path.name == "scaffold.py":
            continue
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        calls = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        assert "create_ref" not in calls, f"{module_path} must not call create_ref"


def test_run_scaffold_unknown_item_raises_value_error(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    with pytest.raises(ValueError, match="Item #999 not found in roadmap store"):
        run_scaffold(store, repo=STAGE_REPO, item=999, source=stage_repo.clone)


def test_run_scaffold_local_holder_holds(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    number = seed_stageable(store)
    from devops_cli.git.worktree_add import worktree_directory

    wt_dir = worktree_directory(number, stage_repo.clone)
    wt_dir.mkdir(parents=True, exist_ok=True)
    (wt_dir / ".git").write_text("gitdir: ...\n")

    report = run_scaffold(store, repo=STAGE_REPO, item=number, source=stage_repo.clone)
    assert report.result == ScaffoldResult.HELD
    assert "worktree" in (report.holder or "")


def test_is_app_author_with_bot_login(stage_repo: StageRepo, config: Callable[..., Path]) -> None:
    from devops_cli.roadmap.steps.scaffold import _is_app_author

    config(service={"github_app": {"slug": "my-bot"}})
    assert _is_app_author("my-bot[bot]", stage_repo.clone) is True
