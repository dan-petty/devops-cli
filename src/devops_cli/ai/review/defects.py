"""Synthetic defect corpora: known defects injected into clean files, to measure review recall.

A real repository cannot tell a reviewer's hits from its misses. Every finding is labelled by
another judgement, usually the verifier being measured. A corpus made by injecting one known
defect per file, at a recorded location, gives a recall that is measured rather than inferred:
the share of injections reported where they were made.

The numbers measure regression, not capability. An injection the generator knows how to make is
one a prompt can be tuned to find, and a reviewer tuned against this corpus gets good at these
defects. Every score carries that caveat.

A corpus directory holds the mutated files under `files/`, the manifest of injections beside it
(outside the reviewed tree, so the reviewer cannot read the answers) and a copy of the source
project's conventions file, so the review sees the same conventions as a review of the source.
"""

from __future__ import annotations

import ast
import builtins
import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from devops_cli.ai.review_schema import LINE_OVERLAP_TOLERANCE, SavedFinding, _parse_location
from devops_cli.config.constants import REVIEW_GENERIC_SYMBOL_STOPWORDS

CORPUS_MANIFEST = "manifest.json"
CORPUS_FILES_DIR = "files"
CORPUS_CONVENTIONS_FILE = "AGENTS.md"
SYNTHETIC_CAVEAT = (
    "Synthetic recall measures regression against defects this generator knows how to inject, "
    "not review capability: a reviewer tuned against the corpus gets good at these defects."
)

# Without a conventions file of its own, a corpus inside another repository would be reviewed
# under that repository's conventions.
_NO_CONVENTIONS = "# Project Conventions\n\nNo conventions file was found for the source files.\n"
# A dropped guard leaves no line behind; a report counts from the enclosing function's start to
# this many lines past where the guard stood.
_GUARD_REACH_LINES = 10
_CONTAINMENT_CALLS = frozenset({"is_relative_to", "is_safe_subpath", "commonpath", "commonprefix"})

# Values too common to identify a defect alone; the key they are set on is named instead.
_GENERIC_TOKENS = frozenset({"true", "false", "yes", "no", "none", "null", "main", "master"})
_BUILTIN_NAMES = frozenset(dir(builtins))

Lines = list[str]


def _numeric_variants(token: str) -> list[str]:
    """A file mode is reported as 0o777, 0777 or 777."""
    digits = token.lower().removeprefix("0o").lstrip("0")
    return [token, digits] if digits.isdigit() and digits != token else [token]


def _changed_evidence(original: str, mutated: str) -> tuple[str, ...]:
    """Tokens only the mutated line has; a generic value is named by the key before it."""
    before = set(re.findall(r"\w+", original))
    tokens = re.findall(r"\w+", mutated)
    evidence: list[str] = []
    for index, token in enumerate(tokens):
        if token in before:
            continue
        if token.lower() not in _GENERIC_TOKENS:
            evidence.extend(_numeric_variants(token))
        elif index:
            evidence.append(tokens[index - 1])
    return tuple(dict.fromkeys(evidence))


def _distinctive(name: str) -> bool:
    """A name specific enough that a finding naming it is about this code."""
    return (
        (len(name) >= 5 or "_" in name)
        and name not in _BUILTIN_NAMES
        and name.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS
    )


def _names_in(expression: ast.expr) -> tuple[str, ...]:
    """The distinctive names an expression uses: its variables, attributes and calls."""
    names = [
        node.attr if isinstance(node, ast.Attribute) else node.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Attribute | ast.Name)
    ]
    return tuple(dict.fromkeys(n for n in names if _distinctive(n)))


@dataclass(frozen=True)
class Site:
    """One place a template can inject its defect: lines [start, end) become `replacement`."""

    start: int
    end: int
    replacement: tuple[str, ...]
    # 1-based lines of the mutated file where a report of the defect counts.
    region: tuple[int, int]
    # Tokens a report of the defect would name, for reports whose line numbers are off.
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class DefectTemplate:
    """A kind of defect, and how to find the places it can be injected."""

    name: str
    description: str
    severity: str
    suffixes: tuple[str, ...]
    find: Callable[[Lines], list[Site]]

    def applies_to(self, path: str) -> bool:
        return path.lower().endswith(self.suffixes)


