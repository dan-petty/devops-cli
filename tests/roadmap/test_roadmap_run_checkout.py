"""The clone of the repository that the jobs of a round read: how it is made, kept on the default
branch and refused when the repository name escapes (#981).
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
)
from devops_cli.exceptions import (
    GitOperationError,
    RoadmapRunError,
)
from devops_cli.exceptions.git import GitHubUnauthenticatedError
from devops_cli.roadmap.run import (
    JobOutcome,
    build_stub_table,
    ensure_checkout,
    run_due_jobs,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_jobs import due_job_runner
from tests.support.roadmap_run import (
    CURRENT_SIM,
    NOW,
    OPENED,
    POLL_KEY,
    REPO,
    SimulatedGit,
    bare_remote,
    commit_to_bare,
    git_in,
    head_of_clone,
    recorded,
    run_metrics_adapter,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


run_refine_adapter = due_job_runner("refine")


def _advance_bare_remote(bare: Path, branch: str, *, onto: str = "main") -> str:
    return CURRENT_SIM[0].advance_bare_remote(bare, branch, onto=onto)


@pytest.fixture
def main_remote(tmp_path: Path, git_sim: SimulatedGit) -> Path:
    """A bare remote holding only `main`."""
    return git_sim.make_bare_remote(tmp_path)


@pytest.fixture
def dangling_head_remote(tmp_path: Path, git_sim: SimulatedGit) -> Path:
    """A bare remote whose HEAD names `main`, which it lacks: it holds only a topic branch."""
    bare = git_sim.make_bare_remote(tmp_path, other_branch="feat/topic")
    del git_sim.remotes[str(bare)]["branches"]["main"]
    git_sim.remotes[str(bare)]["default_branch"] = None
    return bare


# ── The clone ─────────────────────────────────────────────────────────────────


def test_checkouts_git_management(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """Clones to the expected path, tracks origin's default branch as it moves, sets the
    identity, and fails the clone-dependent jobs, metrics and refine, when origin is gone; intake
    needs no clone and still runs (#1358)."""
    data_dir = tmp_path / "data"
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    expected_clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    user_name = git_in(clone_path, "config", "user.name")
    user_email = git_in(clone_path, "config", "user.email")
    new_rev = _advance_bare_remote(main_remote, "main")
    ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    head = head_of_clone(clone_path)
    shutil.rmtree(main_remote)
    shutil.rmtree(clone_path)

    ran: list[str] = []

    def stub(name: str) -> Callable[..., JobOutcome]:
        return recorded(ran, name)

    fail_table = build_stub_table(
        {name: stub(name) for name in ("metrics", "intake", "refine")}, needs_clone=True
    )
    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=fail_table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            now=NOW,
        )
    assert (
        clone_path == expected_clone,
        user_name,
        user_email,
        head,
        ran,
        exc_info.value.failed_jobs,
    ) == (
        True,
        "test-bot",
        "4242+test-bot@users.noreply.github.com",
        (new_rev, "main"),
        ["intake"],
        ("metrics", "refine"),
    )


def test_checkout_tracks_the_default_branch_whatever_other_branches_origin_holds(
    tmp_path: Path, child_argvs: list[list[str]], caplog: pytest.LogCaptureFixture
) -> None:
    """Another branch on origin is never tracked: the clone follows origin's default branch as
    it moves, and logs nothing about a branch choice."""
    remote = bare_remote(tmp_path, other_branch="feat/1-other")
    data_dir = tmp_path / "data"
    first_tip = git_in(remote, "rev-parse", "main")
    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.run"):
        clone_path = ensure_checkout(REPO, data_dir, remote_url=str(remote))
        first = head_of_clone(clone_path)
        new_tip = _advance_bare_remote(remote, "main")
        ensure_checkout(REPO, data_dir, remote_url=str(remote))
    infos = [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.roadmap.run" and record.levelno == logging.INFO
    ]
    assert (first, head_of_clone(clone_path), infos) == (
        (first_tip, "main"),
        (new_tip, "main"),
        [],
    )


def test_checkout_raises_when_the_fetch_fails_and_keeps_the_branch_it_had(
    tmp_path: Path, main_remote: Path, child_argvs: list[list[str]]
) -> None:
    """An unreachable origin raises GitOperationError with git's reason; the clone keeps the
    commit it had (#1366)."""
    data_dir = tmp_path / "data"
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    before = head_of_clone(clone_path)
    shutil.rmtree(main_remote)

    with pytest.raises(GitOperationError) as raised:
        ensure_checkout(REPO, data_dir, remote_url=str(main_remote))

    message = str(raised.value)
    assert (
        "git fetch --prune origin failed" in message,
        "does not appear to be a git repository" in message,
        head_of_clone(clone_path),
    ) == (True, True, before)


def test_checkout_discards_a_tracked_change_a_failed_job_left_in_the_clone(
    tmp_path: Path, child_argvs: list[list[str]]
) -> None:
    """A job that fails after writing a file leaves a tracked change in the clone. The next
    checkout still moves to origin's tip and drops the change, instead of failing every later
    round until a person cleans the clone (#1366)."""
    bare = bare_remote(tmp_path)
    first = commit_to_bare(bare, "main", "main\n")
    data_dir = tmp_path / "data"
    clone_path = ensure_checkout(REPO, data_dir, remote_url=str(bare))
    (clone_path / "f.txt").write_text("left by a failed job\n")
    tip = commit_to_bare(bare, "main", "next\n", parent=first)

    ensure_checkout(REPO, data_dir, remote_url=str(bare))

    assert (
        head_of_clone(clone_path),
        (clone_path / "f.txt").read_text(),
        git_in(clone_path, "status", "--porcelain"),
    ) == ((tip, "main"), "next\n", "")


