"""`publish` of the stage Job on its phases (#6705): the plan, the texts and the end of the run.

`publish` clones the repository at the base into a home of its own and gives that clone to the
writer of `--phase all`. It builds the title and the body with `stage_candidate`, removes each
control character but the line feed, and fits the plan-state comment. It trusts no end that the
agent reports: its checks decide `ended` and `unverified`, it takes `timeout` only after the end
time of the budget, and only a `ci_infra` end of the agent counts toward the split limit.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_PHASE_STATE_FILE
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stage.stage import StagedChange, StageTarget, plan_body_hash
from devops_cli.roadmap.stage.stage_change import MeasuredGroup
from devops_cli.roadmap.stage.stage_job import StageJobExit, recorded_check_in, run_stage_job
from devops_cli.roadmap.stage.stage_job_phases import (
    clean_text,
    fit_plan_state,
    publish_stage_job,
)
from devops_cli.roadmap.stores.store import Item, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_EMAIL,
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    run_git,
    seed_stageable,
    validate_args,
)
from tests.support.roadmap_stage_phases import (
    PHASE_CHANGE,
    PHASE_ROOT,
    gate_files,
    hand_over,
    plan_files,
    prepare_run,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

JOB = "devops-cli-stage-roadmap-1-0123456789"
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
COMMIT_TIME = "2026-11-23T12:00:00+00:00"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def gate_repo(
    stage_repo: StageRepo, openspec_fake: OpenSpecFake, github_api: GitHubApiFake
) -> StageRepo:
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    stage_repo.track(gate_files(openspec_fake.version))
    openspec_fake.script(validate_args(PHASE_CHANGE), 0, VALID_REPORT)
    github_api.route(
        "POST",
        PULLS,
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    github_api.route(
        "POST",
        f"{PULLS}/5/requested_reviewers",
        github_json({"requested_reviewers": []}),
    )
    return stage_repo


@pytest.fixture
def git_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `git` first on PATH that commits at `COMMIT_TIME` and logs the folder and the arguments
    of each call, then runs the git of the host."""
    real = shutil.which("git")
    assert real is not None
    folder = tmp_path / "bin"
    folder.mkdir()
    log = tmp_path / "git.log"
    wrapper = folder / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\t%s\\n" "$PWD" "$*" >> "{log}"\n'
        f'GIT_AUTHOR_DATE="{COMMIT_TIME}" GIT_COMMITTER_DATE="{COMMIT_TIME}" exec "{real}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return log


def _check_out(store: InMemoryRoadmapStore, number: int, now: datetime) -> None:
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.JOB: JOB,
            StageRecordKey.JOB_AT: now.isoformat(),
            StageRecordKey.JOB_DEADLINE: (now + timedelta(hours=3)).isoformat(),
        },
    )


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str]:
    item = store.item(number)
    assert item is not None
    return {str(key): value for key, value in item.job_record.items() if value is not None}


def _form(
    store: InMemoryRoadmapStore, repo: StageRepo, api: GitHubApiFake, number: int
) -> tuple[Any, ...]:
    """What a form of the stage Job wrote: the pushed tree and commit, the opened draft, the record
    of the item and the comments of the item and of the draft."""
    opened = [
        request for request in api.sent if request.method == "POST" and request.url.path == PULLS
    ]
    record = _record(store, number)
    record.pop("stage.job_result", None)
    return (
        repo.origin_git("rev-parse", BRANCH),
        json.loads(opened[-1].content),
        record,
        [comment.body for comment in store.comments_on(number)],
        [comment.body for comment in store.comments_on(5)],
    )


