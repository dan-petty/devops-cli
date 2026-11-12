"""The settings load reads a config file as YAML 1.2, the version that a settings save writes (#4481).

A save writes the file with ruamel.yaml. YAML 1.2 reads a bare `off`, `on`, `yes` or `no` as a
string. YAML 1.1 reads them as bools, and a bare `12:30` as the number 750. So a value that a save
wrote changed type at the next load, and the load stopped. A bare `true` is a bool in both
versions, so a mode setting still refuses it.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import load_settings, reset_settings_cache
from devops_cli.exceptions import ConfigurationError

_CREDENTIAL = "FAKE-value"


def _add(config_path: Path, text: str) -> None:
    """Add `text`, which holds top-level keys that the file does not hold, to the active config
    file. The keys of the floor stay, so the load reaches no service."""
    config_path.write_text(config_path.read_text(encoding="utf-8") + text, encoding="utf-8")
    reset_settings_cache()


@pytest.mark.parametrize("mode", ["off", "on"])
def test_a_bare_mode_of_the_intake_loads_as_the_mode(
    isolate_devops_cli_config: Path, mode: str
) -> None:
    _add(isolate_devops_cli_config, f"roadmap:\n  intake:\n    jev: {mode}\n")

    assert load_settings().roadmap.intake.jev == mode


def test_a_bare_off_for_a_decision_point_loads_as_the_mode_off(
    isolate_devops_cli_config: Path,
) -> None:
    _add(isolate_devops_cli_config, "roadmap:\n  decisions:\n    stage.verify_screen: off\n")

    assert load_settings().roadmap.decisions == {"stage.verify_screen": "off"}


def test_a_yaml_bool_for_the_intake_mode_is_refused(isolate_devops_cli_config: Path) -> None:
    _add(isolate_devops_cli_config, "roadmap:\n  intake:\n    jev: true\n")

    with pytest.raises(ValidationError) as refused:
        load_settings()

    assert [error["loc"] for error in refused.value.errors()] == [("roadmap", "intake", "jev")]


def test_a_key_that_a_mapping_holds_two_times_stops_the_load_and_quotes_no_text(
    isolate_devops_cli_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """YAML 1.2 refuses a duplicate key. YAML 1.1 kept the last value with no message. The error
    has no cause and no context, and no frame of its traceback holds the text of the file."""
    isolate_devops_cli_config.write_text(
        f"ai:\n  provider: ollama\n  provider: {_CREDENTIAL}\n", encoding="utf-8"
    )
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as raised:
        load_settings()

    error = raised.value
    shown = "".join(
        traceback.TracebackException.from_exception(error, capture_locals=True).format()
    )
    captured = capsys.readouterr()
    assert (error.message, error.__cause__, error.__context__) == (
        f"Cannot load the settings: {isolate_devops_cli_config} is not valid YAML "
        "(DuplicateKeyError) at line 3, column 3.",
        None,
        None,
    )
    assert [text for text in (shown, captured.out, captured.err) if _CREDENTIAL in text] == []
