"""`devops roadmap refine`: item refinement to Ready with proposed design, tasks and acceptance criteria.

Without `--item`, refine picks New items in the next planned release by priority, then New items in the
backlog by priority, until 12 Ready items or `--limit` (default 3) are reached.
It skips items that are Ready, Blocked, started, or unchanged since their last run.
Inputs are minimized from `--source` at HEAD SHA (docs, cited files/lines, identifiers, repo map).
Two model steps run with `ai.for_task("analysis")`: research plan (Tavily search when public) and proposal.
Their prompts are `roadmap_refine_research.md` and `roadmap_refine_proposal.md`, and the issue reaches the
model as a JSON document; `chat_structured` adds the schema each reply must match.
Deterministic validation checks sources, key questions and owner decisions, and the Ready check sets
Status New → Ready only when complete.
A model call that fails skips only its item: refine writes the others, then fails with
`RoadmapRefineError` naming each skipped item, its error's class and its schema violation count.
Rejected credentials still stop the run at the first item.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    StructuredOutputValidationError,
)
from devops_cli.ai.common_tools import tavily_search
from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_P0_PRIORITY,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
    CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES,
    CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_REFINE_LIMIT,
    DEFAULT_ROADMAP_RELEASE_CAP,
)
from devops_cli.config.settings import get_ai_api_key, get_tavily_api_key, load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapRefineError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.store import (
    GitHubState,
    Item,
    ItemField,
    JobRecord,
    RefineRecordKey,
    Release,
    RoadmapStore,
)

logger = logging.getLogger(__name__)

# ── Models ────────────────────────────────────────────────────────────────────


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[str] = Field(default_factory=list)


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    verification: str


class QuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    answer: str
    kind: Literal["fact", "decision"]
    sources: list[str] = Field(default_factory=list)


class RefinementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_statement: str
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    key_questions: list[QuestionAnswer] = Field(default_factory=list)
    fits_one_pr: bool = True
    split_offs: list[str] = Field(default_factory=list)
    suspected_block: str | None = None
    dependencies: list[int] = Field(default_factory=list)


@dataclass(frozen=True)
class RefinedItem:
    item: Item
    proposal: RefinementProposal
    open_questions: list[str]
    is_ready: bool
    needs_split: bool
    reason_comment: str | None
    new_body: str
    body_hash: str
    section_hash: str
    skip_reason: str | None = None


@dataclass(frozen=True)
class RefineFailure:
    """An item refine skipped because its model call failed: the error's class name and the
    last reply's schema violation count (0 when it held no JSON, or the call got no reply),
    never the model's text."""

    item: Item
    error: str
    violations: int = 0

    @classmethod
    def of(cls, item: Item, exc: AIClientError) -> RefineFailure:
        """The failure `exc` made of `item`'s model call."""
        violations = exc.violations if isinstance(exc, StructuredOutputValidationError) else 0
        return cls(item=item, error=type(exc).__name__, violations=violations)


@dataclass(frozen=True)
class RefinePlan:
    repo: str
    sha: str
    branch: str
    refined_items: list[RefinedItem] = field(default_factory=list)
    skipped_items: list[tuple[Item, str]] = field(default_factory=list)
    has_writes: bool = False
    failed_items: list[RefineFailure] = field(default_factory=list)


@dataclass(frozen=True)
class RefineApplied:
    refined_count: int
    readied_count: int
    split_count: int
    comments_posted: int


@dataclass(frozen=True)
class RefineOutcome:
    plan: RefinePlan
    applied: RefineApplied | None = None


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


# ── Git & Checkout Inspection ─────────────────────────────────────────────────