def test_checkout_raises_when_origin_head_names_no_branch(
    tmp_path: Path, dangling_head_remote: Path, child_argvs: list[list[str]]
) -> None:
    """A remote whose HEAD names a branch it lacks has no default branch, so the checkout raises
    GitOperationError with git's reason instead of guessing one (#1366)."""
    with pytest.raises(GitOperationError) as raised:
        ensure_checkout(REPO, tmp_path / "data", remote_url=str(dangling_head_remote))

    message = str(raised.value)
    assert (
        "git remote set-head origin --auto failed" in message,
        "Cannot determine remote HEAD" in message,
    ) == (True, True)


def test_clone_and_change_filter_fail_closed_when_login_lookup_fails(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_remote: Path,
    github_api: GitHubApiFake,
) -> None:
    """When `GET /user` fails, the clone rows and the change filter fail closed without fallback.

    `ensure_checkout` fails before configuring `user.name`, so no `devops-cli` identity is
    written. The clone row fails in `run_due_jobs`, and a store with no actor fails the round
    during change filtering rather than filtering with `devops-cli` (#1409).
    """
    github_api.route("GET", "/user", github_json({"message": "Bad credentials"}, status=401))
    data_dir = tmp_path / "data"

    with pytest.raises(GitHubUnauthenticatedError) as raised:
        ensure_checkout(REPO, data_dir, remote_url=str(main_remote))
    assert raised.value.error_code == "GITHUB_UNAUTHENTICATED"

    clone_dir = data_dir / "roadmap" / REPO / CONST_ROADMAP_RUN_CLONE_DIRNAME
    if (clone_dir / ".git").exists():
        assert git_in(clone_dir, "config", "user.name") != "devops-cli"

    table = build_stub_table({"refine": lambda **_: JobOutcome()}, needs_clone=True)
    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            table=table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            batch={OPENED: 1},
        )
    assert "refine" in exc_info.value.failed_jobs

    store_without_actor = seeded_store.as_actor("")
    store_without_actor._actor = None  # type: ignore[assignment]
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        run_due_jobs(
            REPO,
            store_without_actor,
            table=table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            batch={POLL_KEY: 1},
        )
    assert raised.value.error_code == "GITHUB_UNAUTHENTICATED"


def test_a_rounds_clone_jobs_share_one_clone_on_the_default_branch(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    main_remote: Path,
    child_argvs: list[list[str]],
) -> None:
    """Metrics and refine share one clone on `main`, and nothing fails. The dry run of the same
    round starts no git command (#1366)."""
    data_dir = tmp_path / "data"
    main_tip = git_in(main_remote, "rev-parse", "main")
    seen: dict[str, tuple[Path | None, tuple[str, str]]] = {}

    def record(job: str) -> Callable[..., JobOutcome]:
        def run_job(*, clone_path: Path | None = None, **_: Any) -> JobOutcome:
            assert clone_path is not None
            seen[job] = (clone_path, head_of_clone(clone_path))
            return JobOutcome()

        return run_job

    table = build_stub_table(
        {"metrics": record("metrics"), "refine": record("refine")}, needs_clone=True
    )

    def run_round(*, dry_run: bool) -> tuple[str, ...]:
        return run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            remote_url=str(main_remote),
            dry_run=dry_run,
            now=NOW,
        )

    before_dry_run = len(child_argvs)
    planned = run_round(dry_run=True)
    dry_run_git = [argv for argv in child_argvs[before_dry_run:] if argv[0] == "git"]
    ran = run_round(dry_run=False)

    clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    assert (planned, dry_run_git, ran, seen) == (
        ("metrics", "intake", "refine"),
        [],
        ("metrics", "intake", "refine"),
        {"metrics": (clone, (main_tip, "main")), "refine": (clone, (main_tip, "main"))},
    )


def test_ensure_checkout_rejects_path_escape_and_malformed_repo_slugs(tmp_path: Path) -> None:
    """Test that ensure_checkout strictly validates repo slugs and prevents path traversal escapes."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    escapes = [
        "owner//tmp",
        str(tmp_path / "repo"),
        "owner/../etc",
        "owner/name/extra",
        "single_slug",
        "owner/",
        "/name",
    ]
    results: list[bool] = []
    for malformed in escapes:
        with pytest.raises(GitOperationError) as raised:
            ensure_checkout(malformed, data_dir)
        assert raised.value.error_code == "GIT_OPERATION_ERROR"
        results.append(True)

    assert (len(results), all(results)) == (len(escapes), True)


@pytest.mark.parametrize(
    ("job", "runner"), [("metrics", run_metrics_adapter), ("refine", run_refine_adapter)]
)
def test_a_job_that_reads_the_clone_fails_without_one_rather_than_reading_the_cwd(
    seeded_store: InMemoryRoadmapStore, job: str, runner: Callable[..., JobOutcome]
) -> None:
    """A row that runs metrics or refine without `needs_clone` is a table error, not a run
    over the working directory, which in the Service is no git repository (#1358)."""
    with pytest.raises(GitOperationError) as raised:
        runner(store=seeded_store, repo=REPO, clone_path=None)
    assert (f"roadmap {job} job" in str(raised.value), "needs_clone" in str(raised.value)) == (
        True,
        True,
    )
