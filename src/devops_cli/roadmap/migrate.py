"""`devops roadmap migrate`: make GitHub the roadmap's source of truth, once (ADR 0001).

The migration reads the board, the issues, the Releases, the board template and the
hand-written `docs/ROADMAP.md`, then plans every write: the board brought in line with the
template, unset Status and Priority filled from labels, release epics closed and taken off the
board, Releases beyond the planning horizon emptied into the backlog and deleted, unset Value
and Effort filled from the matrix, and rejected ideas recorded as issues closed as not planned.
It never edits an issue body, and it only fills fields that are unset, so a value a person set
stands. Every step plans only what is still to do, so a second run plans nothing and a run that
stopped part-way continues where it stopped.

It never edits a board's options. GitHub's option input takes no id, so an option list sent
through the API gives every option a new id and clears it from every card, and from every
built-in workflow that sets it. The plan lists the renames and additions a person makes in the
board's field settings, which keep ids, before `--confirm`, and the removals after it.

Writes go through the roadmap store, which records each field it sets in the card's job record
(ADR 0002). The plan's report lists the entries the migration leaves for a person to decide on.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from packaging.version import Version
from pydantic import ValidationError as InvalidTemplateError

from devops_cli.config.constants import (
    CONST_PROJECT_TEMPLATE_PATH,
    CONST_ROADMAP_ADR_PATH,
    CONST_ROADMAP_AUTO_ADD_WORKFLOW_PREFIX,
    CONST_ROADMAP_DOCUMENT_PATH,
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_P0_PRIORITY,
    CONST_ROADMAP_RENDER_MARKER,
    CONST_ROADMAP_STATUS_FIELD,
)
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.projects import (
    ProjectField,
    ProjectTemplate,
    declared_priority,
    initial_status,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.document import (
    RoadmapDocument,
    RoadmapEntry,
    linked_issues,
    parse_roadmap,
    title_match,
    titles_index,
)
from devops_cli.roadmap.store import (
    BOARD_FIELDS,
    Board,
    BoardField,
    Card,
    CardKind,
    CloseReason,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    Release,
    RoadmapStore,
    Workflow,
    field_options,
)

_TEMPLATE_SINGLE_SELECT = "single_select"

# ── The plan ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlannedChange:
    """One change the plan makes: to what, how, and the value before and after."""

    subject: str
    change: str
    old: str | None = None
    new: str | None = None


@dataclass(frozen=True)
class PlannedWrite:
    """One store call and the changes it makes."""

    changes: tuple[PlannedChange, ...]
    apply: Callable[[RoadmapStore], object] = field(compare=False, repr=False)


@dataclass(frozen=True)
class OptionEdit:
    """An option edit a person makes in the board's field settings.

    A rename or an addition is due before `--confirm`, because the planned writes set the
    option it names. A removal is due after, once `--confirm` has moved the option's cards.
    """

    field_name: str
    old: str | None
    new: str | None

    @property
    def before_confirm(self) -> bool:
        """Whether the planned writes need the option this edit puts on the board."""
        return self.new is not None

    @property
    def verb(self) -> str:
        """What the person does to the option: rename, add or remove it."""
        return "rename" if self.old and self.new else "add" if self.new else "remove"

    @property
    def change(self) -> PlannedChange:
        """The edit as a row of the report."""
        when = "before --confirm" if self.before_confirm else "after --confirm moves its cards"
        subject = f"{self.field_name} option {self.old or self.new}"
        return PlannedChange(subject, f"{self.verb} by hand, {when}", self.old, self.new)

    def __str__(self) -> str:
        """The edit in words, such as "rename Status option Backlog to New"."""
        target = f" to {self.new}" if self.old and self.new else ""
        return f"{self.verb} {self.field_name} option {self.old or self.new}{target}"


@dataclass(frozen=True)
class ReportedEntry:
    """A ROADMAP entry the report lists, with the issues it is linked to."""

    entry: RoadmapEntry
    issues: tuple[int, ...] = ()


@dataclass(frozen=True)
class MigrationPlan:
    """Every write the migration would make, and the report on what it leaves to a person."""

    repo: str
    ref: str | None
    writes: tuple[PlannedWrite, ...]
    imported: bool
    p0_candidates: tuple[ReportedEntry, ...] = ()
    unfiled: tuple[ReportedEntry, ...] = ()
    closed: tuple[ReportedEntry, ...] = ()
    left_alone: tuple[PlannedChange, ...] = ()
    auto_add: tuple[Workflow, ...] = ()
    option_edits: tuple[OptionEdit, ...] = ()

    @property
    def changes(self) -> list[PlannedChange]:
        """Every planned change, in the order the writes make them."""
        return [change for write in self.writes for change in write.changes]

    @property
    def edits_due(self) -> list[OptionEdit]:
        """The option edits a person makes before `--confirm` may write."""
        return [edit for edit in self.option_edits if edit.before_confirm]


@dataclass(frozen=True)
class _Snapshot:
    """Everything the plan is made from, read once."""

    repo: str
    config: RoadmapConfig
    template: ProjectTemplate
    board: Board | None
    fields: tuple[BoardField, ...]
    cards: tuple[Card, ...]
    items: tuple[Item, ...]
    issues: tuple[IssueRecord, ...]
    releases: tuple[Release, ...]
    workflows: tuple[Workflow, ...]
    document: RoadmapDocument | None

    @property
    def epics(self) -> set[int]:
        return {i.number for i in self.issues if CONST_ROADMAP_EPIC_LABEL in i.labels}

    @property
    def open_items(self) -> list[Item]:
        """The open Items the migration may write: every one but the epics it retires."""
        epics = self.epics
        return [
            item
            for item in self.items
            if item.state is GitHubState.OPEN and item.number not in epics
        ]

    @property
    def options(self) -> dict[str, tuple[str, ...]]:
        """The board's option names by field, once the template's options are in place."""
        return field_options(self.fields) | {
            spec.name: tuple(option.name for option in spec.options)
            for spec in self.template.fields
            if spec.type == _TEMPLATE_SINGLE_SELECT
        }

    @property
    def kept_releases(self) -> list[Release]:
        """The current release, the lowest open one, and the next planned ones by version."""
        open_releases = [r for r in self.releases if r.state is GitHubState.OPEN]
        return open_releases[: 1 + self.config.planning_horizon]

    @property
    def later_releases(self) -> list[Release]:
        """The open Releases beyond the planning horizon."""
        open_releases = [r for r in self.releases if r.state is GitHubState.OPEN]
        return open_releases[1 + self.config.planning_horizon :]


StoreCall = Callable[[RoadmapStore], object]


def _write(apply: StoreCall, *changes: PlannedChange) -> PlannedWrite:
    return PlannedWrite(changes=changes, apply=apply)


def _set_card(card: Card, board_field: ItemField, value: str) -> StoreCall:
    return lambda store: store.set_card_field(card, board_field, value)


def _delete_field(name: str) -> StoreCall:
    return lambda store: store.delete_field(name)


def _close_not_planned(number: int, comment: str) -> StoreCall:
    return lambda store: store.close_issue(number, CloseReason.NOT_PLANNED, comment)


def _remove_card(card: Card) -> StoreCall:
    return lambda store: store.remove_card(card)


def _delete_release(version: str) -> StoreCall:
    return lambda store: store.delete_release(version)


def _record_not_planned(title: str, body: str, comment: str) -> StoreCall:
    """Open an issue for a rejected idea, then close it as not planned."""
    return lambda store: store.close_issue(
        store.create_issue(title, body).number, CloseReason.NOT_PLANNED, comment
    )


def _card_label(card: Card, repo: str) -> str:
    if card.number is not None and (card.repository or "").lower() == repo.lower():
        return f"#{card.number}"
    return card.url or f"draft {card.id}"


# ── Reading ───────────────────────────────────────────────────────────────────


def read_template(store: RoadmapStore, *, ref: str | None) -> ProjectTemplate:
    """The board template on `ref`, read through the store like every runner's inputs."""
    text = store.repository_file(CONST_PROJECT_TEMPLATE_PATH, ref=ref)
    try:
        return ProjectTemplate.model_validate_json(text)
    except InvalidTemplateError as exc:
        raise ConfigurationError(
            f"{CONST_PROJECT_TEMPLATE_PATH} is not a valid board template: {exc}",
            details={"path": CONST_PROJECT_TEMPLATE_PATH},
        ) from exc


