"""Refine's investigation (#2398): one pydantic-ai agent run, with read-only tools on the commit
refine pinned, for an item whose proposal leaves a question with no verified source.

The tools search, list and read that commit with git, and search the web through Firecrawl when the
round allows it. Each tool answer is plain text, cut to `CONST_ROADMAP_REFINE_TOOL_MAX_CHARS`,
and each URL a web search returns joins `allowed_urls`, the URLs a source may cite.
`UsageLimits` caps a run. The run's errors become refine's own classes, and its usage goes to
the spend ledger as one record.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

import httpx2
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext, Tool, capture_run_messages
from pydantic_ai.capabilities import PrepareTools
from pydantic_ai.exceptions import (
    ModelAPIError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.common_tools import firecrawl_search
from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
    CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,
    CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS,
    CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES,
    CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY,
    CONST_ROADMAP_REFINE_TOOL_MAX_CHARS,
    CONST_ROADMAP_REFINE_TOOL_MAX_LINES,
)
from devops_cli.core.process import run_subprocess
from devops_cli.roadmap.agent_run import (
    drain_events,
    model_call_error,
    record_run_spend,
    run_error_message,
)

logger = logging.getLogger(__name__)

# The exit code `_git` gives a command that ran out of time, as timeout(1) does.
_TIMED_OUT = 124
_GIT_TIMEOUT_SECONDS = 15


def _repository_path(text: str) -> str | None:
    """`text` as a path inside the repository, "" for its top, or None for a path outside it."""
    path = PurePosixPath(text.strip() or ".")
    if path.is_absolute() or ".." in path.parts:
        return None
    return "" if str(path) == "." else str(path)


def cut(lines: list[str]) -> str:
    """At most `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines and `..._MAX_CHARS` characters."""
    kept = lines[:CONST_ROADMAP_REFINE_TOOL_MAX_LINES]
    text = "\n".join(kept)[:CONST_ROADMAP_REFINE_TOOL_MAX_CHARS]
    return text if len(kept) == len(lines) else f"{text}\n(more lines are left out)"


def cited_web_search(query: str, key: str, allowed_urls: set[str], *, results: int) -> str:
    """One Firecrawl search of `results` results, as the text a tool answers: each result's
    title, URL and description. Each http or https URL joins `allowed_urls`, the URLs a source
    may cite. A failed search is answered as text, so it cannot stop the run (#2398)."""
    try:
        found = firecrawl_search(query, key, limit=results)
    except (httpx2.HTTPError, ValueError) as exc:
        return f"The search failed: {type(exc).__name__}."
    lines: list[str] = []
    for result in found:
        url = str(result.get("url") or "")
        if urlsplit(url).scheme in {"http", "https"}:
            allowed_urls.add(url)
        lines.append(f"{result.get('title') or ''}\n{url}\n{result.get('description') or ''}")
    return cut("\n\n".join(lines).splitlines()) or "No result."


class ToolSet(Protocol):
    """The tools of one agent run: refine's `InvestigationTools`, or another job's."""

    def tools(self) -> list[Tool[None]]:
        """The pydantic-ai tools the model may call."""


@dataclass(frozen=True)
class InvestigationStopped:
    """An investigation that ended with no proposal: it spent its budget (`UsageLimitExceeded`),
    or the model broke the run's rules past its retries (`UnexpectedModelBehavior`). `reason` is
    the class of pydantic-ai's error, and `message` the first line of its message, masked and cut
    (#2562). Refine keeps the first proposal (#2398)."""

    reason: str
    message: str


@dataclass
class InvestigationTools:
    """The read-only tools of one investigation, on commit `sha` of the checkout at `source`.

    A tool answers each failure as text, so no argument the model sends can stop the run: a
    path outside the repository, a binary file, output that is not UTF-8, or a command that runs
    out of time. `search_web` is a tool only when `firecrawl_key` is set, and it runs at most
    `CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES` searches.
    """

    source: Path
    sha: str
    firecrawl_key: str | None = None
    allowed_urls: set[str] = field(default_factory=set)
    searches: int = 0

    def _git(self, *args: str) -> tuple[int, bytes]:
        """The exit code and the output of one git command; `_TIMED_OUT` when it ran out of time.
        An argument that holds a NUL byte, which no git argument can hold, runs nothing."""
        if any("\0" in arg for arg in args):
            return 1, b""
        try:
            proc = run_subprocess(
                [BIN_GIT, "-C", str(self.source), *args],
                env={"GIT_TERMINAL_PROMPT": "0"},
                text=False,
                timeout=_GIT_TIMEOUT_SECONDS,
                quiet=True,
            )
        except subprocess.TimeoutExpired:
            return _TIMED_OUT, b""
        return proc.returncode, cast(bytes | None, proc.stdout) or b""

    def search_code(self, text: str) -> str:
        """Search the files of the repository for a text, in any case.

        Args:
            text: The text to find. It is a plain text, not a regular expression.

        Returns:
            One line for each match, as `path:line:content`.
        """
        code, out = self._git("grep", "-n", "-I", "-F", "-i", "-e", text, self.sha, "--")
        if code == _TIMED_OUT:
            return "The search ran out of time. Search for a less common text."
        decoded = out.decode("utf-8", errors="replace").splitlines()
        lines = [line.removeprefix(f"{self.sha}:") for line in decoded]
        return cut(lines) if code == 0 and lines else "No match."

    def list_files(self, directory: str = "") -> str:
        """List the files and directories in one directory of the repository.

        Args:
            directory: The repository path of the directory. An empty text is the top.
        """
        path = _repository_path(directory)
        if path is None:
            return f"The path {directory} is outside the repository."
        _, out = self._git("ls-tree", "--name-only", self.sha, *([f"{path}/"] if path else []))
        names = out.decode("utf-8", errors="replace").splitlines()
        return cut(names) or f"The commit holds no directory {path}."

    def read_file(self, path: str, start_line: int = 1, end_line: int = 0) -> str:
        """Read a file of the repository. Each line starts with its number.

        Args:
            path: The repository path of the file, such as `src/app.py`.
            start_line: The first line to read.
            end_line: The last line to read. 0 reads to the end, or to the line limit.
        """
        clean = _repository_path(path)
        if not clean:
            return f"The path {path} is outside the repository."
        code, out = self._git("show", f"{self.sha}:{clean}")
        if code != 0:
            return f"The commit holds no file {clean}."
        if b"\0" in out:
            return f"The file {clean} is binary."
        lines = out.decode("utf-8", errors="replace").splitlines()
        first = max(1, start_line)
        last = len(lines) if end_line < first else min(end_line, len(lines))
        numbered = [f"{number}: {lines[number - 1]}" for number in range(first, last + 1)]
        return cut(numbered) or f"The file {clean} has no lines from line {first}."

    def search_web(self, query: str) -> str:
        """Search the web. Cite a result by its URL.

        Args:
            query: A short search query.
        """
        if not self.firecrawl_key:
            return "Web search is off."
        if self.searches >= CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES:
            return "The search limit for this item is reached."
        self.searches += 1
        return cited_web_search(
            query,
            self.firecrawl_key,
            self.allowed_urls,
            results=CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY,
        )

    def tools(self) -> list[Tool[None]]:
        """The tools of the run: the git tools, and the web search when a key is set."""
        methods: list[Callable[..., str]] = [self.search_code, self.list_files, self.read_file]
        if self.firecrawl_key:
            methods.append(self.search_web)
        return [Tool(method, takes_ctx=False) for method in methods]


def _within_budget(ctx: RunContext[None], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
    """The function tools while the run has budget for one more turn of calls and an answer after
    it; none after that, so the model's next reply calls the output tool."""
    limits = ctx.usage_limits or UsageLimits()
    tool_calls_left = (limits.tool_calls_limit or 0) - ctx.usage.tool_calls
    requests_left = (limits.request_limit or 0) - ctx.usage.requests
    has_budget = tool_calls_left >= CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS
    return tool_defs if has_budget and requests_left > 1 else []


def _retry_once[T: BaseModel](
    agent: Agent[None, T], output_check: Callable[[T], str | None]
) -> None:
    """Make `agent` send the message of `output_check` back to the model once, for the first
    whole reply that the check does not accept."""
    retried = False

    def validate(ctx: RunContext[None], output: T) -> T:
        nonlocal retried
        if ctx.partial_output or retried:
            return output
        message = output_check(output)
        if message is None:
            return output
        retried = True
        raise ModelRetry(message)

    agent.output_validator(validate)


def investigate[T: BaseModel](
    model: Any,
    instructions: str,
    request: str,
    tools: ToolSet,
    output_type: type[T],
    output_check: Callable[[T], str | None] | None = None,
) -> T | InvestigationStopped:
    """Run one investigation and return its reply, or `InvestigationStopped` when the run ends
    with none.

    `output_check` reads each whole reply and returns a message, or None to accept it. The first
    time it returns a message, the run sends the message back to the model as a retry and the
    model gets one more turn; a later reply passes, and the caller decides on it (#2946).

    Raises `AICredentialsError` when the model refuses the key, and `AIClientError` for any
    other failed model call.
    """
    agent: Agent[None, T] = Agent(
        model,
        output_type=output_type,
        instructions=instructions,
        tools=tools.tools(),
        retries={
            "tools": CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,
            "output": CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,
        },
        capabilities=[PrepareTools(_within_budget)],
    )
    if output_check is not None:
        _retry_once(agent, output_check)
    limits = UsageLimits(
        request_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
        tool_calls_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
    )
    started = time.monotonic()
    with capture_run_messages() as messages:
        try:
            result = agent.run_sync(request, usage_limits=limits, event_stream_handler=drain_events)
        except (UsageLimitExceeded, UnexpectedModelBehavior) as stopped:
            return InvestigationStopped(type(stopped).__name__, run_error_message(stopped))
        except ModelAPIError as exc:
            # Raised outside this handler, so a logged traceback holds no reply text.
            error = model_call_error(exc, "The investigation's")
        else:
            return result.output
        finally:
            record_run_spend(model, messages, time.monotonic() - started, stage="analysis")
    raise error


__all__ = [
    "InvestigationStopped",
    "InvestigationTools",
    "ToolSet",
    "cited_web_search",
    "cut",
    "investigate",
]
