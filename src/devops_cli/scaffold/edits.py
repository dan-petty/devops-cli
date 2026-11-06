"""Insert text into a Python module at the positions that `ast` reports (#3204).

Each function takes the source text and returns the new text. None writes a file, and none
searches the text: the syntax tree names the class, the statement or the import to edit.
"""

from __future__ import annotations

import ast

_LINE_LIMIT = 100


def catalog_class(source: str, catalog: str, field_name: str) -> str | None:
    """The name of the class that the `field_name` field of the `catalog` class is typed with."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == catalog:
            for statement in node.body:
                if (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == field_name
                    and isinstance(statement.annotation, ast.Name)
                ):
                    return statement.annotation.id
    return None


def class_fields(source: str, class_name: str) -> set[str]:
    """The names that the body of a top-level class assigns."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
            }
    return set()


def function_names(source: str) -> set[str]:
    """The names of the top-level functions of a module."""
    return {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def append_to_class(source: str, class_name: str, text: str) -> str:
    """Add `text`, indented as a class member, after the last statement of a top-level class."""
    lines = source.splitlines(keepends=True)
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            end = node.body[-1].end_lineno or node.body[-1].lineno
            member = "".join(f"    {line}\n" for line in text.splitlines())
            return "".join([*lines[:end], member, *lines[end:]])
    raise ValueError(class_name)


def append_to_module(source: str, text: str) -> str:
    """Add `text` as the last top-level statements, two blank lines after the code before it."""
    return f"{source.rstrip()}\n\n\n{text.rstrip()}\n"


def _sort_key(name: str) -> tuple[int, str]:
    """The order of ruff's isort inside a `from` import: constants, classes, then the rest."""
    return (0 if name.isupper() else 1 if name[:1].isupper() else 2, name)


def _import_line(module: str, names: list[str]) -> str:
    """One `from` import, in parentheses with one name a line when it passes the line limit."""
    line = f"from {module} import {', '.join(sorted(names, key=_sort_key))}\n"
    if len(line) <= _LINE_LIMIT:
        return line
    body = "".join(f"    {name},\n" for name in sorted(names, key=_sort_key))
    return f"from {module} import (\n{body})\n"


def add_import(source: str, module: str, name: str) -> str:
    """Make `from module import name` true in a module, with the fewest edits.

    A name that the module imports from `module` stays as it is. Another `from module import`
    statement gains the name. Otherwise a new statement goes before the first top-level `from`
    import of a module that sorts after `module`, or after the last import.
    """
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom | ast.Import)]
    from_imports = [node for node in imports if isinstance(node, ast.ImportFrom) and not node.level]
    for node in from_imports:
        if node.module == module:
            if name in [alias.name for alias in node.names]:
                return source
            names = [f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names]
            end = node.end_lineno or node.lineno
            replacement = _import_line(module, [*names, name])
            return "".join([*lines[: node.lineno - 1], replacement, *lines[end:]])
    new_line = f"from {module} import {name}\n"
    for node in from_imports:
        if (node.module or "") > module and (node.module or "").startswith("devops_cli"):
            return "".join([*lines[: node.lineno - 1], new_line, *lines[node.lineno - 1 :]])
    last = imports[-1]
    end = last.end_lineno or last.lineno
    return "".join([*lines[:end], new_line, *lines[end:]])
