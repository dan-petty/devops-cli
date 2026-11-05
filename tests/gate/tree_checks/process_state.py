"""Process-wide state in src is reset by the floor (#2164)."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path

from tests.support.paths import REPO_ROOT

_CONTAINER_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "clear",
        "update",
        "pop",
        "popitem",
        "setdefault",
        "append",
        "extend",
        "insert",
        "remove",
        "add",
        "discard",
    }
)


def _extract_conftest_state_resets(conftest_tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Extract `_PROCESS_STATE_RESETS` from `tests/conftest.py`'s AST without importing conftest."""
    for stmt in conftest_tree.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "_PROCESS_STATE_RESETS"
            and stmt.value is not None
        ):
            raw = ast.literal_eval(stmt.value)
            return {str(k): tuple(str(x) for x in v) for k, v in raw.items()}
    return {}


def _assigned_names(stmt: ast.stmt) -> list[str]:
    """Return top-level variable names bound by an `Assign` or `AnnAssign` statement."""
    if isinstance(stmt, ast.Assign):
        return [target.id for target in stmt.targets if isinstance(target, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id]
    return []


def _index_top_level_defs(
    tree: ast.Module,
) -> tuple[
    dict[str, int], dict[str, ast.ClassDef], dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
]:
    """Index top-level variable assignment lines, classes, and functions in `tree`."""
    assigns: dict[str, int] = {}
    classes: dict[str, ast.ClassDef] = {}
    funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for stmt in tree.body:
        for name in _assigned_names(stmt):
            assigns[name] = getattr(stmt, "lineno", 1)
        if isinstance(stmt, ast.ClassDef):
            classes[stmt.name] = stmt
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[stmt.name] = stmt
    return assigns, classes, funcs


def _find_class_method(
    cls_node: ast.ClassDef | None, method_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the method AST node named `method_name` on `cls_node`, or None."""
    if cls_node is None:
        return None
    for item in cls_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
            return item
    return None


def _collect_local_callee_specs(
    fn_node: ast.AST,
    classes: Mapping[str, ast.ClassDef],
    funcs: Mapping[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> list[str]:
    """Return local function or classmethod specs called inside `fn_node`."""
    callees: list[str] = []
    for sub in ast.walk(fn_node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Name) and sub.func.id in funcs:
            callees.append(sub.func.id)
        elif (
            isinstance(sub.func, ast.Attribute)
            and isinstance(sub.func.value, ast.Name)
            and sub.func.value.id in classes
        ):
            callees.append(f"{sub.func.value.id}.{sub.func.attr}")
    return callees


def _resolve_reset_nodes(
    registered_resets: Sequence[str],
    classes: Mapping[str, ast.ClassDef],
    funcs: Mapping[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> list[tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Resolve registered public reset names and their transitive local helpers to `(cls_name, node)`."""
    resolved: list[tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    visited: set[str] = set()
    queue = [spec for spec in registered_resets if not spec.split(".")[-1].startswith("_")]
    while queue:
        spec = queue.pop()
        if spec in visited:
            continue
        visited.add(spec)
        if "." in spec:
            cls_name, meth_name = spec.split(".", 1)
            method_node = _find_class_method(classes.get(cls_name), meth_name)
            if method_node is not None:
                resolved.append((cls_name, method_node))
        elif (fn_node := funcs.get(spec)) is not None:
            resolved.append((None, fn_node))
            queue.extend(_collect_local_callee_specs(fn_node, classes, funcs))
    return resolved


def _record_assign_target_reset(
    target: ast.expr,
    cls_name: str | None,
    reset_containers: set[str],
    reset_cls_attrs: set[tuple[str, str]],
) -> None:
    """Record a subscript container reset or class attribute rebind from an assignment target."""
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        reset_containers.add(target.value.id)
    elif (
        cls_name is not None
        and isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id in {"cls", cls_name}
    ):
        reset_cls_attrs.add((cls_name, target.attr))


def _record_call_reset(sub: ast.Call, reset_containers: set[str], reset_caches: set[str]) -> None:
    """Record a `cache_clear()` or container-mutating method call inside a reset function."""
    if not (isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name)):
        return
    target_id = sub.func.value.id
    if sub.func.attr == "cache_clear":
        reset_caches.add(target_id)
    elif sub.func.attr in _CONTAINER_MUTATING_METHODS:
        reset_containers.add(target_id)


def _record_assign_reset(
    sub: ast.Assign,
    cls_name: str | None,
    reset_containers: set[str],
    reset_cls_attrs: set[tuple[str, str]],
) -> None:
    """Record container resets or class attribute rebinds across all targets of `sub`."""
    for target in sub.targets:
        _record_assign_target_reset(target, cls_name, reset_containers, reset_cls_attrs)


def _record_node_resets(
    cls_name: str | None,
    rnode: ast.FunctionDef | ast.AsyncFunctionDef,
    reset_globals: set[str],
    reset_containers: set[str],
    reset_caches: set[str],
    reset_cls_attrs: set[tuple[str, str]],
) -> None:
    """Record the globals, containers, caches, and class attributes reset inside `rnode`."""
    for sub in ast.walk(rnode):
        if isinstance(sub, ast.Global):
            reset_globals.update(sub.names)
        if isinstance(sub, ast.Call):
            _record_call_reset(sub, reset_containers, reset_caches)
        if isinstance(sub, ast.Assign):
            _record_assign_reset(sub, cls_name, reset_containers, reset_cls_attrs)


def _decorator_short_name(dec: ast.expr) -> str:
    """Return the bare name of a decorator (`cache`, `lru_cache`, `classmethod`, etc.)."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Name):
        return target.id
    return target.attr if isinstance(target, ast.Attribute) else ""


def _mutated_container_names_in_node(sub: ast.AST) -> list[str]:
    """Return container variable names mutated by `sub` via method call or subscript assignment."""
    if (
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and isinstance(sub.func.value, ast.Name)
        and sub.func.attr in _CONTAINER_MUTATING_METHODS
    ):
        return [sub.func.value.id]
    if isinstance(sub, (ast.Assign, ast.Delete)):
        return [
            target.value.id
            for target in sub.targets
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
        ]
    return []


def _collect_mutated_containers(
    tree: ast.Module, assigns: Mapping[str, int], seen_globals: set[str]
) -> dict[str, int]:
    """Return module-level containers mutated inside functions or methods, mapped to their line."""
    containers: dict[str, int] = {}
    scope_stmts = [
        stmt
        for stmt in tree.body
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for stmt in scope_stmts:
        for sub in ast.walk(stmt):
            for cname in _mutated_container_names_in_node(sub):
                if cname in assigns and cname not in seen_globals:
                    containers.setdefault(cname, assigns[cname])
    return containers


def _classmethod_rebound_attrs(
    cls_name: str, item: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[tuple[str, int]]:
    """Return `(attr_name, lineno)` for class attributes rebound inside `@classmethod` `item`."""
    if not any(_decorator_short_name(d) == "classmethod" for d in item.decorator_list):
        return []
    found: list[tuple[str, int]] = []
    for sub in ast.walk(item):
        if not isinstance(sub, ast.Assign):
            continue
        for target in sub.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in {"cls", cls_name}
            ):
                found.append((target.attr, sub.lineno))
    return found


def _collect_classmethod_rebinds(
    classes: Mapping[str, ast.ClassDef],
) -> list[tuple[str, str, int]]:
    """Return `(cls_name, attr_name, lineno)` for every class attribute a `@classmethod` rebinds."""
    rebinds: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for cls_name, cls_node in classes.items():
        cls_assigns = _index_top_level_defs(ast.Module(body=cls_node.body, type_ignores=[]))[0]
        methods = [
            item
            for item in cls_node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for method in methods:
            for attr, lineno in _classmethod_rebound_attrs(cls_name, method):
                if (cls_name, attr) not in seen:
                    seen.add((cls_name, attr))
                    rebinds.append((cls_name, attr, cls_assigns.get(attr, lineno)))
    return rebinds


def _collect_global_rebinds(tree: ast.Module, assigns: Mapping[str, int]) -> dict[str, int]:
    """Return module-level names rebound through `global`, mapped to their line number."""
    seen_globals: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names:
                seen_globals.setdefault(name, assigns.get(name, node.lineno))
    return seen_globals


def _collect_cached_functions(tree: ast.Module) -> list[tuple[str, int]]:
    """Return `(func_name, lineno)` for every `@cache` or `@lru_cache` function in `tree`."""
    return [
        (node.name, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_decorator_short_name(d) in {"cache", "lru_cache"} for d in node.decorator_list)
    ]


def _find_unreset_process_state(
    rel_path: str, tree: ast.Module, registered_resets: Sequence[str]
) -> list[str]:
    """Return `path:line` violations for any of the 4 process-wide state forms not reset (#1310)."""
    assigns, classes, funcs = _index_top_level_defs(tree)
    reset_globals: set[str] = set()
    reset_containers: set[str] = set()
    reset_caches: set[str] = set()
    reset_cls_attrs: set[tuple[str, str]] = set()
    for cls_name, rnode in _resolve_reset_nodes(registered_resets, classes, funcs):
        _record_node_resets(
            cls_name, rnode, reset_globals, reset_containers, reset_caches, reset_cls_attrs
        )

    seen_globals = _collect_global_rebinds(tree, assigns)
    containers = _collect_mutated_containers(tree, assigns, set(seen_globals))
    return [
        *[
            f"{rel_path}:{lineno}: global {name} is not reset"
            for name, lineno in sorted(seen_globals.items(), key=lambda item: item[1])
            if name not in reset_globals
        ],
        *[
            f"{rel_path}:{lineno}: container {name} is not reset"
            for name, lineno in sorted(containers.items(), key=lambda item: item[1])
            if name not in reset_containers
        ],
        *[
            f"{rel_path}:{lineno}: cached function {name} is not reset"
            for name, lineno in _collect_cached_functions(tree)
            if name not in reset_caches
        ],
        *[
            f"{rel_path}:{lineno}: class attribute {cls_name}.{attr_name} is not reset"
            for cls_name, attr_name, lineno in _collect_classmethod_rebinds(classes)
            if (cls_name, attr_name) not in reset_cls_attrs
        ],
    ]


def _module_name_for_source_path(path: Path) -> str:
    """Return the dotted `devops_cli.*` module name for a file under `src/`."""
    parts = list(path.relative_to(REPO_ROOT / "src").with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def check_every_piece_of_process_wide_state_in_src_is_reset_by_the_floor(
    parsed_source_trees: dict[Path, ast.Module],
    parsed_repo_trees: dict[Path, ast.Module],
) -> None:
    """Every global rebind, mutated module container, cached function, and classmethod singleton in src is reset after each test (#1310)."""
    conftest_tree = parsed_repo_trees[REPO_ROOT / "tests" / "conftest.py"]
    resets_by_module = _extract_conftest_state_resets(conftest_tree)
    violations: list[str] = []
    for path, tree in sorted(parsed_source_trees.items()):
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        module_name = _module_name_for_source_path(path)
        violations.extend(
            _find_unreset_process_state(rel_path, tree, resets_by_module.get(module_name, ()))
        )
    assert violations == []


def check_process_wide_state_invariant_reports_each_unreset_form() -> None:
    """The process-wide state scanner reports `path:line` for each of the four forms when unreset (#1310)."""
    sample = ast.parse(
        "import functools\n"
        "_STATE = None\n"
        "_ITEMS: dict[str, int] = {}\n"
        "def mutate() -> None:\n"
        "    global _STATE\n"
        "    _STATE = 1\n"
        "    _ITEMS['a'] = 2\n"
        "@functools.lru_cache(maxsize=1)\n"
        "def cached_val() -> int:\n"
        "    return 42\n"
        "class Service:\n"
        "    _instance = None\n"
        "    @classmethod\n"
        "    def get(cls) -> object:\n"
        "        cls._instance = object()\n"
        "        return cls._instance\n"
    )
    assert _find_unreset_process_state("src/devops_cli/sample.py", sample, ()) == [
        "src/devops_cli/sample.py:2: global _STATE is not reset",
        "src/devops_cli/sample.py:3: container _ITEMS is not reset",
        "src/devops_cli/sample.py:9: cached function cached_val is not reset",
        "src/devops_cli/sample.py:12: class attribute Service._instance is not reset",
    ]
