"""Argument builders and planned request generators for pr commands (#2234)."""

from __future__ import annotations

from devops_cli.config.constants import CONST_GH_CLI, CONST_ROADMAP_LABELS_PATH
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.github.check_verdict import pr_checks_args
from devops_cli.github.pr_threads import (
    reply_thread_args,
    resolve_thread_args,
    review_threads_args,
    unresolve_thread_args,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.github_store import label_args, repository_file_args
from devops_cli.roadmap.title_labels import requested_labels


def pr_list_args(
    state: str,
    limit: int,
    repo: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr list."""
    cmd = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,state,headRefName,baseRefName,author,updatedAt,url",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_list(
    state: str,
    limit: int,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr list."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls",
            argv=tuple(pr_list_args(state, limit, repo)),
        )
    ]


def pr_view_args(
    number: int | str,
    repo: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr view."""
    cmd = [CONST_GH_CLI, "pr", "view", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_view(
    number: int | str,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr view."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=tuple(pr_view_args(number, repo)),
        )
    ]


def plan_pr_checks(
    number: int | str,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr checks."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}/checks",
            argv=tuple(pr_checks_args(number, repo)),
        )
    ]


def pr_edit_args(
    number: int | str,
    base: str | None = None,
    title: str | None = None,
    body: str | None = None,
    repo: str | None = None,
    milestone: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr edit."""
    cmd = [CONST_GH_CLI, "pr", "edit", str(number)]
    if base:
        cmd.extend(["--base", base])
    if title:
        cmd.extend(["--title", title])
    if body:
        cmd.extend(["--body", body])
    if repo:
        cmd.extend(["--repo", repo])
    if milestone:
        cmd.extend(["--milestone", milestone])
    return cmd


def plan_pr_edit(
    number: int | str,
    base: str | None = None,
    title: str | None = None,
    body: str | None = None,
    repo: str | None = None,
    milestone: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr edit."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="POST",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=tuple(pr_edit_args(number, base, title, body, repo, milestone)),
        )
    ]


def pr_create_args(
    title: str,
    body: str = "",
    base: str | None = None,
    repo: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr create."""
    cmd = [CONST_GH_CLI, "pr", "create", "--draft", "--title", title, "--body", body]
    if base:
        cmd.extend(["--base", base])
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_create(
    title: str,
    body: str = "",
    base: str | None = None,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr create."""
    target_repo = repo or ":owner/:repo"
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="POST",
            target=f"repos/{target_repo}/pulls",
            argv=tuple(pr_create_args(title, body, base, repo)),
        )
    ]
    asked = [label for label in requested_labels(title) if label]
    if asked:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"repos/{target_repo}/contents/{CONST_ROADMAP_LABELS_PATH}",
                argv=(
                    CONST_GH_CLI,
                    *repository_file_args(target_repo, CONST_ROADMAP_LABELS_PATH, ref=base),
                ),
                condition="the pull request opens",
            )
        )
        for label in asked:
            requests.append(
                PlannedRequest(
                    method="POST",
                    target=f"repos/{target_repo}/issues/<number>/labels",
                    argv=(CONST_GH_CLI, *label_args(target_repo, "<number>", label)),
                    condition=MESSAGES.pr.labels_dry_run_condition,
                )
            )
    return requests


def pr_ready_args(
    number: int | str,
    repo: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr ready."""
    cmd = [CONST_GH_CLI, "pr", "ready", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_ready(
    number: int | str,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr ready."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{number}"),
        ),
        PlannedRequest(
            method="POST",
            target=f"repos/{target_repo}/pulls/{number}/ready",
            argv=tuple(pr_ready_args(number, repo)),
        ),
    ]


def pr_diff_args(
    number: int | str,
    color: str = "auto",
    repo: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr diff."""
    cmd = [CONST_GH_CLI, "pr", "diff", str(number), "--color", color]
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_diff(
    number: int | str,
    color: str = "auto",
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr diff."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=tuple(pr_diff_args(number, color, repo)),
        )
    ]


def pr_close_args(
    number: int | str,
    comment: str | None = None,
    delete_branch: bool = False,
    repo: str | None = None,
) -> list[str]:
    """CLI arguments for gh pr close."""
    cmd = [CONST_GH_CLI, "pr", "close", str(number)]
    if comment:
        cmd.extend(["--comment", comment])
    if delete_branch:
        cmd.append("--delete-branch")
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_close(
    number: int | str,
    comment: str | None = None,
    delete_branch: bool = False,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr close."""
    target_repo = repo or ":owner/:repo"
    return [
        PlannedRequest(
            method="POST",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=tuple(pr_close_args(number, comment, delete_branch, repo)),
        )
    ]


def plan_pr_monitor(
    number: int | None,
    interval: int = 60,
    timeout: int = 300,
    require_reviews: bool = True,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr monitor and wait."""
    num_str = str(number) if number is not None else "<number>"
    target_repo = repo or ":owner/:repo"
    owner, repo_name = target_repo.split("/", 1) if "/" in target_repo else (":owner", ":repo")
    repeat_desc = f"every {interval}s up to {timeout}s"
    round_requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{num_str}",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{num_str}"),
            repeat=repeat_desc,
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{num_str}/checks",
            argv=tuple(pr_checks_args(num_str, repo)),
            repeat=repeat_desc,
        ),
        PlannedRequest(
            method="GRAPHQL",
            target="reviewThreads",
            argv=tuple(review_threads_args(owner, repo_name, num_str)),
            repeat=repeat_desc,
        ),
    ]
    if require_reviews:
        round_requests.append(
            PlannedRequest(
                method="GET",
                target=f"repos/{target_repo}/pulls/{num_str}/reviews",
                argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{num_str}/reviews"),
                repeat=repeat_desc,
            )
        )
    return round_requests


def plan_pr_check_readiness(
    number: int | None,
    auto_resolve: bool = False,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr check-readiness."""
    num_str = str(number) if number is not None else "<number>"
    target_repo = repo or ":owner/:repo"
    owner, repo_name = target_repo.split("/", 1) if "/" in target_repo else (":owner", ":repo")
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{num_str}",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{num_str}"),
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{num_str}/checks",
            argv=tuple(pr_checks_args(num_str, repo)),
        ),
        PlannedRequest(
            method="GRAPHQL",
            target="reviewThreads",
            argv=tuple(review_threads_args(owner, repo_name, num_str)),
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{num_str}/files",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{num_str}/files"),
        ),
    ]
    if auto_resolve:
        requests.append(
            PlannedRequest(
                method="GRAPHQL",
                target="resolveReviewThread",
                condition="auto-resolve enabled and threads have replies",
            )
        )
    return requests


