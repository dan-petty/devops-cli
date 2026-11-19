"""Which tests of a changed test file the pull request changed (#3124)."""

from __future__ import annotations

import pytest

from devops_cli.ci.changed_tests import (
    deleted_module_checks,
    is_file_changed,
    is_test_changed,
    only_deleted_checks,
    parse_tests,
)

BASE = '''\
"""Module docstring."""

import pytest


def helper():
    return 1


def test_kept():
    assert helper() == 1


def test_edited():
    assert helper() == 1


class TestGroup:
    def test_method(self):
        assert helper() == 1

    def test_method_edited(self):
        assert helper() == 1
'''

HEAD = '''\
"""Module docstring."""

import pytest


def helper():
    return 1


def test_kept():
    # A comment and a blank line change no statement.

    assert helper() == 1


def test_edited():
    assert helper() == 2


def test_added():
    assert helper() == 2


class TestGroup:
    def test_method(self):
        assert helper() == 1

    def test_method_edited(self):
        assert helper() == 2
'''


@pytest.mark.parametrize(
    ("class_path", "name", "changed"),
    [
        ((), "test_kept", False),
        ((), "test_edited", True),
        ((), "test_added", True),
        (("TestGroup",), "test_method", False),
        (("TestGroup",), "test_method_edited", True),
        ((), "test_missing_from_head", True),
        (("TestOther",), "test_method", True),
    ],
    ids=[
        "comment-only",
        "body-edited",
        "added",
        "method-unchanged",
        "method-edited",
        "not-in-head",
        "other-class",
    ],
)
def test_a_test_is_changed_when_its_function_differs_or_is_new(
    class_path: tuple[str, ...], name: str, changed: bool
) -> None:
    """A test is unchanged only when its function of the base has the same statements, whatever
    the layout and comments, and a test the head does not hold is not known unchanged."""
    assert is_test_changed(class_path, name, parse_tests(BASE), parse_tests(HEAD)) is changed


@pytest.mark.parametrize(
    "head",
    [
        HEAD.replace("return 1", "return 2", 1),
        HEAD.replace("import pytest", "import pytest\nimport os", 1),
        HEAD.replace("def helper():", "@pytest.fixture\ndef helper():", 1),
    ],
    ids=["helper-body", "import", "decorator"],
)
def test_a_change_around_the_tests_makes_every_test_changed(head: str) -> None:
    """A helper, import or fixture that changes is code that each test of the file runs, so a
    test that fails on base after it is no test the fix left alone."""
    assert is_test_changed((), "test_kept", parse_tests(BASE), parse_tests(head)) is True


@pytest.mark.parametrize(
    ("base", "head"),
    [(None, HEAD), (BASE, None), ("def test_kept(:\n", HEAD), (BASE, "def test_kept(:\n")],
    ids=["new-file", "no-head", "base-cannot-parse", "head-cannot-parse"],
)
def test_a_test_with_a_source_that_cannot_be_compared_is_changed(
    base: str | None, head: str | None
) -> None:
    """The check refuses a replay for a test it knows to be unchanged only."""
    assert is_test_changed((), "test_kept", parse_tests(base), parse_tests(head)) is True


@pytest.mark.parametrize(
    ("base", "head", "changed"),
    [
        (BASE, f"# A comment.\n{BASE}\n\n", False),
        (BASE, HEAD, True),
        (BASE, BASE.replace("import pytest", "import pytest\nimport os", 1), True),
        (None, HEAD, True),
        (BASE, None, True),
        ("def test_kept(:\n", HEAD, True),
    ],
    ids=["comment-only", "test-edited", "import", "new-file", "no-head", "base-cannot-parse"],
)
def test_a_file_is_changed_when_its_syntax_tree_differs_or_is_new(
    base: str | None, head: str | None, changed: bool
) -> None:
    """A collection error names a whole file and no test (#6372), so the check asks whether the
    file changed: a comment or a blank line changes no file, and a file that is new or that a
    parse does not hold is not known unchanged."""
    assert is_file_changed(parse_tests(base), parse_tests(head)) is changed


# A check module of `tests/gate/k8s_checks/` at the merge base (#6456).
GATE_BASE = '''\
"""Checks of the gateway manifests."""

from pathlib import Path

import pytest
import yaml

GATEWAY_DIR = Path("k8s/gateway")
SERVICE_MONITOR = GATEWAY_DIR / "servicemonitor.yaml"

# The labels that no query reads.
DROPPED_LABELS = ("client_ip", "user_agent")


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_kept_rule():
    assert _load(GATEWAY_DIR / "config.yaml")["drop"] == list(DROPPED_LABELS)


def check_old_rule():
    assert _load(SERVICE_MONITOR)["drop"] == list(DROPPED_LABELS)


@pytest.mark.parametrize("port", [80, 443])
def check_ports(port):
    assert port in _load(GATEWAY_DIR / "service.yaml")["ports"]
'''

