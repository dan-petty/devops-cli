"""Unit tests for `devops roadmap return`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.return_item import (
    apply_return,
    dry_run_return,
    plan_return,
    render_return_plan,
)
from devops_cli.roadmap.store import ItemField

REPO = "owner/repo"
BOARD_OPTIONS = {
    ItemField.STATUS: ("New", "Ready", "In Progress", "Blocked", "Done"),
    ItemField.PRIORITY: ("P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
}


def test_plan_return_and_apply_return_in_memory_store() -> None:
    """plan_return validates item exists and apply_return comments and moves card to New."""
    store = InMemoryRoadmapStore(repo=REPO, board_options=BOARD_OPTIONS)
    num = store.seed_issue("Unworkable item", body="Premise is flawed", on_board=True)
    item = store.item(num)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")

    plan = plan_return(store, num, "Upstream library removed this API.", REPO)
    assert (plan.item_number, plan.title, plan.target_status) == (
        num,
        "Unworkable item",
        "New",
    )
    rendered = render_return_plan(plan)
    assert f"Item #{num}: Unworkable item" in rendered
    assert "Target Status: New" in rendered
    assert "Upstream library removed this API." in rendered

    apply_return(store, plan)
    updated_item = store.item(num)
    assert updated_item is not None
    comments = store.comments_on(num)
    assert (updated_item.status, comments) == (
        "New",
        ["Upstream library removed this API."],
    )


def test_dry_run_return_produces_requests() -> None:
    """dry_run_return produces planned read and write requests without network."""
    reads, writes = dry_run_return(REPO, 42)
    assert (len(reads) > 0, len(writes) >= 2) == (True, True)


def test_roadmap_return_cli_dry_run() -> None:
    """CLI return --dry-run prints request plan without modifying state."""
    runner = CliRunner()
    res = runner.invoke(
        roadmap_app,
        ["return", "42", "--repo", REPO, "--comment", "Flawed premise", "--dry-run"],
    )
    assert (res.exit_code, "Dry run: no request was made." in res.stdout) == (0, True)


def test_roadmap_return_cli_plan_mode() -> None:
    """CLI return without --confirm prints preview plan only."""
    store = InMemoryRoadmapStore(repo=REPO, board_options=BOARD_OPTIONS)
    num = store.seed_issue("Flawed feature", body="Cannot work", on_board=True)
    item = store.item(num)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "In Progress")

    runner = CliRunner()
    with patch("devops_cli.commands.roadmap._open_roadmap", return_value=(REPO, None, store)):
        res = runner.invoke(
            roadmap_app,
            ["return", str(num), "--repo", REPO, "--comment", "Flawed premise"],
        )
        assert (
            res.exit_code,
            "Plan only: pass --confirm to apply." in res.stdout,
            store.item(num).status if store.item(num) else None,
        ) == (0, True, "In Progress")


def test_roadmap_return_cli_confirm(tmp_path: Path) -> None:
    """CLI return --confirm posts comment and moves item to New."""
    store = InMemoryRoadmapStore(repo=REPO, board_options=BOARD_OPTIONS)
    num = store.seed_issue("Flawed feature", body="Cannot work", on_board=True)
    item = store.item(num)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "In Progress")

    comment_file = tmp_path / "evidence.txt"
    comment_file.write_text("Detailed evidence from upstream docs.", encoding="utf-8")

    runner = CliRunner()
    with patch("devops_cli.commands.roadmap._open_roadmap", return_value=(REPO, None, store)):
        res = runner.invoke(
            roadmap_app,
            [
                "return",
                str(num),
                "--repo",
                REPO,
                "--comment-file",
                str(comment_file),
                "--confirm",
            ],
        )
        updated = store.item(num)
        assert (
            res.exit_code,
            updated.status if updated else None,
            store.comments_on(num),
        ) == (0, "New", ["Detailed evidence from upstream docs."])


def test_roadmap_return_cli_missing_comment() -> None:
    """CLI return fails if neither --comment nor --comment-file is provided."""
    runner = CliRunner()
    res = runner.invoke(roadmap_app, ["return", "42", "--repo", REPO])
    assert res.exit_code != 0
