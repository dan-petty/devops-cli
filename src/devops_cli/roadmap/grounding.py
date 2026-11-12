"""The item rules a pull request is grounded by: it delivers exactly one roadmap Item (#704, #2442).

A pull request into the default branch closes exactly one open issue of its own repository that
holds a `priority/*` label, a roadmap Item (ADR 0016), and it adds the archived change folder of
that issue's change, which `uv run devops openspec archive` writes. Only that archive writes the
living specs and the archive.

Each rule is a pure predicate over the `Grounding` facts: it names what is missing, or returns
None. A rule that needs what an earlier one found missing returns None, so each failure is one
blocker. `github/merge_readiness.py` reads the facts and applies `GROUNDING_RULES`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import (
    CONST_ISSUE_STATE_OPEN,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_ARCHIVED_FOLDER_RE,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_OPENSPEC_SPECS_DIR,
    CONST_PR_FILE_ADDED_STATUSES,
    CONST_PR_FILE_REMOVED_STATUS,
)
from devops_cli.github.client import PullRequestFile
from devops_cli.lang import MESSAGES


class ChangedFilesRead(NamedTuple):
    """The files a pull request changes, or why they could not be read. `truncated` says that
    GitHub listed its limit of files, so the list may be incomplete."""

    files: list[PullRequestFile]
    error: str = ""
    truncated: bool = False


class _GraphModel(BaseModel):
    """A GraphQL payload model: GitHub may add fields, so unknown ones are ignored."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class _Label(_GraphModel):
    name: str


class _Labels(_GraphModel):
    nodes: list[_Label] = Field(default_factory=list)


class _IssueRepository(_GraphModel):
    name_with_owner: str = Field(alias="nameWithOwner")


class ClosingIssue(_GraphModel):
    """An issue GitHub closes when the pull request merges, with its labels."""

    number: int
    state: str
    repository: _IssueRepository
    labels: _Labels = Field(default_factory=_Labels)

    def is_of(self, repo: str) -> bool:
        """Whether the issue belongs to repository `repo` (`owner/name`)."""
        return self.repository.name_with_owner.lower() == repo.lower()

    def reference(self, repo: str) -> str:
        """`#N` for an issue of `repo`, `owner/name#N` for one of another repository."""
        prefix = "" if self.is_of(repo) else self.repository.name_with_owner
        return f"{prefix}#{self.number}"

    def is_item(self) -> bool:
        """Whether the issue is a roadmap Item: it holds a `priority/*` label (ADR 0016)."""
        from devops_cli.roadmap.stores.store import FIELD_VALUES, ItemField, field_label

        priorities = {
            field_label(ItemField.PRIORITY, value) for value in FIELD_VALUES[ItemField.PRIORITY]
        }
        return any(label.name.lower() in priorities for label in self.labels.nodes)


class ClosingRead(NamedTuple):
    """The issues GitHub closes when the PR merges, and how many there are, or why they could
    not be read."""

    issues: tuple[ClosingIssue, ...] = ()
    total: int = 0
    error: str = ""


class Grounding(NamedTuple):
    """What the item rules judge: the PR's base and its repository's default branch, the files
    it changes, and the issues it closes with their labels, read only into the default branch."""

    pr_num: int
    owner: str
    repo: str
    base: str
    default: str
    changed: ChangedFilesRead
    closing: ClosingRead | None = None

    @property
    def into_default(self) -> bool:
        """Whether the PR targets its repository's default branch."""
        return self.default != "" and self.base == self.default

    @property
    def issue(self) -> ClosingIssue | None:
        """The one issue the PR closes; None unless it closes exactly one, read."""
        closing = self.closing
        if closing is None or closing.error or closing.total != 1 or len(closing.issues) != 1:
            return None
        return closing.issues[0]

    @property
    def own_issue(self) -> ClosingIssue | None:
        """The one issue the PR closes when it is an issue of the PR's repository."""
        issue = self.issue
        return issue if issue is not None and issue.is_of(self.repo) else None


def targets_the_default_branch(grounding: Grounding) -> str | None:
    """The PR targets the default branch, where GitHub closes its issue when it merges."""
    texts, number = MESSAGES.pr, grounding.pr_num
    if grounding.into_default:
        return None
    if not grounding.default:
        return texts.grounding_no_default_branch.format(number=number, repo=grounding.repo)
    return texts.grounding_not_into_default.format(
        number=number, base=grounding.base, default=grounding.default
    )


