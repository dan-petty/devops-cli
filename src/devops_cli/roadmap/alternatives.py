"""`devops roadmap alternatives` (#2650): for each open item, one agent run asks which open,
maintained tool or library covers the item's need, in whole or in part.

**Selection.** An open Item with Status New or Ready, whose author has write access, is taken.
Items with no check come first, lowest number first, then items whose last check is older than
`roadmap.alternatives.recheck_days` or whose text changed since, oldest check first. `--limit`
caps a run. An item whose last check failed less than `roadmap.alternatives.retry_days` ago is
left out. `--item` checks the one item it names whenever it is open.

**The run.** `investigate` of refine's investigation runs the agent with three tools: a Firecrawl
web search, a GitHub repository read and a PyPI package read. The tools are the only sources. They
keep the URLs they returned, the facts they read and the searches they ran, and the job writes
those into the record: the model writes only the verdict, the URL of the tool, and what it covers
and lacks. The job refuses a reply that cites a URL no tool returned, and sets `maintained` from
the facts. A failed model call, a stopped run or a refused reply skips its item, and the others are
written. The run fails, naming each skipped item, only when it tried items and checked none.
Rejected credentials stop the run at the first item.

**Writes.** With `--confirm` a check replaces the job's block in the body, records
`alternatives.*` in the job record, and posts one comment that carries
`CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER`. It changes no label and closes no issue. A comment
after the job's last one reaches the next check as a reply. A skipped item gets only
`alternatives.failed_at` and `alternatives.failed_error` in its job record; a written check
clears both.

The check is off when the repository is private, its visibility cannot be read, or no Firecrawl
key is set: a verdict `none` would then say that no tool exists when none was looked for.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, Field
from pydantic_ai import Tool

from devops_cli.ai.client.factory import get_task_model
from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_CLASSIFIER_SEPARATOR,
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_LICENSE_CLASSIFIER,
    CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS,
    CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS,
    CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS,
    CONST_ROADMAP_ALTERNATIVES_MAX_LICENSE_CHARS,
    CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
    CONST_ROADMAP_ALTERNATIVES_REFUSED_ERROR,
    CONST_ROADMAP_ALTERNATIVES_SEARCH_RESULTS,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_MAX_REPLIES,
    CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.defaults import (
    DEFAULT_PYPI_PACKAGE_URL,
    DEFAULT_PYPI_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.exceptions.roadmap import RoadmapAlternativesError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine import (
    extract_section_and_outside,
    hash_text,
    replies_after_marker,
    sanitize_text,
    web_search_of,
)
from devops_cli.roadmap.refine_investigation import (
    InvestigationStopped,
    cited_web_search,
    investigate,
)
from devops_cli.roadmap.store import (
    AlternativesRecordKey,
    GitHubState,
    IssueComment,
    Item,
    RoadmapStore,
    Verdict,
    is_name_segment,
    is_repository_name,
)
from devops_cli.telemetry.instruments import ROADMAP_ALTERNATIVES_TOTAL, emit

logger = logging.getLogger(__name__)

_PROMPT = "roadmap_alternatives.md"

# ── The reply ─────────────────────────────────────────────────────────────────


_TOOL_VERDICTS = frozenset({Verdict.COVERS, Verdict.PARTLY})


class AlternativesReply(BaseModel):
    """The model's reply. The license, the dates, whether the tool is maintained and the searches
    that ran are the job's to write, so the reply holds none of them."""

    verdict: Verdict
    tool_url: str | None = None
    covers: list[str] = Field(default_factory=list)
    lacks: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


# ── The facts a tool read ─────────────────────────────────────────────────────


def _key(url: str) -> str:
    """`url` as the job compares it: a trailing slash does not make another URL."""
    return url.rstrip("/")


@dataclass(frozen=True)
class ToolFacts:
    """What a fact tool read of one tool: `last_activity` is the last push of a repository, or the
    latest upload of a PyPI package."""

    name: str
    url: str
    license: str | None
    last_activity: datetime | None
    archived: bool = False

    def maintained(self, now: datetime) -> bool:
        """Whether the tool is not archived and was active within
        `CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS`."""
        if self.archived or self.last_activity is None:
            return False
        return now - self.last_activity <= timedelta(
            days=CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS
        )