def read_document(store: RoadmapStore, *, ref: str | None) -> RoadmapDocument | None:
    """The hand-written roadmap on `ref`, or None when it is render's generated view."""
    text = store.repository_file(CONST_ROADMAP_DOCUMENT_PATH, ref=ref)
    return None if CONST_ROADMAP_RENDER_MARKER in text.splitlines() else parse_roadmap(text)


def _require_template_fields(fields: Sequence[BoardField], template: ProjectTemplate) -> None:
    """Refuse a board that lacks a template field, which only `project sync` creates."""
    names = {board_field.name for board_field in fields}
    missing = [spec.name for spec in template.fields if spec.name not in names]
    if missing:
        raise GitHubOperationError(
            f"The board lacks the template's {', '.join(missing)} field(s). Create them with "
            "`devops gh project sync`, then run migrate again.",
            operation="roadmap.migrate",
            details={"missing": ", ".join(missing)[:256]},
        )


def _read_snapshot(
    store: RoadmapStore, repo: str, ref: str | None, config: RoadmapConfig
) -> _Snapshot:
    template = read_template(store, ref=ref)
    document = read_document(store, ref=ref)
    board = store.board()
    fields = tuple(store.board_fields()) if board else ()
    if board:
        _require_template_fields(fields, template)
    return _Snapshot(
        repo=repo,
        config=config,
        template=template,
        board=board,
        fields=fields,
        cards=tuple(store.cards()) if board else (),
        items=tuple(store.items()) if board else (),
        issues=tuple(store.issues()),
        releases=tuple(store.releases()),
        workflows=tuple(store.workflows()) if board else (),
        document=document,
    )


