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

A cited dotted reference such as `PullStatus.labels` is a class field when the commit defines
`PullStatus` (#3406). The probe reads the class body and writes the file and line of the field, or
says that the class defines no such field. A token whose left part names no class stays a path. When
a line of the body says that a class field is absent and the commit defines it, the probe records
the line as a false premise, and the stage job returns the item to New with it.

The probe runs at most `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` commands for one item. An
identifier that only files of other languages than Python name needs two commands, one to find the
files and one to read them; with one command left, the probe lists it as not probed. Every
command is `git cat-file`, `git grep`, `git log`, `git show` or `git ls-tree` at the staging commit,
with a `--` before every path, so the probe changes nothing. A cited path that exists at the root
gets one line. For a bare name with no root file, the probe reads the tree once and names the files
under a folder that have the same name, so the model reads a file that exists. It lists the items
that the bound left out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_PROBE_DEFINITION_LINES,
    CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.premise import definition_lines
from devops_cli.roadmap.refine.refine import (
    SYMBOL_PATHSPECS,
    cited_identifiers,
    cited_paths,
    git_result,
)
from devops_cli.roadmap.stage.stage_models import parse_class_fields
from devops_cli.roadmap.stage.stage_paths import StagedTree

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from pathlib import Path

_LOG_FORMAT: Final[str] = "--format=%h %as %s"
# The files of a class whose fields the probe reads: Python files (#3406).
_CLASS_PATHSPEC: Final[str] = "*.py"
# A cited class field: one dot between two identifiers, such as `PullStatus.labels`. The class of
# the staging commit decides whether the token is a field or a path (#3406).
_FIELD_REF: Final[re.Pattern[str]] = re.compile(r"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)$")
# The phrases that a line of the body uses to say that a class defines no field (#3406).
_ABSENCE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:defines?\s+no|does\s+not\s+define|do\s+not\s+define|has\s+no|have\s+no|lacks?|"
    r"is\s+absent|are\s+absent)\b",
    re.IGNORECASE,
)
# A backticked span or a bare word of a line of the body.
_TOKEN: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`|([A-Za-z_]\w*)")
# The words between an absence phrase and the field that it names.
_FIELD_WORDS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "and",
        "attribute",
        "attributes",
        "field",
        "fields",
        "it",
        "its",
        "member",
        "members",
        "or",
        "property",
        "properties",
        "such",
        "the",
    }
)


@dataclass(frozen=True)
class Probe:
    """What the probe found: the lines for the model, the cited items that are missing, the items
    the bound left out, the number of git commands it ran, and the cited fields that the body says
    are absent while the staging commit defines them."""

    lines: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    commands: int = 0
    false_premises: tuple[str, ...] = ()

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
    false_premises: list[str] = field(default_factory=list)
    absent: frozenset[tuple[str, str]] = frozenset()
    _tree: StagedTree | None = None
    _surfaces: dict[str, tuple[str, dict[str, int]] | None] = field(default_factory=dict)

    def git(self, source: Path, *args: str) -> tuple[int, str]:
        """Run one command of the budget in `source`, which is the checkout of the run."""
        self.left -= 1
        return git_result(source, *args)

    def _class_source(self, name: str) -> tuple[str, str] | None:
        """The path and the text of the class `name` at the staging commit, with one `git grep`
        and one `git show`, or None when the commit defines no such class."""
        if self.left < 1:
            return None
        code, out = self.git(
            self.source,
            "grep",
            "-n",
            "-E",
            "-e",
            rf"^class {name}([[:space:](:])",
            self.sha,
            "--",
            _CLASS_PATHSPEC,
        )
        if code != 0 or not out:
            return None
        path = out.splitlines()[0].removeprefix(f"{self.sha}:").split(":", 1)[0]
        if self.left < 1:
            return None
        shown, content = self.git(self.source, "show", f"{self.sha}:{path}")
        return (path, content) if shown == 0 else None

    def surface(self, name: str) -> tuple[str, dict[str, int]] | None:
        """The module of the class `name` at the staging commit and the line of each field of its
        body, or None when the commit defines no such class. The class is read once for the run."""
        if name in self._surfaces:
            return self._surfaces[name]
        found: tuple[str, dict[str, int]] | None = None
        source = self._class_source(name)
        if source is not None:
            path, content = source
            fields = parse_class_fields(content).get(name)
            if fields is not None:
                found = (path, fields)
        self._surfaces[name] = found
        return found

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

    def path_or_field(self, name: str) -> None:
        """Probe `name` as a class field when the staging commit defines the class of its left
        part, and as a path otherwise (#3406). A class that no command can confirm stays a path."""
        parts = _FIELD_REF.match(name)
        if parts is not None:
            class_name = parts.group(1)
            if class_name in self._surfaces:
                if self._surfaces[class_name] is not None:
                    self.field(name)
                    return
            elif self.left >= 3 and self.surface(class_name) is not None:
                self.field(name)
                return
        self.path(name)

    def field(self, ref: str) -> None:
        """Probe the class field `ref` at the staging commit and name its file and line, or say
        that the class defines no such field. A field that the body says is absent while the
        commit defines it is a false premise of the item."""
        texts = MESSAGES.roadmap
        class_name, _, field_name = ref.partition(".")
        surface = self.surface(class_name)
        if surface is None:
            # The class of a split absence statement is only a candidate: a line such as "the
            # field `labels` has no default" names no class, and the probe writes no line for it.
            return
        module, fields = surface
        if field_name in fields:
            line = texts.stage_probe_field_defined.format(
                class_=class_name, field=field_name, where=f"{module}:{fields[field_name]}"
            )
            if (class_name, field_name) in self.absent:
                self.false_premises.append(line)
        else:
            self.missing.append(ref)
            line = texts.stage_probe_field_missing.format(
                class_=class_name, field=field_name, module=module
            )
        self.lines.append(line)

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
        found = definition_lines(self.source, self.sha, name, self.git, commands=self.left)
        if found is None:
            self.skipped.append(name)
            return
        hits = found[:CONST_ROADMAP_STAGE_PROBE_DEFINITION_LINES]
        if hits:
            for hit in hits:
                where = hit.removeprefix(f"{self.sha}:").strip()
                self.lines.append(texts.stage_probe_defined.format(name=name, where=where))
            return
        self.missing.append(name)
        if self.left < 1:
            self.lines.append(texts.stage_probe_undefined.format(name=name, removal="").rstrip())
            return
        commit = self.newest_commit(f"-S{name}", self.sha, "--", *SYMBOL_PATHSPECS)
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


def _tokens(segment: str) -> Iterator[str]:
    """Each backticked span or bare word of `segment`, in the order of the text."""
    for match in _TOKEN.finditer(segment):
        yield match.group(1) or match.group(2)


def _absence_pairs(body: str) -> tuple[tuple[str, str], ...]:
    """Each class and field that a line of `body` says is absent, by the class before the phrase
    and the field after it, or by the two parts of a dotted reference."""
    pairs: list[tuple[str, str]] = []
    for line in body.splitlines():
        phrase = _ABSENCE.search(line)
        if phrase is None:
            continue
        before = list(_tokens(line[: phrase.start()]))
        after = list(_tokens(line[phrase.end() :]))
        pair: tuple[str, str] | None = None
        if before:
            dotted = _FIELD_REF.match(before[-1])
            if dotted is not None:
                pair = (dotted.group(1), dotted.group(2))
        if pair is None:
            class_name = next((token for token in reversed(before) if token.isidentifier()), None)
            field_name = next(
                (
                    token
                    for token in after
                    if token.isidentifier() and token.lower() not in _FIELD_WORDS
                ),
                None,
            )
            if class_name is not None and field_name is not None:
                pair = (class_name, field_name)
        if pair is not None and pair[0] != pair[1]:
            pairs.append(pair)
    return tuple(dict.fromkeys(pairs))


def probe_premise(source: Path, sha: str, body: str) -> Probe:
    """Probe each path, class field and identifier that `body` cites at commit `sha` of the
    checkout `source`. The paths come first, then the fields that an absence statement names, then
    the identifiers, each in the order of the text. An item for which no command is left is listed
    as skipped."""
    run = _Run(source, sha)
    absent = _absence_pairs(body)
    run.absent = frozenset(absent)
    paths = [path for path in cited_paths(body) if _is_probed_path(path)]
    fields = [
        f"{class_name}.{field_name}"
        for class_name, field_name in absent
        if f"{class_name}.{field_name}" not in paths
    ]
    items = [
        *(("path", p) for p in paths),
        *(("field", f) for f in fields),
        *(("identifier", i) for i in cited_identifiers(body)),
    ]
    for kind, name in items:
        if run.left < 1:
            run.skipped.append(name)
        elif kind == "path":
            run.path_or_field(name)
        elif kind == "field":
            run.field(name)
        else:
            run.identifier(name)
    commands = CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS - run.left
    return Probe(
        tuple(run.lines),
        tuple(run.missing),
        tuple(run.skipped),
        commands,
        tuple(run.false_premises),
    )


__all__ = ["Probe", "probe_premise"]


def blocked_by(missing: Iterable[str], creators: Mapping[str, int]) -> tuple[int, ...]:
    """The open items that create a cited path which the staging commit lacks, sorted, with no
    number twice. `creators` maps each path that an open item's plan creates to the number of that
    item (#3418). A path that the commit holds is no dependency, so it is no entry of `missing`."""
    return tuple(sorted({creators[path] for path in missing if path in creators}))
