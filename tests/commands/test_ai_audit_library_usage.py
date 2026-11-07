"""`devops ai audit-library-usage`: arguments, output, report file and exit codes (#1329)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import reset_settings_cache
from tests.support.library_contracts import write_demo_contract, write_demo_workspace


@pytest.fixture
def analysis_dir_at(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], None]:
    """Give `data.analysis_dir` the path, through its environment variable as the floor does."""

    def point(path: Path) -> None:
        monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(path))
        reset_settings_cache()

    return point


def _arguments(tmp_path: Path) -> list[str]:
    """The arguments that point the command at the demo contract and a one-file workspace."""
    contracts_dir = tmp_path / "libraries"
    write_demo_contract(contracts_dir)
    workspace = write_demo_workspace(
        tmp_path, "from demolib import compute\ndef main(): compute(1)\n"
    )
    return ["--contracts-dir", str(contracts_dir), "--dir", str(workspace)]


def test_the_json_flag_prints_the_report_counts(cli: Callable[..., Any], tmp_path: Path) -> None:
    result = cli("ai", "audit-library-usage", *_arguments(tmp_path), "--json")

    data = json.loads(result.stdout)
    assert (result.exit_code, data["files_scanned"], data["breaking_count"]) == (0, 1, 0)


def test_the_report_is_saved_in_the_analysis_directory_and_the_text_output_names_it(
    cli: Callable[..., Any], analysis_dir_at: Callable[[Path], None], tmp_path: Path
) -> None:
    analysis_dir = tmp_path / "out"
    analysis_dir_at(analysis_dir)

    result = cli("ai", "audit-library-usage", *_arguments(tmp_path))

    assert (
        result.exit_code,
        (analysis_dir / "api_drift_report.json").is_file(),
        "saved to" in result.output,
        "api_drift_report.json" in result.output,
    ) == (0, True, True, True)


def test_a_report_that_cannot_be_saved_is_named_in_the_text_output(
    cli: Callable[..., Any], analysis_dir_at: Callable[[Path], None], tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    analysis_dir_at(blocker)

    result = cli("ai", "audit-library-usage", *_arguments(tmp_path))

    assert (result.exit_code, "Could not write" in result.output) == (0, True)


def test_a_report_that_cannot_be_saved_does_not_change_the_json_output(
    cli: Callable[..., Any], analysis_dir_at: Callable[[Path], None], tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    analysis_dir_at(blocker)

    result = cli("ai", "audit-library-usage", *_arguments(tmp_path), "--json")

    assert (result.exit_code, json.loads(result.stdout)["files_scanned"]) == (0, 1)
