"""`devops roadmap migrate` against the in-memory roadmap store (#739).

The fixture is a small roadmap with every case the migration handles: a range heading and a
`####` heading, entries linked by heading and by exact title, an unlinked P0 entry beyond the
planning horizon, an entry whose issue is closed, a rejected matrix row and a matrix row with
Value and Effort. The board has Todo, Backlog and Category; one open issue has a `status/ready`
label and no Status; there are two epics, and milestones for the current release, two planned
releases and one later release. No case runs `gh` or opens a socket.

GitHub's API can't keep an option's id, so the owner renames Backlog to New and adds Blocked in
the board's field settings before `--confirm`, and removes Todo after it. `as_found` is the
board before those edits; `roadmap` is the board once Backlog is New and Blocked exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app
from devops_cli.config.constants import CONST_ROADMAP_RENDER_MARKER
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.migrate import plan_migration
from devops_cli.roadmap.store import (
    BoardField,
    FieldOption,
    FieldSpec,
    GitHubState,
    ItemField,
)

REPO = "example/roadmap"
REF = "release/v0.2.25"
TEMPLATE = (Path(__file__).parents[1] / ".github" / "project-template.json").read_text(
    encoding="utf-8"
)
ROADMAP = """# Strategic Roadmap

## Release Milestones (Chronological Order)

### Foundations (v0.0.1 – v0.1.9 - Completed)
- [x] **Runtime Core**: shipped long ago.

