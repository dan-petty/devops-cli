"""The item rules: a pull request into the default branch delivers exactly one open roadmap Item
of its repository and archives that issue's change (#704, ADR 0016, #2442).

Each rule is a pure predicate over the `Grounding` facts, so every case here is a table row with
no read of GitHub; `tests/test_merge_readiness.py` covers how readiness reads the facts.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from devops_cli.github.client import PullRequestFile
from devops_cli.roadmap.grounding import (
    GROUNDING_RULES,
    ChangedFilesRead,
    ClosingIssue,
    ClosingRead,
    Grounding,
    archives_its_change,
    changed_files_were_read,
    closes_an_issue_of_its_repository,
    closes_an_item,
    closes_an_open_issue,
    closes_one_issue,
    closing_issues_were_read,
    grounding_blockers,
    targets_the_default_branch,
    writes_only_its_own_record,
)

_REPO = "dan-petty/devops-cli"
_ARCHIVE = "openspec/changes/archive"


def _file(filename: str, status: str = "modified") -> PullRequestFile:
    return PullRequestFile(filename=filename, status=status)


_ARCHIVE_704 = _file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "added")


def _issue(
    number: int = 704,
    *,
    state: str = "OPEN",
    repo: str = _REPO,
    labels: tuple[str, ...] = ("type/feature", "priority/p2-medium"),
) -> ClosingIssue:
    """An issue the PR closes; by default an open roadmap Item, which holds a `priority/*`
    label."""
    return ClosingIssue.model_validate(
        {
            "number": number,
            "state": state,
            "repository": {"nameWithOwner": repo},
            "labels": {"nodes": [{"name": label} for label in labels]},
        }
    )


def _closing(*issues: ClosingIssue, total: int | None = None, error: str = "") -> ClosingRead:
    return ClosingRead(issues, len(issues) if total is None else total, error)


def _grounding(
    files: list[PullRequestFile] | None = None,
    *,
    closing: ClosingRead | None = None,
    base: str = "main",
    default: str = "main",
    files_error: str = "",
) -> Grounding:
    """PR #335 into `base`, changing `files` (by default it archives #704's change), and closing
    open Item #704 unless `closing` says otherwise."""
    changed = ChangedFilesRead([_ARCHIVE_704] if files is None else files, files_error)
    return Grounding(
        335,
        "dan-petty",
        _REPO,
        base,
        default,
        changed,
        _closing(_issue()) if closing is None else closing,
    )


def _not_archived(change: str = "704-<slug>") -> str:
    """The blocker of a PR that closes #704 and adds no archived folder for it."""
    return (
        f"PR #335 is not grounded: it adds no {_ARCHIVE}/<date>-{change}/ for #704. Archive "
        f"the change in the last commit of the PR with uv run devops openspec archive {change}."
    )


def _writes_a_record(paths: str, change: str = "704-<slug>") -> str:
    """The blocker of a PR that closes #704 and changes `paths`, which only its own archive may."""
    return (
        f"PR #335 is not grounded: it changes {paths}. Only the archive of the change of #704 "
        f"writes openspec/specs/ and {_ARCHIVE}/, and only in {_ARCHIVE}/<date>-{change}/."
    )


_Rule = Callable[[Grounding], str | None]