OLD_RULE = """\
def check_old_rule():
    assert _load(SERVICE_MONITOR)["drop"] == list(DROPPED_LABELS)


"""
PORTS = """\


@pytest.mark.parametrize("port", [80, 443])
def check_ports(port):
    assert port in _load(GATEWAY_DIR / "service.yaml")["ports"]
"""
MONITOR = 'SERVICE_MONITOR = GATEWAY_DIR / "servicemonitor.yaml"\n'
COMMENT = "# The labels that no query reads."


def _without(source: str, *parts: str) -> str:
    """`source` with each of `parts` taken out."""
    for part in parts:
        assert part in source
        source = source.replace(part, "", 1)
    return source


# The fix of #6439: it deletes a check and the constant that only that check read, and it changes
# the text of a comment.
ONLY_DELETED = _without(GATE_BASE, OLD_RULE, MONITOR).replace(COMMENT, "# Excluded at the source.")
PATH_IMPORT = "from pathlib import Path\n"
# A cached helper that only the deleted check calls, and the import of its decorator.
CACHED_HELPER = """\
@functools.cache
def _monitor():
    return _load(SERVICE_MONITOR)


"""
PROJECT_IMPORT = "from tests.support.paths import REPO_ROOT\n"
PACKAGE_IMPORT = "import tests.support.paths\n"


def _before_old_rule(source: str, statement: str) -> str:
    """`source` with `statement` put just before `check_old_rule`."""
    return source.replace(OLD_RULE, f"{statement}\n\n{OLD_RULE}", 1)


@pytest.mark.parametrize(
    ("base", "head", "deleted"),
    [
        (GATE_BASE, ONLY_DELETED, ("gateway.check_old_rule",)),
        (GATE_BASE, _without(GATE_BASE, PORTS), ("gateway.check_ports",)),
        (
            GATE_BASE,
            _without(GATE_BASE, OLD_RULE, MONITOR, PORTS),
            ("gateway.check_old_rule", "gateway.check_ports"),
        ),
        (
            GATE_BASE,
            ONLY_DELETED.replace('"""Checks of the gateway', '"""Checks of the', 1),
            ("gateway.check_old_rule",),
        ),
        (
            _before_old_rule(GATE_BASE, CACHED_HELPER).replace(
                PATH_IMPORT, f"import functools\n{PATH_IMPORT}", 1
            ),
            ONLY_DELETED,
            ("gateway.check_old_rule",),
        ),
        (
            GATE_BASE.replace(PATH_IMPORT, f"{PATH_IMPORT}{PACKAGE_IMPORT}{PROJECT_IMPORT}", 1),
            ONLY_DELETED.replace(PATH_IMPORT, f"{PATH_IMPORT}{PACKAGE_IMPORT}", 1),
            ("gateway.check_old_rule",),
        ),
    ],
    ids=[
        "check-constant-comment",
        "parametrized-check",
        "two-checks-in-order",
        "docstring",
        "cached-helper-and-standard-import",
        "project-import-that-the-head-keeps",
    ],
)
def test_a_module_that_only_loses_checks_names_them(
    base: str, head: str, deleted: tuple[str, ...]
) -> None:
    """A gate check module whose head keeps the statements of its base in order, and leaves out
    only checks and names that the head does not use, names each deleted check as the gate runner
    names a case. A comment, a blank line and the module docstring change nothing (#6456)."""
    assert only_deleted_checks("gateway", base, head) == deleted


