"""A Staged item for the tests of the implement job (#2665): the repository of `stage_repo` with
the branch that the stage job pushes, the item and its record, and the draft pull request that
GitHub reports for it.

The branch holds one commit by the App, `STAGE_NAME`, with the change folder
`openspec/changes/1-the-job-drops-a-comment/` and its two task groups. `STAGE_NAME` is also the
identity the clone commits as, so the commits of the steps are the App's too.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse

from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.implement.implement import parse_implement_filters, plan_implement
from devops_cli.roadmap.implement.implement_run import ImplementApplied, apply_implement
from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import API, GitHubApiFake, github_json, route_compare_files
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import WINDOW, command_text, git_for_real
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo

BRANCH = "fix/1-the-job-drops-a-comment"
CHANGE = "1-the-job-drops-a-comment"
CHANGE_DIR = f"openspec/changes/{CHANGE}"
PULL = 5
TITLE = "fix(roadmap): the job drops a comment"
BODY = (
    "## Problem or Motivation\n\nThe job drops the last comment of a thread.\n\n"
    "## Acceptance criteria\n\n- The job keeps every comment.\n"
)

# The labels file of the repository: it declares the scope of `TITLE`, and no other scope.
LABELS_FILE = """\
- name: type/docs
  color: 0075CA
- name: type/bug
  color: D73A4A
- name: scope/openspec
  color: 0E8A16
- name: scope/roadmap
  color: 0E8A16
"""

PROPOSAL = (
    "# Proposal\n\n## Why\n\nThe job drops the last comment of a thread (#1). It must keep it.\n\n"
    "## What Changes\n\n- The job keeps every comment.\n\n"
    "## Feasibility\n\n- The job reads every comment of the thread in the clone.\n\n"
    "## Existing Tool Considered\n\nNo external tool covers this repository function.\n"
)
DESIGN = "# Design\n\n## Decisions\n\n- Keep the last comment.\n"
TASKS = """\
# Tasks

## 1. The first group

Reads: `CONTEXT.md`. Changes: `src/devops_cli/shout.py` (new), `tests/test_shout.py` (new).

- [ ] 1.1 Add `src/devops_cli/shout.py`
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## 2. The second group

Reads: `CONTEXT.md`. Changes: `CONTEXT.md`.

- [ ] 2.1 Document the function in `CONTEXT.md`
  - Verification: `$ uv run devops docs check`

## Criteria

