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

A plan text can also say that a call site runs no named check (#3416). The scan of the plan texts
finds each such claim, and the search reads the body of the call site and the body of each function
that it calls in the same file. It then reads the source files of the staging commit. A check that
it finds is a false premise with its path and line, and the stage job returns the item to New with
it. The search is deterministic and spends the commands that the probe of the item has left.

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

import ast
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
# A backticked span of a plan text: the code that a claim names (#3416).
_SPAN: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")
# A line of a plan that says a call site runs no named check (#3416): an absence word, then the
# word check or guard, with the code span of the named check on either side of that word.
_ABSENT_CHECK: Final[re.Pattern[str]] = re.compile(
    r"\b(?:no|not|never|none|without|lacks?|missing|absent)\b"
    r"[^`\n]*?"
    r"(?:`(?P<before>[^`\s]+)`\s+)?"
    r"(?:checks?|guards?)\b"
    r"(?:\s+`(?P<after>[^`\s]+)`)?",
    re.IGNORECASE,
)
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
    the bound left out, the number of git commands it ran, the cited fields that the body says are
    absent while the staging commit defines them, and the commands that it has left."""

    lines: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    commands: int = 0
    false_premises: tuple[str, ...] = ()
    left: int = CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS

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
    identifiers: tuple[str, ...] = ()
    _tree: StagedTree | None = None
    _surfaces: dict[str, tuple[str, dict[str, int]] | None] = field(default_factory=dict)
    _test_modules: dict[str, list[str]] | None = None

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

    def test_modules(self) -> dict[str, list[str]] | None:
        """The test modules that name each cited identifier, or None when no command is left.
        A run with no cited identifier spends no command. The command runs once for the run."""
        if self._test_modules is not None:
            return self._test_modules
        if not self.identifiers:
            self._test_modules = {}
            return self._test_modules
        if self.left < 1:
            return None
        args = ["grep", "-n", "-w", "-F"]
        for name in self.identifiers:
            args.extend(["-e", name])
        args.extend([self.sha, "--", "tests/"])
        code, out = self.git(self.source, *args)
        if code != 0:
            self._test_modules = {name: [] for name in self.identifiers}
            return self._test_modules
        modules: dict[str, set[str]] = {name: set() for name in self.identifiers}
        for line in out.splitlines():
            line_clean = line.removeprefix(f"{self.sha}:")
            parts = line_clean.split(":", 2)
            if len(parts) >= 3:
                path, _, content = parts
                for name in self.identifiers:
                    if re.search(rf"\b{re.escape(name)}\b", content):
                        modules[name].add(path)
        self._test_modules = {name: sorted(modules[name]) for name in self.identifiers}
        return self._test_modules

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
            modules = self.test_modules()
            if modules is None:
                self.lines.append(texts.stage_probe_test_modules_bound)
            elif modules.get(name):
                paths = ", ".join(f"`{path}`" for path in modules[name])
                self.lines.append(texts.stage_probe_test_modules.format(name=name, modules=paths))
            else:
                self.lines.append(texts.stage_probe_test_modules_none.format(name=name))
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


def _line_claims(line: str) -> tuple[tuple[str, str], ...]:
    """Each call site and named check that `line` says the call site runs without (#3416). The
    call site is the other code-spanned identifier of the line, so a line that names no call site
    adds no pair."""
    spans = [span for span in _SPAN.findall(line) if span.isidentifier()]
    claims: list[tuple[str, str]] = []
    for match in _ABSENT_CHECK.finditer(line):
        name = match.group("before") or match.group("after")
        if name is None:
            continue
        site = next((span for span in spans if span != name), None)
        if site is not None:
            claims.append((site, name))
    return tuple(claims)


def _functions(tree: ast.Module) -> dict[str, tuple[int, int]]:
    """The first and the last line of each function of the parsed module `tree`, by name."""
    spans: dict[str, tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.setdefault(node.name, (node.lineno, node.end_lineno or node.lineno))
    return spans


def _callees(tree: ast.Module, span: tuple[int, int]) -> tuple[tuple[str, int], ...]:
    """The name and the line of each call in the body at `span` of the parsed module `tree`, in the
    order of the text, each name once."""
    first, last = span
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not first <= node.lineno <= last:
            continue
        match node.func:
            case ast.Name(id=name):
                found.setdefault(name, node.lineno)
            case ast.Attribute(attr=name):
                found.setdefault(name, node.lineno)
    return tuple(sorted(found.items(), key=lambda call: call[1]))


def _claim_line(content: str, site: str, name: str) -> int | None:
    """The line of the call to `name` in the body of `site` of the Python source `content`, or in
    the body of a function that the body of `site` calls in that source, or None."""
    try:
        tree = ast.parse(content)
    except SyntaxError, ValueError:
        return None
    spans = _functions(tree)
    span = spans.get(site)
    if span is None:
        return None
    calls = _callees(tree, span)
    if (line := next((at for callee, at in calls if callee == name), None)) is not None:
        return line
    for callee, _ in calls:
        body = spans.get(callee)
        if body is None:
            continue
        line = next((at for called, at in _callees(tree, body) if called == name), None)
        if line is not None:
            return line
    return None


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
    identifiers = tuple(cited_identifiers(body))
    run.identifiers = identifiers
    items = [
        *(("path", p) for p in paths),
        *(("field", f) for f in fields),
        *(("identifier", i) for i in identifiers),
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
        lines=tuple(run.lines),
        missing=tuple(run.missing),
        skipped=tuple(run.skipped),
        commands=commands,
        false_premises=tuple(run.false_premises),
        left=run.left,
    )


def claimed_missing_checks(texts: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """Each call site and named check that a line of `texts` says the call site runs without, in the
    order of the texts, each pair once (#3416). A line says so when an absence word comes before the
    word check or guard and a code span names the check on either side of that word; the other
    code-spanned identifier of the line is the call site. A line that names no call site, or no
    check, adds no pair."""
    claims: list[tuple[str, str]] = []
    for text in texts:
        for line in text.splitlines():
            claims.extend(_line_claims(line))
    return tuple(dict.fromkeys(claims))


def _called_where(run: _Run, site: str, name: str) -> str | None:
    """The path and the line of the call to `name` in the body of `site` at the staging commit, or
    in the body of a function that `site` calls in its file, else in the source files of the commit.
    None when the search does not finish or the commit holds no such call."""
    found = definition_lines(run.source, run.sha, site, run.git, commands=run.left)
    if found is None:
        return None
    if found and run.left >= 1:
        path = found[0].removeprefix(f"{run.sha}:").split(":", 1)[0]
        code, content = run.git(run.source, "cat-file", "-p", f"{run.sha}:{path}")
        if code == 0 and (line := _claim_line(content, site, name)) is not None:
            return f"{path}:{line}"
    return _tree_where(run, name)


def _tree_where(run: _Run, name: str) -> str | None:
    """The path and the line of the first line of the staging commit that names `name` as a whole
    word, or None when no command is left or the commit names it nowhere."""
    if run.left < 1:
        return None
    code, out = run.git(
        run.source, "grep", "-n", "-F", "-w", "-e", name, run.sha, "--", *SYMBOL_PATHSPECS
    )
    if code != 0 or not out:
        return None
    path, number, _ = out.splitlines()[0].removeprefix(f"{run.sha}:").split(":", 2)
    return f"{path}:{number}"


def check_claims(source: Path, sha: str, claims: Iterable[tuple[str, str]], left: int) -> Probe:
    """Search commit `sha` of the checkout `source` for each check that a plan text says a call site
    runs without (#3416). The search reads the body of the call site and the body of each function
    that it calls in the same file, then the source files of the commit, with the `left` commands
    that the probe of the item has left. A found check is a false premise that names the path and
    the line of its call. A claim with no command left is listed as skipped, and a search that does
    not finish adds no line."""
    run = _Run(source, sha, left)
    for site, name in claims:
        if run.left < 1:
            run.skipped.append(name)
            continue
        where = _called_where(run, site, name)
        if where is not None:
            run.false_premises.append(
                MESSAGES.roadmap.stage_probe_claim_found.format(site=site, name=name, where=where)
            )
    return Probe(
        skipped=tuple(run.skipped),
        commands=left - run.left,
        false_premises=tuple(run.false_premises),
        left=run.left,
    )


__all__ = ["Probe", "check_claims", "claimed_missing_checks", "probe_premise"]


def blocked_by(missing: Iterable[str], creators: Mapping[str, int]) -> tuple[int, ...]:
    """The open items that create a cited path which the staging commit lacks, sorted, with no
    number twice. `creators` maps each path that an open item's plan creates to the number of that
    item (#3418). A path that the commit holds is no dependency, so it is no entry of `missing`."""
    return tuple(sorted({creators[path] for path in missing if path in creators}))