def _substitute(
    *rules: tuple[str, str | Callable[[re.Match[str]], str]],
) -> Callable[[Lines], list[Site]]:
    """Find lines a rule changes; the defect is the changed line itself."""
    compiled = [(re.compile(pattern), replacement) for pattern, replacement in rules]

    def find(lines: Lines) -> list[Site]:
        sites: list[Site] = []
        for index, line in enumerate(lines):
            for regex, replacement in compiled:
                mutated = regex.sub(replacement, line, count=1)
                if mutated != line:
                    region = (index + 1, index + 1)
                    evidence = _changed_evidence(line, mutated)
                    sites.append(Site(index, index + 1, (mutated,), region, evidence))
                    break
        return sites

    return find


def _python_tree(lines: Lines) -> ast.Module | None:
    try:
        return ast.parse("".join(lines))
    except SyntaxError, ValueError:
        return None


def _parses(lines: Lines) -> bool:
    return _python_tree(lines) is not None


def _orders_values(test: ast.expr) -> bool:
    ordering = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
    return any(
        isinstance(node, ast.Compare) and any(isinstance(op, ordering) for op in node.ops)
        for node in ast.walk(test)
    )


def _checks_containment(test: ast.expr) -> bool:
    names = {
        node.attr if isinstance(node, ast.Attribute) else node.id
        for node in ast.walk(test)
        if isinstance(node, ast.Attribute | ast.Name)
    }
    return bool(names & _CONTAINMENT_CALLS)


def _is_guard(node: ast.AST, lines: Lines, test_matches: Callable[[ast.expr], bool]) -> bool:
    """An `if <test>: raise ...` statement of its own, with no else branch."""
    return (
        isinstance(node, ast.If)
        and not node.orelse
        and all(isinstance(statement, ast.Raise) for statement in node.body)
        and lines[node.lineno - 1].lstrip().startswith("if ")
        and test_matches(node.test)
    )


def _guard_region(tree: ast.Module, guard: ast.If, removed: int) -> tuple[int, int]:
    """Where a report of a dropped guard counts, in the mutated file's line numbers."""
    owners = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.lineno <= guard.lineno
        and (node.end_lineno or node.lineno) >= (guard.end_lineno or guard.lineno)
    ]
    if not owners:
        return guard.lineno, guard.lineno + _GUARD_REACH_LINES
    owner = max(owners, key=lambda node: node.lineno)
    owner_end = (owner.end_lineno or owner.lineno) - removed
    return owner.lineno, min(owner_end, guard.lineno + _GUARD_REACH_LINES)


def _drop_guards(test_matches: Callable[[ast.expr], bool]) -> Callable[[Lines], list[Site]]:
    """Find guards whose removal leaves valid Python; the defect is the missing check."""

    def find(lines: Lines) -> list[Site]:
        tree = _python_tree(lines)
        if tree is None:
            return []
        sites: list[Site] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If) or not _is_guard(node, lines, test_matches):
                continue
            start, end = node.lineno - 1, node.end_lineno or node.lineno
            if not _parses([*lines[:start], *lines[end:]]):
                continue
            region = _guard_region(tree, node, end - start)
            sites.append(Site(start, end, (), region, _names_in(node.test)))
        return sites

    return find


def _drop_awaits(lines: Lines) -> list[Site]:
    """Find `await` expressions; without the await, the coroutine is created and never run."""
    tree = _python_tree(lines)
    if tree is None:
        return []
    sites: list[Site] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Await):
            continue
        line = lines[node.lineno - 1]
        # ast column offsets count UTF-8 bytes.
        column = len(line.encode()[: node.col_offset].decode(errors="ignore"))
        if line[column : column + 6] == "await ":
            mutated = line[:column] + line[column + 6 :]
            # The awaited call, dotted and bare; a module name alone would match any finding
            # about the module.
            callee = node.value.func if isinstance(node.value, ast.Call) else node.value
            name = callee.attr if isinstance(callee, ast.Attribute) else ast.unparse(callee)
            evidence = tuple(
                dict.fromkeys(t for t in (ast.unparse(callee), name) if _distinctive(t))
            )
            sites.append(
                Site(node.lineno - 1, node.lineno, (mutated,), (node.lineno,) * 2, evidence)
            )
    return sites


