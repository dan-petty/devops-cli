"""`devops roadmap stage`: the read of the one draft pull request of a held item (#3387).

The stage job leaves an item out while its branch is on origin. `held_draft` reads the facts of the
one draft pull request of such an item, so that `may_replace` can decide whether the job stages the
item again on that branch: the draft state, the commit of its branch, its authors, its review
threads, the paths that it changes outside the change folder of the item, and the problems that the
plan check finds in its change files.

The GitHub reads are the fake of the API, and the review threads are a fake of the thread read. The
checkout is real git in `tmp_path` (`stage_repo`), as the stage job reads it.

`held_draft` is new, so each test imports it in its own body: a module-level import would stop this
module at collection on the base commit, before any assertion runs, and prove nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.github.pr_threads import ReviewThread
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.stage.stage_change import StageProposal, render_change
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_item, make_stage_proposal
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    pull_request_file_payload,
    route_compare_files,
    route_file,
)
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_held import DraftRead
    from devops_cli.roadmap.stores.store import Item

pytestmark = pytest.mark.usefixtures("keyring_store")

ISSUE = 7
PULL = 12
CHANGE = f"{ISSUE}-the-job-drops-a-comment"
ROOT = f"openspec/changes/{CHANGE}"
BRANCH = f"fix/{CHANGE}"
TITLE = "fix(roadmap): the job drops a comment"
BODY = "The job drops the last comment of a thread."
CREATED = date(2026, 11, 16)
BASE = "b" * 40
MERGE_BASE = "c" * 40

ThreadsRead = Callable[[str, str, int], Sequence[ReviewThread]]


@pytest.fixture(autouse=True)
def _app_slug(config: Callable[..., Path]) -> None:
    """The App whose bot pushes the branch of the stage job, as `stage_repo` names its author."""
    config(service={"github_app": {"slug": "devops-roadmap"}})


def _no_threads(_owner: str, _repo: str, _pull: int) -> list[ReviewThread]:
    """The review thread read of a draft whose threads are all resolved."""
    return []


def _one_thread(_owner: str, _repo: str, _pull: int) -> list[ReviewThread]:
    """The review thread read of a draft with one unresolved thread."""
    return [ReviewThread(id="T1")]


def _passing() -> StageProposal:
    """The plan that the plan check accepts on the clone."""
    return make_stage_proposal()


def _failing() -> StageProposal:
    """The defect of the plan of #5407: the group changes a file that exists, and no code span of
    its tasks names it, so the step of the group packs no file (`group-no-files`)."""
    group = make_stage_proposal().groups[0]
    unnamed = group.model_copy(
        update={
            "test": "Write the test of the last comment",
            "implementation": "Keep the last comment",
        }
    )
    return make_stage_proposal(groups=[unnamed])


def _files(proposal: StageProposal) -> dict[str, str]:
    """The files of the change folder that the stage job writes for `proposal`."""
    return render_change(CHANGE, proposal, {"roadmap-refine"}, created=CREATED)


def _push(
    repo: StageRepo,
    files: Mapping[str, str],
    *,
    author: str = STAGE_NAME,
    extra: Mapping[str, str] | None = None,
) -> str:
    """Push one commit by `author` that holds `files` and `extra` to the branch of the item, and
    return the commit. The clone goes back to `main`, as a stage run finds it."""
    repo.git("switch", "-q", "-c", BRANCH)
    for path, text in {**files, **(extra or {})}.items():
        target = repo.clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("-c", f"user.name={author}", "commit", "-q", "-m", "plan")
    head = repo.git("rev-parse", "HEAD")
    repo.git("push", "-q", "origin", BRANCH)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", BRANCH)
    return head


def _route(
    api: GitHubApiFake,
    *,
    head: str,
    files: Mapping[str, str],
    outside: Sequence[str] = (),
    draft: bool = True,
) -> None:
    """Answer the reads of the draft `PULL` at `head`: its state, the paths that its branch
    changes and the files of its change folder."""
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{PULL}",
        github_json(
            {
                "state": "open",
                "draft": draft,
                "head": {"ref": BRANCH, "sha": head},
                "base": {"ref": "main", "sha": BASE},
            }
        ),
    )
    route_compare_files(
        api,
        STAGE_REPO,
        "main",
        head,
        *[pull_request_file_payload(path) for path in (*files, *outside)],
        merge_base=MERGE_BASE,
    )
    for path, text in files.items():
        route_file(api, STAGE_REPO, path, head, text)


def _staged(head: str, *, sha: str | None = None) -> Item:
    """The item whose record holds the draft `PULL` of the branch at `head`, which `stage.sha`
    records unless `sha` names another commit."""
    return make_item(
        number=ISSUE,
        title=TITLE,
        body=BODY,
        job_record={
            StageRecordKey.PR: str(PULL),
            StageRecordKey.BRANCH: BRANCH,
            StageRecordKey.SHA: head if sha is None else sha,
        },
    )


def _read(item: Item, repo: StageRepo, *, threads: ThreadsRead = _no_threads) -> DraftRead | None:
    """The read of the draft of `item` in the clone, with the client of the session."""
    from devops_cli.roadmap.stage.stage_held import held_draft

    return held_draft(
        item,
        repo=STAGE_REPO,
        source=repo.clone,
        client=get_github_session().client,
        threads=threads,
        default="main",
    )


def test_a_draft_whose_plan_check_finds_a_problem_is_read_as_replaceable(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    files = _files(_failing())
    head = _push(stage_repo, files)
    _route(github_api, head=head, files=files)

    read = _read(_staged(head), stage_repo)

    assert read is not None
    assert may_replace(read)
    assert (read.pull, read.draft, read.at_recorded_commit, read.app_authored) == (
        PULL,
        True,
        True,
        True,
    )
    assert (read.unresolved_threads, read.outside_paths, read.restaged) == (0, (), False)
    assert "group-no-files" in {problem.rule for problem in read.problems}


def test_a_draft_whose_plan_passes_the_check_is_read_as_held(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    files = _files(_passing())
    head = _push(stage_repo, files)
    _route(github_api, head=head, files=files)

    read = _read(_staged(head), stage_repo)

    assert read is not None
    assert (read.problems, read.unresolved_threads, read.outside_paths) == ((), 0, ())
    assert not may_replace(read)


def test_a_draft_with_an_unresolved_review_thread_is_read_as_held(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    files = _files(_failing())
    head = _push(stage_repo, files)
    _route(github_api, head=head, files=files)

    read = _read(_staged(head), stage_repo, threads=_one_thread)

    assert read is not None
    assert (read.unresolved_threads, bool(read.problems)) == (1, True)
    assert not may_replace(read)


def test_a_draft_whose_branch_changes_a_path_outside_the_change_folder_is_read_as_held(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    outside = "src/devops_cli/other.py"
    files = _files(_failing())
    head = _push(stage_repo, files, extra={outside: "OTHER = 1\n"})
    _route(github_api, head=head, files=files, outside=(outside,))

    read = _read(_staged(head), stage_repo)

    assert read is not None
    assert (read.outside_paths, bool(read.problems)) == ((outside,), True)
    assert not may_replace(read)


def test_a_draft_at_another_commit_than_the_recorded_one_is_read_as_held(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    files = _files(_failing())
    head = _push(stage_repo, files)
    _route(github_api, head=head, files=files)

    read = _read(_staged(head, sha="d" * 40), stage_repo)

    assert read is not None
    assert (read.at_recorded_commit, bool(read.problems)) == (False, True)
    assert not may_replace(read)


def test_a_draft_whose_plan_a_person_pushed_is_read_as_held(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    files = _files(_failing())
    head = _push(stage_repo, files, author="Person")
    _route(github_api, head=head, files=files)

    read = _read(_staged(head), stage_repo)

    assert read is not None
    assert (read.app_authored, bool(read.problems)) == (False, True)
    assert not may_replace(read)


def test_a_draft_that_the_job_re_staged_once_is_read_as_restaged(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace, restage_record

    files = _files(_failing())
    head = _push(stage_repo, files)
    _route(github_api, head=head, files=files)
    item = _staged(head)
    recorded = restage_record(item, PULL)
    marked = make_item(
        number=ISSUE,
        title=TITLE,
        body=BODY,
        job_record={**item.job_record, StageRecordKey.RESTAGE: recorded},
    )

    read = _read(marked, stage_repo)

    assert read is not None
    assert (read.restaged, bool(read.problems)) == (True, True)
    assert not may_replace(read)


def test_an_item_with_no_recorded_draft_is_read_as_none(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    item = make_item(number=ISSUE, title=TITLE, body=BODY)

    assert _read(item, stage_repo) is None


def test_a_pull_request_that_is_no_draft_is_read_as_none(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    files = _files(_failing())
    head = _push(stage_repo, files)
    _route(github_api, head=head, files=files, draft=False)

    assert _read(_staged(head), stage_repo) is None


def test_a_draft_whose_branch_origin_lacks_is_read_as_none(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """The draft names a branch that `origin` no longer holds: the job reads no plan of it."""
    files = _files(_failing())
    head = _push(stage_repo, files)
    stage_repo.origin_git("branch", "-q", "-D", BRANCH)
    _route(github_api, head=head, files=files)

    assert _read(_staged(head), stage_repo) is None