# ── The board ─────────────────────────────────────────────────────────────────


def _field_spec(template_field: ProjectField) -> FieldSpec:
    return FieldSpec(
        name=template_field.name,
        single_select=template_field.type == _TEMPLATE_SINGLE_SELECT,
        options=tuple(
            FieldOption(name=o.name, color=o.color, description=o.description)
            for o in template_field.options
        ),
    )


def _plan_options(
    current: BoardField, spec: ProjectField
) -> tuple[list[OptionEdit], dict[str, str]]:
    """The option edits a person makes, and the options whose cards migrate moves.

    A template option the board lacks is a rename of the first option it replaces that the
    board has, which keeps that option's id and so its cards' value, or else an addition. Every
    other option it replaces is merged: migrate moves its cards to the template option, then a
    person removes it. Options the template doesn't know are kept.
    """
    names = {option.name for option in current.options}
    wanted = {option.name for option in spec.options}
    claimed: set[str] = set()
    edits: list[OptionEdit] = []
    merges: dict[str, str] = {}
    for option in spec.options:
        replaced = [name for name in option.replaces if name in names - wanted - claimed]
        claimed.update(replaced)
        if option.name not in names:
            renamed = replaced.pop(0) if replaced else None
            edits.append(OptionEdit(current.name, renamed, option.name))
        merges.update(dict.fromkeys(replaced, option.name))
    edits.extend(OptionEdit(current.name, name, None) for name in merges)
    return edits, merges


def _merge_writes(
    snapshot: _Snapshot, current: BoardField, merges: dict[str, str]
) -> Iterator[PlannedWrite]:
    """Move every card that holds a merged option to the template option that replaces it."""
    board_field = next((f for f in BOARD_FIELDS if f.value == current.name), None)
    if board_field is None:
        return
    for card in snapshot.cards:
        held = card.field_value(board_field)
        target = merges.get(held) if held else None
        if target:
            yield _write(
                _set_card(card, board_field, target),
                PlannedChange(
                    _card_label(card, snapshot.repo), f"set {current.name}", held, target
                ),
            )


