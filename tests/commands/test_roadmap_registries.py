"""`devops roadmap registries`: its table, its JSON output and its exit codes (#3332)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands import roadmap
from devops_cli.commands.roadmap import app
from devops_cli.dry_run.decorator import get_dry_run_class
from devops_cli.lang import HELP
from tests.support.paths import REPO_ROOT

runner = CliRunner()

DECLARING_PATHS = (
    "tests/roadmap/test_roadmap_dry_runs.py",
    "tests/roadmap/test_roadmap_limit_classes.py",
    "tests/support/fakes/roadmap_store.py",
    "tests/telemetry/test_telemetry_instruments.py",
)


def _module(root: Path, name: str, text: str) -> None:
    module = root / "tests" / name
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")


def test_the_registries_help_texts_exist() -> None:
    assert HELP.roadmap.registries
    assert HELP.roadmap.registries_path


def test_the_table_lists_each_entry_of_a_tree(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_one.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_", "tests/test_one.py"),)\n',
    )

    result = runner.invoke(app, ["registries", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "CONST_" in result.output
    assert "prefix" in result.output
    assert "tests/test_one.py" in result.output


def test_the_json_output_lists_each_entry(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_one.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_", "tests/test_one.py"),)\n',
    )

    result = runner.invoke(app, ["registries", "--path", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [
        {
            "token": "CONST_",
            "kind": "prefix",
            "target": "tests/test_one.py",
            "source": "tests/test_one.py:1",
        }
    ]


def test_a_valid_tree_exits_zero_and_prints_the_count(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_one.py",
        'REGISTRY_COUNTS = (("table", "WRITES", "tests/test_one.py"),)\n',
    )

    result = runner.invoke(app, ["registries", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "1" in result.output


def test_a_ratchet_assertion_with_no_declaration_exits_one(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_table.py",
        'TABLE = ("a", "b", "c")\n\ndef test_it() -> None:\n    assert len(TABLE) == 3\n',
    )

    result = runner.invoke(app, ["registries", "--path", str(tmp_path)])

    assert result.exit_code == 1, result.output
    assert "tests/test_table.py:4" in result.output


def test_the_command_lists_the_four_declaring_modules() -> None:
    result = runner.invoke(app, ["registries", "--path", str(REPO_ROOT), "--json"])

    assert result.exit_code == 1, result.output
    sources = {row["source"] for row in json.loads(result.output)}
    for path in DECLARING_PATHS:
        assert any(source.startswith(f"{path}:") for source in sources)


def test_the_command_declares_the_no_external_request_class() -> None:
    assert get_dry_run_class(roadmap.registries_cmd) == "no-external-request"
