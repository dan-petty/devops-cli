"""A config file that is not valid YAML stops the settings from loading with an error that names the
file, the line and the column, and that quotes no text of the file (#1468).

The error of PyYAML quotes the line where the parser stopped, and the `buffer` of its mark holds the
full text of the file. A malformed line is where a pasted credential usually is.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest

from devops_cli.config.settings import load_settings, reset_settings_cache
from devops_cli.exceptions import ConfigurationError

_CREDENTIAL = "FAKE-value"
_NOT_YAML = f"ai:\n  api_key: {_CREDENTIAL}: x\n"


def test_a_config_file_that_is_not_yaml_names_its_file_line_and_column_and_quotes_no_text(
    isolate_devops_cli_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The error has no cause and no context, so no traceback and no tool that walks the chain
    gets the error of PyYAML."""
    isolate_devops_cli_config.write_text(_NOT_YAML, encoding="utf-8")
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as raised:
        load_settings()

    error = raised.value
    shown = "".join(traceback.format_exception(error))
    captured = capsys.readouterr()
    assert (error.message, error.exit_code, error.error_code) == (
        f"Cannot load the settings: {isolate_devops_cli_config} is not valid YAML (ScannerError) "
        "at line 2, column 22.",
        1,
        "CONFIGURATION_ERROR",
    )
    assert (error.__cause__, error.__context__) == (None, None)
    assert [text for text in (shown, captured.out, captured.err) if _CREDENTIAL in text] == []