def _board_writes(snapshot: _Snapshot, edits: list[OptionEdit]) -> Iterator[PlannedWrite]:
    """Create the board from the template, or move merged options' cards and delete stray fields.

    The option edits a person makes in the board's field settings join `edits`.
    """
    template = snapshot.template
    if snapshot.board is None:
        specs = [_field_spec(template_field) for template_field in template.fields]
        yield _write(
            lambda store: store.create_board(template.name, specs),
            PlannedChange("board", "create from the template", None, template.name),
        )
        return
    current = {board_field.name: board_field for board_field in snapshot.fields}
    for spec in template.fields:
        if spec.type == _TEMPLATE_SINGLE_SELECT and current[spec.name].single_select:
            field_edits, merges = _plan_options(current[spec.name], spec)
            edits.extend(field_edits)
            yield from _merge_writes(snapshot, current[spec.name], merges)
    wanted = {spec.name for spec in template.fields}
    for board_field in snapshot.fields:
        if board_field.single_select and board_field.name not in wanted:
            yield _write(
                _delete_field(board_field.name),
                PlannedChange(f"{board_field.name} field", "delete", board_field.name, None),
            )


# ── Items ─────────────────────────────────────────────────────────────────────


def _set(item: Item, board_field: ItemField, value: str | None, change: str) -> PlannedWrite:
    return _write(
        lambda store: store.set_field(item, board_field, value),
        PlannedChange(f"#{item.number}", change, item.field_value(board_field), value),
    )


def _field_writes(snapshot: _Snapshot) -> Iterator[PlannedWrite]:
    """Fill an open Item's unset Status and Priority by the labels `project sync` reads."""
    options = snapshot.options
    statuses = options.get(CONST_ROADMAP_STATUS_FIELD, ())
    priorities = options.get(ItemField.PRIORITY.value, ())
    for item in snapshot.open_items:
        if item.status is None:
            status, _ = initial_status(item.labels, statuses)
            yield _set(item, ItemField.STATUS, status, "set Status")
        declared = None if item.priority else declared_priority(item.labels)
        if declared and declared[0] in priorities:
            yield _set(item, ItemField.PRIORITY, declared[0], "set Priority")


def _epic_writes(snapshot: _Snapshot) -> Iterator[PlannedWrite]:
    """Close every open release epic as not planned, then take every epic off the board."""
    epics = snapshot.epics
    comment = MESSAGES.roadmap.epic_closed.format(adr=_adr_link(snapshot.repo))
    for issue in snapshot.issues:
        if issue.number in epics and issue.state is GitHubState.OPEN:
            yield _write(
                _close_not_planned(issue.number, comment),
                PlannedChange(f"#{issue.number}", "close as not planned", "open", "closed"),
            )
    for card in snapshot.cards:
        if card.kind is CardKind.ISSUE and card.number in epics and _is_ours(card, snapshot.repo):
            yield _write(
                _remove_card(card),
                PlannedChange(f"#{card.number}", "remove from the board"),
            )


def _release_writes(snapshot: _Snapshot) -> Iterator[PlannedWrite]:
    """Move the open Items of Releases beyond the horizon to the backlog, then delete them."""
    for release in snapshot.later_releases:
        for item in snapshot.open_items:
            if item.release == release.title:
                yield _set(item, ItemField.RELEASE, None, "move to the backlog")
        yield _write(
            _delete_release(release.title),
            PlannedChange(f"Release {release.title}", "delete", release.title, None),
        )


def _matrix_values(
    snapshot: _Snapshot, document: RoadmapDocument
) -> Iterator[tuple[Item, ItemField, str]]:
    """Each Value and Effort an open matrix row gives the one open Item its title names."""
    titles = titles_index(snapshot.issues)
    items = {item.number: item for item in snapshot.open_items}
    options = snapshot.options
    for row in document.matrix:
        number = title_match(row.feature, titles) if row.open else None
        item = items.get(number) if number is not None else None
        if item is None:
            continue
        for board_field, value in ((ItemField.VALUE, row.value), (ItemField.EFFORT, row.effort)):
            if value in options.get(board_field.value, ()):
                yield item, board_field, value


def _matrix_writes(
    snapshot: _Snapshot, document: RoadmapDocument, left_alone: list[PlannedChange]
) -> Iterator[PlannedWrite]:
    """Fill an unset Value or Effort from the matrix; list a set value that differs."""
    seen: set[tuple[int, ItemField]] = set()
    for item, board_field, value in _matrix_values(snapshot, document):
        if (item.number, board_field) in seen:
            continue
        seen.add((item.number, board_field))
        current = item.field_value(board_field)
        if current is None:
            yield _set(item, board_field, value, f"set {board_field.value}")
        elif current != value:
            left_alone.append(
                PlannedChange(f"#{item.number}", f"keep {board_field.value}", current, value)
            )


