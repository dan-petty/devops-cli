"""A value that a validator refuses in a config file stops the command with one error line, not a
pydantic traceback (#4610)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import load_settings, reset_settings_cache
from devops_cli.exceptions import ConfigurationError

Capture = Any

_WITH_HUGE_EFFORT = """\
roadmap:
  implement:
    effort: ["huge"]
"""
_WITH_DUPLICATE_REPOS = """\
service:
  repos: ["Owner/Repo", "owner/repo"]
"""


def _use(config_path: Path, text: str) -> None:
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def _load_error() -> ConfigurationError:
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    return raised.value


def test_a_refused_effort_value_names_the_file_the_setting_and_the_reason(
    isolate_devops_cli_config: Path,
) -> None:
    _use(isolate_devops_cli_config, _WITH_HUGE_EFFORT)

    error = _load_error()

    assert error.key == "roadmap.implement.effort"
    text = str(error)
    assert "roadmap.implement.effort" in text
    assert str(isolate_devops_cli_config) in text
    assert "no effort value" in text
    assert "https://errors.pydantic.dev" not in text


def test_a_duplicate_service_repo_names_the_setting_and_the_repository(
    isolate_devops_cli_config: Path,
) -> None:
    _use(isolate_devops_cli_config, _WITH_DUPLICATE_REPOS)

    error = _load_error()

    assert error.key == "service.repos"
    assert "service.repos" in str(error)
    assert "owner/repo" in str(error).lower()


def test_the_cli_exits_1_without_a_traceback(cli: Capture, isolate_devops_cli_config: Path) -> None:
    _use(isolate_devops_cli_config, _WITH_HUGE_EFFORT)

    result = cli("roadmap", "inbox")

    assert result.exit_code == 1
    assert "roadmap.implement.effort" in result.output
    assert "Traceback (most recent call last):" not in result.output
