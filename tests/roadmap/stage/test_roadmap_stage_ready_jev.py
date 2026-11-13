"""The Jev completeness check in the row `stage_ready` (#4308).

GitHub's REST API and `gh` are faked at their edges, and the gateway route of Jev answers through the same fake. The
check only holds a draft: with it on, a green draft is marked ready only when Jev does not doubt it. The diff that Jev
reads is the compare of the base branch and the head commit (#5388): the payload `base.sha` of each draft here is a
stale commit, and the compare from it holds the files of other changes.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from devops_cli.roadmap.stage.stage_ready import mark_stage_ready
from devops_cli.roadmap.stores.store import Item, StageRecordKey
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    github_text,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import PASS, PULL, seed_staged
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

GATEWAY = "http://example.com:4000/v1"
ROUTE = f"{GATEWAY}/systemone"
HEAD = "a" * 40
NEW_HEAD = "b" * 40
STALE_BASE = "c" * 40
DIFF = "diff --git a/openspec/changes/x/tasks.md b/openspec/changes/x/tasks.md\n+- [ ] 1.1 Keep\n"
OTHER_CHANGE = "openspec/changes/archive/2026-11-12-4000-other/tasks.md"
STALE_DIFF = f"{DIFF}diff --git a/{OTHER_CHANGE} b/{OTHER_CHANGE}\n+- [x] 1.1 Other\n"
DIFF_MEDIA_TYPE = "application/vnd.github.diff"


class _Ready:
    """The `gh pr ready` calls that the fake `gh` receives."""

    def __init__(self, gh: ProcessFake) -> None:
        self.calls: list[tuple[str, ...]] = []
        gh.answer(lambda call: call.argv[1:3] == ("pr", "ready"), ProcessAnswer(side_effect=self))

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        self.calls.append(call.argv[1:])
        return subprocess.CompletedProcess(call.argv, 0, stdout="", stderr="")


@pytest.fixture
def api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    return github_api_and_gh[0]


@pytest.fixture
def ready(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> _Ready:
    return _Ready(github_api_and_gh[1])


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def jev_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """The setting on, and the gateway that Jev answers on."""
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_JEV_COMPLETENESS", "true")
    monkeypatch.setenv("DEVOPS_CLI_AI_PROVIDER", "gateway")
    monkeypatch.setenv("DEVOPS_CLI_AI_GATEWAY_URL", GATEWAY)


def _pull(api: GitHubApiFake, head: str = HEAD) -> None:
    """The reads of the draft: its status twice, and the diff of its head since the merge base
    with its base branch. The payload `base.sha` is a stale commit, and the compare from it holds
    the files of another change, as GitHub answers after a merge moved the merge base."""
    payload = github_json(
        {
            "state": "open",
            "draft": True,
            "head": {"sha": head},
            "base": {"ref": "main", "sha": STALE_BASE},
            "labels": [],
        }
    )
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", payload)
    for base, diff in (("main", DIFF), (STALE_BASE, STALE_DIFF)):
        api.route(
            "GET",
            f"/repos/{STAGE_REPO}/compare/{base}...{head}",
            github_text(diff, media_type=DIFF_MEDIA_TYPE),
        )
    path = f"/repos/{STAGE_REPO}/commits/{head}/check-runs?per_page=100"
    api.route("GET", path, github_json({"total_count": 1, "check_runs": [PASS]}))
    api.route(
        "POST", f"/repos/{STAGE_REPO}/issues/{PULL}/comments", github_json({"id": 1}, status=201)
    )


def _jev(api: GitHubApiFake, noul: float, tests: float = 2.0) -> None:
    """Jev's answer to the one request: one Noul value for the one criterion, and a score."""
    levels = {str(level): 0.0 for level in range(4)}
    levels[str(round(tests))] = 1.0
    answers = {
        "criterion_1": {"type": "noul", "noul": noul, "confidence": 0.9},
        "tests": {
            "type": "score",
            "score": float(round(tests)),
            "probabilities": levels,
            "confidence": 0.9,
        },
    }
    api.route(
        "POST",
        ROUTE,
        github_json(
            {
                "model": "typesafe/jev-1.14",
                "answers": answers,
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }
        ),
    )


def _jev_requests(api: GitHubApiFake) -> int:
    return sum(1 for sent in api.sent if str(sent.url) == ROUTE)


