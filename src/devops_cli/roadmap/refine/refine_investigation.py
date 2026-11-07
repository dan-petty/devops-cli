"""Refine's investigation (#2398): one pydantic-ai agent run, with read-only tools on the commit
refine pinned, for an item whose proposal leaves a question with no verified source.

The tools search, list and read that commit with git, and search the web through the configured providers when
the round allows it. Each tool answer is plain text, cut to `CONST_ROADMAP_REFINE_TOOL_MAX_CHARS`. An
answer that found nothing or could not run carries its outcome (`empty_answer`, `error_answer`),
and each URL a web search returns joins `allowed_urls`, the URLs a source may cite.
`UsageLimits` caps a run. The run's errors become refine's own classes, and its usage goes to
the spend ledger as one record.
"""

from __future__ import annotations

import io
import itertools
import logging
import subprocess
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext, Tool, capture_run_messages
from pydantic_ai.capabilities import PrepareTools
from pydantic_ai.exceptions import (
    ModelAPIError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    ToolCallPart,
    ToolReturn,
)
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.web_search import web_search
from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_ROADMAP_INVESTIGATION_MAX_BLOB_BYTES,
    CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
    CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,
    CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS,
    CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES,
    CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY,
    CONST_ROADMAP_REFINE_TOOL_MAX_CHARS,
    CONST_ROADMAP_REFINE_TOOL_MAX_LINES,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.ai import SearchFailed, SearchQueryRefused
from devops_cli.roadmap.agent_run import (
    RunLimit,
    RunTrace,
    drain_events,
    empty_answer,
    error_answer,
    model_call_error,
    ok_answer,
    record_run_spend,
    run_error_message,
)

logger = logging.getLogger(__name__)

# The exit code `_git` gives a command that ran out of time, as timeout(1) does.
GIT_TIMED_OUT = 124
_GIT_TIMEOUT_SECONDS = 15
# The answer of a call whose git command ran out of time.
TIMED_OUT_ANSWER = "The command ran out of time. Try a smaller path or a less common text."
# `git grep` stops at this many matches in one file, one more than a tool answer keeps, so `cut`
# still says that lines are left out. A file of millions of matching lines costs no more than this.
GREP_MATCHES_PER_FILE = CONST_ROADMAP_REFINE_TOOL_MAX_LINES + 1
# The window of the `analysis` task when no setting names one.
_DEFAULT_WINDOW = 8192


def task_window(task: str) -> int:
    """The context window of the task `task` in tokens, or a default when no setting names it. A
    run of the model passes it to `investigate`, so the window ends its tools before the counts of
    calls and requests do (#3206)."""
    return load_settings().ai.for_task(task).context_window or _DEFAULT_WINDOW


def analysis_window() -> int:
    """The context window of the `analysis` task in tokens (see `task_window`)."""
    return task_window("analysis")


def repository_path(text: str) -> str | None:
    """`text` as a path inside the repository, "" for its top, or None for a path outside it."""
    path = PurePosixPath(text.strip() or ".")
    if path.is_absolute() or ".." in path.parts:
        return None
    return "" if str(path) == "." else str(path)


def cut(lines: list[str], *, max_chars: int = CONST_ROADMAP_REFINE_TOOL_MAX_CHARS) -> str:
    """At most `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines and `max_chars` characters."""
    kept = lines[:CONST_ROADMAP_REFINE_TOOL_MAX_LINES]
    text = "\n".join(kept)[:max_chars]
    return text if len(kept) == len(lines) else f"{text}\n(more lines are left out)"