def closing_issues_were_read(grounding: Grounding) -> str | None:
    """The issues the PR closes were read, so the issue rules have something to judge."""
    closing = grounding.closing
    if closing is None or not closing.error:
        return None
    return MESSAGES.pr.grounding_closing_unread.format(number=grounding.pr_num, error=closing.error)


def closes_one_issue(grounding: Grounding) -> str | None:
    """The PR closes exactly one issue when it merges."""
    closing, texts, number = grounding.closing, MESSAGES.pr, grounding.pr_num
    if closing is None or closing.error or closing.total == 1:
        return None
    if closing.total == 0:
        return texts.grounding_closes_no_issue.format(number=number)
    issues = ", ".join(issue.reference(grounding.repo) for issue in closing.issues)
    return texts.grounding_closes_several_issues.format(
        number=number, count=closing.total, issues=issues
    )


def closes_an_issue_of_its_repository(grounding: Grounding) -> str | None:
    """The one issue the PR closes is an issue of the PR's repository, whose change it archives."""
    issue = grounding.issue
    if issue is None or grounding.own_issue is not None:
        return None
    return MESSAGES.pr.grounding_closes_foreign_issue.format(
        number=grounding.pr_num, issue=issue.reference(grounding.repo), repo=grounding.repo
    )


def closes_an_open_issue(grounding: Grounding) -> str | None:
    """The one issue the PR closes is open."""
    issue = grounding.own_issue
    if issue is None or issue.state.lower() == CONST_ISSUE_STATE_OPEN:
        return None
    return MESSAGES.pr.grounding_closes_closed_issue.format(
        number=grounding.pr_num, issue=issue.number
    )


def closes_an_item(grounding: Grounding) -> str | None:
    """The one issue the PR closes is a roadmap Item: it holds a `priority/*` label."""
    issue = grounding.own_issue
    if issue is None or issue.is_item():
        return None
    return MESSAGES.pr.grounding_issue_not_item.format(number=grounding.pr_num, issue=issue.number)


def changed_files_were_read(grounding: Grounding) -> str | None:
    """The files the PR changes were read, so the change-folder rules have something to judge."""
    if not grounding.changed.error:
        return None
    return MESSAGES.pr.grounding_files_unread.format(
        number=grounding.pr_num, error=grounding.changed.error
    )


def _archives(changed: PullRequestFile, issue: int) -> bool:
    """Whether this change adds a file to an archived change folder of `issue`."""
    match = re.fullmatch(CONST_OPENSPEC_ARCHIVED_FOLDER_RE, changed.filename)
    return (
        match is not None
        and int(match.group("issue")) == issue
        and changed.status in CONST_PR_FILE_ADDED_STATUSES
    )


def _change_named_by(changed: PullRequestFile) -> re.Match[str] | None:
    """The change folder that `changed` leaves in the PR's head: an active folder it does not
    remove, or an archived folder it adds. None for any other file."""
    if changed.status in CONST_PR_FILE_ADDED_STATUSES:
        archived = re.fullmatch(CONST_OPENSPEC_ARCHIVED_FOLDER_RE, changed.filename)
        return archived or re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, changed.filename)
    if changed.status == CONST_PR_FILE_REMOVED_STATUS:
        return None
    return re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, changed.filename)


def _its_change(files: list[PullRequestFile], issue: int) -> str:
    """The name of the change of `issue` that the PR leaves in its head, or the placeholder
    `<issue>-<slug>` when it leaves none."""
    matches = (match for changed in files if (match := _change_named_by(changed)))
    names = (match.group("change") for match in matches if int(match.group("issue")) == issue)
    return next(names, f"{issue}-<slug>")


def _archived_folder(change: str) -> str:
    """The folder `openspec archive` moves `change` to, its date left as a placeholder."""
    return f"{CONST_OPENSPEC_ARCHIVE_DIR}/<date>-{change}/"


def archives_its_change(grounding: Grounding) -> str | None:
    """The PR adds the archived change folder of the one issue it closes."""
    issue = grounding.own_issue
    if issue is None or grounding.changed.error:
        return None
    files = grounding.changed.files
    if any(_archives(changed, issue.number) for changed in files):
        return None
    change = _its_change(files, issue.number)
    return MESSAGES.pr.grounding_change_not_archived.format(
        number=grounding.pr_num, folder=_archived_folder(change), issue=issue.number, change=change
    )


