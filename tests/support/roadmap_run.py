"""The helpers that the `devops roadmap run` test files share: the store and clone fixtures, the
simulated git remote, the due-table stamps and the intake rows (#981).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, cast

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.intake.intake_model import (
    ModelProposal,
    ProposalRequest,
    UnusableProposalError,
)
from devops_cli.roadmap.run import (
    JobOutcome,
    JobRow,
    WebhookDelivery,
    build_stub_table,
    run_due_jobs,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ItemField,
    RoadmapStore,
    install_roadmap_store,
)
from devops_cli.server.service import TriggerBatch
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import API, GitHubApiFake, RunnerSession, github_json
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_jobs import due_job_runner

REPO = "example/roadmap"


# An open planning bucket: a milestone with any title, which no job reads as a version.
PLANNED = "2026-11-05"


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


OPENED = CONST_ROADMAP_INTAKE_BATCH_KEYS[0]


POLL_KEY = ("poll", "", "")


# The Priority that makes an issue an Item, as a person sets it.
PLACED = {ItemField.PRIORITY: "P2-Medium"}


run_intake_adapter = due_job_runner("intake")


run_metrics_adapter = due_job_runner("metrics")


@pytest.fixture
def seeded_store(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The roadmap every command opens, with a closed and an open milestone."""
    roadmap_store._roadmap.clock = lambda: NOW - timedelta(minutes=10)
    roadmap_store.seed_milestone("Docs pass", state=GitHubState.CLOSED)
    roadmap_store.seed_milestone(PLANNED)
    return roadmap_store


