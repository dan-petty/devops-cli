"""Read referenced classes and model fields in the stage job (#3344).

Collect dotted references from plan texts, find model definitions at the staged commit with git,
and extract their annotated fields with AST.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

from devops_cli.exceptions.git import GitOperationError
from devops_cli.roadmap.clone_git import git

_DOTTED_REF: Final[re.Pattern[str]] = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b")


def referenced_classes(texts: Iterable[str]) -> set[str]:
    """The first part of each dotted reference in `texts`."""
    classes: set[str] = set()
    for text in texts:
        for match in _DOTTED_REF.finditer(text):
            classes.add(match.group(1))
    return classes


def _annotated_fields(node: ast.ClassDef) -> tuple[str, ...]:
    fields: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.append(stmt.target.id)
    return tuple(fields)


def _base_names(node: ast.ClassDef) -> set[str]:
    bases: set[str] = set()
    for b in node.bases:
        if isinstance(b, ast.Name):
            bases.add(b.id)
        elif isinstance(b, ast.Attribute):
            bases.add(b.attr)
    return bases


def _find_model_names(class_bases: Mapping[str, set[str]]) -> set[str]:
    model_names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, bases in class_bases.items():
            if name not in model_names and (
                "BaseModel" in bases or any(b in model_names for b in bases)
            ):
                model_names.add(name)
                changed = True
    return model_names


def _resolve_fields(
    name: str,
    module_classes: Mapping[str, ast.ClassDef],
    class_bases: Mapping[str, set[str]],
    model_names: set[str],
    seen: set[str] | None = None,
) -> tuple[str, ...]:
    visited = seen if seen is not None else set()
    if name in visited or name not in module_classes:
        return ()
    visited.add(name)
    collected: list[str] = []
    for base in class_bases.get(name, ()):
        if base in model_names and base in module_classes:
            for field in _resolve_fields(base, module_classes, class_bases, model_names, visited):
                if field not in collected:
                    collected.append(field)
    for field in _annotated_fields(module_classes[name]):
        if field not in collected:
            collected.append(field)
    return tuple(collected)


def parse_module_models(source_code: str) -> dict[str, tuple[str, ...]]:
    """Annotated fields of each model class that subclasses BaseModel in `source_code`."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}
    module_classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    class_bases = {name: _base_names(node) for name, node in module_classes.items()}
    model_names = _find_model_names(class_bases)
    return {
        name: _resolve_fields(name, module_classes, class_bases, model_names)
        for name in model_names
    }


def _class_field_lines(node: ast.ClassDef) -> dict[str, int]:
    """The line of each annotated or assigned field of the body of `node`."""
    fields: dict[str, int] = {}
    for stmt in node.body:
        names: list[str] = []
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.append(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            names += [target.id for target in stmt.targets if isinstance(target, ast.Name)]
        for name in names:
            fields.setdefault(name, stmt.lineno)
    return fields


def parse_class_fields(source_code: str) -> dict[str, dict[str, int]]:
    """The line of each annotated or assigned field of each class of `source_code`, by class name.

    The reader takes the fields of the class body and no field of a base class, because a probe
    names the line of the definition. A module that `ast` cannot parse holds no class."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}
    return {
        node.name: _class_field_lines(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def _grep_class_paths(source: Path, sha: str, name: str) -> list[str]:
    args = ["grep", "-n", f"^class {name}(", sha, "--", "src/"]
    try:
        output = git(source, *args, operation="stage model grep")
    except GitOperationError:
        return []
    prefix = f"{sha}:"
    paths: list[str] = []
    for line in output.splitlines():
        rel = line.removeprefix(prefix)
        file_path = rel.split(":", 2)[0]
        if file_path.endswith(".py") and file_path not in paths:
            paths.append(file_path)
    return paths


def model_fields(
    source: Path,
    sha: str,
    names: Sequence[str] | set[str],
) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Find each named class at `sha` under `src/` and return module path and annotated fields."""
    models: dict[str, tuple[str, tuple[str, ...]]] = {}
    parsed_files: dict[str, dict[str, tuple[str, ...]]] = {}
    for name in sorted(set(names)):
        paths = _grep_class_paths(source, sha, name)
        for path in paths:
            if path not in parsed_files:
                try:
                    code = git(source, "show", f"{sha}:{path}", operation="stage model show")
                except GitOperationError:
                    continue
                parsed_files[path] = parse_module_models(code)
            if name in parsed_files[path]:
                models[name] = (path, parsed_files[path][name])
                break
    return models
