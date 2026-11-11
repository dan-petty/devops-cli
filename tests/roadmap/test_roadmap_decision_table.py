"""The table of the decision points (ADR 0020, #4501): the settings check `roadmap.decisions`
against it, and it gives the same names and cuts files as `REGISTRY`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.decision_registry import REGISTRY
from devops_cli.roadmap.decision_table import POINT_CUTS, check_modes

if TYPE_CHECKING:
    from pathlib import Path


def test_the_table_gives_the_names_and_the_cuts_files_of_the_registry() -> None:
    assert dict(POINT_CUTS) == {name: REGISTRY.point(name).cuts for name in REGISTRY.names}


def test_a_key_that_names_no_point_is_refused_and_the_points_are_named(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"demo\.typo.*demo\.point"):
        check_modes({"demo.typo": "shadow"}, {"demo.point": tmp_path / "cuts.json"})


def test_on_is_refused_for_a_point_with_no_cuts_file_and_shadow_is_not(tmp_path: Path) -> None:
    cuts = {"stage.unfitted": tmp_path / "not_fitted.json"}

    with pytest.raises(ValueError, match=r"stage\.unfitted.*not_fitted\.json"):
        check_modes({"stage.unfitted": "on"}, cuts)
    check_modes({"stage.unfitted": "shadow"}, cuts)


def test_each_point_of_the_table_has_its_cuts_file_so_it_takes_on() -> None:
    assert all(path.is_file() for path in POINT_CUTS.values())

    check_modes(dict.fromkeys(POINT_CUTS, "on"))
