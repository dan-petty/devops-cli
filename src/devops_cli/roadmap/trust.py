"""Which authors the roadmap jobs trust (#2478, #3502).

The repository is public, and a job gives the text of an item to a model that writes into the
roadmap. So a job takes an item only when its author is a person with write access (GitHub's
`author_association` is OWNER, MEMBER or COLLABORATOR), or a bot whose login is exactly the login
of the Service App's bot (`service.github_app.bot_login`) or `github-actions[bot]`. GitHub gives
both bots the association CONTRIBUTOR, so the login is the only proof of who wrote the item.

An item of a bot is also text that a person did not write, so a job takes it only after the review
of refine approved it (`JudgeVerdict`). The approval covers the text that the review read: it holds
while the body hashes as refine recorded with the verdict (`body_hash`). A body edit ends it, and a
refine round reviews the item again. The review is a model, so it is no security control: the login
is the control, and refine's model reads only the replies of trusted authors (`trusted_replies`).
"""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.config.constants import (
    CONST_ROADMAP_ACTIONS_BOT_LOGIN,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.settings import load_settings
from devops_cli.roadmap.body_hash import is_unchanged
from devops_cli.roadmap.store import IssueComment, Item, JudgeVerdict, RefineRecordKey


def bot_logins() -> frozenset[str]:
    """The logins of the bots whose items the jobs take: the Service App's bot, when
    `service.github_app.slug` is set, and `github-actions[bot]`."""
    app = load_settings().service.github_app.bot_login
    return frozenset({CONST_ROADMAP_ACTIONS_BOT_LOGIN} | ({app} if app else set()))


def is_bot_filed(item: Item) -> bool:
    """Whether the author of `item` is a bot that the jobs trust. The login must be equal to one
    of `bot_logins()`, so a login that only resembles it is not trusted."""
    return item.author_login in bot_logins()


def is_trusted(item: Item) -> bool:
    """Whether the jobs take the text of `item`: a person with write access or a trusted bot
    opened it."""
    return item.author_association in CONST_ROADMAP_TRUSTED_AUTHORS or is_bot_filed(item)


def is_approved(item: Item) -> bool:
    """Whether a job that takes `item` after refine may take it: a person opened it, or the review
    of refine approved the item that a bot opened, and its body is still the one that the review
    read."""
    if not is_bot_filed(item):
        return True
    approved = item.job_record.get(RefineRecordKey.JUDGE) == JudgeVerdict.APPROVED.value
    return approved and is_unchanged(item, item.body)


def trusted_replies(comments: Sequence[IssueComment]) -> list[IssueComment]:
    """The comments whose author a person with write access or the Service App's bot is: the only
    comments that reach the model of refine. A comment of any other account, a bot included, does
    not."""
    app = load_settings().service.github_app.bot_login
    return [
        comment
        for comment in comments
        if comment.author_association in CONST_ROADMAP_TRUSTED_AUTHORS
        or (app is not None and comment.author_login == app)
    ]
