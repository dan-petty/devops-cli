"""The `devops roadmap registries` command lists and audits the test registry declarations (#3332).

The command reads the module-level `REGISTRY_COUNTS` declarations of the test modules, prints each
entry with its token, its kind, its target path and its source `path:line`, and exits 1 on a
finding. It declares the `no-external-request` dry-run class.
"""

from __future__ import annotations

import json
from typing import Any

from devops_cli.lang import HELP
from tests.support.paths import REPO_ROOT

# The modules of the repository that declare a registry entry (#3254).
_DECLARING_MODULES = (
    "tests/roadmap/test_roadmap_dry_runs.py",
    "tests/roadmap/test_roadmap_limit_classes.py",
    "tests/support/fakes/roadmap_store.py",
    "tests/telemetry/test_telemetry_instruments.py",
)


def _write(root: Any, name: str, text: str) -> None:
    """Write one module under the `tests` folder of `root`."""
    module = root / "tests" / name
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")


def test_the_registries_help_texts_exist() -> None:
    """The command and its `--path` option have a help text, so `devops roadmap --help` lists the
    command and a person reads what `--path` chooses."""
    assert HELP.roadmap.registries.strip()
    assert HELP.roadmap.registries_path.strip()


def test_a_ratchet_assertion_with_no_declaration_exits_one(tmp_path: Any, cli: Any) -> None:
    """A length assertion on a module table that no declaration covers is a finding, so the
    command names its `path:line` and exits 1."""
    _write(
        tmp_path,
        "test_table.py",
        'TABLE = ("a", "b", "c")\n\n\ndef test_table() -> None:\n    assert len(TABLE) == 3\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 1
    assert "tests/test_table.py:5" in result.output
    assert "TABLE" in result.output


def test_an_invalid_declaration_exits_one(tmp_path: Any, cli: Any) -> None:
    """A declaration whose value is no plain literal is an error, so the command names its
    `path:line` and exits 1."""
    _write(tmp_path, "test_computed.py", "REGISTRY_COUNTS = _entries()\n")

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 1
    assert "tests/test_computed.py:1" in result.output


def test_the_table_lists_each_entry_of_a_tree(tmp_path: Any, cli: Any) -> None:
    """A declared entry reaches the table with its token, its kind, its target path and its
    source `path:line`."""
    _write(
        tmp_path,
        "test_declared.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_X_", "src/devops_cli/x.py"),)\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 0
    for text in ("CONST_X_", "prefix", "src/devops_cli/x.py", "tests/test_declared.py:1"):
        assert text in result.stdout


def test_the_json_output_lists_each_entry(tmp_path: Any, cli: Any) -> None:
    """`--json` emits one object for each entry, with the token, the kind, the target path and the
    source `path:line`."""
    _write(
        tmp_path,
        "test_declared.py",
        'REGISTRY_COUNTS = (("name", "TABLE", "src/devops_cli/x.py"),)\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path), "--json")

    assert result.exit_code == 0
    (row,) = json.loads(result.stdout)
    assert row == {
        "registry_token": "TABLE",
        "kind": "name",
        "path": "src/devops_cli/x.py",
        "source": "tests/test_declared.py:1",
    }


def test_a_valid_tree_exits_zero_and_prints_the_count(tmp_path: Any, cli: Any) -> None:
    """A tree whose declarations are plain literals and whose assertions all have a declaration
    exits 0 and names the count of valid declarations."""
    _write(
        tmp_path,
        "test_two.py",
        'REGISTRY_COUNTS = (("name", "A", "src/a.py"), ("name", "B", "src/b.py"))\n',
    )

    result = cli("roadmap", "registries", "--path", str(tmp_path))

    assert result.exit_code == 0
    assert "Valid declarations: 1" in result.stdout


def test_the_command_lists_the_four_declaring_modules(cli: Any) -> None:
    """The command discovers every module-level `REGISTRY_COUNTS` declaration of the repository:
    the four declaring modules and their seven entries, each token as written and not masked."""
    result = cli("roadmap", "registries", "--path", str(REPO_ROOT), "--json")

    rows = json.loads(result.stdout)
    assert len(rows) == 7
    assert {row["source"].rsplit(":", 1)[0] for row in rows} == set(_DECLARING_MODULES)
    for row in rows:
        assert row["source"].rsplit(":", 1)[1].isdigit()
    assert {row["registry_token"] for row in rows} >= {"INSTRUMENTS", "devops_cli_", "WRITES"}


def test_the_command_declares_the_no_external_request_class() -> None:
    """The command reads the working tree and sends no request, so it declares
    `no-external-request`."""
    from devops_cli.commands.roadmap import registries_cmd
    from devops_cli.dry_run import get_dry_run_class

    assert get_dry_run_class(registries_cmd) == "no-external-request"