### Multi-IDE MCP Scaffolding (v0.2.25 - Active Release)
- [ ] **GitHub-Sourced Roadmap View (P1 - High, Issue #1)**:
  - *Context & Rationale*: linked by the issue its heading names.
- [ ] **The Gate Cache Certifies Only the Tree It Checked (P1 - High)**:
  - *Context & Rationale*: linked by its title alone.
- [ ] **Delivered Thing (P2 - Medium, Issue #5)**:
  - *Context & Rationale*: its issue is closed.
- [ ] **Unfiled Polish (P2 - Medium)**:
  - *Context & Rationale*: no issue names it.
- [x] **Per-Check Input Scoping for the CI Cache — investigated, not building (P3 - Low)**:
  - *Finding*: the cache already keys on every input.

### Autonomous Fleet Governance (v0.3.2 - Scheduled)
- [ ] **Background Project Watcher Daemon (`devops gh pm daemon`) (P0 - Critical, Overlaps #741)**:
  - *Context & Rationale*: an aspirational P0 feature.

### Major Visionary Themes (v0.4.x & v0.5.x)

#### Self-Evolving Systems (v0.5.x)
- **Neurosymbolic Synthesis**: a theme, not an entry.

---
- [ ] **Backlog Entry After the Themes (P2 - Medium)**:
  - *Context & Rationale*: under no release heading.

## Value vs. Effort Prioritization Matrix

| Priority Category | Feature / Focus | Primary Open Source Resource | Value | Effort | Target Release | Status |
|---|---|---|---|---|---|---|
| **Quick Wins** | The Gate Cache Certifies Only the Tree It Checked | git | High | Low | v0.2.25 | 📋 Scheduled (P1) |
|  | The Matrix Disagrees | pytest | High | Medium | v0.2.25 | 📋 Scheduled (P2) |
|  | Shipped Long Ago | uv | High | Low | v0.2.20 | ✅ Completed |
| **De-prioritized** | Bare-Metal OS Installers | Shell scripts | Low | High | — | ❌ Rejected (DevContainer native) |
"""

STATUS_OPTIONS = (
    FieldOption(name="Todo", color="GRAY", description="Fresh"),
    FieldOption(name="Backlog", color="GRAY", description="Queued backlog items"),
    FieldOption(name="Ready", color="BLUE", description="Scoped"),
    FieldOption(name="In Progress", color="YELLOW", description="WIP"),
    FieldOption(name="In Review", color="PURPLE", description="PR open"),
    FieldOption(name="Done", color="GREEN", description="Merged"),
)

runner = CliRunner()


def _select(name: str, *options: str) -> FieldSpec:
    return FieldSpec(
        name=name, single_select=True, options=tuple(FieldOption(name=o) for o in options)
    )


def _status(store: InMemoryRoadmapStore) -> BoardField:
    return next(f for f in store.board_fields() if f.name == "Status")


def _rename_and_add_by_hand(store: InMemoryRoadmapStore) -> None:
    """Rename Backlog to New and add Blocked, as the owner does before --confirm."""
    options = _status(store).options
    store.edit_options_by_hand(
        "Status",
        [
            *(o.model_copy(update={"name": "New"}) if o.name == "Backlog" else o for o in options),
            FieldOption(name="Blocked", color="RED"),
        ],
    )


def _remove_by_hand(store: InMemoryRoadmapStore, name: str) -> None:
    """Remove a Status option, as the owner does once --confirm has moved its cards."""
    store.edit_options_by_hand("Status", [o for o in _status(store).options if o.name != name])


def _words(output: str) -> str:
    """The output with its line wrapping undone."""
    return " ".join(output.split())


@pytest.fixture
def as_found(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The fixture roadmap before its owner's option edits, in the store every command opens."""
    store = roadmap_store
    for spec in (
        FieldSpec(name="Status", single_select=True, options=STATUS_OPTIONS),
        _select("Priority", "P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
        _select("Category", "Quick Win", "Major Project"),
        _select("Value", "High", "Medium", "Low"),
        _select("Effort", "Low", "Medium", "High"),
    ):
        store.seed_field(spec)
    store.seed_file(".github/roadmap.toml", "board = 2\n", ref=REF)
    store.seed_file(".github/project-template.json", TEMPLATE, ref=REF)
    store.seed_file("docs/ROADMAP.md", ROADMAP, ref=REF)
    store.create_release("v0.2.24", state=GitHubState.CLOSED)
    for version in ("v0.2.25", "v0.2.26", "v0.2.27", "v0.3.0"):
        store.create_release(version)
    person = store.as_actor("alice")
    seeded: list[tuple[str, dict[str, Any], dict[ItemField, str]]] = [
        (
            "feat(github): roadmap view",
            {"labels": ("priority/p1-high",), "release": "v0.2.25"},
            {ItemField.STATUS: "Backlog"},
        ),
        (
            "fix(ci): the gate cache certifies only the tree it checked",
            {"labels": ("status/ready",), "release": "v0.2.25"},
            {},
        ),
        ("Release Epic: v0.2.25", {"labels": ("type/epic",)}, {}),
        ("Release Epic: v0.2.26", {"labels": ("type/epic",), "on_board": False}, {}),
        (
            "feat(ai): delivered thing",
            {"state": GitHubState.CLOSED, "state_reason": "completed"},
            {ItemField.STATUS: "Done"},
        ),
        (
            "feat(ai): a later idea",
            {"labels": ("priority/p2-medium",), "release": "v0.3.0"},
            {ItemField.STATUS: "Todo"},
        ),
        ("feat(ai): a pull request", {"pull_request": True}, {ItemField.STATUS: "Todo"}),
        (
            "feat(docs): the matrix disagrees",
            {},
            {ItemField.STATUS: "Ready", ItemField.VALUE: "Low"},
        ),
    ]
    for title, issue, fields in seeded:
        on_board = issue.pop("on_board", True)
        number = store.seed_issue(title, body=f"Body of {title}", on_board=on_board, **issue)
        for board_field, value in fields.items():
            card = next(card for card in store.cards() if card.number == number)
            person.set_card_field(card, board_field, value)
    return store


@pytest.fixture
def roadmap(as_found: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The fixture roadmap once its owner has renamed Backlog to New and added Blocked."""
    _rename_and_add_by_hand(as_found)
    return as_found


def _state(store: InMemoryRoadmapStore) -> tuple[Any, ...]:
    """Everything the migration could change, to compare before and after a run."""
    return (
        store.board_fields(),
        store.cards(),
        store.issues(),
        store.releases(),
        [store.comments_on(issue.number) for issue in store.issues()],
    )


def _migrate(*flags: str) -> Any:
    return runner.invoke(app, ["migrate", "--repo", REPO, "--ref", REF, *flags])


def _plan(store: InMemoryRoadmapStore) -> Any:
    return plan_migration(store, repo=REPO, ref=REF, config=RoadmapConfig(board=2))


def _status_options(store: InMemoryRoadmapStore) -> list[tuple[str | None, str]]:
    return [(option.id, option.name) for option in _status(store).options]


# ── Without writing ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("flags", [("--dry-run",), ()], ids=["dry-run", "no-flag"])
def test_without_confirm_nothing_changes_and_the_plan_lists_every_write(
    as_found: InMemoryRoadmapStore, flags: tuple[str, ...]
) -> None:
    before = _state(as_found)
    result = _migrate(*flags)
    planned = [
        "| #6 | set Status | Todo | New |",
        "| #7 | set Status | Todo | New |",
        "| Category field | delete | Category | — |",
        "| #1 | set Priority | — | P1-High |",
        "| #2 | set Status | — | Ready |",
        "| #6 | set Priority | — | P2-Medium |",
        "| #3 | close as not planned | open | closed |",
        "| #4 | close as not planned | open | closed |",
        "| #3 | remove from the board | — | — |",
        "| #6 | move to the backlog | v0.3.0 | — |",
        "| Release v0.3.0 | delete | v0.3.0 | — |",
        "| #2 | set Value | — | High |",
        "| #2 | set Effort | — | Low |",
        "| #8 | set Effort | — | Medium |",
        "| Bare-Metal OS Installers | open as an issue closed as not planned | — | closed |",
        "| Status option Backlog | rename by hand, before --confirm | Backlog | New |",
        "| Status option Blocked | add by hand, before --confirm | — | Blocked |",
        "| Status option Todo | remove by hand, after --confirm moves its cards | Todo | — |",
    ]
    rows = [line for line in result.output.splitlines() if line.startswith("| ")]
    assert (
        result.exit_code,
        _state(as_found) == before,
        [row for row in planned if row not in rows],
        "Nothing was written" in result.output,
    ) == (0, True, [], True)


def test_confirm_refuses_before_any_write_until_the_options_are_edited_by_hand(
    as_found: InMemoryRoadmapStore,
) -> None:
    """The plan sets New, which only a rename in the board's field settings can bring (#739)."""
    before = _state(as_found)
    result = _migrate("--confirm")
    assert (
        result.exit_code,
        _state(as_found) == before,
        "Nothing was written: Make these option edits in the board's field settings first"
        in _words(result.output),
        "rename Status option Backlog to New; add Status option Blocked." in _words(result.output),
    ) == (1, True, True, True)


# ── With --confirm ────────────────────────────────────────────────────────────


def test_confirm_brings_the_board_in_line_and_every_card_keeps_its_status(
    as_found: InMemoryRoadmapStore,
) -> None:
    """The owner renames and adds, migrate moves the Todo cards, then the owner removes Todo."""
    backlog_id = _status_options(as_found)[1][0]
    _rename_and_add_by_hand(as_found)
    result = _migrate("--confirm")
    _remove_by_hand(as_found, "Todo")
    statuses = {card.number: card.status for card in as_found.cards()}
    assert (
        result.exit_code,
        [name for _, name in _status_options(as_found)],
        _status_options(as_found)[0][0] == backlog_id,
        [f.name for f in as_found.board_fields() if f.name == "Category"],
        statuses,
    ) == (
        0,
        ["New", "Ready", "In Progress", "In Review", "Done", "Blocked"],
        True,
        [],
        {1: "New", 2: "Ready", 5: "Done", 6: "New", 7: "New", 8: "Ready"},
    )


def test_confirm_fills_unset_status_and_priority_from_labels(
    roadmap: InMemoryRoadmapStore,
) -> None:
    _migrate("--confirm")
    items = {item.number: (item.status, item.priority) for item in roadmap.items()}
    assert (items[1], items[2], items[6], items[8]) == (
        ("New", "P1-High"),
        ("Ready", None),
        ("New", "P2-Medium"),
        ("Ready", None),
    )


def test_confirm_closes_the_epics_as_not_planned_and_takes_them_off_the_board(
    roadmap: InMemoryRoadmapStore,
) -> None:
    _migrate("--confirm")
    epics = [issue for issue in roadmap.issues() if "type/epic" in issue.labels]
    assert (
        [(e.number, e.state, e.state_reason) for e in epics],
        [card.number for card in roadmap.cards() if card.number in (3, 4)],
        all(
            "0001-github-is-the-roadmap-source.md" in roadmap.comments_on(e.number)[0]
            for e in epics
        ),
    ) == (
        [(3, GitHubState.CLOSED, "not_planned"), (4, GitHubState.CLOSED, "not_planned")],
        [],
        True,
    )


def test_confirm_moves_the_later_release_into_the_backlog_and_deletes_it(
    roadmap: InMemoryRoadmapStore,
) -> None:
    _migrate("--confirm")
    assert (
        [release.title for release in roadmap.releases()],
        [item.number for item in roadmap.backlog()],
    ) == (["v0.2.24", "v0.2.25", "v0.2.26", "v0.2.27"], [6, 8])


def test_confirm_records_the_rejected_row_as_an_issue_closed_as_not_planned(
    roadmap: InMemoryRoadmapStore,
) -> None:
    _migrate("--confirm")
    recorded = [issue for issue in roadmap.issues() if issue.number > 8]
    assert [
        (issue.title, issue.state_reason, "❌ Rejected" in issue.body) for issue in recorded
    ] == [
        ("Bare-Metal OS Installers", "not_planned", True),
        (
            "Per-Check Input Scoping for the CI Cache — investigated, not building",
            "not_planned",
            False,
        ),
    ]


def test_confirm_sets_value_and_effort_only_where_they_were_unset(
    roadmap: InMemoryRoadmapStore,
) -> None:
    result = _migrate("--confirm")
    items = {item.number: (item.value, item.effort) for item in roadmap.items()}
    assert (items[2], items[8], "| #8 | keep Value | Low | High |" in result.output) == (
        ("High", "Low"),
        ("Low", "Medium"),
        True,
    )


def test_confirm_edits_no_issue_body_and_records_every_write(
    roadmap: InMemoryRoadmapStore,
) -> None:
    bodies = {issue.number: issue.body for issue in roadmap.issues()}
    _migrate("--confirm")
    records = {card.number: card.job_record for card in roadmap.cards()}
    assert (
        {issue.number: issue.body for issue in roadmap.issues() if issue.number in bodies},
        records,
    ) == (
        bodies,
        {
            1: {ItemField.PRIORITY: "P1-High"},
            2: {ItemField.STATUS: "Ready", ItemField.VALUE: "High", ItemField.EFFORT: "Low"},
            5: {},
            6: {ItemField.STATUS: "New", ItemField.PRIORITY: "P2-Medium", ItemField.RELEASE: None},
            7: {ItemField.STATUS: "New"},
            8: {ItemField.EFFORT: "Medium"},
        },
    )


def test_a_second_confirmed_run_plans_nothing(roadmap: InMemoryRoadmapStore) -> None:
    """Before the owner removes Todo, a rerun writes nothing and still lists the removal."""
    first = _migrate("--confirm")
    after_first = _state(roadmap)
    rerun = _migrate("--confirm")
    unchanged = _state(roadmap) == after_first
    _remove_by_hand(roadmap, "Todo")
    after_removal = _state(roadmap)
    second = _migrate("--confirm")
    plan = _plan(roadmap)
    assert (
        (first.exit_code, rerun.exit_code, second.exit_code),
        unchanged,
        "Nothing for migrate to write" in _words(rerun.output),
        "| Status option Todo | remove by hand" in rerun.output,
        (plan.writes, plan.option_edits),
        "Nothing to migrate" in second.output,
        _state(roadmap) == after_removal,
    ) == ((0, 0, 0), True, True, True, ((), ()), True, True)


# ── The report ────────────────────────────────────────────────────────────────


def _section(output: str, number: int) -> str:
    """The report section headed `## <number>.`, up to the next section."""
    start = output.index(f"## {number}.")
    end = output.find("\n## ", start + 1)
    return output[start : end if end != -1 else None]


def test_the_report_lists_candidates_unfiled_and_closed_entries_and_the_writes(
    as_found: InMemoryRoadmapStore,
) -> None:
    output = _migrate().output
    p0, unfiled, closed, writes = (_section(output, n) for n in (1, 2, 3, 4))
    linked_or_p0 = ("Watcher Daemon", "Gate Cache", "Roadmap View", "Delivered Thing")
    assert (
        "docs/ROADMAP.md:21 — Background Project Watcher Daemon" in p0,
        "overlaps #741" in p0,
        [name for name in ("Unfiled Polish", "Backlog Entry After the Themes") if name in unfiled],
        [name for name in linked_or_p0 if name in unfiled],
        "docs/ROADMAP.md:13 — Delivered Thing — P2" in closed and "#5 closed" in closed,
        "| Status option Backlog | rename by hand, before --confirm | Backlog | New |" in writes,
    ) == (True, True, ["Unfiled Polish", "Backlog Entry After the Themes"], [], True, True)


def test_a_p0_entry_that_matches_an_issue_is_listed_with_its_match(
    roadmap: InMemoryRoadmapStore,
) -> None:
    roadmap.seed_issue("feat(github): background project watcher daemon (`devops gh pm daemon`)")
    assert "matches #9" in _section(_migrate().output, 1)


def test_the_report_names_an_enabled_auto_add_workflow(roadmap: InMemoryRoadmapStore) -> None:
    roadmap.seed_workflow("Auto-add sub-issues to project", enabled=True)
    roadmap.seed_workflow("Item closed", enabled=True)
    output = _migrate().output
    assert output[output.index("### Enabled auto-add") :].splitlines()[2:3] == [
        "- Auto-add sub-issues to project"
    ]


# ── Edges ─────────────────────────────────────────────────────────────────────


def test_a_file_carrying_the_render_marker_is_not_imported(
    roadmap: InMemoryRoadmapStore,
) -> None:
    roadmap.seed_file("docs/ROADMAP.md", f"{CONST_ROADMAP_RENDER_MARKER}\n\n{ROADMAP}", ref=REF)
    plan = _plan(roadmap)
    subjects = [change.subject for change in plan.changes]
    assert (
        plan.imported,
        plan.p0_candidates + plan.unfiled + plan.closed,
        "Bare-Metal OS Installers" in subjects,
        [c.change for c in plan.changes if c.change in ("set Value", "set Effort")],
        "carries the `devops roadmap render` marker" in _migrate().output,
    ) == (False, (), False, [], True)


def test_a_board_number_that_names_no_board_plans_a_board_from_the_template(
    roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryRoadmapStore(board_exists=False, repo=REPO)
    monkeypatch.setattr("devops_cli.roadmap.store.get_roadmap_store", lambda repo, **_: store)
    for path, text in (
        (".github/roadmap.toml", "board = 7\n"),
        (".github/project-template.json", TEMPLATE),
        ("docs/ROADMAP.md", "# Roadmap\n"),
    ):
        store.seed_file(path, text, ref=REF)
    preview = _migrate()
    created = _migrate("--confirm")
    assert (
        "| board | create from the template |" in preview.output,
        created.exit_code,
        "Created board #1" in created.output,
        [f.name for f in store.board_fields()],
    ) == (
        True,
        0,
        True,
        ["Job record", "Status", "Priority", "Value", "Effort"],
    )


def test_a_board_missing_a_template_field_is_refused_before_any_write(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    roadmap_store.seed_file(".github/roadmap.toml", "board = 2\n", ref=REF)
    roadmap_store.seed_file(".github/project-template.json", TEMPLATE, ref=REF)
    roadmap_store.seed_file("docs/ROADMAP.md", ROADMAP, ref=REF)
    result = _migrate("--confirm")
    assert (result.exit_code, "devops gh project sync" in result.output) == (1, True)


def test_a_failed_read_exits_1_and_names_it(unreadable_github_roadmap: list[list[str]]) -> None:
    result = _migrate("--confirm")
    assert (
        result.exit_code,
        "Could not plan the roadmap migration" in result.output,
        [args[:2] for args in unreadable_github_roadmap],
    ) == (1, True, [["api", "-H"]])
