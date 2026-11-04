"""`devops review fetch-databases`: arguments, wiring, output and exit code (#2131).

What the fetch does is in `tests/security/test_tool_databases.py`. These cases drive the command.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_OSV_DB_DIR_ENV
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_REPORT = json.dumps(
    {
        "results": [
            {
                "packages": [{"package": {"name": "idna", "version": "3.6", "ecosystem": "PyPI"}}],
            }
        ]
    }
)


@pytest.fixture
def lockfile_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tree with one lockfile, and cache directories for the two tools below `tmp_path`."""
    monkeypatch.setenv(CONST_OSV_DB_DIR_ENV, str(tmp_path / "osv"))
    monkeypatch.setenv("TRIVY_CACHE_DIR", str(tmp_path / "trivy"))
    root = tmp_path / "tree"
    root.mkdir()
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    return root


def _answer(process_fake: ProcessFake, program: str, answer: ProcessAnswer) -> None:
    def starts(call: ProcessCall) -> bool:
        return bool(call.argv) and call.argv[0] == program

    process_fake.answer(starts, answer)


def test_the_command_reports_each_database_it_fetched_and_where(
    cli: Callable[..., Any], process_fake: ProcessFake, lockfile_tree: Path, tmp_path: Path
) -> None:
    _answer(process_fake, "osv-scanner", ProcessAnswer(returncode=1, stdout=_REPORT))
    _answer(process_fake, "trivy", ProcessAnswer())
    database = tmp_path / "osv" / "osv-scalibr" / "PyPI"
    database.mkdir(parents=True)
    (database / "all.zip").write_bytes(b"advisories\n")

    result = cli("review", "fetch-databases", str(lockfile_tree))

    assert result.exit_code == 0
    assert result.output == (
        f"✓ Fetched the osv-scanner database of PyPI into {tmp_path / 'osv' / 'osv-scalibr'}.\n"
        f"✓ Fetched the Trivy database and checks into {tmp_path / 'trivy'}.\n"
    )


def test_the_command_says_when_the_tree_names_no_ecosystem(
    cli: Callable[..., Any], process_fake: ProcessFake, lockfile_tree: Path, tmp_path: Path
) -> None:
    (lockfile_tree / "uv.lock").unlink()
    _answer(process_fake, "trivy", ProcessAnswer())

    result = cli("review", "fetch-databases", str(lockfile_tree))

    assert result.exit_code == 0
    assert result.output == (
        f"! No osv-scanner database fetched: the lockfiles of {lockfile_tree} name no ecosystem that has "
        "one.\n"
        f"✓ Fetched the Trivy database and checks into {tmp_path / 'trivy'}.\n"
    )


def test_the_command_exits_with_1_and_shows_the_error_of_a_tool_that_failed(
    cli: Callable[..., Any], process_fake: ProcessFake, lockfile_tree: Path
) -> None:
    _answer(process_fake, "osv-scanner", ProcessAnswer(returncode=1, stdout=_REPORT))
    _answer(process_fake, "trivy", ProcessAnswer(returncode=1, stderr="no route to host\n"))

    result = cli("review", "fetch-databases", str(lockfile_tree))

    assert result.exit_code == 1
    assert "trivy did not fetch its database (exit code 1): no route to host" in result.output


def test_a_dry_run_lists_the_commands_and_starts_none(
    cli: Callable[..., Any], process_fake: ProcessFake, lockfile_tree: Path, tmp_path: Path
) -> None:
    result = cli("review", "fetch-databases", str(lockfile_tree), "--dry-run")

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == (
        "Dry run: no process was started. fetch-databases would run these commands, in order:"
    )
    assert [line.split()[0] for line in result.output.splitlines()[1:]] == ["1.", "2.", "3."]
    assert f"TRIVY_CACHE_DIR={tmp_path / 'trivy'} trivy fs --download-db-only --quiet" in (
        result.output
    )
    assert [call.argv for call in process_fake.calls if call.argv[0] != "git"] == []
