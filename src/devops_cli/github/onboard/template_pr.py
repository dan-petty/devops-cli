"""Rows 9 and 11: the template pull request, its checks, its ready mark and its merge (D3).

Row 9 adds only the template files that the repository lacks. A file that the repository holds
with other text stays: after the first render the repository owns its files, and the copier manager
of Renovate brings each new tag of the template. The row writes the files to `TEMPLATE_BRANCH` with
the Git data API, in one tree and one commit, opens the draft pull request (AGENTS.md rule 6), and
waits for the check runs of its head. A repository that holds each file gives row 10 the check
runs of the head of its open template pull request. A merged or closed template pull request gives
row 10 no check: its head ran the workflows of that time, and the first confirmed run already wrote
its checks into the live ruleset (#7476). Row 11 marks the pull request ready and turns on
auto-merge with the head that the checks ran on. When GitHub has nothing to wait for, it merges the
pull request at once, as `gh pr merge --auto` does, so the run of the person starts the merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlencode

from devops_cli.core import clock
from devops_cli.github.client import missing_pull_reviewers
from devops_cli.github.onboard.model import DOC_MERGE, PersonStep, Row, RowContext, RowState
from devops_cli.github.onboard.routes import TEMPLATE_BRANCH

if TYPE_CHECKING:
    from devops_cli.github.onboard.baseline import Baseline
    from devops_cli.github.onboard.routes import RouteWriter
    from devops_cli.github.session import GitHubSession

TEMPLATE_PULL_TITLE: Final[str] = "ci: add the files of the repository template"
_TEMPLATE_PULL_BODY: Final[str] = (
    "Add the files of the repository template of {template} at {ref} that this repository does not "
    "hold yet. `devops repos onboard` renders the template with Copier and keeps each file that "
    "the repository already holds. Renovate brings each new tag of the template with `copier "
    "update`."
)
_FILE_MODE: Final[str] = "100644"
# The check runs of a new pull request start within a minute and end within a few on GitHub's
# runners; a wait past this bound leaves the row waiting, and the next run goes on.
_CHECKS_WAIT_SECONDS: Final[float] = 900.0
_CHECKS_POLL_SECONDS: Final[float] = 15.0
_PASSED_CONCLUSIONS: Final[frozenset[str]] = frozenset({"success", "neutral", "skipped"})
# The merge states in which GitHub has nothing to wait for, so auto-merge has nothing to start
# (`gh pr merge --auto` merges at once in these states).
_MERGEABLE_NOW: Final[frozenset[str]] = frozenset({"CLEAN", "HAS_HOOKS", "UNSTABLE"})
_READY_MUTATION: Final[str] = (
    "mutation($id: ID!) { markPullRequestReadyForReview(input: {pullRequestId: $id}) "
    "{ pullRequest { isDraft } } }"
)
_AUTO_MERGE_MUTATION: Final[str] = (
    "mutation($id: ID!, $head: GitObjectID!) { enablePullRequestAutoMerge(input: "
    "{pullRequestId: $id, mergeMethod: SQUASH, expectedHeadOid: $head}) "
    "{ pullRequest { autoMergeRequest { mergeMethod } } } }"
)
_MERGE_MUTATION: Final[str] = (
    "mutation($id: ID!, $head: GitObjectID!) { mergePullRequest(input: "
    "{pullRequestId: $id, mergeMethod: SQUASH, expectedHeadOid: $head}) "
    "{ pullRequest { merged } } }"
)
_MERGE_STATE_QUERY: Final[str] = (
    "query($id: ID!) { node(id: $id) { ... on PullRequest { mergeStateStatus } } }"
)


@dataclass(frozen=True)
class _Checks:
    """The check runs of a head: the names that passed, the names that ended `success`, the names
    that ended `skipped`, the names that failed, and whether all of them ended."""

    passed: tuple[str, ...]
    successful: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: tuple[str, ...]
    ended: bool


def _file_states(
    session: GitHubSession, repo: str, files: dict[str, str], ref: str
) -> tuple[list[str], list[str]]:
    """The files that `ref` lacks, and the files that it holds with other text."""
    missing: list[str] = []
    kept: list[str] = []
    for path, text in files.items():
        live = session.client.get_file_at(repo, path, ref)
        if live is None:
            missing.append(path)
        elif live != text:
            kept.append(path)
    return missing, kept


def _open_pull(session: GitHubSession, repo: str, owner: str) -> dict[str, Any] | None:
    """The open template pull request, or None."""
    query = urlencode({"state": "open", "head": f"{owner}:{TEMPLATE_BRANCH}"})
    pulls = session.rest("GET", f"/repos/{repo}/pulls?{query}")
    return pulls[0] if isinstance(pulls, list) and pulls else None


def _branch_sha(session: GitHubSession, repo: str, branch: str) -> str | None:
    """The head of `branch`, or None when it does not exist."""
    from devops_cli.exceptions.git import GitHubNotFoundError

    try:
        answer = session.rest("GET", f"/repos/{repo}/git/ref/heads/{branch}")
    except GitHubNotFoundError:
        return None
    return str(answer["object"]["sha"])


def _read_checks(session: GitHubSession, repo: str, head: str) -> _Checks:
    """The check runs of `head`. A name counts as passed on `success`, `neutral` or `skipped`,
    and only a run that ended `success` gives a name that a ruleset may require (#7318)."""
    runs = list(
        session.paginate(f"/repos/{repo}/commits/{head}/check-runs", iterable_key="check_runs")
    )
    ended = bool(runs) and all(run.get("status") == "completed" for run in runs)
    passed = tuple(
        sorted(str(run["name"]) for run in runs if run.get("conclusion") in _PASSED_CONCLUSIONS)
    )
    successful = tuple(
        sorted(str(run["name"]) for run in runs if run.get("conclusion") == "success")
    )
    skipped = tuple(sorted(str(run["name"]) for run in runs if run.get("conclusion") == "skipped"))
    failed = tuple(
        sorted(
            str(run["name"])
            for run in runs
            if run.get("status") == "completed" and run.get("conclusion") not in _PASSED_CONCLUSIONS
        )
    )
    return _Checks(
        passed=passed, successful=successful, skipped=skipped, failed=failed, ended=ended
    )


def _wait_for_checks(session: GitHubSession, repo: str, head: str, *, wait: bool) -> _Checks:
    """The check runs of `head`, read again every `_CHECKS_POLL_SECONDS` while `wait` and they
    have not ended, up to `_CHECKS_WAIT_SECONDS`."""
    deadline = clock.monotonic() + _CHECKS_WAIT_SECONDS
    checks = _read_checks(session, repo, head)
    while wait and not checks.ended and clock.monotonic() < deadline:
        clock.sleep(_CHECKS_POLL_SECONDS)
        checks = _read_checks(session, repo, head)
    return checks


def _push_files(
    session: GitHubSession,
    writer: RouteWriter,
    ctx: RowContext,
    baseline: Baseline,
    paths: list[str],
    parent: str,
    branch_exists: bool,
) -> str | None:
    """Write `paths` in one commit on `TEMPLATE_BRANCH` after `parent`, and give the new head.
    In a plan it gives None."""
    repo = ctx.repo
    commit = session.rest("GET", f"/repos/{repo}/git/commits/{parent}")
    tree = writer.rest(
        "template-tree",
        f"/repos/{repo}/git/trees",
        {
            "base_tree": commit["tree"]["sha"],
            "tree": [
                {"path": path, "mode": _FILE_MODE, "type": "blob", "content": baseline.files[path]}
                for path in paths
            ],
        },
    )
    created = writer.rest(
        "template-commit",
        f"/repos/{repo}/git/commits",
        {
            "message": TEMPLATE_PULL_TITLE,
            "tree": tree["sha"] if tree else "<tree>",
            "parents": [parent],
        },
    )
    head = str(created["sha"]) if created else None
    if branch_exists:
        writer.rest(
            "template-branch-update",
            f"/repos/{repo}/git/refs/heads/{TEMPLATE_BRANCH}",
            {"sha": head, "force": True},
        )
    else:
        writer.rest(
            "template-branch-create",
            f"/repos/{repo}/git/refs",
            {"ref": f"refs/heads/{TEMPLATE_BRANCH}", "sha": head},
        )
    return head


def _checks_row(ctx: RowContext, number: int, checks: _Checks, changes: tuple[str, ...]) -> Row:
    """Row 9 from the checks of the head of the template pull request."""
    name = "Template pull request"
    if checks.failed:
        return Row(
            9,
            name,
            RowState.FAILED,
            changes=changes,
            reason=f"#{number}: failed checks {', '.join(checks.failed)}",
        )
    if not checks.ended:
        return Row(
            9,
            name,
            RowState.WAITING,
            changes=changes,
            reason=f"#{number}: its checks have not ended",
        )
    ctx.checks_passed = True
    ctx.successful_checks = checks.successful
    ctx.skipped_checks = checks.skipped
    state = RowState.APPLIED if changes else RowState.WAITING
    return Row(
        9,
        name,
        state,
        changes=changes,
        reason=f"#{number}: checks passed: {', '.join(checks.passed)}",
    )


def template_row(
    session: GitHubSession,
    writer: RouteWriter,
    ctx: RowContext,
    baseline: Baseline,
    template: str,
) -> tuple[Row, tuple[str, ...]]:
    """Row 9, and the template files that the repository holds with other text.

    When the repository holds each file, the row reads the check runs of the head of the open
    template pull request, so row 10 finds the evidence of a pull request that still waits (#7318).
    A merged or closed template pull request gives row 10 no check, because a name that its head
    reported can be a name that no workflow reports now (#7476).
    """
    name = "Template pull request"
    repo = ctx.repo
    missing, kept = _file_states(session, repo, baseline.files, ctx.default_branch)
    pull = _open_pull(session, repo, ctx.options.repo.owner)
    if not missing:
        if pull is not None:
            checks = _read_checks(session, repo, str(pull["head"]["sha"]))
            ctx.successful_checks = checks.successful
            ctx.skipped_checks = checks.skipped
        return Row(9, name, RowState.PRESENT), tuple(kept)
    head = str(pull["head"]["sha"]) if pull else None
    stale = missing
    if pull is not None:
        absent, differing = _file_states(
            session, repo, {path: baseline.files[path] for path in missing}, TEMPLATE_BRANCH
        )
        stale = sorted({*absent, *differing})
    changes = tuple(f"add {path}" for path in stale)
    if stale:
        parent = head or _branch_sha(session, repo, ctx.default_branch)
        if parent is None:
            reason = f"{repo} has no commit on {ctx.default_branch}"
            return Row(9, name, RowState.NOT_READABLE, reason=reason), tuple(kept)
        branch_exists = pull is not None or _branch_sha(session, repo, TEMPLATE_BRANCH) is not None
        head = _push_files(session, writer, ctx, baseline, stale, parent, branch_exists)
        if pull is None:
            body = _TEMPLATE_PULL_BODY.format(template=template, ref=baseline.ref)
            pull = writer.rest(
                "template-pull",
                f"/repos/{repo}/pulls",
                {
                    "title": TEMPLATE_PULL_TITLE,
                    "head": TEMPLATE_BRANCH,
                    "base": ctx.default_branch,
                    "body": body,
                    "draft": True,
                },
            )
    if pull is None or head is None:
        return Row(9, name, RowState.PENDING, changes=changes), tuple(kept)
    existing_reviewers = tuple(
        str(entry.get("login") or "")
        for entry in (pull.get("requested_reviewers") or ())
        if isinstance(entry, dict)
    )
    author = str((pull.get("user") or {}).get("login") or "")
    needed = missing_pull_reviewers(
        (ctx.options.repo.owner,), author=author, existing=existing_reviewers
    )
    if needed:
        writer.rest(
            "template-pull-reviewers",
            f"/repos/{repo}/pulls/{pull['number']}/requested_reviewers",
            {"reviewers": list(needed)},
        )
    ctx.template_pull = int(pull["number"])
    ctx.template_head = head
    if stale and not writer.confirm:
        return Row(9, name, RowState.PENDING, changes=changes), tuple(kept)
    checks = _wait_for_checks(session, repo, head, wait=writer.confirm)
    return _checks_row(ctx, ctx.template_pull, checks, changes), tuple(kept)


def _graphql_errors(answer: dict[str, Any] | None) -> str | None:
    """The first error message of a GraphQL answer, or None."""
    errors = (answer or {}).get("errors") or []
    return str(errors[0].get("message", "")) if errors else None


def ready_row(
    session: GitHubSession, writer: RouteWriter, ctx: RowContext, template_state: RowState
) -> Row:
    """Row 11: after the checks of the template pull request pass, mark it ready and turn on
    auto-merge, or merge it at once when GitHub has nothing to wait for (D3). A head that moved
    after the checks waits for the next run. The merge and the auto-merge name the head that the
    checks ran on (`expectedHeadOid`), so GitHub refuses them when the head moves later."""
    name = "Ready"
    if template_state is RowState.PRESENT:
        return Row(11, name, RowState.PRESENT)
    if template_state is RowState.PENDING:
        return Row(
            11,
            name,
            RowState.PENDING,
            changes=("mark the template pull request ready", "turn on auto-merge"),
        )
    if ctx.template_pull is None or not ctx.checks_passed:
        return Row(
            11,
            name,
            RowState.SKIPPED,
            reason="the checks of the template pull request have not passed",
        )
    pull = session.rest("GET", f"/repos/{ctx.repo}/pulls/{ctx.template_pull}")
    if pull.get("auto_merge") or pull.get("merged"):
        return Row(
            11,
            name,
            RowState.PRESENT,
            reason=f"#{ctx.template_pull} merges when its required checks pass",
        )
    node, head = str(pull["node_id"]), ctx.template_head or str(pull["head"]["sha"])
    if str(pull["head"]["sha"]) != head:
        return Row(
            11,
            name,
            RowState.WAITING,
            reason=f"#{ctx.template_pull} got a commit after its checks; the next run checks it",
        )
    changes: list[str] = []
    if pull.get("draft"):
        error = _graphql_errors(writer.graphql("pull-ready", _READY_MUTATION, {"id": node}))
        if error:
            return Row(11, name, RowState.FAILED, reason=error)
        changes.append(f"#{ctx.template_pull}: ready")
    if not writer.confirm:
        return Row(11, name, RowState.PENDING, changes=(*changes, "turn on auto-merge"))
    state = session.client.graphql(_MERGE_STATE_QUERY, {"id": node})
    merge_state = str(((state.get("data") or {}).get("node") or {}).get("mergeStateStatus", ""))
    mutation = _MERGE_MUTATION if merge_state in _MERGEABLE_NOW else _AUTO_MERGE_MUTATION
    error = _graphql_errors(writer.graphql("pull-auto-merge", mutation, {"id": node, "head": head}))
    if error:
        step = PersonStep(
            f"Merge the template pull request #{ctx.template_pull}: {error}", DOC_MERGE
        )
        return Row(11, name, RowState.PERSON, changes=tuple(changes), reason=error, steps=(step,))
    changes.append(
        f"#{ctx.template_pull}: merged"
        if mutation is _MERGE_MUTATION
        else f"#{ctx.template_pull}: auto-merge on"
    )
    return Row(11, name, RowState.APPLIED, changes=tuple(changes))


__all__ = ["TEMPLATE_PULL_TITLE", "ready_row", "template_row"]
