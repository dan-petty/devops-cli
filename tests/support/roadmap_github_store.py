"""The helpers that the GitHub roadmap store test files share: the recorded GitHub replies, the
recording `gh` runner and the builders of stores and issues (#1335).
"""

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from typing import Any

from devops_cli.github.session import get_github_session
from devops_cli.roadmap.stores.github_store import (
    GitHubRoadmapStore,
)
from devops_cli.roadmap.stores.store import (
    Item,
    RoadmapStore,
)
from tests.support.fakes.github import (
    RunnerSession,
)
from tests.support.fakes.github_repository import GitHubFake
from tests.support.paths import FIXTURES

ROADMAP_FIXTURES = FIXTURES / "roadmap"


REPO = "dan-petty/devops-cli"


def recorded(name: str) -> Any:
    return json.loads((ROADMAP_FIXTURES / name).read_text(encoding="utf-8"))


MILESTONES = recorded("milestones.json")


ISSUES_IN_MILESTONE = recorded("issues-milestone-43.json")


OPEN_ISSUES = recorded("issues-open.json")


EVENTS = recorded("issue-events.json")


LISTING_MILESTONES = f"repos/{REPO}/milestones?state=all&per_page=100"


def labeled(payload: dict[str, Any], *labels: str, **changes: Any) -> dict[str, Any]:
    """A copy of a recorded issue with `labels` added to its own, and `changes` made."""
    copy: dict[str, Any] = deepcopy(payload)
    copy["labels"] = [*copy["labels"], *({"name": label} for label in labels)]
    return {**copy, **changes}


class RecordedGh:
    """A gh runner that answers each command from recorded output and keeps every call.

    A reply that is a function is called with the command's argv, so a write can change what a
    later read returns.
    """

    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = replies
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        command = " ".join(args)
        key = next((key for key in self.replies if key in command), None)
        assert key is not None, f"no recorded reply for: {command}"
        reply = self.replies[key]
        reply = reply(args) if callable(reply) else reply
        returncode, output = reply if isinstance(reply, tuple) else (0, reply)
        text = output if isinstance(output, str) else json.dumps(output)
        return subprocess.CompletedProcess(args, returncode, text, "" if returncode == 0 else text)

    @property
    def writes(self) -> list[list[str]]:
        """The calls that change GitHub."""
        return [args for args, _ in self.calls if {"POST", "PATCH", "DELETE"} & set(args)]


def recorded_store(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, RecordedGh]:
    runner = RecordedGh(replies)
    return GitHubRoadmapStore(REPO, runner=runner, session=RunnerSession(runner)), runner


def fake_store(github: GitHubFake) -> GitHubRoadmapStore:
    """The store over the whole repository `github` fakes at the `gh` process edge."""
    return GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))


def seeded(**issues: tuple[str, ...]) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """A repository whose issue `#<n>`, keyed `i<n>`, holds the labels given, and its store."""
    github = GitHubFake(REPO)
    for key, labels in issues.items():
        github.seed_issue(int(key.removeprefix("i")), labels=labels, body="Text")
    return github, fake_store(github)


def read(store: RoadmapStore, number: int) -> Item:
    found = store.item(number)
    assert found is not None
    return found


# ── Failed reads ──────────────────────────────────────────────────────────────


def over_github(replies: dict[str, Any] | None = None) -> tuple[GitHubRoadmapStore, RecordedGh]:
    """The store whose REST listings the process's GitHub session reads from the `github_api`
    fake, and whose gh commands `replies` answer (#983)."""
    runner = RecordedGh(replies or {})
    return GitHubRoadmapStore(REPO, runner=runner, session=get_github_session()), runner


# ── What intake reads and writes (#742) ───────────────────────────────────────


def issue_payload(number: int, **changes: Any) -> dict[str, Any]:
    """The recorded open issue #917 as issue `number`, with its node id."""
    return {**OPEN_ISSUES[1], "number": number, "node_id": f"I_kw{number}", **changes}
