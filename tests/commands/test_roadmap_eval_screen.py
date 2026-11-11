"""`devops roadmap eval screen` (#4282): a dry run makes no request, and a fit from an earlier
report makes none either. The scoring is tested in
`tests/roadmap/stage/test_roadmap_stage_screen_eval.py`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.roadmap.stage.stage_eval_cases import CASES_DIRECTORY, load_cases
from devops_cli.roadmap.stage.stage_screen_eval import ScreenRow, read_split, screen_json, two_way
from tests.support.fakes.jev import JevFake
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

ROOT = REPO_ROOT


def test_the_eval_group_lists_the_screen(cli: Callable[..., Any]) -> None:
    result = cli("roadmap", "eval", "screen", "--help")

    flags = ("--reviewer", "--from", "--write-cuts", "--dry-run")
    assert (result.exit_code, [flag in result.output for flag in flags]) == (0, [True] * 4)


def test_a_dry_run_names_one_request_for_each_case_and_makes_none(
    cli: Callable[..., Any], jev: JevFake
) -> None:
    cases = len(load_cases(ROOT / CASES_DIRECTORY))

    result = cli("roadmap", "eval", "screen", "--dry-run")

    assert result.exit_code == 0
    assert f"asks Jev about {cases} case(s)" in " ".join(result.output.split())
    assert jev.requests == []


def test_a_fit_from_a_report_makes_no_request(
    cli: Callable[..., Any], jev: JevFake, tmp_path: Path
) -> None:
    names = [case.name for case in load_cases(ROOT / CASES_DIRECTORY)]
    rows = [
        ScreenRow(n, False, 2, 2, True, 1, 1, {"a": 0.5 + i / 100}) for i, n in enumerate(names)
    ]
    report = tmp_path / "report.json"
    report.write_text(
        screen_json(
            rows,
            two_way(rows, read_split(ROOT / CASES_DIRECTORY)),
            taken="now",
            jev_model="typesafe/jev-1.14",
        ),
        encoding="utf-8",
    )

    result = cli("roadmap", "eval", "screen", "--from", str(report))

    assert result.exit_code == 0
    assert "No screen can skip more than 0 of 57 reviews" in " ".join(result.output.split())
    assert jev.requests == []
