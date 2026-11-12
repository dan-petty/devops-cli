"""`devops roadmap stage`: check plan numbers against staged constants (#3308).

A plan that carries a number from an issue or plan text is a claim that the number holds in the
code. This module extracts constant names and candidate numbers from plan texts, reads module-level
integer constants from the staged repository commit using `git grep`, `git show`, and `ast`, and
refuses a plan when a sentence gives a constant a different value.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final

from devops_cli.exceptions.git import GitOperationError
from devops_cli.lang.en.messages import MESSAGES
from devops_cli.roadmap.clone_git import git

# An uppercase identifier with at least two characters.
_CONSTANT_NAME: Final[re.Pattern[str]] = re.compile(r"\b[A-Z][A-Z0-9_]+\b")

# Keywords in uppercase that are not constant names.
_EXCLUDED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "ADDED",
        "AND",
        "AST",
        "CI",
        "HEAD",
        "JSON",
        "MODIFIED",
        "MUST",
        "NOT",
        "OR",
        "PR",
        "REST",
        "SHALL",
        "SHOULD",
        "THEN",
        "WHEN",
        "YAML",
    }
)

# A candidate decimal integer, with the `_` digit separators of a Python literal (6_500): not
# part of a note reference (#2714), line location (:12), date (2026-11-03), range (1790-2000), or
# version/path (v1.0.0, a/40). `(?![\d_])` keeps the literal whole, so the engine does not
# backtrack from `1790` to `179` or from `6_500` to `6`.
_CANDIDATE_NUMBER: Final[re.Pattern[str]] = re.compile(
    r"(?<![#:\w/.])(?<!\d-)(\d+(?:_\d+)*)(?![\d_]|[/.]\w|-\d)"
)

# The text between a constant name and the value that a plan states for it in the staged tree:
# `NAME = 40`, `NAME: Final[int] = 40` or `NAME` is 40 (#5034). An operand (`NAME + 1`), an
# option value (`-n 0`), the value of another name in the sentence, and a new value that the
# change sets (raise `NAME` to 80) are no staged value of `NAME`.
_VALUE_LINK: Final[str] = r"`?(?:\s*:\s*[\w.\[\]]+\s*=|\s*(?:==?|is\b))\s*`?"

_PARAGRAPH_SPLIT: Final[re.Pattern[str]] = re.compile(r"\n\s*(?:[-*]\s+|\d+\.\s+|#+\s+|\n+)")
_SENTENCE_SPLIT: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+")

_NON_LITERAL: Final[object] = object()


def candidate_names(texts: Iterable[str]) -> set[str]:
    """The constant names that `texts` cite: uppercase identifiers with at least two characters."""
    names: set[str] = set()
    for text in texts:
        for match in _CONSTANT_NAME.finditer(text):
            name = match.group()
            if name not in _EXCLUDED_NAMES:
                names.add(name)
    return names


def _sentences(text: str) -> list[str]:
    """The sentences of `text`."""
    sentences: list[str] = []
    for block in _PARAGRAPH_SPLIT.split(text):
        normalized = " ".join(block.split())
        if not normalized:
            continue
        for sentence in _SENTENCE_SPLIT.split(normalized):
            sentence = sentence.strip()
            if sentence:
                sentences.append(sentence)
    return sentences


def _eval_literal_or_alias(val_node: ast.expr | None) -> Any:
    if val_node is None:
        return _NON_LITERAL
    if (
        isinstance(val_node, ast.Constant)
        and isinstance(val_node.value, int)
        and not isinstance(val_node.value, bool)
    ):
        return int(val_node.value)
    if (
        isinstance(val_node, ast.UnaryOp)
        and isinstance(val_node.op, ast.USub)
        and isinstance(val_node.operand, ast.Constant)
        and isinstance(val_node.operand.value, int)
        and not isinstance(val_node.operand.value, bool)
    ):
        return -int(val_node.operand.value)
    if isinstance(val_node, ast.Name):
        return val_node.id
    return _NON_LITERAL


def _stmt_targets_and_val(stmt: ast.stmt) -> tuple[list[str], ast.expr | None]:
    if isinstance(stmt, ast.Assign):
        targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        return targets, stmt.value
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id], stmt.value
    return [], None


def _parse_module_definitions(source: str, filename: str) -> dict[str, list[Any]]:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return {}
    defs: dict[str, list[Any]] = defaultdict(list)
    for stmt in tree.body:
        targets, val_node = _stmt_targets_and_val(stmt)
        if not targets or val_node is None:
            continue
        parsed = _eval_literal_or_alias(val_node)
        for target in targets:
            defs[target].append(parsed)
    return defs


def _extract_raw_definitions(sources: Mapping[str, str]) -> dict[str, set[Any]]:
    """The raw definitions found at module level in `sources`: integer literals, aliases, or non-literals."""
    definitions: dict[str, set[Any]] = defaultdict(set)
    for path, source in sources.items():
        for name, values in _parse_module_definitions(source, path).items():
            definitions[name].update(values)
    return definitions


def _resolve_constant(
    name: str,
    definitions: Mapping[str, set[Any]],
    visited: set[str],
) -> int | None:
    if name in visited:
        return None
    visited.add(name)
    defs = definitions.get(name)
    if not defs:
        return None
    resolved: set[int] = set()
    for item in defs:
        if item is _NON_LITERAL:
            return None
        if isinstance(item, int):
            resolved.add(item)
        elif isinstance(item, str):
            alias_val = _resolve_constant(item, definitions, visited.copy())
            if alias_val is None:
                return None
            resolved.add(alias_val)
        else:
            return None
    if len(resolved) == 1:
        return next(iter(resolved))
    return None


def parse_constants(
    sources: Mapping[str, str],
    names: Iterable[str] | None = None,
) -> dict[str, int]:
    """Parse module-level integer constants from `sources`, resolving aliases across modules."""
    definitions = _extract_raw_definitions(sources)
    result: dict[str, int] = {}
    candidate_keys = set(names) if names is not None else set(definitions)
    for key in candidate_keys:
        value = _resolve_constant(key, definitions, set())
        if value is not None:
            result[key] = value
    return result


def _git_grep_paths(source: Path, sha: str, names: set[str]) -> list[str]:
    args = ["grep", "-l"]
    for name in sorted(names):
        args.extend(["-e", name])
    args.extend([sha, "--", "src/"])
    try:
        output = git(source, *args, operation="stage constants grep")
    except GitOperationError:
        return []
    prefix = f"{sha}:"
    return [
        line.removeprefix(prefix).strip()
        for line in output.splitlines()
        if line.strip() and line.removeprefix(prefix).strip().endswith(".py")
    ]


def _load_git_sources(source: Path, sha: str, paths: list[str], loaded: dict[str, str]) -> None:
    for path in paths:
        if path in loaded:
            continue
        try:
            loaded[path] = git(source, "show", f"{sha}:{path}", operation="stage constants show")
        except GitOperationError:
            continue


def _discover_aliases(loaded: Mapping[str, str], searched: set[str]) -> set[str]:
    new_aliases: set[str] = set()
    for defs in _extract_raw_definitions(loaded).values():
        for item in defs:
            if isinstance(item, str) and item not in searched:
                new_aliases.add(item)
    return new_aliases


def staged_constants(source: Path, sha: str, names: Iterable[str]) -> dict[str, int]:
    """Find each constant in `names` at `sha` in `source`, read the files with `git show`, and parse with AST."""
    candidate_set = set(names)
    if not candidate_set:
        return {}

    loaded_sources: dict[str, str] = {}
    pending_names = set(candidate_set)
    searched_names: set[str] = set()

    while pending_names:
        to_search = pending_names - searched_names
        if not to_search:
            break
        searched_names.update(to_search)
        matched = _git_grep_paths(source, sha, to_search)
        _load_git_sources(source, sha, matched, loaded_sources)
        pending_names.update(_discover_aliases(loaded_sources, searched_names))

    return parse_constants(loaded_sources, names=candidate_set)


def _states_value(sentence: str, constant: str, number: re.Match[str]) -> bool:
    """Whether `number` follows `constant` with `=` or `is` in `sentence` (#5034)."""
    link = re.compile(rf"\b{re.escape(constant)}\b{_VALUE_LINK}$")
    return link.search(sentence, 0, number.start()) is not None


def constant_problems(texts: Iterable[str], constants: Mapping[str, int]) -> list[str]:
    """One problem for each sentence that names one known constant, holds one candidate number,
    gives that number to the constant with `=` or `is`, and differs from the staged tree value
    (#3308, #5034)."""
    if not constants:
        return []
    problems: list[str] = []
    texts_msg = MESSAGES.roadmap
    for text in texts:
        for sentence in _sentences(text):
            known = [name for name in constants if re.search(rf"\b{re.escape(name)}\b", sentence)]
            if len(known) != 1:
                continue
            numbers = list(_CANDIDATE_NUMBER.finditer(sentence))
            constant = known[0]
            if len(numbers) != 1 or not _states_value(sentence, constant, numbers[0]):
                continue
            plan_value = int(numbers[0].group(1))
            staged_value = constants[constant]
            if plan_value != staged_value:
                problems.append(
                    texts_msg.stage_problem_constant_mismatch.format(
                        constant=constant,
                        staged=staged_value,
                        plan=plan_value,
                    )
                )
    return list(dict.fromkeys(problems))


__all__ = [
    "candidate_names",
    "constant_problems",
    "parse_constants",
    "staged_constants",
]
