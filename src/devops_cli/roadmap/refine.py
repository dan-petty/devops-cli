"""`devops roadmap refine`: item refinement to Ready with proposed design, tasks and acceptance criteria.

Without `--item`, refine picks up to `--limit` (default 3) items, nearest place first (#1515):
each open milestone's New items, in milestone order (due date, then number); the backlog's P0 and
P1 items; the backlog's other New items; each place by priority. The number of Ready items does
not stop a round: the board shows that number to the person who plans, and `--limit` is the only
cap (#2004). Each open milestone and the backlog's P0/P1 items also give their Ready items no
refine round has recorded, which refine confirms Ready or sets back to New. It leaves out items
that are Blocked or started, items whose section a person edited (`check_person_edits`), and
items unchanged since their last round that still wait on their next step, so none of them takes
one of the `--limit` places. Selection judges an item by the body its listing carried, so an item
nothing changed costs no body read and no model call (#1539). `--item` refines the item it names
whenever it is open, New or Ready, since a person asked for it.

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
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel, ConfigDict, Field

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
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_P0_PRIORITY,
    CONST_ROADMAP_P1_PRIORITY,
    CONST_ROADMAP_P2_PRIORITY,
    CONST_ROADMAP_P3_PRIORITY,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_HELD_STATUSES,
    CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS,
    CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
    CONST_ROADMAP_REFINE_MAX_REPLIES,
    CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    CONST_ROADMAP_REFINE_NO_BLOCK_TEXTS,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_REFINE_LIMIT
from devops_cli.config.settings import get_firecrawl_api_key, load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.exceptions.roadmap import RoadmapRefineError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine_investigation import (
    InvestigationStopped,
    InvestigationTools,
    investigate,
)
from devops_cli.roadmap.store import (
    GitHubState,
    IssueComment,
    Item,
    ItemField,
    JobRecord,
    RefineRecordKey,
    RoadmapStore,
)

logger = logging.getLogger(__name__)

# ── Models ────────────────────────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    verification: str


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


class RefinementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_statement: str
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    key_questions: list[QuestionAnswer] = Field(default_factory=list)
    fits_one_pr: bool = True
    split_offs: list[str] = Field(default_factory=list)
    suspected_block: str | None = None
    dependencies: list[int] = Field(default_factory=list)
    block_paths: list[str] = Field(default_factory=list)


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
class RefinedItem:
    """An item's refinement. When `skip_reason` is set none of it is written; with `record_only`
    apply still records the hashes of the body refine saw, so the item reads as unchanged until
    its body changes (#1526). `next_step` is what the item waits on, with `step_details` (the
    questions, the split or the blockers) and the open items `blocked_by` (#1758), and
    `block_paths` the paths whose code causes the block (#2005)."""

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
    skip_reason: str | None = None
    record_only: bool = False


@dataclass(frozen=True)
class WaitingItem:
    """An item refine did not refine in this round, with the next step it waits on (#1758):
    `details` names the open items it waits on, or why refine leaves it alone."""

    item: Item
    step: NextStep
    details: tuple[str, ...] = ()


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


def extract_section_and_outside(body: str) -> tuple[str, str | None]:
    """Returns (body_outside_section, section_inside_markers_or_none)."""
    start_marker = CONST_ROADMAP_REFINE_START_MARKER
    end_marker = CONST_ROADMAP_REFINE_END_MARKER

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
    """The hash of `body` outside its refine section, and the section's, None when it holds none."""
    outside, inside = extract_section_and_outside(body)
    return hash_text(outside), (hash_text(inside) if inside else None)


def _is_unchanged(item: Item, body: str) -> bool:
    """Whether `body` hashes as refine last recorded for `item`, outside the section and in it."""
    recorded = (
        item.job_record.get(RefineRecordKey.BODY_HASH),
        item.job_record.get(RefineRecordKey.SECTION_HASH),
    )
    return _body_hashes(body) == recorded


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
) -> tuple[RefinementProposal, list[str]]:
    """Deterministically validates proposal sources, key questions, decisions and block paths.
    Returns (validated_proposal, open_questions).

    A fact with no verified source and a question only a person decides are open questions, and
    so is each of the body's unanswered key questions whose number no answer names (#2398). The
    key questions and owner decisions are the person's, read from the body outside refine's
    own section, so a refined item's section never asks its own questions again (#1758). Only
    the block paths that the checkout holds are kept (#2005).
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
        asked for number, asked in enumerate(body_questions(body), start=1) if number not in named
    )

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


def check_ready(proposal: RefinementProposal, open_questions: Sequence[str]) -> bool:
    """Deterministic check: problem non-empty, 1+ criterion with verification, no open questions,
    fits one PR, and no suspected block.
    """
    if not proposal.problem_statement.strip():
        return False
    if not proposal.acceptance_criteria:
        return False
    if not all(
        c.description.strip() and c.verification.strip() for c in proposal.acceptance_criteria
    ):
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
_HANDLE_RE = re.compile(r"(?<!`)(@[a-zA-Z0-9_\-]+)(?!`)")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_BARE_URL_RE = re.compile(r"(?<!`)(https?://[^\s\)\]]+)(?!`)")


def sanitize_text(text: str, allowed_urls: set[str]) -> str:
    """Strips images and HTML tags, wraps handles and unallowed URLs in code spans."""
    # 1. Remove end markers inside text
    t = text.replace(CONST_ROADMAP_REFINE_END_MARKER, "[end-marker]")
    # 2. Remove images
    t = _IMAGE_RE.sub("", t)
    # 3. Remove HTML tags
    t = _HTML_TAG_RE.sub("", t)
    # 4. Wrap @handles
    t = _HANDLE_RE.sub(r"`\1`", t)

    # 5. Process markdown links
    def _link_sub(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2)
        if url in allowed_urls:
            return f"[{label}]({url})"
        return f"{label} (`{url}`)"

    t = _MARKDOWN_LINK_RE.sub(_link_sub, t)

    # 6. Wrap bare URLs not in allowed_urls
    def _bare_url_sub(m: re.Match[str]) -> str:
        raw_match = m.group(1)
        stripped = raw_match.rstrip(".,;:!?")
        punct = raw_match[len(stripped) :]
        if stripped in allowed_urls:
            return f"{stripped}{punct}"
        return f"`{stripped}`{punct}"

    t = _BARE_URL_RE.sub(_bare_url_sub, t)
    return t


def _option_lines(qa: QuestionAnswer) -> list[str]:
    """The options a decision compared, the chosen one and each rejected one with its reason."""
    return [
        f"  - {'Chosen' if option.chosen else 'Rejected'}: "
        f"{option.option.strip().rstrip('.')}. {option.reason.strip()}"
        for option in qa.options
    ]


def render_proposal_section(
    proposal: RefinementProposal,
    open_questions: list[str],
    sha: str,
    allowed_urls: set[str],
) -> str:
    """Builds the sanitized plain text markdown section between markers.

    The markers go around the text after it is sanitized, so `sanitize_text` neutralises an
    end marker in the model's text but never the section's own (#1470).
    """
    lines: list[str] = [
        f"<!-- checked-at: sha={sha} -->",
        "## Proposed design",
        "",
        "### Problem statement",
        proposal.problem_statement.strip(),
        "",
        "### Acceptance criteria",
    ]
    for idx, ac in enumerate(proposal.acceptance_criteria, start=1):
        lines.append(f"- Criterion {idx}: {ac.description.strip()}")
        lines.append(f"  Verification: {ac.verification.strip()}")

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
    return f"{CONST_ROADMAP_REFINE_START_MARKER}\n{section}\n{CONST_ROADMAP_REFINE_END_MARKER}"


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


def replies_since_refine(comments: Sequence[IssueComment]) -> list[IssueComment] | None:
    """The comments after refine's last comment, oldest first, or None when refine left none."""
    marked = [
        index
        for index, comment in enumerate(comments)
        if CONST_ROADMAP_REFINE_COMMENT_MARKER in comment.body
    ]
    return list(comments[marked[-1] + 1 :]) if marked else None


def _cited_code_changed(store: RoadmapStore, item: Item, since: datetime) -> bool:
    """Whether a commit on the default branch changed a path the item's block cites at or after
    `since`, the time of refine's last comment on it (#2005)."""
    for path in _recorded_block_paths(item):
        changed = store.path_changed_at(path)
        if changed is not None and changed >= since:
            return True
    return False


def _still_waiting(store: RoadmapStore, item: Item) -> WaitingItem | None:
    """The next step an item nothing changed since its last round still waits on, or None when
    the wait is over and refine looks at it again (#1758): the round recorded no step, a blocker
    closed, a comment followed refine's last one, or a commit on the default branch changed a
    path the block cites after that comment (#2005). Only a body edit ends an `EDIT` wait."""
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
    comments = store.comments_on(item.number)
    replies = replies_since_refine(comments)
    # No reply: the last comment is refine's own.
    if replies is None or replies or _cited_code_changed(store, item, comments[-1].created_at):
        return None
    return WaitingItem(item, step, details)


@dataclass
class _Selection:
    """The items one selection takes, and those it leaves with their next step."""

    store: RoadmapStore
    selected: list[Item] = field(default_factory=list)
    waiting: list[WaitingItem] = field(default_factory=list)

    def consider(self, item: Item) -> None:
        """Take `item` unless its wait is not over or a person edited its section (#1515)."""
        if _is_unchanged(item, item.body):
            waits = _still_waiting(self.store, item)
            if waits is not None:
                self.waiting.append(waits)
                return
        edit_problem = check_person_edits(item, item.body)
        if edit_problem:
            self.waiting.append(WaitingItem(item, NextStep.EDIT, (edit_problem,)))
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
    """`items`' open New items, and their unrefined Ready ones when `unrefined_ready`, highest
    priority first."""
    picked = [
        it
        for it in items
        if it.state is GitHubState.OPEN
        and (it.status == CONST_ROADMAP_STATUS_NEW or (unrefined_ready and _is_unrefined_ready(it)))
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
    source: Path,
    sha: str,
    client: LLMClient | Any,
    web: WebSearch | None = None,
    investigator: Any = None,
    max_context_tokens: int = 8192,
) -> RefinedItem:
    """Refines one item through context collection, proposal, validation and, when a question
    stays open, the investigation with `web`'s search and the `investigator` model (#2398)."""
    web = web or WebSearch()
    current_body = store.read_issue_body(item.number)

    # Person edits check
    edit_problem = check_person_edits(item, current_body)
    if edit_problem:
        return RefinedItem(
            item=item,
            proposal=RefinementProposal(problem_statement=""),
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
    request: dict[str, Any] = {
        "number": item.number,
        "title": item.title,
        "body": current_body,
        "replies": _replies_for_model(store.comments_on(item.number)),
        "context": ctx,
        "body_questions": [
            {"number": number, "question": asked}
            for number, asked in enumerate(body_questions(current_body), start=1)
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
        raw_proposal, current_body, allowed_urls, source, sha, store
    )
    if needs_investigation(proposal, open_questions):
        tools = InvestigationTools(source=source, sha=sha, firecrawl_key=web.key)
        revised = _investigate(
            item, request, raw_proposal, proposal, open_questions, tools, investigator
        )
        if revised is not None:
            allowed_urls = tools.allowed_urls
            proposal, open_questions = validate_proposal(
                revised, current_body, allowed_urls, source, sha, store
            )
    is_ready = check_ready(proposal, open_questions)
    needs_split = not proposal.fits_one_pr
    step, model_details, blocked_by = next_step_of(
        store, proposal, open_questions, is_ready=is_ready
    )
    # The details hold the model's text, which goes into a comment: sanitized like the section,
    # on one line each (#1758).
    details = tuple(" ".join(sanitize_text(d, allowed_urls).split()) for d in model_details)
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

    b_hash = hash_text(outside)
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
        body_hash=b_hash,
        section_hash=s_hash,
        next_step=step,
        step_details=details,
        blocked_by=blocked_by,
        block_paths=block_paths,
    )


def _prompt(task: str) -> str:
    """The system prompt of a refine step: the step's task, then the keys of the reply."""
    return f"{load_task_prompt(task)}\n\n{load_task_prompt('roadmap_refine_reply.md')}"


def _investigate(
    item: Item,
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
    each decision with no verified source (#2398).
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
            "Refine's investigation of #%d stopped with no proposal (%s); the item keeps its "
            "open questions.",
            item.number,
            revised.reason,
        )
        return None
    return revised


def _replies_for_model(comments: Sequence[IssueComment]) -> list[str]:
    """The replies the model reads: the comments after refine's last comment, or every comment
    when refine left none, the newest `CONST_ROADMAP_REFINE_MAX_REPLIES`, each cut to its token
    cap (#1758)."""
    replies = replies_since_refine(comments)
    kept = (comments if replies is None else replies)[-CONST_ROADMAP_REFINE_MAX_REPLIES:]
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
) -> RefinePlan:
    """Plans refinement for eligible candidates without writing anything to GitHub.

    `model` is the proposal step's client and `investigator` the investigation's pydantic-ai
    model; each defaults to the `analysis` task's (#2398)."""
    source_path = Path(source)
    sha = inspect_checkout(source_path, repo)

    candidates, waiting = select_candidates(store, item_number=item_number, limit=limit)
    if not candidates:
        return RefinePlan(repo=repo, sha=sha, waiting_items=waiting, has_writes=False)

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
                source=source_path,
                sha=sha,
                client=client,
                web=web,
                investigator=investigator,
                max_context_tokens=max_tokens,
            )
        except AICredentialsError:
            raise
        except AIClientError as exc:
            failed.append(_failed_item(cand, exc))
            continue
        refined.append(res)

    has_writes = any(r.skip_reason is None or r.record_only for r in refined) or any(
        failure.item_caused for failure in failed
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


def _failed_item(item: Item, exc: AIClientError) -> RefineFailure:
    """Record `item` as skipped for its failed model call, logging no model text: the error's
    message can quote the reply."""
    failure = RefineFailure.of(item, exc)
    logger.warning(
        "Refine skipped #%d: its model call failed (%s, %d schema violation(s)).",
        item.number,
        failure.error,
        failure.violations,
    )
    return failure


def raise_for_failed_items(plan: RefinePlan) -> None:
    """Fail a run in which the model call failed for any item, once the others are written.

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
    )


def _body_unchanged_since_read(store: RoadmapStore, number: int, body_hash: str) -> bool:
    """Whether issue `number` still holds the text outside its section that `body_hash` hashes,
    so what refine learned from the body it read still holds; a body a person changed since is
    reported."""
    fresh_outside, _ = extract_section_and_outside(store.read_issue_body(number))
    if hash_text(fresh_outside) == body_hash:
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


def apply_refine(store: RoadmapStore, plan: RefinePlan) -> RefineApplied:
    """Applies the planned writes to GitHub: updates issue body, marks, status and comments, and
    records the body of an item too big to refine or failing on its own text."""
    refined_count = readied_count = split_count = comments_posted = 0

    for r in plan.refined_items:
        if r.skip_reason is not None:
            continue

        # Race condition check: ensure body did not change between read and write
        if not _body_unchanged_since_read(store, r.item.number, r.body_hash):
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
        }

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
        if r.reason_comment:
            store.comment(r.item.number, r.reason_comment)
            comments_posted += 1

    _record_unwritten(store, plan)
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
    "DesignOption",
    "NextStep",
    "QuestionAnswer",
    "RefineApplied",
    "RefineFailure",
    "RefinePlan",
    "RefinedItem",
    "RefinementProposal",
    "WaitingItem",
    "WebSearch",
    "apply_refine",
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
    "replies_since_refine",
    "sanitize_text",
    "select_candidates",
    "step_comment",
    "validate_proposal",
    "web_search_of",
]
