"""The requests the roadmap jobs make, as a dry run lists them without making any (#412, #1125).

A dry run makes no request, reads included. It returns the job's real result type, marked as a
dry run, holding the requests a run makes in order as `PlannedRequest`s (#741): the exact `gh`
argv and stdin, built by the same argument builders `GitHubRoadmapStore` runs, so the plan
cannot drift from the run. A value that needs a read is a placeholder in angle brackets, a
request that runs only when something holds names that in `condition`, and a request a run makes
for each page, item or field says so in `repeat`.

`StoreRequests` gives the requests of each store operation; `render_requests`,
`reprioritize_requests` and `migrate_requests` put a job's operations in the order the job makes
them. A store reads the board's fields, and the listing of each filter, once (#1361), so an
operation that needs them lists their read under the condition that the run has not made it yet.
A board write lists the read of its one card and the edit by node ids; an add lists the read of
the card it names and that card's restore when it is archived. Every run of a job that sent a
GraphQL request, as every run that reads the board does, ends with one GraphQL budget read, for
its spend line, after any write; a run that sent none makes no budget read (#1400).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from devops_cli.config.constants import (
    CONST_AGENT_TASKS_DIR,
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_PROJECT_TEMPLATE_PATH,
    CONST_ROADMAP_CONFIG_PATH,
    CONST_ROADMAP_DOCUMENT_PATH,
    CONST_ROADMAP_MIGRATE_BOARD_FILTER,
    CONST_ROADMAP_OPEN_ITEMS_FILTER,
    CONST_ROADMAP_RENDER_BOARD_FILTER,
    CONST_ROADMAP_REPRIORITIZE_BOARD_FILTER,
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
from devops_cli.roadmap.store import IssueQuery

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


def is_page_repeat(repeat: str) -> bool:
    """Whether `repeat` is only a page repeat: the request runs at least once, then again per
    page. Any other repeat may run no time at all."""
    texts = MESSAGES.roadmap
    return repeat in (texts.plan_repeat_page, texts.intake_repeat_page)


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
        target = MESSAGES.roadmap.plan_targets[key].format(
            board=self.number, owner=self.owner, **values
        )
        return planned_gh(argv, target, stdin=stdin, condition=condition, repeat=repeat)

    # ── Reads ──

    def file(self, path: str, ref: str | None) -> Requests:
        at = ref or MESSAGES.roadmap.intake_placeholder_default_branch
        return [
            self.gh(gh.repository_file_args(self.repo, path, ref=ref), "file", path=path, ref=at)
        ]

    def listing(self, endpoint: str, key: str, **values: str) -> Requests:
        """A REST listing, a full page at a time until a page is short."""
        args = gh.listing_page_args(endpoint, _p("page"))
        return [self.gh(args, key, repeat=MESSAGES.roadmap.plan_repeat_page, **values)]

    def releases(self) -> Requests:
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

    def items(self, release: str | None = None) -> Requests:
        if release is None:
            return [*self.kept_board(), *self._issues("state=all")]
        query = f"milestone={_p('milestone')}&state=all"
        return [*self.kept_board(), *self.releases(), *self._issues(query)]

    def backlog(self) -> Requests:
        return [
            *self.kept_board(CONST_ROADMAP_OPEN_ITEMS_FILTER),
            *self._issues("milestone=none&state=open"),
        ]

    def issues(self) -> Requests:
        return self._issues("state=all")

    def board_fields(self, board: str | None = None) -> Requests:
        return [self.gh(gh.board_fields_args(self.owner, board or self.number), "fields")]

    def kept_fields(self) -> Requests:
        """The fields read a store makes the first time it needs the board's fields."""
        return within(self.board_fields(), MESSAGES.roadmap.plan_conditions["fields_unread"])

    def card(self, subject: str) -> Requests:
        """One card by its node id: its fields, its job record and the GraphQL points left."""
        return [self.gh(board_card_args(_p("card_id")), "card", subject=subject)]

    def workflows(self) -> Requests:
        return [self.gh(gh.board_workflows_args(self.owner, self.number), "workflows")]

    def find_board(self) -> Requests:
        return [self.gh(gh.project_list_args(self.owner), "boards")]

    def default_branch(self) -> Requests:
        return [self.gh(gh.default_branch_args(self.repo), "default_branch")]

    def release_pull_requests(self) -> Requests:
        args = gh.release_pull_requests_args(self.repo, _p("milestone"))
        return [*self.releases(), self.gh(args, "release_prs", release=_p("release"))]

    def merged_pull_requests(self, branch: str) -> Requests:
        texts = MESSAGES.roadmap
        merged = self.listing(
            gh.merged_pull_requests_endpoint(self.repo, branch), "merged_prs", branch=branch
        )
        files = self.listing(
            gh.pull_request_files_endpoint(self.repo, _p("number")),
            "pr_files",
            subject=_p("number"),
        )
        return [*merged, *within(files, repeat=texts.plan_repeat["merged"])]

    def pr_checks(self) -> Requests:
        from devops_cli.github.check_verdict import pr_checks_args

        args = pr_checks_args(_p("number"), self.repo)[1:]
        return [self.gh(args, "pr_checks", subject=_p("number"))]

    def release_published(self) -> Requests:
        args = gh.release_tag_args(self.repo, _p("tag"))
        return [self.gh(args, "release_published", release=_p("tag"))]

    def open_pull_requests(self) -> Requests:
        return [self.gh(gh.open_pull_requests_args(self.repo), "open_prs")]

    def status_changed_at(self, subject: str) -> Requests:
        args = gh.issue_status_args(self.repo, _number(subject))
        return [self.gh(args, "status_at", subject=subject)]

    def release_changes(self, subject: str) -> Requests:
        endpoint = gh.issue_events_endpoint(self.repo, _number(subject))
        return self.listing(endpoint, "events", subject=subject)

    def comments_on(self, subject: str) -> Requests:
        endpoint = gh.comments_endpoint(self.repo, _number(subject))
        return self.listing(endpoint, "comments", subject=subject)

    def dependencies(self, subject: str) -> Requests:
        endpoint = gh.dependencies_endpoint(self.repo, _number(subject))
        return self.listing(endpoint, "dependencies", subject=subject)

    def branch(self) -> Requests:
        args = gh.branch_ref_args(self.repo, _p("branch"))
        return [self.gh(args, "branch", branch=_p("branch"))]

    def issue(self, subject: str) -> Requests:
        return [self.gh(gh.issue_args(self.repo, _number(subject)), "issue", subject=subject)]

    def count_issues(self, query: IssueQuery, *, text: str | None = None) -> Requests:
        args = gh.issue_count_args(self.repo, query)
        shown = text or gh.issue_search_text(self.repo, query)
        return [self.gh(args, "count", query=shown)]

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

    def run_record(self) -> Requests:
        return self.kept_board()

    def budget(self) -> Requests:
        """The run's last request, once it has sent a GraphQL request: the GraphQL budget its
        spend line reports."""
        done = MESSAGES.roadmap.plan_conditions["done"]
        return [self.gh(graphql_budget_args(), "budget", condition=done)]

    # ── Writes ──

    def create_release(self) -> Requests:
        fields = [("title", _p("release")), ("description", ""), ("state", "open")]
        args = gh.milestone_args(self.repo, "POST", None, fields)
        return [*self.releases(), self.gh(args, "create_release", release=_p("release"))]

    def close_release(self) -> Requests:
        args = gh.milestone_args(self.repo, "PATCH", _p("milestone"), [("state", "closed")])
        return [*self.releases(), self.gh(args, "edit_release", release=_p("release"))]

    def delete_release(self) -> Requests:
        args = gh.milestone_args(self.repo, "DELETE", _p("milestone"))
        return [*self.releases(), self.gh(args, "delete_release", release=_p("release"))]

    def create_branch(self) -> Requests:
        args = gh.create_branch_args(self.repo, _p("branch"), _p("sha"))
        return [self.gh(args, "create_branch", branch=_p("branch"), sha=_p("sha"))]

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
        """The board's fields once a run, every milestone for a Release value, the card, the
        job record, then the field: the milestone for the Release, through REST. `field_name`
        None stands for either."""
        cond = MESSAGES.roadmap.plan_conditions
        release, other = cond["release_field"], cond["other_field"]
        listing = within(self.releases(), cond["release_named"])
        milestone = gh.issue_milestone_args(self.repo, _number(subject), _p("milestone"))
        patch = self.gh(milestone, "milestone", subject=subject)
        change = ["--single-select-option-id", _p("option_id")]
        edit = self._edit(subject, field_name or _p("field"), change, "set_field")
        head, card = self.kept_fields(), self.card(subject)
        if field_name == "Release":
            return [*head, *listing, *card, self._record(subject), patch]
        if field_name is not None:
            return [*head, *card, self._record(subject), edit]
        return [
            *head,
            *within(listing, release),
            *card,
            self._record(subject),
            *within([patch], release),
            *within([edit], other),
        ]

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

    def close_issue(self, subject: str, reason: str) -> Requests:
        args = gh.close_issue_args(self.repo, _number(subject), reason)
        return [
            *self.issue(subject),
            *self.comment(subject),
            self.gh(args, "close_issue", subject=subject),
        ]

    def close_as_duplicate(self, subject: str) -> Requests:
        stdin = gh.close_as_duplicate_request(_p("node_id"), _p("original_id"))
        return [
            self.gh(gh.GRAPHQL_INPUT_ARGS, "close_duplicate", stdin=stdin, subject=subject),
        ]

    def set_run_record(self) -> Requests:
        """The board's fields and items once a run, the card, or the card created when there is
        none, which nothing reads after, then the job record."""
        texts = MESSAGES.roadmap
        cond, run_record = texts.plan_conditions, texts.plan_targets["run_record"]
        create = self.gh(gh.run_record_card_args(self.owner, self.number), "create_card")
        edit = gh.card_edit_args(
            _p("card_id"), _p("board_id"), _p("field_id"), ["--text", _p("record")]
        )
        return [
            *self.kept_fields(),
            *self.kept_board(),
            *within(self.card(run_record), cond["run_card"]),
            *within([create], cond["no_card"]),
            self.gh(
                edit, "card_field", subject=run_record, field=CONST_GH_PROJECT_JOB_RECORD_FIELD
            ),
        ]

    def set_card_field(self) -> Requests:
        """The board's fields once a run, the card, then the field and the job record by node
        ids."""
        card, field_name = _p("card"), _p("field")
        change = ["--single-select-option-id", _p("option_id")]
        field_edit = gh.card_edit_args(_p("card_id"), _p("board_id"), _p("field_id"), change)
        record_edit = gh.card_edit_args(
            _p("card_id"), _p("board_id"), _p("field_id"), ["--text", _p("record")]
        )
        return [
            *self.kept_fields(),
            *self.card(card),
            self.gh(field_edit, "card_field", subject=card, field=field_name),
            self.gh(
                record_edit, "card_field", subject=card, field=CONST_GH_PROJECT_JOB_RECORD_FIELD
            ),
        ]

    def remove_card(self) -> Requests:
        """The card, then its removal."""
        args = gh.item_delete_args(self.owner, self.number, _p("card_id"))
        card = _p("card")
        return [*self.card(card), self.gh(args, "remove_card", subject=card)]

    def delete_field(self) -> Requests:
        args = gh.field_delete_args(_p("field_id"))
        return [*self.board_fields(), self.gh(args, "delete_field", field=_p("field"))]

    def create_board(self) -> Requests:
        texts = MESSAGES.roadmap
        new = _p("new_board")
        stdin = gh.create_field_request(_p("board_id"), _p("field"), _p("value"))
        return [
            self.gh(gh.project_create_args(self.owner, _p("title")), "create_board"),
            self.gh(gh.project_link_args(self.owner, new, self.repo), "link_board"),
            *self.board_fields(new),
            self.gh(
                gh.GRAPHQL_INPUT_ARGS,
                "create_field",
                stdin=stdin,
                repeat=texts.plan_repeat["field"],
            ),
        ]


