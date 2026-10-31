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

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS,
    CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL, DEFAULT_PYPI_PACKAGE_URL
from devops_cli.dry_run.requests import PlannedRequest, both, render_request_plan
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import github_store as gh
from devops_cli.roadmap.store import CloseReason

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
        return within(self._issues("state=all"), unread)

    def items(self, *, milestone: str | None = None) -> Requests:
        """Every Item, or the Items of the milestone numbered `milestone`, a placeholder."""
        if milestone is None:
            return self.every_issue()
        return self._issues(f"milestone={milestone}&state=all")

    def backlog(self) -> Requests:
        return self._issues("milestone=none&state=open")

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

    def comment(self, subject: str) -> Requests:
        args = gh.comment_args(self.repo, _number(subject), _p("comment"))
        return [self.gh(args, "comment", subject=subject)]

    def close(self, subject: str, reason: CloseReason, *, comment: bool) -> Requests:
        """The issue, which a close refuses when it is no open issue, then its comment when one
        is given, then one `PATCH` that closes it for `reason` (#1658)."""
        edit = self._edit(subject, "close", gh.issue_close(reason), reason=reason.value)
        return [*self.issue(subject), *(self.comment(subject) if comment else []), edit]

    def label_issue(self, subject: str) -> Requests:
        args = gh.label_args(self.repo, _number(subject), _p("label"))
        return [self.gh(args, "label", subject=subject)]

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
    from devops_cli.roadmap.github_store import milestone_edit_args

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
    from devops_cli.roadmap.github_store import milestone_edit_args

    target = int(_number(name)) if _number(name).isdigit() else 0
    store = StoreRequests(repo)
    reads = list(store.milestones())
    write = planned_gh(
        milestone_edit_args(repo, target, fields),
        f"repos/{repo}/milestones/{name}",
    )
    return [*reads, write]