def cited_web_search(query: str, allowed_urls: set[str], *, results: int) -> str:
    """One web search of `results` results, as the text a tool answers: each result's
    title, URL and snippet. Each URL joins `allowed_urls`, the URLs a source may cite. A refused
    query and a search that no provider answered are answered as text, so they cannot stop the
    run (#2398, #3925)."""
    try:
        found = web_search(query, limit=results)
    except SearchQueryRefused as exc:
        return str(exc)
    except SearchFailed:
        return "The search failed: no provider answered."
    lines: list[str] = []
    for hit in found:
        allowed_urls.add(hit.url)
        lines.append(f"{hit.title}\n{hit.url}\n{hit.snippet}")
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
    (#2562). Refine keeps the first proposal (#2398).

    `schema_broken` is true when the model broke the run's rules with the output tool: its last
    reply held no call to a function tool, so it never gave a valid reply (#3037)."""

    reason: str
    message: str
    schema_broken: bool = False


@dataclass
class InvestigationTools:
    """The read-only tools of one investigation, on commit `sha` of the checkout at `source`.

    A tool answers each failure as text, so no argument the model sends can stop the run: a
    path outside the repository, a binary file, output that is not UTF-8, or a command that runs
    out of time. A failure is an `error_answer` and a call that finds nothing is an
    `empty_answer`, so the run can count each. `search_web` is a tool only when `web` is
    set, and it runs at most `CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES` searches.
    """

    source: Path
    sha: str
    web: bool = False
    allowed_urls: set[str] = field(default_factory=set)
    searches: int = 0
    searched: list[str] = field(default_factory=list)

    def _git(self, *args: str) -> tuple[int, bytes]:
        """The exit code and the output of one git command; `GIT_TIMED_OUT` when it ran out of time.
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
            return GIT_TIMED_OUT, b""
        return proc.returncode, cast(bytes | None, proc.stdout) or b""

    def search_code(self, text: str) -> ToolReturn:
        """Search the files of the repository for a text, in any case.

        Args:
            text: The text to find. It is a plain text, not a regular expression.

        Returns:
            One line for each match, as `path:line:content`.
        """
        self.searched.append(f"search_code {text!r}")
        code, out = self._git(
            "grep",
            "-n",
            "-I",
            "-F",
            "-i",
            f"--max-count={GREP_MATCHES_PER_FILE}",
            "-e",
            text,
            self.sha,
            "--",
        )
        if code == GIT_TIMED_OUT:
            return error_answer("The search ran out of time. Search for a less common text.")
        decoded = out.decode("utf-8", errors="replace").splitlines()
        lines = [line.removeprefix(f"{self.sha}:") for line in decoded]
        return ok_answer(cut(lines)) if code == 0 and lines else empty_answer("No match.")

    def list_files(self, directory: str = "") -> ToolReturn:
        """List the files and directories in one directory of the repository.

        Args:
            directory: The repository path of the directory. An empty text is the top.
        """
        self.searched.append(f"list_files {directory!r}")
        path = repository_path(directory)
        if path is None:
            return error_answer(f"The path {directory} is outside the repository.")
        code, out = self._git("ls-tree", "--name-only", self.sha, *([f"{path}/"] if path else []))
        if code == GIT_TIMED_OUT:
            return error_answer(TIMED_OUT_ANSWER)
        names = out.decode("utf-8", errors="replace").splitlines()
        if not names:
            return error_answer(f"The commit holds no directory {path}.")
        return ok_answer(cut(names))

    def _text_blob(self, clean: str) -> str | ToolReturn:
        """The text of the file `clean` at the commit, or the `error_answer` of a tool for a file
        that is missing, binary or larger than `CONST_ROADMAP_INVESTIGATION_MAX_BLOB_BYTES`, or
        for a git command that ran out of time. The size is read first, so a huge file is never
        held in memory."""
        size_code, size = self._git("cat-file", "-s", f"{self.sha}:{clean}")
        if size_code == GIT_TIMED_OUT:
            return error_answer(TIMED_OUT_ANSWER)
        if size_code != 0:
            return error_answer(f"The commit holds no file {clean}.")
        if int(size.strip() or 0) > CONST_ROADMAP_INVESTIGATION_MAX_BLOB_BYTES:
            return error_answer(f"The file {clean} is too large to read.")
        code, out = self._git("show", f"{self.sha}:{clean}")
        if code == GIT_TIMED_OUT:
            return error_answer(TIMED_OUT_ANSWER)
        if code != 0:
            return error_answer(f"The commit holds no file {clean}.")
        if b"\0" in out:
            return error_answer(f"The file {clean} is binary.")
        return out.decode("utf-8", errors="replace")

    def read_file(self, path: str, start_line: int = 1, end_line: int = 0) -> ToolReturn:
        """Read a file of the repository. Each line starts with its number.

        Args:
            path: The repository path of the file, such as `src/app.py`.
            start_line: The first line to read.
            end_line: The last line to read. 0 reads to the end, or to the line limit.
        """
        self.searched.append(f"read_file {path!r}")
        clean = repository_path(path)
        if not clean:
            return error_answer(f"The path {path} is outside the repository.")
        blob = self._text_blob(clean)
        if isinstance(blob, ToolReturn):
            return blob
        first = max(1, start_line)
        # One line past the limit lets `cut` say that lines are left out.
        stop = first - 1 + CONST_ROADMAP_REFINE_TOOL_MAX_LINES + 1
        if end_line >= first:
            stop = min(end_line, stop)
        text = io.StringIO(blob, newline="\n")
        lines = (line.rstrip("\n").removesuffix("\r") for line in text)
        numbered = [
            f"{number}: {line}"
            for number, line in enumerate(itertools.islice(lines, first - 1, stop), start=first)
        ]
        if not numbered:
            return empty_answer(f"The file {clean} has no lines from line {first}.")
        return ok_answer(cut(numbered))

    def search_web(self, query: str) -> str:
        """Search the web. Cite a result by its URL.

        Args:
            query: A short search query.
        """
        self.searched.append(f"search_web {query!r}")
        if not self.web:
            return "Web search is off."
        if self.searches >= CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES:
            return "The search limit for this item is reached."
        self.searches += 1
        return cited_web_search(
            query,
            self.allowed_urls,
            results=CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY,
        )

    def tools(self) -> list[Tool[None]]:
        """The tools of the run: the git tools, and the web search when the round allows it."""
        methods: list[Callable[..., str | ToolReturn]] = [
            self.search_code,
            self.list_files,
            self.read_file,
        ]
        if self.web:
            methods.append(self.search_web)
        return [Tool(method, takes_ctx=False) for method in methods]


def tool_stop(window: int) -> int:
    """The tokens of the messages at which a run of `window` offers no more tools: the window less
    its share for the reply (`CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE`)."""
    return window - window // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE


def _limit_reached(ctx: RunContext[None], window: int | None) -> RunLimit | None:
    """The limit that takes the tools from this request, or None while the run has budget for one
    more turn of calls and an answer after it, and its messages and a share of the `window` for
    the reply (`CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE`) still fit it. Without a window
    the messages are no limit. The check of the window comes last because it measures the
    messages (#3037, #3240)."""
    limits = ctx.usage_limits or UsageLimits()
    if (limits.tool_calls_limit or 0) - ctx.usage.tool_calls < (
        CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS
    ):
        return RunLimit.CALLS
    if (limits.request_limit or 0) - ctx.usage.requests <= 1:
        return RunLimit.REQUESTS
    if window is not None and tokens_of(ctx.messages) >= tool_stop(window):
        return RunLimit.WINDOW
    return None


def _offering(
    window: int | None, offered: list[tuple[str, ...]], limits_hit: list[RunLimit]
) -> Callable[[RunContext[None], list[ToolDefinition]], list[ToolDefinition]]:
    """The hook of a run: it offers the function tools while no limit is reached, and none after
    that, so the model's next reply calls the output tool. It adds the names of the tools that it
    offers to `offered`, one entry for each model request (#3477), and the first limit that it
    reaches to `limits_hit` (#3240)."""

    def hook(ctx: RunContext[None], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
        limit = _limit_reached(ctx, window) if tool_defs else None
        if limit is not None and not limits_hit:
            limits_hit.append(limit)
        tools = [] if limit is not None else tool_defs
        offered.append(tuple(tool.name for tool in tools))
        return tools

    return hook


def tokens_of(messages: Sequence[ModelMessage]) -> int:
    """The tokens of every message of a run: its instructions, requests, replies and tool answers.
    The JSON form is a little longer than the text a model reads, so the count errs high."""
    return count_tokens(ModelMessagesTypeAdapter.dump_json(list(messages)).decode())


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


def _broke_the_output_rules(messages: Sequence[ModelMessage], tools: Collection[str]) -> bool:
    """Whether the last reply of the run held no call to a function tool of `tools`: a reply that
    breaks the schema of the output, as against a tool that ran out of retries."""
    replies = [message for message in messages if isinstance(message, ModelResponse)]
    calls = (
        [part for part in replies[-1].parts if isinstance(part, ToolCallPart)] if replies else []
    )
    return not any(call.tool_name in tools for call in calls)


def investigate[T: BaseModel](
    model: Any,
    instructions: str,
    request: str,
    tools: ToolSet,
    output_type: type[T],
    output_check: Callable[[T], str | None] | None = None,
    *,
    limits: UsageLimits | None = None,
    output_retries: int | None = None,
    trace: RunTrace | None = None,
    window: int | None = None,
) -> T | InvestigationStopped:
    """Run one investigation and return its reply, or `InvestigationStopped` when the run ends
    with none.

    `output_check` reads each whole reply and returns a message, or None to accept it. The first
    time it returns a message, the run sends the message back to the model as a retry and the
    model gets one more turn; a later reply passes, and the caller decides on it (#2946).

    `limits` replaces the budget of refine, and must set `request_limit` and `tool_calls_limit`,
    which the hook `_limit_reached` reads. `output_retries` replaces the retries of a reply that
    breaks the schema. `trace` takes what the run did, also when it stops (#3037), the tools
    that each request offered (#3477), and the limit that ended its tools (#3240). `window` is the
    context window of the model in tokens: a request that would leave less than
    `1 / CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE` of it for the reply offers no tool.

    Raises `AICredentialsError` when the model refuses the key, and `AIClientError` for any
    other failed model call.
    """
    function_tools = tools.tools()
    offered: list[tuple[str, ...]] = []
    limits_hit: list[RunLimit] = []
    agent: Agent[None, T] = Agent(
        model,
        output_type=output_type,
        instructions=instructions,
        tools=function_tools,
        retries={
            "tools": CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,
            "output": CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES
            if output_retries is None
            else output_retries,
        },
        capabilities=[PrepareTools(_offering(window, offered, limits_hit))],
    )
    if output_check is not None:
        _retry_once(agent, output_check)
    limits = limits or UsageLimits(
        request_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
        tool_calls_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
    )
    tool_names = {tool.name for tool in function_tools}
    started = time.monotonic()
    with capture_run_messages() as messages:
        try:
            result = agent.run_sync(request, usage_limits=limits, event_stream_handler=drain_events)
        except (UsageLimitExceeded, UnexpectedModelBehavior) as stopped:
            # The hook takes the tools away before the requests run out, so a hard stop with no
            # earlier limit is one reply with more calls than the budget had left. The message of
            # the error is not read.
            if isinstance(stopped, UsageLimitExceeded) and not limits_hit:
                limits_hit.append(RunLimit.CALLS)
            return InvestigationStopped(
                type(stopped).__name__,
                run_error_message(stopped),
                schema_broken=isinstance(stopped, UnexpectedModelBehavior)
                and _broke_the_output_rules(messages, tool_names),
            )
        except ModelAPIError as exc:
            # Raised outside this handler, so a logged traceback holds no reply text.
            error = model_call_error(exc, "The investigation's")
        else:
            return result.output
        finally:
            if trace is not None:
                trace.absorb(
                    messages,
                    tools=tool_names,
                    offered=offered,
                    limit=limits_hit[0] if limits_hit else None,
                )
            record_run_spend(model, messages, time.monotonic() - started, stage="analysis")
    raise error


__all__ = [
    "InvestigationStopped",
    "InvestigationTools",
    "ToolSet",
    "analysis_window",
    "cited_web_search",
    "cut",
    "investigate",
    "repository_path",
    "task_window",
    "tokens_of",
    "tool_stop",
]