@pytest.mark.parametrize(
    ("rule", "grounding", "found"),
    [
        (targets_the_default_branch, _grounding(), None),
        (
            targets_the_default_branch,
            _grounding(base="feat/stacked"),
            "PR #335 is not grounded: it targets feat/stacked, not the default branch main. "
            "Change its base with devops pr edit 335 --base main.",
        ),
        (
            targets_the_default_branch,
            _grounding(default=""),
            "PR #335 is not grounded: GitHub names no default branch for dan-petty/devops-cli.",
        ),
        (closing_issues_were_read, _grounding(), None),
        (
            closing_issues_were_read,
            _grounding(closing=_closing(error="gh: Server Error (HTTP 500)")),
            "PR #335 is not grounded: the issues it closes could not be read "
            "(gh: Server Error (HTTP 500)).",
        ),
        (closes_one_issue, _grounding(), None),
        (
            closes_one_issue,
            _grounding(closing=_closing()),
            "PR #335 is not grounded: it closes no issue. Put Closes #<issue> in its body for "
            "the one issue it delivers.",
        ),
        (
            closes_one_issue,
            _grounding(closing=_closing(_issue(1), _issue(2), total=12)),
            "PR #335 is not grounded: it closes 12 issues (#1, #2), and a PR delivers exactly one.",
        ),
        (closes_an_issue_of_its_repository, _grounding(), None),
        (
            closes_an_issue_of_its_repository,
            _grounding(closing=_closing(_issue(repo="other/project"))),
            "PR #335 is not grounded: it closes other/project#704, which is not an issue of "
            "dan-petty/devops-cli.",
        ),
        (closes_an_open_issue, _grounding(), None),
        (
            closes_an_open_issue,
            _grounding(closing=_closing(_issue(state="CLOSED"))),
            "PR #335 is not grounded: it closes #704, which is not open.",
        ),
        (closes_an_item, _grounding(), None),
        (
            closes_an_item,
            _grounding(closing=_closing(_issue(labels=("Priority/P1-High",)))),
            None,
        ),
        (
            closes_an_item,
            _grounding(closing=_closing(_issue(labels=("priority/high",)))),
            "PR #335 is not grounded: #704 is not a roadmap item: it holds no priority label. "
            "Run devops roadmap intake on it.",
        ),
        (changed_files_were_read, _grounding(), None),
        (
            changed_files_were_read,
            _grounding([], files_error="gh: Server Error (HTTP 500)"),
            "PR #335 is not grounded: the files it changes could not be read "
            "(gh: Server Error (HTTP 500)).",
        ),
        (archives_its_change, _grounding(), None),
        (archives_its_change, _grounding([_file("src/x.py")]), _not_archived()),
        (writes_only_its_own_record, _grounding(), None),
        (
            writes_only_its_own_record,
            _grounding([_file("openspec/specs/widget/spec.md")]),
            _writes_a_record("openspec/specs/widget/spec.md"),
        ),
    ],
    ids=[
        "default-branch",
        "another-branch",
        "no-default-branch",
        "closing-read",
        "closing-unread",
        "one-issue",
        "no-issue",
        "more-issues-than-one-page",
        "own-repository",
        "another-repository",
        "open",
        "closed",
        "item",
        "priority-label-in-another-case",
        "unknown-priority-label",
        "files-read",
        "files-unread",
        "archived",
        "not-archived",
        "own-record",
        "a-spec-without-the-archive",
    ],
)
def test_each_item_rule_names_what_is_missing_or_nothing(
    rule: _Rule, grounding: Grounding, found: str | None
) -> None:
    """A rule names what the PR lacks, or returns None when the facts satisfy it."""
    assert rule(grounding) == found


@pytest.mark.parametrize(
    ("issue", "files"),
    [
        (704, [_ARCHIVE_704]),
        (704, [_file(f"{_ARCHIVE}/2026-10-23-704-x/tasks.md", "renamed")]),
        (704, [_file(f"{_ARCHIVE}/2026-10-23-704-x/design.md", "copied")]),
        (89, [_file("src/x.py"), _file(f"{_ARCHIVE}/2026-10-23-089-x/proposal.md", "added")]),
        (
            704,
            [
                _file("openspec/changes/704-x/proposal.md", "removed"),
                _file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "added"),
                _file("openspec/specs/widget/spec.md", "added"),
                _file("openspec/specs/export/spec.md", "modified"),
            ],
        ),
    ],
    ids=["added", "renamed", "copied", "zero-padded-089", "with-the-living-specs-it-writes"],
)
def test_a_pr_that_archives_the_change_of_its_issue_is_grounded(
    issue: int, files: list[PullRequestFile]
) -> None:
    """A PR into the default branch that closes one open roadmap Item and adds that issue's
    archived change folder is grounded, with the living specs its archive wrote."""
    assert grounding_blockers(_grounding(files, closing=_closing(_issue(issue)))) == []


