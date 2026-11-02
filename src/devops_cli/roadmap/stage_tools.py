"""The read-only toolbox of the stage planner (#3037).

The planner of the stage job is an agent that reads the repository before it writes a plan. It has
nine tools: `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`,
`callers`, `repo_map` and `read_spec`. The first three are the tools of refine's investigation.
The others read the staged commit with git, or read the checkout through tree-sitter. No tool
writes a file, runs a shell command or opens a network connection.

A tool answers each failure as text, so no argument that the model sends can stop the run. A tool
runs only `git` with a fixed list of arguments, and a `--` before every path. `file_symbols` and
`repo_map` read the files of the checkout, which the job holds at the staged commit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic_ai import Tool

from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.ai.repomap import generate_repo_map, render_repo_map_text
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_LOG_MAX_COUNT,
    CONST_ROADMAP_STAGE_MAP_MAX_FILES,
    CONST_ROADMAP_STAGE_SPEC_MAX_CHARS,
)
from devops_cli.roadmap.refine_investigation import (
    InvestigationTools,
    cut,
    repository_path,
)

_COMMIT: Final[re.Pattern[str]] = re.compile(r"[0-9a-fA-F]{7,40}")
_SYMBOL: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAPABILITY: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_REQUIREMENT_HEADING: Final[str] = "### Requirement:"
_SPECS: Final[str] = "openspec/specs"


def _outside(text: str) -> str:
    return f"The path {text} is outside the repository."


@dataclass
class StageTools(InvestigationTools):
    """The nine read-only tools of one plan run, on commit `sha` of the checkout at `source`.

    It extends refine's tools and leaves out `search_web`: the toolbox opens no network
    connection.
    """

    def git_log(self, path: str = "") -> str:
        """List the newest commits that changed a path, or any path when none is given.

        Args:
            path: The repository path of a file or a directory. An empty text is the whole tree.
        """
        clean = repository_path(path)
        if clean is None:
            return _outside(path)
        _, out = self._git(
            "log",
            f"--max-count={CONST_ROADMAP_STAGE_LOG_MAX_COUNT}",
            "--format=%h %as %s",
            self.sha,
            "--",
            *([clean] if clean else []),
        )
        lines = out.decode("utf-8", errors="replace").splitlines()
        return cut(lines) if lines else f"No commit changed {clean or 'the tree'}."

    def git_show(self, commit: str, path: str = "") -> str:
        """Show one commit of the history: its message and its diff.

        Args:
            commit: The hash of the commit, from `git_log`. A name such as a branch is refused.
            path: The repository path to limit the diff to. An empty text shows the whole diff.
        """
        name = commit.strip()
        if not _COMMIT.fullmatch(name):
            return f"The argument {commit} is no commit hash."
        clean = repository_path(path)
        if clean is None:
            return _outside(path)
        code, _ = self._git("merge-base", "--is-ancestor", name, self.sha)
        if code != 0:
            return f"The commit {name} is not in the history of the staged commit."
        _, out = self._git(
            "show",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--stat",
            "--patch",
            "--format=%h %as %s%n",
            name,
            "--",
            *([clean] if clean else []),
        )
        return cut(out.decode("utf-8", errors="replace").splitlines())

    def callers(self, symbol: str) -> str:
        """List the places that call a function, a method or a class: each name followed by `(`.

        Args:
            symbol: The name of the symbol, such as `plan_item`.

        Returns:
            One line for each match, as `path:line:content`.
        """
        if not _SYMBOL.fullmatch(symbol):
            return f"The text {symbol} is no symbol name."
        pattern = rf"(^|[^A-Za-z0-9_]){symbol}\("
        code, out = self._git("grep", "-n", "-I", "-E", "-e", pattern, self.sha, "--")
        decoded = out.decode("utf-8", errors="replace").splitlines()
        lines = [line.removeprefix(f"{self.sha}:") for line in decoded]
        return cut(lines) if code == 0 and lines else f"No call of {symbol}."

    def _checkout_path(self, path: str) -> tuple[Path | None, str]:
        """The resolved path of a file or directory of the checkout, and the answer when it is
        none. A path outside the repository, and a link that leaves it, give no path."""
        clean = repository_path(path)
        if clean is None:
            return None, _outside(path)
        root = self.source.resolve()
        try:
            resolved = (root / clean).resolve()
        except OSError, ValueError:
            return None, f"The text {path!r} is no path."
        if not resolved.is_relative_to(root):
            return None, _outside(path)
        return resolved, clean

    def file_symbols(self, path: str) -> str:
        """List the classes, functions and methods of one source file, with their lines.

        Args:
            path: The repository path of the file, such as `src/app.py`.

        Returns:
            One line for each symbol, as `line: signature`.
        """
        resolved, clean = self._checkout_path(path)
        if resolved is None:
            return clean
        if not clean or not resolved.is_file():
            return f"The checkout holds no file {clean}."
        parsed = TreeSitterEngine().parse_file(resolved)
        if parsed is None or not parsed.symbols:
            return f"The file {clean} has no symbols to read."
        lines = [
            f"{symbol.span.line_start}: {symbol.signature or symbol.name}"
            for symbol in parsed.symbols
        ]
        return cut(lines)

    def repo_map(self, directory: str = "") -> str:
        """Map the symbols of the source files under one directory.

        Args:
            directory: The repository path of the directory. An empty text is the top.
        """
        resolved, clean = self._checkout_path(directory)
        if resolved is None:
            return clean
        if not resolved.is_dir():
            return f"The checkout holds no directory {clean}."
        nodes = generate_repo_map(
            resolved, max_files=CONST_ROADMAP_STAGE_MAP_MAX_FILES, include_tests=True
        )
        if not nodes:
            return f"No source file under {clean or 'the top'} has symbols."
        placed = [
            node.model_copy(update={"path": f"{clean}/{node.path}" if clean else node.path})
            for node in nodes
        ]
        return cut(render_repo_map_text(placed).splitlines())

    def read_spec(self, capability: str = "", requirement: str = "") -> str:
        """Read a base spec of the project. Without a capability, list the capabilities. With one,
        list its requirement names. With a requirement name too, return the whole requirement.

        Args:
            capability: The name of the capability, such as `roadmap-stage`.
            requirement: The name of one requirement of the capability.
        """
        if not capability:
            _, out = self._git("ls-tree", "--name-only", self.sha, f"{_SPECS}/")
            names = [Path(line).name for line in out.decode("utf-8", errors="replace").splitlines()]
            return cut(names) or "The commit holds no spec."
        if not _CAPABILITY.fullmatch(capability):
            return f"The text {capability} is no capability name."
        code, out = self._git("show", f"{self.sha}:{_SPECS}/{capability}/spec.md")
        if code != 0:
            return f"The commit holds no spec {capability}."
        lines = out.decode("utf-8", errors="replace").splitlines()
        names = [
            line.removeprefix(_REQUIREMENT_HEADING).strip()
            for line in lines
            if line.startswith(_REQUIREMENT_HEADING)
        ]
        if not requirement:
            return cut(names) or f"The spec {capability} holds no requirement."
        return _requirement_text(lines, capability, requirement.strip())

    def tools(self) -> list[Tool[None]]:
        """The nine tools of the toolbox, and no other."""
        return [
            Tool(method, takes_ctx=False)
            for method in (
                self.list_files,
                self.read_file,
                self.search_code,
                self.git_log,
                self.git_show,
                self.file_symbols,
                self.callers,
                self.repo_map,
                self.read_spec,
            )
        ]


def _requirement_text(lines: list[str], capability: str, name: str) -> str:
    """The lines of the requirement `name`, from its heading to the next requirement or section."""
    heading = f"{_REQUIREMENT_HEADING} {name}"
    start = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        return f"The spec {capability} holds no requirement {name}."
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith(_REQUIREMENT_HEADING) or lines[i].startswith("## ")
        ),
        len(lines),
    )
    kept = lines[start:end]
    while kept and not kept[-1].strip():
        kept.pop()
    return cut(kept, max_chars=CONST_ROADMAP_STAGE_SPEC_MAX_CHARS)


__all__ = ["StageTools"]