def test_one_plan_gives_the_same_publish_in_both_forms(
    gate_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    git_log: Path,
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    # A plan whose group creates no file: the plan files hold no line estimate, so a created
    # file counts one line in the measure of `publish`.
    group = make_stage_proposal().groups[0].model_copy(update={"creates": [], "creates_lines": {}})
    proposal = make_stage_proposal(groups=[group])
    gate_repo.track({"tests/test_sample.py": "def test_it() -> None: ...\n"})
    model_fake.answer(proposal)
    first = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(first)

    whole = run_stage_job(first, repo=STAGE_REPO, item=number, source=gate_repo.clone, now=now)
    assert whole.exit_code is StageJobExit.RESULT
    expected = _form(first, gate_repo, github_api, number)
    listed = gate_repo.origin_git("ls-tree", "-r", "--name-only", BRANCH, "--", PHASE_ROOT)
    rendered = {
        path: gate_repo.origin_git("show", f"{BRANCH}:{path}") + "\n" for path in listed.split()
    }
    gate_repo.origin_git("branch", "-D", BRANCH)
    clone = tmp_path / "second"
    run_git(tmp_path, "clone", "-q", str(gate_repo.origin), str(clone))
    for key, value in (("user.name", STAGE_NAME), ("user.email", STAGE_EMAIL)):
        run_git(clone, "config", key, value)
    second = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(second)
    folders, _ = _prepare_in(second, clone, tmp_path, now)
    hand_over(
        folders, rendered, candidate=f"# {proposal.summary}\n\n{proposal.pull_request_body}\n"
    )

    phased = publish_stage_job(second, folders, repo=STAGE_REPO, item=number, now=now)

    assert phased.exit_code is StageJobExit.RESULT
    assert _form(second, gate_repo, github_api, number) == expected
    assert git_log.read_text(encoding="utf-8")


def _prepare_in(
    store: InMemoryRoadmapStore, clone: Path, tmp_path: Path, now: datetime
) -> tuple[Any, int]:
    from devops_cli.roadmap.phases.files import RunFolders
    from devops_cli.roadmap.stage.stage_job_phases import prepare_stage_job

    folders = RunFolders(tmp_path / "run").make()
    assert prepare_stage_job(store, folders, repo=STAGE_REPO, item=1, source=clone, now=now) is None
    return folders, 1


def test_publish_runs_no_git_command_under_the_work_folder(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, git_log: Path, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(
        folders, plan_files(now.date()), candidate="# Keep the last comment\n\nIt keeps it.\n"
    )
    git_log.write_text("", encoding="utf-8")

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert run.exit_code is StageJobExit.RESULT
    work = str(folders.work)
    calls = git_log.read_text(encoding="utf-8").splitlines()
    assert calls
    assert [call for call in calls if work in call] == []


def _published_body(api: GitHubApiFake) -> dict[str, Any]:
    opened = [
        request for request in api.sent if request.method == "POST" and request.url.path == PULLS
    ]
    body: dict[str, Any] = json.loads(opened[-1].content)
    return body


def test_a_missing_candidate_gives_the_title_of_the_issue_and_the_why_of_the_proposal(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(folders, plan_files(now.date()))

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert run.exit_code is StageJobExit.RESULT
    body = _published_body(github_api)
    assert body["title"] == "docs(spec): plan #1 the job drops a comment"
    assert body["body"].startswith(make_stage_proposal().why)


def test_a_body_text_that_the_form_refuses_gives_the_why_of_the_proposal(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    long_text = "The job keeps the comment. " * 400
    hand_over(folders, plan_files(now.date()), candidate=f"# Keep the last comment\n\n{long_text}")

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert run.exit_code is StageJobExit.RESULT
    body = _published_body(github_api)
    assert body["title"] == "docs(spec): plan #1 Keep the last comment"
    assert body["body"].startswith(make_stage_proposal().why)
    assert _record(store, number).get("stage.failed_class") is None


def test_a_handle_a_tag_and_a_control_character_go_through_safe_text_once(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(
        folders,
        plan_files(now.date()),
        candidate="# Keep the last comment\n\nAsk @octocat to keep <b> the \x1b last comment.\n",
    )

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert run.exit_code is StageJobExit.RESULT
    body = _published_body(github_api)["body"]
    assert body.count("`@octocat`") == 1
    assert body.count("&lt;b>") == 1
    assert "&amp;lt;" not in body
    assert "\x1b" not in body


def test_clean_text_removes_each_control_character_but_the_line_feed() -> None:
    assert clean_text("a\x1bb\x07c\nd\re\tf\x7f") == "abc\ndef"


def _change(titles: list[str]) -> StagedChange:
    item = Item(number=1, title="fix(roadmap): the job drops a comment", url="u")
    groups = make_stage_proposal().groups
    measured = tuple(
        MeasuredGroup(groups[0].model_copy(update={"title": title}), 100, 1) for title in titles
    )
    return StagedChange(
        StageTarget(item, "fix", "the-job-drops-a-comment"),
        "title",
        "body",
        {"f": "x"},
        measured,
        True,
        9000,
        make_stage_proposal(),
    )


def test_long_group_titles_are_cut_in_the_plan_state_comment_and_kept_in_the_files() -> None:
    from devops_cli.roadmap.stage.stage import plan_state_text

    change = _change(["Keep the comment " * 1000] * 5)
    assert len(plan_state_text(change, 99999)) > 65536

    fitted = fit_plan_state(change)

    assert len(plan_state_text(fitted, 99999)) <= 65536
    assert fitted.files == change.files
    assert fitted.proposal == change.proposal
    assert fit_plan_state(_change(["Keep the comment"])) == _change(["Keep the comment"])


def test_publish_counts_the_requests_of_prepare(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    folders, number = prepare_run(store, gate_repo, tmp_path, now=now)
    hand_over(folders, plan_files(now.date()), candidate="# Keep the last comment\n\nIt keeps.\n")
    path = folders.state / CONST_ROADMAP_PHASE_STATE_FILE
    state = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**state, "requests": 7}), encoding="utf-8")

    run = publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now)

    assert run.budget.spent() >= 7


def _ended_agent(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    tmp_path: Path,
    config: Callable[..., Path],
    end: str,
    *,
    now: datetime,
    before: Callable[[int], None] | None = None,
) -> tuple[Any, int]:
    config(roadmap={"stage": {"job": JOB}})
    folders, number = prepare_run(store, repo, tmp_path, now=now)
    _check_out(store, number, now)
    if before is not None:
        before(number)
    hand_over(
        folders,
        plan_files(now.date()),
        candidate="# Keep the last comment\n\nIt keeps.\n",
        outcome={"end": end},
    )
    return publish_stage_job(store, folders, repo=STAGE_REPO, item=number, now=now), number


@pytest.mark.parametrize(
    ("end", "exit_code"),
    [
        pytest.param("provider", StageJobExit.EVICTED, id="provider"),
        pytest.param("spend_limit", StageJobExit.FAILURE, id="spend-limit"),
    ],
)
def test_a_provider_end_records_its_class_and_no_count(
    store: InMemoryRoadmapStore,
    gate_repo: StageRepo,
    tmp_path: Path,
    config: Callable[..., Path],
    end: str,
    exit_code: StageJobExit,
) -> None:
    run, number = _ended_agent(store, gate_repo, tmp_path, config, end, now=datetime.now(UTC))

    assert run.exit_code is exit_code
    record = _record(store, number)
    assert (record["stage.failed_class"], record.get("stage.plan_defects")) == (end, None)
    assert gate_repo.origin_git("branch", "--format=%(refname:short)").split() == ["main"]


def test_an_agent_ci_infra_end_counts_toward_the_split_limit(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path, config: Callable[..., Path]
) -> None:
    run, number = _ended_agent(
        store, gate_repo, tmp_path, config, "ci_infra", now=datetime.now(UTC)
    )

    assert run.exit_code is StageJobExit.FAILURE
    record = _record(store, number)
    assert (record["stage.failed_class"], record["stage.plan_defects"]) == ("ci_infra", "1")
    assert record.get("stage.job") is None


def test_agent_ci_infra_ends_up_to_the_limit_return_the_item_for_a_split(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path, config: Callable[..., Path]
) -> None:
    def two_earlier(number: int) -> None:
        item = store.item(number)
        assert item is not None
        store.set_marks(
            item,
            {
                StageRecordKey.PLAN_DEFECTS: "2",
                StageRecordKey.PLAN_DEFECTS_BODY: plan_body_hash(item),
            },
        )

    config(roadmap={"stage": {"plan_defect_limit": 3}})
    run, number = _ended_agent(
        store, gate_repo, tmp_path, config, "ci_infra", now=datetime.now(UTC), before=two_earlier
    )

    assert run.exit_code is StageJobExit.FAILURE
    item = store.item(number)
    assert item is not None
    assert item.status == "New"
    assert "split it into smaller items" in store.comments_on(number)[-1].body
    assert _record(store, number)["stage.failed_class"] == FailureClass.PLAN_DEFECT.value


def test_a_timeout_after_the_end_time_checks_in_the_deadline(
    store: InMemoryRoadmapStore, gate_repo: StageRepo, tmp_path: Path, config: Callable[..., Path]
) -> None:
    now = datetime.now(UTC) - timedelta(days=1)

    run, number = _ended_agent(store, gate_repo, tmp_path, config, "timeout", now=now)

    assert run.exit_code is StageJobExit.DEADLINE
    item = store.item(number)
    assert item is not None
    check_in = recorded_check_in(item)
    assert check_in is not None
    assert check_in.result == "deadline"


@pytest.mark.parametrize("end", ["timeout", "unverified"])
def test_an_early_timeout_or_an_unverified_end_with_good_files_is_pushed(
    store: InMemoryRoadmapStore,
    gate_repo: StageRepo,
    tmp_path: Path,
    config: Callable[..., Path],
    end: str,
) -> None:
    run, number = _ended_agent(store, gate_repo, tmp_path, config, end, now=datetime.now(UTC))

    assert run.exit_code is StageJobExit.RESULT
    assert _record(store, number)["stage.pr"] == "5"
