"""`devops roadmap registries` (#3332): the command layer of the test registry audit.

The audit rules are tested in `tests/roadmap/test_registry_audit.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.dry_run import get_dry_run_class
from devops_cli.lang import HELP

Cli = Callable[..., Any]


def _write_module(root: Path, name: str, source: str) -> Path:
    """One module of the tree under audit: `<root>/tests/<name>`."""
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    path = tests_dir / name
    path.write_text(source, encoding="utf-8")
    return path


def test_the_registries_help_texts_exist() -> None:
    """The catalog holds the command help and the `--path` help."""
    assert HELP.roadmap.registries.strip()
    assert HELP.roadmap.registries_path.strip()


def test_the_table_lists_each_entry_of_a_tree(cli: Cli, tmp_path: Path) -> None:
    """Each declared entry is one row with its token, its kind, its target path and its source
    `path:line`."""
    _write_module(
        tmp_path,
        "test_plain.py",
        'REGISTRY_COUNTS = (("name", "stage_requests", "src/x.py"),)\n',
    )

    result = cli(["roadmap", "registries", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    for text in ("stage_requests", "name", "src/x.py", "tests/test_plain.py:1"):
        assert text in result.output


def test_the_json_output_lists_each_entry(cli: Cli, tmp_path: Path) -> None:
    """`--json` parses and holds one object per entry with its token, kind, target path and
    source."""
    _write_module(
        tmp_path,
        "test_plain.py",
        'REGISTRY_COUNTS = (("name", "stage_requests", "src/x.py"),)\n',
    )

    result = cli(["roadmap", "registries", "--path", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entries"] == [
        {
            "token": "stage_requests",
            "kind": "name",
            "path": "src/x.py",
            "source": "tests/test_plain.py:1",
        }
    ]
    assert payload["findings"] == []


def test_a_valid_tree_exits_zero_and_prints_the_count(cli: Cli, tmp_path: Path) -> None:
    """A tree whose declarations are valid and whose ratchet assertions are all covered exits 0
    and prints the count of valid entries."""
    _write_module(
        tmp_path,
        "test_valid.py",
        'REGISTRY_COUNTS = (("table", "TABLE", "src/x.py"),)\n'
        'TABLE = ("a", "b", "c")\n'
        "assert len(TABLE) == 3\n",
    )

    result = cli(["roadmap", "registries", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Valid entries: 1. No ratchet assertion lacks a declaration." in result.output


def test_a_ratchet_assertion_with_no_declaration_exits_one(cli: Cli, tmp_path: Path) -> None:
    """A length ratchet with no declaration is reported with its `path:line` and exits 1."""
    _write_module(
        tmp_path,
        "test_ratchet.py",
        'TABLE = ("a", "b", "c")\nassert len(TABLE) == 3\n',
    )

    result = cli(["roadmap", "registries", "--path", str(tmp_path)])

    assert result.exit_code == 1
    assert "tests/test_ratchet.py:2" in result.output


def test_a_computed_declaration_exits_one(cli: Cli, tmp_path: Path) -> None:
    """A declaration that is not a plain literal is reported with its `path:line` and exits 1."""
    _write_module(tmp_path, "test_computed.py", "REGISTRY_COUNTS = build()\n")

    result = cli(["roadmap", "registries", "--path", str(tmp_path)])

    assert result.exit_code == 1
    assert "tests/test_computed.py:1" in result.output


def test_the_command_lists_the_four_declaring_modules(cli: Cli) -> None:
    """On this repository the command lists the declarations of the four modules that #3254
    added."""
    result = cli(["roadmap", "registries"])

    assert result.exit_code in (0, 1), result.output
    for path in (
        "tests/roadmap/test_roadmap_dry_runs.py",
        "tests/roadmap/test_roadmap_limit_classes.py",
        "tests/support/fakes/roadmap_store.py",
        "tests/telemetry/test_telemetry_instruments.py",
    ):
        assert path in result.output


def test_the_command_declares_the_no_external_request_class() -> None:
    """`devops roadmap registries` reads local files and sends no request."""
    from devops_cli.commands.roadmap import registries_cmd

    assert get_dry_run_class(registries_cmd) == "no-external-request"