- Group 1: The job keeps every comment.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
"""
TICKED_FIRST = TASKS.replace("- [ ] 1.1 Add", "- [x] 1.1 Add")
TICKED_ALL = TICKED_FIRST.replace("- [ ] 2.1 Document", "- [x] 2.1 Document")
SHOUT = '"""Shout."""\n\n\ndef shout(text: str) -> str:\n    """Shout `text`."""\n    return text.upper()\n'
SHOUT_DOC = "# Context\nThe shout function upper-cases a text.\n"
TASKS_PATH = f"{CHANGE_DIR}/tasks.md"

# The declaration of the project steps (#3484) that devops-cli keeps on its default branch. A test
# world holds it on `main`, as the repository of devops-cli does; `undeclare_steps` takes it off.
STEPS_FILE = ".devops/roadmap.toml"
STEPS_DECLARATION = "[implement.steps]\ndocs = true\narchive = true\n"
# The most seconds that the job of a test world waits for the checks of its pull request: three
# polls, and not the hour of a Job, so a watch that waits out the monitor polls the pull request four
# times and not 121 (#4688).
WATCH_SECONDS = 3 * DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS

OPEN_DRAFT = {
    "state": "open",
    "draft": True,
    "merged": False,
    "title": "docs(openspec): plan #1 Stop the job dropping a comment",
    "head": {"ref": BRANCH, "sha": ""},
    "base": {"ref": "main", "sha": ""},
    "labels": [],
}
# The draft after the review of its plan found an open finding: the stage job labels it (#3264).
NEEDS_FIX_DRAFT = {**OPEN_DRAFT, "labels": [{"name": "plan/needs-fix"}]}


def branch_of(number: int, slug: str = "the-job-drops-a-comment") -> str:
    """The staged branch of item `number`, named with the slug of its change folder."""
    return f"fix/{number}-{slug}"


def write_change(
    root: Path,
    tasks: str = TASKS,
    number: int = 1,
    *,
    slug: str = "the-job-drops-a-comment",
    archived: bool = False,
) -> None:
    """The files of the change folder of item `number`, in the checkout at `root`. With
    `archived`, the folder is where `openspec archive` puts it, with a date."""
    name = f"2026-10-28-{number}-{slug}" if archived else f"{number}-{slug}"
    folder = root / "openspec" / "changes" / ("archive" if archived else "") / name
    folder.mkdir(parents=True, exist_ok=True)
    for filename, text in (
        ("proposal.md", PROPOSAL),
        ("design.md", DESIGN),
        ("tasks.md", tasks),
        (".openspec.yaml", "schema: spec-driven\ncreated: 2026-10-29\nskip_specs: true\n"),
    ):
        (folder / filename).write_text(text, encoding="utf-8")


def push_staged_branch(
    repo: StageRepo,
    *,
    tasks: str = TASKS,
    author: str = STAGE_NAME,
    number: int = 1,
    slug: str = "the-job-drops-a-comment",
    files: Mapping[str, str] | None = None,
    subject: str | None = None,
) -> None:
    """Push the branch of item `number` with one commit by `author` that adds the change and the
    `files` of `files`, as the stage job does; the clone stays on `main` with no local branch.
    `slug` names the branch and the change folder. `subject` is the subject of the commit, which
    holds no plan title unless a test gives one."""
    branch = branch_of(number, slug)
    repo.git("switch", "-q", "-c", branch)
    write_change(repo.clone, tasks, number, slug=slug)
    for name, text in (files or {}).items():
        (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / name).write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    message = subject or "fix(roadmap): plan"
    repo.git("-c", f"user.name={author}", "commit", "-q", "-m", message)
    repo.git("push", "-q", "origin", branch)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", branch)


def merge_plan(
    repo: StageRepo,
    number: int = 1,
    *,
    tasks: str = TASKS,
    slug: str = "the-job-drops-a-comment",
    archived: bool = False,
    subject: str | None = None,
) -> None:
    """Merge the change of item `number` into `main` of `origin`, as the merge of its staging
    pull request does: one commit on `main`, and no branch. `subject` is the subject of the
    commit, which holds no summary of the plan unless a test gives one."""
    write_change(repo.clone, tasks, number, slug=slug, archived=archived)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", subject or f"docs(openspec): plan #{number}")
    repo.git("push", "-q", "origin", "main")


def seed_staged(
    store: InMemoryRoadmapStore,
    *,
    labels: tuple[str, ...] = ("type/bug", "effort/low"),
    priority: str = "P1-High",
    status: str = "Ready",
    record: bool = True,
    author_association: str | None = "OWNER",
    author_login: str | None = None,
    title: str = TITLE,
    pull: int = PULL,
) -> int:
    """An item with the stage job's record: its branch and the draft pull request `pull`. The
    login of the author is given to the store only when the caller names one."""
    author: dict[str, Any] = {"author_association": author_association}
    if author_login is not None:
        author["author_login"] = author_login
    number = store.seed_issue(
        title,
        body=BODY,
        labels=labels,
        fields={ItemField.STATUS: status, ItemField.PRIORITY: priority},
        **author,
    )
    if record:
        item = store.item(number)
        assert item is not None
        store.set_marks(
            item, {StageRecordKey.BRANCH: branch_of(number), StageRecordKey.PR: str(pull)}
        )
    return number


def route_pull_status(
    api: GitHubApiFake, status: dict[str, object] = OPEN_DRAFT, pull: int = PULL
) -> None:
    """GitHub's answer to the read of the state of pull request `pull`."""
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{pull}", github_json(status))


@pytest.fixture
def app_slug(config: Callable[..., Path]) -> None:
    """The slug of the App, so that `STAGE_NAME` is its bot's login."""
    config(service={"github_app": {"slug": STAGE_NAME.removesuffix("[bot]")}})


@pytest.fixture
def no_continuation(config: Callable[..., Path]) -> None:
    """The Service does not continue a Job that ended without a result (#3721). A test that reads
    the stop of such a Job uses this fixture, so the stop stays Blocked."""
    config(roadmap={"implement": {"continuations_per_item": 0}})


