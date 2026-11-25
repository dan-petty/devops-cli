"""Write GitHub read snapshots under `work/github/` for the credential-free agent phase (#6831).

The repository is public, and the agent reads these files. So the snapshot holds only the text of
an author that the jobs trust (`roadmap/trust.py`), as the reads of the planner do
(`stage_github.py`). An issue file holds the title, the body and the comments only for an item
that a person with write access or a trusted bot opened, and only the comments that a person with
write access or the Service App wrote. A pull request file holds the patch text only for such a
pull request. The issue index lists only such an issue.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_STAGE_GITHUB_INDEX_BODY_CHARS,
    CONST_ROADMAP_STAGE_GITHUB_INDEX_MAX_ISSUES,
    CONST_ROADMAP_STAGE_ISSUE_BODY_CHARS,
    CONST_ROADMAP_STAGE_ISSUE_COMMENT_CHARS,
    CONST_ROADMAP_STAGE_ISSUE_TITLE_CHARS,
    CONST_ROADMAP_STAGE_PULL_FILE_PATCH_CHARS,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.stage.stage_github import ITEM_TEXT_LEFT_OUT, last_trusted_comments
from devops_cli.roadmap.stage.stage_overlap import open_pulls
from devops_cli.roadmap.stage.stage_pull_files import named_pull_requests
from devops_cli.roadmap.stores.store import Item
from devops_cli.roadmap.trust import is_trusted
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient, IssueView

_DIR_MODE: Final[int] = 0o700
_FILE_MODE: Final[int] = 0o600
# Match standalone `#<number>` references without matching markdown heading `##1` or URLs `/#1`.
_ISSUE_REF: Final[re.Pattern[str]] = re.compile(r"(?<![\w/#])#(\d+)\b")
# The line that stands for the patch text of a pull request that an account with no write access
# opened.
_PATCH_TEXT_LEFT_OUT: Final[str] = (
    "An account with no write access opened this pull request. Its patch text is left out."
)


def referenced_issue_numbers(body: str, *, exclude: int | None = None) -> list[int]:
    """Positive issue or pull request numbers referenced as `#<number>` in `body`, in order."""
    seen: dict[int, None] = {}
    for raw in _ISSUE_REF.findall(body):
        number = int(raw)
        if number > 0 and number != exclude:
            seen.setdefault(number, None)
    return list(seen)


def _write_snapshot_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(_FILE_MODE)


def _write_snapshot_json(path: Path, payload: object) -> None:
    _write_snapshot_bytes(path, json.dumps(payload, indent=2).encode("utf-8"))


def _record_error(
    errors: list[dict[str, str]], target: str, kind: str, exc: GitHubOperationError
) -> None:
    errors.append(
        {
            "target": target,
            "kind": kind,
            "error": type(exc).__name__,
            "message": mask_secrets(str(exc))[:200],
        }
    )


def _read_issue_payload(
    client: GitHubClient, repo: str, number: int
) -> tuple[dict[str, Any], IssueView]:
    """The file of the issue or pull request `number`, and the item as GitHub gave it. For an item
    that an account with no write access opened (`trust.is_trusted`), the title and the body are
    null, the comments are not read, and `note` says that the text is left out."""
    issue: IssueView = client.get_issue(repo, number)
    trusted = is_trusted(issue)
    comments = last_trusted_comments(client, repo, issue) if trusted else []
    closing_pull: int | None = None
    if not issue.is_pull_request and issue.state != "open":
        closing_pull = client.get_closing_pull(repo, number)
    payload: dict[str, Any] = {
        "number": issue.number,
        "state": issue.state,
        "state_reason": issue.state_reason,
        "title": (
            mask_secrets(issue.title)[:CONST_ROADMAP_STAGE_ISSUE_TITLE_CHARS] if trusted else None
        ),
        "labels": list(issue.label_names),
        "body": (
            mask_secrets(issue.body or "")[:CONST_ROADMAP_STAGE_ISSUE_BODY_CHARS]
            if trusted
            else None
        ),
        "comments": [
            mask_secrets(comment.body)[:CONST_ROADMAP_STAGE_ISSUE_COMMENT_CHARS]
            for comment in comments
        ],
        "is_pull_request": issue.is_pull_request,
        "merged_at": issue.merged_at,
        "closing_pull": closing_pull,
    }
    if not trusted:
        payload["note"] = ITEM_TEXT_LEFT_OUT
    return payload, issue


def _write_issues_and_pull_files(
    github_dir: Path,
    client: GitHubClient,
    repo: str,
    body: str,
    item_number: int,
    errors: list[dict[str, str]],
) -> None:
    issues_dir = github_dir / "issues"
    pull_files_dir = github_dir / "pull-files"
    issues_dir.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
    pull_files_dir.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)

    # Each pull request to read, with whether a trusted author opened it. A named pull request
    # whose author no read gave is not trusted.
    pull_candidates: dict[int, bool] = dict.fromkeys(named_pull_requests([body]), False)
    for number in referenced_issue_numbers(body, exclude=item_number):
        try:
            payload, issue = _read_issue_payload(client, repo, number)
        except GitHubOperationError as exc:
            _record_error(errors, f"#{number}", "issue", exc)
            continue
        _write_snapshot_json(issues_dir / f"{number}.json", payload)
        if issue.is_pull_request:
            pull_candidates[number] = is_trusted(issue)

    _write_pull_files(pull_files_dir, client, repo, pull_candidates, errors)


def _write_pull_files(
    pull_files_dir: Path,
    client: GitHubClient,
    repo: str,
    pulls: Mapping[int, bool],
    errors: list[dict[str, str]],
) -> None:
    """Write the changed files of each pull request of `pulls`. The value says whether a trusted
    author opened the pull request: the file of another pull request holds the name and the
    status of each changed file, a null `patch`, and a `note` that says so."""
    for number, trusted in pulls.items():
        try:
            changed = client.get_pull_files(repo, number)
        except GitHubOperationError as exc:
            _record_error(errors, f"#{number}", "pull_files", exc)
            continue
        payload: dict[str, Any] = {
            "number": number,
            "files": [
                {
                    "filename": entry.filename,
                    "status": entry.status,
                    "previous_filename": entry.previous_filename,
                    "additions": entry.additions,
                    "changes": entry.changes,
                    "patch": (
                        mask_secrets(entry.patch)[:CONST_ROADMAP_STAGE_PULL_FILE_PATCH_CHARS]
                        if trusted and entry.patch is not None
                        else None
                    ),
                }
                for entry in changed
            ],
        }
        if not trusted:
            payload["note"] = _PATCH_TEXT_LEFT_OUT
        _write_snapshot_json(pull_files_dir / f"{number}.json", payload)


def _write_open_pulls(
    github_dir: Path, client: GitHubClient, repo: str, errors: list[dict[str, str]]
) -> None:
    try:
        listed = open_pulls(client, repo)
    except GitHubOperationError as exc:
        _record_error(errors, "pulls", "open_pulls", exc)
        return
    payload = [
        {
            "number": pull.number,
            "title": pull.title,
            "state": pull.state,
            "plan": pull.plan,
            "files": list(pull.files),
        }
        for pull in listed.pulls
    ]
    _write_snapshot_json(github_dir / "pulls.json", payload)


def _write_issue_index(
    github_dir: Path, client: GitHubClient, repo: str, errors: list[dict[str, str]]
) -> None:
    """Write one line for each open issue that a trusted author opened (`trust.is_trusted`). An
    open issue of another account gets no line, so each line holds the same keys."""
    try:
        issues = client.list_open_issues(repo, limit=CONST_ROADMAP_STAGE_GITHUB_INDEX_MAX_ISSUES)
    except GitHubOperationError as exc:
        _record_error(errors, "issue-index", "open_issues", exc)
        return
    chunks: list[bytes] = []
    total_bytes = 0
    for issue in issues:
        if not is_trusted(issue):
            continue
        entry = {
            "ref": f"#{issue.number}",
            "number": issue.number,
            "title": mask_secrets(issue.title)[:CONST_ROADMAP_STAGE_ISSUE_TITLE_CHARS],
            "labels": list(issue.label_names),
            "body": mask_secrets(issue.body or "")[:CONST_ROADMAP_STAGE_GITHUB_INDEX_BODY_CHARS],
        }
        line = (json.dumps(entry, separators=(",", ":")) + "\n").encode("utf-8")
        if total_bytes + len(line) > CONST_ROADMAP_PHASE_JSON_MAX_BYTES:
            break
        chunks.append(line)
        total_bytes += len(line)
    _write_snapshot_bytes(github_dir / "issue-index.jsonl", b"".join(chunks))


def write_github_snapshot(
    github_dir: Path,
    *,
    repo: str,
    item: Item,
    client: GitHubClient | None = None,
) -> Path:
    """Snapshot GitHub reads into `github_dir` for the credential-free agent phase (#6831).

    Failed reads are recorded in `errors.json` and do not abort `prepare`."""
    github_dir.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    if client is None:
        from devops_cli.github.session import get_github_session

        try:
            client = get_github_session().client
        except GitHubOperationError as exc:
            _record_error(errors, "session", "client", exc)
            _write_snapshot_json(github_dir / "errors.json", errors)
            return github_dir

    _write_issues_and_pull_files(github_dir, client, repo, item.body, item.number, errors)
    _write_open_pulls(github_dir, client, repo, errors)
    _write_issue_index(github_dir, client, repo, errors)
    _write_snapshot_json(github_dir / "errors.json", errors)
    return github_dir


__all__ = ["referenced_issue_numbers", "write_github_snapshot"]
