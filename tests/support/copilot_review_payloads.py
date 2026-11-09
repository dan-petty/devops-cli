"""Copilot's code review as GitHub's REST API records it, in the shapes read from #1283 (#1345).

The reviews endpoint names the bot `copilot-pull-request-reviewer[bot]`. The issue timeline names
the same account (id 175728472) `Copilot`, type Bot: its `reviewed` event carries the id of the
review it records, `copilot_work_started` names the person who asked as its actor, and nothing
but `reviewed` marks the end of a pass. A review request names the account the same way, as
`requested_reviewer`, with its app's `html_url`.
"""

from __future__ import annotations

from typing import Any

COPILOT_APP_URL = "https://github.com/apps/copilot-pull-request-reviewer"
# The account in a review record, as the reviews endpoint names it.
REVIEWS_COPILOT: dict[str, Any] = {
    "login": "copilot-pull-request-reviewer[bot]",
    "id": 175728472,
    "type": "Bot",
    "html_url": COPILOT_APP_URL,
}
# The same account in the issue timeline.
TIMELINE_COPILOT: dict[str, Any] = {
    "login": "Copilot",
    "id": 175728472,
    "type": "Bot",
    "html_url": COPILOT_APP_URL,
}
MAINTAINER: dict[str, Any] = {
    "login": "maintainer",
    "id": 1001,
    "type": "User",
    "html_url": "https://github.com/maintainer",
}
CHANGES_RECOMMENDED = "## Copilot review overview\n\n### 🟡 Changes recommended\n\nRename this."
NO_CHANGES = "## Copilot review overview\n\n### 🟢 No changes recommended\n\nLooks good."
# The ids of #1283's first two Copilot reviews, which its timeline's `reviewed` events carry.
FIRST_REVIEW_ID = 5442444068
SECOND_REVIEW_ID = 5444616621


def copilot_review(
    review_id: int,
    *,
    body: str = CHANGES_RECOMMENDED,
    submitted_at: str = "2026-10-07T12:43:24Z",
    commit_id: str = "bffad060b319",
) -> dict[str, Any]:
    """One of Copilot's reviews, as the reviews endpoint lists it."""
    return {
        "id": review_id,
        "user": REVIEWS_COPILOT,
        "body": body,
        "state": "COMMENTED",
        "submitted_at": submitted_at,
        "commit_id": commit_id,
    }


def review_requested(reviewer: dict[str, Any] = TIMELINE_COPILOT) -> dict[str, Any]:
    """A timeline event: the maintainer asks `reviewer` for a review."""
    return {
        "event": "review_requested",
        "actor": MAINTAINER,
        "review_requester": MAINTAINER,
        "requested_reviewer": reviewer,
    }


def work_started() -> dict[str, Any]:
    """A timeline event: Copilot starts a pass, with the person who asked as its actor."""
    return {"event": "copilot_work_started", "actor": MAINTAINER}


def reviewed(review_id: int, user: dict[str, Any] = TIMELINE_COPILOT) -> dict[str, Any]:
    """A timeline event: review `review_id` was submitted by `user`."""
    return {"id": review_id, "event": "reviewed", "user": user, "state": "commented"}


def copilot_pass(review_id: int) -> list[dict[str, Any]]:
    """The timeline of one finished pass, as #1283 recorded each of its thirteen."""
    return [review_requested(), work_started(), reviewed(review_id)]
