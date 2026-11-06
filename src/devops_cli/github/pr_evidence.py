"""The comment that holds the check results of a pull request, and its one copy (#3199).

`devops pr evidence` posts it, and the roadmap Service can post it for its own pull requests: both
call `publish_pr_evidence`. Every number in the comment comes from the check runs that GitHub
returns for the head commit, so no person types a count that can be wrong.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from devops_cli.config.constants import CONST_FAIL_TO_PASS_CHECK_NAME, CONST_PR_EVIDENCE_MARKER
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.check_verdict import CheckBucket, PRCheckItem, read_check_runs
from devops_cli.github.defect_classifier import is_defect_pr
from devops_cli.github.session import GitHubSession

_NO_LINK = "-"


class EvidenceAction(StrEnum):
    """What `publish_pr_evidence` did with the comment."""

    CREATED = "created"
    UPDATED = "updated"


@dataclass(frozen=True)
class EvidenceOutcome:
    """The comment that was written, and whether it is a new comment or the update of one."""

    action: EvidenceAction
    body: str


def _table_cell(text: str) -> str:
    """`text` for a cell of a Markdown table: a pipe would end the cell, a line break the row."""
    return " ".join(text.split()).replace("|", "\\|")


def _row(item: PRCheckItem) -> str:
    link = f"[run]({item.link})" if item.link else _NO_LINK
    return f"| {_table_cell(item.name)} | {_table_cell(item.state)} | {link} |"


def build_pr_evidence_comment(
    items: Sequence[PRCheckItem],
    *,
    head_sha: str,
    title: str,
    labels: Sequence[str] = (),
    attribution: Sequence[str] = (),
) -> str:
    """The text of the comment: the marker line, the head commit, a table of the checks with their
    conclusion and link, the link of the passing fail-to-pass run when the pull request is a fix,
    a line for each skipped check, and the paragraphs `attribution`."""
    lines = [
        CONST_PR_EVIDENCE_MARKER,
        "## Check results",
        "",
        f"Head commit: `{head_sha}`",
        "",
        "| Check | Conclusion | Link |",
        "| --- | --- | --- |",
        *(_row(item) for item in items),
    ]
    if is_defect_pr(title, labels):
        passed = next(
            (
                item
                for item in items
                if item.name == CONST_FAIL_TO_PASS_CHECK_NAME
                and item.bucket == CheckBucket.PASS
                and item.link
            ),
            None,
        )
        if passed is not None:
            lines += ["", f"Fail-to-pass run: {passed.link}"]
    skipped = [item for item in items if item.bucket == CheckBucket.SKIPPING]
    if skipped:
        lines.append("")
        lines += [f"Skipped check: {_table_cell(item.name)}" for item in skipped]
    text = "\n".join(lines) + "\n"
    if attribution:
        text += "\n" + "\n\n".join(attribution) + "\n"
    return text


def _opens_with_marker(body: str) -> bool:
    return body.startswith(CONST_PR_EVIDENCE_MARKER)


def publish_pr_evidence(
    session: GitHubSession, repo: str, number: int, *, attribution: Sequence[str] = ()
) -> EvidenceOutcome:
    """Write the check results of the head commit of pull request `number` in `repo` as the one
    comment of the pull request that opens with the marker line and that the session's own login
    wrote: update it when it exists, else post it. A comment of another author never matches, so
    nobody can claim the marker. No check run that cannot be read is posted: a read that fails
    raises, and nothing is written."""
    client = session.client
    pull = client.get_pull(repo, number)
    owner, name = repo.split("/", 1)
    summary = read_check_runs(owner, name, pull.head.sha, session=session)
    if summary.unread_reason:
        raise GitHubUnreadError(summary.unread_reason, details={"repo": repo, "pull": number})
    body = build_pr_evidence_comment(
        summary.items,
        head_sha=pull.head.sha,
        title=pull.title,
        labels=pull.labels,
        attribution=attribution,
    )
    own = next(
        (
            comment
            for comment in client.list_issue_comments(repo, number)
            if comment.author == session.login and _opens_with_marker(comment.body)
        ),
        None,
    )
    if own is None:
        client.create_issue_comment(repo, number, body)
        return EvidenceOutcome(EvidenceAction.CREATED, body)
    client.update_issue_comment(repo, own.id, body)
    return EvidenceOutcome(EvidenceAction.UPDATED, body)