class _PyPIInfo(BaseModel):
    name: str
    version: str
    license_expression: str | None = None
    license: str | None = None
    classifiers: list[str] = Field(default_factory=list)
    package_url: str

    @property
    def license_name(self) -> str | None:
        """The license the package states: its SPDX expression, else its `license` field when that
        is a name and not a whole text, else the name in its first `License ::` classifier."""
        if self.license_expression:
            return self.license_expression
        text = (self.license or "").strip()
        if text and "\n" not in text and len(text) <= CONST_ROADMAP_ALTERNATIVES_MAX_LICENSE_CHARS:
            return text
        classifier = next(
            (
                c
                for c in self.classifiers
                if c.startswith(CONST_ROADMAP_ALTERNATIVES_LICENSE_CLASSIFIER)
            ),
            None,
        )
        if classifier is None:
            return None
        return classifier.rsplit(CONST_ROADMAP_ALTERNATIVES_CLASSIFIER_SEPARATOR, 1)[-1]


class _PyPIFile(BaseModel):
    upload_time_iso_8601: datetime


class _PyPIPackage(BaseModel):
    """A package as `https://pypi.org/pypi/<name>/json` gives it."""

    info: _PyPIInfo
    urls: list[_PyPIFile] = Field(default_factory=list)

    @property
    def last_upload(self) -> datetime | None:
        return max((file.upload_time_iso_8601 for file in self.urls), default=None)


def _read_pypi(name: str) -> _PyPIPackage | None:
    """The PyPI record of package `name`, or None when PyPI has no such package. Raises on any
    other failed read."""
    url = DEFAULT_PYPI_PACKAGE_URL.format(name=quote(name, safe=""))
    with new_http_client(level=EgressLevel.PUBLIC) as client:
        response = client.get(url, timeout=DEFAULT_PYPI_TIMEOUT_SECONDS)
    if response.status_code == httpx2.codes.NOT_FOUND:
        return None
    response.raise_for_status()
    return _PyPIPackage.model_validate(response.json())


def _day(moment: datetime | None) -> str:
    return moment.date().isoformat() if moment else MESSAGES.roadmap.alternatives_never


def _yes_no(answer: bool) -> str:
    texts = MESSAGES.roadmap
    return texts.alternatives_yes if answer else texts.alternatives_no


