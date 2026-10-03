"""What a passing verification or invalidation criterion proves about its finding.

A verdict the criteria settle is final: the model never sees the finding. In review session
`20261001-224227`, 36 findings were VERIFIED by criteria and none of their 37 passing commands
checked the cited code. One was a regex echoed against a literal, on a CRITICAL finding that
cited CVE-2021-44228; others were `git log --grep` over the history and version prints, and 97%
of the passing `python -c` criteria asserted nothing.

A passing command is evidence only when it runs the code the finding cites and checks the
outcome (#846):

- `python -c`: the script checks a value that comes from the cited code: a name it imports from
  the cited module, the cited file read and parsed (`json.loads`, `yaml.safe_load`), or
  anything computed from either. The check is an `assert` over such a value; a `raise`, or an
  exit with a failing status, under a condition over one (`if`, `while`, `and`/`or`, a `try`
  that runs it); or `sys.exit`, `exit` or `raise SystemExit` of a comparison, `not` or
  conditional over one. Searching a cited file's text is a grep, so a cited Python file counts
  only through its import. Testing that something exists (`assert f`, `f is not None`,
  `Path(...).exists()`) or reflecting on it (`hasattr`, `co_varnames`) shows only that the code
  is there.
- Anything else (`grep`, `git grep`, `git log`, `wc`, `cat`, `head`, `tail`, `find`) finds,
  counts or prints code, and never counts.
"""

from __future__ import annotations

import ast
import posixpath
import shlex
import sys
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath

from devops_cli.config.constants import (
    CONST_EXISTENCE_CRITERIA_CALLS,
    CONST_EXIT_CRITERIA_CALLS,
    CONST_PARSING_CRITERIA_CALLS,
    CONST_PYTHON_CRITERIA_BINARIES,
    CONST_READING_CRITERIA_CALLS,
    CONST_REFLECTION_CRITERIA_ATTRIBUTES,
    CONST_REFLECTION_CRITERIA_CALLS,
)

# How much of the cited code a value carries: nothing, only the text of a cited file, or what
# the cited code is or computes.
_NOTHING, _TEXT, _CODE = 0, 1, 2

# Whether a module name, or a string literal naming a file, is one the finding cites.
_Cites = Callable[[str], bool]


def python_invocation(args: Sequence[str]) -> tuple[str, str] | None:
    """What a `python -c <script>` or `python -m <module>` command runs: the option, and the
    script or module; None for any other command.

    Python reads its own options up to the first `-c` or `-m`, inside a cluster too, and passes
    the rest to the script or module: `python -Bc pass -c <script>` and `python -m X -c <script>`
    never run `<script>`. Only `-c` or `-m` as the first argument is read, so the criteria
    validator and the evidence rule both check what Python runs.
    """
    if (
        len(args) < 3
        or Path(args[0]).name not in CONST_PYTHON_CRITERIA_BINARIES
        or args[1] not in {"-c", "-m"}
    ):
        return None
    return args[1], args[2]


def _python_script(args: list[str]) -> str | None:
    """The script a `python -c` command runs; None for any other command."""
    invocation = python_invocation(args)
    return invocation[1] if invocation is not None and invocation[0] == "-c" else None


def _parse(source: str) -> ast.Module | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(source)
    except SyntaxError, ValueError:
        return None


def _call_name(func: ast.AST | None) -> str | None:
    """The name a call is made by: `f` for `f(...)` and for `m.f(...)`."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _reflects(tree: ast.Module) -> bool:
    """Whether the script inspects code (`hasattr`, `inspect.getsource`, `__code__`) instead of
    only running it."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _call_name(node.func) in CONST_REFLECTION_CRITERIA_CALLS:
                return True
        elif isinstance(node, ast.Attribute) and node.attr in CONST_REFLECTION_CRITERIA_ATTRIBUTES:
            return True
    return False


