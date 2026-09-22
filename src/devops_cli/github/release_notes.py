"""Keep published GitHub release descriptions equal to the changelog they came from.

A release body is written once, at publish time, from `CHANGELOG.md`. GitHub can append
its own generated summary underneath, and for this repository that summary is noise: a
release is cut from a single `feat(release): vX.Y.Z` pull request, so "What's Changed"
lists that one pull request and nothing else. Four published releases carry the section
because they were published before the workflow set `generate_release_notes: false`.

Nothing in the repository could remove it afterwards, so the descriptions stayed wrong.
This module republishes a release body from the changelog, which both strips what GitHub
appended and keeps an edited changelog entry reaching the release it describes.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from devops_cli.config.constants import CONST_GENERATED_NOTES_HEADING
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh

logger = logging.getLogger(__name__)

# GitHub appends its generated summary under a level-two heading and closes with a
# comparison link. Both are removed together: the link is part of the same appended block,
# and a body written from the changelog never contains either.
_GENERATED_BLOCK_RE = re.compile(
    rf"\n*^##\s+{re.escape(CONST_GENERATED_NOTES_HEADING)}\s*$.*\Z",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class ReleaseBody:
    """One published release and what its description should say."""

    tag: str
    published: str
    expected: str

    @property
    def differs(self) -> bool:
        """Report whether the published description needs replacing."""
        return self.published.strip() != self.expected.strip()

    @property
    def carries_generated_notes(self) -> bool:
        """Report whether GitHub's generated summary is present in the published body."""
        return bool(_GENERATED_BLOCK_RE.search(self.published))


def strip_generated_notes(body: str) -> str:
    """Remove GitHub's appended summary from a release body."""
    return _GENERATED_BLOCK_RE.sub("", body).rstrip() + "\n"


def list_published_releases(repo: str, limit: int = 100) -> list[str]:
    """List published release tags, newest first."""
    result = run_gh(
        ["release", "list", "--repo", repo, "--limit", str(limit), "--json", "tagName"],
        check=False,
        quiet=True,
    )
    if result.returncode != 0:
        raise GitHubOperationError(f"Could not list releases for '{repo}': {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Malformed release listing for '{repo}': {exc}") from exc
    if not isinstance(payload, list):
        return []
    return [
        str(item["tagName"]) for item in payload if isinstance(item, dict) and "tagName" in item
    ]


def get_release_body(repo: str, tag: str) -> str | None:
    """Return a published release's description, or ``None`` if it cannot be read."""
    result = run_gh(
        ["release", "view", tag, "--repo", repo, "--json", "body"], check=False, quiet=True
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None
    return str(payload.get("body") or "") if isinstance(payload, dict) else None


def set_release_body(repo: str, tag: str, body: str) -> bool:
    """Replace a published release's description, reporting whether it succeeded."""
    result = run_gh(
        ["release", "edit", tag, "--repo", repo, "--notes", body], check=False, quiet=True
    )
    if result.returncode != 0:
        logger.debug("Failed updating release %s: %s", tag, result.stderr.strip())
        return False
    return True


__all__ = [
    "ReleaseBody",
    "get_release_body",
    "list_published_releases",
    "set_release_body",
    "strip_generated_notes",
]
