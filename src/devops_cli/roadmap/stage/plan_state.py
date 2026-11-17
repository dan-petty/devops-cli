"""The plan-state comment of a plan pull request, and the comment of each run (#6197).

No job posts the same content twice (#6193). So the issue of an item holds one plan-state comment
for each plan pull request: the branch, the pull request, the task groups with the tokens of the
inputs of each step, the open findings and the advisory findings. Its hidden key line names the
pull request (`state_key`), and the stage job and the step fix-plan edit it in place with the
marked-comment upsert of `steps/comment.py` (`post`, through `RoadmapStore.edit_comment`): the stage
job on each stage and restage, and the step after each attempt that posts a comment. Each run also
posts one comment with the facts of that run only, under a hidden event line (`event_key`).

`plan_comment_of` gives the comment whose open findings hold for a pull request: its state comment,
else, for a pull request that a release before #6197 staged, the newest legacy plan comment that
names it (the stage comment, or the comment of an attempt of the step). The read skips the comment
of a run, which lists no open finding. The step builds the state comment of such a pull request
from that legacy comment, with the groups of the newest legacy stage comment (`legacy_groups`).
Old comments stay on GitHub as they are.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
    CONST_ROADMAP_PLAN_EVENT_KEY,
    CONST_ROADMAP_PLAN_STATE_KEY,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import safe_text
from devops_cli.roadmap.stage.stage_verify import open_findings_section
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.trust import trusted_replies

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import MeasuredGroup
    from devops_cli.roadmap.stage.stage_verify import Finding
    from devops_cli.roadmap.stores.store import IssueComment, RoadmapStore

# The comments that list the open findings of a plan in a release before #6197: the stage comment
# and the comment of an attempt of the step fix-plan.
_PLAN_MARKERS: Final[tuple[str, ...]] = (
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
)
# The text of the key line of every state comment and of the line of every comment of a run.
_STATE_LEAD: Final[str] = CONST_ROADMAP_PLAN_STATE_KEY.partition("{pull}")[0]
_EVENT_LEAD: Final[str] = CONST_ROADMAP_PLAN_EVENT_KEY.partition("{pull}")[0]


def state_key(pull: int) -> str:
    """The hidden key line of the plan-state comment of the plan pull request `pull`."""
    return CONST_ROADMAP_PLAN_STATE_KEY.format(pull=pull)


def event_key(pull: int) -> str:
    """The hidden line of the comment of one run on the plan pull request `pull`."""
    return CONST_ROADMAP_PLAN_EVENT_KEY.format(pull=pull)


def groups_section(budget: int, groups: Sequence[MeasuredGroup]) -> str:
    """The section of the state comment that lists the task groups, each with the tokens of the
    inputs of its step, for the budget of the run."""
    texts = MESSAGES.roadmap
    listed = "\n".join(
        texts.stage_comment_group.format(
            index=index, title=safe_text(measured.group.title), tokens=measured.tokens
        )
        for index, measured in enumerate(groups, start=1)
    )
    return texts.plan_state_groups.format(budget=budget, groups=listed)


def state_text(
    branch: str,
    pull: int,
    *,
    groups: str = "",
    open_findings: Sequence[Finding] = (),
    advisory: str = "",
) -> str:
    """The plan-state comment of the plan pull request `pull` on `branch`: its marker and its key
    line, then the section of the groups `groups` (`groups_section`), the open findings, and the
    section of the advisory findings `advisory` (`findings_section`)."""
    head = MESSAGES.roadmap.plan_state_comment.format(
        marker=CONST_ROADMAP_STAGE_COMMENT_MARKER,
        key=state_key(pull),
        branch=branch,
        pull=pull,
        groups=groups,
    )
    return head + open_findings_section(open_findings) + advisory


def _first_sentence(template: str) -> str:
    """The first sentence of the heading of a section of findings. A comment of an older release
    can hold another second sentence (#5968)."""
    heading = template.split("{findings}")[0].strip()
    return heading.partition(". ")[0] + "."


def groups_part(body: str) -> str:
    """The section of the task groups of `body`, a state comment or a legacy stage comment, as it
    stands: from its heading to the end of its list. Empty when `body` holds none."""
    lead = MESSAGES.roadmap.plan_state_groups.partition("{budget}")[0]
    start = body.find(lead)
    if start < 0:
        return ""
    listed = body.find("\n\n", start + len(lead))
    if listed < 0:
        return body[start:]
    end = body.find("\n\n", listed + 2)
    return body[start:] if end < 0 else body[start:end]


def advisory_part(body: str) -> str:
    """The section of the advisory findings of `body`, a state comment or a legacy plan comment,
    with each of its lines: the findings that stop no draft. Empty when `body` lists none."""
    template = MESSAGES.roadmap.stage_comment_findings
    _, found, rest = body.partition(_first_sentence(template))
    if not found:
        return ""
    lines: list[str] = []
    for line in rest.partition("\n")[2].lstrip("\n").splitlines():
        if not line.startswith("- "):
            break
        lines.append(line)
    return template.format(findings="\n".join(lines)) if lines else ""


def _new_form(body: str) -> bool:
    """Whether `body` is a state comment or the comment of a run, which #6197 writes."""
    return _STATE_LEAD in body or _EVENT_LEAD in body


def state_of(comments: Sequence[IssueComment], pull: int) -> IssueComment | None:
    """The plan-state comment of `pull` among `comments`, oldest first: the first that holds its
    key, which is the one that the upsert edits."""
    key = state_key(pull)
    return next((comment for comment in comments if key in comment.body), None)


def legacy_comment(comments: Sequence[IssueComment], pull: int) -> str:
    """The newest plan comment of `pull` among `comments` in the form of a release before #6197:
    a comment of the stage job or of the step that names the pull request. A state comment and the
    comment of a run are no legacy comment. Empty when no comment qualifies."""
    names = re.compile(rf"#{pull}\b")
    for comment in reversed(comments):
        body = comment.body
        if _new_form(body):
            continue
        if any(marker in body for marker in _PLAN_MARKERS) and names.search(body):
            return body
    return ""


def legacy_groups(comments: Sequence[IssueComment], pull: int) -> str:
    """The section of the task groups of the newest legacy stage comment of `pull` among
    `comments`, or an empty text when no such comment lists the groups."""
    names = re.compile(rf"#{pull}\b")
    for comment in reversed(comments):
        body = comment.body
        if _new_form(body) or CONST_ROADMAP_STAGE_COMMENT_MARKER not in body:
            continue
        if names.search(body) and (found := groups_part(body)):
            return found
    return ""


def plan_comment_of(comments: Sequence[IssueComment], pull: int) -> str:
    """The comment whose open findings hold for the plan pull request `pull`, among the trusted
    `comments` of its item: its state comment, else its newest legacy plan comment."""
    state = state_of(comments, pull)
    return state.body if state is not None else legacy_comment(comments, pull)


class _TrustedTarget(Target):
    """The issue of an item, whose comments of a trusted author (`trusted_replies`) the upsert
    reads: a comment of another account that copies the key is never the state comment."""

    def list_comments(self) -> Sequence[Any]:
        return trusted_replies(super().list_comments())


def write_state(store: RoadmapStore, repo: str, number: int, pull: int, body: str) -> bool:
    """Write `body` as the plan-state comment of `pull` on issue `number`: an edit of the comment
    that holds its key, or a new comment when none does. It returns whether it wrote."""
    target = _TrustedTarget(repo, number, store=store)
    return post(target, CONST_ROADMAP_STAGE_COMMENT_MARKER, state_key(pull), body)


__all__ = [
    "advisory_part",
    "event_key",
    "groups_part",
    "groups_section",
    "legacy_comment",
    "legacy_groups",
    "plan_comment_of",
    "state_key",
    "state_of",
    "state_text",
    "write_state",
]
