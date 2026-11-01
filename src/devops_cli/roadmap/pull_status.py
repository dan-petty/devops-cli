"""The Status of the item a pull request delivers, set when the pull request opens and when it
is ready for review (#2717).

`devops pr create` sets In Progress and `devops pr ready` sets In Review on the open issue of
this repository that the pull request closes, when that issue is an Item. A Status moves forward
only: In Review never goes back to In Progress, and a Blocked item stays Blocked, because a
person or a stop of the implement job set that, and only a person or a clear rule of the Service
(`stop_clear.py`) takes it out. A pull request that closes no item changes nothing. A closed issue loses its
`status/*` labels in `.github/workflows/clear-status.yml`.
"""

from __future__ import annotations

from typing import Final

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.merge_readiness import read_closing_issues
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.store import ItemField

# The Statuses that each target replaces; no Status at all is replaced too.
_REPLACES: Final[dict[str, frozenset[str | None]]] = {
    CONST_ROADMAP_STATUS_IN_PROGRESS: frozenset(
        {
            None,
            CONST_ROADMAP_STATUS_NEW,
            CONST_ROADMAP_STATUS_READY,
            CONST_ROADMAP_STATUS_PLANNED,
        }
    ),
    CONST_ROADMAP_STATUS_IN_REVIEW: frozenset(
        {
            None,
            CONST_ROADMAP_STATUS_NEW,
            CONST_ROADMAP_STATUS_READY,
            CONST_ROADMAP_STATUS_PLANNED,
            CONST_ROADMAP_STATUS_IN_PROGRESS,
        }
    ),
}


def set_delivered_status(repo: str, pull: int, status: str) -> int | None:
    """Set `status` on the item that pull request `pull` of `repo` (`owner/name`) closes, and
    return its number, or None when the pull request closes no open item of `repo` or the item's
    Status stays. A read that fails raises `GitHubOperationError` with its reason."""
    owner, _, name = repo.partition("/")
    closing = read_closing_issues(owner, name, pull)
    if closing.error:
        raise GitHubOperationError(MESSAGES.pr.status_closing_unread.format(error=closing.error))
    store = roadmap_store.get_roadmap_store(repo)
    for issue in closing.issues:
        item = store.item(issue.number) if issue.is_of(repo) and issue.state == "OPEN" else None
        if item is not None and item.status in _REPLACES[status]:
            store.set_field(item, ItemField.STATUS, status)
            return item.number
    return None
