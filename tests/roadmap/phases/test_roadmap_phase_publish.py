"""`publish` applies the patches of the agent phase as data and pushes commits of the bot (#6601).

The patches come from code that the agent controls, so `publish` reads them as data: git applies
each to a new repository, and `publish` writes its own commit with the bot as author. It refuses a
new or changed link, gitlink or `.gitmodules`, and a workflow file that the plan does not name,
before it pushes with a lease on the old tip (#3702).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import PublishRefusedError
from devops_cli.roadmap.phases.publish import NewTree, PublishTarget, delete_branch, publish_patch
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


def _none(_tree: NewTree) -> None:
    """A claim check that finds no claim."""


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
        [(patch, "fix: make check CI pass (#1)")],
        before_push=lambda _tree: checked.append("claim"),
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

    published = publish_patch(_target(stage_repo, branch), [(patch, "fix: x")], before_push=_none)

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
        publish_patch(_target(stage_repo, branch), [(patch, "fix: x")], before_push=_none)

    assert stage_repo.origin_git("rev-parse", BRANCH) == branch


def _linked_base(stage_repo: StageRepo) -> str:
    """The head branch on `origin` at a commit that holds the link `linked` to `CONTEXT.md` and the
    file `plain.txt`, as the commit that `prepare` judged."""
    (stage_repo.clone / "linked").symlink_to("CONTEXT.md")
    (stage_repo.clone / "plain.txt").write_text("plain\n", encoding="utf-8")
    stage_repo.git("switch", "-q", "-c", BRANCH)
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "a link and a file")
    stage_repo.git("push", "-q", "origin", BRANCH)
    return stage_repo.git("rev-parse", "HEAD")


def _retarget(root: Path) -> None:
    (root / "linked").unlink()
    (root / "linked").symlink_to("/proc/self/environ")


def _file_to_link(root: Path) -> None:
    (root / "plain.txt").unlink()
    (root / "plain.txt").symlink_to("/proc/self/environ")


def _link_to_file(root: Path) -> None:
    (root / "linked").unlink()
    (root / "linked").write_text("now a file\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (_retarget, "is a new or changed link"),
        (_file_to_link, "is a new or changed link"),
        (_link_to_file, "changes a link or gitlink"),
    ],
    ids=["retarget", "file-to-link", "link-to-file"],
)
def test_publish_refuses_a_changed_link_and_pushes_nothing(
    stage_repo: StageRepo,
    real_git: ProcessFake,
    change: Callable[[Path], None],
    reason: str,
) -> None:
    """A change of mode 120000 on the base, as the agent phase can write it, stops the publish
    before the push. The agent phase formats a link like any file, so this refusal is the one
    stop of a link (#6691)."""
    base = _linked_base(stage_repo)
    patch = _patch(stage_repo, base, change)

    with pytest.raises(PublishRefusedError, match=reason):
        publish_patch(_target(stage_repo, base), [(patch, "fix: x")], before_push=_none)

    assert stage_repo.origin_git("rev-parse", BRANCH) == base


def test_a_workflow_file_that_the_plan_names_is_published(
    stage_repo: StageRepo, branch: str
) -> None:
    patch = _patch(stage_repo, branch, _write(WORKFLOW, "on: push\n"))

    published = publish_patch(
        _target(stage_repo, branch, workflows=(WORKFLOW,)), [(patch, "ci: x")], before_push=_none
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
        publish_patch(_target(stage_repo, branch), [(patch, "fix: x")], before_push=_none)

    assert stage_repo.origin_git("rev-parse", BRANCH) == moved


def test_a_claim_check_that_raises_stops_the_push(stage_repo: StageRepo, branch: str) -> None:
    patch = _patch(stage_repo, branch, _write("a.txt"))

    def claimed(_tree: NewTree) -> None:
        raise PublishRefusedError("Item holds an owner label")

    with pytest.raises(PublishRefusedError, match="owner label"):
        publish_patch(_target(stage_repo, branch), [(patch, "fix: x")], before_push=claimed)

    assert stage_repo.origin_git("rev-parse", BRANCH) == branch


def test_an_empty_patch_publishes_nothing(stage_repo: StageRepo, branch: str) -> None:
    assert publish_patch(_target(stage_repo, branch), [(b"", "fix: x")], before_push=_none) is None
    assert stage_repo.origin_git("rev-parse", BRANCH) == branch


def _main_moves(repo: StageRepo) -> str:
    """`main` of `origin` gains a commit, as a merge does on GitHub: the new base."""
    repo.git("switch", "-q", "main")
    _write("main.txt")(repo.clone)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "main moves")
    repo.git("push", "-q", "origin", "main")
    return repo.git("rev-parse", "HEAD")


def test_publish_writes_a_commit_for_each_patch_on_a_base_other_than_the_old_tip(
    stage_repo: StageRepo, branch: str
) -> None:
    """The implement Job rebases onto the main commit that `prepare` recorded, and keeps the
    archive as its own commit (#3702): `publish` fetches that base, writes one commit of the bot for
    each patch on it, and the lease on the old tip lets the push replace that tip."""
    base = _main_moves(stage_repo)
    work = _patch(stage_repo, base, _write("src/fixed.py", "fixed = True\n"))
    archive = _patch(stage_repo, base, _write("openspec/archive.md", "archived\n"))
    target = _target(stage_repo, branch).model_copy(update={"base": base})

    published = publish_patch(
        target,
        [(work, "fix(roadmap): the work (#1)"), (b"", "empty"), (archive, "docs: archive (#1)")],
        before_push=_none,
    )

    assert published is not None
    log = stage_repo.origin_git("log", "--reverse", "--format=%s|%an", f"{base}..{BRANCH}")
    assert log.splitlines() == [f"fix(roadmap): the work (#1)|{BOT}", f"docs: archive (#1)|{BOT}"]
    assert published.paths == ("src/fixed.py", "openspec/archive.md")


@pytest.mark.parametrize("exists", [False, True], ids=["new", "taken"])
def test_publish_makes_a_new_branch_only_where_none_is(
    stage_repo: StageRepo, real_git: ProcessFake, exists: bool
) -> None:
    """A Planned item has no branch yet: an empty lease makes `publish` push a new branch, and
    refuse when the branch exists, so it overwrites no push of another writer (#3702)."""
    base = stage_repo.git("rev-parse", "HEAD")
    if exists:
        stage_repo.git("push", "-q", "origin", f"{base}:refs/heads/{BRANCH}")
    patch = _patch(stage_repo, base, _write("a.txt"))
    target = PublishTarget(
        url=str(stage_repo.origin), branch=BRANCH, base=base, lease="", author=BOT, email=BOT_EMAIL
    )

    if exists:
        with pytest.raises(GitOperationError, match="push"):
            publish_patch(target, [(patch, "feat: x (#1)")], before_push=_none)
        assert stage_repo.origin_git("rev-parse", BRANCH) == base
    else:
        published = publish_patch(target, [(patch, "feat: x (#1)")], before_push=_none)
        assert published is not None
        assert stage_repo.origin_git("rev-parse", BRANCH) == published.commit


def test_the_claim_check_reads_the_new_tree_from_its_objects(
    stage_repo: StageRepo, branch: str
) -> None:
    """The implement Job reads the change of the new tree before the push: the names in a folder
    and the text of a file come from the git objects, and a file that the tree does not hold has
    no text (#3702)."""
    patch = _patch(stage_repo, branch, _write("docs/a/proposal.md", "## Why\n\nA reason.\n"))
    seen: list[object] = []

    def read(tree: NewTree) -> None:
        seen.extend([tree.changed, tree.names("docs"), tree.text("docs/a/proposal.md")])
        seen.append(tree.text("docs/b/proposal.md"))

    published = publish_patch(
        _target(stage_repo, branch), [(patch, "feat: x (#1)")], before_push=read
    )

    assert published is not None
    assert seen == [("docs/a/proposal.md",), ("a",), "## Why\n\nA reason.\n", None]


def test_a_second_publish_of_the_same_tree_pushes_nothing(
    stage_repo: StageRepo, branch: str
) -> None:
    """A run whose tree the branch holds already gets the commit on the branch back and makes no
    push, so a second run pushes nothing (#3702)."""
    patch = _patch(stage_repo, branch, _write("a.txt"))
    first = publish_patch(_target(stage_repo, branch), [(patch, "feat: x (#1)")], before_push=_none)
    assert first is not None
    target = _target(stage_repo, branch).model_copy(update={"lease": first.commit})

    again = publish_patch(target, [(patch, "feat: x (#1)")], before_push=_none)

    assert again == first
    assert stage_repo.origin_git("rev-parse", BRANCH) == first.commit


def test_a_branch_that_publish_made_is_deleted_with_a_lease(
    stage_repo: StageRepo, branch: str
) -> None:
    """GitHub refused the draft of a new branch: `publish` deletes the branch that it pushed, and
    only while the branch is at that commit (#3702)."""
    delete_branch(_target(stage_repo, branch))

    assert stage_repo.origin_git("branch", "--list", BRANCH) == ""


def test_each_git_call_of_publish_has_its_new_folder_as_home(
    stage_repo: StageRepo, branch: str, real_git: ProcessFake
) -> None:
    """In `--phase all` the agent can write the home folder, and git still reads files there with
    no configuration file, as `.config/git/attributes` and `.netrc`. Each git call of `publish` gets
    the new empty folder of the publish as its home (#6655)."""
    patch = _patch(stage_repo, branch, _write("a.txt"))
    before = len(real_git.calls)

    publish_patch(_target(stage_repo, branch), [(patch, "fix: x")], before_push=_none)

    calls = [call for call in real_git.calls[before:] if call.argv[0] == "git"]
    homes = {(call.env or {}).get("HOME") for call in calls}
    assert len(homes) == 1
    (home,) = homes
    assert home is not None
    assert Path(home).name.startswith("devops-publish-")
    assert {(call.env or {}).get("XDG_CONFIG_HOME") for call in calls} == {home}
