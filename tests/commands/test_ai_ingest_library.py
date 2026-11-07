"""`devops ai ingest library`: arguments, output and exit codes (#1329)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_an_installed_package_is_saved_as_a_contract_file(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    result = cli("ai", "ingest", "library", "pydantic", "--max-depth", 1, "--output-dir", tmp_path)

    assert (
        result.exit_code,
        "pydantic" in result.output,
        (tmp_path / "pydantic.json").is_file(),
    ) == (0, True, True)


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_the_json_format_prints_the_contract_as_json(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    result = cli(
        "ai",
        "ingest",
        "library",
        "pydantic",
        "--max-depth",
        1,
        "--output-dir",
        tmp_path,
        "--format",
        "json",
    )

    assert (result.exit_code, '"package_name": "pydantic"' in result.output) == (0, True)


def test_a_package_that_is_not_installed_exits_with_an_error(cli: Callable[..., Any]) -> None:
    result = cli("ai", "ingest", "library", "nonexistent_pkg_xyz_999")

    assert result.exit_code != 0
