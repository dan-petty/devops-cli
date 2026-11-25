"""Write GitHub read snapshots under `work/github/` for the credential-free agent phase (#6831)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_STAGE_GITHUB_INDEX_BODY_CHARS,
    CONST_ROADMAP_STAGE_GITHUB_INDEX_MAX_ISSUES,
    CONST_ROADMAP_STAGE_ISSUE_BODY_CHARS,
    CONST_ROADMAP_STAGE_ISSUE_COMMENT_CHARS,
    CONST_ROADMAP_STAGE_ISSUE_COMMENTS,
    CONST_ROADMAP_STAGE_ISSUE_TITLE_CHARS,
    CONST_ROADMAP_STAGE_PULL_FILE_PATCH_CHARS,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.stage.stage_overlap import open_pulls
from devops_cli.roadmap.stage.stage_pull_files import named_pull_requests
from devops_cli.roadmap.stores.store import Item
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient, IssueView

_DIR_MODE: Final[int] = 0o700
_FILE_MODE: Final[int] = 0o600
# Match standalone `#<number>` references without matching markdown heading `##1` or URLs `/#1`.
_ISSUE_REF: Final[re.Pattern[str]] = re.compile(r"(?<![\w/#])#(\d+)\b")


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
) -> tuple[dict[str, Any], bool]:
    issue: IssueView = client.get_issue(repo, number)
    comments: list[str] = []
    if issue.comments > 0:
        raw_comments = client.get_last_comments(
            repo, number, total=issue.comments, count=CONST_ROADMAP_STAGE_ISSUE_COMMENTS
        )
        comments = [
            mask_secrets(comment)[:CONST_ROADMAP_STAGE_ISSUE_COMMENT_CHARS]
            for comment in raw_comments
        ]
    closing_pull: int | None = None
    if not issue.is_pull_request and issue.state != "open":
        closing_pull = client.get_closing_pull(repo, number)
    payload = {
        "number": issue.number,
        "state": issue.state,
        "state_reason": issue.state_reason,
        "title": mask_secrets(issue.title)[:CONST_ROADMAP_STAGE_ISSUE_TITLE_CHARS],
        "labels": list(issue.label_names),
        "body": mask_secrets(issue.body or "")[:CONST_ROADMAP_STAGE_ISSUE_BODY_CHARS],
        "comments": comments,
        "is_pull_request": issue.is_pull_request,
        "merged_at": issue.merged_at,
        "closing_pull": closing_pull,
    }
    return payload, issue.is_pull_request


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

    pull_candidates: dict[int, None] = {n: None for n in named_pull_requests([body])}
    for number in referenced_issue_numbers(body, exclude=item_number):
        try:
            payload, is_pr = _read_issue_payload(client, repo, number)
        except GitHubOperationError as exc:
            _record_error(errors, f"#{number}", "issue", exc)
            continue
        _write_snapshot_json(issues_dir / f"{number}.json", payload)
        if is_pr:
            pull_candidates.setdefault(number, None)

    _write_pull_files(pull_files_dir, client, repo, pull_candidates, errors)


def _write_pull_files(
    pull_files_dir: Path,
    client: GitHubClient,
    repo: str,
    numbers: Iterable[int],
    errors: list[dict[str, str]],
) -> None:
    for number in numbers:
        try:
            changed = client.get_pull_files(repo, number)
        except GitHubOperationError as exc:
            _record_error(errors, f"#{number}", "pull_files", exc)
            continue
        payload = {
            "number": number,
            "files": [
                {
                    "filename": entry.filename,
                    "status": entry.status,
                    "previous_filename": entry.previous_filename,
                    "additions": entry.additions,
                    "changes": entry.changes,
                    "patch": (
                        None
                        if entry.patch is None
                        else mask_secrets(entry.patch)[:CONST_ROADMAP_STAGE_PULL_FILE_PATCH_CHARS]
                    ),
                }
                for entry in changed
            ],
        }
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
    try:
        issues = client.list_open_issues(repo, limit=CONST_ROADMAP_STAGE_GITHUB_INDEX_MAX_ISSUES)
    except GitHubOperationError as exc:
        _record_error(errors, "issue-index", "open_issues", exc)
        return
    chunks: list[bytes] = []
    total_bytes = 0
    for issue in issues:
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