@dataclass
class AlternativesTools:
    """The tools of one item's check. `search_web` runs at most
    `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` searches, and the two fact tools make at most
    `CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS` reads together. A tool answers a failed read, or a
    read over its limit, as text, so no argument the model sends can stop the run; a spent GitHub
    quota still stops it. The tools keep what they return: the URLs a source may cite, the facts
    by URL, and the searches that ran.
    """

    store: RoadmapStore
    firecrawl_key: str
    allowed_urls: set[str] = field(default_factory=set)
    facts: dict[str, ToolFacts] = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)
    fact_reads: int = 0

    def search_web(self, query: str) -> str:
        """Search the web. Cite a result by its URL.

        Args:
            query: A short search query.
        """
        if len(self.queries) >= CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES:
            return MESSAGES.roadmap.alternatives_search_limit
        self.queries.append(query)
        found: set[str] = set()
        answer = cited_web_search(
            query,
            self.firecrawl_key,
            found,
            results=CONST_ROADMAP_ALTERNATIVES_SEARCH_RESULTS,
        )
        self.allowed_urls |= {_key(url) for url in found}
        return answer

    def github_repository(self, name: str) -> str:
        """Read the facts of a GitHub repository: its license, last push, whether it is archived,
        its stars and its latest release.

        Args:
            name: The repository as `owner/name`.
        """
        texts = MESSAGES.roadmap
        if not is_repository_name(name):
            return texts.alternatives_bad_repository
        if self._spent():
            return texts.alternatives_fact_limit
        try:
            repository = self.store.repository_facts(name)
        except GitHubRateLimitError:
            raise
        except GitHubOperationError as exc:
            logger.warning(
                "A repository read of the alternatives check failed: %s.", type(exc).__name__
            )
            return texts.alternatives_read_failed.format(error=type(exc).__name__)
        if repository is None:
            return texts.alternatives_no_repository.format(name=name)
        self._learn(
            ToolFacts(
                name=repository.full_name,
                url=_key(repository.url),
                license=repository.license,
                last_activity=repository.pushed_at,
                archived=repository.archived,
            )
        )
        released = (
            f"{repository.latest_release} ({_day(repository.released_at)})"
            if repository.latest_release
            else texts.alternatives_no_release
        )
        return "\n".join(
            [
                repository.url,
                texts.alternatives_fact_license.format(
                    license=repository.license or texts.alternatives_not_stated
                ),
                texts.alternatives_fact_push.format(date=_day(repository.pushed_at)),
                texts.alternatives_fact_archived.format(answer=_yes_no(repository.archived)),
                texts.alternatives_fact_stars.format(stars=repository.stars),
                texts.alternatives_fact_release.format(release=released),
            ]
        )

    def pypi_package(self, name: str) -> str:
        """Read the facts of a package on PyPI: its license, latest version and the date of its
        latest upload.

        Args:
            name: The package name as PyPI spells it.
        """
        texts = MESSAGES.roadmap
        if not is_name_segment(name):
            return texts.alternatives_bad_package
        if self._spent():
            return texts.alternatives_fact_limit
        try:
            package = _read_pypi(name)
        except (httpx2.HTTPError, ValueError) as exc:
            logger.warning("A PyPI read of the alternatives check failed: %s.", type(exc).__name__)
            return texts.alternatives_read_failed.format(error=type(exc).__name__)
        if package is None:
            return texts.alternatives_no_package.format(name=name)
        self._learn(
            ToolFacts(
                name=package.info.name,
                url=_key(package.info.package_url),
                license=package.info.license_name,
                last_activity=package.last_upload,
            )
        )
        return "\n".join(
            [
                package.info.package_url,
                texts.alternatives_fact_license.format(
                    license=package.info.license_name or texts.alternatives_not_stated
                ),
                texts.alternatives_fact_version.format(version=package.info.version),
                texts.alternatives_fact_upload.format(date=_day(package.last_upload)),
            ]
        )

    def _spent(self) -> bool:
        """Whether the fact reads are spent; if not, counts one more."""
        if self.fact_reads >= CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS:
            return True
        self.fact_reads += 1
        return False

    def _learn(self, facts: ToolFacts) -> None:
        self.facts[facts.url] = facts
        self.allowed_urls.add(facts.url)

    def tools(self) -> list[Tool[None]]:
        """The three tools of the run."""
        return [
            Tool(method, takes_ctx=False)
            for method in (self.search_web, self.github_repository, self.pypi_package)
        ]


# ── The check ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CheckedTool:
    """The tool a check found, with the facts the job read: the model wrote none of them."""

    name: str
    url: str
    license: str | None
    last_activity: datetime | None
    maintained: bool


@dataclass(frozen=True)
class Check:
    """One item's check, ready to write: the comment, and the body with the job's block."""

    item: Item
    verdict: Verdict
    tool: CheckedTool | None
    covers: tuple[str, ...]
    lacks: tuple[str, ...]
    queries: tuple[str, ...]
    sources: tuple[str, ...]
    checked_at: datetime
    body_hash: str
    new_body: str
    comment: str


@dataclass(frozen=True)
class CheckFailure:
    """An item the job skipped, and why: a failed model call, a run that ended with no reply, or a
    reply the job refused. `error_class` and `failed_at` go to the item's job record."""

    item: Item
    reason: str
    error_class: str
    failed_at: datetime


@dataclass(frozen=True)
class Selection:
    """The items a run checks, and the open ones it leaves because their check is current."""

    selected: list[Item]
    current: list[Item]


@dataclass(frozen=True)
class AlternativesPlan:
    """A run's result. `off_reason` is set when the check is off, and then nothing else is."""

    repo: str
    checks: list[Check] = field(default_factory=list)
    failures: list[CheckFailure] = field(default_factory=list)
    current: list[Item] = field(default_factory=list)
    off_reason: str | None = None
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()

    @property
    def has_writes(self) -> bool:
        """Whether a run with `--confirm` writes anything: a check, or the record of a failure."""
        return bool(self.checks) or bool(self.failures) or bool(self.write_requests)


def body_hash_of(body: str) -> str:
    """The hash of `body` outside the job's block and refine's section: what a person wrote, so a
    write of either job starts no new check."""
    outside, _ = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    return hash_text(extract_section_and_outside(outside)[0])