def _is_a_record_of_another_change(path: str, issue: int, archives_its_own: bool) -> bool:
    """Whether `path` is in the living specs or the archive, outside what the archive of the
    change of `issue` writes."""
    if path.startswith(f"{CONST_OPENSPEC_SPECS_DIR}/"):
        return not archives_its_own
    if not path.startswith(f"{CONST_OPENSPEC_ARCHIVE_DIR}/"):
        return False
    match = re.fullmatch(CONST_OPENSPEC_ARCHIVED_FOLDER_RE, path)
    return match is None or int(match.group("issue")) != issue


def writes_only_its_own_record(grounding: Grounding) -> str | None:
    """Only the archive of the change of the issue the PR closes writes the living specs and
    the archive."""
    issue = grounding.own_issue
    if issue is None or grounding.changed.error:
        return None
    files = grounding.changed.files
    archives_its_own = any(_archives(changed, issue.number) for changed in files)
    written = [
        changed.filename
        for changed in files
        if _is_a_record_of_another_change(changed.filename, issue.number, archives_its_own)
    ]
    if not written:
        return None
    return MESSAGES.pr.grounding_record_written.format(
        number=grounding.pr_num,
        paths=", ".join(written)[:CONST_MAX_ERROR_DETAIL_LENGTH],
        issue=issue.number,
        specs=CONST_OPENSPEC_SPECS_DIR,
        archive=CONST_OPENSPEC_ARCHIVE_DIR,
        folder=_archived_folder(_its_change(files, issue.number)),
    )


# A new rule is one more entry, in the order its blockers are reported.
GROUNDING_RULES: tuple[Callable[[Grounding], str | None], ...] = (
    targets_the_default_branch,
    closing_issues_were_read,
    closes_one_issue,
    closes_an_issue_of_its_repository,
    closes_an_open_issue,
    closes_an_item,
    changed_files_were_read,
    archives_its_change,
    writes_only_its_own_record,
)


def grounding_blockers(grounding: Grounding) -> list[str]:
    """The blocker of each item rule the facts break, in the order of `GROUNDING_RULES`."""
    return [found for rule in GROUNDING_RULES if (found := rule(grounding))]


# The title that the stage job writes for a plan (`staging_title`): the pull request plans an item
# and delivers none, so the rules of a delivery do not apply to it (#3280).
_PLAN_TITLE_RE = re.compile(r"docs\(openspec\): plan #(?P<issue>\d+) ")
_PLANS_LINE_RE = re.compile(r"^Plans #(?P<issue>\d+)\s*$", re.MULTILINE)


def plan_issue(title: str) -> int | None:
    """The issue that a plan pull request plans, read from its title; None for any other title."""
    match = _PLAN_TITLE_RE.match(title)
    return int(match.group("issue")) if match else None


def plan_blockers(pr_num: int, issue: int, body: str, files: list[PullRequestFile]) -> list[str]:
    """The blocker of each rule of a plan that its body or its files break, in a fixed order.

    The body has exactly one line `Plans #<issue>` and no closing keyword. The plan adds a file to
    the active change folder of the issue and changes nothing under the living specs.
    """
    # Imported here: `stage_change` loads the model client, and `pr --help` must not (startup budget).
    from devops_cli.roadmap.stage.stage_change import closing_keyword_in

    texts = MESSAGES.pr
    found: list[str] = []
    plans = [int(match.group("issue")) for match in _PLANS_LINE_RE.finditer(body)]
    if plans != [issue]:
        found.append(texts.grounding_plan_no_plans_line.format(number=pr_num, issue=issue))
    if (keyword := closing_keyword_in(body)) is not None:
        found.append(texts.grounding_plan_closes.format(number=pr_num, keyword=keyword))
    if not any(_adds_to_active_folder(changed, issue) for changed in files):
        found.append(
            texts.grounding_plan_no_folder.format(
                number=pr_num, issue=issue, folder=f"{CONST_OPENSPEC_CHANGES_DIR}/{issue}-<slug>/"
            )
        )
    written = [f.filename for f in files if f.filename.startswith(f"{CONST_OPENSPEC_SPECS_DIR}/")]
    if written:
        found.append(
            texts.grounding_plan_writes_spec.format(
                number=pr_num,
                paths=", ".join(written)[:CONST_MAX_ERROR_DETAIL_LENGTH],
                specs=CONST_OPENSPEC_SPECS_DIR,
            )
        )
    return found


def _adds_to_active_folder(changed: PullRequestFile, issue: int) -> bool:
    """Whether this change adds a file to the active change folder of `issue`."""
    match = re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, changed.filename)
    return (
        match is not None
        and int(match.group("issue")) == issue
        and changed.status in CONST_PR_FILE_ADDED_STATUSES
    )