def _widen_mode(match: re.Match[str]) -> str:
    owner = match.group(2)
    return f"{match.group(1)}{owner * 3}"


_IMAGE = r"[\w.-]+(?::\d+)?(?:/[\w.-]+)*"
_PINNED = r"(?::(?!latest\b)\w[\w.-]*|@sha256:[0-9a-f]{64})"

TEMPLATES: tuple[DefectTemplate, ...] = (
    DefectTemplate(
        "drop-bounds-check",
        "Removed a guard that rejects out-of-range values.",
        "HIGH",
        (".py",),
        _drop_guards(_orders_values),
    ),
    DefectTemplate(
        "drop-path-containment",
        "Removed a guard that keeps a path inside its base directory.",
        "HIGH",
        (".py",),
        _drop_guards(_checks_containment),
    ),
    DefectTemplate(
        "drop-await",
        "Removed an await, so the coroutine is created and never run.",
        "HIGH",
        (".py",),
        _drop_awaits,
    ),
    DefectTemplate(
        "unpin-image-tag",
        "Replaced a pinned image tag or digest with latest.",
        "MEDIUM",
        (".yaml", ".yml", "dockerfile", "containerfile"),
        _substitute(
            (rf"^(\s*-?\s*image:\s*[\"']?)({_IMAGE}){_PINNED}", r"\g<1>\g<2>:latest"),
            (rf"^(FROM\s+(?:--platform=\S+\s+)?)({_IMAGE}){_PINNED}", r"\g<1>\g<2>:latest"),
        ),
    ),
    DefectTemplate(
        "unpin-action-ref",
        "Replaced a pinned action ref with a moving branch.",
        "MEDIUM",
        (".yaml", ".yml"),
        _substitute(
            (r"^(\s*-?\s*uses:\s*[\w.-]+/[\w./-]+@)(?!main\b|master\b)[\w.-]+", r"\g<1>main")
        ),
    ),
    DefectTemplate(
        "disable-tls-verify",
        "Turned off TLS certificate verification.",
        "HIGH",
        (".py", ".yaml", ".yml"),
        _substitute(
            (
                r"^(\s*(?:validate_certs|tls_verify|verify_ssl):\s*)(?:true|yes|True)\b",
                r"\g<1>false",
            ),
            (r"^(\s*(?:insecure_skip_tls_verify|insecureSkipVerify):\s*)false\b", r"\g<1>true"),
            (r"\b((?:ssl_)?verify=)True\b", r"\g<1>False"),
        ),
    ),
    DefectTemplate(
        "log-secrets",
        "Let a task log its secrets by turning no_log off.",
        "HIGH",
        (".yaml", ".yml"),
        _substitute((r"^(\s*no_log:\s*)(?:true|yes|True)\b", r"\g<1>false")),
    ),
    DefectTemplate(
        "widen-file-mode",
        "Made a private file or directory readable or writable by everyone.",
        "HIGH",
        (".py", ".yaml", ".yml"),
        _substitute((r"(mode:\s*[\"']?0?|mode=0o|chmod\([^,()]+,\s*0o)([1-7])00\b", _widen_mode)),
    ),
    DefectTemplate(
        "weaken-pod-security",
        "Weakened a container's security context.",
        "HIGH",
        (".yaml", ".yml"),
        _substitute(
            (r"^(\s*(?:runAsNonRoot|readOnlyRootFilesystem):\s*)true\b", r"\g<1>false"),
            (r"^(\s*(?:allowPrivilegeEscalation|privileged):\s*)false\b", r"\g<1>true"),
        ),
    ),
)


