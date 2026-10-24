"""The requests the roadmap jobs make, as a dry run lists them without making any (#412, #1125).

A dry run makes no request, reads included. It returns the job's real result type, marked as a
dry run, holding the requests a run makes in order as `PlannedRequest`s (#741): the exact `gh`
argv and stdin, built by the same argument builders `GitHubRoadmapStore` runs, so the plan
cannot drift from the run. A REST listing, which the store reads through the GitHub session
(#983), is its `GET` and URL. A value that needs a read is a placeholder in angle brackets, a
request that runs only when something holds names that in `condition`, and a request a run makes
for each page, item or field says so in `repeat`.

`StoreRequests` gives the requests of each store operation; `refine_requests` puts the refine
job's operations in the order the job makes them, and intake's plan (`intake_requests`) does the
same for intake. A store reads the board's fields, and the listing of each filter, once (#1361),
so an operation that needs them lists their read under the condition that the run has not made
it yet.
A board write lists the read of its one card and the edit by node ids; an add lists the read of
the card it names and that card's restore when it is archived. Every run of a job that sent a
GraphQL request, as every run that reads the board does, ends with one GraphQL budget read, for
its spend line, after any write; a run that sent none makes no budget read (#1400).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from devops_cli.config.constants import (
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_ROADMAP_CONFIG_PATH,
    CONST_ROADMAP_OPEN_ITEMS_FILTER,
    CONST_ROADMAP_REFINE_BOARD_FILTER,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.dry_run.requests import PlannedRequest, both, render_request_plan
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import github_store as gh
from devops_cli.roadmap.board_read import (
    board_budget_args,
    board_card_args,
    board_items_args,
    graphql_budget_args,
)

_GH = "gh"
Requests = list[PlannedRequest]


def _p(key: str) -> str:
    """The placeholder `key` names."""
    return MESSAGES.roadmap.plan_placeholders[key]


def within(requests: Iterable[PlannedRequest], condition: str = "", repeat: str = "") -> Requests:
    """The requests, each run only when `condition` holds as well as its own, and `repeat`ed
    as well as its own repeat."""
    return [
        replace(
            request,
            condition=both(condition, request.condition),
            repeat="; ".join(part for part in (repeat, request.repeat) if part),
        )
        for request in requests
    ]


def planned_gh(
    argv: Sequence[str],
    target: str,
    *,
    stdin: str | None = None,
    condition: str = "",
    repeat: str = "",
) -> PlannedRequest:
    """One `gh` command against `target`: its transport and whether it writes, as `run_gh`
    classifies it."""
    from devops_cli.github.rate_limiter import gh_request_resource
    from devops_cli.github.request_classifier import is_write_gh_command

    args = list(argv)
    texts = MESSAGES.roadmap
    via = {"graphql": "GraphQL", "search": "REST search"}.get(gh_request_resource(args), "REST")
    write = is_write_gh_command(args, input=stdin)
    verb = texts.intake_request_write if write else texts.intake_request_read
    return PlannedRequest(
        method=f"{via} {verb}",
        target=target,
        argv=(_GH, *args),
        stdin=stdin,
        condition=condition,
        repeat=repeat,
    )


def planned_session_read(
    path: str, target: str, *, condition: str = "", repeat: str = ""
) -> PlannedRequest:
    """One read the GitHub session sends (#983): a REST GET of `target`, shown as its request
    line, the method and the URL of `path` under GitHub's API."""
    return PlannedRequest(
        method=f"REST {MESSAGES.roadmap.intake_request_read}",
        target=target,
        argv=("GET", f"{CONST_URL_GITHUB_API_BASE}{path}"),
        condition=condition,
        repeat=repeat,
    )


def is_page_repeat(repeat: str) -> bool:
    """Whether `repeat` is only a page repeat: the request runs at least once, then again per
    page. Any other repeat may run no time at all."""
    return repeat == MESSAGES.roadmap.plan_repeat_page


@dataclass(frozen=True)
class StoreRequests:
    """The requests each `GitHubRoadmapStore` operation makes on `repo`'s board, whose number
    `.github/roadmap.toml` gives, reading the board with the job's Projects filter."""

    repo: str
    board_filter: str = ""
    board: str = ""

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def number(self) -> str:
        return self.board or _p("board")

    def gh(
        self,
        argv: Sequence[str],
        key: str,
        *,
        stdin: str | None = None,
        condition: str = "",
        repeat: str = "",
        **values: str,
    ) -> PlannedRequest:
        """One `gh` command, against the target `key` names in `plan_targets`."""
        target = self._target(key, **values)
        return planned_gh(argv, target, stdin=stdin, condition=condition, repeat=repeat)

    def _target(self, key: str, **values: str) -> str:
        """What the request `key` names in `plan_targets` reads or writes."""
        return MESSAGES.roadmap.plan_targets[key].format(
            board=self.number, owner=self.owner, **values
        )

    # ── Reads ──

    def file(self, path: str, ref: str | None) -> Requests:
        at = ref or MESSAGES.roadmap.intake_placeholder_default_branch
        return [
            self.gh(gh.repository_file_args(self.repo, path, ref=ref), "file", path=path, ref=at)
        ]

    def listing(self, endpoint: str, key: str, **values: str) -> Requests:
        """A REST listing the GitHub session reads (#983): its first page, then each next page
        GitHub links."""
        target = self._target(key, **values)
        path = gh.listing_path(endpoint)
        return [planned_session_read(path, target, repeat=MESSAGES.roadmap.plan_repeat_page)]

    def milestones(self) -> Requests:
        return self.listing(gh.milestones_endpoint(self.repo), "milestones")

    def _issues(self, query: str) -> Requests:
        return self.listing(gh.issues_endpoint(self.repo, query), "issues", query=query)

    def board_read(self, board_filter: str | None = None) -> Requests:
        """A board read: the budget query, the first page, then a page per cursor."""
        query = self.board_filter if board_filter is None else board_filter
        matching = f' matching "{query}"' if query else ""
        later = board_items_args(self.owner, self.number, query, after=_p("cursor"))
        return [
            self.gh(
                board_budget_args(self.owner, self.number, query), "board_budget", matching=matching
            ),
            self.gh(
                board_items_args(self.owner, self.number, query), "board_first", matching=matching
            ),
            self.gh(
                later,
                "board_page",
                repeat=MESSAGES.roadmap.plan_repeat_board_page,
                matching=matching,
            ),
        ]

    def kept_board(self, board_filter: str | None = None) -> Requests:
        """The board read a store makes the first time it needs this filter's listing."""
        unread = MESSAGES.roadmap.plan_conditions["board_unread"]
        return within(self.board_read(board_filter), unread)

    def items(self, *, milestone: str | None = None) -> Requests:
        """Every Item, or the Items of the milestone numbered `milestone`, a placeholder."""
        query = "state=all" if milestone is None else f"milestone={milestone}&state=all"
        return [*self.kept_board(), *self._issues(query)]

    def backlog(self) -> Requests:
        return [
            *self.kept_board(CONST_ROADMAP_OPEN_ITEMS_FILTER),
            *self._issues("milestone=none&state=open"),
        ]

    def issues(self) -> Requests:
        return self._issues("state=all")

    def board_fields(self) -> Requests:
        return [self.gh(gh.board_fields_args(self.owner, self.number), "fields")]

    def kept_fields(self) -> Requests:
        """The fields read a store makes the first time it needs the board's fields."""
        return within(self.board_fields(), MESSAGES.roadmap.plan_conditions["fields_unread"])

    def card(self, subject: str) -> Requests:
        """One card by its node id: its fields, its job record and the GraphQL points left."""
        return [self.gh(board_card_args(_p("card_id")), "card", subject=subject)]

    def comments_on(self, subject: str) -> Requests:
        endpoint = gh.comments_endpoint(self.repo, _number(subject))
        return self.listing(endpoint, "comments", subject=subject)

    def issue(self, subject: str) -> Requests:
        return [self.gh(gh.issue_args(self.repo, _number(subject)), "issue", subject=subject)]

    def path_change(self, path: str) -> Requests:
        """The newest commit on the default branch that changed `path` (#2005)."""
        return [self.gh(gh.path_commits_args(self.repo, path), "path_change", subject=path)]

    def closures(self, subject: str) -> Requests:
        args = gh.closures_args(self.repo, _number(subject))
        return [self.gh(args, "closures", subject=subject)]

    def evidence(self, subject: str) -> Requests:
        """One read per piece of evidence, by its kind."""
        value = _p("evidence")
        texts = MESSAGES.roadmap
        kinds = (
            (gh.advisory_args(value), "advisory"),
            (gh.workflow_run_args(self.repo, value), "workflow_run"),
            (gh.commit_args(self.repo, value), "commit"),
        )
        repeat = texts.plan_repeat["evidence"]
        return [self.gh(args, key, subject=subject, repeat=repeat) for args, key in kinds]

    def budget(self) -> Requests:
        """The run's last request, once it has sent a GraphQL request: the GraphQL budget its
        spend line reports."""
        done = MESSAGES.roadmap.plan_conditions["done"]
        return [self.gh(graphql_budget_args(), "budget", condition=done)]

    # ── Writes ──

    def _edit(
        self, subject: str, field_name: str, change: Sequence[str], key: str
    ) -> PlannedRequest:
        """An `item-edit` of one card by node ids, which sends only the mutation."""
        args = gh.card_edit_args(_p("card_id"), _p("board_id"), _p("field_id"), change)
        return self.gh(args, key, subject=subject, field=field_name)

    def _record(self, subject: str) -> PlannedRequest:
        record = CONST_GH_PROJECT_JOB_RECORD_FIELD
        return self._edit(subject, record, ["--text", _p("record")], "record")

    def set_marks(self, subject: str) -> Requests:
        """The board's fields once a run, the card, then the job record."""
        return [*self.kept_fields(), *self.card(subject), self._record(subject)]

    def set_field(self, subject: str, field_name: str | None = None) -> Requests:
        """The board's fields once a run, the card, the job record, then the field by its
        option's id. `field_name` None stands for any board field."""
        change = ["--single-select-option-id", _p("option_id")]
        edit = self._edit(subject, field_name or _p("field"), change, "set_field")
        return [*self.kept_fields(), *self.card(subject), self._record(subject), edit]

    def comment(self, subject: str) -> Requests:
        args = gh.comment_args(self.repo, _number(subject), _p("comment"))
        return [self.gh(args, "comment", subject=subject)]

    def label_issue(self, subject: str) -> Requests:
        args = gh.label_args(self.repo, _number(subject), _p("label"))
        return [self.gh(args, "label", subject=subject)]

    def add_item(self, subject: str) -> Requests:
        """The issue, the add, which names the card, then that card, and its restore when it is
        archived (#1403)."""
        args = gh.item_add_args(self.owner, self.number, _p("url"))
        unarchive = gh.item_unarchive_args(self.owner, self.number, _p("card_id"))
        archived = MESSAGES.roadmap.plan_conditions["card_archived"]
        return [
            *self.issue(subject),
            self.gh(args, "add_item", subject=subject),
            *self.card(subject),
            self.gh(unarchive, "unarchive_card", condition=archived, subject=subject),
        ]

    def create_issue(self, subject: str, labels: Sequence[str] = ()) -> Requests:
        args = gh.create_issue_args(self.repo, _p("title"), _p("body"), labels)
        return [self.gh(args, "create_issue", subject=subject)]

    def write_issue_body(self, subject: str) -> Requests:
        args = gh.write_issue_body_args(self.repo, _number(subject), _p("body"))
        return [self.gh(args, "issue", subject=subject)]

    def close_as_duplicate(self, subject: str) -> Requests:
        stdin = gh.close_as_duplicate_request(_p("node_id"), _p("original_id"))
        return [
            self.gh(gh.GRAPHQL_INPUT_ARGS, "close_duplicate", stdin=stdin, subject=subject),
        ]


def _number(subject: str) -> str:
    """The issue number a subject such as `#7` names, or the subject itself as a placeholder."""
    return subject[1:] if subject.startswith("#") and subject[1:].isdigit() else subject


# ── The jobs ──────────────────────────────────────────────────────────────────


def _config(store: StoreRequests, ref: str | None) -> Requests:
    return store.file(CONST_ROADMAP_CONFIG_PATH, ref)


def refine_requests(
    repo: str,
    ref: str | None,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap refine` reads, in order, ending with its closing budget read,
    and the writes `--confirm` makes before that last read. Each item's comments are read for
    the replies since refine's last comment, and each open item a blocked item waits on is read
    for its state (#1758). A round without `--item` reads the newest commit of each path the
    block of a waiting item cites, when no reply ends the wait first (#2005)."""
    store = StoreRequests(repo, CONST_ROADMAP_REFINE_BOARD_FILTER)
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    target_item = f"#{item}" if item is not None else _p("item")
    blockers = within(store.issue(_p("blocker")), repeat=rep["blocker"])

    if item is not None:
        reads = [
            *_config(store, ref),
            *store.board_fields(),
            *store.card(target_item),
            *store.issue(target_item),
            *store.comments_on(target_item),
            *blockers,
        ]
        writes = [
            *store.write_issue_body(target_item),
            *store.set_field(target_item, field_name="Status"),
            *within(store.comment(target_item), cond["posted"]),
        ]
    else:
        each_milestone = rep["milestone"]
        each_candidate = rep["item"]
        reads = [
            *_config(store, ref),
            *store.board_fields(),
            *store.milestones(),
            *within(store.items(milestone=_p("milestone")), repeat=each_milestone),
            *store.backlog(),
            *within(
                [*store.issue(target_item), *store.comments_on(target_item)],
                repeat=each_candidate,
            ),
            *blockers,
            *within(
                store.path_change(_p("path")),
                cond["still_waiting"],
                repeat=rep["block_path"],
            ),
        ]
        writes = [
            *within(
                [
                    *store.write_issue_body(target_item),
                    *store.set_field(target_item, field_name="Status"),
                    *within(store.comment(target_item), cond["posted"]),
                ],
                repeat=each_candidate,
            )
        ]

    return (*reads, *store.budget()), tuple(writes)


def render_dry_run(
    job: str,
    repo: str,
    requests: Sequence[PlannedRequest],
    writes: Sequence[PlannedRequest] = (),
    *,
    writes_heading: str | None = None,
    notes: Sequence[str] = (),
) -> None:
    """Print a dry run: the requests a run makes, numbered in order, each with what it reads or
    writes above its exact command, then the writes `--confirm` adds, then the notes."""
    texts = MESSAGES.roadmap
    heading = "\n\n".join([texts.plan_dry_run_title.format(job=job, repo=repo), texts.plan_dry_run])
    shown = [*notes, *texts.plan_dry_run_notes]
    render_request_plan(heading, requests, () if writes else shown, described=True)
    if writes:
        heading = writes_heading or texts.plan_dry_run_writes
        render_request_plan(heading, writes, shown, described=True)


__all__ = [
    "StoreRequests",
    "is_page_repeat",
    "planned_gh",
    "planned_session_read",
    "refine_requests",
    "render_dry_run",
    "within",
]
