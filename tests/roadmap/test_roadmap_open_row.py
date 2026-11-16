"""The row `open` of the Service opens the pull request of a pushed delivery branch that has none,
in the mode of `roadmap.open.mode` (#5974)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.github.release_title import RELEASE_CONFIG_PATH
from devops_cli.roadmap.open_row import delivery_why, open_candidates, run_open_round
from devops_cli.roadmap.run import STATUS_LANE_ROWS
from devops_cli.roadmap.stores.store import ImplementRecordKey, ItemField, StageRecordKey
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")

OPEN_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "open")
LABELS_YML = (
    '- name: "scope/roadmap"\n  color: "ededed"\n'
    '- name: "type/test"\n  color: "ededed"\n'
    '- name: "type/bug"\n  color: "ededed"\n'
)
ITEM_TITLE = "test(roadmap): the Planned limit stays out of refine"
CHANGE = "openspec/changes/archive/2026-11-16-{number}-the-planned-limit"
WHY = "The planning threshold must not stop an item from going from New to Ready."


def _store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    store.seed_file(".github/labels.yml", LABELS_YML, ref="main")
    store.seed_file(
        RELEASE_CONFIG_PATH, Path(RELEASE_CONFIG_PATH).read_text(encoding="utf-8"), ref="main"
    )
    return store


def _item(store: InMemoryRoadmapStore, branch: str | None, **marks: str) -> int:
    number = store.seed_issue(ITEM_TITLE, fields={ItemField.PRIORITY: "P2-Medium"})
    item = store.item(number)
    assert item is not None
    record = {ImplementRecordKey.BRANCH: branch} if branch else {}
    store.set_marks(item, {**record, **marks})
    return number


def _push(stage_repo: StageRepo, branch: str) -> str:
    """Push `branch` with one commit of runtime code to `origin`, and give its head."""
    stage_repo.git("switch", "-q", "-c", branch)
    target = stage_repo.clone / "src" / "devops_cli" / "sample.py"
    target.write_text("def keep(comments):\n    return comments\n", encoding="utf-8")
    stage_repo.git("commit", "-q", "-am", "change runtime code")
    stage_repo.git("push", "-q", "origin", branch)
    stage_repo.git("switch", "-q", "main")
    return stage_repo.git("rev-parse", branch)


def test_the_row_follows_stage_needs_a_clone_is_due_on_a_first_run_and_starts_in_plan() -> None:
    from devops_cli.config.settings import RoadmapConfig

    names = [row.name for row in STATUS_LANE_ROWS]

    assert (
        names[names.index("stage") + 1],
        OPEN_ROW.needs_clone,
        OPEN_ROW.first_run_due,
        RoadmapConfig().open.mode,
    ) == ("open", True, True, "plan")


def test_a_candidate_is_the_recorded_pushed_branch_of_a_free_item_with_no_pull_request() -> None:
    store = _store()
    free = _item(store, "test/1-free")
    _item(store, "test/2-not-pushed")
    with_pull = _item(store, "test/3-with-pull")
    store.seed_pull("a draft", head_ref="test/3-other-branch")
    _item(store, "test/5-orphan", **{StageRecordKey.PENDING: '{"branch": "test/5-orphan"}'})
    _item(store, "test/6-job", **{ImplementRecordKey.JOB: "runner-6"})
    _item(store, "test/7-stopped", **{ImplementRecordKey.STOPPED: "a check failed"})
    _item(store, None)
    heads = "\n".join(
        f"{index:040x}\trefs/heads/{branch}"
        for index, branch in enumerate(
            (
                "test/1-free",
                "test/3-with-pull",
                "test/5-orphan",
                "test/6-job",
                "test/7-stopped",
                "test/8-a-person",
            ),
            start=1,
        )
    )

    found = open_candidates(store, heads)

    assert [(c.item.number, c.branch, c.sha) for c in found] == [(free, "test/1-free", f"{1:040x}")]
    assert with_pull == 3


def test_mode_off_reads_nothing(
    stage_repo: StageRepo, github_api: GitHubApiFake, config: Callable[..., Path]
) -> None:
    store = _store()
    _item(store, "test/1-free")
    config(roadmap={"open": {"mode": "off"}})

    OPEN_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert github_api.requested == []


def test_mode_plan_logs_the_branch_and_writes_nothing(
    stage_repo: StageRepo, github_api: GitHubApiFake, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store()
    number = _item(store, "test/1-the-planned-limit")
    sha = _push(stage_repo, "test/1-the-planned-limit")
    github_api.route(
        "GET", f"/repos/{STAGE_REPO}/commits/{sha}/pulls?per_page=100", github_json([])
    )

    with caplog.at_level(logging.INFO):
        result = run_open_round(
            store, repo=STAGE_REPO, source=stage_repo.clone, mode="plan", base="main"
        )

    assert [c.item.number for c in result.candidates] == [number]
    assert [r for r in github_api.requested if not r.startswith("GET")] == []
    assert any("mode plan" in record.getMessage() for record in caplog.records)


def test_a_head_that_had_a_pull_request_is_not_opened_again(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    store = _store()
    _item(store, "test/1-the-planned-limit")
    sha = _push(stage_repo, "test/1-the-planned-limit")
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{sha}/pulls?per_page=100",
        github_json([{"number": 77, "state": "closed", "merged_at": None, "head": {"sha": sha}}]),
    )

    result = run_open_round(store, repo=STAGE_REPO, source=stage_repo.clone, mode="on", base="main")

    assert (result.candidates, result.opened) == ([], [])


def test_mode_on_opens_a_test_item_with_a_runtime_diff_under_a_type_that_ships(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """The test of #5974: the pushed branch changes runtime code, and the item has the type
    `test`. The row opens a draft whose type ships a release, and whose body closes the item and
    names the archived change."""
    store = _store()
    number = _item(store, "test/1-the-planned-limit")
    sha = _push(stage_repo, "test/1-the-planned-limit")
    change = CHANGE.format(number=number)
    store.seed_file(f"{change}/proposal.md", f"# Proposal\n\n## Why\n{WHY}\n", ref=sha)
    github_api.route(
        "GET", f"/repos/{STAGE_REPO}/commits/{sha}/pulls?per_page=100", github_json([])
    )
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/compare/main...{sha}?per_page=1",
        github_json(
            {
                "merge_base_commit": {"sha": "base"},
                "files": [
                    {"filename": "src/devops_cli/sample.py", "status": "modified"},
                    {"filename": f"{change}/proposal.md", "status": "added"},
                ],
            }
        ),
    )
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls?head=example:test/1-the-planned-limit&state=open",
        github_json([]),
    )
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json(
            {"number": 900, "html_url": "https://github.com/example/roadmap/pull/900"}, status=201
        ),
    )

    result = run_open_round(store, repo=STAGE_REPO, source=stage_repo.clone, mode="on", base="main")

    sent = next(r for r in github_api.sent if r.method == "POST")
    payload = json.loads(sent.content)
    assert result.opened == [900]
    assert (payload["title"], payload["head"], payload["draft"]) == (
        "fix(roadmap): the Planned limit stays out of refine",
        "test/1-the-planned-limit",
        True,
    )
    assert payload["body"] == f"{WHY}\n\nCloses #{number}\n\nChange: `{change}/`"


def test_the_why_falls_back_to_the_item_summary() -> None:
    assert (
        delivery_why(None, ITEM_TITLE, 200),
        delivery_why("## Why\nFixes #12 and more.\n", ITEM_TITLE, 200),
        delivery_why(f"## Why\n{WHY}\n", ITEM_TITLE, 10),
        delivery_why(f"## Why\n{WHY}\n", ITEM_TITLE, 200),
    ) == (
        "the Planned limit stays out of refine",
        "the Planned limit stays out of refine",
        "the Planned limit stays out of refine",
        WHY,
    )
