"""The construct gate check reports every escape of a committed tree, with no program started.

`tests/gate/construct_gate.py` runs as part of the `constructs` row of `devops ci`
(#2164). These cases give it a small tree and the names of its tracked files, so git and ast-grep
do not start.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_AST_GREP_SCAN_ARGS
from tests.gate.construct_gate import (
    CONST_AST_GREP_RULE_FILES,
    CONST_BANNED_HAND_ROLLED_APIS,
    VIOLATIONS,
    construct_gate_escapes,
    scan_problems,
    violation_table_problems,
)


def _edit(table: dict[str, Any], path: Sequence[str], value: object) -> None:
    """Set the key a path names inside nested tables."""
    *parents, key = path
    for name in parents:
        table = table[name]
    table[key] = value


def _complying_construct_gate_pyproject() -> dict[str, Any]:
    """Build, as a fresh dict, a pyproject.toml the construct gate meta-test accepts."""
    lint = {
        "select": ["E", "TID251"],
        "ignore": [],
        "flake8-tidy-imports": {
            "banned-api": {
                api: {"msg": "Parse and format addresses with ipaddress.ip_address."}
                for api in sorted(CONST_BANNED_HAND_ROLLED_APIS)
            }
        },
    }
    return {"tool": {"ruff": {"lint": lint}}}


def _populate_complying_construct_gate_tree(project: Path) -> None:
    """Populate a tmp_path tree with files complying with the construct gate."""
    (project / "sgconfig.yml").write_text(
        "ruleDirs:\n  - .ast-grep/rules\ntestConfigs:\n  - testDir: .ast-grep/rule-tests\n",
        encoding="utf-8",
    )
    (project / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: ast-grep-scan\n"
        f"        entry: uv run ast-grep {' '.join(CONST_AST_GREP_SCAN_ARGS)}\n",
        encoding="utf-8",
    )
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (project / "tests").mkdir(parents=True, exist_ok=True)
    (project / "tests" / "test_app.py").write_text("x = 1\n", encoding="utf-8")
    (project / ".gitignore").write_text("target/\n", encoding="utf-8")

    rules_dir = project / ".ast-grep" / "rules"
    tests_dir = project / ".ast-grep" / "rule-tests"
    rules_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    for rid, files in CONST_AST_GREP_RULE_FILES.items():
        (rules_dir / f"{rid}.yml").write_text(
            f"id: {rid}\nlanguage: python\nseverity: error\nfiles: {list(files)}\nmessage: msg\n"
            "rule:\n  pattern: $X\n",
            encoding="utf-8",
        )
        (tests_dir / f"{rid}-test.yml").write_text(
            f"id: {rid}\nvalid:\n  - 'x = 1'\ninvalid:\n  - 'y = 2'\n",
            encoding="utf-8",
        )


_CONSTRUCT_GATE_ESCAPES = [
    pytest.param((), None, {}, [], id="complying"),
    pytest.param(
        (),
        None,
        {
            "sgconfig.yml": (
                "ruleDirs:\n  - .ast-grep/rules\ntestConfigs:\n  - testDir: .ast-grep/rule-tests\n"
                "extraKey: true\n"
            )
        },
        ["[sgconfig.yml] extraKey: outside the allowlist"],
        id="sgconfig-unlisted-key",
    ),
    pytest.param(
        (),
        None,
        {
            "sgconfig.yml": (
                "ruleDirs:\n  - .ast-grep/other\ntestConfigs:\n  - testDir: .ast-grep/rule-tests\n"
            )
        },
        ["[sgconfig.yml] ruleDirs: ['.ast-grep/other'], not ['.ast-grep/rules']"],
        id="sgconfig-ruledirs-modified",
    ),
    pytest.param(
        (),
        None,
        {
            "subdir/sgconfig.yml": "ruleDirs: []\n",
            "subdir/deeper/sgconfig.yml": "ruleDirs: []\n",
        },
        [
            "subdir/deeper/sgconfig.yml: a second sgconfig.yml",
            "subdir/sgconfig.yml: a second sgconfig.yml",
        ],
        id="second-sgconfig",
    ),
    pytest.param(
        (),
        None,
        {".ast-grep/rules/net-port-table.yml": None},
        ["net-port-table: missing from .ast-grep/rules"],
        id="rule-missing",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-custom.yml": (
                "id: net-custom\nlanguage: python\nseverity: error\nrule:\n  pattern: $X\n"
            )
        },
        ["[net-custom] outside CONST_AST_GREP_RULE_FILES"],
        id="rule-unlisted",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: warning\nfiles: ['src/**']\n"
                "rule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] severity: warning, not error"],
        id="rule-severity-not-error",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: error\nfiles: [src/ai/**]\n"
                "rule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] files: ['src/ai/**'], not ['src/**']"],
        id="rule-files-narrowed",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: error\nrule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] files: None, not ['src/**']"],
        id="rule-files-missing",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/test-elapsed-upper-bound.yml": (
                "id: test-elapsed-upper-bound\nlanguage: python\nseverity: error\n"
                "files: ['src/**']\nrule:\n  pattern: $X\n"
            )
        },
        ["[test-elapsed-upper-bound] files: ['src/**'], not ['tests/**']"],
        id="test-rule-files-moved",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: error\nfiles: ['src/**']\n"
                "ignores: [src]\nrule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] ignores: outside the allowlist"],
        id="rule-ignores-set",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rule-tests/net-port-table-test.yml": "id: net-port-table\ninvalid:\n  - 'x = 1'\n"
        },
        ["[net-port-table] has no valid case"],
        id="rule-no-valid-case",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rule-tests/net-port-table-test.yml": "id: net-port-table\nvalid:\n  - 'x = 1'\n"
        },
        ["[net-port-table] has no invalid case"],
        id="rule-no-invalid-case",
    ),
    pytest.param(
        (),
        None,
        {
            ".pre-commit-config.yaml": (
                "repos:\n  - repo: local\n    hooks:\n      - id: ast-grep-scan\n"
                "        entry: uv run ast-grep scan src\n"
            )
        },
        [
            f"ast-grep-scan hook cmd: ['uv', 'run', 'ast-grep', 'scan', 'src'], "
            f"not {['uv', 'run', 'ast-grep', *CONST_AST_GREP_SCAN_ARGS]}"
        ],
        id="precommit-scan-cmd-changed",
    ),
    pytest.param(
        (),
        None,
        {".pre-commit-config.yaml": "repos: []\n"},
        ["ast-grep-scan hook: missing from .pre-commit-config.yaml"],
        id="precommit-scan-hook-missing",
    ),
    pytest.param(
        (),
        None,
        {".gitignore": "src/app.py\n"},
        ["src/app.py: matched by .gitignore"],
        id="ignore-file-hides-source",
    ),
    pytest.param(
        (),
        None,
        {".gitignore": "tests/test_app.py\n"},
        ["tests/test_app.py: matched by .gitignore"],
        id="ignore-file-hides-a-test",
    ),
    pytest.param(
        ("lint", "select"),
        ["E"],
        {},
        ["TID251: not enforced"],
        id="tid251-unselected",
    ),
    pytest.param(
        ("lint", "ignore"),
        ["TID251"],
        {},
        ["TID251: not enforced"],
        id="tid251-ignored",
    ),
    pytest.param(
        ("lint", "per-file-ignores"),
        {"src/*": ["TID251"]},
        {},
        ["[tool.ruff.lint.per-file-ignores] src/*: waives TID251"],
        id="tid251-waived",
    ),
    pytest.param(
        ("lint", "flake8-tidy-imports", "banned-api"),
        {"socket.inet_ntoa": {"msg": "x"}},
        {},
        [
            "socket.inet_aton: missing from flake8-tidy-imports.banned-api",
            "socket.inet_ntop: missing from flake8-tidy-imports.banned-api",
            "socket.inet_pton: missing from flake8-tidy-imports.banned-api",
        ],
        id="banned-api-missing",
    ),
]


def _tracked(project: Path) -> list[str]:
    """Name every file of the tree as tracked, as a commit of the tree would hold it."""
    return sorted(p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file())


@pytest.mark.parametrize("path, value, files, expected", _CONSTRUCT_GATE_ESCAPES)
def test_every_construct_gate_escape_is_reported(
    tmp_path: Path,
    path: Sequence[str],
    value: object,
    files: Mapping[str, str | None],
    expected: list[str],
) -> None:
    """Every way to bypass the construct gate without detection is reported (#1107, #1902)."""
    _populate_complying_construct_gate_tree(tmp_path)
    pyproject = _complying_construct_gate_pyproject()
    if path:
        _edit(pyproject["tool"]["ruff"], path, value)
    for name, content in files.items():
        dest = tmp_path / name
        if content is None:
            if dest.exists():
                dest.unlink()
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    assert construct_gate_escapes(pyproject, tmp_path, _tracked(tmp_path)) == expected


def test_a_second_sgconfig_that_git_does_not_track_is_not_reported(tmp_path: Path) -> None:
    """Scratch under `.data` and a checkout nested under `.claude/worktrees` hold an `sgconfig.yml` no commit holds (#1787)."""
    _populate_complying_construct_gate_tree(tmp_path)
    tracked = _tracked(tmp_path)
    scratch = tmp_path / ".data" / "agent" / "scratch" / "astgrep" / "sgconfig.yml"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text("ruleDirs: []\n", encoding="utf-8")

    assert construct_gate_escapes(_complying_construct_gate_pyproject(), tmp_path, tracked) == []


def test_a_source_that_git_does_not_track_is_not_reported_as_hidden(tmp_path: Path) -> None:
    """A source file `.gitignore` matches but no commit holds hides nothing from the gate (#1787)."""
    _populate_complying_construct_gate_tree(tmp_path)
    tracked = _tracked(tmp_path)
    ignored = tmp_path / "src" / "target" / "scratch.py"
    ignored.parent.mkdir()
    ignored.write_text("x = 1\n", encoding="utf-8")

    assert construct_gate_escapes(_complying_construct_gate_pyproject(), tmp_path, tracked) == []


def test_the_table_of_violations_holds_the_tree_of_every_rule() -> None:
    """A rule that holds another tree than the table names, or has no violation, is reported."""
    rules = [
        {"id": rule, "files": list(files)} for rule, files in CONST_AST_GREP_RULE_FILES.items()
    ]
    moved = [{**rules[0], "files": ["tests/**"]}, *rules[1:]]

    assert (violation_table_problems(rules), len(violation_table_problems(moved))) == ([], 1)


def test_the_scan_check_names_a_rule_that_misses_its_tree_or_leaks_into_the_other() -> None:
    """A violation with no report fails, and so does a report for the twin in the other tree."""
    reported = {f"{v.tree}/v{n}.py": {v.rule} for n, v in enumerate(VIOLATIONS)}
    leaked = {**reported, "tests/o0.py": {VIOLATIONS[0].rule}}
    missed = {name: rules for name, rules in reported.items() if name != "src/v0.py"}

    assert (scan_problems(reported), scan_problems(leaked), scan_problems(missed)) == (
        [],
        ["net-port-table: reported in tests"],
        ["net-port-table: no report for a violation in src"],
    )