def _not_planned_sources(document: RoadmapDocument) -> Iterator[tuple[str, str, str, int]]:
    """Each rejected matrix row and not-building entry: title, status, text and line."""
    for row in document.matrix:
        if row.rejected:
            yield row.feature, row.status, row.text, row.line
    for entry in document.entries:
        if entry.not_building:
            yield entry.title, "investigated, not building", entry.text, entry.line


def _not_planned_writes(snapshot: _Snapshot, document: RoadmapDocument) -> Iterator[PlannedWrite]:
    """Record each rejected idea as an issue closed as not planned, unless one already is."""
    titles = titles_index(snapshot.issues)
    states = {issue.number: issue.state for issue in snapshot.issues}
    adr = _adr_link(snapshot.repo)
    for title, status, text, line in _not_planned_sources(document):
        location = f"{CONST_ROADMAP_DOCUMENT_PATH}:{line}"
        comment = MESSAGES.roadmap.not_planned_closed.format(
            status=status, location=location, adr=adr
        )
        existing = title_match(title, titles)
        if existing is None:
            body = MESSAGES.roadmap.not_planned_body.format(location=location, text=text)
            yield _write(
                _record_not_planned(title, body, comment),
                PlannedChange(title, "open as an issue closed as not planned", None, "closed"),
            )
        elif states[existing] is GitHubState.OPEN:
            yield _write(
                _close_not_planned(existing, comment),
                PlannedChange(f"#{existing}", "close as not planned", "open", "closed"),
            )


# ── The report ────────────────────────────────────────────────────────────────


def _is_ours(card: Card, repo: str) -> bool:
    return (card.repository or "").lower() == repo.lower()


def _adr_link(repo: str) -> str:
    return f"https://github.com/{repo}/blob/HEAD/{CONST_ROADMAP_ADR_PATH}"


def _beyond_horizon(entry: RoadmapEntry, kept: Sequence[Release]) -> bool:
    """Whether the entry sits in a release later than every release the migration keeps."""
    if entry.release is None:
        return False
    newest = max((release.version for release in kept), default=None)
    return newest is None or Version(entry.release) > newest


def _report_entries(
    snapshot: _Snapshot, document: RoadmapDocument
) -> tuple[list[ReportedEntry], list[ReportedEntry], list[ReportedEntry]]:
    """The P0 candidates, the unfiled entries and the entries whose issue is closed."""
    titles = titles_index(snapshot.issues)
    states = {issue.number: issue.state for issue in snapshot.issues}
    kept = snapshot.kept_releases
    candidates: list[ReportedEntry] = []
    unfiled: list[ReportedEntry] = []
    closed: list[ReportedEntry] = []
    for entry in (entry for entry in document.entries if not entry.done):
        reported = ReportedEntry(entry=entry, issues=linked_issues(entry, titles))
        if entry.priority == CONST_ROADMAP_P0_PRIORITY and _beyond_horizon(entry, kept):
            candidates.append(reported)
        elif not reported.issues:
            unfiled.append(reported)
        if reported.issues and all(
            states.get(number) is GitHubState.CLOSED for number in reported.issues
        ):
            closed.append(reported)
    return candidates, unfiled, closed


def plan_migration(
    store: RoadmapStore, *, repo: str, ref: str | None, config: RoadmapConfig
) -> MigrationPlan:
    """Read the roadmap and plan every write the migration still has to make."""
    snapshot = _read_snapshot(store, repo, ref, config)
    document = snapshot.document
    left_alone: list[PlannedChange] = []
    edits: list[OptionEdit] = []
    writes = [
        *_board_writes(snapshot, edits),
        *_field_writes(snapshot),
        *_epic_writes(snapshot),
        *_release_writes(snapshot),
        *(_matrix_writes(snapshot, document, left_alone) if document else ()),
        *(_not_planned_writes(snapshot, document) if document else ()),
    ]
    candidates, unfiled, closed = _report_entries(snapshot, document) if document else ([], [], [])
    auto_add = tuple(
        workflow
        for workflow in snapshot.workflows
        if workflow.enabled and workflow.name.startswith(CONST_ROADMAP_AUTO_ADD_WORKFLOW_PREFIX)
    )
    return MigrationPlan(
        repo=repo,
        ref=ref,
        writes=tuple(writes),
        imported=document is not None,
        p0_candidates=tuple(candidates),
        unfiled=tuple(unfiled),
        closed=tuple(closed),
        left_alone=tuple(left_alone),
        auto_add=auto_add,
        option_edits=tuple(edits),
    )