def select_templates(names: Sequence[str] | None) -> tuple[DefectTemplate, ...]:
    """The named templates, or all of them; unknown names raise ValueError."""
    if not names:
        return TEMPLATES
    by_name = {template.name: template for template in TEMPLATES}
    if unknown := [name for name in names if name not in by_name]:
        known = ", ".join(by_name)
        raise ValueError(f"Unknown defect template(s): {', '.join(unknown)}. Known: {known}.")
    return tuple(by_name[name] for name in dict.fromkeys(names))


class Injection(BaseModel):
    """One injected defect and where a report of it counts."""

    id: str
    template: str
    file: str
    line: int
    region_start: int
    region_end: int
    original: str
    mutated: str
    description: str
    severity: str
    evidence: list[str] = Field(default_factory=list)


class DefectCorpus(BaseModel):
    """The manifest of a synthetic defect corpus."""

    sources: list[str]
    seed: int
    created_at: str
    caveat: str = SYNTHETIC_CAVEAT
    injections: list[Injection] = Field(default_factory=list)

    @classmethod
    def load(cls, corpus_dir: Path) -> DefectCorpus:
        return cls.model_validate_json((corpus_dir / CORPUS_MANIFEST).read_text(encoding="utf-8"))

    def write(self, corpus_dir: Path) -> Path:
        path = corpus_dir / CORPUS_MANIFEST
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def _inject(
    path: Path, rel: str, files_dir: Path, seed: int, templates: Sequence[DefectTemplate]
) -> Injection | None:
    """Inject one defect into a copy of the file, chosen by the seed; None when none fits."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError, UnicodeDecodeError:
        return None
    candidates = [(t, sites) for t in templates if t.applies_to(rel) and (sites := t.find(lines))]
    if not candidates:
        return None
    # Seeded per file, so adding a file does not change the injections in the others. The
    # template is drawn first, so frequent patterns do not crowd out rarer ones.
    rng = random.Random(f"{seed}:{rel}")
    template, sites = rng.choice(candidates)
    site = rng.choice(sites)
    target = files_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join([*lines[: site.start], *site.replacement, *lines[site.end :]]), "utf-8"
    )
    return Injection(
        id=f"{rel}:{site.start + 1}:{template.name}",
        template=template.name,
        file=rel,
        line=site.start + 1,
        region_start=site.region[0],
        region_end=site.region[1],
        original="".join(lines[site.start : site.end]).rstrip("\n"),
        mutated="".join(site.replacement).rstrip("\n"),
        description=template.description,
        severity=template.severity,
        evidence=list(site.evidence),
    )


def generate_corpus(
    files: Sequence[tuple[Path, str]],
    corpus_dir: Path,
    *,
    sources: Sequence[str],
    seed: int,
    conventions: str = "",
    templates: Sequence[DefectTemplate] = TEMPLATES,
) -> DefectCorpus:
    """Write a corpus of the source files that take an injection, one defect in each.

    `files` pairs each source file with the path its mutated copy takes under `files/`.
    """
    files_dir = corpus_dir / CORPUS_FILES_DIR
    files_dir.mkdir(parents=True, exist_ok=True)
    injections = [
        injection
        for path, rel in files
        if (injection := _inject(path, rel, files_dir, seed, templates)) is not None
    ]
    (corpus_dir / CORPUS_CONVENTIONS_FILE).write_text(conventions or _NO_CONVENTIONS, "utf-8")
    corpus = DefectCorpus(
        sources=list(sources),
        seed=seed,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        injections=injections,
    )
    corpus.write(corpus_dir)
    return corpus


class InjectionOutcome(BaseModel):
    """Whether the review found an injection, and what verification made of it."""

    id: str
    template: str
    file: str
    line: int
    found: bool = False
    reported: bool = False
    in_file: bool = False
    # "line" when a finding pointed into the injection's region, "content" when a finding on
    # the file named its evidence.
    matched_by: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    # The matched findings' titles, so a reader can check each match is about the injection.
    titles: list[str] = Field(default_factory=list)


class TemplateScore(BaseModel):
    injections: int = 0
    found: int = 0
    reported: int = 0


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


class CorpusScore(BaseModel):
    """Recall of one review session over a synthetic defect corpus."""

    caveat: str = SYNTHETIC_CAVEAT
    session_id: str
    injections: int
    found: int
    found_by_line: int
    reported: int
    in_file: int
    dropped: int
    unmatched_findings: int
    by_template: dict[str, TemplateScore] = Field(default_factory=dict)
    outcomes: list[InjectionOutcome] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recall_found(self) -> float:
        """Share of injections some finding named, before verification."""
        return _ratio(self.found, self.injections)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recall_reported(self) -> float:
        """Share of injections still reported after verification."""
        return _ratio(self.reported, self.injections)


def _match(finding: SavedFinding, injection: Injection, tolerance: int) -> tuple[bool, list[str]]:
    """Whether a finding names the injection's file, and how it matched the injection."""
    path, start, end = _parse_location(finding.location)
    file = injection.file.lower()
    if not path or not (path == file or path.endswith(f"/{file}")):
        return False, []
    matched_by: list[str] = []
    if start is not None and end is not None:
        if start <= injection.region_end + tolerance and end >= injection.region_start - tolerance:
            matched_by.append("line")
    text = f"{finding.title}\n{finding.description}\n{finding.fix}"
    if any(
        re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text, re.IGNORECASE)
        for token in injection.evidence
    ):
        matched_by.append("content")
    return True, matched_by


