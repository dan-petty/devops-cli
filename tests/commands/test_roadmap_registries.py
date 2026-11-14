"""`devops roadmap registries` (#3332): the command layer of the registry audit.

The audit itself is tested in `tests/roadmap/test_registry_audit.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.commands.roadmap import registries_cmd
from devops_cli.dry_run.decorator import get_dry_run_class
from devops_cli.lang import HELP
from tests.support.paths import REPO_ROOT

Cli = Callable[..., Any]

DECLARING_MODULES = [
    "tests/roadmap/test_roadmap_dry_runs.py",
    "tests/roadmap/test_roadmap_limit_classes.py",
    "tests/support/fakes/roadmap_store.py",
    "tests/telemetry/test_telemetry_instruments.py",
]


def _write(root: Path, relative: str, text: str) -> Path:
    """Write one test module of a temporary tree and return its path."""
    module = root / "tests" / relative
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")
    return module


def test_the_registries_help_texts_exist() -> None:
    """The catalog holds the help of the subcommand and of its --path option."""
    assert HELP.roadmap.registries.strip() != ""
    assert HELP.roadmap.registries_path.strip() != ""


def test_the_table_lists_each_entry_of_a_tree(cli: Cli, tmp_path: Path) -> None:
    """The table prints the token, the kind, the target path and the source of each entry."""
    _write(
        tmp_path,
        "test_one.py",
        'REGISTRY_COUNTS = (("table", "WRITES", "tests/test_one.py"),)\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 0, result.output
    for cell in ("WRITES", "table", "tests/test_one.py", "tests/test_one.py:1"):
        assert cell in result.stdout


def test_a_valid_tree_exits_zero_and_prints_the_count(cli: Cli, tmp_path: Path) -> None:
    """A tree with no finding exits 0 and prints the count of valid declarations."""
    _write(tmp_path, "test_one.py", 'REGISTRY_COUNTS = (("name", "stage_requests", "src/x.py"),)\n')
    _write(
        tmp_path,
        "test_two.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_X_", "tests/test_two.py"),)\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert "2" in result.stderr


def test_the_json_output_lists_each_entry(cli: Cli, tmp_path: Path) -> None:
    """`--json` prints one object for each entry and nothing else on the standard output."""
    _write(
        tmp_path,
        "test_one.py",
        'REGISTRY_COUNTS = (("table", "WRITES", "tests/test_one.py"),)\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path), "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {
            "token": "WRITES",
            "kind": "table",
            "path": "tests/test_one.py",
            "source": "tests/test_one.py:1",
        }
    ]


def test_a_ratchet_assertion_with_no_declaration_exits_one(cli: Cli, tmp_path: Path) -> None:
    """A length ratchet that no entry covers warns with its path:line and exits 1."""
    _write(
        tmp_path,
        "test_ratchet.py",
        'TABLE = ("a", "b", "c")\n\n\ndef test_the_table() -> None:\n    assert len(TABLE) == 3\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 1
    assert "tests/test_ratchet.py:5" in result.stderr
    assert "TABLE" in result.stderr


def test_an_invalid_declaration_exits_one(cli: Cli, tmp_path: Path) -> None:
    """A declaration that is no plain literal reports an error with its path:line and exits 1."""
    _write(tmp_path, "test_computed.py", "REGISTRY_COUNTS = tuple()\n")

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 1
    assert "tests/test_computed.py:1" in result.stderr


def test_the_command_lists_the_four_declaring_modules(cli: Cli) -> None:
    """The audit of this repository names the four declaring modules of #3254."""
    result = cli("roadmap", "registries", "--path", str(REPO_ROOT), "--json")

    rows = json.loads(result.stdout)
    declaring = sorted({row["source"].rsplit(":", 1)[0] for row in rows})
    assert declaring == DECLARING_MODULES


def test_the_command_declares_the_no_external_request_class() -> None:
    """The dry-run class ratchet reads the class of the subcommand."""
    assert get_dry_run_class(registries_cmd) == "no-external-request"