def _imported_names(tree: ast.Module, cites_module: _Cites) -> set[str]:
    """The names the script binds to the cited module, or to what it defines."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.partition(".")[0]
                for alias in node.names
                if cites_module(alias.name)
            )
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name != "*"
                and (cites_module(node.module) or cites_module(f"{node.module}.{alias.name}"))
            )
    return names


def _names(target: ast.AST) -> list[str]:
    return [node.id for node in ast.walk(target) if isinstance(node, ast.Name)]


def _binding(node: ast.AST) -> tuple[list[str], Sequence[ast.AST]] | None:
    """The names a statement or clause binds, with the code their values come from.

    An exception a `try` catches comes from its body, and what a function returns from its own.
    """
    match node:
        case ast.Assign(targets=targets, value=value):
            return [name for target in targets for name in _names(target)], [value]
        case (
            ast.AnnAssign(target=target, value=ast.expr() as value)
            | ast.AugAssign(target=target, value=value)
            | ast.NamedExpr(target=target, value=value)
        ):
            return _names(target), [value]
        case (
            ast.For(target=target, iter=value)
            | ast.AsyncFor(target=target, iter=value)
            | ast.comprehension(target=target, iter=value)
        ):
            return _names(target), [value]
        case ast.withitem(context_expr=value, optional_vars=ast.expr() as target):
            return _names(target), [value]
        case ast.Try(handlers=handlers, body=body) | ast.TryStar(handlers=handlers, body=body):
            return [handler.name for handler in handlers if handler.name], body
        case ast.FunctionDef(name=name, body=body) | ast.AsyncFunctionDef(name=name, body=body):
            return [name], body
    return None


def _decides(status: ast.expr) -> bool:
    """Whether an exit status is a decision: a comparison, `and`/`or`, `not` or conditional."""
    return isinstance(status, (ast.Compare, ast.BoolOp, ast.IfExp)) or (
        isinstance(status, ast.UnaryOp) and isinstance(status.op, ast.Not)
    )


class _Script:
    """A `python -c` script, read for the values it takes from the cited code and the checks it
    makes on them.

    The reading ignores the order of statements: a name carries the cited code if any value it
    is ever given does.
    """

    def __init__(self, tree: ast.Module, cites_module: _Cites, cites_file: _Cites) -> None:
        self._tree = tree
        self._cites_file = cites_file
        self._imported = _imported_names(tree, cites_module)
        self._carries = dict.fromkeys(self._imported, _CODE)
        bindings = [b for node in ast.walk(tree) if (b := _binding(node)) is not None]
        readers: dict[str, list[int]] = {}
        for at, (_, sources) in enumerate(bindings):
            for name in {n for source in sources for n in _names(source)}:
                readers.setdefault(name, []).append(at)
        # A binding is read again only when a name it reads rises, at most twice per name.
        pending = list(reversed(range(len(bindings))))
        while pending:
            names, sources = bindings[pending.pop()]
            carried = max((self._carried(source) for source in sources), default=_NOTHING)
            for name in names:
                if carried > self._carries.get(name, _NOTHING):
                    self._carries[name] = carried
                    pending.extend(readers.get(name, ()))

    def _reads_a_cited_file(self, call: ast.Call) -> bool:
        return any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and self._cites_file(node.value)
            for node in ast.walk(call)
        )

    def _carried(self, node: ast.AST) -> int:
        """How much of the cited code an expression or statement carries.

        Parsing a cited file's text gives values of the cited code; the text alone is a grep's.
        """
        carried = _NOTHING
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                carried = max(carried, self._carries.get(sub.id, _NOTHING))
            elif isinstance(sub, ast.Call):
                name = _call_name(sub.func)
                arguments = (*sub.args, *(keyword.value for keyword in sub.keywords))
                if name in CONST_PARSING_CRITERIA_CALLS and any(
                    self._carried(argument) >= _TEXT for argument in arguments
                ):
                    return _CODE
                if name in CONST_READING_CRITERIA_CALLS and self._reads_a_cited_file(sub):
                    carried = max(carried, _TEXT)
            if carried == _CODE:
                break
        return carried

    def _tests_existence(self, test: ast.AST) -> bool:
        """Whether a test asks only whether something exists: an imported name or attribute
        (`f`, `not app.f`, `f is not None`), or a path (`Path(...).exists()`)."""
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], (ast.Is, ast.IsNot))
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
        ):
            test = test.left
        if isinstance(test, ast.Call):
            return _call_name(test.func) in CONST_EXISTENCE_CRITERIA_CALLS
        while isinstance(test, ast.Attribute):
            test = test.value
        return isinstance(test, ast.Name) and test.id in self._imported

    def _uses(self, node: ast.AST) -> bool:
        """Whether code computes with a value from the cited code, beyond testing it exists."""
        test = node.value if isinstance(node, ast.Expr) else node
        return self._carried(test) == _CODE and not self._tests_existence(test)

    def _exit_fails_on_it(self, call: ast.Call, guarded: bool) -> bool:
        """Whether an exit's status depends on the cited code: a decision over it, or a failing
        status under a condition over it. `sys.exit(f(...))` exits 0 whenever `f` returns
        None, so a status the cited code returns is no check."""
        status = call.args[0] if call.args else None
        if status is None:
            return False
        if isinstance(status, ast.Constant):
            return guarded and status.value not in (None, 0)
        if _decides(status):
            return guarded or self._uses(status)
        return guarded and isinstance(status, ast.JoinedStr)

    def checks(self, node: ast.AST | None = None, guarded: bool = False) -> bool:
        """Whether the code holds a check that fails on what the cited code does.

        `guarded`: the code runs only under a condition over the cited code, so a `raise` or a
        failing exit in it depends on that code.
        """
        node = self._tree if node is None else node
        if isinstance(node, ast.Assert):
            return self._uses(node.test) or (
                guarded and isinstance(node.test, ast.Constant) and not node.test.value
            )
        if isinstance(node, ast.Raise):
            if (
                isinstance(node.exc, ast.Call)
                and _call_name(node.exc.func) in CONST_EXIT_CRITERIA_CALLS
            ):
                return self._exit_fails_on_it(node.exc, guarded)
            return guarded and _call_name(node.exc) not in CONST_EXIT_CRITERIA_CALLS
        if isinstance(node, ast.Call) and _call_name(node.func) in CONST_EXIT_CRITERIA_CALLS:
            return self._exit_fails_on_it(node, guarded)
        if isinstance(node, (ast.If, ast.While)):
            inner = guarded or self._uses(node.test)
            return self.checks(node.test, guarded) or any(
                self.checks(statement, inner) for statement in (*node.body, *node.orelse)
            )
        if isinstance(node, ast.IfExp):
            inner = guarded or self._uses(node.test)
            return (
                self.checks(node.test, guarded)
                or self.checks(node.body, inner)
                or self.checks(node.orelse, inner)
            )
        if isinstance(node, ast.BoolOp):
            return any(
                self.checks(value, guarded or any(map(self._uses, node.values[:at])))
                for at, value in enumerate(node.values)
            )
        if isinstance(node, (ast.Try, ast.TryStar)):
            inner = guarded or any(map(self._uses, node.body))
            parts = (*node.body, *node.handlers, *node.orelse, *node.finalbody)
            return any(self.checks(part, inner) for part in parts)
        if isinstance(node, ast.Match):
            inner = guarded or self._uses(node.subject)
            return any(self.checks(case, inner) for case in node.cases)
        return any(self.checks(child, guarded) for child in ast.iter_child_nodes(node))


def _script_checks(args: list[str], cites_module: _Cites, cites_file: _Cites) -> bool:
    """Whether a `python -c` command checks what the code it cites does, without reflecting."""
    script = _python_script(args)
    tree = _parse(script) if script is not None else None
    if tree is None or _reflects(tree):
        return False
    return _Script(tree, cites_module, cites_file).checks()


def _split(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _outside_the_standard_library(module: str) -> bool:
    return module.partition(".")[0] not in sys.stdlib_module_names


def is_tautological_criterion(command: str) -> bool:
    """Whether a command proves nothing about any finding, whatever its exit status.

    Only a `python -c` script that checks what a module it imports does, or a file it reads and
    parses, can count; which finding it counts for is `counts_as_evidence`'s question. A finding
    cites reviewed code, never the standard library.
    """
    args = _split(command)
    if not args:
        return True
    return not _script_checks(args, _outside_the_standard_library, lambda _file: True)


def _cited_paths(location: str, repo_root: Path) -> list[PurePosixPath]:
    """The cited file relative to the repository root, and under `src/` when it lives there."""
    file_part = location.split(":", 1)[0].strip()
    if not file_part:
        return []
    cited = PurePosixPath(posixpath.normpath(file_part))
    if not cited.parts:
        return []
    if cited.is_absolute():
        try:
            cited = cited.relative_to(repo_root.resolve().as_posix())
        except ValueError:
            return []
    if cited.parts[0] != "src" and (repo_root / "src" / cited).is_file():
        return [cited, PurePosixPath("src", cited)]
    return [cited]


def _module_names(paths: list[PurePosixPath]) -> set[str]:
    """The names the cited file imports as, from the repository root and from `src/`.

    Criteria run with both on `PYTHONPATH`.
    """
    names: set[str] = set()
    for path in paths:
        if path.suffix != ".py":
            continue
        parts = list(path.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        starts = (0, 1) if parts[:1] == ["src"] else (0,)
        names.update(".".join(parts[start:]) for start in starts if parts[start:])
    return names


def counts_as_evidence(command: str, location: str, repo_root: Path) -> bool:
    """Whether a passing command shows anything about the code a finding at `location` cites."""
    args = _split(command)
    if not args:
        return False
    paths = _cited_paths(location, repo_root)
    modules = _module_names(paths)
    root = repo_root.resolve()
    # A cited Python file counts only through its import: reading its source is a grep.
    files = {str(base / path) for path in paths if path.suffix != ".py" for base in (Path(), root)}
    return _script_checks(
        args,
        lambda module: any(module == m or module.startswith(f"{m}.") for m in modules),
        lambda literal: posixpath.normpath(literal) in files,
    )