def _recorded_time(item: Item, key: AlternativesRecordKey, name: str) -> datetime | None:
    """The time that the job record of `item` holds at `key`, or None when it holds none or the
    value is not a time."""
    recorded = item.job_record.get(key)
    if not recorded:
        return None
    try:
        return datetime.fromisoformat(recorded)
    except ValueError:
        logger.warning(
            "The %s time recorded on #%d is not a time; the item is checked.", name, item.number
        )
        return None


def _checked_at(item: Item) -> datetime | None:
    """When the job's last check of `item` ran, or None when it recorded none or the record is
    not a time."""
    return _recorded_time(item, AlternativesRecordKey.CHECKED_AT, "check")


def _in_retry_delay(item: Item, retry_days: int, now: datetime) -> bool:
    """Whether the last check of `item` failed less than `retry_days` days before `now`."""
    failed_at = _recorded_time(item, AlternativesRecordKey.FAILED_AT, "failure")
    return failed_at is not None and now - failed_at < timedelta(days=retry_days)


def _is_eligible(item: Item) -> bool:
    return (
        item.state is GitHubState.OPEN
        and item.status in {CONST_ROADMAP_STATUS_NEW, CONST_ROADMAP_STATUS_READY}
        and item.author_association in CONST_ROADMAP_TRUSTED_AUTHORS
    )


def _is_due(item: Item, checked_at: datetime, recheck_days: int, now: datetime) -> bool:
    """Whether the check of `item` made at `checked_at` is old, or its text changed since."""
    old = now - checked_at > timedelta(days=recheck_days)
    return old or item.job_record.get(AlternativesRecordKey.BODY_HASH) != body_hash_of(item.body)


def select_items(
    store: RoadmapStore,
    *,
    item_number: int | None,
    limit: int,
    recheck_days: int,
    retry_days: int,
    now: datetime,
) -> Selection:
    """Up to `limit` items to check, in the order the module's docstring gives, and the eligible
    items whose check is current. An item whose check failed less than `retry_days` days ago is in
    neither list. `item_number` names the one open item to check, whatever its failure."""
    if item_number is not None:
        item = store.item(item_number)
        return Selection([item] if item and item.state is GitHubState.OPEN else [], [])
    unchecked: list[Item] = []
    due: list[tuple[datetime, Item]] = []
    current: list[Item] = []
    for item in filter(_is_eligible, store.items()):
        if _in_retry_delay(item, retry_days, now):
            continue
        checked_at = _checked_at(item)
        if checked_at is None:
            unchecked.append(item)
        elif _is_due(item, checked_at, recheck_days, now):
            due.append((checked_at, item))
        else:
            current.append(item)
    ordered = sorted(unchecked, key=lambda it: it.number)
    ordered += [item for _, item in sorted(due, key=lambda pair: (pair[0], pair[1].number))]
    return Selection(ordered[:limit], current)