class SimulatedGit:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.remotes: dict[str, dict[str, Any]] = {}
        self.clones: dict[str, dict[str, Any]] = {}
        self.argvs: list[list[str]] = []
        self._commit_counter = 1

    def new_commit(self) -> str:
        sha = f"{self._commit_counter:040x}"
        self._commit_counter += 1
        return sha

    def serve_as(self, url: str, bare: Path) -> None:
        """Answer a clone or a fetch of `url`, such as the GitHub URL that a Service lane clones,
        with the bare remote `bare`."""
        self.remotes[url] = self.remotes[str(bare)]

    def _reachable(self, url: str) -> bool:
        """Whether a clone or a fetch reaches `url`: a served URL, or a bare remote that exists."""
        return url in self.remotes and (url.startswith("https://") or Path(url).exists())

    def make_bare_remote(self, tmp_path: Path, *, other_branch: str | None = None) -> Path:
        bare = tmp_path / "remote.git"
        bare.mkdir(parents=True, exist_ok=True)
        tip = self.new_commit()
        self.remotes[str(bare)] = {
            "branches": {"main": tip},
            "default_branch": "main",
            "tags": [],
            "files": {"main": {}},
        }
        if other_branch is not None:
            other_tip = self.new_commit()
            self.remotes[str(bare)]["branches"][other_branch] = other_tip
            self.remotes[str(bare)]["files"][other_branch] = {}
        return bare

    def advance_bare_remote(self, bare: Path, branch: str, *, onto: str = "main") -> str:
        new_tip = self.new_commit()
        remote = self.remotes[str(bare)]
        remote["branches"][branch] = new_tip
        remote["files"][branch] = dict(remote["files"].get(onto, {}))
        return new_tip

    def commit_file(
        self, bare: Path, branch: str, content: str, *, parent: str | None = None
    ) -> str:
        new_tip = self.new_commit()
        remote = self.remotes[str(bare)]
        remote["branches"][branch] = new_tip
        if branch not in remote["files"]:
            remote["files"][branch] = {}
        remote["files"][branch]["f.txt"] = content
        return new_tip

    def clone_head(self, clone_path: Path) -> tuple[str, str]:
        info = self.clones.get(str(clone_path))
        if info:
            return info["head"], info["branch"]
        return ("", "")

    def git_query(self, cwd: Path, *args: str) -> str:
        info = self.clones.get(str(cwd))
        if args and args[0] == "config":
            key = args[1]
            return info["config"].get(key, "") if info else ""
        if args and args[0] == "status":
            return ""
        if args and args[0] == "rev-parse":
            ref = args[1] if len(args) > 1 else "HEAD"
            remote = self.remotes.get(str(cwd))
            if remote:
                return remote["branches"].get(ref, "")
            if info:
                return info["head"]
        if args and args[0] == "tag":
            if len(args) >= 2:
                tag = args[1]
                remote = self.remotes.get(str(cwd))
                if remote:
                    remote["tags"].append(tag)
            return ""
        return ""

    def _op_clone(self, subcmd: list[str]) -> ProcessAnswer:
        url, target = (arg for arg in subcmd[1:] if not arg.startswith("-"))
        clone_dir = Path(target)
        if not self._reachable(url):
            return ProcessAnswer(
                returncode=128,
                stderr=f"fatal: repository '{url}' does not exist\n",
            )
        remote = self.remotes[url]
        (clone_dir / ".git").mkdir(parents=True, exist_ok=True)
        default_branch = remote["default_branch"] or "main"
        head_tip = remote["branches"].get(default_branch, "")
        self.clones[str(clone_dir)] = {
            "remote_url": url,
            "config": {},
            "branch": default_branch,
            "head": head_tip,
        }
        for fname, text in remote["files"].get(default_branch, {}).items():
            (clone_dir / fname).write_text(text, encoding="utf-8")
        return ProcessAnswer(returncode=0)

    def _op_fetch(self, clone_info: dict[str, Any] | None) -> ProcessAnswer:
        if not clone_info:
            return ProcessAnswer(returncode=0)
        remote_url = clone_info["remote_url"]
        if not self._reachable(remote_url):
            return ProcessAnswer(
                returncode=128,
                stderr=f"fatal: '{remote_url}' does not appear to be a git repository\nfatal: Could not read from remote repository.\n",
            )
        return ProcessAnswer(returncode=0)

    def _op_remote(self, subcmd: list[str], clone_info: dict[str, Any] | None) -> ProcessAnswer:
        if subcmd[1:] == ["set-head", "origin", "--auto"]:
            if not clone_info:
                return ProcessAnswer(returncode=0)
            remote = self.remotes.get(clone_info["remote_url"])
            if not remote or remote.get("default_branch") is None:
                return ProcessAnswer(
                    returncode=1,
                    stderr="fatal: Cannot determine remote HEAD\n",
                )
            return ProcessAnswer(returncode=0)
        return ProcessAnswer(returncode=0)

    def _op_symbolic_ref(self, clone_info: dict[str, Any] | None) -> ProcessAnswer:
        if not clone_info:
            return ProcessAnswer(stdout="refs/remotes/origin/main\n")
        remote = self.remotes.get(clone_info["remote_url"])
        default_branch = remote["default_branch"] if remote else "main"
        return ProcessAnswer(stdout=f"refs/remotes/origin/{default_branch}\n")

    def _op_checkout(
        self, cwd: Path, subcmd: list[str], clone_info: dict[str, Any] | None
    ) -> ProcessAnswer:
        branch = subcmd[3] if len(subcmd) > 3 else "main"
        if clone_info:
            remote = self.remotes.get(clone_info["remote_url"])
            if remote:
                tip = remote["branches"].get(branch, "")
                clone_info["branch"] = branch
                clone_info["head"] = tip
                for fname, text in remote["files"].get(branch, {}).items():
                    (cwd / fname).write_text(text, encoding="utf-8")
        return ProcessAnswer(returncode=0)

    def _op_reset(
        self, cwd: Path, subcmd: list[str], clone_info: dict[str, Any] | None
    ) -> ProcessAnswer:
        ref = subcmd[2] if len(subcmd) > 2 else ""
        branch = ref.split("/")[-1] if "/" in ref else "main"
        if clone_info:
            remote = self.remotes.get(clone_info["remote_url"])
            if remote:
                for fname, text in remote["files"].get(branch, {}).items():
                    (cwd / fname).write_text(text, encoding="utf-8")
        return ProcessAnswer(returncode=0)

    def _op_config(self, subcmd: list[str], clone_info: dict[str, Any] | None) -> ProcessAnswer:
        if len(subcmd) >= 3:
            key, val = subcmd[1], subcmd[2]
            if clone_info:
                clone_info["config"][key] = val
            return ProcessAnswer(returncode=0)
        if len(subcmd) == 2:
            key = subcmd[1]
            val = clone_info["config"].get(key, "") if clone_info else ""
            return ProcessAnswer(returncode=0, stdout=f"{val}\n")
        return ProcessAnswer(returncode=0)

    def _op_tag(
        self, cwd: Path, subcmd: list[str], clone_info: dict[str, Any] | None
    ) -> ProcessAnswer:
        if "-l" in subcmd:
            remote = self.remotes.get(str(cwd)) or (
                self.remotes.get(clone_info["remote_url"]) if clone_info else None
            )
            tags = remote["tags"] if remote else []
            out_lines = [f"{tag}|2026-10-01 00:00:00 +0000" for tag in tags]
            out = "\n".join(out_lines) + ("\n" if out_lines else "")
            return ProcessAnswer(returncode=0, stdout=out)
        if len(subcmd) >= 2:
            tag = subcmd[1]
            remote = self.remotes.get(str(cwd))
            if remote:
                remote["tags"].append(tag)
            return ProcessAnswer(returncode=0)
        return ProcessAnswer(returncode=0)

    def _op_rev_parse(self, clone_info: dict[str, Any] | None) -> ProcessAnswer:
        if clone_info:
            return ProcessAnswer(
                returncode=0, stdout=f"{clone_info['head']}\n{clone_info['branch']}\n"
            )
        return ProcessAnswer(returncode=0, stdout="1111111111111111111111111111111111111111\n")

    def answer_call(self, call: ProcessCall) -> ProcessAnswer:
        argv = list(call.argv)
        self.argvs.append(argv)
        if not argv or Path(argv[0]).name != "git":
            return ProcessAnswer()

        if len(argv) > 2 and argv[1] == "-C":
            cwd = Path(argv[2])
            subcmd = argv[3:]
        else:
            cwd = Path(call.cwd) if call.cwd else Path.cwd()
            subcmd = argv[1:]

        if not subcmd:
            return ProcessAnswer()

        clone_info = self.clones.get(str(cwd))
        handlers: dict[str, Callable[[], ProcessAnswer]] = {
            "clone": lambda: self._op_clone(subcmd),
            "fetch": lambda: self._op_fetch(clone_info),
            "remote": lambda: self._op_remote(subcmd, clone_info),
            "symbolic-ref": lambda: self._op_symbolic_ref(clone_info),
            "checkout": lambda: self._op_checkout(cwd, subcmd, clone_info),
            "reset": lambda: self._op_reset(cwd, subcmd, clone_info),
            "config": lambda: self._op_config(subcmd, clone_info),
            "tag": lambda: self._op_tag(cwd, subcmd, clone_info),
            "rev-parse": lambda: self._op_rev_parse(clone_info),
            "log": lambda: ProcessAnswer(returncode=0, stdout=""),
            "status": lambda: ProcessAnswer(returncode=0, stdout=""),
        }
        handler = handlers.get(subcmd[0])
        return handler() if handler else ProcessAnswer(returncode=0)