@pytest.mark.parametrize(
    ("files", "blockers"),
    [
        ([_file("src/x.py")], [_not_archived()]),
        ([_file("openspec/changes/704-x/proposal.md", "added")], [_not_archived("704-x")]),
        ([_file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "modified")], [_not_archived()]),
        ([_file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "removed")], [_not_archived()]),
        (
            [_file(f"{_ARCHIVE}/2026-10-23-705-x/proposal.md", "added")],
            [_not_archived(), _writes_a_record(f"{_ARCHIVE}/2026-10-23-705-x/proposal.md")],
        ),
        (
            [_file("openspec/specs/widget/spec.md", "modified")],
            [_not_archived(), _writes_a_record("openspec/specs/widget/spec.md")],
        ),
        (
            [_ARCHIVE_704, _file(f"{_ARCHIVE}/2026-10-01-705-y/tasks.md", "modified")],
            [_writes_a_record(f"{_ARCHIVE}/2026-10-01-705-y/tasks.md", "704-x")],
        ),
        (
            [_ARCHIVE_704, _file(f"{_ARCHIVE}/.gitkeep", "removed")],
            [_writes_a_record(f"{_ARCHIVE}/.gitkeep", "704-x")],
        ),
        (
            [
                _file("openspec/changes/704-x/proposal.md", "added"),
                _file("openspec/changes/704-x/tasks.md", "added"),
            ],
            [_not_archived("704-x")],
        ),
    ],
    ids=[
        "no-change-folder",
        "an-active-change",
        "an-archived-folder-the-base-holds",
        "its-archived-folder-removed",
        "the-archived-folder-of-another-issue",
        "a-spec-without-the-archive",
        "another-issues-archive-changed",
        "a-file-of-the-archive-directory",
        "one-blocker-for-the-files-of-one-change",
    ],
)
def test_a_pr_that_does_not_archive_its_change_names_the_folder(
    files: list[PullRequestFile], blockers: list[str]
) -> None:
    """A PR that closes #704 adds #704's archived change folder, and only that archive writes the
    living specs and the archive. Each blocker names the folder readiness expects, with the PR's
    own change when it has one, or each file only the archive may write."""
    assert grounding_blockers(_grounding(files)) == blockers


@pytest.mark.parametrize(
    "grounding",
    [
        _grounding(closing=_closing()),
        _grounding(closing=_closing(_issue(1), _issue(2))),
        _grounding(closing=_closing(_issue(repo="other/project"))),
        _grounding(closing=_closing(_issue(state="CLOSED"))),
        _grounding(closing=_closing(_issue(labels=("type/feature",)))),
        _grounding([], files_error="gh: Server Error (HTTP 500)"),
        _grounding(closing=_closing(error="Something went wrong")),
        Grounding(335, "dan-petty", _REPO, "feat/stacked", "main", ChangedFilesRead([])),
    ],
    ids=[
        "no-closing-reference",
        "two-issues",
        "issue-of-another-repository",
        "closed-issue",
        "issue-with-no-priority-label",
        "files-unreadable",
        "closing-issues-unreadable",
        "another-branch",
    ],
)
def test_each_way_a_pr_is_ungrounded_is_exactly_one_blocker(grounding: Grounding) -> None:
    """A rule that needs what an earlier one found missing names nothing, so each failure is one
    blocker."""
    assert len(grounding_blockers(grounding)) == 1


def test_the_rules_run_in_the_order_their_blockers_are_reported() -> None:
    """The branch, the issues it closes, then the change it archives."""
    assert [rule.__name__ for rule in GROUNDING_RULES] == [
        "targets_the_default_branch",
        "closing_issues_were_read",
        "closes_one_issue",
        "closes_an_issue_of_its_repository",
        "closes_an_open_issue",
        "closes_an_item",
        "changed_files_were_read",
        "archives_its_change",
        "writes_only_its_own_record",
    ]
