"""The title and the body of a plan pull request from the body candidate of the stage agent (#6705).

The stage agent writes the change folder and a body candidate, `PLAN_PULL_REQUEST.md` at the root
of its clone (`CONST_ROADMAP_STAGE_CANDIDATE_FILE`): the line `# <summary>`, then the text of the
body. `devops roadmap plan-recheck --candidate` and `publish` of the stage Job build the title and
the body here, so the agent sees each rule of the texts that `publish` runs:

- The title is `staging_title` of the summary of the candidate. A candidate with no summary, or
  with a summary that does not fit the title, gives the title of the summary of the issue title.
  The round leaves out an item whose title summary does not fit (`long_title_reason`), so that
  summary fits.
- The body is `pull_request_body` of the first text that fits the plan form: the text of the
  candidate, the Why of the proposal, and the summary of the issue title. A text over the room of
  the body goes to the next one, so no size refusal fails a Job. `pull_request_body` and
  `staging_title` call `safe_text` and `safe_title` once, and this module only masks a text
  before it.
- A closing keyword in the title or the text of the candidate is a problem: a plan closes no
  issue.
"""

from __future__ import annotations

from dataclasses import dataclass

from devops_cli.exceptions import RoadmapStageError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import (
    body_room,
    closing_keyword_in,
    pull_request_body,
    safe_text,
    staging_title,
)
from devops_cli.security.sanitizer import mask_secrets

# The heading mark of the line of the summary.
_SUMMARY_MARK = "# "


@dataclass(frozen=True)
class Candidate:
    """The body candidate of the stage agent: the summary of the title and the text of the body,
    each as the agent wrote it."""

    summary: str
    text: str


@dataclass(frozen=True)
class PlanTexts:
    """The title and the body of the plan pull request, and the problems of the candidate."""

    title: str
    body: str
    problems: tuple[str, ...] = ()


def read_candidate(text: str) -> Candidate:
    """The candidate of the file text `text`: the summary of its first line when that line starts
    with `# `, and the rest as the text. A text with no such line has no summary."""
    first, _, rest = text.strip().partition("\n")
    if first.startswith(_SUMMARY_MARK):
        return Candidate(first.removeprefix(_SUMMARY_MARK).strip(), rest.strip())
    return Candidate("", text.strip())


def issue_summary(title: str) -> str:
    """The summary of the issue title `title`: the text after the first colon, or the whole title
    when it has no colon."""
    head, colon, summary = title.partition(":")
    return (summary if colon else head).strip()


def _title(number: int, summary: str, fallback: str) -> str:
    """`staging_title` of `summary`, else of `fallback`."""
    if summary:
        try:
            return staging_title(number, summary)
        except RoadmapStageError:
            pass
    return staging_title(number, fallback)


def _body(number: int, change: str, texts: tuple[str, ...]) -> str:
    """`pull_request_body` of the first of `texts` that fits the plan form, each text masked."""
    room = body_room(number, change)
    last: ValidationError | None = None
    for text in texts:
        masked = mask_secrets(text)
        if not masked.strip() or len(safe_text(masked)) > room:
            continue
        try:
            return pull_request_body(number, change, masked)
        except ValidationError as exc:
            last = exc
    raise RoadmapStageError(
        MESSAGES.roadmap.stage_candidate_no_body.format(number=number, error=last or ""),
        failed_items=[number],
    )


def plan_texts(
    number: int, change: str, issue_title: str, candidate: Candidate | None, why: str
) -> PlanTexts:
    """The title and the body of the plan pull request of item `number`, whose change folder is
    `change`, as the module says: from `candidate`, else from `why`, the Why of the proposal, else
    from `issue_title`. A closing keyword of the candidate is a problem."""
    fallback = issue_summary(issue_title)
    summary = candidate.summary if candidate is not None else ""
    text = candidate.text if candidate is not None else ""
    title = _title(number, summary, fallback)
    problems: list[str] = []
    if candidate is not None:
        keyword = closing_keyword_in(f"{title}\n{safe_text(text)}")
        if keyword is not None:
            problems.append(MESSAGES.roadmap.stage_closing.format(keyword=keyword))
    body = _body(number, change, (text, why, fallback))
    return PlanTexts(title, body, tuple(problems))


__all__ = ["Candidate", "PlanTexts", "issue_summary", "plan_texts", "read_candidate"]