CURRENT_SIM: list[SimulatedGit] = []


@pytest.fixture
def git_sim(tmp_path: Path, git_fake: GitFake) -> Iterator[SimulatedGit]:
    sim = SimulatedGit(tmp_path)
    CURRENT_SIM.append(sim)
    git_fake.answer(
        lambda call: bool(call.argv and Path(call.argv[0]).name == "git"), sim.answer_call
    )
    try:
        yield sim
    finally:
        CURRENT_SIM.clear()


def git_in(cwd: Path, *args: str) -> str:
    sim = CURRENT_SIM[0] if CURRENT_SIM else None
    return sim.git_query(cwd, *args) if sim else ""


def bare_remote(tmp_path: Path, *, other_branch: str | None = None) -> Path:
    return CURRENT_SIM[0].make_bare_remote(tmp_path, other_branch=other_branch)


def serve_as(url: str, bare: Path) -> None:
    CURRENT_SIM[0].serve_as(url, bare)


def commit_to_bare(bare: Path, branch: str, content: str, *, parent: str | None = None) -> str:
    return CURRENT_SIM[0].commit_file(bare, branch, content, parent=parent)


def head_of_clone(clone_path: Path) -> tuple[str, str]:
    return CURRENT_SIM[0].clone_head(clone_path)