def _outcome(
    injection: Injection,
    candidates: Sequence[SavedFinding],
    reported: Sequence[SavedFinding],
    matched: set[int],
    tolerance: int,
) -> InjectionOutcome:
    outcome = InjectionOutcome(
        id=injection.id, template=injection.template, file=injection.file, line=injection.line
    )
    for finding in candidates:
        in_file, matched_by = _match(finding, injection, tolerance)
        outcome.in_file = outcome.in_file or in_file
        if matched_by:
            outcome.found = True
            outcome.matched_by = sorted({*outcome.matched_by, *matched_by})
            outcome.statuses.append(finding.status)
            outcome.titles.append(finding.title)
    for index, finding in enumerate(reported):
        if _match(finding, injection, tolerance)[1]:
            matched.add(index)
            outcome.reported = True
    return outcome


def score_corpus(
    corpus: DefectCorpus,
    candidates: Sequence[SavedFinding],
    reported: Sequence[SavedFinding],
    *,
    session_id: str,
    tolerance: int = LINE_OVERLAP_TOLERANCE,
) -> CorpusScore:
    """Match a session's findings against the corpus's injections.

    `candidates` are every finding the review produced, whatever verification made of them, and
    `reported` the ones it kept. A finding matches an injection when it names the file and either
    points into the injection's region or names its evidence.
    """
    matched: set[int] = set()
    outcomes = [
        _outcome(injection, candidates, reported, matched, tolerance)
        for injection in corpus.injections
    ]
    by_template: dict[str, TemplateScore] = {}
    for outcome in outcomes:
        score = by_template.setdefault(outcome.template, TemplateScore())
        score.injections += 1
        score.found += outcome.found
        score.reported += outcome.reported
    return CorpusScore(
        session_id=session_id,
        injections=len(outcomes),
        found=sum(o.found for o in outcomes),
        found_by_line=sum("line" in o.matched_by for o in outcomes),
        reported=sum(o.reported for o in outcomes),
        in_file=sum(o.in_file for o in outcomes),
        dropped=sum(o.found and not o.reported for o in outcomes),
        unmatched_findings=len(reported) - len(matched),
        by_template=by_template,
        outcomes=outcomes,
    )


__all__ = [
    "CORPUS_CONVENTIONS_FILE",
    "CORPUS_FILES_DIR",
    "CORPUS_MANIFEST",
    "SYNTHETIC_CAVEAT",
    "TEMPLATES",
    "CorpusScore",
    "DefectCorpus",
    "DefectTemplate",
    "Injection",
    "InjectionOutcome",
    "Site",
    "TemplateScore",
    "generate_corpus",
    "score_corpus",
    "select_templates",
]