def _git(checkout: Path, *args: str) -> tuple[int, str]:
    proc = run_subprocess(
        [BIN_GIT, "-C", str(checkout), *args],
        env={"GIT_TERMINAL_PROMPT": "0"},
        timeout=15,
        quiet=True,
    )
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def inspect_checkout(source: Path | str, expected_repo: str) -> tuple[str, str]:
    """Inspects the checkout at `source`, verifies origin matches `expected_repo`,
    and returns (sha, branch). Raises GitHubOperationError if origin mismatch.
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
    if code_sha != 0 or not sha:
        raise GitHubOperationError(
            f"Could not determine HEAD SHA in {source}.",
            operation="roadmap.refine.inspect_checkout",
            details={"source": str(source)[:256]},
        )
    code_br, branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    branch_name = branch if (code_br == 0 and branch and branch != "HEAD") else "HEAD"
    return sha, branch_name


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
        code, out = _git(source, "ls-tree", "-r", "--name-only", sha, d)
        if code == 0 and out:
            files.extend(out.splitlines()[:15])
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
    code_adr, adr_list = _git(source, "ls-tree", "-r", "--name-only", sha, "docs/adr")
    if code_adr == 0 and adr_list:
        for adr_path in adr_list.splitlines()[:5]:
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


# ── Search & External Research ────────────────────────────────────────────────


def _categorize_search_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "timeout" in msg:
        return "timeout"
    status_match = re.search(r"\b(4\d\d|5\d\d)\b", msg)
    if status_match:
        return status_match.group(1)
    return "malformed reply"


def run_research_step(
    store: RoadmapStore,
    body: str,
    client: LLMClient | Any,
) -> tuple[list[dict[str, str]], set[str]]:
    """Runs step 1 (research plan) and executes queries through Tavily when allowed.
    Returns (results_list, allowed_urls).
    """
    try:
        is_private = store.repository_is_private()
    except Exception as exc:
        logger.warning("Could not read repository visibility: %s", exc)
        return [], set()

    tavily_key = get_tavily_api_key()
    if is_private or not tavily_key:
        return [], set()

    # Step 1: research plan from model
    request = {"body": body, "max_queries": CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES}
    try:
        plan: ResearchPlan = client.chat_structured(
            load_task_prompt("roadmap_refine_research.md"),
            json.dumps(request, ensure_ascii=False, indent=1),
            ResearchPlan,
        )
    except AICredentialsError:
        raise
    except AIClientError as exc:
        # The error's message can quote the reply, so only its class is logged.
        logger.warning(
            "Research plan generation failed (%s); refining without search results.",
            type(exc).__name__,
        )
        return [], set()

    queries = [q.strip() for q in plan.queries if q.strip()][
        :CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES
    ]
    search_results: list[dict[str, str]] = []
    allowed_urls: set[str] = set()

    for query in queries:
        try:
            res = tavily_search(
                query=query,
                max_results=CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY,
                api_key=tavily_key,
            )
            for item in res:
                url = item.get("url") or ""
                if url:
                    allowed_urls.add(url)
                search_results.append(
                    {
                        "query": query,
                        "title": item.get("title") or "",
                        "url": url,
                        "content": item.get("content") or "",
                    }
                )
        except Exception as exc:
            cat = _categorize_search_error(exc)
            search_results.append({"query": query, "error": f"research failed: {cat}"})

    return search_results, allowed_urls


# ── Proposal Validation ───────────────────────────────────────────────────────

_KEY_QUESTIONS_HEADING_RE = re.compile(r"^#+\s*Key questions\b", re.IGNORECASE)
_OWNER_DECISIONS_HEADING_RE = re.compile(r"^#+\s*Owner decisions\b", re.IGNORECASE)


def _normalize_question(text: str) -> str:
    cleaned = re.sub(r"^[-\*0-9\.\s]+", "", text)
    cleaned = re.sub(r"[\*_`\?]", "", cleaned)
    return " ".join(cleaned.lower().split())


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


def _is_valid_source(src: str, allowed_urls: set[str], source: Path, sha: str) -> bool:
    if src in allowed_urls or src.startswith("http://") or src.startswith("https://"):
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


def validate_proposal(
    proposal: RefinementProposal,
    body: str,
    allowed_urls: set[str],
    source: Path,
    sha: str,
    store: RoadmapStore,
) -> tuple[RefinementProposal, list[str]]:
    """Deterministically validates proposal sources, key questions, and decisions.
    Returns (validated_proposal, open_questions).
    """
    open_questions: list[str] = []
    validated_qa: list[QuestionAnswer] = []

    # 1. Sources validation
    for qa in proposal.key_questions:
        valid_srcs = [s for s in qa.sources if _is_valid_source(s, allowed_urls, source, sha)]
        if qa.kind == "fact" and not valid_srcs:
            open_questions.append(f"{qa.question} (missing verified source)")
        else:
            validated_qa.append(qa.model_copy(update={"sources": valid_srcs}))

    # 2. Body's own key questions check
    body_questions = _extract_heading_bullets(body, _KEY_QUESTIONS_HEADING_RE)
    answered_normalized = {_normalize_question(qa.question) for qa in proposal.key_questions}
    for bq in body_questions:
        norm = _normalize_question(bq)
        if not any(norm in a or a in norm for a in answered_normalized):
            open_questions.append(bq)

    # 3. Decision checking against ## Owner decisions
    owner_decisions = [
        line.strip().lower() for line in _extract_heading_bullets(body, _OWNER_DECISIONS_HEADING_RE)
    ]
    final_qa: list[QuestionAnswer] = []
    for qa in validated_qa:
        if qa.kind == "decision":
            ans_clean = qa.answer.strip().lower()
            is_owner = any(d in ans_clean or ans_clean in d for d in owner_decisions if len(d) > 5)
            marker = "(owner decision)" if is_owner else "(proposed)"
            new_ans = f"{qa.answer} {marker}" if marker not in qa.answer else qa.answer
            final_qa.append(qa.model_copy(update={"answer": new_ans}))
        else:
            final_qa.append(qa)

    # 4. Dependency check
    all_known_issues: set[int] = (
        {item.number for item in store.items()} if hasattr(store, "items") else set()
    )
    valid_deps = [dep for dep in proposal.dependencies if dep in all_known_issues]

    validated_proposal = proposal.model_copy(
        update={
            "key_questions": final_qa,
            "dependencies": valid_deps,
        }
    )
    return validated_proposal, open_questions


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
    if proposal.suspected_block and proposal.suspected_block.strip().lower() not in {
        "none",
        "null",
        "",
    }:
        return False
    return True


# ── Rendering & Sanitization ──────────────────────────────────────────────────

_IMAGE_RE = re.compile(r"!\[.*?\](?:\(.*?\)|\[.*?\])")
_HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
_HANDLE_RE = re.compile(r"(?<!`)(@[a-zA-Z0-9_\-]+)(?!`)")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_BARE_URL_RE = re.compile(r"(?<!`)(https?://[^\s\)]+)(?!`)")


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


def render_proposal_section(
    proposal: RefinementProposal,
    open_questions: list[str],
    sha: str,
    branch: str,
    allowed_urls: set[str],
) -> str:
    """Builds the sanitized plain text markdown section between markers."""
    lines: list[str] = [
        CONST_ROADMAP_REFINE_START_MARKER,
        f"<!-- checked-at: sha={sha} branch={branch} -->",
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

    lines.append(CONST_ROADMAP_REFINE_END_MARKER)
    raw = "\n".join(lines)
    return sanitize_text(raw, allowed_urls)


# ── Selection ─────────────────────────────────────────────────────────────────

_PRIORITY_ORDER: Final[dict[str | None, int]] = {
    CONST_ROADMAP_CRITICAL_PRIORITY: 0,
    CONST_ROADMAP_P0_PRIORITY: 1,
    "P1-High": 2,
    "P2-Medium": 3,
    "P3-Low": 4,
}


def _priority_rank(priority: str | None) -> int:
    return _PRIORITY_ORDER.get(priority, 5)


def _find_next_planned_release(releases: Sequence[Release]) -> Release | None:
    open_releases = [r for r in releases if r.state is GitHubState.OPEN]
    if not open_releases:
        return None
    current = min(open_releases, key=lambda r: r.version)
    later = [r for r in open_releases if r.version > current.version]
    return min(later, key=lambda r: r.version, default=None)


def _select_single_candidate(
    store: RoadmapStore, item_number: int
) -> tuple[list[Item], list[tuple[Item, str]]]:
    item = store.item(item_number)
    if item is None:
        return [], []
    if (
        item.status in {CONST_ROADMAP_STATUS_READY, "Blocked", "In Progress"}
        or item.state is GitHubState.CLOSED
    ):
        return [], [(item, f"status {item.status or 'closed'} is not New")]
    # Check unchanged
    body = store.read_issue_body(item.number)
    outside, inside = extract_section_and_outside(body)
    b_hash, s_hash = hash_text(outside), (hash_text(inside) if inside else None)
    if b_hash == item.job_record.get(RefineRecordKey.BODY_HASH) and s_hash == item.job_record.get(
        RefineRecordKey.SECTION_HASH
    ):
        return [], [(item, "body and section unchanged")]
    return [item], []


def select_candidates(
    store: RoadmapStore,
    *,
    item_number: int | None = None,
    limit: int = DEFAULT_ROADMAP_REFINE_LIMIT,
) -> tuple[list[Item], list[tuple[Item, str]]]:
    """Selects items to refine based on rules, returning (selected, skipped)."""
    if item_number is not None:
        return _select_single_candidate(store, item_number)

    next_rel = _find_next_planned_release(store.releases())
    next_items = store.items(release=next_rel.title) if next_rel else []
    backlog_items = store.backlog()

    # Count ready items across next planned and backlog
    ready_count = sum(
        1 for it in (*next_items, *backlog_items) if it.status == CONST_ROADMAP_STATUS_READY
    )

    # Filter New items
    next_new = [it for it in next_items if it.status == "New" and it.state is GitHubState.OPEN]
    backlog_new = [
        it for it in backlog_items if it.status == "New" and it.state is GitHubState.OPEN
    ]

    next_new.sort(key=lambda it: _priority_rank(it.priority))
    backlog_new.sort(key=lambda it: _priority_rank(it.priority))

    selected: list[Item] = []
    skipped: list[tuple[Item, str]] = []

    def _consider(it: Item) -> bool:
        body = store.read_issue_body(it.number)
        outside, inside = extract_section_and_outside(body)
        b_hash = hash_text(outside)
        s_hash = hash_text(inside) if inside else None
        if b_hash == it.job_record.get(RefineRecordKey.BODY_HASH) and s_hash == it.job_record.get(
            RefineRecordKey.SECTION_HASH
        ):
            skipped.append((it, "unchanged"))
            return False
        selected.append(it)
        return True

    # 1. Next release New items
    for it in next_new:
        if len(selected) >= limit:
            break
        _consider(it)

    # 2. Backlog New items until ready + selected reaches cap
    cap = DEFAULT_ROADMAP_RELEASE_CAP
    for it in backlog_new:
        if len(selected) >= limit or (ready_count + len(selected)) >= cap:
            break
        _consider(it)

    return selected, skipped


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
    branch: str,
    client: LLMClient | Any,
    max_context_tokens: int = 8192,
) -> RefinedItem:
    """Refines one item through context collection, research, proposal, and validation."""
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
            skip_reason=edit_problem,
        )

    # Step 1: Research
    search_results, allowed_urls = run_research_step(store, current_body, client)

    # Step 2: Context minimization
    ctx = collect_context(source, sha, current_body, max_tokens=max_context_tokens)

    # Step 3: Proposal generation
    request = {
        "number": item.number,
        "title": item.title,
        "body": current_body,
        "context": ctx,
        "search_results": search_results,
    }
    raw_proposal: RefinementProposal = client.chat_structured(
        load_task_prompt("roadmap_refine_proposal.md"),
        json.dumps(request, ensure_ascii=False, indent=1),
        RefinementProposal,
    )

    # Step 4: Validation
    proposal, open_questions = validate_proposal(
        raw_proposal, current_body, allowed_urls, source, sha, store
    )
    is_ready = check_ready(proposal, open_questions)
    needs_split = not proposal.fits_one_pr

    # Step 5: Render section & Check size
    rendered_section = render_proposal_section(proposal, open_questions, sha, branch, allowed_urls)
    outside, _ = extract_section_and_outside(current_body)
    new_body = outside.rstrip() + "\n\n" + rendered_section

    if len(new_body) > CONST_ROADMAP_REFINE_MAX_BODY_CHARS:
        return RefinedItem(
            item=item,
            proposal=proposal,
            open_questions=open_questions,
            is_ready=False,
            needs_split=needs_split,
            reason_comment=None,
            new_body=current_body,
            body_hash="",
            section_hash="",
            skip_reason=f"new body would exceed {CONST_ROADMAP_REFINE_MAX_BODY_CHARS} characters",
        )

    # Reason comment
    comment: str | None = None
    if is_ready:
        comment = MESSAGES.roadmap.refine_ready_comment.format(sha=sha[:12])
    elif needs_split:
        count = len(proposal.split_offs) or 2
        comment = MESSAGES.roadmap.refine_split_comment.format(count=count, sha=sha[:12])

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
    )


# ── Top-Level Entry Points ────────────────────────────────────────────────────


def plan_refine(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path | str = ".",
    ref: str | None = None,
    item_number: int | None = None,
    limit: int = DEFAULT_ROADMAP_REFINE_LIMIT,
    config: RoadmapConfig | None = None,
    model: Any = None,
) -> RefinePlan:
    """Plans refinement for eligible candidates without writing anything to GitHub."""
    source_path = Path(source)
    sha, branch = inspect_checkout(source_path, repo)

    candidates, skipped = select_candidates(store, item_number=item_number, limit=limit)
    if not candidates:
        return RefinePlan(
            repo=repo, sha=sha, branch=branch, skipped_items=skipped, has_writes=False
        )

    settings = load_settings()
    ai_config = settings.ai
    client = model or LLMClient(ai_config.for_task("analysis"), api_key=get_ai_api_key(settings))
    max_tokens = ai_config.for_task("analysis").context_window or 8192

    refined: list[RefinedItem] = []
    failed: list[RefineFailure] = []
    for cand in candidates:
        try:
            res = refine_one_item(
                store,
                cand,
                source=source_path,
                sha=sha,
                branch=branch,
                client=client,
                max_context_tokens=max_tokens,
            )
        except AICredentialsError:
            raise
        except AIClientError as exc:
            failed.append(_failed_item(cand, exc))
            continue
        refined.append(res)

    has_writes = any(r.skip_reason is None for r in refined)
    return RefinePlan(
        repo=repo,
        sha=sha,
        branch=branch,
        refined_items=refined,
        skipped_items=skipped,
        has_writes=has_writes,
        failed_items=failed,
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


def apply_refine(store: RoadmapStore, plan: RefinePlan) -> RefineApplied:
    """Applies the planned writes to GitHub: updates issue body, marks, status and comments."""
    refined_count = readied_count = split_count = comments_posted = 0

    for r in plan.refined_items:
        if r.skip_reason is not None:
            continue

        # Race condition check: ensure body did not change between read and write
        fresh_body = store.read_issue_body(r.item.number)
        fresh_outside, _ = extract_section_and_outside(fresh_body)
        if hash_text(fresh_outside) != r.body_hash:
            logger.warning(
                "Skipping #%d: the body changed between the read and the write.",
                r.item.number,
            )
            continue

        # Write body
        store.write_issue_body(r.item.number, r.new_body)
        refined_count += 1

        # Prepare marks
        marks: JobRecord = {
            RefineRecordKey.BODY_HASH: r.body_hash,
            RefineRecordKey.SECTION_HASH: r.section_hash,
            RefineRecordKey.NEEDS_SPLIT: "true" if r.needs_split else "false",
        }

        # Status change & marks
        if r.is_ready:
            store.set_field(r.item, ItemField.STATUS, CONST_ROADMAP_STATUS_READY, marks=marks)
            readied_count += 1
        else:
            store.set_marks(r.item, marks)

        if r.needs_split:
            split_count += 1

        # Comment
        if r.reason_comment:
            store.comment(r.item.number, r.reason_comment)
            comments_posted += 1

    return RefineApplied(
        refined_count=refined_count,
        readied_count=readied_count,
        split_count=split_count,
        comments_posted=comments_posted,
    )


def _store_repo(store: RoadmapStore) -> str | None:
    if hasattr(store, "_repo"):
        val = getattr(store, "_repo")
        return str(val) if val is not None else None
    roadmap = getattr(store, "_roadmap", None)
    if roadmap is not None and hasattr(roadmap, "repo"):
        val = getattr(roadmap, "repo")
        return str(val) if val is not None else None
    return None


def refine_item(
    store: RoadmapStore,
    number: int,
    *,
    source: Path | str = ".",
    ref: str | None = None,
    config: RoadmapConfig | None = None,
    confirm: bool = True,
    model: Any = None,
) -> RefineOutcome:
    """Entry point for refining a single item directly (used by intake hook and CLI)."""
    source_path = Path(source)
    repo = _store_repo(store) or get_repo_origin_name(source_path) or "example/repo"
    plan = plan_refine(
        store,
        repo=repo,
        source=source_path,
        ref=ref,
        item_number=number,
        config=config,
        model=model,
    )
    applied = apply_refine(store, plan) if (confirm and plan.has_writes) else None
    raise_for_failed_items(plan)
    return RefineOutcome(plan=plan, applied=applied)


def render_refine_plan(plan: RefinePlan) -> str:
    """Formats the refinement plan for CLI stdout report."""
    lines: list[str] = [MESSAGES.roadmap.refine_title.format(repo=plan.repo)]
    if not (plan.refined_items or plan.skipped_items or plan.failed_items):
        lines.append(MESSAGES.roadmap.refine_none)
        return "\n".join(lines)

    if plan.refined_items:
        lines.append("## Refined Items")
        for r in plan.refined_items:
            if r.skip_reason:
                lines.append(f"- #{r.item.number} {r.item.title}: skipped ({r.skip_reason})")
            else:
                status_str = "Ready" if r.is_ready else ("Needs Split" if r.needs_split else "New")
                lines.append(f"- #{r.item.number} {r.item.title} -> {status_str}")
                if r.open_questions:
                    lines.append(f"  Open questions: {len(r.open_questions)}")

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

    if plan.skipped_items:
        lines.append("## Skipped Items")
        for it, reason in plan.skipped_items:
            lines.append(f"- #{it.number} {it.title}: {reason}")

    return "\n".join(lines)


__all__ = [
    "AcceptanceCriterion",
    "QuestionAnswer",
    "RefineApplied",
    "RefineFailure",
    "RefineOutcome",
    "RefinePlan",
    "RefinedItem",
    "RefinementProposal",
    "ResearchPlan",
    "apply_refine",
    "check_person_edits",
    "check_ready",
    "collect_context",
    "extract_section_and_outside",
    "hash_text",
    "inspect_checkout",
    "plan_refine",
    "raise_for_failed_items",
    "refine_item",
    "render_proposal_section",
    "render_refine_plan",
    "sanitize_text",
    "select_candidates",
    "validate_proposal",
]
