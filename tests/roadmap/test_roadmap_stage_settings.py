"""The settings `roadmap.stage.filter`, `limit` and `step_tokens`, and the options that replace
them for one run (#2659)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from devops_cli.config import settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

Cli = Callable[..., Any]

DEFAULT_FILTER = ["status=ready"]


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty user config file, with the project layer absent and the variables unset."""
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_PATH", path)
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(tmp_path / "no-project-config.yaml"))
    for name in ("FILTER", "LIMIT", "STEP_TOKENS"):
        monkeypatch.delenv(f"DEVOPS_CLI_ROADMAP_STAGE_{name}", raising=False)
    settings.reset_settings_cache()
    return path


def _stage_settings() -> tuple[list[str], int, int]:
    loaded = settings.load_settings().roadmap.stage
    return loaded.filter, loaded.limit, loaded.step_tokens


def test_the_defaults_are_every_ready_item_three_items_and_forty_thousand_tokens(
    config_file: Path,
) -> None:
    assert _stage_settings() == (DEFAULT_FILTER, 3, 40000)


def test_a_config_file_and_a_variable_set_the_limit_and_the_filter(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file.write_text("roadmap:\n  stage:\n    limit: 1\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready,type=feature")

    assert _stage_settings() == (["status=ready", "type=feature"], 1, 40000)


def test_a_config_file_sets_the_filter_as_a_list(config_file: Path) -> None:
    config_file.write_text(
        "roadmap:\n  stage:\n    filter:\n      - status=ready\n      - effort=small\n",
        encoding="utf-8",
    )

    assert _stage_settings() == (["status=ready", "effort=small"], 3, 40000)


@pytest.mark.parametrize("entry", ["color=red", "ready", "type=", "=bug"])
def test_an_invalid_filter_entry_is_refused_naming_it(
    config_file: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", f"status=ready,{entry}")

    with pytest.raises(ConfigurationError, match="DEVOPS_CLI_ROADMAP_STAGE_FILTER") as refused:
        settings.load_settings()

    assert f"'{entry}'" in str(refused.value)


def test_a_filter_with_no_entry_is_refused(config_file: Path) -> None:
    config_file.write_text("roadmap:\n  stage:\n    filter: []\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="too_short"):
        settings.load_settings()


# ── The command ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def two_kinds(roadmap_store: InMemoryRoadmapStore, openspec_fake: OpenSpecFake) -> None:
    """A Ready P1 bug (#1) and a Ready P1 feature (#2)."""
    seed_stageable(roadmap_store)
    roadmap_store.seed_issue(
        "feat(roadmap): the job drops a label",
        body="The job drops a label.",
        labels=("type/feature",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))


def _plan(cli: Cli, repo: StageRepo, *args: str) -> str:
    result = cli(
        "roadmap", "stage", "--repo", STAGE_REPO, "--source", str(repo.clone), "--plan", *args
    )
    assert result.exit_code == 0, result.output
    return str(result.output)


@pytest.mark.usefixtures("keyring_store", "two_kinds", "config_file")
def test_the_command_takes_the_filter_and_the_limit_of_the_settings(
    cli: Cli,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready,type=feature")
    model_fake.answer(make_stage_proposal())

    output = _plan(cli, stage_repo)

    assert "- #2 feat(roadmap): the job drops a label: branch `feat/2-" in output
    assert "#1 " not in output


@pytest.mark.usefixtures("keyring_store", "two_kinds", "config_file")
def test_the_options_replace_the_filter_of_the_settings_for_one_run(
    cli: Cli,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready,type=feature")
    model_fake.answer(make_stage_proposal())

    output = _plan(cli, stage_repo, "--filter", "status=ready", "--filter", "type=bug")

    assert "- #1 fix(roadmap): the job drops a comment: branch `fix/1-" in output
    assert "#2 " not in output


@pytest.mark.usefixtures("keyring_store", "two_kinds", "config_file")
def test_the_limit_of_the_settings_caps_the_command_and_the_option_replaces_it(
    cli: Cli,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "1")
    model_fake.answer(make_stage_proposal())
    capped = _plan(cli, stage_repo)

    model_fake.answer(make_stage_proposal())
    model_fake.answer(make_stage_proposal())
    both = _plan(cli, stage_repo, "--limit", "2")

    assert ("#1 " in capped, "#2 " in capped) == (True, False)
    assert ("#1 " in both, "#2 " in both) == (True, True)
