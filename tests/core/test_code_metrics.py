"""Tests for the McCabe complexity metric of `core.code_metrics` (#773).

Ruff's PLR1702 caps nesting (#1876), so the module measures complexity only.
"""

from __future__ import annotations

import ast

import pytest

from devops_cli.core.code_metrics import measure_tree

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
