"""Pre-analysis analyzes the files under review and no other file (#1919).

A review of a pull request that changed 17 files spent four minutes in pre-analysis, which calls
no model: the stage analyzed all 2,339 files of the checkout, ten files each second, at the pace
of the rate limit for model calls.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from devops_cli.ai.analyze import load_cached_analysis
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.config.defaults import DEFAULT_REVIEW_RATE_CAPACITY

_REVIEWED = ["src/app.py", "src/util.py"]


def _project(root: Path, modules: int) -> Path:
    """A project outside git with `modules` Python modules under `src/`, `_REVIEWED` among them."""
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'app'\n", encoding="utf-8")
    names = ["app", "util", *(f"mod{index}" for index in range(modules - len(_REVIEWED)))]
    for name in names:
        (root / "src" / f"{name}.py").write_text(
            f"def {name}() -> int:\n    return 1\n", encoding="utf-8"
        )
    return root


def _pre_analysis(root: Path, files: list[str]) -> list[str]:
    """Run pre-analysis of `files` as a pull request review does; the paths it returns."""
    orchestrator = ReviewPipelineOrchestrator(
        session_id="pre-analysis", target_dir=root, session_dir=root.parent / "session"
    )
    metadata = orchestrator.run_pre_analysis_refresh(
        target_dir=root, files=files, target_type="pr", target_ref="7"
    )
    return sorted(metadata)


def _summary(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if "Pre-analysis metadata for" in line]


def test_pre_analysis_analyzes_and_saves_only_the_files_under_review(tmp_path: Path) -> None:
    """Verify a review of two files of a twelve-file project returns and caches the metadata of
    those two files only."""
    root = _project(tmp_path / "app", modules=12)

    returned = _pre_analysis(root, _REVIEWED)

    cached = load_cached_analysis(root)
    assert (returned, sorted(f.path for f in cached.files) if cached else None) == (
        _REVIEWED,
        _REVIEWED,
    )


def test_pre_analysis_says_how_many_files_it_analyzed_and_how_many_it_reused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify the first review of two files analyzes both, and a second review of the same
    unchanged files reuses their cached metadata and analyzes none."""
    root = _project(tmp_path / "app", modules=12)

    _pre_analysis(root, _REVIEWED)
    first = _summary(capsys.readouterr().out)
    _pre_analysis(root, _REVIEWED)
    second = _summary(capsys.readouterr().out)

    assert (first, second) == (
        ["✓ Pre-analysis metadata for 2 file(s): 2 analyzed, 0 reused from the cache"],
        ["✓ Pre-analysis metadata for 2 file(s): 0 analyzed, 2 reused from the cache"],
    )


def test_pre_analysis_does_not_wait_for_the_model_call_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify pre-analysis of more files than the model-call rate limit lets start at once
    analyzes all of them and never waits. The limiter waits through `asyncio.sleep`, which the
    `clock` fixture leaves to the event loop, so this spy records each wait and then waits."""
    files = int(DEFAULT_REVIEW_RATE_CAPACITY) + 5
    root = _project(tmp_path / "app", modules=files)
    reviewed = sorted(str(path.relative_to(root)) for path in (root / "src").glob("*.py"))
    waits: list[float] = []
    real_sleep = asyncio.sleep

    async def recording_sleep(delay: float, result: object = None) -> object:
        if delay > 0:
            waits.append(delay)
        return await real_sleep(delay, result)

    monkeypatch.setattr(asyncio, "sleep", recording_sleep)

    returned = _pre_analysis(root, reviewed)

    assert (len(returned), waits) == (files, [])
