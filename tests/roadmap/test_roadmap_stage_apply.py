"""`devops roadmap stage`: the writes of one item, in git and on GitHub (#2654)."""

from __future__ import annotations

import json
import stat
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from devops_cli import exceptions
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.config.defaults import DEFAULT_ROADMAP_STAGE_STEP_TOKENS
from devops_cli.exceptions import GitHubOperationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import ended_by_stop
from devops_cli.roadmap.stage import (
    StageApplied,
    StageFailure,
    StagePlan,
    StageResult,
    apply_stage,
    parse_filters,
    plan_stage,
    render_stage_plan,
    stage_results,
)
from devops_cli.roadmap.stage_change import StageProposal, StageSplit
from devops_cli.roadmap.stage_toolbox import ToolboxModel
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
from tests.support.scripted_model import Script, call
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
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for i in range(2, 5):
        store.seed_issue(f"placeholder {i}")
    store.seed_pull("staging PR", head_ref=BRANCH, draft=True)
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
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    *,
    step_tokens: int | None = None,
    toolbox: Script | None = None,
) -> StageApplied:
    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        step_tokens=step_tokens,
        model=ToolboxModel(toolbox.model()) if toolbox else None,
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


def test_the_draft_pull_request_holds_the_labels_of_its_title(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    model_fake.answer(make_stage_proposal())
    _stage(store, stage_repo)
    assert store._roadmap.issues[5].labels == ("type/docs", "scope/openspec")


def test_a_refused_label_keeps_the_staged_item_and_notes_in_the_comment(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    from tests.roadmap_faults import Fault, StoppingStore

    model_fake.answer(make_stage_proposal())
    failing = StoppingStore(store, Fault(at=1, write="label_issue"))
    applied = apply_stage(
        failing.as_store(),
        plan_stage(store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(())),
        source=stage_repo.clone,
    )
    assert (applied.staged, applied.stopped, applied.failed) == ((1,), (), ())
    assert stage_repo.origin_git("branch", "--list", BRANCH).strip() != ""
    item = store.item(1)
    assert item is not None
    assert all(
        k in item.job_record for k in ("stage.branch", "stage.pr", "stage.sha", "stage.groups")
    )
    comment = _comments(store, 1)[0]
    assert "#5" in comment
    assert "type/docs" in comment


def test_an_unauthenticated_error_from_label_issue_ends_the_run(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    from unittest.mock import patch

    from devops_cli.exceptions.git import GitHubUnauthenticatedError

    model_fake.answer(make_stage_proposal())
    with patch.object(store, "label_issue", side_effect=GitHubUnauthenticatedError("bad token")):
        with pytest.raises(GitHubUnauthenticatedError, match="bad token"):
            _stage(store, stage_repo)


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
    assert f"budget of {DEFAULT_ROADMAP_STAGE_STEP_TOKENS} tokens" in comment
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
    lost = group.model_copy(
        update={"changes": ["src/devops_cli/missing.py"], "creates": [], "creates_lines": {}}
    )
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
    stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for i in range(3, 5):
        store.seed_issue(f"placeholder {i}")
    store.seed_pull("staging PR", head_ref="fix/2-the-job-drops-a-label", draft=True)
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


# ── The report of the plan run (#3037) ────────────────────────────────────────

_SECRET = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


@pytest.mark.usefixtures("model_fake")
def test_the_comment_lists_the_tool_calls_and_the_counts_of_the_plan_run(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, opened: GitHubApiFake
) -> None:
    script = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())

    applied = _stage(store, stage_repo, toolbox=script)

    (comment,) = _comments(store)
    assert applied.staged == (1,)
    assert "The plan run made 2 model request(s)" in comment
    assert '1. `read_file({"path":"src/devops_cli/sample.py"})`' in comment
    assert "input tokens" in comment
    assert "output tokens" in comment


@pytest.mark.usefixtures("model_fake")
def test_the_comment_of_an_item_that_made_no_tool_call_says_so(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, opened: GitHubApiFake
) -> None:
    _stage(store, stage_repo, toolbox=Script(make_stage_proposal()))

    (comment,) = _comments(store)
    assert "The plan run made 1 model request(s)" in comment
    assert "The model made no tool call." in comment


def test_the_comment_of_an_item_planned_with_one_call_has_no_report(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake, opened: GitHubApiFake
) -> None:
    model_fake.answer(make_stage_proposal())

    _stage(store, stage_repo)

    (comment,) = _comments(store)
    assert "plan run" not in comment


@pytest.mark.usefixtures("model_fake")
def test_the_comment_of_an_item_with_two_plan_runs_lists_the_calls_of_both_and_sums_the_counts(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, opened: GitHubApiFake
) -> None:
    stage_repo.track({"tests/security/test_scanner_tool_executor.py": ""})
    group = make_stage_proposal().groups[0]
    refused = make_stage_proposal(
        groups=[
            group.model_copy(
                update={"changes": [*group.changes, "tests/test_scanner_tool_executor.py"]}
            )
        ]
    )
    script = Script(
        call("list_files", directory="src"),
        refused,
        call("read_file", path="src/devops_cli/sample.py"),
        make_stage_proposal(),
    )

    _stage(store, stage_repo, toolbox=script)

    (comment,) = _comments(store)
    assert "The plan run made 4 model request(s)" in comment
    first = comment.index("1. `list_files(")
    second = comment.index("2. `read_file(")
    assert first < second


@pytest.mark.usefixtures("model_fake")
def test_the_comment_holds_the_masked_argument_and_not_the_secret(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, opened: GitHubApiFake
) -> None:
    script = Script(call("search_code", text=_SECRET), make_stage_proposal())

    _stage(store, stage_repo, toolbox=script)

    (comment,) = _comments(store)
    assert (_SECRET in comment, "<masked-github-token>" in comment) == (False, True)


def test_the_replay_of_2971_returns_the_item_with_the_evidence_and_opens_no_pull_request(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    """The issue cites `validate_url`, which a commit removed (#3011)."""
    stage_repo.track({"src/devops_cli/urls.py": "def validate_url(url):\n    return url\n"})
    stage_repo.git("rm", "-q", "src/devops_cli/urls.py")
    stage_repo.git("commit", "-q", "-m", "remove validate_url")
    stage_repo.git("push", "-q", "origin", "main")
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(
        store, "fix(http): validate_url lets a private address pass", body="Fix `validate_url`."
    )
    evidence = "`validate_url` has no definition at the staging commit. Commit removed it."
    model_fake.answer(StageProposal.model_validate({"premise_failed": evidence}))

    applied = _stage(store, stage_repo)

    request = json.loads(model_fake.calls[0].prompt)
    assert "remove validate_url" in request["probes"]
    assert (applied.returned, applied.staged, applied.stopped, applied.failed) == (
        (number,),
        (),
        (),
        (),
    )
    (comment,) = _comments(store, number)
    assert comment.startswith("<!-- devops roadmap stage -->\n")
    assert comment.endswith(evidence)
    item = store.item(number)
    assert item is not None
    assert item.status == "New"
    assert StageRecordKey.BRANCH not in item.job_record
    assert _pushed(stage_repo) == ["main"]
    assert github_api.requested == []
    assert model_fake.call_count == 1


def test_a_returned_item_counts_under_the_result_returned(
    stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    model_fake.answer(StageProposal.model_validate({"premise_failed": "The premise is false."}))
    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
    )

    applied = apply_stage(store, plan, source=stage_repo.clone)

    assert stage_results(plan, applied) == {1: StageResult.RETURNED}
    assert render_stage_plan(plan).count("## Returned: the premise is false") == 1
