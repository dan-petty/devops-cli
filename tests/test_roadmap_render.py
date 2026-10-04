"""`devops roadmap render` against the in-memory roadmap store (#739).

Render writes `docs/ROADMAP.md` from GitHub: the current release, the planned releases within
the horizon, then the backlog by priority. No case runs `gh` or opens a socket.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.config.constants import CONST_ROADMAP_RENDER_MARKER
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import FieldOption, FieldSpec, GitHubState, Item, ItemField

REPO = "example/roadmap"
REF = "release/v0.2.25"
PRIORITIES = ("P0-Critical", "P1-High", "P2-Medium", "P3-Low")

runner = CliRunner()


@pytest.fixture
def roadmap(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """Releases on both sides of the horizon, Items in each, and a backlog of mixed priority."""
    store = roadmap_store
    for name, options in (
        ("Status", ("New", "Ready", "In Progress", "In Review", "Done", "Blocked")),
        ("Priority", PRIORITIES),
        ("Value", ("High", "Medium", "Low")),
        ("Effort", ("Low", "Medium", "High")),
    ):
        store.seed_field(
            FieldSpec(
                name=name, single_select=True, options=tuple(FieldOption(name=o) for o in options)
            )
        )
    store.seed_file(".github/roadmap.toml", "board = 2\n", ref=REF)
    store.create_release("v0.2.24", state=GitHubState.CLOSED)
    store.create_release("v0.2.25", description="Multi-IDE MCP Scaffolding")
    for version in ("v0.2.26", "v0.2.27", "v0.3.0"):
        store.create_release(version)
    seeded = [
        ("shipped before", {"release": "v0.2.24", "state": GitHubState.CLOSED}, {}),
        (
            "feat(github): roadmap view",
            {"release": "v0.2.25"},
            {ItemField.STATUS: "In Progress", ItemField.PRIORITY: "P1-High"},
        ),
        (
            "fix(ci): delivered",
            {"release": "v0.2.25", "state": GitHubState.CLOSED},
            {
                ItemField.STATUS: "Done",
                ItemField.PRIORITY: "P0-Critical",
                ItemField.VALUE: "High",
                ItemField.EFFORT: "Low",
            },
        ),
        ("planned next", {"release": "v0.2.26"}, {ItemField.STATUS: "Ready"}),
        ("planned after", {"release": "v0.2.27"}, {}),
        ("beyond the horizon", {"release": "v0.3.0"}, {}),
        ("backlog p2 first", {}, {ItemField.PRIORITY: "P2-Medium"}),
        ("backlog unset", {}, {}),
        ("backlog p0", {}, {ItemField.PRIORITY: "P0-Critical"}),
        ("backlog p2 second", {}, {ItemField.PRIORITY: "P2-Medium"}),
    ]
    person = store.as_actor("alice")
    for title, issue, fields in seeded:
        number = store.seed_issue(title, on_board=True, **issue)  # type: ignore[arg-type]
        item = store.item(number)
        for board_field, value in fields.items():
            person.set_field(item, board_field, value)  # type: ignore[arg-type]
    return store


def _render(*flags: str) -> object:
    return runner.invoke(app, ["render", "--repo", REPO, "--ref", REF, *flags])


def test_the_file_starts_with_the_marker_and_lists_sections_in_order(
    roadmap: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    output = tmp_path / "ROADMAP.md"
    result = runner.invoke(app, ["render", "--repo", REPO, "--ref", REF, "--output", str(output)])
    lines = output.read_text(encoding="utf-8").splitlines()
    assert (
        result.exit_code,
        lines[0],
        [line for line in lines if line.startswith("## ")],
    ) == (
        0,
        CONST_ROADMAP_RENDER_MARKER,
        [
            "## Current release: v0.2.25 — Multi-IDE MCP Scaffolding",
            "## Planned release: v0.2.26",
            "## Planned release: v0.2.27",
            "## Backlog",
        ],
    )


def test_each_line_holds_number_title_and_fields_and_a_closed_item_is_checked(
    roadmap: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    output = tmp_path / "ROADMAP.md"
    runner.invoke(app, ["render", "--repo", REPO, "--ref", REF, "--output", str(output)])
    text = output.read_text(encoding="utf-8")
    current = text[text.index("## Current release") : text.index("## Planned release: v0.2.26")]
    assert [line for line in current.splitlines() if line.startswith("- ")] == [
        "- [x] #3 fix(ci): delivered — Status: Done · Priority: P0-Critical · Value: High · "
        "Effort: Low",
        "- [ ] #2 feat(github): roadmap view — Status: In Progress · Priority: P1-High · "
        "Value: — · Effort: —",
    ]


def test_the_backlog_is_sorted_by_priority_unset_last_then_by_number(
    roadmap: InMemoryRoadmapStore,
) -> None:
    text = _render("--plan").output  # type: ignore[attr-defined]
    backlog = text[text.index("## Backlog") :]
    assert [line.split(" — ")[0] for line in backlog.splitlines() if line.startswith("- ")] == [
        "- [ ] #9 backlog p0",
        "- [ ] #7 backlog p2 first",
        "- [ ] #10 backlog p2 second",
        "- [ ] #8 backlog unset",
    ]


def test_two_runs_on_the_same_state_write_identical_bytes(
    roadmap: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    for output in (first, second):
        runner.invoke(app, ["render", "--repo", REPO, "--ref", REF, "--output", str(output)])
    assert (first.read_bytes() == second.read_bytes(), first.stat().st_size > 0) == (True, True)


def test_plan_prints_the_file_and_writes_nothing(
    roadmap: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    output = tmp_path / "ROADMAP.md"
    result = runner.invoke(
        app, ["render", "--repo", REPO, "--ref", REF, "--output", str(output), "--plan"]
    )
    assert (result.exit_code, output.exists(), CONST_ROADMAP_RENDER_MARKER in result.output) == (
        0,
        False,
        True,
    )


def test_a_failed_read_leaves_the_file_untouched_and_exits_non_zero(
    unreadable_github_roadmap: list[list[str]], tmp_path: Path
) -> None:
    output = tmp_path / "ROADMAP.md"
    output.write_text("hand-written\n", encoding="utf-8")
    result = runner.invoke(app, ["render", "--repo", REPO, "--ref", REF, "--output", str(output)])
    assert (
        result.exit_code,
        output.read_text(encoding="utf-8"),
        len(unreadable_github_roadmap),
    ) == (
        1,
        "hand-written\n",
        1,
    )


def test_a_read_that_fails_after_the_config_also_writes_nothing(
    roadmap: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A board read failing part-way must not leave a half-rendered file behind."""
    output = tmp_path / "ROADMAP.md"
    output.write_text("hand-written\n", encoding="utf-8")

    def short_read() -> list[Item]:
        raise GitHubOperationError("Read 4 of 676 board #2 items, so the read is incomplete.")

    monkeypatch.setattr(roadmap, "backlog", short_read)
    result = runner.invoke(app, ["render", "--repo", REPO, "--ref", REF, "--output", str(output)])
    assert (result.exit_code, output.read_text(encoding="utf-8")) == (1, "hand-written\n")
