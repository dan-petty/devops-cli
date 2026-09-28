"""Structural guards on the public re-export surface declared by `__all__`.

`__all__` is the only machine-readable claim a package makes about what it
promises to expose, and `devops_cli.ai.library.introspector` reports it verbatim
as that package's public API. Ruff's F822 would normally catch a name declared
there and defined nowhere, but every large package in this tree defines a
module-level `__getattr__` for lazy re-export, and that alone suppresses F822 for
the whole module. A name can therefore sit in `__all__` indefinitely, advertised
to consumers and introspection alike, and raise `AttributeError` the first time
anyone reaches for it.

These tests close that gap. The tree-wide checks are static so they cost
milliseconds rather than the minutes that resolving every lazily-loaded AI export
would take, and they deliberately over-approximate what a module can serve: that
bias can only let a phantom through, never invent one.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "devops_cli"

DunderAll = ast.Assign | ast.AnnAssign


def _find_dunder_all(tree: ast.Module) -> DunderAll | None:
    """Locate the module's `__all__` in either the bare or the annotated assignment form."""
    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            return node
    return None


def _declared_exports(node: DunderAll) -> list[str]:
    """The string elements of `__all__` in source order, so repeats survive for counting."""
    value = node.value
    if not isinstance(value, ast.List | ast.Tuple):
        return []
    return [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def _names_bound_by(node: ast.AST) -> set[str]:
    """Names a single statement binds, covering the four statement kinds that can bind one."""
    if isinstance(node, ast.Import | ast.ImportFrom):
        return {alias.asname or alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def _bound_names(tree: ast.Module) -> set[str]:
    """Every name bound anywhere in the module.

    Walking the whole tree rather than just its top level is intentional: imports
    guarded by `try` or `if TYPE_CHECKING` still bind names that `__all__` may
    legitimately advertise.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        names |= _names_bound_by(node)
    return names


def _lazy_dispatch_names(tree: ast.Module, all_node: DunderAll) -> set[str]:
    """Every string literal in the module other than `__all__`'s own elements.

    Lazy packages spell their exports as strings inside the membership sets their
    `__getattr__` tests against, so a string literal anywhere else in the module
    is evidence the module knows that name. Excluding `__all__` is what gives the
    check its teeth: a phantom name appears nowhere but the list that promises it.
    """
    others = ast.Module(body=[n for n in tree.body if n is not all_node], type_ignores=[])
    return {
        node.value
        for node in ast.walk(others)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _sibling_modules(path: Path) -> set[str]:
    """Submodule names, which a package `__getattr__` may import on demand by name."""
    return {
        entry.stem if entry.suffix == ".py" else entry.name
        for entry in path.parent.iterdir()
        if entry.suffix == ".py" or (entry / "__init__.py").exists()
    }


def _servable_names(path: Path, tree: ast.Module, all_node: DunderAll) -> set[str]:
    """Every name the module could plausibly produce, by binding or by lazy dispatch."""
    return _bound_names(tree) | _lazy_dispatch_names(tree, all_node) | _sibling_modules(path)


def _exporting_modules() -> list[tuple[Path, ast.Module, DunderAll]]:
    """Every module under `src/devops_cli` that declares an `__all__`."""
    found: list[tuple[Path, ast.Module, DunderAll]] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = _find_dunder_all(tree)
        if node is not None:
            found.append((path, tree, node))
    return found


def test_no_phantom_exports() -> None:
    """A name in `__all__` that its module cannot serve is a promise broken on first use."""
    offenders = {
        str(path.relative_to(SRC_ROOT)): phantoms
        for path, tree, node in _exporting_modules()
        if (phantoms := sorted(set(_declared_exports(node)) - _servable_names(path, tree, node)))
    }
    assert offenders == {}, f"__all__ declares names the module cannot serve: {offenders}"


def test_no_duplicate_exports() -> None:
    """A repeated `__all__` entry is proof the list outgrew anyone's ability to read it."""
    offenders = {
        str(path.relative_to(SRC_ROOT)): repeats
        for path, _tree, node in _exporting_modules()
        if (repeats := sorted(n for n, c in Counter(_declared_exports(node)).items() if c > 1))
    }
    assert offenders == {}, f"__all__ repeats entries: {offenders}"


def test_config_package_exports_resolve() -> None:
    """`devops_cli.config` imports eagerly, so every name it declares must resolve right now.

    This is the dynamic counterpart to the static sweep above, pinning the package
    whose declared surface had drifted furthest from what it could actually hand out.
    """
    import devops_cli.config as config

    declared = list(config.__all__)
    unresolvable = [name for name in declared if not hasattr(config, name)]
    assert (unresolvable, len(declared)) == ([], len(set(declared)))