@pytest.fixture
def staged_tasks() -> str:
    """The `tasks.md` of the staged branch. A test module overrides it for a change of its own."""
    return TASKS


@pytest.fixture
def planned_tasks() -> str:
    """The `tasks.md` that `main` holds for a Planned item. A test module overrides it."""
    return TASKS


@pytest.fixture
def staged_files() -> dict[str, str]:
    """The files that the staged branch adds besides its change folder. A test module overrides it."""
    return {}


@pytest.fixture
def plan_subject() -> str | None:
    """The subject of the commit that adds the change folder: the commit of the staged branch, or
    the merge of the plan into `main`. None keeps a subject with no summary of the plan. A test
    parametrizes it to give a plan title (#5341)."""
    return None


@pytest.fixture
def staged_repo(
    stage_repo: StageRepo,
    app_slug: None,
    staged_tasks: str,
    staged_files: dict[str, str],
    plan_subject: str | None,
) -> StageRepo:
    """`stage_repo` with the staged branch pushed."""
    push_staged_branch(stage_repo, tasks=staged_tasks, files=staged_files, subject=plan_subject)
    return stage_repo


# ── The calls of an agent ─────────────────────────────────────────────────────────────────


def group_one_calls() -> tuple[tuple[str, dict[str, Any]], ...]:
    """The calls of an agent that writes the code of group 1 and ticks its task."""
    return (
        ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
        ("write_file", {"path": TASKS_PATH, "content": TICKED_FIRST}),
    )


def group_two_calls(tasks: str = TICKED_ALL) -> tuple[tuple[str, dict[str, Any]], ...]:
    """The calls of an agent that writes the document of group 2 and ticks its task."""
    return (
        ("write_file", {"path": "CONTEXT.md", "content": SHOUT_DOC}),
        ("write_file", {"path": TASKS_PATH, "content": tasks}),
    )


def two_groups(*more: ModelResponse) -> ModelScript:
    """The replies of a model that completes group 1 and then group 2, then the `more` replies."""
    return ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
        *more,
    )


def a_fix() -> tuple[ModelResponse, ModelResponse]:
    """The replies of a model that fixes a failed check by changing the code, and says so."""
    changed = SHOUT + "\n\ndef whisper(text: str) -> str:\n    return text.lower()\n"
    return (
        tool_calls(("write_file", {"path": "src/devops_cli/shout.py", "content": changed})),
        say("Fixed the check."),
    )


def long_run_trace() -> ImplementTrace:
    """The trace of a long run (#4457): 100 model events of 20,000 input tokens, 300 output
    tokens and 4 seconds, each followed by one or two shell calls (150 in all), then a failed
    attempt. Its totals are 2,030,000 tokens and 400.0 seconds, and the bound of the trace drops
    every model event."""
    trace = ImplementTrace(step="group 1")
    calls = 0
    for number in range(100):
        trace.model_call("model-a", 20_000, 300, 4.0)
        for _ in range(1 if number % 2 else 2):
            trace.tool_call("shell", "git", f"{calls:012x}", "ok", status=0)
            calls += 1
    trace.attempt(1, "model-a", "limit_reached", "the step made too many requests", repair=False)
    return trace


# ── Pull request 5, as GitHub answers the watch of the job ────────────────────────────────

CHECK_LINK = f"https://github.com/{STAGE_REPO}/actions/runs/101/job/202"
OLD_HEAD = "0" * 40
PASS: dict[str, Any] = {
    "name": "Tests & Coverage",
    "status": "completed",
    "conclusion": "success",
    "html_url": CHECK_LINK,
}
FAIL: dict[str, Any] = {**PASS, "conclusion": "failure"}
RUNNING: dict[str, Any] = {**PASS, "status": "in_progress", "conclusion": None}
_PULL_API = f"api repos/{STAGE_REPO}/pulls/{PULL}"
_THREADS_QUERY = "GetReviewThreads"
_ARCHIVED_FILE = {
    "filename": f"openspec/changes/archive/2026-10-29-{CHANGE}/proposal.md",
    "status": "added",
}


def _threads_page(*threads: dict[str, Any]) -> str:
    page = {"nodes": list(threads), "pageInfo": {"hasNextPage": False, "endCursor": None}}
    return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": page}}}})


