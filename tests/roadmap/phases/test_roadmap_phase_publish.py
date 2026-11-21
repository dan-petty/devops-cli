"""`publish` applies the patch of the agent phase as data and pushes one commit (#6601).

The patch comes from code that the agent controls, so `publish` reads it as data: git applies it to
the index of a fresh clone, and `publish` writes its own commit with the bot as author. It refuses
a new or changed link, gitlink or `.gitmodules`, and a workflow file that the plan does not name,
before it pushes with a lease on the old tip (#3702).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import PublishRefusedError
from devops_cli.roadmap.phases.publish import PublishTarget, publish_patch
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_stage import StageRepo, run_git

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-sample"
BOT = "example-bot[bot]"
BOT_EMAIL = "1+example-bot[bot]@users.noreply.github.com"
WORKFLOW = ".github/workflows/ci.yml"


@pytest.fixture
def real_git(process_fake: ProcessFake) -> ProcessFake:
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    return process_fake


@pytest.fixture
def branch(stage_repo: StageRepo, real_git: ProcessFake) -> str:
    """The head branch of the pull request on `origin`, at the commit that `prepare` judged."""
    stage_repo.git("switch", "-q", "-c", BRANCH)
    stage_repo.git("push", "-q", "origin", BRANCH)
    return stage_repo.git("rev-parse", "HEAD")


def _target(repo: StageRepo, tip: str, *, workflows: tuple[str, ...] = ()) -> PublishTarget:
    return PublishTarget(
        url=str(repo.origin),
        branch=BRANCH,
        base=tip,
        lease=tip,
        author=BOT,
        email=BOT_EMAIL,
        workflow_paths=workflows,
    )


def _patch(repo: StageRepo, tip: str, change: Callable[[Path], None], *, add: bool = True) -> bytes:
    """The patch of `change` in the clone, from `tip`, as the agent phase writes it. With no `add`,
    the change stages what it commits itself."""
    change(repo.clone)
    if add:
        repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "agent work")
    patch = repo.git("diff", "--binary", "--full-index", tip, "HEAD")
    repo.git("reset", "-q", "--hard", tip)
    return (patch + "\n").encode()


def _write(name: str, text: str = "x\n") -> Callable[[Path], None]:
    def change(root: Path) -> None:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")

    return change


def test_publish_pushes_one_commit_of_the_bot_on_the_judged_head(
    stage_repo: StageRepo, branch: str
) -> None:
    patch = _patch(stage_repo, branch, _write("src/fixed.py", "fixed = True\n"))
    checked: list[str] = []

    published = publish_patch(
        _target(stage_repo, branch),
        patch,
        "fix: make check CI pass (#1)",
        before_push=lambda: checked.append("claim"),
    )

    assert published is not None
    tip = stage_repo.origin_git("rev-parse", BRANCH)
    assert (published.commit, published.paths, checked) == (tip, ("src/fixed.py",), ["claim"])
    assert stage_repo.origin_git("log", "-1", "--format=%an <%ae>|%cn|%P", tip) == (
        f"{BOT} <{BOT_EMAIL}>|{BOT}|{branch}"
    )
    assert stage_repo.origin_git("show", f"{tip}:src/fixed.py") == "fixed = True"


def test_an_author_line_in_the_patch_does_not_change_the_author(
    stage_repo: StageRepo, branch: str
) -> None:
    patch = b"From: Mallory <mallory@example.com>\nSubject: [PATCH] x\n\n" + _patch(
        stage_repo, branch, _write("a.txt")
    )

    published = publish_patch(
        _target(stage_repo, branch), patch, "fix: x", before_push=lambda: None
    )

    assert published is not None
    assert stage_repo.origin_git("log", "-1", "--format=%an", published.commit) == BOT


def _link(root: Path) -> None:
    (root / "environ").symlink_to("/proc/self/environ")


def _gitlink(root: Path) -> None:
    sha = run_git(root, "rev-parse", "HEAD")
    run_git(root, "update-index", "--add", "--cacheinfo", f"160000,{sha},vendor/sub")


HOOK = (
    b"diff --git a/.git/hooks/pre-push b/.git/hooks/pre-push\n"
    b"new file mode 100755\n--- /dev/null\n+++ b/.git/hooks/pre-push\n@@ -0,0 +1 @@\n+env\n"
)


@pytest.mark.parametrize(
    ("hostile", "reason"),
    [
        ("link", "is a new or changed link"),
        ("gitlink", "is a new or changed link"),
        ("gitmodules", "changes the submodules"),
        ("git-folder", "git apply refused the patch"),
        ("workflow", "workflow file that the plan does not name"),
    ],
)
def test_publish_refuses_a_hostile_patch_and_pushes_nothing(
    stage_repo: StageRepo, branch: str, hostile: str, reason: str
) -> None:
    """A new link, a new gitlink, a change of `.gitmodules`, a path in `.git` and a workflow file
    that the plan does not name each stop the publish before the push (#3702)."""
    if hostile == "git-folder":
        patch = HOOK
    else:
        change = {
            "link": _link,
            "gitlink": _gitlink,
            "gitmodules": _write(".gitmodules", '[submodule "x"]\n'),
            "workflow": _write(WORKFLOW, "on: push\n"),
        }[hostile]
        patch = _patch(stage_repo, branch, change, add=hostile != "gitlink")

    with pytest.raises(PublishRefusedError, match=reason):
        publish_patch(_target(stage_repo, branch), patch, "fix: x", before_push=lambda: None)

    assert stage_repo.origin_git("rev-parse", BRANCH) == branch


def test_a_workflow_file_that_the_plan_names_is_published(
    stage_repo: StageRepo, branch: str
) -> None:
    patch = _patch(stage_repo, branch, _write(WORKFLOW, "on: push\n"))

    published = publish_patch(
        _target(stage_repo, branch, workflows=(WORKFLOW,)), patch, "ci: x", before_push=lambda: None
    )

    assert published is not None
    assert published.paths == (WORKFLOW,)


def test_a_branch_that_moved_since_the_judgment_gets_no_push(
    stage_repo: StageRepo, branch: str
) -> None:
    """Another writer moved the branch: the lease on the judged head refuses the publish, and the
    commit of the other writer stays."""
    patch = _patch(stage_repo, branch, _write("a.txt"))
    _write("other.txt")(stage_repo.clone)
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "another writer")
    stage_repo.git("push", "-q", "origin", BRANCH)
    moved = stage_repo.git("rev-parse", "HEAD")

    with pytest.raises(GitOperationError, match="push"):
        publish_patch(_target(stage_repo, branch), patch, "fix: x", before_push=lambda: None)

    assert stage_repo.origin_git("rev-parse", BRANCH) == moved


def test_a_claim_check_that_raises_stops_the_push(stage_repo: StageRepo, branch: str) -> None:
    patch = _patch(stage_repo, branch, _write("a.txt"))

    def claimed() -> None:
        raise PublishRefusedError("Item holds an owner label")

    with pytest.raises(PublishRefusedError, match="owner label"):
        publish_patch(_target(stage_repo, branch), patch, "fix: x", before_push=claimed)

    assert stage_repo.origin_git("rev-parse", BRANCH) == branch


def test_an_empty_patch_publishes_nothing(stage_repo: StageRepo, branch: str) -> None:
    assert (
        publish_patch(_target(stage_repo, branch), b"", "fix: x", before_push=lambda: None) is None
    )
    assert stage_repo.origin_git("rev-parse", BRANCH) == branch