def pr_view_payload_args(number: int | str, repo: str | None = None) -> list[str]:
    """CLI arguments for gh pr view with json fields."""
    cmd = [CONST_GH_CLI, "pr", "view", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    cmd.extend(["--json", "number,title,labels,files,state,mergedAt"])
    return cmd


def merged_prs_payload_args(limit: int = 100, repo: str | None = None) -> list[str]:
    """CLI arguments for gh pr list of merged PRs."""
    cmd = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        "merged",
        "--limit",
        str(limit),
        "--json",
        "number,title,labels,files,state,mergedAt",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def plan_pr_hardening_report(
    pr: int | None = None,
    limit: int = 100,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr hardening-report."""
    target_repo = repo or ":owner/:repo"
    if pr is not None:
        return [
            PlannedRequest(
                method="GET",
                target=f"repos/{target_repo}/pulls/{pr}",
                argv=tuple(pr_view_payload_args(pr, repo)),
            )
        ]
    return [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls?state=merged",
            argv=tuple(merged_prs_payload_args(limit, repo)),
        )
    ]


def plan_pr_threads_list(
    number: int | str,
    unresolved_only: bool = False,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr threads list."""
    target_repo = repo or ":owner/:repo"
    owner, repo_name = target_repo.split("/", 1) if "/" in target_repo else (":owner", ":repo")
    return [
        PlannedRequest(
            method="GRAPHQL",
            target="reviewThreads",
            argv=tuple(review_threads_args(owner, repo_name, number)),
            condition="unresolved threads only" if unresolved_only else "",
        )
    ]


def plan_pr_threads_reply(
    thread_id: str,
    body: str,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr threads reply."""
    return [
        PlannedRequest(
            method="GRAPHQL",
            target="addPullRequestReviewThreadReply",
            argv=tuple(reply_thread_args(thread_id, body)),
        )
    ]


def plan_pr_threads_resolve(
    thread_ids: list[str],
    without_reply: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr threads resolve."""
    requests: list[PlannedRequest] = []
    for tid in thread_ids:
        if not without_reply:
            requests.append(
                PlannedRequest(
                    method="GRAPHQL",
                    target="node",
                    argv=(
                        CONST_GH_CLI,
                        "api",
                        "graphql",
                        "-f",
                        f'query=query {{ node(id: "{tid}") ... }}',
                    ),
                    condition="validation of non-opener reply",
                )
            )
        requests.append(
            PlannedRequest(
                method="GRAPHQL",
                target="resolveReviewThread",
                argv=tuple(resolve_thread_args(tid)),
            )
        )
    return requests


def plan_pr_threads_unresolve(
    thread_id: str,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr threads unresolve."""
    return [
        PlannedRequest(
            method="GRAPHQL",
            target="unresolveReviewThread",
            argv=tuple(unresolve_thread_args(thread_id)),
        )
    ]


def plan_pr_threads_resolve_all(
    number: int | str,
    only_replied: bool = True,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for devops pr threads resolve-all."""
    target_repo = repo or ":owner/:repo"
    owner, repo_name = target_repo.split("/", 1) if "/" in target_repo else (":owner", ":repo")
    return [
        PlannedRequest(
            method="GRAPHQL",
            target="reviewThreads",
            argv=tuple(review_threads_args(owner, repo_name, number)),
        ),
        PlannedRequest(
            method="GRAPHQL",
            target="resolveReviewThread",
            condition="threads have replies" if only_replied else "all open threads",
            repeat="for each unresolved thread",
        ),
    ]