@pytest.fixture
def child_argvs(
    monkeypatch: pytest.MonkeyPatch, github_api: GitHubApiFake, git_sim: SimulatedGit
) -> list[list[str]]:
    """Answer the session's login lookup through the session fake and record git argvs."""
    github_api.route("GET", "/user", github_json({"login": "test-bot"}))
    github_api.route("GET", "/users/test-bot", github_json({"id": 4242, "login": "test-bot"}))
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 60.0
    )
    return git_sim.argvs


REPO_DIR = Path("roadmap") / "example" / "roadmap"


TWENTY_MINUTES_AGO = NOW - timedelta(minutes=20)


def stamp_successes(tmp_path: Path, **last_success: datetime) -> None:
    """Write each job's last success to the repository's `schedule.json`, and nothing else."""
    path = tmp_path / REPO_DIR / "schedule.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    stamps = {job: at.isoformat() for job, at in last_success.items()}
    path.write_text(json.dumps(stamps), encoding="utf-8")


def recorded(
    ran: list[str], name: str, job: Callable[..., JobOutcome] | None = None
) -> Callable[..., JobOutcome]:
    """A job that adds `name` to `ran` and then runs `job`, or does nothing when `job` is None."""

    def run(**kwargs: Any) -> JobOutcome:
        ran.append(name)
        return job(**kwargs) if job else JobOutcome()

    return run


def read_schedule(tmp_path: Path) -> dict[str, str]:
    """The repository's `schedule.json`."""
    return cast(
        dict[str, str],
        json.loads((tmp_path / REPO_DIR / "schedule.json").read_text(encoding="utf-8")),
    )


def poll_round(
    store: RoadmapStore,
    tmp_path: Path,
    *,
    now: datetime = NOW,
    table: Sequence[JobRow] | None = None,
    batch: dict[tuple[str, str, str], int] | None = None,
) -> tuple[str, ...]:
    """The jobs one round runs at `now`, on the Service's poll unless `batch` says otherwise."""
    return run_due_jobs(
        REPO,
        store,
        batch={POLL_KEY: 1} if batch is None else batch,
        table=build_stub_table() if table is None else table,
        data_dir=tmp_path,
        now=now,
    )


# ── Intake's limit (#1360) ────────────────────────────────────────────────────


@dataclass
class IntakeModel:
    """Embeds every text alike and proposes a P2 feature for every candidate but those titled
    in `unusable`, for which it has no usable proposal; `asked` holds each title it judged."""

    unusable: frozenset[str] = frozenset()
    asked: list[str] = field(default_factory=list)
    proposals: Mapping[str, ModelProposal] = field(default_factory=dict)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def propose(self, request: ProposalRequest) -> ModelProposal:
        self.asked.append(request.title)
        if request.title in self.unusable:
            raise UnusableProposalError("no proposal fits")
        if request.title in self.proposals:
            return self.proposals[request.title]
        return ModelProposal(
            type="type/feature",
            type_reason="it adds a capability.",
            priority="P2-Medium",
            priority_reason="useful, not urgent.",
            value="Medium",
            value_reason="it helps maintainers.",
            effort="Low",
            effort_reason="one module.",
        )


@dataclass
class Clock:
    now: datetime = NOW - timedelta(minutes=10)

    def __call__(self) -> datetime:
        return self.now


