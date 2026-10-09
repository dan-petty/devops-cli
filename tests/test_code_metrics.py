"""Tests for the one nesting and complexity metric, and the commit hook built on it (#773)."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from devops_cli.config.defaults import DEFAULT_MAX_NESTING_DEPTH
from devops_cli.core.code_metrics import breaches, main, measure_tree, nesting_depth

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _nested_ifs(levels: int) -> str:
    """Return the source of one function holding `levels` nested ifs."""
    lines = ["def f(x):"]
    lines += ["    " * (level + 1) + f"if x > {level}:" for level in range(levels)]
    lines.append("    " * (levels + 1) + "return x")
    return "\n".join(lines) + "\n"


def _write(tmp_path: Path, name: str, source: str) -> Path:
    module = tmp_path / name
    module.write_text(source, encoding="utf-8")
    return module


def test_deep_nesting_fails_the_commit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AGENTS.md caps nesting at 5, and the tree satisfies it, so the hook holds the line."""
    module = _write(tmp_path, "deep.py", _nested_ifs(7))

    status = main(["--max-depth", "5", str(module)])

    assert (status, "nesting 8 > 5" in capsys.readouterr().err) == (1, True)


def test_shallow_nesting_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A gate that rejected ordinary code would be turned off within a day."""
    module = _write(
        tmp_path, "shallow.py", "def f(x):\n    if x:\n        return 1\n    return 0\n"
    )

    assert (main(["--max-depth", "5", str(module)]), capsys.readouterr().err) == (0, "")


@pytest.mark.parametrize(
    ("levels", "depth", "status"),
    [
        pytest.param(4, 5, 0, id="four-nested-ifs-pass"),
        pytest.param(5, 6, 1, id="five-nested-ifs-fail"),
    ],
)
def test_the_function_body_is_depth_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], levels: int, depth: int, status: int
) -> None:
    """The hook counts as CI does: the body is depth 1, so 5 nested blocks reach depth 6."""
    module = _write(tmp_path, "boundary.py", _nested_ifs(levels))
    function = ast.parse(module.read_text(encoding="utf-8")).body[0]
    assert isinstance(function, ast.FunctionDef)

    assert (nesting_depth(function), main(["--max-depth", "5", str(module)])) == (depth, status)
    capsys.readouterr()


def test_only_existing_python_files_are_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """pre-commit hands the hook Python files, but a stray argument is skipped, not parsed."""
    notes = _write(tmp_path, "notes.txt", _nested_ifs(7))

    assert main(["--max-depth", "5", str(notes), str(tmp_path / "missing.py")]) == 0
    assert capsys.readouterr().err == ""


def test_an_unparseable_file_is_reported_rather_than_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Silently passing a file it could not read would make the gate meaningless."""
    module = _write(tmp_path, "broken.py", "def f(:\n")

    status = main(["--max-depth", "5", str(module)])

    assert (status, "could not parse" in capsys.readouterr().err) == (1, True)


def test_a_long_expression_is_measured_rather_than_overflowing(tmp_path: Path) -> None:
    """`1 + 1 + ... + 1` parses one node deeper per term.

    A recursive walk spending two frames per node raised RecursionError from 600 terms on, a
    traceback where the hook before it passed; the walk keeps its own stack (#586).
    """
    expression = " + ".join(["1"] * 3000)
    module = _write(tmp_path, "long.py", f"def f(x):\n    if x:\n        return {expression}\n")
    function = ast.parse(module.read_text(encoding="utf-8")).body[0]
    assert isinstance(function, ast.FunctionDef)

    assert (nesting_depth(function), breaches(module, 5)) == (2, [])


@pytest.mark.parametrize(
    "overflow",
    [
        pytest.param(RecursionError("Stack overflow during compilation"), id="recursion-error"),
        pytest.param(MemoryError("Parser stack overflowed"), id="memory-error"),
    ],
)
def test_a_parser_overflow_is_reported_rather_than_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overflow: Exception
) -> None:
    """`ast.parse` overflows on an expression too deep for it, a long unary chain among them."""

    def parse(source: str) -> ast.Module:
        raise overflow

    module = _write(tmp_path, "deep.py", "x = 1\n")
    monkeypatch.setattr(ast, "parse", parse)

    assert breaches(module, 5) == [f"{module}: could not parse ({overflow})"]