def require_option_edits_made(plan: MigrationPlan) -> None:
    """Refuse a plan whose writes need options a person has yet to put on the board."""
    due = plan.edits_due
    if due:
        edits = "; ".join(str(edit) for edit in due)
        raise GitHubOperationError(
            MESSAGES.roadmap.edits_due.format(edits=edits),
            operation="roadmap.migrate",
            details={"edits": edits[:256]},
        )


def apply_migration(
    store: RoadmapStore,
    plan: MigrationPlan,
    *,
    on_write: Callable[[PlannedWrite], None] | None = None,
) -> Board | None:
    """Make the plan's writes in order, returning the board it created, if it created one.

    A plan whose option edits a person has yet to make raises before any write.
    """
    require_option_edits_made(plan)
    created: Board | None = None
    for planned in plan.writes:
        result = planned.apply(store)
        created = result if isinstance(result, Board) else created
        if on_write is not None:
            on_write(planned)
    return created


def _cell(text: str | None) -> str:
    return "—" if text is None else text.replace("|", "\\|").replace("\n", " ")


def _entry_line(reported: ReportedEntry, note: str) -> str:
    entry = reported.entry
    location = f"{CONST_ROADMAP_DOCUMENT_PATH}:{entry.line}"
    priority = entry.priority or "no priority"
    return f"- {location} — {entry.title} — {priority} — section “{entry.section}”{note}"


def _p0_note(reported: ReportedEntry) -> str:
    matches = "".join(f" — matches #{number}" for number in reported.issues)
    overlaps = "".join(f" — overlaps #{number}" for number in reported.entry.overlaps)
    return matches + overlaps


def _closed_note(reported: ReportedEntry) -> str:
    return " — " + ", ".join(f"#{number} closed" for number in reported.issues)


def _section(heading: str, lines: Sequence[str]) -> list[str]:
    return [heading, "", *(lines or [MESSAGES.roadmap.report_none]), ""]


def _change_rows(changes: Sequence[PlannedChange]) -> list[str]:
    if not changes:
        return []
    header = ["| Subject | Change | Old | New |", "| :--- | :--- | :--- | :--- |"]
    return header + [
        f"| {_cell(c.subject)} | {_cell(c.change)} | {_cell(c.old)} | {_cell(c.new)} |"
        for c in changes
    ]


def render_report(plan: MigrationPlan) -> str:
    """The plan and its report as Markdown, in four sections."""
    messages = MESSAGES.roadmap
    ref = plan.ref or messages.default_branch
    not_imported = [messages.report_not_imported.format(path=CONST_ROADMAP_DOCUMENT_PATH)]
    sections = [
        messages.report_title.format(repo=plan.repo, ref=ref),
        "",
        *([] if plan.imported else [not_imported[0], ""]),
        *_section(messages.report_p0, [_entry_line(r, _p0_note(r)) for r in plan.p0_candidates]),
        *_section(messages.report_unfiled, [_entry_line(r, "") for r in plan.unfiled]),
        *_section(messages.report_closed, [_entry_line(r, _closed_note(r)) for r in plan.closed]),
        *_section(messages.report_writes, _change_rows(plan.changes)),
        *_section(
            messages.report_option_edits, _change_rows([e.change for e in plan.option_edits])
        ),
        *_section(messages.report_left_alone, _change_rows(plan.left_alone)),
        *_section(messages.report_auto_add, [f"- {w.name}" for w in plan.auto_add]),
    ]
    return "\n".join(sections).rstrip() + "\n"


__all__ = [
    "MigrationPlan",
    "OptionEdit",
    "PlannedChange",
    "PlannedWrite",
    "ReportedEntry",
    "apply_migration",
    "plan_migration",
    "read_document",
    "read_template",
    "render_report",
    "require_option_edits_made",
]