OPEN_THREAD: dict[str, Any] = {
    "id": "T1",
    "isResolved": False,
    "path": "src/devops_cli/shout.py",
    "line": 3,
    "comments": {
        "nodes": [{"id": "T1-0", "body": "Rename this.", "author": {"login": "reviewer"}}],
        "pageInfo": {"hasNextPage": False},
    },
}


class PullFake:
    """Pull request 5 of `STAGE_REPO` as GitHub answers `monitor_pr` and `gh`.

    The head is the tip of `BRANCH` on `origin`. The checks of the first head that it sees are
    `runs[0]`, those of the second head `runs[1]`, and the last list repeats. `stale` reads show
    the previous head, `OLD_HEAD`, with a failed check. `gh pr ready` flips the draft flag.
    `closed` closes the pull request without a merge. The compare of `main` and each head lists
    the archived change (#2530).
    """

    def __init__(self, api: GitHubApiFake, gh: ProcessFake, repo: StageRepo) -> None:
        self.api, self.gh, self.repo = api, gh, repo
        self.runs: list[list[dict[str, Any]]] = [[PASS]]
        self.heads: list[str] = []
        self.stale = 0
        self.conflict = False
        self.closed = False
        self.ready_calls: list[tuple[str, ...]] = []
        self.log = "FAILED tests/test_shout.py::test_shout - assert 'A' == 'a'"
        self.run_view_calls: list[tuple[str, ...]] = []
        self.threads()
        self._answer(
            "/status", ProcessAnswer(stdout=json.dumps({"state": "success", "statuses": []}))
        )
        self._answer("contents/openspec/changes", ProcessAnswer())
        references = {
            "totalCount": 1,
            "nodes": [
                {
                    "number": 1,
                    "state": "OPEN",
                    "repository": {"nameWithOwner": STAGE_REPO},
                    "labels": {"nodes": [{"name": "priority/p1-high"}]},
                }
            ],
        }
        closing = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": references}}}}
        self._answer("closingIssuesReferences", ProcessAnswer(stdout=json.dumps(closing)))
        gh.answer(
            lambda call: " ".join(call.argv).endswith(_PULL_API),
            ProcessAnswer(side_effect=self._pull),
        )
        gh.answer(
            lambda call: call.argv[1:3] == ("pr", "ready"), ProcessAnswer(side_effect=self._ready)
        )
        gh.answer(
            lambda call: call.argv[1:3] == ("run", "view"),
            ProcessAnswer(side_effect=self._run_view),
        )
        api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}/reviews?per_page=100", github_json([]))
        api.route(
            "GET", f"/repos/{STAGE_REPO}/issues/{PULL}/timeline?per_page=100", github_json([])
        )
        api.route("PATCH", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json({"number": PULL}))
        api.route(
            "POST",
            f"/repos/{STAGE_REPO}/issues/{PULL}/comments",
            github_json({"id": 1}, status=201),
        )
        api.route("PATCH", f"/repos/{STAGE_REPO}/issues/comments/1", github_json({"id": 1}))
        self.comments()

    def comments(self, *comments: dict[str, Any]) -> None:
        """The comments that the pull request holds when the job lists them (#4070). None at first."""
        listing = f"/repos/{STAGE_REPO}/issues/{PULL}/comments?per_page=100"
        self.api.route("GET", listing, github_json(list(comments)))

    def _answer(self, route: str, answer: ProcessAnswer) -> None:
        self.gh.answer(lambda call, key=route: key in " ".join(call.argv), answer)

    def threads(self, *threads: dict[str, Any]) -> None:
        """The unresolved review threads of the pull request."""
        self._answer(_THREADS_QUERY, ProcessAnswer(stdout=_threads_page(*threads)))

    def _route_checks(self, sha: str, runs: list[dict[str, Any]]) -> None:
        path = f"/repos/{STAGE_REPO}/commits/{sha}/check-runs?per_page=100"
        self.api.route("GET", path, github_json({"total_count": len(runs), "check_runs": runs}))

    def _pull(self, _call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if self.stale > 0:
            self.stale -= 1
            sha, runs = OLD_HEAD, [FAIL]
        else:
            sha = self.repo.origin_git("rev-parse", BRANCH)
            if sha not in self.heads:
                self.heads.append(sha)
            runs = self.runs[min(self.heads.index(sha), len(self.runs) - 1)]
        self._route_checks(sha, runs)
        route_compare_files(self.api, STAGE_REPO, "main", sha, _ARCHIVED_FILE, merge_base="c" * 40)
        repo = {"full_name": STAGE_REPO, "default_branch": "main"}
        dirty = self.conflict
        payload = {
            "number": PULL,
            "merged": False,
            "state": "closed" if self.closed else "open",
            "draft": not self.ready_calls,
            "mergeable": not dirty,
            "mergeable_state": "dirty" if dirty else "clean",
            "base": {"ref": "main", "sha": "b" * 40, "repo": repo},
            "head": {"ref": BRANCH, "sha": sha, "repo": repo},
        }
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload))

    def _ready(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        self.ready_calls.append(call.argv[1:])
        return subprocess.CompletedProcess([], 0, stdout="")

    def _run_view(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        self.run_view_calls.append(call.argv[1:])
        return subprocess.CompletedProcess([], 0, stdout=self.log)


# ── The job, end to end ───────────────────────────────────────────────────────────────────


def archive_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `uv run devops openspec archive <change>` does to the worktree: it moves the change
    folder under `archive/`, dated."""
    assert call.cwd is not None
    change = command_text(call).split()[-1]
    source = call.cwd / "openspec" / "changes" / change
    target = call.cwd / "openspec" / "changes" / "archive" / f"2026-10-29-{change}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(source, target)
    return subprocess.CompletedProcess(call.argv, 0, stdout="archived\n")


def docs_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `uv run devops docs generate` does: it writes one generated file."""
    assert call.cwd is not None
    (call.cwd / "docs" / "GENERATED.md").parent.mkdir(parents=True, exist_ok=True)
    (call.cwd / "docs" / "GENERATED.md").write_text("Generated.\n", encoding="utf-8")
    return subprocess.CompletedProcess(call.argv, 0, stdout="generated\n")


def move_main_when(
    world: JobWorld,
    matches: Callable[[ProcessCall], bool],
    effect: Callable[[ProcessCall], subprocess.CompletedProcess[str]],
) -> None:
    """Make `main` gain a commit that conflicts with the branch, at the first call that `matches`.
    The call itself has the `effect` that it has without this move."""
    moved: list[bool] = []

    def move(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if not moved:
            moved.append(True)
            path = world.repo.clone / "src" / "devops_cli"
            path.mkdir(parents=True, exist_ok=True)
            (path / "shout.py").write_text('"""Main shouts."""\n', encoding="utf-8")
            world.repo.git("add", "-A")
            world.repo.git("commit", "-q", "-m", "main also adds the shout")
            world.repo.git("push", "-q", "origin", "main")
        return effect(call)

    world.programs.answer(matches, ProcessAnswer(side_effect=move))


def advance_main(world: JobWorld, name: str = "main-moved.txt", text: str = "Main.\n") -> None:
    """What a merge does on GitHub: `main` of `origin` gains a commit that writes `name`."""
    (world.repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
    (world.repo.clone / name).write_text(text, encoding="utf-8")
    world.repo.git("add", "-A")
    world.repo.git("commit", "-q", "-m", f"main adds {name}")
    world.repo.git("push", "-q", "origin", "main")


@dataclass
class JobWorld:
    """A Staged item, its repository, GitHub and the process edge, ready for a run."""

    repo: StageRepo
    store: InMemoryRoadmapStore
    api: GitHubApiFake
    programs: ProcessFake
    pull: PullFake
    clock: ClockFake
    number: int = 1
    comments: list[str] = field(default_factory=list)

    def plan(
        self, *, item: int | None = None, limit: int = 1, filters: tuple[str, ...] = ()
    ) -> Any:
        """The plan of a run."""
        return plan_implement(
            self.store,
            repo=STAGE_REPO,
            source=self.repo.clone,
            filters=parse_implement_filters(filters),
            item_number=item,
            limit=limit,
        )

    def run(
        self,
        script: ModelScript,
        *,
        limit: int = 1,
        item: int | None = None,
        splitter: Any = None,
        window: int = WINDOW,
    ) -> ImplementApplied:
        """Plan and apply a run with the scripted model."""
        return apply_implement(
            self.store,
            self.plan(item=item, limit=limit),
            source=self.repo.clone,
            model=script.model(),
            window=window,
            splitter=splitter,
        )

    def issue_comments(self, number: int = 1) -> list[str]:
        """The bodies of the comments on an item."""
        return [comment.body for comment in self.store.comments_on(number)]

    def sent(self, method: str, tail: str) -> list[dict[str, Any]]:
        """The JSON bodies of the requests `method` `tail` that GitHub received."""
        url = f"{API}/repos/{STAGE_REPO}/{tail}"
        return [
            json.loads(request.content)
            for request in self.api.sent
            if (request.method, str(request.url)) == (method, url)
        ]

    def origin_log(self) -> list[str]:
        """The subjects of the commits of `BRANCH` on origin past main, oldest first."""
        out = self.repo.origin_git("log", "--reverse", "--format=%s", f"main..{BRANCH}")
        return out.splitlines()


def undeclare_steps(repo: StageRepo) -> None:
    """Take the declaration of the project steps off `main` of `origin`, as a target repository
    that is not devops-cli has none."""
    repo.git("rm", "-q", STEPS_FILE)
    repo.git("commit", "-q", "-m", "Declare no project step")
    repo.git("push", "-q", "origin", "main")


def _world(
    repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    clock: ClockFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
    *,
    planned: bool,
) -> JobWorld:
    """The job in a runner, with pull request 5 as a draft whose checks pass, and the process edge,
    where git runs for real and the project's own commands are answered. The kernel call that makes
    the job's process unreadable is answered too: it would change the test run. For a Planned item,
    GitHub makes pull request 5 when the job opens it."""
    repo.track({STEPS_FILE: STEPS_DECLARATION})
    monkeypatch.setattr("devops_cli.core.process_hardening._prctl", lambda *_args: 0)
    # The runner Job acts as the App, with a token for the one repository. The test mints no token.
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.acts_as_github_app", lambda: True
    )
    api, programs = github_api_and_gh
    # A watch that waits out the monitor's timeout moves the clock past the reset of the quota.
    for resource in ("core", "graphql"):
        get_github_rate_limiter().update_quota(
            resource, remaining=5000, limit=5000, reset_epoch=time.time() + 86400.0
        )
    config(
        roadmap={"implement": {"in_runner": True, "monitor_timeout_seconds": WATCH_SECONDS}},
        service={"github_app": {"token_repository": STAGE_REPO}},
    )
    programs.answer("git", ProcessAnswer(side_effect=git_for_real))
    programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=archive_effect),
    )
    programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(side_effect=docs_effect),
    )
    route_pull_status(api)
    if planned:
        api.route(
            "POST",
            f"/repos/{STAGE_REPO}/pulls",
            github_json(
                {"number": PULL, "html_url": f"https://example.com/pull/{PULL}"}, status=201
            ),
        )
    roadmap_store.seed_file(".github/labels.yml", LABELS_FILE)
    seed_staged(roadmap_store, record=not planned)
    for i in range(2, 5):
        roadmap_store.seed_issue(f"placeholder {i}")
    roadmap_store.seed_pull("staging PR", head_ref=BRANCH, draft=True)
    return JobWorld(repo, roadmap_store, api, programs, PullFake(api, programs, repo), clock)


@pytest.fixture
def job_world(
    staged_repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    clock: ClockFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> JobWorld:
    """The job in a runner with a Staged item: its branch is pushed, and its draft is open."""
    return _world(
        staged_repo, github_api_and_gh, config, clock, roadmap_store, monkeypatch, planned=False
    )


@pytest.fixture
def planned_world(
    stage_repo: StageRepo,
    app_slug: None,
    planned_tasks: str,
    plan_subject: str | None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    clock: ClockFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> JobWorld:
    """The job in a runner with a Planned item: the change is on `main`, and no branch and no
    pull request exist."""
    merge_plan(stage_repo, tasks=planned_tasks, subject=plan_subject)
    return _world(
        stage_repo, github_api_and_gh, config, clock, roadmap_store, monkeypatch, planned=True
    )