def _request(item: Item, comments: Sequence[IssueComment]) -> str:
    """The JSON document the model reads: the item without the job's block, the replies since the
    job's last comment (every comment when it left none), and the budget."""
    outside, _ = extract_section_and_outside(
        item.body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    after = replies_after_marker(comments, CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER)
    replies = (comments if after is None else after)[-CONST_ROADMAP_REFINE_MAX_REPLIES:]
    document = {
        "number": item.number,
        "title": item.title,
        "body": truncate_to_token_limit(
            outside.strip(), max_tokens=CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS
        ),
        "replies": [
            truncate_to_token_limit(reply.body, max_tokens=CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS)
            for reply in replies
        ],
        "search_budget": {
            "searches": CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
            "results_per_search": CONST_ROADMAP_ALTERNATIVES_SEARCH_RESULTS,
            "fact_reads": CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS,
        },
    }
    return json.dumps(document, ensure_ascii=False, indent=1)


def _refusal(reply: AlternativesReply, tools: AlternativesTools) -> str | None:
    """Why the job refuses `reply`, or None. A tool verdict needs a tool whose facts a tool read,
    `not-applicable` needs a run with no search and no fact read, and every source must be a URL
    that a tool returned."""
    texts = MESSAGES.roadmap
    if reply.verdict is Verdict.NOT_APPLICABLE and (tools.queries or tools.fact_reads):
        return texts.alternatives_reason_not_applicable
    if reply.verdict in _TOOL_VERDICTS:
        if reply.tool_url is None:
            return texts.alternatives_reason_no_tool.format(verdict=reply.verdict.value)
        if _key(reply.tool_url) not in tools.facts:
            return texts.alternatives_reason_no_facts.format(url=reply.tool_url)
    unknown = next((url for url in reply.sources if _key(url) not in tools.allowed_urls), None)
    return texts.alternatives_reason_url.format(url=unknown) if unknown is not None else None


def _checked_tool(
    reply: AlternativesReply, tools: AlternativesTools, now: datetime
) -> CheckedTool | None:
    """The tool of a tool verdict, from the facts read; None for any other verdict."""
    if reply.verdict not in _TOOL_VERDICTS or reply.tool_url is None:
        return None
    facts = tools.facts[_key(reply.tool_url)]
    return CheckedTool(
        name=facts.name,
        url=facts.url,
        license=facts.license,
        last_activity=facts.last_activity,
        maintained=facts.maintained(now),
    )


def _clean(texts: Sequence[str], allowed_urls: set[str]) -> tuple[str, ...]:
    """The model's `texts` on one line each, with no live link, mention, image, tag or marker."""
    return tuple(sanitize_text(" ".join(text.split()), allowed_urls) for text in texts)


def _tool_section(tool: CheckedTool | None) -> list[str]:
    texts = MESSAGES.roadmap
    if tool is None:
        return [texts.alternatives_comment_no_tool]
    return [
        texts.alternatives_comment_tool.format(name=tool.name, url=tool.url),
        texts.alternatives_comment_license.format(
            license=tool.license or texts.alternatives_not_stated
        ),
        texts.alternatives_comment_activity.format(date=_day(tool.last_activity)),
        texts.alternatives_comment_maintained.format(answer=_yes_no(tool.maintained)),
    ]


def _list_section(title: str, lines: Sequence[str]) -> list[str]:
    item = MESSAGES.roadmap.alternatives_comment_item
    return [title, *(item.format(text=line) for line in lines)] if lines else []


def _comment_of(check: Check) -> str:
    """The comment of a check: the marker, the verdict, the tool with its facts, the lists, and a
    line that says what the check does not do."""
    texts = MESSAGES.roadmap
    heading = [
        CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
        texts.alternatives_comment_heading.format(verdict=check.verdict.value),
    ]
    sections = [
        heading,
        _tool_section(check.tool),
        _list_section(texts.alternatives_comment_covers, check.covers),
        _list_section(texts.alternatives_comment_lacks, check.lacks),
        _list_section(texts.alternatives_comment_queries, check.queries),
        _list_section(texts.alternatives_comment_sources, check.sources),
        [texts.alternatives_comment_footer.format(date=check.checked_at.date().isoformat())],
    ]
    return "\n\n".join("\n".join(section) for section in sections if section)


def _block_of(check: Check) -> str:
    """The block of the body: the latest verdict and tool, between the job's two markers."""
    texts = MESSAGES.roadmap
    tool = check.tool
    if tool is None:
        detail = texts.alternatives_block_no_tool
    else:
        detail = texts.alternatives_block_tool.format(
            name=tool.name,
            url=tool.url,
            license=tool.license or texts.alternatives_not_stated,
            date=_day(tool.last_activity),
            maintained=(
                texts.alternatives_maintained
                if tool.maintained
                else texts.alternatives_not_maintained
            ),
        )
    return "\n".join(
        [
            CONST_ROADMAP_ALTERNATIVES_START_MARKER,
            texts.alternatives_block_verdict.format(
                date=check.checked_at.date().isoformat(), verdict=check.verdict.value
            ),
            detail,
            CONST_ROADMAP_ALTERNATIVES_END_MARKER,
        ]
    )


def _marker_problem(body: str) -> str | None:
    """Why the job writes no block to `body`, or None: it holds a marker of the block with no
    partner, so a write could replace a person's text between the two."""
    _, inside = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    markers = (CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER)
    if inside is None and any(marker in body for marker in markers):
        return MESSAGES.roadmap.alternatives_reason_markers
    return None


def _with_block(body: str, block: str) -> str:
    """`body` with its block of the job replaced by `block`, or with `block` at its end."""
    _, inside = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    if inside is None:
        return f"{body.rstrip()}\n\n{block}" if body.strip() else block
    start = body.find(CONST_ROADMAP_ALTERNATIVES_START_MARKER)
    end = body.find(CONST_ROADMAP_ALTERNATIVES_END_MARKER, start) + len(
        CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    return f"{body[:start]}{block}{body[end:]}"


def validate_reply(
    item: Item, reply: AlternativesReply, tools: AlternativesTools, now: datetime
) -> Check | CheckFailure:
    """The check that `reply` makes, or the failure when the job refuses it."""
    refusal = _refusal(reply, tools) or _marker_problem(item.body)
    if refusal is not None:
        return CheckFailure(item, refusal, CONST_ROADMAP_ALTERNATIVES_REFUSED_ERROR, now)
    allowed = tools.allowed_urls
    partial = Check(
        item=item,
        verdict=reply.verdict,
        tool=_checked_tool(reply, tools, now),
        covers=_clean(reply.covers, allowed),
        lacks=_clean(reply.lacks, allowed),
        queries=_clean(tools.queries, allowed),
        sources=tuple(dict.fromkeys(_key(url) for url in reply.sources)),
        checked_at=now,
        body_hash=body_hash_of(item.body),
        new_body="",
        comment="",
    )
    return replace(
        partial,
        new_body=_with_block(item.body, _block_of(partial)),
        comment=_comment_of(partial),
    )


def _stopped_reason(stopped: InvestigationStopped) -> str:
    """The reason of a run that stopped: the class of the error and, when it has one, its masked
    message (#2562, #2922)."""
    texts = MESSAGES.roadmap
    if not stopped.message:
        return texts.alternatives_reason_stopped.format(reason=stopped.reason)
    return texts.alternatives_reason_stopped_message.format(
        reason=stopped.reason, message=stopped.message
    )


def _check_one(
    store: RoadmapStore, item: Item, *, key: str, model: Any, now: datetime
) -> Check | CheckFailure:
    """One item's agent run and its validated reply. Raises `AICredentialsError` when the model
    refuses the key."""
    tools = AlternativesTools(store=store, firecrawl_key=key)
    request = _request(item, store.comments_on(item.number))
    texts = MESSAGES.roadmap
    try:
        reply = investigate(model, load_task_prompt(_PROMPT), request, tools, AlternativesReply)
    except AICredentialsError:
        raise
    except AIClientError as exc:
        logger.warning(
            "The alternatives check of #%d was skipped: its model call failed (%s).",
            item.number,
            type(exc).__name__,
        )
        error = type(exc).__name__
        return CheckFailure(item, texts.alternatives_reason_error.format(error=error), error, now)
    if isinstance(reply, InvestigationStopped):
        logger.warning(
            "The alternatives check of #%d was skipped: its run stopped (%s).",
            item.number,
            reply.reason,
        )
        return CheckFailure(item, _stopped_reason(reply), reply.reason, now)
    return validate_reply(item, reply, tools, now)


# ── Entry points ──────────────────────────────────────────────────────────────


def plan_alternatives(
    store: RoadmapStore,
    *,
    repo: str,
    item_number: int | None = None,
    limit: int | None = None,
    now: datetime | None = None,
    investigator: Any = None,
) -> AlternativesPlan:
    """Plans the checks of the selected items without writing anything. `limit` is
    `roadmap.alternatives.limit` by default. `investigator` is the pydantic-ai model of the runs,
    the `analysis` task's by default."""
    moment = now or datetime.now(UTC)
    web = web_search_of(store)
    if web.key is None:
        return AlternativesPlan(repo=repo, off_reason=web.off_reason)
    config = load_settings().roadmap.alternatives
    selection = select_items(
        store,
        item_number=item_number,
        limit=config.limit if limit is None else limit,
        recheck_days=config.recheck_days,
        retry_days=config.retry_days,
        now=moment,
    )
    if not selection.selected:
        return AlternativesPlan(repo=repo, current=selection.current)
    model = investigator or get_task_model("analysis")
    checks: list[Check] = []
    failures: list[CheckFailure] = []
    for item in selection.selected:
        outcome = _check_one(store, item, key=web.key, model=model, now=moment)
        if isinstance(outcome, CheckFailure):
            failures.append(outcome)
        else:
            checks.append(outcome)
    return AlternativesPlan(repo=repo, checks=checks, failures=failures, current=selection.current)


def _unchanged_since_read(store: RoadmapStore, check: Check) -> bool:
    """Whether issue `check.item` still holds the text the check read, so a person's edit since
    is not written over."""
    if body_hash_of(store.read_issue_body(check.item.number)) == check.body_hash:
        return True
    logger.warning(
        "Skipping #%d: the body changed between the read and the write.", check.item.number
    )
    return False


def apply_alternatives(store: RoadmapStore, plan: AlternativesPlan) -> int:
    """Writes each check: the body block, the job record, then the comment, and counts it in
    `devops_cli_roadmap_alternatives_total` by its verdict. Then records each failure in the job
    record of its item: the time and the class of the error. Returns how many checks it wrote; a
    check whose body a person changed since the read is left for the next run."""
    written = 0
    for check in plan.checks:
        if not _unchanged_since_read(store, check):
            continue
        number = check.item.number
        store.write_issue_body(number, check.new_body)
        store.set_marks(
            check.item,
            {
                AlternativesRecordKey.CHECKED_AT: check.checked_at.isoformat(),
                AlternativesRecordKey.BODY_HASH: check.body_hash,
                AlternativesRecordKey.VERDICT: check.verdict.value,
                AlternativesRecordKey.TOOL: check.tool.url if check.tool else None,
                AlternativesRecordKey.FAILED_AT: None,
                AlternativesRecordKey.FAILED_ERROR: None,
            },
        )
        store.comment(number, check.comment)
        emit(ROADMAP_ALTERNATIVES_TOTAL, 1, {"verdict": check.verdict.value})
        written += 1
    for failure in plan.failures:
        store.set_marks(
            failure.item,
            {
                AlternativesRecordKey.FAILED_AT: failure.failed_at.isoformat(),
                AlternativesRecordKey.FAILED_ERROR: failure.error_class,
            },
        )
    return written


def raise_for_failed_checks(plan: AlternativesPlan) -> None:
    """Fail a run that tried items and checked none, once the failures are recorded (#2949). A run
    that checked at least one item, or tried none, does not fail. The error names each skipped item
    with its reason, and holds no text of the model."""
    if plan.checks or not plan.failures:
        return
    texts = MESSAGES.roadmap
    items = ", ".join(
        texts.alternatives_failed_item.format(number=failure.item.number, reason=failure.reason)
        for failure in plan.failures
    )
    raise RoadmapAlternativesError(
        texts.alternatives_failed.format(count=len(plan.failures), items=items),
        failed_items=[failure.item.number for failure in plan.failures],
    )


def dry_run_alternatives(
    repo: str, *, item: int | None = None, limit: int | None = None
) -> AlternativesPlan:
    """The plan a dry run returns, having made no external request."""
    from devops_cli.roadmap.request_plan import alternatives_requests

    reads, writes = alternatives_requests(repo, item=item, limit=limit)
    return AlternativesPlan(repo=repo, dry_run=True, requests=reads, write_requests=writes)


def render_alternatives_plan(plan: AlternativesPlan) -> str:
    """The report: each check, each item whose check is current, and each skipped item."""
    texts = MESSAGES.roadmap
    lines = [texts.alternatives_title.format(repo=plan.repo)]
    if plan.off_reason:
        lines.append(texts.alternatives_off.format(reason=plan.off_reason))
        return "\n".join(lines)
    if not (plan.checks or plan.current or plan.failures):
        lines.append(texts.alternatives_none)
        return "\n".join(lines)
    if plan.checks:
        lines.append(texts.alternatives_checked_heading)
        lines += [
            texts.alternatives_check_line.format(
                number=check.item.number, title=check.item.title, verdict=check.verdict.value
            )
            for check in plan.checks
        ]
    if plan.current:
        lines.append(texts.alternatives_current_heading)
        lines += [
            texts.alternatives_current_line.format(
                number=item.number,
                title=item.title,
                date=_day(_checked_at(item)),
            )
            for item in plan.current
        ]
    if plan.failures:
        lines.append(texts.alternatives_skipped_heading)
        lines += [
            texts.alternatives_skipped_line.format(
                number=failure.item.number, title=failure.item.title, reason=failure.reason
            )
            for failure in plan.failures
        ]
    return "\n".join(lines)


__all__ = [
    "AlternativesPlan",
    "AlternativesReply",
    "AlternativesTools",
    "Check",
    "CheckFailure",
    "CheckedTool",
    "Selection",
    "ToolFacts",
    "Verdict",
    "apply_alternatives",
    "body_hash_of",
    "dry_run_alternatives",
    "plan_alternatives",
    "raise_for_failed_checks",
    "render_alternatives_plan",
    "select_items",
    "validate_reply",
]
