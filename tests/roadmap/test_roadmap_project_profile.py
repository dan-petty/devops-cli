"""The project profile and toolchain presets of the implement job (#4635).

A repository declares its toolchain preset in `.devops/roadmap.toml` on the default branch.
A repository with no such file gets the `neutral` preset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.commands import BIN_DEVOPS, BIN_UV
from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.implement.implement_scoped_ci import scoped_checks
from devops_cli.roadmap.project_profile import resolve_profile, review_tag_pattern
from devops_cli.roadmap.toolchains import DEVOPS_CLI_PRESET, NEUTRAL_PRESET
from tests.support.roadmap_stage import StageRepo

STEPS_FILE = ".devops/roadmap.toml"
CONFIG = Path("/data/cache/pre-commit-config.yaml")


def test_the_toolchain_preset_is_read_from_roadmap_toml_on_the_default_branch(
    stage_repo: StageRepo,
) -> None:
    stage_repo.track({STEPS_FILE: '[project]\ntoolchain = "devops-cli"\n'})

    profile = resolve_profile(stage_repo.clone, "origin/main")

    assert profile == DEVOPS_CLI_PRESET
    assert profile.preset.name == "devops-cli"


def test_a_commit_with_no_profile_file_resolves_to_neutral_preset(
    stage_repo: StageRepo,
) -> None:
    profile = resolve_profile(stage_repo.clone, "origin/main")

    assert profile == NEUTRAL_PRESET
    assert profile.preset.name == "neutral"

    # Scoped checks with no hooks hold no argv that names uv or devops ci
    checks_no_hooks = scoped_checks(
        "main", ["tests/test_shout.py"], config=None, preset=profile.preset
    )
    assert checks_no_hooks == []

    # Scoped checks with hooks hold only pre-push
    checks_with_hooks = scoped_checks(
        "main", ["tests/test_shout.py"], config=CONFIG, preset=profile.preset
    )
    assert len(checks_with_hooks) == 1
    assert checks_with_hooks[0].name == "pre-push"
    assert not any("devops" in part for part in checks_with_hooks[0].argv)


def test_devops_cli_preset_parity() -> None:
    checks = scoped_checks("main", ["tests/test_shout.py"], config=CONFIG, preset=DEVOPS_CLI_PRESET)

    assert [c.name for c in checks] == ["pre-push", "static", "tests"]
    assert DEVOPS_CLI_PRESET.docs_step is True
    assert DEVOPS_CLI_PRESET.archive_argv == (
        BIN_UV,
        "run",
        BIN_DEVOPS,
        "openspec",
        "archive",
        "<change>",
    )
    assert DEVOPS_CLI_PRESET.step_gates == "ruff-mypy"


def test_an_unknown_preset_name_raises_configuration_error_naming_the_file(
    stage_repo: StageRepo,
) -> None:
    stage_repo.track({STEPS_FILE: '[project]\ntoolchain = "cargo"\n'})

    with pytest.raises(ConfigurationError, match=r"\.devops/roadmap\.toml"):
        resolve_profile(stage_repo.clone, "origin/main")


def test_an_invalid_toml_file_raises_configuration_error(stage_repo: StageRepo) -> None:
    stage_repo.track({STEPS_FILE: "invalid = [toml\n"})

    with pytest.raises(ConfigurationError, match=r"\.devops/roadmap\.toml"):
        resolve_profile(stage_repo.clone, "origin/main")


def test_profile_is_read_from_commit_and_not_from_working_tree(
    stage_repo: StageRepo,
) -> None:
    stage_repo.track({STEPS_FILE: '[project]\ntoolchain = "devops-cli"\n'})
    (stage_repo.clone / STEPS_FILE).write_text(
        '[project]\ntoolchain = "neutral"\n', encoding="utf-8"
    )

    profile = resolve_profile(stage_repo.clone, "origin/main")

    assert profile == DEVOPS_CLI_PRESET


def test_the_review_table_gives_the_tag_pattern_and_the_default_is_v_star(
    stage_repo: StageRepo,
) -> None:
    """`[review] tag_pattern` configures the project review tag glob with default `v*` (#4730)."""
    assert review_tag_pattern(stage_repo.clone) == "v*"

    stage_repo.track({STEPS_FILE: '[project]\ntoolchain = "neutral"\n'})
    assert review_tag_pattern(stage_repo.clone) == "v*"

    stage_repo.track(
        {STEPS_FILE: '[project]\ntoolchain = "devops-cli"\n\n[review]\ntag_pattern = "release-*"\n'}
    )
    assert review_tag_pattern(stage_repo.clone) == "release-*"
    assert resolve_profile(stage_repo.clone, "origin/main") == DEVOPS_CLI_PRESET

    (stage_repo.clone / STEPS_FILE).write_text("[review]\nunknown = 'x'\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match=r"\.devops/roadmap\.toml"):
        review_tag_pattern(stage_repo.clone)

    (stage_repo.clone / STEPS_FILE).write_text(
        "[review]\ntag_pattern = '--exec'\n", encoding="utf-8"
    )
    with pytest.raises(ConfigurationError, match=r"\.devops/roadmap\.toml"):
        review_tag_pattern(stage_repo.clone)

    (stage_repo.clone / STEPS_FILE).write_text("invalid = [toml\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match=r"\.devops/roadmap\.toml"):
        review_tag_pattern(stage_repo.clone)