# ── The jobs ──────────────────────────────────────────────────────────────────


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
    leaves alone the time of its newest comment, once for each such comment (#2475). Refine
    reads no repository file, so `ref` changes no request."""
    del ref
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    target_item = f"#{item}" if item is not None else _p("item")
    blockers = within(store.issue(_p("blocker")), repeat=rep["blocker"])

    if item is not None:
        reads = [
            *store.issue(target_item),
            *store.issue(target_item),
            *store.comments_on(target_item),
            *store.every_issue(),
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
            *store.milestones(),
            *within(store.items(milestone=_p("milestone")), repeat=each_milestone),
            *store.backlog(),
            *within(
                [
                    *store.issue(target_item),
                    *store.comments_on(target_item),
                    *store.every_issue(),
                ],
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
            ),
            *within(store.set_marks(target_item), cond["capped"], repeat=each_candidate),
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
    repository is private or no Firecrawl key is set. For each item it checks it reads the
    item's comments, runs the model, and makes the searches and fact reads the model asks for;
    `--item` names the item, and `limit` caps the items of a round, which `--limit` sets."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    cond, rep, methods = texts.plan_conditions, texts.plan_repeat, texts.plan_methods
    subject = f"#{item}" if item is not None else _p("item")
    each_item = rep["alternatives_item"]
    visibility = [store.gh(gh.is_private_args(repo), "visibility")]
    search = PlannedRequest(
        method=methods["search"],
        target=texts.plan_targets["web_search"].format(subject=subject),
        argv=("POST", DEFAULT_FIRECRAWL_SEARCH_URL),
        repeat=rep["search"].format(limit=CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES),
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
    reads = [
        *visibility,
        *store.every_issue(),
        *within([*store.comments_on(subject), model, search, *facts], cond["check_on"], each_item),
    ]
    writes = within(
        [
            *store.write_issue_body(subject),
            *store.set_marks(subject),
            *store.comment(subject),
        ],
        cond["check_on"],
        each_item,
    )
    return tuple(reads), tuple(writes)


def stage_requests(
    repo: str,
    *,
    item: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap stage` reads, in order, and the writes `--confirm` makes after them
    (#2654). The run updates its clone, reads every issue and the open issues that an item
    depends on, reads the branches of `origin` and the change folders of the default branch
    (#2714), and for each item asks the model, and validates the change. The model is asked
    again only when a task group is over the budget or the change fails its checks. Each run then
    fetches the staged branch of each closed item. The writes are the worktree, the commit and
    the push of each item, the draft pull request, the record and the comment, and the removal of
    the draft and the branch of a closed item. `limit` and `item` change no request: they change
    how many items the run repeats them for."""
    del limit
    store = StoreRequests(repo)
    texts = MESSAGES.roadmap
    req, cond, rep = texts.stage_requests, texts.stage_request_conditions, texts.plan_repeat
    clone, tree, branch, change = "<model-clone>", "<worktree>", _p("branch"), _p("change")
    each_item, each_closed = rep["stage_item"], rep["stage_closed"]

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
        git("fetch_branch", clone, "fetch", "-q", "origin", branch, repeat=each_closed),
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
            "worktree",
            clone,
            "worktree",
            "add",
            "--no-track",
            "-b",
            branch,
            tree,
            "origin/main",
            repeat=each_item,
        ),
        git("commit", tree, "add", "--", f"openspec/changes/{change}", repeat=each_item),
        git("commit", tree, "commit", "-q", "-m", _p("title"), repeat=each_item),
        git("push", tree, "push", "-q", "-u", "origin", branch, repeat=each_item),
        other("REST write", "pull", "POST", pulls),
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
            "--format=%an",
            f"origin/main..origin/{branch}",
            when=cond["staged"],
        ),
        other("GET", "pull_status", "GET", pulls, when=cond["staged"]),
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
        *within(store.set_field(target, "Status"), repeat=each_item),
        *within(store.set_marks(target), cond["clear_stop"], repeat=each_item),
        git("rebase", tree, "rebase", "origin/main"),
        other("model", "model_step", "model", repeat=each_group),
        git("commit", tree, "commit", "-m", _p("title"), repeat=each_group),
        other("process", "docs", "uv", "run", "devops", "docs", "generate", "--sync-readme"),
        git("commit", tree, "commit", "-m", _p("title"), when=cond["docs_commit"]),
        other("process", "archive", "uv", "run", "devops", "openspec", "archive", _p("change")),
        git("commit", tree, "commit", "-m", _p("title")),
        git(
            "push",
            tree,
            "push",
            f"--force-with-lease={branch}:{_p('remote_tip')}",
            "origin",
            branch,
            when=cond["staged"],
        ),
        git("push_new", tree, "push", "-u", "origin", new_branch, when=cond["planned"]),
        other(
            "REST write",
            "create_pull",
            "POST",
            f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/pulls",
            when=cond["planned"],
        ),
        other("REST write", "body", "PATCH", pulls),
        other("REST write", "pull_comment", "POST", f"{issues}/{_p('pull')}/comments"),
        other("process", "watch", "gh", "pr", "checks", _p("pull")),
        other("process", "run_log", "gh", "run", "view", "--log-failed", when=cond["run_log"]),
        other("model", "model_fix", "model", when=cond["model_fix"]),
        other("process", "ready", "gh", "pr", "ready", _p("pull"), when=cond["ready"]),
        *within(store.set_field(target, "Status"), repeat=each_item),
        *within(store.comment(target), repeat=each_item),
        git("remove_worktree", clone, "worktree", "remove", "--force", tree),
    ]
    return tuple(reads), tuple(writes)


def explain_requests(
    repo: str, *, item: int
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """What `devops roadmap explain` reads, in order (#2911). It makes no write and no model call.
    It reads what the plan of the implement job reads, which covers the clone, the issues, the
    branches and the change folders, and the open issue that a stage item depends on. The
    selections of both jobs read the same listing, so the list holds each read once."""
    reads, _ = implement_requests(repo, item=item)
    blockers = within(
        StoreRequests(repo).issue(_p("blocker")), repeat=MESSAGES.roadmap.plan_repeat["blocker"]
    )
    return (*reads, *blockers), ()


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
    "explain_requests",
    "implement_requests",
    "is_page_repeat",
    "milestones_close_requests",
    "milestones_edit_requests",
    "milestones_list_requests",
    "milestones_status_requests",
    "planned_gh",
    "planned_session_read",
    "refine_requests",
    "render_dry_run",
    "stage_requests",
    "within",
]