def make_candidates(count: int) -> tuple[InMemoryRoadmapStore, Clock, list[str]]:
    """A roadmap with an open milestone and `count` open issues with no Priority, titled
    `candidate 1` up: each one intake's candidate."""
    clock = Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    titles = [f"candidate {n}" for n in range(1, count + 1)]
    for title in titles:
        store.seed_issue(title)
    return store, clock, titles


def intake_table(model: IntakeModel, ran: list[str]) -> tuple[JobRow, ...]:
    """The due table with the Service's own intake over `model`, each run's name added to
    `ran`."""
    intake = partial(run_intake_adapter, model=model)
    return build_stub_table({"intake": recorded(ran, "intake", intake)})


# ── On the GitHub store, at the `gh` process edge (#1361) ─────────────────────


def labeled_changes(count: int, actor: str) -> list[dict[str, Any]]:
    """`count` label events by `actor` on issues #1.., newest first, in no milestone."""
    return [
        {
            "event": "labeled",
            "created_at": (NOW - timedelta(seconds=10 + n)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actor": {"login": actor},
            "issue": {"number": n + 1, "milestone": None},
            "label": {"name": "scope/cli"},
        }
        for n in range(count)
    ]


@pytest.fixture
def roadmap_bot(web: WebFake) -> None:
    """The Service is logged in as `roadmap-bot`: GitHub answers `GET /user` with that login, and
    the quota is fresh, so pacing never runs `gh api rate_limit`."""
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    web.page(
        f"{API}/user",
        json.dumps({"login": "roadmap-bot"}),
        headers={"content-type": "application/json"},
    )


DEFAULT_JOB_NAMES = (
    "metrics",
    "implement",
    "stage_ready",
    "stage",
    "release_comments",
    "github_status",
    "cloudflare_status",
    "pr_conflicts",
    "intake",
    "refine",
)


POLL = TriggerBatch(repo=REPO, counts={POLL_KEY: 1}, first_at=NOW, last_at=NOW)


def service_github(events: list[dict[str, Any]]) -> GitHubFake:
    """The repository `service_job` opens, with three Items, the labels file intake reads, and
    `events` dated now."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    github = GitHubFake(
        REPO,
        milestones=[{"number": 26, "title": PLANNED, "state": "open"}],
        files={".github/labels.yml": Path(".github/labels.yml").read_text(encoding="utf-8")},
        events=[event | {"created_at": now} for event in events],
    )
    for number in range(1, 4):
        github.seed_issue(number, labels=("priority/p2-medium", "status/ready"))
    return github


def serve_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gh: Callable[..., Any], *, stamped: bool = True
) -> None:
    """`service_job` opens its stores over `gh`, logged in as `roadmap-bot`, with every job of
    the default table run a minute ago, so a poll runs only what changes since then make due.
    Unstamped, no job has run yet, so each row with a first run due is due on the first poll."""
    minute_ago = datetime.now(UTC) - timedelta(minutes=1)
    if stamped:
        stamp_successes(tmp_path, **dict.fromkeys(DEFAULT_JOB_NAMES, minute_ago))
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    install_roadmap_store(
        lambda repo, **_: GitHubRoadmapStore(repo, runner=gh, session=RunnerSession(gh))
    )


# ── The Service's status and model lanes (#1532) ──────────────────────────────


def lane_table(
    rows: Sequence[JobRow], *, needs_clone: bool = False, **runners: Callable[..., JobOutcome]
) -> tuple[JobRow, ...]:
    """A lane's rows, in its order, each running its stub from `runners` or doing nothing, with a
    clone only when `needs_clone`."""
    return tuple(
        replace(
            row,
            runner=runners.get(row.name, lambda **_: JobOutcome()),
            needs_clone=needs_clone and row.needs_clone,
        )
        for row in rows
    )


# ── Scoped updates (ADR 0017) ─────────────────────────────────────────────────


def webhook_delivery(action: str, number: int, *, event: str = "issues") -> WebhookDelivery:
    """What a webhook delivery of `event` with `action` about issue `number` carries."""
    return WebhookDelivery(repo=REPO, event=event, action=action, number=number)
