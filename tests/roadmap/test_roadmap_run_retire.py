"""The start of the Service removes the clones and the snapshots of the lanes that it does not
run (#5553): they are caches, and the volume of the Service keeps them otherwise."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from devops_cli.roadmap.run import retire_lane_state

REPO = "example/roadmap"


def _make(state_dir: Path, *paths: str) -> None:
    for path in paths:
        (state_dir / path).mkdir(parents=True, exist_ok=True)
        (state_dir / path / "kept.txt").write_text("cache\n", encoding="utf-8")


def _left(state_dir: Path) -> set[str]:
    return {
        str(path.relative_to(state_dir))
        for path in state_dir.rglob("*")
        if path.is_file() or not any(path.iterdir())
    }


def test_the_start_removes_the_state_of_lanes_that_the_service_does_not_run(
    tmp_path: Path,
) -> None:
    """With the default lanes, the clone of a lane `model`, the three clones of the earlier lanes
    and the snapshot of the lane `model` go. The clone and the snapshot of `stage`, the snapshot
    of intake, `schedule.json` and the state of a repository that the Service does not manage
    stay."""
    state_dir = tmp_path / "roadmap"
    _make(
        state_dir,
        "example/roadmap/lanes/model",
        "example/roadmap/lanes/stage",
        "example/roadmap/clone",
        "example/roadmap/model-clone",
        "example/roadmap/triage-clone",
        "example/other/model-clone",
        "listing-model",
        "listing-stage",
        "listing/example",
    )
    (state_dir / "example/roadmap/schedule.json").write_text("{}\n", encoding="utf-8")

    removed = retire_lane_state(state_dir, [REPO])

    assert (sorted(str(path.relative_to(state_dir)) for path in removed), _left(state_dir)) == (
        [
            "example/roadmap/clone",
            "example/roadmap/lanes/model",
            "example/roadmap/model-clone",
            "example/roadmap/triage-clone",
            "listing-model",
        ],
        {
            "example/other/model-clone/kept.txt",
            "example/roadmap/lanes/stage/kept.txt",
            "example/roadmap/schedule.json",
            "listing-stage/kept.txt",
            "listing/example/kept.txt",
        },
    )


def test_a_group_keeps_the_clone_and_the_snapshot_of_its_lane(tmp_path: Path) -> None:
    """With `service.lanes` `{model: [stage, refine]}`, the lane `model` runs, so its clone and its
    snapshot stay, and the lane `stage` does not, so its clone and its snapshot go."""
    state_dir = tmp_path / "roadmap"
    _make(
        state_dir,
        "example/roadmap/lanes/model",
        "example/roadmap/lanes/stage",
        "listing-model",
        "listing-stage",
    )

    removed = retire_lane_state(state_dir, [REPO], {"model": ["stage", "refine"]})

    assert sorted(str(path.relative_to(state_dir)) for path in removed) == [
        "example/roadmap/lanes/stage",
        "listing-stage",
    ]


def test_a_path_that_cannot_be_removed_goes_to_the_log_and_the_start_goes_on(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A clone whose files the Service cannot remove gives one warning, and the other retired
    paths still go."""
    state_dir = tmp_path / "roadmap"
    _make(state_dir, "example/roadmap/model-clone", "listing-model")
    locked = state_dir / "example/roadmap/model-clone"
    locked.chmod(0o500)
    try:
        with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.run"):
            retire_lane_state(state_dir, [REPO])
    finally:
        locked.chmod(0o700)

    assert (
        (state_dir / "listing-model").exists(),
        (locked / "kept.txt").exists(),
        any(str(locked) in record.getMessage() for record in caplog.records),
    ) == (False, True, True)