def test_the_hook_loads_no_scanner_and_no_pydantic_ai(tmp_path: Path) -> None:
    """A commit-time gate must cost less than the commit: no scanner, no pydantic_ai."""
    module = _write(tmp_path, "shallow.py", _nested_ifs(1))
    code = f"""
import json
import sys

from devops_cli.core.code_metrics import main

status = main(["--max-depth", "5", {str(module)!r}])
print("__HOOK_STATUS__" + json.dumps({{"status": status, "modules": sorted(sys.modules)}}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    line = next(line for line in proc.stdout.splitlines() if line.startswith("__HOOK_STATUS__"))
    result = json.loads(line.removeprefix("__HOOK_STATUS__"))
    loaded = [
        name
        for name in result["modules"]
        if name == "devops_cli.security"
        or name.startswith("devops_cli.security.")
        or name == "pydantic_ai"
    ]
    assert (result["status"], loaded) == (0, [])


_ASSERTS_IN_WITH = """
def f(x):
    with x:
        assert x
        assert x
        assert x
        assert x
"""

_BOOLEAN_OPERANDS = """
def f(a, b, c):
    if a and b and c:
        return 1
    return 0
"""

_CLOSURE = """
def outer(x):
    def inner(y):
        if y:
            return 1
        if y > 2:
            return 2
    return inner
"""

_FACTORY = """
def factory():
    class C:
        def m(self):
            def helper():
                return 1
            return helper()
    return C
"""

_LOOPS_WITH_ELSE = """
def f(items, n):
    for item in items:
        pass
    else:
        pass
    while n:
        n -= 1
    else:
        pass
"""

_TRY_TWO_HANDLERS_ELSE = """
def f():
    try:
        pass
    except ValueError:
        pass
    except KeyError:
        pass
    else:
        pass
"""

_TRY_ONE_HANDLER = """
def f():
    try:
        pass
    except ValueError:
        pass
"""

_MATCH_WILDCARD = """
def f(val):
    match val:
        case 1:
            return 10
        case 2:
            return 20
        case _:
            return 0
"""

_IF_ELIF_CHAIN = """
def f(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    else:
        return 4
"""

_IFEXP_AND_LAMBDA = """
def f(x):
    g = lambda y: y if y else 0
    return g(x) if x else None
"""

_ASYNC_BLOCKS = """
async def f(x):
    async with x:
        async for y in x:
            pass
"""


@pytest.mark.parametrize(
    ("source", "name", "complexity"),
    [
        pytest.param(_ASSERTS_IN_WITH, "f", 1, id="asserts-in-with"),
        pytest.param(_BOOLEAN_OPERANDS, "f", 2, id="boolean-operands"),
        pytest.param(_CLOSURE, "outer", 4, id="closure-outer"),
        pytest.param(_CLOSURE, "inner", 3, id="closure-inner"),
        pytest.param(_FACTORY, "factory", 3, id="factory-class-method-helper"),
        pytest.param(_LOOPS_WITH_ELSE, "f", 3, id="for-else-while-else"),
        pytest.param(_TRY_TWO_HANDLERS_ELSE, "f", 4, id="try-two-handlers-else"),
        pytest.param(_TRY_ONE_HANDLER, "f", 2, id="try-one-handler"),
        pytest.param(_MATCH_WILDCARD, "f", 3, id="match-two-literals-wildcard"),
        pytest.param(_IF_ELIF_CHAIN, "f", 4, id="if-elif-elif-else"),
        pytest.param(_IFEXP_AND_LAMBDA, "f", 1, id="ifexp-lambda"),
        pytest.param(_ASYNC_BLOCKS, "f", 2, id="async-with-async-for"),
    ],
)
def test_complexity_is_ruffs_c901_count(source: str, name: str, complexity: int) -> None:
    """Each value is what `ruff check --select C901` with `max-complexity = 0` reports."""
    measured = {fn.name: fn.cyclomatic_complexity for fn in measure_tree(ast.parse(source))}

    assert measured[name] == complexity


def test_the_commit_hook_runs_this_module_at_the_default_cap() -> None:
    """The hook takes its cap as an argument, so it must stay the project's default."""
    config = yaml.safe_load((_PROJECT_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hook = next(
        hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook["id"] == "structural-invariants"
    )

    assert (hook["entry"], hook["args"]) == (
        "uv run python3 -m devops_cli.core.code_metrics",
        ["--max-depth", str(DEFAULT_MAX_NESTING_DEPTH)],
    )