def _number(subject: str) -> str:
    """The issue number a subject such as `#7` names, or the subject itself as a placeholder."""
    return subject[1:] if subject.startswith("#") and subject[1:].isdigit() else subject


# ── The jobs ──────────────────────────────────────────────────────────────────


def _config(store: StoreRequests, ref: str | None) -> Requests:
    return store.file(CONST_ROADMAP_CONFIG_PATH, ref)


def render_requests(repo: str, ref: str | None) -> tuple[PlannedRequest, ...]:
    """What `devops roadmap render` reads, in order, then its closing budget read."""
    store = StoreRequests(repo, CONST_ROADMAP_RENDER_BOARD_FILTER)
    each = MESSAGES.roadmap.plan_repeat["release"]
    return (
        *_config(store, ref),
        *store.board_fields(),
        *store.releases(),
        *within(store.items(release=_p("release")), repeat=each),
        *store.backlog(),
        *store.budget(),
    )


def reprioritize_requests(
    repo: str, ref: str | None
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap reprioritize` reads, in order, ending with its closing budget read,
    and the writes `--confirm` makes before that last read."""
    store = StoreRequests(repo, CONST_ROADMAP_REPRIORITIZE_BOARD_FILTER)
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    item = _p("item")
    reads = [
        *_config(store, ref),
        *store.board_fields(),
        *store.items(),
        *store.releases(),
        *within(
            [
                *store.release_changes(item),
                *store.status_changed_at(item),
                *store.comments_on(item),
            ],
            cond["pending"],
            rep["pending"],
        ),
        *store.default_branch(),
        *store.run_record(),
        *within(store.release_pull_requests(), cond["current"]),
        *within(store.release_published(), both(cond["current"], cond["merged"])),
        *within(
            [
                *store.dependencies(item),
                *store.open_pull_requests(),
                *store.status_changed_at(item),
                *store.release_changes(item),
            ],
            cond["judged"],
            rep["item"],
        ),
        *within(store.branch(), cond["starting"]),
    ]
    writes = [
        *within([*store.create_release(), *store.create_branch()], cond["starting"]),
        *within(
            [
                *store.comments_on(item),
                *store.status_changed_at(item),
                *store.release_changes(item),
                *store.set_marks(item),
                *store.set_field(item),
                *store.comment(item),
                *store.set_marks(item),
            ],
            cond["change"],
            rep["item"],
        ),
        *within(store.set_run_record(), cond["record"]),
        *within(store.close_release(), cond["closing"]),
    ]
    return (*reads, *store.budget()), tuple(writes)


def migrate_requests(
    repo: str, ref: str | None
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap migrate` reads, in order, ending with its closing budget read, and
    the writes `--confirm` makes before that last read."""
    store = StoreRequests(repo, CONST_ROADMAP_MIGRATE_BOARD_FILTER)
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    item = _p("item")
    reads = [
        *_config(store, ref),
        *store.file(CONST_PROJECT_TEMPLATE_PATH, ref),
        *store.file(CONST_ROADMAP_DOCUMENT_PATH, ref),
        *store.find_board(),
        *within(
            [*store.board_fields(), *store.board_read(), *store.items()],
            cond["board"],
        ),
        *store.issues(),
        *store.releases(),
        *within(store.workflows(), cond["board"]),
    ]
    each = rep["write"]
    writes = [
        *within(store.create_board(), cond["no_board"]),
        *within(store.delete_field(), cond["renamed"], each),
        *within(store.set_card_field(), cond["card"], each),
        *within(store.set_field(item), cond["unset"], each),
        *within(
            [*store.close_issue(item, "not_planned"), *store.remove_card()], cond["epic"], each
        ),
        *within([*store.set_field(item, "Release"), *store.delete_release()], cond["beyond"], each),
        *within(
            [*store.create_issue(_p("title")), *store.close_issue(_p("number"), "not_planned")],
            both(cond["not_planned"], cond["unfiled"]),
            each,
        ),
        *within(store.close_issue(item, "not_planned"), cond["not_planned"], each),
    ]
    return (*reads, *store.budget()), tuple(writes)


def close_requests(
    repo: str, ref: str | None
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap close` reads, in order, ending with its closing budget read, and
    the writes `--confirm` makes before that last read: the closes, then the cut (#743). It
    reads the merged pull requests of each closed Release that holds an open issue before the
    current release's (#1362)."""
    from devops_cli.commands.release import (
        _build_release_pr_command,
        milestone_issues_args,
        milestone_pull_requests_args,
    )
    from devops_cli.config.defaults import DEFAULT_RELEASE_LABEL

    store = StoreRequests(repo, CONST_ROADMAP_RENDER_BOARD_FILTER)
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    release, number = _p("release"), _p("number")
    branch, cut_branch = f"release/{release}", f"release/{release}"
    fragment = f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{number}.md"
    task = f"{CONST_AGENT_TASKS_DIR}/task-{number}-<slug>.md"

    def closes(into: str) -> Requests:
        return [
            *store.merged_pull_requests(into),
            *within(store.pr_checks(), cond["closes"], rep["merged"]),
            *within(store.file(task, _p("sha")), cond["task_file"], rep["closing"]),
        ]

    reads = [
        *_config(store, ref),
        *store.releases(),
        *within(store.issues(), cond["read_issues"]),
        *within(closes(f"release/{_p('shipped')}"), cond["shipped"], rep["shipped"]),
        *within(
            [
                *closes(branch),
                *within(
                    [
                        *store.release_pull_requests(),
                        *store.default_branch(),
                        *within(store.file(fragment, branch), repeat=rep["completed"]),
                    ],
                    cond["no_open"],
                ),
            ],
            cond["current"],
        ),
    ]
    pr_create = _build_release_pr_command(
        pr_title=f"feat(release): {release}",
        pr_body=_p("body"),
        base=_p("branch"),
        branch_name=cut_branch,
        draft=False,
        labels=DEFAULT_RELEASE_LABEL,
        milestone=release,
    )
    cut = [
        _git(texts.plan_targets["git_fetch"].format(branch=branch), "fetch", "origin", branch),
        *store.board_fields(),
        *store.releases(),
        *within(store.items(release=release), repeat=rep["release"]),
        *store.backlog(),
        _git(
            texts.plan_targets["git_push"].format(branch=cut_branch),
            *("push", "--force-with-lease", "-u", "origin", cut_branch),
        ),
        store.gh(milestone_issues_args(release), "milestone_issues", release=release),
        store.gh(milestone_pull_requests_args(release), "milestone_prs", release=release),
        store.gh(pr_create[1:], "pr_create", branch=cut_branch),
    ]
    writes = [
        *within(store.close_issue(_p("item"), "completed"), cond["closes"], rep["closing"]),
        *within(cut, cond["cut"]),
    ]
    return (*reads, *store.budget()), tuple(writes)


def _git(target: str, *args: str) -> PlannedRequest:
    """A git command against the clone's `origin`."""
    return PlannedRequest(method="git", target=target, argv=("git", *args))


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
    "close_requests",
    "is_page_repeat",
    "migrate_requests",
    "planned_gh",
    "render_dry_run",
    "render_requests",
    "reprioritize_requests",
    "within",
]
