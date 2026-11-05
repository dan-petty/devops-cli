"""The premise probe of the stage job (#3011).

An issue can rest on a premise that is already false: it cites a path that a commit deleted, or a
function that no code defines. `collect_context` shows the model what exists, and shows nothing for
a thing that is gone. This probe asks the staging commit about each path and identifier that the
issue cites, with the extraction of `collect_context`, and writes one line for each answer. The
model reads the lines before it plans, and a plan quotes them in `feasibility`.

For a path the probe asks whether the commit holds it and, for a missing one, which commit deleted
or renamed it. For an identifier it asks for a definition and, for an identifier with none, which
commit last added or removed its text. A missing thing with no such commit may be a thing that the
issue asks to create: the line says that no commit held it.

The probe runs at most `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` commands for one item. Every
command is `git cat-file`, `git grep`, `git log` or `git ls-tree` at the staging commit, with a
`--` before every path, so the probe changes nothing. A cited path that exists at the root gets one
line. For a bare name with no root file, the probe reads the tree once and names the files under a
folder that have the same name, so the model reads a file that exists. It lists the items that the
bound left out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_PROBE_DEFINITION_LINES,
    CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.premise import definition_lines
from devops_cli.roadmap.refine import (
    SYMBOL_PATHSPEC,
    cited_identifiers,
    cited_paths,
    git_result,
)
from devops_cli.roadmap.stage_paths import StagedTree

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

_LOG_FORMAT: Final[str] = "--format=%h %as %s"


@dataclass(frozen=True)
class Probe:
    """What the probe found: the lines for the model, the cited items that are missing, the items
    the bound left out, and the number of git commands it ran."""

    lines: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    commands: int = 0

    @property
    def text(self) -> str:
        """The lines, then the items not probed, or an empty text when the issue cites nothing."""
        lines = list(self.lines)
        if self.skipped:
            lines.append(
                MESSAGES.roadmap.stage_probe_skipped.format(
                    bound=CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS,
                    items=", ".join(f"`{name}`" for name in self.skipped),
                )
            )
        return "\n".join(lines)


@dataclass
class _Run:
    """The state of one probe: its checkout and commit, and the commands it has left."""

    source: Path
    sha: str
    left: int = CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS
    lines: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    _tree: StagedTree | None = None

    def git(self, source: Path, *args: str) -> tuple[int, str]:
        """Run one command of the budget in `source`, which is the checkout of the run."""
        self.left -= 1
        return git_result(source, *args)

    def same_name(self, name: str) -> list[str]:
        """The files of the staging commit with the name of `name`, sorted and at most
        `SAME_NAME_MAX`; an empty list when no command is left to read the tree. The tree is read
        once for the run, on the first missing cited path."""
        if self._tree is None:
            if self.left < 1:
                return []
            code, out = self.git(self.source, "ls-tree", "-r", "-z", "--name-only", self.sha)
            self._tree = (
                StagedTree(path for path in out.split("\0") if path)
                if code == 0
                else StagedTree(())
            )
        return self._tree.same_name(name)

    def newest_commit(self, *args: str) -> str:
        """The newest commit that `git log` finds with `args` at the staging commit, as `hash
        date subject`, or an empty text when it finds none (the command costs one of the budget)."""
        code, out = self.git(self.source, "log", "-n1", _LOG_FORMAT, *args)
        return out.strip() if code == 0 else ""

    def path(self, name: str) -> None:
        texts = MESSAGES.roadmap
        code, _ = self.git(self.source, "cat-file", "-e", f"{self.sha}:{name}")
        if code == 0:
            self.lines.append(texts.stage_probe_path_present.format(path=name))
            return
        self.missing.append(name)
        same = self.same_name(name)
        if same:
            candidates = ", ".join(f"`{path}`" for path in same)
            removal = self._removal(name) if self.left >= 1 else ""
            self.lines.append(
                texts.stage_probe_path_missing_root.format(
                    path=name, candidates=candidates, removal=removal
                ).rstrip()
            )
            return
        if self.left < 1:
            self.lines.append(texts.stage_probe_path_missing.format(path=name, removal="").rstrip())
            return
        removal = self._removal(name)
        self.lines.append(texts.stage_probe_path_missing.format(path=name, removal=removal))

    def _removal(self, name: str) -> str:
        """The sentence on the commit that deleted or renamed `name`, or that no commit did."""
        texts = MESSAGES.roadmap
        commit = self.newest_commit("--diff-filter=DR", self.sha, "--", name)
        return (
            texts.stage_probe_removed.format(commit=commit)
            if commit
            else texts.stage_probe_path_never
        )

    def identifier(self, name: str) -> None:
        texts = MESSAGES.roadmap
        hits = definition_lines(self.source, self.sha, name, self.git)[
            :CONST_ROADMAP_STAGE_PROBE_DEFINITION_LINES
        ]
        if hits:
            for hit in hits:
                where = hit.removeprefix(f"{self.sha}:").strip()
                self.lines.append(texts.stage_probe_defined.format(name=name, where=where))
            return
        self.missing.append(name)
        if self.left < 1:
            self.lines.append(texts.stage_probe_undefined.format(name=name, removal="").rstrip())
            return
        commit = self.newest_commit(f"-S{name}", self.sha, "--", SYMBOL_PATHSPEC)
        removal = (
            texts.stage_probe_touched.format(commit=commit)
            if commit
            else texts.stage_probe_name_never
        )
        self.lines.append(texts.stage_probe_undefined.format(name=name, removal=removal))


def _is_probed_path(path: str) -> bool:
    """Whether `path` ends in an extension that starts with a letter, so `0.41` is no path."""
    suffix = PurePosixPath(path).suffix
    return len(suffix) > 1 and suffix[1].isalpha()


def probe_premise(source: Path, sha: str, body: str) -> Probe:
    """Probe each path and identifier that `body` cites at commit `sha` of the checkout `source`.
    The paths come first, then the identifiers, each in the order of the text. An item for which
    no command is left is listed as skipped."""
    run = _Run(source, sha)
    items = [
        *(("path", p) for p in cited_paths(body) if _is_probed_path(p)),
        *(("identifier", i) for i in cited_identifiers(body)),
    ]
    for kind, name in items:
        if run.left < 1:
            run.skipped.append(name)
        elif kind == "path":
            run.path(name)
        else:
            run.identifier(name)
    commands = CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS - run.left
    return Probe(tuple(run.lines), tuple(run.missing), tuple(run.skipped), commands)


__all__ = ["Probe", "probe_premise"]


def blocked_by(missing: Iterable[str], creators: Mapping[str, int]) -> tuple[int, ...]:
    """The open items that create a cited path which the staging commit lacks, sorted, with no
    number twice. `creators` maps each path that an open item's plan creates to the number of that
    item (#3418). A path that the commit holds is no dependency, so it is no entry of `missing`."""
    return tuple(sorted({creators[path] for path in missing if path in creators}))