REBOUND = 'DROPPED_LABELS = ("client_ip", "user_agent")\n'
REBINDING = 'DROPPED_LABELS = ("client_ip",)\n'
CALL = 'yaml.add_constructor("!env", lambda loader, node: "")\n'
GATEWAY_DIR = 'GATEWAY_DIR = Path("k8s/gateway")\n'
# Left-out statements that run code at import, which can set state that a kept case reads.
RUNS_CODE = {
    "left-out-assigned-call": f"_ = {CALL}",
    "left-out-call-decorator": '@pytest.fixture(autouse=True)\ndef _env():\n    return ""\n',
    "left-out-plain-decorator": '@REGISTRY.register\ndef _env():\n    return ""\n',
    "left-out-call-in-mark-argument": (
        '@pytest.mark.parametrize("port", _ports())\ndef check_more_ports(port):\n    assert port\n'
    ),
    "left-out-call-in-functools-argument": (
        '@functools.lru_cache(maxsize=_size())\ndef _env():\n    return ""\n'
    ),
    "left-out-default-call": (
        'def _env(strict=os.environ.setdefault("GATE_STRICT", "1")):\n    return strict\n'
    ),
    "left-out-class-with-base": "class _Loader(yaml.SafeLoader):\n    pass\n",
    "left-out-class-body-call": 'class _Env:\n    STRICT = os.environ.setdefault("GATE_STRICT", "1")\n',
    "left-out-project-import": "import tests.support.strict\n",
    "left-out-relative-import": "from . import _strict\n",
}
# A second definition of a kept check, which the first one does not run.
KEPT_AGAIN = """

def check_kept_rule():
    assert _load(GATEWAY_DIR / "values.yaml")
"""


@pytest.mark.parametrize(
    ("base", "head"),
    [
        (
            GATE_BASE,
            _without(GATE_BASE, OLD_RULE).replace('"config.yaml"', '"values.yaml"', 1),
        ),
        (
            GATE_BASE,
            _without(GATE_BASE, OLD_RULE, MONITOR)
            + '\n\ndef check_new_rule():\n    assert _load(GATEWAY_DIR / "config.yaml")\n',
        ),
        (
            GATE_BASE,
            _without(GATE_BASE, OLD_RULE, MONITOR).replace(
                'encoding="utf-8"', 'encoding="ascii"', 1
            ),
        ),
        (
            GATE_BASE,
            _without(GATE_BASE, OLD_RULE, MONITOR).replace("[80, 443]", "[80]", 1),
        ),
        (
            GATE_BASE,
            _without(GATE_BASE, OLD_RULE, MONITOR).replace("import yaml", "import os\nimport yaml"),
        ),
        (GATE_BASE, _without(GATE_BASE, OLD_RULE, MONITOR, PORTS).replace(COMMENT, PORTS)),
        (GATE_BASE, _without(ONLY_DELETED, GATEWAY_DIR)),
        (GATE_BASE.replace(REBOUND, REBOUND + REBINDING), ONLY_DELETED),
        (GATE_BASE.replace(REBOUND, REBOUND + CALL), ONLY_DELETED),
        (
            GATE_BASE.replace(PATH_IMPORT, f"from __future__ import annotations\n{PATH_IMPORT}"),
            ONLY_DELETED,
        ),
        (GATE_BASE + KEPT_AGAIN, GATE_BASE),
        (GATE_BASE, GATE_BASE.replace(COMMENT, "# Excluded at the source.")),
        (None, ONLY_DELETED),
        (GATE_BASE, None),
        ("def check_old_rule(:\n", ONLY_DELETED),
        (GATE_BASE, "def check_kept_rule(:\n"),
        *(
            (_before_old_rule(GATE_BASE, statement), ONLY_DELETED)
            for statement in RUNS_CODE.values()
        ),
    ],
    ids=[
        "other-check-changed",
        "check-added",
        "helper-changed",
        "parametrize-label-changed",
        "import-added",
        "statement-moved",
        "left-out-name-still-used",
        "left-out-rebinding-of-a-used-name",
        "left-out-top-level-call",
        "left-out-future-import",
        "deleted-redefinition-of-a-kept-check",
        "no-check-deleted",
        "new-module",
        "no-head",
        "base-cannot-parse",
        "head-cannot-parse",
        *RUNS_CODE,
    ],
)
def test_a_module_that_does_more_than_lose_checks_names_none(
    base: str | None, head: str | None
) -> None:
    """A module that adds, changes or moves a statement, that leaves out a statement that a kept
    case can still see or that runs code at import, or that a side does not hold or parse, names
    no deleted check, so its gate row still needs a case that proves the fix (#6456)."""
    assert only_deleted_checks("gateway", base, head) == ()


@pytest.mark.parametrize(
    ("base", "deleted"),
    [
        (GATE_BASE, ("gateway.check_kept_rule", "gateway.check_old_rule", "gateway.check_ports")),
        (None, ()),
        ("def check_old_rule(:\n", ()),
    ],
    ids=["checks-in-order", "no-base", "base-cannot-parse"],
)
def test_a_deleted_module_names_each_check_of_its_base(
    base: str | None, deleted: tuple[str, ...]
) -> None:
    """A gate check module that the fix deletes names each check of its base, in order, as the
    gate runner names a case (#6456)."""
    assert deleted_module_checks("gateway", base) == deleted
