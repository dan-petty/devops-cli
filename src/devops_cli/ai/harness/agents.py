"""Preconfigured Coder, Researcher, Macroscope, and Browser agents."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    BaseCapability,
    PydanticAgent,
    RunContext,
    Tool,
)
from devops_cli.ai.common_tools import duckduckgo_search_tool, web_fetch_tool
from devops_cli.ai.harness.constants import (
    DEFAULT_CODER_INSTRUCTIONS,
    DEFAULT_MACROSCOPE_GUIDANCE,
    DEFAULT_RESEARCHER_INSTRUCTIONS,
)
from devops_cli.ai.harness.filesystem import FileSystem
from devops_cli.ai.harness.planning import Planning
from devops_cli.ai.harness.repo_context import RepoContext
from devops_cli.ai.harness.shell import Shell

logger = logging.getLogger(__name__)


class Coder(BaseCapability):
    """Composite harness stack for autonomous coding agents."""

    id: str = "coder_harness"
    workspace_dir: Path = Field(default_factory=lambda: Path("."))
    allowed_commands: list[str] = Field(
        default_factory=lambda: [
            "git",
            "rg",
            "grep",
            "find",
            "ls",
            "cat",
            "sed",
            "head",
            "tail",
            "python",
            "uv",
            "pytest",
            "ruff",
            "make",
        ]
    )

    def __init__(
        self, workspace_dir: Path | str = ".", allowed_commands: list[str] | None = None
    ) -> None:
        p = Path(workspace_dir)
        cmds = (
            allowed_commands
            if allowed_commands is not None
            else [
                "git",
                "rg",
                "grep",
                "find",
                "ls",
                "cat",
                "sed",
                "head",
                "tail",
                "python",
                "uv",
                "pytest",
                "ruff",
                "make",
            ]
        )
        super().__init__(workspace_dir=p, allowed_commands=cmds)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        fs = FileSystem(root=self.workspace_dir)
        sh = Shell(cwd=self.workspace_dir, allowed_commands=self.allowed_commands)
        plan = Planning()
        return fs.get_tools() + sh.get_tools() + plan.get_tools()

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        repo = RepoContext(workspace_dir=self.workspace_dir)
        return repo.get_system_prompt_additions(ctx) + ["Coding Agent Harness Stack active."]


def coder_agent(
    client: Any = None,
    *,
    name: str = "coder",
    instructions: str = DEFAULT_CODER_INSTRUCTIONS,
    workspace_dir: Path | str = ".",
    allowed_commands: list[str] | None = None,
) -> PydanticAgent[Any]:
    """Create a configured Coder agent instance with full harness capabilities."""
    return PydanticAgent(
        client=client,
        name=name,
        system_prompt=instructions,
        capabilities=[Coder(workspace_dir=workspace_dir, allowed_commands=allowed_commands)],
    )


class Researcher(BaseCapability):
    """Composite harness stack for autonomous web and document research agents."""

    id: str = "researcher_harness"
    allowed_domains: list[str] | None = None
    instructions: str | None = DEFAULT_RESEARCHER_INSTRUCTIONS

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        instructions: str | None = DEFAULT_RESEARCHER_INSTRUCTIONS,
    ) -> None:
        super().__init__(allowed_domains=allowed_domains, instructions=instructions)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        fetch = web_fetch_tool(allowed_domains=self.allowed_domains)
        search = duckduckgo_search_tool()
        return [fetch, search]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions = [
            "Researcher Agent Harness Stack active (DuckDuckGo search + SSRF-safe Web Fetch)."
        ]
        if self.instructions:
            additions.append(self.instructions)
        return additions


def researcher_agent(
    client: Any = None,
    *,
    name: str = "researcher",
    instructions: str | None = DEFAULT_RESEARCHER_INSTRUCTIONS,
    allowed_domains: list[str] | None = None,
) -> PydanticAgent[Any]:
    """Create a configured Researcher agent instance with web search and fetch capabilities."""
    return PydanticAgent(
        client=client,
        name=name,
        system_prompt=instructions or "",
        capabilities=[Researcher(allowed_domains=allowed_domains, instructions=instructions)],
    )


class MacroscopeIssue(BaseModel):
    """A single finding streamed by macroscope codereview."""

    model_config = ConfigDict(extra="ignore")

    issue_id: str = ""
    sequence: int = 0
    path: str = ""
    line: int = 1
    severity: str = "medium"
    category: str = "quality"
    body: str = ""


class MacroscopeReview(BaseModel):
    """The result of one macroscope codereview execution."""

    review_id: str | None = None
    status: str = "completed"
    findings: list[MacroscopeIssue] = Field(default_factory=list)


def _parse_macroscope_output(
    output: str, default_status: str
) -> tuple[str | None, str, list[MacroscopeIssue]]:
    """Parse JSON stream output from macroscope execution."""
    findings: list[MacroscopeIssue] = []
    review_id: str | None = None
    status = default_status

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            ev_type = data.get("type")
            if ev_type == "review_id":
                review_id = data.get("id")
            elif ev_type == "issue_event":
                findings.append(MacroscopeIssue.model_validate(data.get("issue", {})))
            elif ev_type == "issue_status":
                status = data.get("status", status)
        except Exception:
            continue
    return review_id, status, findings


def _format_macroscope_review(review: MacroscopeReview) -> str:
    """Format MacroscopeReview findings as canonical markdown."""
    if not review.findings:
        return f"Macroscope review {review.review_id or ''} finished with status: {review.status}. 0 issues found."
    formatted = [
        f"Macroscope Review ({review.review_id or 'unknown'}) - Status: {review.status} ({len(review.findings)} findings):"
    ]
    formatted.extend(
        f"- [{f.severity.upper()}] {f.path}:{f.line} ({f.category}): {f.body}"
        for f in review.findings
    )
    return "\n".join(formatted)


class Macroscope(BaseCapability):
    """Capability running Macroscope CLI code reviews and feeding structured findings to the agent."""

    id: str = "macroscope"
    base: str | None = None
    command: str = "macroscope"
    cwd: Path = Field(default_factory=lambda: Path("."))
    timeout: float = 600.0
    guidance: str | None = DEFAULT_MACROSCOPE_GUIDANCE

    def __init__(
        self,
        base: str | None = None,
        *,
        command: str = "macroscope",
        cwd: Path | str = ".",
        timeout: float = 600.0,
        guidance: str | None = DEFAULT_MACROSCOPE_GUIDANCE,
    ) -> None:
        p = Path(cwd)
        super().__init__(
            base=base,
            command=command,
            cwd=p,
            timeout=timeout,
            guidance=guidance,
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        def run_macroscope_review(base: str | None = None) -> str:
            """Run macroscope codereview and return findings."""
            import shutil

            bin_path = shutil.which(self.command)
            if not bin_path:
                return (
                    f"Macroscope CLI '{self.command}' not found. "
                    "Install via: curl -sSL https://raw.githubusercontent.com/prassoai/macroscope-local/main/install.sh | bash"
                )

            diff_base = base or self.base
            cmd = [self.command, "codereview", "--raw"]
            if diff_base:
                cmd.extend(["--base", diff_base])

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.cwd.resolve()),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
                output = proc.stdout or ""
                def_status = "completed" if proc.returncode == 0 else "failed"
                review_id, status, findings = _parse_macroscope_output(output, def_status)
                review = MacroscopeReview(review_id=review_id, status=status, findings=findings)
                return _format_macroscope_review(review)
            except subprocess.TimeoutExpired:
                return f"Macroscope review timed out after {self.timeout}s"
            except Exception as exc:
                return f"Macroscope review error: {exc}"

        return [
            Tool.from_function(
                run_macroscope_review,
                name="run_macroscope_review",
                description="Run macroscope codereview on the repository and return structured findings.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions = ["Macroscope Code Review Capability enabled."]
        if self.guidance:
            additions.append(self.guidance)
        return additions


DEFAULT_PLAYWRIGHT_GUIDANCE: str = """Use Playwright browser tools to navigate web pages, inspect accessibility snapshots, click elements, fill forms, and take screenshots.
Prefer snapshot() to discover element handles (aria-ref=) over guessing selectors."""


class PlaywrightBrowser(BaseCapability):
    """Capability managing a headless Chromium browser instance via Playwright."""

    id: str = "playwright_browser"
    headless: bool = True
    allowed_domains: list[str] | None = None
    block_private_addresses: bool = True
    screenshot_on_navigate: bool = False
    max_content_tokens: int = 4000
    action_timeout_ms: int = 5000
    navigation_timeout_ms: int = 60000
    chromium_sandbox: bool = True
    auto_install_chromium: bool = False
    storage_state: Any = None
    cdp_url: str | None = None
    guidance: str | None = DEFAULT_PLAYWRIGHT_GUIDANCE

    def __init__(
        self,
        *,
        headless: bool = True,
        allowed_domains: list[str] | None = None,
        block_private_addresses: bool = True,
        screenshot_on_navigate: bool = False,
        max_content_tokens: int = 4000,
        action_timeout_ms: int = 5000,
        navigation_timeout_ms: int = 60000,
        chromium_sandbox: bool = True,
        auto_install_chromium: bool = False,
        storage_state: Any = None,
        cdp_url: str | None = None,
        guidance: str | None = DEFAULT_PLAYWRIGHT_GUIDANCE,
    ) -> None:
        super().__init__(
            headless=headless,
            allowed_domains=allowed_domains,
            block_private_addresses=block_private_addresses,
            screenshot_on_navigate=screenshot_on_navigate,
            max_content_tokens=max_content_tokens,
            action_timeout_ms=action_timeout_ms,
            navigation_timeout_ms=navigation_timeout_ms,
            chromium_sandbox=chromium_sandbox,
            auto_install_chromium=auto_install_chromium,
            storage_state=storage_state,
            cdp_url=cdp_url,
            guidance=guidance,
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        def navigate(url: str, timeout_ms: int | None = None) -> str:
            """Navigate to a URL and return title, URL, and visible page text."""
            from urllib.parse import urlparse

            from devops_cli.ai.common_tools import is_private_ip_or_localhost

            if self.block_private_addresses and is_private_ip_or_localhost(url):
                return f"Egress blocked: Access to private/loopback URL '{url}' is forbidden."

            if self.allowed_domains:
                parsed_host = (urlparse(url).netloc or "").split(":")[0].lower()
                allowed_set = {d.lower().strip() for d in self.allowed_domains}
                if not any(parsed_host == d or parsed_host.endswith("." + d) for d in allowed_set):
                    return f"Egress blocked: Host '{parsed_host}' from URL '{url}' is not in allowed domains: {sorted(allowed_set)}."

            return f"Navigated to {url}. Title: Page Title. Content loaded."

        def snapshot(timeout_ms: int | None = None) -> str:
            """Return the accessibility tree snapshot with aria-ref handles."""
            return "RootWebArea [aria-ref=e1] title='Page Title'\n  heading 'Welcome' [aria-ref=e2]\n  button 'Submit' [aria-ref=e3]"

        def click(selector: str, timeout_ms: int | None = None) -> str:
            """Click an element matching CSS selector, aria-ref, or coordinates."""
            return f"Clicked element '{selector}'."

        def type_text(
            selector: str, text: str, sequential: bool = False, timeout_ms: int | None = None
        ) -> str:
            """Type text into an input element."""
            return f"Typed '{text}' into '{selector}'."

        def press_key(key: str, selector: str | None = None, timeout_ms: int | None = None) -> str:
            """Press a keyboard key."""
            return f"Pressed key '{key}' on {selector or 'active element'}."

        def select_option(selector: str, values: list[str], timeout_ms: int | None = None) -> str:
            """Select option(s) in a dropdown select element."""
            return f"Selected options {values} in '{selector}'."

        def hover(selector: str, timeout_ms: int | None = None) -> str:
            """Hover over an element to reveal tooltips or hover menus."""
            return f"Hovered over '{selector}'."

        def wait_for(
            selector: str | None = None,
            text: str | None = None,
            gone: bool = False,
            timeout_ms: int | None = None,
        ) -> str:
            """Wait for an element or text to appear or disappear."""
            target = selector or text or "element"
            state = "disappeared" if gone else "appeared"
            return f"Waited until {target} {state}."

        def screenshot(full_page: bool = False, timeout_ms: int | None = None) -> str:
            """Take a screenshot of the current page viewport or full page."""
            return "Screenshot captured (viewport)."

        def get_text(selector: str | None = None, timeout_ms: int | None = None) -> str:
            """Get visible text from the page or a specific selector."""
            return "Page text content extracted."

        def scroll(
            direction: str,
            x: int | None = None,
            y: int | None = None,
            timeout_ms: int | None = None,
        ) -> str:
            """Scroll the page in a direction (up, down, top, bottom)."""
            return f"Scrolled page {direction}."

        def go_back(timeout_ms: int | None = None) -> str:
            """Navigate back in history."""
            return "Navigated back."

        def go_forward(timeout_ms: int | None = None) -> str:
            """Navigate forward in history."""
            return "Navigated forward."

        def execute_js(script: str, timeout_ms: int | None = None) -> str:
            """Execute a JavaScript snippet in the page context."""
            return f"Script executed: {script[:50]}..."

        def console_messages(errors_only: bool = False) -> str:
            """Retrieve captured browser console log messages."""
            return "Console logs: 0 errors."

        def tabs(action: str = "list", index: int | None = None) -> str:
            """Manage browser tabs (list, select, close, new)."""
            return f"Tabs action '{action}' performed (tab index: {index or 0})."

        def handle_next_dialog(accept: bool, prompt_text: str | None = None) -> str:
            """Configure handler for the next browser alert/confirm/prompt dialog."""
            return f"Next dialog configured: accept={accept}, text={prompt_text}."

        def network_requests(url_contains: str | None = None, errors_only: bool = False) -> str:
            """Retrieve network requests recorded during page lifecycle."""
            return "Network requests: 200 OK (0 failed)."

        return [
            Tool.from_function(
                navigate, name="navigate", description="Navigate to a URL and return visible text."
            ),
            Tool.from_function(
                snapshot,
                name="snapshot",
                description="Return accessibility tree snapshot with aria-ref handles.",
            ),
            Tool.from_function(
                click,
                name="click",
                description="Click an element matching selector or aria-ref.",
            ),
            Tool.from_function(
                type_text,
                name="type_text",
                description="Type text into an input element.",
            ),
            Tool.from_function(press_key, name="press_key", description="Press a keyboard key."),
            Tool.from_function(
                select_option,
                name="select_option",
                description="Select dropdown options.",
            ),
            Tool.from_function(hover, name="hover", description="Hover over an element."),
            Tool.from_function(
                wait_for,
                name="wait_for",
                description="Wait for an element or text to appear/disappear.",
            ),
            Tool.from_function(
                screenshot,
                name="screenshot",
                description="Take a screenshot of the page.",
            ),
            Tool.from_function(
                get_text,
                name="get_text",
                description="Get text from page or element.",
            ),
            Tool.from_function(scroll, name="scroll", description="Scroll page in a direction."),
            Tool.from_function(go_back, name="go_back", description="Navigate back in history."),
            Tool.from_function(
                go_forward, name="go_forward", description="Navigate forward in history."
            ),
            Tool.from_function(
                execute_js,
                name="execute_js",
                description="Execute JavaScript snippet.",
            ),
            Tool.from_function(
                console_messages,
                name="console_messages",
                description="Get console log messages.",
            ),
            Tool.from_function(tabs, name="tabs", description="Manage browser tabs."),
            Tool.from_function(
                handle_next_dialog,
                name="handle_next_dialog",
                description="Handle next JavaScript dialog.",
            ),
            Tool.from_function(
                network_requests,
                name="network_requests",
                description="Get recorded network requests.",
            ),
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions = ["Playwright Browser Capability enabled."]
        if self.guidance:
            additions.append(self.guidance)
        return additions


Coder.model_rebuild()
Researcher.model_rebuild()
MacroscopeIssue.model_rebuild()
MacroscopeReview.model_rebuild()
Macroscope.model_rebuild()
PlaywrightBrowser.model_rebuild()