def _jev_diffs(api: GitHubApiFake) -> list[str]:
    """The diff in the state of each request to Jev."""
    return [
        json.loads(sent.content)["state"]["diff"] for sent in api.sent if str(sent.url) == ROUTE
    ]


def _comments(api: GitHubApiFake) -> list[str]:
    return [
        json.loads(sent.content)["body"]
        for sent in api.sent
        if sent.method == "POST" and sent.url.path.endswith(f"issues/{PULL}/comments")
    ]


def _item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def test_with_the_setting_off_jev_is_never_asked(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    seed_staged(store)
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{PULL}",
        github_json({"state": "open", "draft": True, "head": {"sha": HEAD}, "labels": []}),
    )
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [PASS]}),
    )

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (len(applied.marked), _jev_requests(api), len(ready.calls)) == (1, 0, 1)


@pytest.mark.usefixtures("jev_on")
def test_a_pass_of_jev_leaves_the_decision_to_the_checks_and_marks_the_green_draft(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    number = seed_staged(store)
    _pull(api)
    _jev(api, noul=0.95)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, _jev_requests(api), len(ready.calls), _comments(api)) == (
        (number,),
        1,
        1,
        [],
    )
    assert _item(store, number).job_record.get(StageRecordKey.JEV) is None


@pytest.mark.usefixtures("jev_on")
def test_jev_reads_the_diff_of_the_draft_since_the_merge_base_with_its_base_branch(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    """The payload `base.sha` is not the merge base: the diff is the compare of the base branch
    and the head commit, and the round reads no diff of the pulls endpoint (#5388)."""
    seed_staged(store)
    _pull(api)
    _jev(api, noul=0.95)

    mark_stage_ready(store, repo=STAGE_REPO)

    pulls_diffs = [
        sent
        for sent in api.sent
        if sent.url.path == f"/repos/{STAGE_REPO}/pulls/{PULL}"
        and sent.headers.get("accept") == DIFF_MEDIA_TYPE
    ]
    assert (_jev_diffs(api), pulls_diffs) == ([DIFF], [])


@pytest.mark.usefixtures("jev_on")
def test_a_criterion_in_doubt_keeps_the_draft_a_draft_with_one_note_and_no_second_request(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    number = seed_staged(store)
    _pull(api)
    _jev(api, noul=0.1)

    first = mark_stage_ready(store, repo=STAGE_REPO)
    second = mark_stage_ready(store, repo=STAGE_REPO)

    notes = _comments(api)
    assert (first.waiting, second.waiting, _jev_requests(api), ready.calls, len(notes)) == (
        (number,),
        (number,),
        1,
        [],
        1,
    )
    assert "The job keeps every comment." in notes[0]
    assert _item(store, number).job_record[StageRecordKey.JEV] == f"{HEAD}:held"


@pytest.mark.usefixtures("jev_on")
def test_a_new_head_commit_is_checked_again(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    number = seed_staged(store)
    _pull(api)
    _jev(api, noul=0.1)
    mark_stage_ready(store, repo=STAGE_REPO)
    _pull(api, head=NEW_HEAD)
    _jev(api, noul=0.9)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, _jev_requests(api), len(ready.calls)) == ((number,), 2, 1)
    assert _item(store, number).job_record.get(StageRecordKey.JEV) is None


@pytest.mark.usefixtures("jev_on")
def test_an_error_of_jev_holds_the_draft_posts_one_note_and_asks_again_next_round(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    number = seed_staged(store)
    _pull(api)
    api.route("POST", ROUTE, github_json({"error": "boom"}, status=500))

    first = mark_stage_ready(store, repo=STAGE_REPO)
    _pull(api)
    second = mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        first.waiting,
        second.waiting,
        _jev_requests(api),
        ready.calls,
        len(_comments(api)),
    ) == (
        (number,),
        (number,),
        2,
        [],
        1,
    )
    assert _item(store, number).job_record[StageRecordKey.JEV] == f"{HEAD}:error"


@pytest.mark.usefixtures("jev_on")
def test_the_check_never_marks_a_draft_ready_when_checks_failed(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    """A draft whose checks did not pass is not asked about: the check runs after the checks."""
    seed_staged(store)
    _pull(api)
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [{**PASS, "conclusion": "failure"}]}),
    )
    _jev(api, noul=0.99)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, _jev_requests(api), ready.calls) == ((), 0, [])
