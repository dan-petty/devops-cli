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
same for intake. A store reads the listing of every issue once (#1361), so an operation that
needs it lists its read under the condition that the run has not made it yet. A field or mark
write lists the read of its issue, then one `PATCH` of the issue's labels and body (ADR 0016).
No request reaches a project board.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from devops_cli.ai.web_search import first_configured_provider
from devops_cli.config.constants import (
    CONST_OPENSPEC_CONFIG_PATH,
    CONST_ROADMAP_ADR_DIRECTORY,
    CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS,
    CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.config.defaults import DEFAULT_DEPS_DEV_PROJECT_URL, DEFAULT_PYPI_PACKAGE_URL
from devops_cli.dry_run.requests import PlannedRequest, both, render_request_plan
from devops_cli.git.branch_authors import LOG_FORMAT
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stores import github_store as gh
from devops_cli.roadmap.stores.listing_snapshot import CHANGED_LISTING, FULL_LISTING
from devops_cli.roadmap.stores.store import CloseReason

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
    """The requests each `GitHubRoadmapStore` operation makes on `repo`."""

    repo: str

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
        return MESSAGES.roadmap.plan_targets[key].format(**values)

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

    def every_issue(self) -> Requests:
        """The listing of every issue, which a store reads the first time it needs it."""
        unread = MESSAGES.roadmap.plan_conditions["issues_unread"]
        return within(self._issues(FULL_LISTING), unread)

    def changed_issues(self) -> Requests:
        """The listing of the issues changed since the watermark of the snapshot, which a store
        with an incremental listing reads in place of every issue (#4448)."""
        unread = MESSAGES.roadmap.plan_conditions["issues_unread"]
        since = MESSAGES.roadmap.intake_placeholder_watermark
        return within(self._issues(CHANGED_LISTING.format(since=since)), unread)

    def items(self, *, milestone: str | None = None) -> Requests:
        """Every Item, or the Items of the milestone numbered `milestone`, a placeholder."""
        if milestone is None:
            return self.every_issue()
        return self._issues(f"milestone={milestone}&state=all")

    def backlog(self) -> Requests:
        return self._issues("milestone=none&state=open")

    def open_items(self) -> Requests:
        """The listing of the open issues, which `open_items` reads (#2915)."""
        return self._issues("state=open")

    def open_pulls(self) -> Requests:
        """The listing of the open pull requests (#2915)."""
        return self.listing(gh.pulls_endpoint(self.repo), "open_pulls")

    def check_runs(self) -> Requests:
        """The check runs of the head commit of each open draft of a job, one read for each
        draft (#3494). The commit is a placeholder, since the run learns it from the listing."""
        path = f"/repos/{self.repo}/commits/{_p('head_sha')}/check-runs?per_page=100"
        request = planned_session_read(
            path, self._target("check_runs"), repeat=MESSAGES.roadmap.plan_repeat_draft
        )
        return within([request], MESSAGES.roadmap.plan_conditions["job_drafts"])

    def repository_labels(self) -> Requests:
        """The listing of the labels of the repository (#2915)."""
        return self.listing(gh.labels_endpoint(self.repo), "repository_labels")

    def candidates(self) -> Requests:
        return self.every_issue()

    def issues(self) -> Requests:
        return self.every_issue()

    def comments_on(self, subject: str) -> Requests:
        endpoint = gh.comments_endpoint(self.repo, _number(subject))
        return self.listing(endpoint, "comments", subject=subject)

    def issue(self, subject: str) -> Requests:
        return [self.gh(gh.issue_args(self.repo, _number(subject)), "issue", subject=subject)]

    def issue_now(self, subject: str) -> Requests:
        """The read of an issue a write makes first: its labels and its job record now."""
        return [self.gh(gh.issue_args(self.repo, _number(subject)), "issue_now", subject=subject)]

    def path_change(self, path: str) -> Requests:
        """The newest commit on the default branch that changed `path` (#2005)."""
        return [self.gh(gh.path_commits_args(self.repo, path), "path_change", subject=path)]

    def closures(self, subject: str) -> Requests:
        args = gh.closures_args(self.repo, _number(subject))
        return [self.gh(args, "closures", subject=subject)]

    def renames(self, subject: str) -> Requests:
        """The title changes on the timeline of an issue (#3486)."""
        args = gh.renames_args(self.repo, _number(subject))
        return [self.gh(args, "renames", subject=subject)]

    def pull_title(self, subject: str, pull: str) -> Requests:
        """The read of the plan pull request of an item, through the issues endpoint."""
        return [self.gh(gh.issue_args(self.repo, _number(pull)), "pull_title", subject=subject)]

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

    # ── Writes ──

    def _edit(self, subject: str, key: str, stdin: str, **values: str) -> PlannedRequest:
        """One `PATCH` of an issue, its fields as JSON on stdin."""
        args = gh.issue_edit_args(self.repo, _number(subject))
        return self.gh(args, key, stdin=stdin, subject=subject, **values)

    def set_title(self, subject: str) -> Requests:
        """One `PATCH` that writes the title of an issue (#3486)."""
        return [self._edit(subject, "set_title", gh.issue_edit(title=_p("title")))]

    def set_marks(self, subject: str) -> Requests:
        """The issue now, then its body with the job record's marks."""
        edit = self._edit(subject, "record", gh.issue_edit(body=_p("record")))
        return [*self.issue_now(subject), edit]

    def set_field(self, subject: str, field_name: str | None = None) -> Requests:
        """The issue now, then its labels, the field's family replaced, and its body with the
        job record, in one write. `field_name` None stands for any field."""
        stdin = gh.issue_edit(labels=[_p("labels")], body=_p("record"))
        edit = self._edit(subject, "set_field", stdin, field=field_name or _p("field"))
        return [*self.issue_now(subject), edit]

    def write_status(self, subject: str) -> Requests:
        """The Status write of `status_sync.write_status`: the field write, then the read of the
        issue that checks the label (#5018)."""
        return [*self.set_field(subject, "Status"), *self.status_read_back(subject)]

    def status_read_back(self, subject: str) -> Requests:
        """The read of an issue after its Status write, which checks the label (#5018)."""
        args = gh.issue_args(self.repo, _number(subject))
        return [self.gh(args, "status_read_back", subject=subject)]

    def comment(self, subject: str, *, job: bool = True) -> Requests:
        """The comment. A comment that can be a roadmap job's (`job`) first reads the comments
        of the issue, and a repeat of a recent comment of the job does not post (#4793)."""
        args = gh.comment_args(self.repo, _number(subject), _p("comment"))
        post = [self.gh(args, "comment", subject=subject)]
        if not job:
            return post
        conditions = MESSAGES.roadmap.plan_conditions
        read = within(self.comments_on(subject), conditions["job_comment"])
        return [*read, *within(post, conditions["no_repeat"])]

    def close(self, subject: str, reason: CloseReason, *, comment: bool) -> Requests:
        """The issue, which a close refuses when it is no open issue, then its comment when one
        is given, then one `PATCH` that closes it for `reason` (#1658)."""
        edit = self._edit(subject, "close", gh.issue_close(reason), reason=reason.value)
        return [*self.issue(subject), *(self.comment(subject) if comment else []), edit]

    def label_issue(self, subject: str) -> Requests:
        args = gh.label_args(self.repo, _number(subject), _p("label"))
        return [self.gh(args, "label", subject=subject)]

    def unlabel_issue(self, subject: str) -> Requests:
        args = gh.unlabel_args(self.repo, _number(subject), _p("label"))
        return [self.gh(args, "unlabel", subject=subject)]

    def create_issue(self, subject: str, labels: Sequence[str] = ()) -> Requests:
        args = gh.create_issue_args(self.repo, _p("title"), _p("body"), labels)
        return [self.gh(args, "create_issue", subject=subject)]

    def add_sub_issue(self, parent: str, subject: str) -> Requests:
        args = gh.add_sub_issue_args(self.repo, _number(parent), _p("sub_issue_id"))
        return [self.gh(args, "add_sub_issue", subject=subject, parent=parent)]

    def write_issue_body(self, subject: str) -> Requests:
        """The issue now, for the job record it holds, then its new body with that record."""
        edit = self._edit(subject, "body", gh.issue_edit(body=_p("body")))
        return [*self.issue(subject), edit]


def _number(subject: str) -> str:
    """The issue number a subject such as `#7` names, or the subject itself as a placeholder."""
    return subject[1:] if subject.startswith("#") and subject[1:].isdigit() else subject


def milestones_list_requests(repo: str) -> list[PlannedRequest]:
    """Planned requests for listing milestones in a repository."""
    return list(StoreRequests(repo).milestones())


def milestones_status_requests(repo: str) -> list[PlannedRequest]:
    """Planned requests for inspecting milestone status."""
    return list(StoreRequests(repo).milestones())


def milestones_close_requests(repo: str, name: str) -> list[PlannedRequest]:
    """Planned requests for closing a milestone."""
    from devops_cli.roadmap.stores.github_store import milestone_edit_args

    target = int(_number(name)) if _number(name).isdigit() else 0
    store = StoreRequests(repo)
    reads = list(store.milestones())
    write = planned_gh(
        milestone_edit_args(repo, target, [("state", "closed")]),
        f"repos/{repo}/milestones/{name}",
    )
    return [*reads, write]


def milestones_edit_requests(
    repo: str,
    name: str,
    fields: Sequence[tuple[str, str]],
) -> list[PlannedRequest]:
    """Planned requests for editing a milestone."""
    from devops_cli.roadmap.stores.github_store import milestone_edit_args

    target = int(_number(name)) if _number(name).isdigit() else 0
    store = StoreRequests(repo)
    reads = list(store.milestones())
    write = planned_gh(
        milestone_edit_args(repo, target, fields),
        f"repos/{repo}/milestones/{name}",
    )
    return [*reads, write]


# ── The jobs ──────────────────────────────────────────────────────────────────


def _wait_reads(store: StoreRequests) -> Requests:
    """The reads that end the wait of an item that no reply follows (#2005, #3483): the newest
    commit of each path that its block cites or its wait text names, and, for a wait on a person,
    each issue that the wait text names and the timeline of each that is closed."""
    cond, rep = MESSAGES.roadmap.plan_conditions, MESSAGES.roadmap.plan_repeat
    named = _p("named_issue")
    each = rep["named_issue"].format(limit=CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS)
    return [
        *within(store.path_change(_p("path")), cond["still_waiting"], repeat=rep["block_path"]),
        *within(store.issue(named), cond["person_waiting"], repeat=each),
        *within(store.closures(named), cond["named_closed"], repeat=each),
    ]


def refine_requests(
    repo: str,
    ref: str | None,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap refine` reads, in order, and the writes `--confirm` makes after
    them. Each item's comments are read for the replies since refine's last comment, and each
    open item a blocked item waits on is read for its state (#1758). A round without `--item`
    reads the newest commit of each path the block of a waiting item cites, when no reply ends
    the wait first (#2005). A round records on each item that the cap on refine's comments
    leaves alone the time of its newest comment, once for each such comment (#2475). A round
    records on a waiting item the comments it read, when its job record does not hold them yet
    (#3667). A round reads
    the comments of each item that an account that the jobs do not trust opened, and writes one
    comment on it when none holds the marker of the notice (#3502). When a proposal defers a
    part, the plan holds the intake requests of one new candidate and the record of its number
    (#2423). Refine reads no repository file, so `ref` changes no request."""
    from devops_cli.roadmap.intake.intake_requests import planned_requests

    del ref
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    target_item = f"#{item}" if item is not None else _p("item")
    blockers = within(store.issue(_p("blocker")), repeat=rep["blocker"])
    part_reads, part_writes = planned_requests([_p("deferred_part")], repo=repo, ref=None, new=True)
    deferred_reads = within(part_reads, cond["deferred"])
    deferred_writes = within([*part_writes, *store.set_marks(target_item)], cond["deferred"])
    # A repeat that the store refuses records the time of the round as the start of the wait.
    comment_writes = [
        *within(store.comment(target_item), cond["posted"]),
        *within(store.set_marks(target_item), cond["repeat_refused"]),
    ]

    if item is not None:
        reads = [
            *store.issue(target_item),
            *store.issue(target_item),
            *store.comments_on(target_item),
            *store.every_issue(),
            *blockers,
            *deferred_reads,
        ]
        writes = [
            *deferred_writes,
            *store.write_status(target_item),
            *comment_writes,
        ]
    else:
        each_milestone = rep["milestone"]
        each_candidate = rep["item"]
        reads = [
            *store.milestones(),
            *within(store.items(milestone=_p("milestone")), repeat=each_milestone),
            *store.backlog(),
            *within(
                [
                    *store.issue(target_item),
                    *store.comments_on(target_item),
                    *store.every_issue(),
                    *deferred_reads,
                ],
                repeat=each_candidate,
            ),
            *within(
                store.comments_on(target_item),
                cond["outside_author"],
                repeat=rep["outside_item"],
            ),
            *blockers,
            *_wait_reads(store),
        ]
        writes = [
            *within(
                [
                    *deferred_writes,
                    *store.write_status(target_item),
                    *comment_writes,
                ],
                repeat=each_candidate,
            ),
            *within(store.set_marks(target_item), cond["capped"], repeat=each_candidate),
            *within(store.set_marks(target_item), cond["wait_unrecorded"], repeat=each_candidate),
            *within(store.comment(target_item), cond["outside_notice"], repeat=rep["outside_item"]),
        ]

    return tuple(reads), tuple(writes)


def alternatives_requests(
    repo: str,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap alternatives` reads, in order, and the writes `--confirm` makes after
    them (#2650). The run reads the repository's visibility and every issue, and stops when the
    repository is private or no search provider is configured. Once for the run it reads the
    directory of the ADRs and each file of it (#3505), and, when it checks an item that is no skip
    class, the SBOM of the repository (#4661). For each item it checks it reads the item's
    comments, runs the model, and makes the searches and fact reads the model asks for, and the
    deps.dev read of the project of a tool that the SBOM and the deployed paths do not hold;
    `--item` names the item, and `limit` caps the items of a round, which `--limit` sets."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    cond, rep, methods = texts.plan_conditions, texts.plan_repeat, texts.plan_methods
    subject = f"#{item}" if item is not None else _p("item")
    each_item = rep["alternatives_item"]
    visibility = [store.gh(gh.is_private_args(repo), "visibility")]
    # The first configured provider is the one that a search asks first. With none, the check is
    # off and the run makes no search.
    provider = first_configured_provider()
    search = (
        [
            PlannedRequest(
                method=methods["search"].format(provider=provider.name),
                target=texts.plan_targets["web_search"].format(subject=subject),
                argv=(provider.method, provider.url),
                repeat=rep["search"].format(limit=CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES),
            )
        ]
        if provider
        else []
    )
    fact_repeat = rep["fact"].format(limit=CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS)
    repository = _p("repository")
    facts = [
        store.gh(
            gh.repository_args(repository),
            "repository_facts",
            subject=repository,
            repeat=fact_repeat,
        ),
        store.gh(
            gh.latest_release_args(repository),
            "latest_release",
            subject=repository,
            repeat=fact_repeat,
        ),
        PlannedRequest(
            method=methods["pypi"],
            target=texts.plan_targets["pypi_package"].format(subject=_p("package")),
            argv=("GET", DEFAULT_PYPI_PACKAGE_URL.format(name=_p("package"))),
            repeat=fact_repeat,
        ),
    ]
    model = PlannedRequest(
        method=methods["model"],
        target=texts.plan_targets["model_run"].format(subject=subject),
    )
    adrs = within(
        [
            *store.file(CONST_ROADMAP_ADR_DIRECTORY, None),
            *within(
                store.file(f"{CONST_ROADMAP_ADR_DIRECTORY}/{_p('adr_file')}", None),
                repeat=rep["adr_file"],
            ),
        ],
        cond["check_on"],
    )
    sbom = store.gh(gh.sbom_args(repo), "sbom", condition=cond["inventory_read"])
    # The project key is one path segment, its `/` encoded, as the job sends it.
    owner, name = _p("owner"), _p("name")
    deps_dev = PlannedRequest(
        method=methods["deps_dev"],
        target=texts.plan_targets["deps_dev_project"].format(subject=f"github.com/{owner}/{name}"),
        argv=("GET", DEFAULT_DEPS_DEV_PROJECT_URL.format(project=f"github.com%2F{owner}%2F{name}")),
        condition=cond["deps_dev_read"],
    )
    reads = [
        *visibility,
        *store.every_issue(),
        *adrs,
        sbom,
        *within(
            [*store.comments_on(subject), model, *search, *facts, deps_dev],
            cond["check_on"],
            each_item,
        ),
    ]
    writes = within(
        [
            *store.set_marks(subject),
            *within(store.comment(subject), cond["check_changed"]),
        ],
        cond["check_on"],
        each_item,
    )
    return tuple(reads), tuple(writes)


def consolidate_requests(
    repo: str,
    *,
    limit: int | None = None,
    decline: str | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap consolidate` reads, in order, and the writes `--confirm` makes after
    them (#3740). A run reads the open issues and every issue, embeds the texts that the cache of
    vectors lacks, and reads the closes of each member of a shortlist. For each shortlist that no
    earlier plan judged, at most `--limit`, it asks the model twice: a proposal and a refutation.
    It resolves the commit and reads a file only when the model cites a path with a line. A run
    writes no GitHub change. `--decline` reads the issue of the anchor of the group and writes its
    job record, on `--confirm`."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    cond, rep, methods, targets = (
        texts.plan_conditions,
        texts.plan_repeat,
        texts.plan_methods,
        texts.plan_targets,
    )
    if decline is not None:
        return (
            tuple(store.issue_now(_p("item"))),
            tuple(store.set_marks(_p("item"))),
        )
    model = methods["model"]
    each_shortlist = rep["consolidate_shortlist"]
    reads = [
        *store.open_items(),
        *store.every_issue(),
        PlannedRequest(model, targets["consolidate_embed"], condition=cond["consolidate_embed"]),
        *within(store.closures(_p("item")), repeat=rep["consolidate_member"]),
        *within(
            [
                PlannedRequest(model, targets["consolidate_proposal"].format(subject=_p("item"))),
                PlannedRequest(model, targets["consolidate_refutation"]),
            ],
            repeat=each_shortlist,
        ),
        PlannedRequest(
            "git",
            targets["consolidate_resolve"],
            argv=("git", "rev-parse", "--verify", "<ref>^{commit}"),
            condition=cond["consolidate_cited"],
        ),
        PlannedRequest(
            "git",
            targets["consolidate_show"],
            argv=("git", "show", f"<commit>:{_p('path')}"),
            condition=cond["consolidate_cited"],
            repeat=rep["consolidate_citation"],
        ),
    ]
    return tuple(reads), ()


def retitle_requests(
    repo: str,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap retitle` reads, in order, and the writes `--confirm` makes after them
    (#3486). The run reads every issue. For each item with a long title it reads the comments and
    the title changes of the item, then the title of its plan pull request when the item is
    Planned, or runs the model when it is not. An item that the run leaves gets one write of the
    body with the skip mark (#4038), and the next run does not read it again. `--item` names the
    item, and `limit` caps the items of a run."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    cond, rep, methods = texts.plan_conditions, texts.plan_repeat, texts.plan_methods
    subject = f"#{item}" if item is not None else _p("item")
    each_item = rep["retitle_item"]
    model = PlannedRequest(
        method=methods["model"],
        target=texts.plan_targets["model_run"].format(subject=subject),
    )
    reads = [
        *store.every_issue(),
        *within(
            [*store.comments_on(subject), *store.renames(subject)],
            repeat=each_item,
        ),
        *within(store.pull_title(subject, _p("pull")), cond["planned"], each_item),
        *within([model], cond["unplanned"], each_item),
    ]
    writes = [
        *within([*store.set_title(subject), *store.comment(subject)], cond["retitled"], each_item),
        *within(store.set_marks(subject), cond["retitle_skipped"], each_item),
    ]
    return tuple(reads), tuple(writes)


def _openspec_config_read(clone: str) -> PlannedRequest:
    """The read of whether the default branch holds `openspec/config.yaml` (#4629): with no file,
    the stage job holds every item."""
    return PlannedRequest(
        "git",
        MESSAGES.roadmap.stage_requests["openspec_config"],
        argv=(
            "git",
            "-C",
            clone,
            "ls-tree",
            "--name-only",
            "origin/main",
            "--",
            CONST_OPENSPEC_CONFIG_PATH,
        ),
    )


def stage_requests(
    repo: str,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap stage` reads, in order, and the writes `--confirm` makes after them
    (#2654). The run updates its clone, reads every issue and the open issues that an item
    depends on, reads the branches of `origin` and the change folders of the default branch
    (#2714), moves the clone to the staged commit when the round selects an item (#3301), reads
    the tracked files of the clone (#3010) and the tasks of each open plan (#3418), and for each
    item asks the model, and validates the change. The model is asked again only when a task group
    is over the budget, a path of the plan is no file, or the change fails its checks. Each run
    then fetches the staged branch of each closed item. The writes are the worktree, which starts
    at the staged commit, the commit and the push of each item, the draft pull request, the record and the comment, and the removal of
    the draft and the branch of a closed item. `limit` and `item` change no request: they change
    how many items the run repeats them for."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    req, cond, rep = texts.stage_requests, texts.stage_request_conditions, texts.plan_repeat
    clone, tree, branch, change = "<model-clone>", "<worktree>", _p("branch"), _p("change")
    each_item, each_closed = rep["stage_item"], rep["stage_closed"]
    each_rejected = rep["stage_rejected"]

    def git(key: str, cwd: str, *args: str, when: str = "", repeat: str = "") -> PlannedRequest:
        return PlannedRequest(
            "git", req[key], argv=("git", "-C", cwd, *args), condition=when, repeat=repeat
        )

    def other(method: str, key: str, *argv: str, when: str = "") -> PlannedRequest:
        return PlannedRequest(method, req[key], argv=argv, condition=when, repeat=each_item)

    pulls = f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/pulls"
    reads = [
        git("update_clone", clone, "fetch", "--prune", "origin"),
        *store.every_issue(),
        *(store.issue(f"#{item}") if item is not None else []),
        *within(store.issue(_p("blocker")), repeat=rep["blocker"]),
        git("remote_heads", clone, "ls-remote", "--heads", "origin"),
        git("fetch_default", clone, "fetch", "-q", "origin", "main"),
        git(
            "default_plans",
            clone,
            "ls-tree",
            "--name-only",
            "origin/main",
            "openspec/changes/",
            "openspec/changes/archive/",
        ),
        _openspec_config_read(clone),
        planned_session_read(
            f"/repos/{repo}/pulls/{_p('pull')}",
            req["plan_state"],
            condition=cond["plan_state"],
            repeat=rep["stage_plan"],
        ),
        *within(store.comments_on(_p("pull")), cond["rejected_comments"], repeat=each_rejected),
        git("fetch_branch", clone, "fetch", "-q", "origin", branch, repeat=each_rejected),
        *within(
            store.path_change(_p("path")),
            cond["rejected_path"],
            repeat=rep["stage_rejected_path"].format(limit=CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS),
        ),
        git(
            "move_clone",
            clone,
            "merge",
            "--ff-only",
            "-q",
            "<staged commit>",
            when=cond["move_clone"],
        ),
        git("tracked_files", clone, "ls-files", "-z", when=cond["tracked_files"]),
        PlannedRequest(
            "GraphQL read",
            req["open_pulls"],
            argv=("POST", f"{CONST_URL_GITHUB_API_BASE}/graphql"),
            condition=cond["open_pulls"],
            repeat=each_item,
        ),
        git(
            "open_plan",
            clone,
            "show",
            f"origin/main:openspec/changes/{change}/tasks.md",
            when=cond["open_plan"],
            repeat=rep["open_plan"],
        ),
        git("fetch_branch", clone, "fetch", "-q", "origin", branch, repeat=each_closed),
        *within(store.open_pulls(), cond["orphan_pulls"]),
        *within(store.comments_on(_p("item")), cond["rejected_reason"], repeat=each_item),
        PlannedRequest("model", req["model_change"], repeat=each_item),
        PlannedRequest(
            "model", req["model_split"], condition=cond["model_split"], repeat=each_item
        ),
        PlannedRequest(
            "model", req["model_correction"], condition=cond["model_correction"], repeat=each_item
        ),
        other(
            "process", "validate", "openspec", "validate", change, "--strict", when=cond["validate"]
        ),
    ]
    writes = [
        PlannedRequest(
            "REST write",
            req["close_pull"],
            argv=("PATCH", f"{pulls}/{_p('pull')}"),
            condition=cond["close_pull"],
            repeat=each_closed,
        ),
        git(
            "delete_branch",
            clone,
            "push",
            "origin",
            "--delete",
            branch,
            when=cond["delete_branch"],
            repeat=each_closed,
        ),
        *within(store.set_marks(_p("item")), cond["close_pull"], repeat=each_closed),
        git(
            "delete_rejected",
            clone,
            "push",
            f"--force-with-lease=refs/heads/{branch}:{_p('remote_tip')}",
            "origin",
            f":refs/heads/{branch}",
            when=cond["delete_rejected"],
            repeat=each_rejected,
        ),
        *within(store.comment(_p("item")), repeat=each_rejected),
        *within(store.write_status(_p("item")), repeat=each_rejected),
        git(
            "worktree",
            clone,
            "worktree",
            "add",
            "--no-track",
            "-b",
            branch,
            tree,
            "<staged commit>",
            repeat=each_item,
        ),
        *within(store.set_marks(_p("item")), repeat=each_item),
        git("commit", tree, "add", "--", f"openspec/changes/{change}", repeat=each_item),
        git("commit", tree, "commit", "-q", "-m", _p("title"), repeat=each_item),
        git("push", tree, "push", "-q", "-u", "origin", branch, repeat=each_item),
        other("REST write", "pull", "POST", pulls),
        *within(store.file(CONST_ROADMAP_LABELS_PATH, None), repeat=each_item),
        *within(store.label_issue(_p("pull")), repeat=each_item),
        git(
            "delete_failed",
            clone,
            "push",
            "origin",
            "--delete",
            branch,
            when=cond["delete_failed"],
            repeat=each_item,
        ),
        *within(store.set_marks(_p("item")), repeat=each_item),
        *within(store.comment(_p("item")), repeat=each_item),
    ]
    return tuple(reads), tuple(writes)


def fix_plan_requests(
    repo: str, *, item: int | None = None
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap step fix-plan` reads, in order, and the writes `--confirm` adds after
    them (#5061, #5213). The run reads every issue and the plan pull request of each Staged item
    until one qualifies. With `--confirm`, the attempt fetches the default branch and the branch of
    the plan, checks the head and its authors, and reads the change folder at the head before the
    attempt marks. A plan that the reader refuses gets only `fix_plan.at` and `fix_plan.result`.
    Else the attempt moves the clone to the default branch, reads the open findings of the last
    plan comment of the item, reads the open plans on the default branch when the premise cites a
    missing path, and calls the review and the planner. The writes are the attempt marks, the
    commit on the default branch, its push with a lease, the title and the body of the pull
    request, the label, the comment and the result marks. `item` changes no request: it names the
    one item to judge."""
    del item
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    req, cond = texts.fix_plan_requests, texts.fix_plan_request_conditions
    each = texts.plan_repeat["fix_plan_item"]
    clone, tree, branch = "<model-clone>", "<worktree>", _p("branch")
    pull = f"/repos/{repo}/pulls/{_p('pull')}"
    attempt = cond["attempt"]
    review = cond["review"]

    def git(key: str, cwd: str, *args: str, when: str = attempt) -> PlannedRequest:
        return PlannedRequest("git", req[key], argv=("git", "-C", cwd, *args), condition=when)

    reads = [
        *store.every_issue(),
        planned_session_read(pull, req["pull_state"], repeat=each),
        git("fetch", clone, "fetch", "-q", "origin", "main", branch),
        git("tip", clone, "rev-parse", f"origin/{branch}"),
        git("identity", clone, "config", "user.name"),
        git("authors", clone, "log", "origin/main.." + f"origin/{branch}"),
        git("tree", clone, "ls-tree", "-r", "--name-only", "-z", "<head>"),
        git("show", clone, "show", f"<head>:openspec/changes/{_p('change')}/<file>"),
        *within(store.comments_on(_p("item")), cond["marks"]),
        git("move_clone", clone, "merge", "--ff-only", "-q", "<default head>", when=cond["marks"]),
        PlannedRequest(
            "GraphQL read",
            req["open_pulls"],
            argv=("POST", f"{CONST_URL_GITHUB_API_BASE}/graphql"),
            condition=cond["open_pulls"],
        ),
        git(
            "open_plans",
            clone,
            "ls-tree",
            "--name-only",
            "origin/main",
            "openspec/changes/",
            "openspec/changes/archive/",
            when=cond["open_plans"],
        ),
        git(
            "open_tasks",
            clone,
            "show",
            "origin/main:openspec/changes/<open change>/tasks.md",
            when=cond["open_plans"],
        ),
        PlannedRequest("model", req["model_review"], condition=review),
        PlannedRequest("model", req["model_repair"], condition=cond["repair"]),
        PlannedRequest(
            "process",
            req["validate"],
            argv=("openspec", "validate", _p("change"), "--strict"),
            condition=cond["validate"],
        ),
    ]
    push = cond["push"]
    writes = [
        *within(store.set_marks(_p("item")), cond["unreadable"]),
        *within(store.set_marks(_p("item")), cond["marks"]),
        git("worktree", clone, "worktree", "add", "--detach", tree, "origin/main", when=push),
        git("commit", tree, "commit", "-q", "-m", _p("title"), when=push),
        git("rebase", tree, "rebase", "-q", "origin/main", when=push),
        git(
            "push",
            tree,
            "push",
            "-q",
            f"--force-with-lease=refs/heads/{branch}:<head>",
            "origin",
            f"HEAD:refs/heads/{branch}",
            when=push,
        ),
        PlannedRequest(
            "REST write",
            req["update_pull"],
            argv=("PATCH", f"{CONST_URL_GITHUB_API_BASE}{pull}"),
            condition=cond["update_pull"],
        ),
        *within(store.unlabel_issue(_p("pull")), cond["unlabel"]),
        *within(store.comment(_p("item")), cond["comment"]),
        *within(store.set_marks(_p("item")), cond["marks"]),
    ]
    return tuple(reads), tuple(writes)


def implement_requests(
    repo: str,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap implement` reads, in order, and the writes `--confirm` makes after
    them (#2665, #2714). The run updates its clone, reads every issue, the comments of an item
    with a stop, the branches of `origin` and the change folders of the default branch. For a
    Staged item it reads the commit authors of the branch and the state of its pull request. For a
    Planned item it reads the tasks of its change. The writes are, for each item, the worktree
    (on the staged branch, or on a new branch at the default branch), the Status, the rebase, one
    model step for each task group, the documentation and the archive, the push (for a Planned
    item the first push, then the draft pull request), the title and the body and the comment of
    the pull request, the watch of its checks, one fix step when a check fails, `gh pr ready`, the
    Status and the record, and the comment on the issue. `limit` and `item` change no request:
    they change how many items the run repeats them for."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    req, cond, rep = texts.implement_requests, texts.implement_request_conditions, texts.plan_repeat
    clone, tree, branch = "<model-clone>", "<worktree>", _p("branch")
    new_branch = _p("new_branch")
    each_item, each_group = rep["implement_item"], rep["implement_group"]
    pulls = f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/pulls/{_p('pull')}"
    issues = f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/issues"
    target = f"#{item}" if item is not None else _p("item")
    # A push of the job runs in a new git folder that reads no configuration of the clone (GHSA).
    origin_git = ("git", f"--git-dir={_p('git_folder')}", "push", "--quiet", "--no-verify")

    def git(
        key: str, cwd: str, *args: str, when: str = "", repeat: str = each_item
    ) -> PlannedRequest:
        return PlannedRequest(
            "git", req[key], argv=("git", "-C", cwd, *args), condition=when, repeat=repeat
        )

    def other(
        method: str, key: str, *argv: str, when: str = "", repeat: str = each_item
    ) -> PlannedRequest:
        return PlannedRequest(method, req[key], argv=argv, condition=when, repeat=repeat)

    reads = [
        PlannedRequest(
            "git",
            req["update_clone"],
            argv=("git", "-C", clone, "fetch", "--prune", "origin"),
        ),
        *store.every_issue(),
        *(store.issue(target) if item is not None else []),
        *within(store.comments_on(target), cond["comments"], repeat=each_item),
        PlannedRequest(
            "git", req["remote_heads"], argv=("git", "-C", clone, "ls-remote", "--heads", "origin")
        ),
        git("fetch_default", clone, "fetch", "-q", "origin", "main", repeat=""),
        git(
            "default_plans",
            clone,
            "ls-tree",
            "--name-only",
            "origin/main",
            "openspec/changes/",
            "openspec/changes/archive/",
            repeat="",
        ),
        git(
            "planned_tasks",
            clone,
            "show",
            f"origin/main:openspec/changes/{_p('change')}/tasks.md",
            when=cond["planned"],
        ),
        git("fetch_branch", clone, "fetch", "-q", "origin", branch, when=cond["staged"]),
        git(
            "authors",
            clone,
            "log",
            LOG_FORMAT,
            f"origin/main..origin/{branch}",
            when=cond["staged"],
        ),
        other("GET", "pull", "GET", pulls, when=cond["staged"]),
        *store.file(CONST_ROADMAP_LABELS_PATH, None),
    ]
    writes = [
        git(
            "worktree",
            clone,
            "worktree",
            "add",
            "--track",
            "-b",
            branch,
            tree,
            f"origin/{branch}",
            when=cond["staged"],
        ),
        git(
            "worktree_new",
            clone,
            "worktree",
            "add",
            "--no-track",
            "-b",
            new_branch,
            tree,
            "origin/main",
            when=cond["planned"],
        ),
        *within(store.write_status(target), repeat=each_item),
        *within(store.set_marks(target), cond["clear_stop"], repeat=each_item),
        git("rebase", tree, "rebase", "origin/main"),
        other("model", "model_step", "model", repeat=each_group),
        other("model", "model_split", "model", when=cond["split"], repeat=each_item),
        git("commit", tree, "commit", "-m", _p("title"), repeat=each_group),
        git("amend", tree, "commit", "-m", _p("title"), when=cond["amend"], repeat=each_group),
        *within(store.comment(target), cond["return"], repeat=each_item),
        *within(store.write_status(target), cond["return"], repeat=each_item),
        other("process", "docs", "uv", "run", "devops", "docs", "generate"),
        git("commit", tree, "commit", "-m", _p("title"), when=cond["docs_commit"]),
        other("process", "archive", "uv", "run", "devops", "openspec", "archive", _p("change")),
        git("commit", tree, "commit", "-m", _p("title")),
        other(
            "git",
            "push",
            *origin_git,
            f"--force-with-lease=refs/heads/{branch}:{_p('remote_tip')}",
            _p("origin_url"),
            f"{_p('tip')}:refs/heads/{branch}",
            when=cond["staged"],
        ),
        other(
            "git",
            "push_new",
            *origin_git,
            _p("origin_url"),
            f"{_p('tip')}:refs/heads/{new_branch}",
            when=cond["planned"],
        ),
        other(
            "REST write",
            "create_pull",
            "POST",
            f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/pulls",
            when=cond["planned"],
        ),
        other("REST write", "body", "PATCH", pulls),
        other("REST write", "pull_comment", "POST", f"{issues}/{_p('pull')}/comments"),
        *within(store.label_issue(_p("pull")), repeat=each_item),
        *within(store.unlabel_issue(_p("pull")), cond["unlabel"], repeat=each_item),
        other("process", "watch", "gh", "pr", "checks", _p("pull")),
        other("process", "run_log", "gh", "run", "view", "--log-failed", when=cond["run_log"]),
        other("model", "model_fix", "model", when=cond["model_fix"]),
        other("process", "ready", "gh", "pr", "ready", _p("pull"), when=cond["ready"]),
        *within(store.write_status(target), repeat=each_item),
        *within(store.comment(target), repeat=each_item),
        git("remove_worktree", clone, "worktree", "remove", "--force", tree),
    ]
    return tuple(reads), tuple(writes)


def explain_requests(
    repo: str, *, item: int, trace: bool = False
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap explain` reads, in order (#2911). It makes no write and no model call.
    It reads what the plan of the implement job reads, which covers the clone, the issues, the
    branches and the change folders, whether the default branch holds `openspec/config.yaml`
    (#4629), and the open issue that a stage item depends on. The command reads the heads of
    `origin` and the plans once and gives them to both jobs, so the list holds each read once.
    With `trace` it reads the one issue and nothing else (#3032)."""
    if trace:
        return tuple(StoreRequests(repo).issue(f"#{item}")), ()
    reads, _ = implement_requests(repo, item=item)
    store = StoreRequests(repo)
    blockers = within(store.issue(_p("blocker")), repeat=MESSAGES.roadmap.plan_repeat["blocker"])
    refine = [*store.comments_on(f"#{item}"), *_wait_reads(store)]
    return (*reads, _openspec_config_read("<model-clone>"), *blockers, *refine), ()


def plan_recheck_requests(
    repo: str, branch: str | None = None
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap plan-recheck` reads, in order (#3492): the default branch of the
    clone, the files of the change folders, the open issues, and the issue of each folder that is
    not open. With `branch`, a ref of the clone, it also reads the files of that ref (#3498). It
    makes no write and calls no model."""
    texts = MESSAGES.roadmap
    clone = "<model-clone>"
    store = StoreRequests(repo)
    git_reads = [
        PlannedRequest(
            "git",
            texts.plan_recheck_request_fetch,
            argv=("git", "-C", clone, "fetch", "-q", "origin", "main"),
        ),
        PlannedRequest(
            "git",
            texts.plan_recheck_request_tree,
            argv=("git", "-C", clone, "ls-tree", "-r", "--name-only", "origin/main"),
        ),
        PlannedRequest(
            "git",
            texts.plan_recheck_request_files,
            argv=(
                "git",
                "-C",
                clone,
                "show",
                f"origin/main:openspec/changes/{_p('change')}/<file>",
            ),
            repeat=texts.plan_repeat["recheck_folder"],
        ),
    ]
    if branch is not None:
        git_reads += [
            PlannedRequest(
                "git",
                texts.plan_recheck_request_branch_tree,
                argv=("git", "-C", clone, "ls-tree", "-r", "--name-only", branch),
            ),
            PlannedRequest(
                "git",
                texts.plan_recheck_request_branch_files,
                argv=(
                    "git",
                    "-C",
                    clone,
                    "show",
                    f"{branch}:openspec/changes/{_p('change')}/<file>",
                ),
                repeat=texts.plan_repeat["recheck_folder"],
            ),
        ]
    closed = within(
        store.issue(_p("item")),
        texts.plan_recheck_request_closed_condition,
        repeat=texts.plan_repeat["recheck_folder"],
    )
    return (*git_reads, *store.open_items(), *closed), ()


def inbox_requests(
    repo: str,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap inbox` reads, in order (#2915). It reads the open issues, the open
    pull requests, the labels of the repository and `.github/labels.yml` on the default branch,
    and the newest commit that changed that file only when the labels differ. It reads the check
    runs of the head commit of each open draft of a job, one read for each draft (#3494). It
    reads the listing of every issue never, makes no write and calls no model."""
    store = StoreRequests(repo)
    differ = MESSAGES.roadmap.plan_conditions["labels_differ"]
    reads = [
        *store.open_items(),
        *store.open_pulls(),
        *store.repository_labels(),
        *store.file(CONST_ROADMAP_LABELS_PATH, None),
        *within(store.path_change(CONST_ROADMAP_LABELS_PATH), differ),
        *store.check_runs(),
    ]
    return tuple(reads), ()


def repair_requests(
    repo: str,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap repair` reads, in order, and the writes `--confirm` makes after them
    (#3478). It reads the open issues once and the comments of each item whose record names the
    next step `ready` or `person`. For a listed item, `--confirm` reads the issue again, then sets
    the Status Ready or writes the body without the refine section and clears the refine marks.
    It calls no model."""
    store = StoreRequests(repo)
    target = _p("item")
    each = MESSAGES.roadmap.plan_repeat["item"]
    reads = [
        *store.open_items(),
        *within(store.comments_on(target), repeat=each),
        *within(store.issue(target), repeat=each),
    ]
    writes = within(
        [
            *store.write_status(target),
            *store.write_issue_body(target),
            *store.set_marks(target),
        ],
        repeat=each,
    )
    return tuple(reads), tuple(writes)


def onboard_requests(
    repo: str,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap onboard` reads, in order, and the writes `--confirm` makes after
    them (#1359). It reads the repository, the App installation listing when acting as the App,
    .github/labels.yml, the repository labels, and .github/workflows/clear-status.yml.
    With --confirm, it creates missing labels with POST."""
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    reads = [
        planned_session_read(f"/repos/{repo}", repo),
        planned_session_read(
            "/installation/repositories",
            repo,
            condition=texts.plan_conditions["as_app"],
        ),
        *store.file(CONST_ROADMAP_LABELS_PATH, None),
        *store.repository_labels(),
        *store.file(".github/workflows/clear-status.yml", None),
    ]
    writes = [
        PlannedRequest(
            method=f"REST {texts.intake_request_write}",
            target=texts.plan_targets["create_label"].format(label=_p("label")),
            argv=("POST", f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/labels"),
            repeat=texts.plan_repeat["missing_label"],
        )
    ]
    return tuple(reads), tuple(writes)


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
    "alternatives_requests",
    "consolidate_requests",
    "explain_requests",
    "fix_plan_requests",
    "implement_requests",
    "inbox_requests",
    "is_page_repeat",
    "milestones_close_requests",
    "milestones_edit_requests",
    "milestones_list_requests",
    "milestones_status_requests",
    "onboard_requests",
    "plan_recheck_requests",
    "planned_gh",
    "planned_session_read",
    "refine_requests",
    "render_dry_run",
    "retitle_requests",
    "stage_requests",
    "within",
]
