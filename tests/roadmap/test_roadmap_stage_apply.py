"""`devops roadmap stage`: the writes of one item, in git and on GitHub (#2654)."""

from __future__ import annotations

import json
import stat
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from devops_cli import exceptions
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.exceptions import GitHubOperationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import ended_by_stop
from devops_cli.roadmap.stage import (
    StageApplied,
    StageFailure,
    StagePlan,
    apply_stage,
    parse_filters,
    plan_stage,
)
from devops_cli.roadmap.stage_change import StageSplit
from devops_cli.roadmap.store import ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, github_json
from tests.support.roadmap_stage import (
    STAGE_EMAIL,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    seed_stageable,
    validate_args,
)
from tests.support.service_stop import stop_error

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


@pytest.fixture
def opened(github_api: GitHubApiFake) -> GitHubApiFake:
    """GitHub, answering the request that opens a pull request."""
    github_api.route("POST", PULLS, OPENED)
    return github_api


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


def _stage(
    store: InMemoryRoadmapStore, repo: StageRepo, *, step_tokens: int | None = None
) -> StageApplied:
    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        step_tokens=step_tokens,
    )
    return apply_stage(store, plan, source=repo.clone)


def _comments(store: InMemoryRoadmapStore, number: int = 1) -> list[str]:
    return [c.body for c in store.comments_on(number)]


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def test_a_ready_bug_is_staged_with_one_commit_by_the_app(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    model_fake.answer(make_stage_proposal())

    applied = _stage(store, stage_repo)

    assert (applied.staged, applied.stopped, applied.failed) == ((1,), (), ())
    assert stage_repo.origin_git("log", "--format=%ae|%s", f"main..{BRANCH}") == (
        f"{STAGE_EMAIL}|docs(openspec): plan #1 Stop the job dropping a comment"
    )
    files = stage_repo.origin_git("ls-tree", "-r", "--name-only", BRANCH, "--", "openspec").split()
    assert files == [
        f"openspec/changes/{CHANGE}/.openspec.yaml",
        f"openspec/changes/{CHANGE}/design.md",
        f"openspec/changes/{CHANGE}/proposal.md",
        f"openspec/changes/{CHANGE}/specs/comment-thread/spec.md",
        f"openspec/changes/{CHANGE}/tasks.md",
        "openspec/config.yaml",
        "openspec/specs/roadmap-refine/spec.md",
    ]
    assert opened.requested == [f"POST {API}{PULLS}"]
    request = json.loads(opened.sent[0].content)
    assert request["draft"] is True
    assert request["title"] == "docs(openspec): plan #1 Stop the job dropping a comment"
    assert (request["head"], request["base"]) == (BRANCH, "main")
    assert request["body"].startswith("Plans #1\n")


def test_the_clone_keeps_its_head_and_no_worktree_after_a_stage(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    model_fake.answer(make_stage_proposal())

    _stage(store, stage_repo)

    assert stage_repo.git("branch", "--show-current") == "main"
    assert stage_repo.git("branch", "--format=%(refname:short)") == "main"
    assert len(stage_repo.git("worktree", "list").splitlines()) == 1


def test_a_staged_item_gets_one_comment_and_a_record_and_keeps_its_status(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    model_fake.answer(make_stage_proposal())

    _stage(store, stage_repo)

    (comment,) = _comments(store)
    assert comment.startswith("<!-- devops roadmap stage -->\n")
    assert f"branch `{BRANCH}`" in comment
    assert "draft pull request #5" in comment
    assert "1. Keep the last comment:" in comment
    assert "budget of 40000 tokens" in comment
    assert "did not run" not in comment
    item = store.item(1)
    assert item is not None
    assert item.status == "Ready"
    sha = stage_repo.origin_git("rev-parse", BRANCH)
    groups = json.loads(item.job_record[StageRecordKey.GROUPS] or "")
    assert (
        item.job_record[StageRecordKey.BRANCH],
        item.job_record[StageRecordKey.PR],
        item.job_record[StageRecordKey.SHA],
        [g[0] for g in groups],
        item.job_record.get(StageRecordKey.NEEDS_SPLIT),
        item.job_record.get(StageRecordKey.FILE_CAP),
    ) == (BRANCH, "5", sha, ["Keep the last comment"], None, None)


def test_an_item_whose_plan_names_a_missing_path_twice_gets_no_branch_and_no_draft(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    group = make_stage_proposal().groups[0]
    lost = group.model_copy(update={"changes": ["src/devops_cli/missing.py"], "creates": []})
    model_fake.answer(make_stage_proposal(groups=[lost]))

    applied = _stage(store, stage_repo)

    assert (applied.staged, applied.stopped) == ((), ())
    assert opened.requested == []
    assert _pushed(stage_repo) == ["main"]
    assert _comments(store) == []
    assert model_fake.call_count == 2


def test_the_comment_says_when_openspec_did_not_validate_the_change(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    opened: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.installed = False
    model_fake.answer(make_stage_proposal())

    _stage(store, stage_repo)

    assert "`openspec validate` did not run" in _comments(store)[0]


def test_a_group_over_the_budget_gets_a_comment_and_a_record_and_no_branch(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    heavy = heavy_group(stage_repo)
    model_fake.answer(make_stage_proposal(groups=[heavy]), StageSplit(groups=[heavy]))

    applied = _stage(store, stage_repo, step_tokens=6000)

    assert (applied.staged, applied.stopped) == ((), (1,))
    (comment,) = _comments(store)
    assert comment.startswith("<!-- devops roadmap stage -->\n")
    assert '"Keep the last comment"' in comment
    assert "over the budget of 6000 tokens" in comment
    item = store.item(1)
    assert item is not None
    assert (item.job_record[StageRecordKey.NEEDS_SPLIT] or "").startswith("Keep the last comment (")
    assert item.job_record[StageRecordKey.FILE_CAP] == str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS)
    assert StageRecordKey.BRANCH not in item.job_record
    assert _pushed(stage_repo) == ["main"]
    assert github_api.requested == []


class _CommentRefused(InMemoryRoadmapStore):
    """A store whose comment on issue `refused` fails, as GitHub fails a write, and whose comment
    on issue `stopped` fails as the request budget fails it when the Service is stopping
    (#2753)."""

    refused = 0
    stopped = 0

    def comment(self, number: int, body: str) -> None:
        if number == self.stopped:
            raise stop_error()
        if number == self.refused:
            raise GitHubOperationError("comment refused", operation="roadmap.issue.comment")
        super().comment(number, body)


def test_a_comment_that_fails_for_a_stopped_item_leaves_the_others_stopped(
    stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    store = _CommentRefused(repo=STAGE_REPO)
    store.refused = seed_stageable(store)
    other = seed_stageable(store, "fix(roadmap): the job drops a label")
    heavy = heavy_group(stage_repo)
    stuck = make_stage_proposal(groups=[heavy])
    model_fake.answer(stuck, StageSplit(groups=[heavy]), stuck, StageSplit(groups=[heavy]))

    applied = _stage(store, stage_repo, step_tokens=6000)

    (failure,) = applied.failed
    assert (failure.number, failure.error) == (1, "GitHubOperationError")
    assert applied.stopped == (other,)
    assert len(_comments(store, other)) == 1
    refused = store.item(1)
    assert refused is not None
    assert StageRecordKey.NEEDS_SPLIT not in refused.job_record


def _stuck_stage(stage_repo: StageRepo, model_fake: ModelFake, store: _CommentRefused) -> StagePlan:
    """The plan for two items whose group is over the budget, so each gets a comment."""
    heavy = heavy_group(stage_repo)
    stuck = make_stage_proposal(groups=[heavy])
    model_fake.answer(stuck, StageSplit(groups=[heavy]), stuck, StageSplit(groups=[heavy]))
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        step_tokens=6000,
    )


def test_a_stop_of_the_service_ends_the_run_and_is_no_failed_item(
    stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    store = _CommentRefused(repo=STAGE_REPO)
    store.stopped = seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    plan = _stuck_stage(stage_repo, model_fake, store)

    with pytest.raises(exceptions.ServiceStoppingError) as raised:
        apply_stage(store, plan, source=stage_repo.clone)
    assert "stop" in str(raised.value).lower() or str(raised.value) != ""


def test_a_stop_of_the_service_after_a_write_that_failed_ends_the_run_with_that_failure(
    stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    store = _CommentRefused(repo=STAGE_REPO)
    store.refused = seed_stageable(store)
    store.stopped = seed_stageable(store, "fix(roadmap): the job drops a label")
    plan = _stuck_stage(stage_repo, model_fake, store)

    with pytest.raises(exceptions.RoadmapStageError) as raised:
        apply_stage(store, plan, source=stage_repo.clone)

    assert list(raised.value.failed_items) == [store.refused]
    assert not ended_by_stop(raised.value)


def test_a_stop_of_the_service_keeps_the_failures_that_the_plan_found(
    stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    store = _CommentRefused(repo=STAGE_REPO)
    store.stopped = seed_stageable(store)
    plan = _stuck_stage(stage_repo, model_fake, store)
    planned = replace(plan, failed=(StageFailure(7, "fix(roadmap): a title", "AIClientError", ""),))

    with pytest.raises(exceptions.RoadmapStageError) as raised:
        apply_stage(store, planned, source=stage_repo.clone)

    assert list(raised.value.failed_items) == [7]


def _refuse_pushes_of(repo: StageRepo, fragment: str) -> None:
    hook = repo.origin / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        f'  case "$ref" in *"{fragment}"*) echo "refused by the hook" >&2; exit 1;; esac\n'
        "done\n",
        encoding="utf-8",
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)


def test_a_refused_push_stops_its_item_and_the_others_are_staged(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    seed_stageable(store, "fix(roadmap): the job drops a label")
    _refuse_pushes_of(stage_repo, "/1-")
    model_fake.answer(make_stage_proposal())

    applied = _stage(store, stage_repo)

    assert applied.staged == (2,)
    (failure,) = applied.failed
    assert (failure.number, failure.error) == (1, "GitOperationError")
    assert "refused by the hook" in failure.reason
    assert _pushed(stage_repo) == ["fix/2-the-job-drops-a-label", "main"]
    assert [json.loads(r.content)["head"] for r in opened.sent] == ["fix/2-the-job-drops-a-label"]
    item = store.item(1)
    assert item is not None
    assert StageRecordKey.BRANCH not in item.job_record
    assert _comments(store, 1) == []
    assert stage_repo.git("branch", "--format=%(refname:short)") == "main"


def test_a_pull_request_that_cannot_open_leaves_no_remote_branch(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route("POST", PULLS, github_json({"message": "Validation Failed"}, status=422))
    model_fake.answer(make_stage_proposal())

    applied = _stage(store, stage_repo)

    assert applied.staged == ()
    assert [f.number for f in applied.failed] == [1]
    assert _pushed(stage_repo) == ["main"]
    item = store.item(1)
    assert item is not None
    assert StageRecordKey.BRANCH not in item.job_record
    assert _comments(store) == []


def test_a_run_with_nothing_to_stage_writes_nothing(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    empty = InMemoryRoadmapStore(repo=STAGE_REPO)
    empty.seed_issue("fix(roadmap): not ready", fields={ItemField.PRIORITY: "P1-High"})

    applied = _stage(empty, stage_repo)

    assert (applied.staged, applied.stopped, applied.failed) == ((), (), ())
    assert github_api.requested == []
    assert model_fake.call_count == 0
