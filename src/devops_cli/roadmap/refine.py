"""`devops roadmap refine`: item refinement to Ready with proposed design, tasks and acceptance criteria.

Without `--item`, refine picks up to `--limit` (default 3) items, nearest place first (#1515):
each open milestone's New items, in milestone order (due date, then number); the backlog's P0 and
P1 items; the backlog's other New items; each place by priority. The number of Ready items does
not stop a round: the board shows that number to the person who plans, and `--limit` is the only
cap (#2004). Each open milestone and the backlog's P0/P1 items also give their Ready items no
refine round has recorded, which refine confirms Ready or sets back to New. It leaves out items
that are Blocked or started, items that an account without write access opened (GitHub's
`author_association` is not OWNER, MEMBER or COLLABORATOR), which wait on a person (#2478),
items whose section a person edited (`check_person_edits`), items unchanged since their last
round that still wait on their next step, and items on which refine wrote
`CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` comments in the last 24 hours, which wait on a person
(#2475), so none of them takes one of the `--limit` places. Selection judges an item by the body
and the author its listing carried, so an item nothing changed costs no body read and no model
call (#1539). The cap reads the comments of each item that the selection would take, once for
the selection. Apply records, logs and counts once each comment that the cap stops: the comment
that would answer the item's newest comment. `--item` refines the item it names whenever it is
open, New or Ready, whoever opened it and however many comments refine wrote on it, since a
person asked for it.

A part of an item that cannot be built as written, or that waits on a question or a block that only
a person or an outside event settles, moves to new issues (`deferred`, #2423) when the rest of the
item is Ready. Intake plans each part; `--confirm` files the parts first, each with a body that
starts with `Split from #<issue>.`, then writes the section and sets Ready. The Ready comment names
the new issues and the job record holds them (`RefineRecordKey.DEFERRED`). A part that intake
cannot place keeps the item New and waiting on a person. An item that is too big for one pull
request still waits for a person to split it.

Every item refine does not set Ready gets a next step (`NextStep`, #1758), recorded in its job
record and posted as one comment that carries `CONST_ROADMAP_REFINE_COMMENT_MARKER`: the open
questions go to a person, a split goes to a person with the proposed items, and open dependencies
block it. A later round looks at an unchanged item again when a comment follows refine's last one,
which costs one comment read for each item that waits, or when every item that blocks it is
closed. The comments since refine's last one reach the model as `replies`. An item refine cannot
write a design for (too big, or two replies that never validated) waits on a body edit alone. An
unchanged item whose record holds no step is refined again so it gets one. The report groups
every item by its next step.
A proposal with a suspected block or an open dependency also names the repository paths whose
code causes the block (`block_paths`). Refine records those that the checkout holds, at most
`CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS`, and a later round looks at the waiting item again when a
commit on the default branch changed one of them at or after refine's last comment (#2005). That
costs one commit read for each recorded path of an item that still waits, once a round.
The check of the alternatives job (#2650) is an input of both model calls (`alternatives`: its
verdict, tool, block and latest comment). A `covers` verdict is a question that only a person
answers: adopt the tool, or keep the item with a reason. It is open, and the item waits on a
person, until a person replies after the job's comment and the proposal answers it (#2652). Refine
records the covering tool it asked about (`RefineRecordKey.ALTERNATIVES_ASKED`); an open New or
Ready item with another covering tool is refined again, though its body is unchanged.
Inputs are minimized from `--source` at HEAD SHA (docs, cited files/lines, identifiers, repo map).
The proposal is one `chat_structured` call with `ai.for_task("analysis")`: its prompts are
`roadmap_refine_proposal.md` and `roadmap_refine_reply.md`, the issue and the body's unanswered key
questions, numbered, reach the model as a JSON document, and `chat_structured` adds the schema each
reply must match. Deterministic validation checks sources, key questions and owner decisions. When
a fact or a decision has no verified source, or a body question no answer names, the investigation
(`refine_investigation`, #2398) runs one pydantic-ai agent with read-only tools on the pinned commit,
and with Firecrawl web search when the repository is public and a key is set; its revised proposal is
validated the same way. A decision names the options it compared, a question only a person can
decide waits on a person, and the Ready check sets Status New → Ready only when complete. The plan
says when web search is off, and why.
A model call that fails skips only its item: refine writes the others, then fails with
`RoadmapRefineError` naming each skipped item, its error's class and its schema violation count.
Rejected credentials still stop the run at the first item.
An item whose refined body would pass the size limit is recorded rather than tried again: apply
writes no body and records the hashes of the body it saw, so the item reads as unchanged until its
body changes. A reply about an item that never validated (`StructuredOutputValidationError` or
`ReplyRejectedError`) records the body's hash as failed, and a second one on the same body settles
the item the same way. A failure that says nothing about the item, such as a timeout, records
nothing (#1526).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel, ConfigDict, Field, field_validator

from devops_cli.ai.client import LLMClient, get_llm_client
from devops_cli.ai.client.factory import get_task_model
from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    ReplyRejectedError,
    StructuredOutputValidationError,
)
from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_JOB_COMMENT_MARKERS,
    CONST_ROADMAP_P0_PRIORITY,
    CONST_ROADMAP_P1_PRIORITY,
    CONST_ROADMAP_P2_PRIORITY,
    CONST_ROADMAP_P3_PRIORITY,
    CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_HELD_STATUSES,
    CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS,
    CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
    CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM,
    CONST_ROADMAP_REFINE_MAX_REPLIES,
    CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    CONST_ROADMAP_REFINE_NO_BLOCK_TEXTS,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_REFINE_LIMIT
from devops_cli.config.settings import get_firecrawl_api_key, load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.exceptions.roadmap import RoadmapRefineError
from devops_cli.exceptions.security import SecurityError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake import (
    IntakePlan,
    NewCandidate,
    Outcome,
    apply_intake,
    plan_intake,
)
from devops_cli.roadmap.intake_model import IntakeModel, build_intake_model
from devops_cli.roadmap.refine_investigation import (
    InvestigationStopped,
    InvestigationTools,
    investigate,
)
from devops_cli.roadmap.store import (
    AlternativesRecordKey,
    GitHubState,
    IssueComment,
    Item,
    ItemField,
    JobRecord,
    RefineRecordKey,
    RoadmapStore,
    Verdict,
)
from devops_cli.telemetry.instruments import ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL, emit

logger = logging.getLogger(__name__)

# ── Models ────────────────────────────────────────────────────────────────────


# OpenSpec's test of a requirement's text: the word SHALL or MUST, in capitals
# (`containsShallOrMust` in OpenSpec 1.14.3, `dist/core/parsers/requirement-text.js`).
_SHALL_OR_MUST: Final[re.Pattern[str]] = re.compile(r"\b(SHALL|MUST)\b")


class AcceptanceCriterion(BaseModel):
    """One requirement of the change in the shape of an OpenSpec spec delta (#1849): the
    requirement's `name` and its `requirement` text, which says SHALL or MUST, and one scenario,
    `scenario`, with its `when` and `then`. The rendered block goes into a change's spec delta as
    it is."""

    model_config = ConfigDict(extra="forbid")
    name: str
    requirement: str
    scenario: str
    when: str
    then: str

    @field_validator("requirement")
    @classmethod
    def _says_shall_or_must(cls, requirement: str) -> str:
        if not _SHALL_OR_MUST.search(requirement):
            raise ValueError(MESSAGES.roadmap.refine_requirement_keyword)
        return requirement


class DesignOption(BaseModel):
    """One option a decision compared, and why it was chosen or rejected (#2398)."""

    model_config = ConfigDict(extra="forbid")
    option: str
    chosen: bool = False
    reason: str


class QuestionAnswer(BaseModel):
    """A question and its answer. `kind` is `fact`, `decision`, or `person` for a decision only
    a person makes; `body_question` is the number of the body's key question it answers (#2398)."""

    model_config = ConfigDict(extra="forbid")
    question: str
    answer: str
    kind: Literal["fact", "decision", "person"]
    sources: list[str] = Field(default_factory=list)
    options: list[DesignOption] = Field(default_factory=list)
    body_question: int | None = None


# The most parts that one proposal moves to new issues (#2423): intake makes one embedding call and
# one proposal call for each part.
_MAX_DEFERRED_PARTS: Final[int] = 3


class DeferredPart(BaseModel):
    """A part of the item that cannot be built as written, or that waits on a question or a block
    that only a person or an outside event settles. Refine files it as a new issue so that the
    rest of the item can reach Ready (#2423)."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class RefinementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_statement: str
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    existing_tool: str
    key_questions: list[QuestionAnswer] = Field(default_factory=list)
    fits_one_pr: bool = True
    split_offs: list[str] = Field(default_factory=list)
    suspected_block: str | None = None
    dependencies: list[int] = Field(default_factory=list)
    block_paths: list[str] = Field(default_factory=list)
    deferred: list[DeferredPart] = Field(default_factory=list, max_length=_MAX_DEFERRED_PARTS)


class NextStep(StrEnum):
    """What an item waits on after a refine round, and what makes refine look at it again (#1758).

    `READY`: refine set it to Ready. `PERSON`: a person answers the questions refine asked in a
    comment. `SPLIT`: a person splits it as refine proposed in a comment. `BLOCKED`: the open
    items it depends on close. A reply after refine's last comment, a body edit, or a commit on
    the default branch after that comment that changes a path the block cites (#2005) ends each
    of these waits, and a closed blocker ends `BLOCKED`. `EDIT`: refine cannot write a design
    for the body, and only a body edit ends the wait. `NONE`: refine changes no item that is
    closed, In Progress, Done or Blocked.
    """

    READY = "ready"
    PERSON = "person"
    SPLIT = "split"
    BLOCKED = "blocked"
    EDIT = "edit"
    NONE = "none"


@dataclass(frozen=True)
class PlannedDeferral:
    """A deferred part as refine files it, its text sanitized, and the intake plan of the new
    issue (#2423)."""

    part: DeferredPart
    plan: IntakePlan


@dataclass(frozen=True)
class RefinedItem:
    """An item's refinement. When `skip_reason` is set none of it is written; with `record_only`
    apply still records the hashes of the body refine saw, so the item reads as unchanged until
    its body changes (#1526). `next_step` is what the item waits on, with `step_details` (the
    questions, the split or the blockers) and the open items `blocked_by` (#1758), and
    `block_paths` the paths whose code causes the block (#2005). `body_hash` is the hash of the
    body without the alternatives job's block and refine's section, which the check for an
    unchanged item compares; `read_hash` is the hash of the body without the section alone, which
    the check before a write compares, so a block written since the read is not lost.
    `alternatives_asked` is the URL of the covering tool that the round put to a person (#2652).
    `deferred` holds the parts that apply files as new issues before it sets the item Ready
    (#2423)."""

    item: Item
    proposal: RefinementProposal
    open_questions: list[str]
    is_ready: bool
    needs_split: bool
    reason_comment: str | None
    new_body: str
    body_hash: str
    section_hash: str | None
    next_step: NextStep
    step_details: tuple[str, ...] = ()
    blocked_by: tuple[int, ...] = ()
    block_paths: tuple[str, ...] = ()
    alternatives_asked: str | None = None
    read_hash: str = ""
    skip_reason: str | None = None
    record_only: bool = False
    deferred: tuple[PlannedDeferral, ...] = ()


@dataclass(frozen=True)
class WaitingItem:
    """An item refine did not refine in this round, with the next step it waits on (#1758):
    `details` names the open items it waits on, or why refine leaves it alone.

    `cap_stop` is set when the cap on refine's comments stops the comment that would answer the
    item's newest comment, and no earlier round stopped it: the newest comment's creation time,
    which apply records in the item's job record, logs and counts (#2475).
    """

    item: Item
    step: NextStep
    details: tuple[str, ...] = ()
    cap_stop: str | None = None


@dataclass(frozen=True)
class RefineFailure:
    """An item refine skipped because its model call failed: the error's class name and the
    last reply's schema violation count (0 when it held no JSON, or the call got no reply),
    never the model's text.

    `item_caused` is set when the model answered about the item and no answer validated, which
    the item's own text brings again, so apply records it (#1526). A timeout or a dropped stream
    says nothing about the item.
    """

    item: Item
    error: str
    violations: int = 0
    item_caused: bool = False

    @classmethod
    def of(cls, item: Item, exc: AIClientError) -> RefineFailure:
        """The failure `exc` made of `item`'s model call."""
        violations = exc.violations if isinstance(exc, StructuredOutputValidationError) else 0
        return cls(
            item=item,
            error=type(exc).__name__,
            violations=violations,
            item_caused=isinstance(exc, StructuredOutputValidationError | ReplyRejectedError),
        )


@dataclass(frozen=True)
class RefinePlan:
    repo: str
    sha: str = ""
    refined_items: list[RefinedItem] = field(default_factory=list)
    waiting_items: list[WaitingItem] = field(default_factory=list)
    has_writes: bool = False
    failed_items: list[RefineFailure] = field(default_factory=list)
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()
    web_search_off: str | None = None


@dataclass(frozen=True)
class RefineApplied:
    refined_count: int
    readied_count: int
    split_count: int
    comments_posted: int


# ── Parsing & Hashes ──────────────────────────────────────────────────────────


def extract_section_and_outside(
    body: str,
    start_marker: str = CONST_ROADMAP_REFINE_START_MARKER,
    end_marker: str = CONST_ROADMAP_REFINE_END_MARKER,
) -> tuple[str, str | None]:
    """Returns (body_outside_section, section_inside_markers_or_none). The section is the one
    between the two markers, refine's by default; another job's block (#2650) has its own."""
    start_idx = body.find(start_marker)
    if start_idx == -1:
        return body, None
    end_idx = body.find(end_marker, start_idx + len(start_marker))
    if end_idx == -1:
        return body, None

    section_inside = body[start_idx + len(start_marker) : end_idx]
    outside = body[:start_idx] + body[end_idx + len(end_marker) :]
    return outside, section_inside


def hash_text(text: str) -> str:
    """SHA-256 hex digest of stripped text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _body_hashes(body: str) -> tuple[str, str | None]:
    """The hash of `body` outside its refine section, and the section's, None when it holds none.
    The block of the alternatives job (#2650) is no part of either: it is not a person's text."""
    body, _ = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    outside, inside = extract_section_and_outside(body)
    return hash_text(outside), (hash_text(inside) if inside else None)


def _is_unchanged(item: Item, body: str) -> bool:
    """Whether `body` hashes as refine last recorded for `item`, outside the section and in it."""
    recorded = (
        item.job_record.get(RefineRecordKey.BODY_HASH),
        item.job_record.get(RefineRecordKey.SECTION_HASH),
    )
    return _body_hashes(body) == recorded


# ── The check of the alternatives job (#2652) ────────────────────────────────


@dataclass(frozen=True)
class RecordedCheck:
    """The check of the alternatives job (#2650) that an item holds: its verdict and tool from the
    job record, and its block from the body. A record with no block is no check, since a person
    deleted the block."""

    verdict: Verdict
    tool: str | None
    block: str


@dataclass(frozen=True)
class CoversQuestion:
    """The question a `covers` verdict puts to a person: adopt the tool, or keep the item with a
    reason. `answered` is set when a person replied after the job's latest comment, and then the
    proposal must answer the question. `answers` holds those replies (the newest ones, each cut to
    its token cap): the request carries them, as `replies` loses them once refine comments again."""

    text: str
    answered: bool
    answers: tuple[str, ...] = ()


def recorded_check(item: Item, body: str) -> RecordedCheck | None:
    """The check of the alternatives job that `item` holds in its job record and in `body`, or
    None when it holds none."""
    _, block = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    recorded = item.job_record.get(AlternativesRecordKey.VERDICT)
    if block is None or not recorded:
        return None
    try:
        verdict = Verdict(recorded)
    except ValueError:
        return None
    tool = item.job_record.get(AlternativesRecordKey.TOOL) or None
    return RecordedCheck(verdict, tool, block.strip())


def _covering_tool(item: Item) -> str | None:
    """The URL of the tool that the item's recorded check found to cover it, or None."""
    check = recorded_check(item, item.body)
    return check.tool if check is not None and check.verdict is Verdict.COVERS else None


def _needs_second_look(item: Item) -> bool:
    """Whether the item holds a covering tool that no refine round put to a person: refine
    looks at the item again, though its body is unchanged and it waits on a person or is Ready.
    An item that waits on a body edit alone is left to that edit (#2652)."""
    tool = _covering_tool(item)
    asked = item.job_record.get(RefineRecordKey.ALTERNATIVES_ASKED)
    return tool is not None and tool != asked and _recorded_step(item) is not NextStep.EDIT


def _latest_check_comment(comments: Sequence[IssueComment]) -> IssueComment | None:
    """The alternatives job's newest comment, or None when it left none."""
    marked = [c for c in comments if CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER in c.body]
    return marked[-1] if marked else None


def _alternatives_request(
    check: RecordedCheck | None, comments: Sequence[IssueComment], covers: CoversQuestion | None
) -> dict[str, Any] | None:
    """The `alternatives` key of a request: the recorded check with the job's latest comment,
    which lists what the tool covers and lacks, and the replies of persons that answer a `covers`
    question, or None when the item holds no check."""
    if check is None:
        return None
    latest = _latest_check_comment(comments)
    return {
        "verdict": check.verdict.value,
        "tool": check.tool,
        "block": check.block,
        "comment": (
            truncate_to_token_limit(latest.body, max_tokens=CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS)
            if latest
            else None
        ),
        "answers": list(covers.answers) if covers is not None else [],
    }


def covers_question(
    check: RecordedCheck | None, comments: Sequence[IssueComment]
) -> CoversQuestion | None:
    """The question that a `covers` check puts to a person, or None for any other check. It is
    answered when a comment of a person follows the job's latest comment, or any comment of a
    person when the job left none: a comment of a roadmap job is none."""
    if check is None or check.verdict is not Verdict.COVERS or not check.tool:
        return None
    after_check = replies_after_marker(comments, CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER)
    persons = _comments_without(
        comments if after_check is None else after_check, CONST_ROADMAP_JOB_COMMENT_MARKERS
    )
    answers = tuple(
        truncate_to_token_limit(reply.body, max_tokens=CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS)
        for reply in persons[-CONST_ROADMAP_REFINE_MAX_REPLIES:]
    )
    return CoversQuestion(
        MESSAGES.roadmap.refine_alternatives_question.format(url=check.tool),
        bool(persons),
        answers,
    )


def _asked_questions(body: str, covers: CoversQuestion | None) -> list[str]:
    """The questions the request numbers: the body's unanswered key questions, then the `covers`
    question once a person has replied to it."""
    asked = body_questions(body)
    return [*asked, covers.text] if covers is not None and covers.answered else asked


# ── Git & Checkout Inspection ─────────────────────────────────────────────────


def _git(checkout: Path, *args: str) -> tuple[int, str]:
    proc = run_subprocess(
        [BIN_GIT, "-C", str(checkout), *args],
        env={"GIT_TERMINAL_PROMPT": "0"},
        timeout=15,
        quiet=True,
    )
    return proc.returncode, proc.stdout if proc.returncode == 0 else (proc.stderr or "").strip()


def inspect_checkout(source: Path | str, expected_repo: str) -> str:
    """Inspects the checkout at `source`, verifies origin matches `expected_repo`, and returns
    its HEAD sha, which pins the code refine read. Raises GitHubOperationError if origin
    mismatch.
    """
    path = Path(source)
    origin_name = get_repo_origin_name(path)
    if not origin_name or origin_name.lower() != expected_repo.lower():
        raise GitHubOperationError(
            f"Checkout at {source} origin ({origin_name}) does not match expected repository {expected_repo}.",
            operation="roadmap.refine.inspect_checkout",
            details={
                "source": str(source)[:256],
                "origin": str(origin_name)[:256],
                "expected": expected_repo[:256],
            },
        )
    code_sha, sha = _git(path, "rev-parse", "HEAD")
    sha = sha.strip()
    if code_sha != 0 or not sha:
        raise GitHubOperationError(
            f"Could not determine HEAD SHA in {source}.",
            operation="roadmap.refine.inspect_checkout",
            details={"source": str(source)[:256]},
        )
    return sha


# ── Context Minimization ──────────────────────────────────────────────────────

_CITED_PATH_RE = re.compile(
    r"(?:[\s\(\[`]|^)([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9_]+)(?::(\d+)(?:-(\d+))?)?(?:[\s\)\]`:]|$)"
)
_BACKTICK_IDENT_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]{2,})`")


def _read_git_file(source: Path, sha: str, path: str) -> str | None:
    code_exists, _ = _git(source, "cat-file", "-e", f"{sha}:{path}")
    if code_exists != 0:
        return None
    code_show, content = _git(source, "show", f"{sha}:{path}")
    return content if code_show == 0 else None


def _slice_lines(content: str, start: int | None, end: int | None) -> str:
    lines = content.splitlines()
    if start is None:
        return content
    s = max(1, start) - 1
    e = min(len(lines), end or start)
    return "\n".join(lines[s:e])


def _collect_cited_files(source: Path, sha: str, body: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in _CITED_PATH_RE.finditer(body):
        path, start_s, end_s = match.group(1), match.group(2), match.group(3)
        if ".." in path or path.startswith("/") or path in found:
            continue
        content = _read_git_file(source, sha, path)
        if content is not None:
            start = int(start_s) if start_s else None
            end = int(end_s) if end_s else None
            found[path] = _slice_lines(content, start, end)
            if len(found) >= 10:
                break
    return found


def _collect_identifiers(source: Path, sha: str, body: str) -> list[str]:
    raw_idents = {m.group(1) for m in _BACKTICK_IDENT_RE.finditer(body)}
    results: list[str] = []
    for ident in sorted(raw_idents)[:5]:
        code, out = _git(source, "grep", "-n", "-F", "-w", "-e", ident, sha, "--")
        if code == 0 and out:
            lines = out.splitlines()[:5]
            results.extend(lines)
        if len(results) >= 20:
            break
    return results[:20]


def _collect_repo_map(source: Path, sha: str, paths: Sequence[str]) -> list[str]:
    dirs = {str(Path(p).parent) for p in paths if "/" in p}
    files: list[str] = []
    for d in sorted(dirs):
        code, out = _git(source, "ls-tree", "-r", "-z", "--name-only", sha, d)
        if code == 0 and out:
            items = out.split("\0") if "\0" in out else out.splitlines()
            files.extend([f for f in items if f][:15])
        if len(files) >= 50:
            break
    return files[:50]


def collect_context(
    source: Path,
    sha: str,
    body: str,
    max_tokens: int,
) -> str:
    """Collects docs, cited code, grep results, and repo map, capped to token budget."""
    sections: list[str] = []

    # CONTEXT.md
    ctx = _read_git_file(source, sha, "CONTEXT.md")
    if ctx:
        sections.append(f"### CONTEXT.md\n{ctx}")

    # docs/adr/*.md
    code_adr, adr_list = _git(source, "ls-tree", "-r", "-z", "--name-only", sha, "docs/adr")
    if code_adr == 0 and adr_list:
        adr_items = adr_list.split("\0") if "\0" in adr_list else adr_list.splitlines()
        for adr_path in [p for p in adr_items if p][:5]:
            adr_content = _read_git_file(source, sha, adr_path)
            if adr_content:
                sections.append(f"### {adr_path}\n{adr_content}")

    # Cited files
    cited = _collect_cited_files(source, sha, body)
    for p, text in cited.items():
        sections.append(f"### Code: {p}\n{text}")

    # Backticked identifiers
    grep_hits = _collect_identifiers(source, sha, body)
    if grep_hits:
        sections.append("### Identifier matches\n" + "\n".join(grep_hits))

    # Repo map
    repo_files = _collect_repo_map(source, sha, list(cited.keys()))
    if repo_files:
        sections.append("### Relevant Directory Tree\n" + "\n".join(repo_files))

    raw_text = "\n\n".join(sections)
    return truncate_to_token_limit(raw_text, max_tokens=max_tokens)


# ── Web Search State ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WebSearch:
    """The round's web search: the Firecrawl key the investigation searches with, or, when web
    search is off, the reason, which the plan reports once (#2398)."""

    key: str | None = None
    off_reason: str | None = None


def web_search_of(store: RoadmapStore) -> WebSearch:
    """The round's web search: on for a public repository with a Firecrawl key, else off with the
    reason. A failed read of the repository's visibility turns it off; a spent quota stops the
    round."""
    texts = MESSAGES.roadmap
    try:
        is_private = store.repository_is_private()
    except GitHubRateLimitError:
        raise
    except GitHubOperationError as exc:
        logger.warning("Could not read repository visibility: %s", exc)
        return WebSearch(off_reason=texts.refine_web_off_unread)
    if is_private:
        return WebSearch(off_reason=texts.refine_web_off_private)
    key = get_firecrawl_api_key()
    return WebSearch(key=key) if key else WebSearch(off_reason=texts.refine_web_off_no_key)


# ── Proposal Validation ───────────────────────────────────────────────────────

_OWNER_DECISIONS_HEADING_RE = re.compile(r"^#+\s*Owner decisions\b", re.IGNORECASE)


# The marks an answer's text gets: a fact with no source and a person's question open a question,
# and a decision follows the owner, a sourced best practice, or is only proposed (#2398).
_MISSING_SOURCE: Final[str] = "(missing verified source)"
_A_PERSON_DECIDES: Final[str] = "(a person decides)"
_OWNER_DECISION: Final[str] = "(owner decision)"
_BEST_PRACTICE: Final[str] = "(best practice)"
_PROPOSED: Final[str] = "(proposed)"
_MARKS_RE = re.compile(
    "|".join(
        re.escape(mark)
        for mark in (_MISSING_SOURCE, _A_PERSON_DECIDES, _OWNER_DECISION, _BEST_PRACTICE, _PROPOSED)
    )
)
# How the investigation's request names a decision that has no verified source (#2398).
_DECISION_WITHOUT_SOURCE: Final[str] = "(decision with no verified source)"

# The characters that can close a question's text without answering it.
_EMPHASIS_CHARS: Final[str] = "*_` \t"
_KEY_QUESTIONS_TITLE_RE = re.compile(r"Key questions\b", re.IGNORECASE)
_DEPENDENCIES_TITLE_RE = re.compile(r"Dependencies\b", re.IGNORECASE)
# The punctuation that can follow or wrap an issue reference in a list of them, such as `(#12),`.
_REFERENCE_PUNCTUATION: Final[str] = ".,;:()[]"


def _section_tokens(tokens: Sequence[Token], title_re: re.Pattern[str]) -> list[Token]:
    """The tokens under the first heading whose title `title_re` matches, up to the next heading
    of the same or a higher level; a lower heading stays inside the section."""
    for index, token in enumerate(tokens[:-1]):
        if token.type == "heading_open" and title_re.match(tokens[index + 1].content.strip()):
            level = int(token.tag[1:])
            rest = tokens[index + 3 :]
            end = next(
                (
                    i
                    for i, other in enumerate(rest)
                    if other.type == "heading_open" and int(other.tag[1:]) <= level
                ),
                len(rest),
            )
            return list(rest[:end])
    return []


def _top_items(tokens: Sequence[Token]) -> list[list[Token]]:
    """The tokens inside each top-level list item of `tokens`, in order."""
    items: list[list[Token]] = []
    for token in tokens:
        if token.type == "list_item_open" and token.level == 1:
            items.append([])
        elif token.type == "list_item_close" and token.level == 1:
            continue
        elif items and token.level > 1:
            items[-1].append(token)
    return items


def _unanswered_question(item: Sequence[Token]) -> str | None:
    """The question an item asks when nothing answers it, else None.

    The item's first paragraph is its text, its wrapped lines joined. Text after the last
    question mark, other than emphasis, answers it in place, and so does any block after that
    paragraph inside the item, such as a nested list, a paragraph or a code block.
    """
    if len(item) < 3 or item[0].type != "paragraph_open" or item[1].type != "inline":
        return None
    text = " ".join(item[1].content.split())
    _, mark, after = text.rpartition("?")
    answered = bool(after.strip(_EMPHASIS_CHARS)) or len(item) > 3
    return text if mark and not answered else None


def body_questions(body: str) -> list[str]:
    """The key questions the body leaves unanswered, in order (#2398).

    Under the person's "Key questions" heading, outside refine's own section, each top-level
    list item that asks a question (its first paragraph holds a question mark) and that nothing
    answers (`_unanswered_question`) is a question. A list item with no question mark, and a
    paragraph or a code block outside the list, is not. The body is parsed as CommonMark, so a
    question that wraps to a second line stays one question, and a heading in a code block is
    not a heading.
    """
    persons_text, _ = extract_section_and_outside(body)
    section = _section_tokens(MarkdownIt("commonmark").parse(persons_text), _KEY_QUESTIONS_TITLE_RE)
    asked = (_unanswered_question(item) for item in _top_items(section))
    return [question for question in asked if question]


def body_dependencies(body: str) -> list[int]:
    """The issues the body names under a "Dependencies" heading, in order (#2654).

    The section is the one refine writes (`render_proposal_section`) or a person writes: the
    text under the heading, up to the next heading of the same or a higher level. A word that is
    `#` and digits, with the punctuation of a list around it, is an issue; the body is parsed as
    CommonMark, so a heading in a code block is not a heading.
    """
    section = _section_tokens(MarkdownIt("commonmark").parse(body), _DEPENDENCIES_TITLE_RE)
    words = (
        word.strip(_REFERENCE_PUNCTUATION)
        for token in section
        if token.type == "inline"
        for word in token.content.split()
    )
    return [int(word[1:]) for word in words if word.startswith("#") and word[1:].isdigit()]


def _extract_heading_bullets(body: str, heading_re: re.Pattern[str]) -> list[str]:
    lines = body.splitlines()
    in_section = False
    bullets: list[str] = []
    for line in lines:
        if line.startswith("#"):
            if heading_re.match(line.strip()):
                in_section = True
                continue
            elif in_section:
                break
        if in_section:
            stripped = line.strip()
            if stripped.startswith(("-", "*")) or (
                len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ". "
            ):
                content = re.sub(r"^([-\*]|\d+\.)\s+", "", stripped)
                if content:
                    bullets.append(content)
            elif stripped and not bullets:
                bullets.append(stripped)
    return bullets


def _checkout_path(cited: str, source: Path, sha: str) -> str | None:
    """The repository path that `cited` names, without its line, when the checkout holds it at
    `sha`; None for other text and for a path outside the repository."""
    match = _CITED_PATH_RE.match(cited.strip())
    if match is None:
        return None
    path = match.group(1)
    if ".." in path or path.startswith("/"):
        return None
    code, _ = _git(source, "cat-file", "-e", f"{sha}:{path}")
    return path if code == 0 else None


def _block_paths(cited: Sequence[str], source: Path, sha: str) -> list[str]:
    """The checkout's paths among `cited`, each one time and without its line, at most
    `CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS` of them (#2005)."""
    kept: list[str] = []
    for text in cited:
        path = _checkout_path(text, source, sha)
        if path is not None and path not in kept:
            kept.append(path)
        if len(kept) >= CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS:
            break
    return kept


def _is_valid_source(src: str, allowed_urls: set[str], source: Path, sha: str) -> bool:
    if src in allowed_urls or urlsplit(src).scheme in {"http", "https"}:
        return src in allowed_urls
    match = _CITED_PATH_RE.match(src.strip())
    if not match:
        return False
    path = match.group(1)
    line_s = match.group(2)
    content = _read_git_file(source, sha, path)
    if content is None:
        return False
    if line_s:
        line_num = int(line_s)
        total_lines = len(content.splitlines())
        return 1 <= line_num <= max(1, total_lines)
    return True


def _marked(qa: QuestionAnswer, owner_decisions: Sequence[str]) -> QuestionAnswer:
    """`qa` with the one mark of its kind: a person's question, or a decision that quotes an
    owner decision, follows a best practice with a verified source, or is only proposed (#2398).
    A mark the model copied from an earlier section goes first, so the answer holds one."""
    if qa.kind == "fact":
        return qa
    answer = " ".join(_MARKS_RE.sub("", qa.answer).split())
    marker = _A_PERSON_DECIDES
    if qa.kind == "decision":
        quotes_owner = any(d in answer.lower() for d in owner_decisions if len(d) > 5)
        marker = _OWNER_DECISION if quotes_owner else _BEST_PRACTICE if qa.sources else _PROPOSED
    return qa.model_copy(update={"answer": f"{answer} {marker}".strip()})


def validate_proposal(
    proposal: RefinementProposal,
    body: str,
    allowed_urls: set[str],
    source: Path,
    sha: str,
    store: RoadmapStore,
    covers: CoversQuestion | None = None,
) -> tuple[RefinementProposal, list[str]]:
    """Deterministically validates proposal sources, key questions, decisions and block paths.
    Returns (validated_proposal, open_questions).

    A fact with no verified source and a question only a person decides are open questions, and
    so is each of the body's unanswered key questions whose number no answer names (#2398). The
    key questions and owner decisions are the person's, read from the body outside refine's
    own section, so a refined item's section never asks its own questions again (#1758). Only
    the block paths that the checkout holds are kept (#2005). A `covers` question (#2652) is open
    with the mark of a question for a person until a person replies; after that it is numbered
    after the body's questions, and open until an answer names it.
    """
    open_questions: list[str] = []
    validated_qa: list[QuestionAnswer] = []
    persons_text, _ = extract_section_and_outside(body)
    owner_decisions = [
        line.strip().lower()
        for line in _extract_heading_bullets(persons_text, _OWNER_DECISIONS_HEADING_RE)
    ]

    for qa in proposal.key_questions:
        valid_srcs = [s for s in qa.sources if _is_valid_source(s, allowed_urls, source, sha)]
        if qa.kind == "fact" and not valid_srcs:
            open_questions.append(f"{qa.question} {_MISSING_SOURCE}")
            continue
        if qa.kind == "person":
            open_questions.append(f"{qa.question} {_A_PERSON_DECIDES}")
        validated_qa.append(_marked(qa.model_copy(update={"sources": valid_srcs}), owner_decisions))

    named = {qa.body_question for qa in proposal.key_questions}
    open_questions.extend(
        asked
        for number, asked in enumerate(_asked_questions(body, covers), start=1)
        if number not in named
    )
    if covers is not None and not covers.answered:
        open_questions.append(f"{covers.text} {_A_PERSON_DECIDES}")

    all_known_issues: set[int] = (
        {item.number for item in store.items()} if hasattr(store, "items") else set()
    )
    valid_deps = [dep for dep in proposal.dependencies if dep in all_known_issues]

    validated_proposal = proposal.model_copy(
        update={
            "key_questions": validated_qa,
            "dependencies": valid_deps,
            "block_paths": _block_paths(proposal.block_paths, source, sha),
        }
    )
    return validated_proposal, open_questions


def needs_investigation(proposal: RefinementProposal, open_questions: Sequence[str]) -> bool:
    """Whether a validated proposal leaves what the investigation can settle: an open question
    that is not a person's, or a decision with no verified source (#2398)."""
    persons = sum(qa.kind == "person" for qa in proposal.key_questions)
    proposed = any(
        qa.kind == "decision" and qa.answer.endswith(_PROPOSED) for qa in proposal.key_questions
    )
    return len(open_questions) > persons or proposed


def _suspected_block(proposal: RefinementProposal) -> str | None:
    """The proposal's suspected block, or None when it names none."""
    block = (proposal.suspected_block or "").strip()
    return None if block.lower() in CONST_ROADMAP_REFINE_NO_BLOCK_TEXTS else block


def _complete(criterion: AcceptanceCriterion) -> bool:
    """Whether each part of a criterion's requirement block has text."""
    return all(part.strip() for part in criterion.model_dump().values())


def check_ready(proposal: RefinementProposal, open_questions: Sequence[str]) -> bool:
    """Deterministic check: a problem statement, 1+ criterion with every part of its requirement
    block, an answer to the existing-tool question (#1849), no open questions, fits one PR, and
    no suspected block.
    """
    if not proposal.problem_statement.strip() or not proposal.existing_tool.strip():
        return False
    if not proposal.acceptance_criteria:
        return False
    if not all(_complete(criterion) for criterion in proposal.acceptance_criteria):
        return False
    if open_questions:
        return False
    if not proposal.fits_one_pr:
        return False
    return _suspected_block(proposal) is None


def _is_open(store: RoadmapStore, number: int) -> bool:
    """Whether issue `number` is an open Item."""
    found = store.item(number)
    return found is not None and found.state is GitHubState.OPEN


def next_step_of(
    store: RoadmapStore,
    proposal: RefinementProposal,
    open_questions: Sequence[str],
    *,
    is_ready: bool,
) -> tuple[NextStep, tuple[str, ...], tuple[int, ...]]:
    """The next step a validated proposal gives its item, with its details and the open items
    that block it (#1758): the open questions go to a person first, then the split, then the
    open dependencies, then a suspected block, and last a proposal with no checkable criterion."""
    if is_ready:
        return NextStep.READY, (), ()
    if open_questions:
        return NextStep.PERSON, tuple(open_questions), ()
    if not proposal.fits_one_pr:
        return NextStep.SPLIT, tuple(proposal.split_offs), ()
    blockers = tuple(dep for dep in proposal.dependencies if _is_open(store, dep))
    if blockers:
        return NextStep.BLOCKED, tuple(f"#{dep}" for dep in blockers), blockers
    block = _suspected_block(proposal)
    return NextStep.PERSON, (block or MESSAGES.roadmap.refine_incomplete,), ()


def step_comment(
    item: Item,
    step: NextStep,
    details: Sequence[str],
    sha: str,
    block_paths: Sequence[str] = (),
) -> str:
    """The one comment that tells a person the item's next step, carrying refine's marker: the
    Ready notice, or the questions, the split or the blockers, with the Status change from Ready
    first (#1515, #1758), and last the files whose change ends the wait (#2005)."""
    texts = MESSAGES.roadmap
    short = sha[:12]
    marker = CONST_ROADMAP_REFINE_COMMENT_MARKER
    if step is NextStep.READY:
        return texts.refine_ready_comment.format(marker=marker, sha=short)
    numbered = step is NextStep.SPLIT
    listed = "\n".join(
        f"{index}. {detail}" if numbered else f"- {detail}"
        for index, detail in enumerate(details, start=1)
    )
    template = texts.refine_step_comments[step.value]
    comment = texts.refine_step_comment.format(
        marker=marker,
        status=texts.refine_back_to_new.format(sha=short)
        if item.status == CONST_ROADMAP_STATUS_READY
        else "",
        step=template.format(sha=short, count=len(details) or 2),
        details=listed,
    )
    if not block_paths:
        return comment
    paths = ", ".join(f"`{path}`" for path in block_paths)
    return f"{comment}\n\n{texts.refine_block_paths.format(paths=paths)}"


# ── Rendering & Sanitization ──────────────────────────────────────────────────

_IMAGE_RE = re.compile(r"!\[.*?\](?:\(.*?\)|\[.*?\])")
_HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
# The `<` that opens an HTML comment, declaration, CDATA section or processing instruction:
# GitHub hides the text after an unclosed one, and `<!--` can forge a marker or a record block.
_RAW_HTML_OPENER_RE = re.compile(r"<(?=[!?])")
# The URL holds no backtick or space, so the code span that replaces the link closes on its own
# backticks.
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)`]+)\)")
# The text that GitHub links, mentions or cross-references by itself, the leftmost first: a URL
# with a scheme that its autolinks take, in any case; a `www.` link, wherever it starts, as in
# a table cell or after `>`; a handle; and an `owner/repo#N` reference, also in emphasis or
# after a slash, `.` or a handle, with the letters, digits, `.`, `-`, `/`, `#` and `:` after it,
# which can hold a second reference or a URL. A URL and a `www.` link end before a backtick, a
# `|`, a bracket, a parenthesis or a backslash, so neither runs into a code span or the next
# table cell, nor takes in what opens a link or escapes a backtick. An owner holds letters, digits
# and `-`, as an account name does, and starts after none of them, and no quantifier gives back
# what it took, so the search takes time in proportion to the text.
_LIVE_TEXT_RE = re.compile(
    r"(?:https?|ftp)://[^\s()\[\]`|\\]++"
    r"|www\.[^\s()\[\]`|\\]++"
    r"|@[a-zA-Z0-9_\-]++"
    r"|(?<![a-zA-Z0-9\-])[a-zA-Z0-9\-]++/[\w.\-]++#\d[a-zA-Z0-9.\-/#:]*+",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION: Final[str] = ".,;:!?"
_BACKTICK_RUN_RE = re.compile(r"`+")
# A backtick before the next space, which an autolink at that place would take in.
_BACKTICK_BEFORE_SPACE_RE = re.compile(r"\S*`")
# GitHub's Markdown is CommonMark, with tables, which split a row into cells before code spans.
_GITHUB_MARKDOWN: Final = MarkdownIt("commonmark").enable("table")
# The block tokens that GitHub shows as code, in which it links, mentions and references nothing.
_CODE_BLOCKS: Final = frozenset({"code_block", "fence"})


@dataclass(frozen=True)
class _Code:
    """What a text shows as code: the text of its code spans and the text of its code blocks,
    with the info strings of its fenced code blocks; and whether it shows a backtick as text."""

    spans: str
    blocks: str
    stray_backtick: bool


def _shown_code(text: str) -> _Code:
    """The code that `text` shows, as markdown-it parses it."""
    spans: list[str] = []
    blocks: list[str] = []
    stray = False
    for block in _GITHUB_MARKDOWN.parse(text):
        if block.type in _CODE_BLOCKS:
            blocks += (block.content, block.info)
        for token in block.children or ():
            if token.type == "code_inline":
                spans.append(token.content)
            stray = stray or (token.type == "text" and "`" in token.content)
    return _Code("\n".join(spans), "\n".join(blocks), stray)


def _replace_outside_code(
    text: str,
    pattern: re.Pattern[str],
    group: int,
    replace: Callable[[re.Match[str]], str],
    *,
    spans_are_code: bool,
) -> str:
    """`text` with `replace` applied to each match of `pattern` whose `group` starts outside
    code; a match in a code block, and in a code span when `spans_are_code`, stays as it is
    (#2525).

    A character that `text` does not hold, from U+E000 on, marks the start of each match, and the
    marks that the Markdown parser then shows as code give the matches in code. Such a character
    is no space, backslash, backtick or block mark, so the marks change no code. A space goes
    between a replacement and a backtick next to it, or a backslash before it, so that a backtick
    run of the replacement joins no other run and is not escaped.
    """
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    held = set(text)
    absent = (chr(code) for code in itertools.count(0xE000) if chr(code) not in held)
    marks = list(itertools.islice(absent, len(matches)))
    pieces: list[str] = []
    end = 0
    for mark, match in zip(marks, matches, strict=True):
        pieces += (text[end : match.start(group)], mark)
        end = match.start(group)
    code = _shown_code("".join(pieces) + text[end:])
    in_code = set(code.blocks + code.spans if spans_are_code else code.blocks)
    out: list[str] = []
    end = 0
    for mark, match in zip(marks, matches, strict=True):
        replacement = match[0] if mark in in_code else replace(match)
        if replacement != match[0]:
            out += (text[end : match.start()], replacement)
            end = match.end()
    out.append(text[end:])
    return _spaced(out)


def _spaced(pieces: Sequence[str]) -> str:
    """`pieces` joined, with a space between a backtick or a backslash and a backtick after it."""
    joined: list[str] = []
    last = ""
    for piece in filter(None, pieces):
        if last in ("`", "\\") and piece.startswith("`"):
            joined.append(" ")
        joined.append(piece)
        last = piece[-1]
    return "".join(joined)


def _neutralized(match: re.Match[str], allowed_urls: set[str], fence: Callable[[], str]) -> str:
    """The link, handle or reference that `match` holds, in a code span between two of the next
    `fence`, with its trailing punctuation kept outside.

    A link that `allowed_urls` holds stays a link, unless a backtick comes before the next
    space: GitHub's autolink runs to that space and would take the backtick that opens a code
    span.
    """
    raw = match[0]
    link = raw.rstrip(_TRAILING_PUNCTUATION)
    if link in allowed_urls and not _BACKTICK_BEFORE_SPACE_RE.match(match.string, match.end()):
        return raw
    ticks = fence()
    return f"{ticks}{link}{ticks}{raw[len(link) :]}"


def sanitize_text(text: str, allowed_urls: set[str]) -> str:
    """Strips images and HTML tags, turns the `<` of a comment opener into an entity, and wraps
    handles, unallowed URLs and `www.` links, and cross-repository references in code spans.

    The opener is neutralized after the tags are stripped, so a stripped tag cannot build one
    again (#2478), and also in code, since the record block and the markers are found in the raw
    text. A link, handle or reference in code stays as it is. An added code span takes one
    backtick more than the longest run in the text, so it closes on its own backticks and on no
    backtick of the model's (#2525).

    A backtick that the text shows as text makes GitHub's parser, cmark, take a later code span
    of a length it has already closed as text, and makes markdown-it miss a code span after an
    unclosed `[`. In such a text each added code span takes a length of its own, and a link,
    handle or reference in a code span is wrapped too (#2525).
    """
    # 1. Remove end markers inside text
    t = text.replace(CONST_ROADMAP_REFINE_END_MARKER, "[end-marker]")
    # 2. Remove images
    t = _IMAGE_RE.sub("", t)
    # 3. Remove HTML tags
    t = _HTML_TAG_RE.sub("", t)
    # 4. Neutralize comment, declaration and processing instruction openers
    t = _RAW_HTML_OPENER_RE.sub("&lt;", t)
    shortest = max(map(len, _BACKTICK_RUN_RE.findall(t)), default=0) + 1
    stray = "`" in t and _shown_code(t).stray_backtick
    lengths = itertools.count(shortest) if stray else itertools.repeat(shortest)

    def _fence() -> str:
        return "`" * next(lengths)

    # 5. Process markdown links outside code
    def _link_sub(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2)
        if url in allowed_urls:
            return f"[{label}]({url})"
        ticks = _fence()
        return f"{label} ({ticks}{url}{ticks})"

    t = _replace_outside_code(t, _MARKDOWN_LINK_RE, 2, _link_sub, spans_are_code=not stray)

    # 6. Wrap handles, unallowed URLs and `www.` links, and references outside code
    return _replace_outside_code(
        t,
        _LIVE_TEXT_RE,
        0,
        lambda match: _neutralized(match, allowed_urls, _fence),
        spans_are_code=not stray,
    )


def _option_lines(qa: QuestionAnswer) -> list[str]:
    """The options a decision compared, the chosen one and each rejected one with its reason."""
    return [
        f"  - {'Chosen' if option.chosen else 'Rejected'}: "
        f"{option.option.strip().rstrip('.')}. {option.reason.strip()}"
        for option in qa.options
    ]


def _requirement_block(criterion: AcceptanceCriterion) -> list[str]:
    """A criterion as an OpenSpec requirement block with its one scenario (#1849)."""
    return [
        "",
        f"### Requirement: {criterion.name.strip()}",
        criterion.requirement.strip(),
        "",
        f"#### Scenario: {criterion.scenario.strip()}",
        f"- **WHEN** {criterion.when.strip()}",
        f"- **THEN** {criterion.then.strip()}",
    ]


def render_proposal_section(
    proposal: RefinementProposal,
    open_questions: list[str],
    sha: str,
    allowed_urls: set[str],
) -> str:
    """Builds the sanitized plain text markdown section between markers.

    The markers and the `checked-at` comment go around the text after it is sanitized, so
    `sanitize_text` neutralises an end marker or a comment opener in the model's text but never
    the section's own (#1470, #2478).
    """
    lines: list[str] = [
        "## Proposed design",
        "",
        "### Problem statement",
        proposal.problem_statement.strip(),
        "",
        "### Acceptance criteria",
    ]
    for criterion in proposal.acceptance_criteria:
        lines.extend(_requirement_block(criterion))

    lines.append("")
    lines.append("### Existing Tool Considered")
    lines.append(proposal.existing_tool.strip())

    lines.append("")
    lines.append("### Key questions")
    if proposal.key_questions:
        for qa in proposal.key_questions:
            src_str = f" [sources: {', '.join(qa.sources)}]" if qa.sources else ""
            lines.append(f"- **{qa.question.strip()}**: {qa.answer.strip()}{src_str}")
            lines.extend(_option_lines(qa))
    else:
        lines.append("None.")

    if open_questions:
        lines.append("")
        lines.append("### Open questions")
        for oq in open_questions:
            lines.append(f"- {oq.strip()}")

    lines.append("")
    lines.append("### Fit")
    if proposal.fits_one_pr:
        lines.append("Fits in one pull request.")
    else:
        lines.append(f"Needs splitting into {len(proposal.split_offs) or 2} items:")
        for idx, so in enumerate(proposal.split_offs, start=1):
            lines.append(f"{idx}. {so.strip()}")

    lines.append("")
    lines.append("### Suspected block")
    lines.append(proposal.suspected_block.strip() if proposal.suspected_block else "None.")

    lines.append("")
    lines.append("### Dependencies")
    if proposal.dependencies:
        lines.append(", ".join(f"#{d}" for d in proposal.dependencies))
    else:
        lines.append("None.")

    section = sanitize_text("\n".join(lines), allowed_urls)
    return (
        f"{CONST_ROADMAP_REFINE_START_MARKER}\n<!-- checked-at: sha={sha} -->\n{section}\n"
        f"{CONST_ROADMAP_REFINE_END_MARKER}"
    )


# ── Selection ─────────────────────────────────────────────────────────────────

_PRIORITY_ORDER: Final[dict[str | None, int]] = {
    CONST_ROADMAP_CRITICAL_PRIORITY: 0,
    CONST_ROADMAP_P0_PRIORITY: 1,
    CONST_ROADMAP_P1_PRIORITY: 2,
    CONST_ROADMAP_P2_PRIORITY: 3,
    CONST_ROADMAP_P3_PRIORITY: 4,
}


# The backlog's items at this rank or higher (P0 and P1) also give their unrefined Ready items,
# as each open milestone does.
_BACKLOG_FIRST_RANK: Final[int] = _PRIORITY_ORDER[CONST_ROADMAP_P1_PRIORITY]


def _priority_rank(priority: str | None) -> int:
    return _PRIORITY_ORDER.get(priority, 5)


def _select_single_candidate(
    store: RoadmapStore, item_number: int
) -> tuple[list[Item], list[WaitingItem]]:
    """The item `--item` names: refined whenever it is open, New or Ready, since a person asked
    for it, however little changed since its last round (#1758)."""
    item = store.item(item_number)
    if item is None:
        return [], []
    texts = MESSAGES.roadmap
    if item.state is GitHubState.CLOSED:
        return [], [WaitingItem(item, NextStep.NONE, (texts.refine_held_closed,))]
    if item.status in CONST_ROADMAP_REFINE_HELD_STATUSES:
        held = texts.refine_held_status.format(status=item.status)
        return [], [WaitingItem(item, NextStep.NONE, (held,))]
    return [item], []


def _recorded_step(item: Item) -> NextStep | None:
    """The next step the item's last refine round recorded, or None when it recorded none."""
    recorded = item.job_record.get(RefineRecordKey.NEXT_STEP)
    try:
        return NextStep(recorded) if recorded else None
    except ValueError:
        return None


def _recorded_blockers(item: Item) -> list[int]:
    """The open items the item's last refine round found blocking it."""
    recorded = item.job_record.get(RefineRecordKey.BLOCKED_BY) or ""
    return [int(part) for part in recorded.split(",") if part.strip().isdecimal()]


def _recorded_block_paths(item: Item) -> list[str]:
    """The paths whose code the item's last refine round found causing its block (#2005)."""
    recorded = item.job_record.get(RefineRecordKey.BLOCK_PATHS) or ""
    return [path for path in recorded.split(",") if path.strip()]


def replies_after_marker(
    comments: Sequence[IssueComment], marker: str
) -> list[IssueComment] | None:
    """The comments after the last comment that holds `marker`, oldest first, or None when no
    comment holds it. A job marks its own comments, so what follows is a person's reply."""
    marked = [index for index, comment in enumerate(comments) if marker in comment.body]
    return list(comments[marked[-1] + 1 :]) if marked else None


def replies_since_refine(comments: Sequence[IssueComment]) -> list[IssueComment] | None:
    """The comments after refine's last comment, oldest first, or None when refine left none. A
    comment of another roadmap job (#2650) is no reply of a person, so it is left out."""
    replies = replies_after_marker(comments, CONST_ROADMAP_REFINE_COMMENT_MARKER)
    return None if replies is None else _without_other_jobs_comments(replies)


def _comments_without(
    comments: Sequence[IssueComment], markers: Sequence[str]
) -> list[IssueComment]:
    """The comments that hold none of `markers`, oldest first."""
    return [c for c in comments if not any(marker in c.body for marker in markers)]


def _without_other_jobs_comments(comments: Sequence[IssueComment]) -> list[IssueComment]:
    """The comments that no roadmap job but refine wrote: those of persons and of refine."""
    others = [
        m for m in CONST_ROADMAP_JOB_COMMENT_MARKERS if m != CONST_ROADMAP_REFINE_COMMENT_MARKER
    ]
    return _comments_without(comments, others)


def _cited_code_changed(store: RoadmapStore, item: Item, since: datetime) -> bool:
    """Whether a commit on the default branch changed a path the item's block cites at or after
    `since`, the time of refine's last comment on it (#2005)."""
    for path in _recorded_block_paths(item):
        changed = store.path_changed_at(path)
        if changed is not None and changed >= since:
            return True
    return False


def _still_waiting(
    store: RoadmapStore, item: Item, comments_on: Callable[[int], list[IssueComment]]
) -> WaitingItem | None:
    """The next step an item nothing changed since its last round still waits on, or None when
    the wait is over and refine looks at it again (#1758): the round recorded no step, a blocker
    closed, a comment followed refine's last one, or a commit on the default branch changed a
    path the block cites after that comment (#2005). Only a body edit ends an `EDIT` wait.
    `comments_on` reads the item's comments."""
    step = _recorded_step(item)
    details: tuple[str, ...] = ()
    match step:
        case None:
            return None
        case NextStep.EDIT:
            return WaitingItem(item, step)
        case NextStep.BLOCKED:
            blockers = [number for number in _recorded_blockers(item) if _is_open(store, number)]
            if not blockers:
                return None
            details = tuple(f"#{number}" for number in blockers)
        case NextStep.READY:
            # A New item refine set Ready: a person set it back, and refine waits for the reason.
            step, details = NextStep.PERSON, (MESSAGES.roadmap.refine_set_back_by_person,)
    comments = comments_on(item.number)
    replies = replies_since_refine(comments)
    if replies is None or replies:
        return None
    # No reply: the last comment that is not another job's is refine's own.
    last = _without_other_jobs_comments(comments)[-1]
    if _cited_code_changed(store, item, last.created_at):
        return None
    return WaitingItem(item, step, details)


def _outside_author(item: Item) -> WaitingItem | None:
    """The wait of an item that an account without write access opened, as GitHub's
    `author_association` gives it, or None for the owner's, a member's or a collaborator's item.

    Build agents take Ready items as work, so a round never refines text from such an account:
    the item waits on a person, who refines it with `--item` (#2478). An item with no
    association, which GitHub never gives, is treated the same way.
    """
    if item.author_association in CONST_ROADMAP_TRUSTED_AUTHORS:
        return None
    texts = MESSAGES.roadmap
    detail = texts.refine_outside_author.format(
        association=item.author_association or texts.refine_author_unknown, number=item.number
    )
    return WaitingItem(item, NextStep.PERSON, (detail,))


def _comment_cap(item: Item, comments: Sequence[IssueComment]) -> WaitingItem | None:
    """The wait of an item on which refine wrote `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM`
    comments in the last `CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS` hours, or None.

    The item waits on a person, so another bot that answers each refine comment gets no more
    of them (#2475). The cap stops the comment that would answer the item's newest comment; it
    is a new stop, which apply records, logs and counts, unless the item's record holds that
    comment's time from an earlier round.
    """
    hours = CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS
    since = datetime.now(UTC) - timedelta(hours=hours)
    count = sum(
        1
        for comment in comments
        if CONST_ROADMAP_REFINE_COMMENT_MARKER in comment.body and comment.created_at > since
    )
    if count < CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM:
        return None
    newest = _without_other_jobs_comments(comments)[-1].created_at.isoformat()
    stopped_before = item.job_record.get(RefineRecordKey.CAPPED_AFTER) == newest
    detail = MESSAGES.roadmap.refine_comment_cap.format(
        count=count, hours=hours, number=item.number
    )
    return WaitingItem(
        item, NextStep.PERSON, (detail,), cap_stop=None if stopped_before else newest
    )


@dataclass
class _Selection:
    """The items one selection takes, and those it leaves with their next step. It reads the
    comments on each item once."""

    store: RoadmapStore
    selected: list[Item] = field(default_factory=list)
    waiting: list[WaitingItem] = field(default_factory=list)
    comments: dict[int, list[IssueComment]] = field(default_factory=dict)

    def comments_on(self, number: int) -> list[IssueComment]:
        """The comments on issue `number`, read once for the selection."""
        if number not in self.comments:
            self.comments[number] = self.store.comments_on(number)
        return self.comments[number]

    def consider(self, item: Item) -> None:
        """Take `item` unless an account without write access opened it (#2478), its wait is
        not over, a person edited its section (#1515), or refine wrote its cap of comments on
        it in the last 24 hours (#2475)."""
        outside = _outside_author(item)
        if outside is not None:
            self.waiting.append(outside)
            return
        if _is_unchanged(item, item.body) and not _needs_second_look(item):
            waits = _still_waiting(self.store, item, self.comments_on)
            if waits is not None:
                self.waiting.append(waits)
                return
        edit_problem = check_person_edits(item, item.body)
        if edit_problem:
            self.waiting.append(WaitingItem(item, NextStep.EDIT, (edit_problem,)))
            return
        capped = _comment_cap(item, self.comments_on(item.number))
        if capped is not None:
            self.waiting.append(capped)
            return
        self.selected.append(item)


def _is_unrefined_ready(item: Item) -> bool:
    """Whether `item` is Ready with no record of a refine round: project sync or a person set
    it Ready without a design (#1515). The record, not the body, tells: a section refine wrote
    before #1470 ends in `[end-marker]`, so its body reads as holding none."""
    return (
        item.status == CONST_ROADMAP_STATUS_READY
        and item.job_record.get(RefineRecordKey.SECTION_HASH) is None
    )


def _refinable(items: Sequence[Item], *, unrefined_ready: bool) -> list[Item]:
    """`items`' open New items, their unrefined Ready ones when `unrefined_ready`, and the Ready
    ones that hold a covering tool no round asked about (#2652), highest priority first."""
    picked = [
        it
        for it in items
        if it.state is GitHubState.OPEN
        and (
            it.status == CONST_ROADMAP_STATUS_NEW
            or (unrefined_ready and _is_unrefined_ready(it))
            or (it.status == CONST_ROADMAP_STATUS_READY and _needs_second_look(it))
        )
    ]
    return sorted(picked, key=lambda it: _priority_rank(it.priority))


def select_candidates(
    store: RoadmapStore,
    *,
    item_number: int | None = None,
    limit: int = DEFAULT_ROADMAP_REFINE_LIMIT,
) -> tuple[list[Item], list[WaitingItem]]:
    """Selects up to `limit` items to refine, nearest place first as the module's docstring
    orders them, returning (selected, waiting): each item it leaves out waits on its next step.
    The number of Ready items does not stop it (#2004)."""
    if item_number is not None:
        return _select_single_candidate(store, item_number)

    open_milestones = [m for m in store.milestones() if m.state is GitHubState.OPEN]
    milestone_items = [store.items(milestone=m.number) for m in open_milestones]
    backlog_items = store.backlog()

    ordered = [
        # The open milestones' items, nearest first, then the backlog's P0 and P1 items
        *(it for items in milestone_items for it in _refinable(items, unrefined_ready=True)),
        *(
            it
            for it in _refinable(backlog_items, unrefined_ready=True)
            if _priority_rank(it.priority) <= _BACKLOG_FIRST_RANK
        ),
        # The backlog's other New items
        *(
            it
            for it in _refinable(backlog_items, unrefined_ready=False)
            if _priority_rank(it.priority) > _BACKLOG_FIRST_RANK
        ),
    ]

    selection = _Selection(store)
    for it in ordered:
        if len(selection.selected) >= limit:
            break
        selection.consider(it)
    return selection.selected, selection.waiting


# ── Refine Engine ─────────────────────────────────────────────────────────────


def check_person_edits(item: Item, current_body: str) -> str | None:
    """Verifies that no manual edit was made to the refine section or body without record."""
    _, inside = extract_section_and_outside(current_body)
    stored_section_hash = item.job_record.get(RefineRecordKey.SECTION_HASH)
    if inside is not None:
        if stored_section_hash is None:
            return "the body holds a section refine has no record of"
        if hash_text(inside) != stored_section_hash:
            return "the section's hash differs from the one refine last recorded"
    return None


def refine_one_item(
    store: RoadmapStore,
    item: Item,
    *,
    repo: str,
    source: Path,
    sha: str,
    client: LLMClient | Any,
    web: WebSearch | None = None,
    investigator: Any = None,
    max_context_tokens: int = 8192,
    intake_model: IntakeModel | None = None,
) -> RefinedItem:
    """Refines one item through context collection, proposal, validation and, when a question
    stays open, the investigation with `web`'s search and the `investigator` model (#2398). A
    Ready proposal's deferred parts get an intake plan each, with `intake_model` (#2423)."""
    web = web or WebSearch()
    current_body = store.read_issue_body(item.number)

    # Person edits check
    edit_problem = check_person_edits(item, current_body)
    if edit_problem:
        return RefinedItem(
            item=item,
            proposal=RefinementProposal(problem_statement="", existing_tool=""),
            open_questions=[],
            is_ready=False,
            needs_split=False,
            reason_comment=None,
            new_body=current_body,
            body_hash="",
            section_hash="",
            next_step=NextStep.EDIT,
            step_details=(edit_problem,),
            skip_reason=edit_problem,
        )

    # Step 1: Context minimization
    ctx = collect_context(source, sha, current_body, max_tokens=max_context_tokens)

    # Step 2: Proposal generation
    comments = store.comments_on(item.number)
    check = recorded_check(item, current_body)
    covers = covers_question(check, comments)
    request: dict[str, Any] = {
        "number": item.number,
        "title": item.title,
        "body": current_body,
        "replies": _replies_for_model(comments),
        "alternatives": _alternatives_request(check, comments, covers),
        "context": ctx,
        "body_questions": [
            {"number": number, "question": asked}
            for number, asked in enumerate(_asked_questions(current_body, covers), start=1)
        ],
        "deferred_issues": [
            {"number": number, "title": title} for number, title in _recorded_deferrals(store, item)
        ],
    }
    raw_proposal: RefinementProposal = client.chat_structured(
        _prompt("roadmap_refine_proposal.md"),
        json.dumps(request, ensure_ascii=False, indent=1),
        RefinementProposal,
    )

    # Step 3: Validation, and the investigation of what stays open (#2398)
    allowed_urls: set[str] = set()
    proposal, open_questions = validate_proposal(
        raw_proposal, current_body, allowed_urls, source, sha, store, covers
    )
    if needs_investigation(proposal, open_questions):
        tools = InvestigationTools(source=source, sha=sha, firecrawl_key=web.key)
        revised = _investigate(
            item, repo, request, raw_proposal, proposal, open_questions, tools, investigator
        )
        if revised is not None:
            allowed_urls = tools.allowed_urls
            proposal, open_questions = validate_proposal(
                revised, current_body, allowed_urls, source, sha, store, covers
            )
    is_ready = check_ready(proposal, open_questions)
    needs_split = not proposal.fits_one_pr
    step, model_details, blocked_by = next_step_of(
        store, proposal, open_questions, is_ready=is_ready
    )
    deferred, refused = (
        _plan_deferrals(store, item, proposal, repo=repo, model=intake_model, urls=allowed_urls)
        if is_ready
        else ((), None)
    )
    if refused is not None:
        is_ready, step, model_details = False, NextStep.PERSON, (refused,)
    # The details hold the model's text, which goes into a comment: sanitized like the section,
    # on one line each (#1758). Each goes on its line first, so its code is the code that the
    # comment shows (#2525).
    details = tuple(sanitize_text(" ".join(d.split()), allowed_urls) for d in model_details)
    # The paths are the cause of a block: an open dependency or a suspected block (#2005).
    blocked = bool(blocked_by) or _suspected_block(proposal) is not None
    block_paths = tuple(proposal.block_paths) if blocked else ()

    # Step 4: Render section & Check size
    rendered_section = render_proposal_section(proposal, open_questions, sha, allowed_urls)
    outside, _ = extract_section_and_outside(current_body)
    new_body = outside.rstrip() + "\n\n" + rendered_section

    if len(new_body) > CONST_ROADMAP_REFINE_MAX_BODY_CHARS:
        seen_body_hash, seen_section_hash = _body_hashes(current_body)
        too_big = f"new body would exceed {CONST_ROADMAP_REFINE_MAX_BODY_CHARS} characters"
        return RefinedItem(
            item=item,
            proposal=proposal,
            open_questions=open_questions,
            is_ready=False,
            needs_split=needs_split,
            reason_comment=None,
            new_body=current_body,
            body_hash=seen_body_hash,
            section_hash=seen_section_hash,
            next_step=NextStep.EDIT,
            step_details=(too_big,),
            skip_reason=too_big,
            record_only=True,
        )

    # One comment gives the next step; a Ready item refine finds not ready goes back to New (#1515)
    comment = step_comment(item, step, details, sha, block_paths)

    s_hash = hash_text(
        rendered_section[
            len(CONST_ROADMAP_REFINE_START_MARKER) : -len(CONST_ROADMAP_REFINE_END_MARKER)
        ]
    )

    return RefinedItem(
        item=item,
        proposal=proposal,
        open_questions=open_questions,
        is_ready=is_ready,
        needs_split=needs_split,
        reason_comment=comment,
        new_body=new_body,
        body_hash=_body_hashes(current_body)[0],
        section_hash=s_hash,
        next_step=step,
        step_details=details,
        blocked_by=blocked_by,
        block_paths=block_paths,
        alternatives_asked=check.tool if check and check.verdict is Verdict.COVERS else None,
        read_hash=hash_text(outside),
        deferred=deferred,
    )


def _recorded_numbers(item: Item) -> list[int]:
    """The issues that refine filed for the deferred parts of `item` in earlier rounds."""
    recorded = item.job_record.get(RefineRecordKey.DEFERRED) or ""
    return [int(number) for number in recorded.split(",") if number.strip().isdigit()]


def _recorded_deferrals(store: RoadmapStore, item: Item) -> list[tuple[int, str]]:
    """The number and title of each issue that refine filed for a deferred part of `item`."""
    found = ((number, store.item(number)) for number in _recorded_numbers(item))
    return [(number, filed.title) for number, filed in found if filed is not None]


def _joined(text: str) -> str:
    return " ".join(text.split())


def _deferral_candidate(item: Item, part: DeferredPart, urls: set[str]) -> NewCandidate:
    """The new issue of `part`: its text sanitized like the section, and a body that starts with
    the link to `item`. It has no `source`, so intake links no sub-issue and `item` stays a plain
    item that the stage job takes (#2423)."""
    title = sanitize_text(_joined(part.title), urls)
    body = sanitize_text(part.body.strip(), urls)
    split_from = MESSAGES.roadmap.refine_deferred_split_from.format(number=item.number)
    return NewCandidate(title=title, body=f"{split_from}\n\n{body}")


def _plan_deferrals(
    store: RoadmapStore,
    item: Item,
    proposal: RefinementProposal,
    *,
    repo: str,
    model: IntakeModel | None,
    urls: set[str],
) -> tuple[tuple[PlannedDeferral, ...], str | None]:
    """The intake plan of each deferred part of a Ready proposal that no earlier round filed, or
    the detail that keeps the item waiting on a person: a part that intake cannot place, or
    whose text looks like a secret (#2423)."""
    recorded = {_joined(title) for _, title in _recorded_deferrals(store, item)}
    parts = [part for part in proposal.deferred if _joined(part.title) not in recorded]
    if not parts:
        return (), None
    intake_model = model or build_intake_model()
    planned: list[PlannedDeferral] = []
    for part in parts:
        candidate = _deferral_candidate(item, part, urls)
        refused = MESSAGES.roadmap.refine_deferred_refused.format(title=candidate.title)
        try:
            plan = plan_intake(store, repo=repo, model=intake_model, new=candidate)
        except SecurityError:
            return (), refused
        if any(decision.outcome is not Outcome.PLACE for decision in plan.decisions):
            return (), refused
        planned.append(PlannedDeferral(DeferredPart(title=candidate.title, body=part.body), plan))
    return tuple(planned), None


def _prompt(task: str) -> str:
    """The system prompt of a refine step: the step's task, then the keys of the reply."""
    return f"{load_task_prompt(task)}\n\n{load_task_prompt('roadmap_refine_reply.md')}"


def _investigate(
    item: Item,
    repo: str,
    request: dict[str, Any],
    first: RefinementProposal,
    proposal: RefinementProposal,
    open_questions: Sequence[str],
    tools: InvestigationTools,
    investigator: Any,
) -> RefinementProposal | None:
    """The proposal the investigation returns for `item`, or None when it stops with none.

    It gets the proposal request without the context, which its tools read, with the first
    proposal and the questions the validated `proposal` leaves open: the open questions and
    each decision with no verified source (#2398). The warning for a stop names `repo` and the
    reason, with no text of the model (#2562).
    """
    unsourced = [
        f"{qa.question} {_DECISION_WITHOUT_SOURCE}"
        for qa in proposal.key_questions
        if qa.kind == "decision" and qa.answer.endswith(_PROPOSED)
    ]
    document = {key: value for key, value in request.items() if key != "context"} | {
        "proposal": first.model_dump(mode="json"),
        "open_questions": [*open_questions, *unsourced],
        "web_search": tools.firecrawl_key is not None,
    }
    revised = investigate(
        investigator or get_task_model("analysis"),
        _prompt("roadmap_refine_investigation.md"),
        json.dumps(document, ensure_ascii=False, indent=1),
        tools,
        RefinementProposal,
    )
    if isinstance(revised, InvestigationStopped):
        logger.warning(
            MESSAGES.roadmap.refine_investigation_stopped.format(
                number=item.number,
                repo=repo,
                reason=MESSAGES.roadmap.run_stop_reason.format(
                    error=revised.reason, message=revised.message
                ),
            )
        )
        return None
    return revised


def _replies_for_model(comments: Sequence[IssueComment]) -> list[str]:
    """The replies the model reads: the comments after refine's last comment, or every comment
    when refine left none, the newest `CONST_ROADMAP_REFINE_MAX_REPLIES`, each cut to its token
    cap (#1758)."""
    replies = replies_since_refine(comments)
    persons = _without_other_jobs_comments(comments) if replies is None else replies
    kept = persons[-CONST_ROADMAP_REFINE_MAX_REPLIES:]
    return [
        truncate_to_token_limit(reply.body, max_tokens=CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS)
        for reply in kept
    ]


# ── Top-Level Entry Points ────────────────────────────────────────────────────


def plan_refine(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path | str = ".",
    ref: str | None = None,
    item_number: int | None = None,
    limit: int = DEFAULT_ROADMAP_REFINE_LIMIT,
    model: Any = None,
    investigator: Any = None,
    intake_model: IntakeModel | None = None,
) -> RefinePlan:
    """Plans refinement for eligible candidates without writing anything to GitHub.

    `model` is the proposal step's client and `investigator` the investigation's pydantic-ai
    model; each defaults to the `analysis` task's (#2398). `intake_model` plans the new issues
    of deferred parts, and is built only when a part exists (#2423)."""
    source_path = Path(source)
    sha = inspect_checkout(source_path, repo)

    candidates, waiting = select_candidates(store, item_number=item_number, limit=limit)
    cap_stops = any(w.cap_stop is not None for w in waiting)
    if not candidates:
        return RefinePlan(repo=repo, sha=sha, waiting_items=waiting, has_writes=cap_stops)

    settings = load_settings()
    ai_config = settings.ai
    client = model or get_llm_client(task="analysis", settings=settings)
    max_tokens = ai_config.for_task("analysis").context_window or 8192
    web = web_search_of(store)

    refined: list[RefinedItem] = []
    failed: list[RefineFailure] = []
    for cand in candidates:
        try:
            res = refine_one_item(
                store,
                cand,
                repo=repo,
                source=source_path,
                sha=sha,
                client=client,
                web=web,
                investigator=investigator,
                max_context_tokens=max_tokens,
                intake_model=intake_model,
            )
        except AICredentialsError:
            raise
        except AIClientError as exc:
            failed.append(_failed_item(cand, repo, exc))
            continue
        refined.append(res)

    has_writes = (
        cap_stops
        or any(r.skip_reason is None or r.record_only for r in refined)
        or any(failure.item_caused for failure in failed)
    )
    return RefinePlan(
        repo=repo,
        sha=sha,
        refined_items=refined,
        waiting_items=waiting,
        has_writes=has_writes,
        failed_items=failed,
        web_search_off=web.off_reason,
    )


def dry_run_refine(
    repo: str,
    *,
    ref: str | None = None,
    item: int | None = None,
    limit: int | None = None,
) -> RefinePlan:
    """The plan a dry run returns, having made no external request."""
    from devops_cli.roadmap.request_plan import refine_requests

    reads, writes = refine_requests(repo, ref, item=item, limit=limit)
    return RefinePlan(
        repo=repo,
        sha="",
        dry_run=True,
        requests=reads,
        write_requests=writes,
        has_writes=bool(writes),
    )


def _failed_item(item: Item, repo: str, exc: AIClientError) -> RefineFailure:
    """Record `item` as skipped for its failed model call, logging no model text: the error's
    message can quote the reply. The warning gives `repo`, the error's class and its `reason`: the
    code with the HTTP status or the timeout (#2562)."""
    failure = RefineFailure.of(item, exc)
    logger.warning(
        MESSAGES.roadmap.refine_item_skipped.format(
            number=item.number,
            repo=repo,
            error=failure.error,
            reason=exc.reason,
            violations=failure.violations,
        )
    )
    return failure


def raise_for_failed_items(plan: RefinePlan, readied_count: int = 0) -> None:
    """Fail a run in which the model call failed for any item, once the others are written.
    The error carries `readied_count`, the items the run set Ready before it failed (#2659).

    The error names each skipped item with its error's class and schema violation count. It is
    raised outside the handler that caught the model's error and is not chained to it, so a
    logged traceback holds no reply text.
    """
    if not plan.failed_items:
        return
    items = ", ".join(
        MESSAGES.roadmap.refine_failed_item.format(
            number=failure.item.number, error=failure.error, violations=failure.violations
        )
        for failure in plan.failed_items
    )
    raise RoadmapRefineError(
        MESSAGES.roadmap.refine_failed.format(count=len(plan.failed_items), items=items),
        failed_items=[failure.item.number for failure in plan.failed_items],
        readied_count=readied_count,
    )


def _body_unchanged_since_read(store: RoadmapStore, number: int, body_hash: str) -> bool:
    """Whether issue `number` still holds the text that `body_hash` hashes, the body without
    the alternatives job's block and refine's section, so what refine learned from the body it
    read still holds; a body a person changed since is reported."""
    if _body_hashes(store.read_issue_body(number))[0] == body_hash:
        return True
    logger.warning("Skipping #%d: the body changed between the read and the write.", number)
    return False


def _outside_unchanged_since_read(store: RoadmapStore, number: int, read_hash: str) -> bool:
    """Whether issue `number` still holds the body outside its section that `read_hash` hashes,
    the job's block included: a write of the new body would replace anything the job or a person
    wrote since the read."""
    fresh_outside, _ = extract_section_and_outside(store.read_issue_body(number))
    if hash_text(fresh_outside) == read_hash:
        return True
    logger.warning("Skipping #%d: the body changed between the read and the write.", number)
    return False


def _record_failure(store: RoadmapStore, failure: RefineFailure) -> None:
    """Record a failure the item's own text caused: the first records the body it was about, and
    a second on the same body settles the item as unchanged, like the size guard (#1526)."""
    item = failure.item
    body_hash, section_hash = _body_hashes(item.body)
    if not _body_unchanged_since_read(store, item.number, body_hash):
        return
    if item.job_record.get(RefineRecordKey.FAILED_BODY_HASH) != body_hash:
        store.set_marks(item, {RefineRecordKey.FAILED_BODY_HASH: body_hash})
        return
    store.set_marks(
        item,
        {
            RefineRecordKey.BODY_HASH: body_hash,
            RefineRecordKey.SECTION_HASH: section_hash,
            RefineRecordKey.FAILED_BODY_HASH: None,
            RefineRecordKey.NEXT_STEP: NextStep.EDIT.value,
        },
    )


def _record_unwritten(store: RoadmapStore, plan: RefinePlan) -> None:
    """Record what refine saw of the items it wrote no section to, where the next round would
    only repeat it: an item too big to refine, and an item the model's reply never validated for."""
    for r in plan.refined_items:
        if r.record_only and _body_unchanged_since_read(store, r.item.number, r.body_hash):
            store.set_marks(
                r.item,
                {
                    RefineRecordKey.BODY_HASH: r.body_hash,
                    RefineRecordKey.SECTION_HASH: r.section_hash,
                    RefineRecordKey.NEXT_STEP: r.next_step.value,
                },
            )
    for failure in plan.failed_items:
        if failure.item_caused:
            _record_failure(store, failure)


def _record_cap_stops(store: RoadmapStore, plan: RefinePlan) -> None:
    """Record, log and count each comment that the cap on refine's comments stopped and no
    earlier round stopped. The record holds the time of the item's newest comment, so a later
    round that finds no newer comment counts the item no more (#2475)."""
    for waiting in plan.waiting_items:
        if waiting.cap_stop is None:
            continue
        store.set_marks(waiting.item, {RefineRecordKey.CAPPED_AFTER: waiting.cap_stop})
        logger.warning(
            "Refine left #%d alone and wrote no comment: it reached its limit of %d comments on "
            "the item in %d hours.",
            waiting.item.number,
            CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM,
            CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS,
        )
        emit(ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL, 1)


def _file_deferrals(store: RoadmapStore, refined: RefinedItem) -> tuple[int, ...] | None:
    """File the deferred parts of `refined` through intake, and return the numbers of every part
    of the item, the recorded ones first. When a part is not filed, record the numbers that are,
    log a warning and return None, so the item keeps its body and its Status (#2423)."""
    numbers = _recorded_numbers(refined.item)
    for deferral in refined.deferred:
        applied = apply_intake(store, deferral.plan)
        (decision,) = deferral.plan.decisions
        number = applied.filed[0] if applied.filed else decision.subject.number
        if applied.failed or not applied.placed or number is None:
            if len(numbers) > len(_recorded_numbers(refined.item)):
                store.set_marks(refined.item, {RefineRecordKey.DEFERRED: _numbers_text(numbers)})
            logger.warning(
                MESSAGES.roadmap.refine_deferred_incomplete.format(
                    number=refined.item.number,
                    filed=len(numbers),
                    count=len(_recorded_numbers(refined.item)) + len(refined.deferred),
                )
            )
            return None
        numbers.append(number)
    return tuple(numbers)


def _numbers_text(numbers: Sequence[int]) -> str:
    return ",".join(str(number) for number in numbers)


def _with_deferrals(comment: str | None, numbers: Sequence[int]) -> str | None:
    """The Ready comment with the sentence that names the new issues of the deferred parts."""
    if comment is None or not numbers:
        return comment
    items = ", ".join(f"#{number}" for number in numbers)
    return f"{comment}\n\n{MESSAGES.roadmap.refine_deferred_comment.format(items=items)}"


def apply_refine(store: RoadmapStore, plan: RefinePlan) -> RefineApplied:
    """Applies the planned writes to GitHub: updates issue body, marks, status and comments,
    records the body of an item too big to refine or failing on its own text, and records each
    comment that the cap on refine's comments stopped."""
    refined_count = readied_count = split_count = comments_posted = 0

    for r in plan.refined_items:
        if r.skip_reason is not None:
            continue

        # Race condition check: ensure body did not change between read and write
        if not _outside_unchanged_since_read(store, r.item.number, r.read_hash):
            continue

        # The deferred parts are filed first: an item whose parts are not all filed is not set
        # Ready, and the next round files the rest (#2423)
        deferred = _file_deferrals(store, r) if r.deferred else ()
        if deferred is None:
            continue

        # Write body
        store.write_issue_body(r.item.number, r.new_body)
        refined_count += 1

        # Prepare marks
        marks: JobRecord = {
            RefineRecordKey.BODY_HASH: r.body_hash,
            RefineRecordKey.SECTION_HASH: r.section_hash,
            RefineRecordKey.NEEDS_SPLIT: "true" if r.needs_split else "false",
            RefineRecordKey.FAILED_BODY_HASH: None,
            RefineRecordKey.NEXT_STEP: r.next_step.value,
            RefineRecordKey.BLOCKED_BY: ",".join(str(number) for number in r.blocked_by) or None,
            RefineRecordKey.BLOCK_PATHS: ",".join(r.block_paths) or None,
            RefineRecordKey.ALTERNATIVES_ASKED: r.alternatives_asked,
        }
        if deferred:
            marks[RefineRecordKey.DEFERRED] = _numbers_text(deferred)

        # Status change & marks: a Ready item refine finds not ready goes back to New (#1515)
        if r.is_ready:
            store.set_field(r.item, ItemField.STATUS, CONST_ROADMAP_STATUS_READY, marks=marks)
            readied_count += 1
        elif r.item.status == CONST_ROADMAP_STATUS_READY:
            store.set_field(r.item, ItemField.STATUS, CONST_ROADMAP_STATUS_NEW, marks=marks)
        else:
            store.set_marks(r.item, marks)

        if r.needs_split:
            split_count += 1

        # Comment
        comment = _with_deferrals(r.reason_comment, deferred)
        if comment:
            store.comment(r.item.number, comment)
            comments_posted += 1

    _record_unwritten(store, plan)
    _record_cap_stops(store, plan)
    return RefineApplied(
        refined_count=refined_count,
        readied_count=readied_count,
        split_count=split_count,
        comments_posted=comments_posted,
    )


def _step_lines(plan: RefinePlan, step: NextStep) -> list[str]:
    """The report's lines for the items that wait on `step`: each item, then its details."""
    texts = MESSAGES.roadmap
    entries = [
        (
            texts.refine_item_line if r.skip_reason else texts.refine_refined_line,
            r.item,
            r.step_details,
        )
        for r in plan.refined_items
        if r.next_step is step
    ] + [(texts.refine_item_line, w.item, w.details) for w in plan.waiting_items if w.step is step]
    lines: list[str] = []
    for line, item, details in entries:
        lines.append(line.format(number=item.number, title=item.title))
        lines.extend(texts.refine_detail_line.format(detail=detail) for detail in details)
    return [texts.refine_step_headings[step.value], *lines] if lines else []


def render_refine_plan(plan: RefinePlan) -> str:
    """Formats the refinement plan for CLI stdout report: the items grouped by next step, then
    the items whose model call failed (#1758)."""
    lines: list[str] = [MESSAGES.roadmap.refine_title.format(repo=plan.repo)]
    if plan.web_search_off:
        lines.append(MESSAGES.roadmap.refine_web_search_off.format(reason=plan.web_search_off))
    if not (plan.refined_items or plan.waiting_items or plan.failed_items):
        lines.append(MESSAGES.roadmap.refine_none)
        return "\n".join(lines)

    for step in NextStep:
        lines.extend(_step_lines(plan, step))

    if plan.failed_items:
        lines.append(MESSAGES.roadmap.refine_failed_heading)
        lines.extend(
            MESSAGES.roadmap.refine_failed_line.format(
                number=failure.item.number,
                title=failure.item.title,
                error=failure.error,
                violations=failure.violations,
            )
            for failure in plan.failed_items
        )

    return "\n".join(lines)


__all__ = [
    "AcceptanceCriterion",
    "DeferredPart",
    "DesignOption",
    "NextStep",
    "PlannedDeferral",
    "QuestionAnswer",
    "RefineApplied",
    "RefineFailure",
    "RefinePlan",
    "RefinedItem",
    "RefinementProposal",
    "WaitingItem",
    "WebSearch",
    "apply_refine",
    "body_dependencies",
    "body_questions",
    "check_person_edits",
    "check_ready",
    "collect_context",
    "dry_run_refine",
    "extract_section_and_outside",
    "hash_text",
    "inspect_checkout",
    "needs_investigation",
    "next_step_of",
    "plan_refine",
    "raise_for_failed_items",
    "render_proposal_section",
    "render_refine_plan",
    "replies_after_marker",
    "replies_since_refine",
    "sanitize_text",
    "select_candidates",
    "step_comment",
    "validate_proposal",
    "web_search_of",
]
