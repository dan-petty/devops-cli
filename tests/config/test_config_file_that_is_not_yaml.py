"""A config file that is not valid YAML stops the settings from loading with an error that names the
file, the line and the column, and that quotes no text of the file (#1468).

The error of PyYAML quotes the line where the parser stopped, and the `buffer` of its mark holds the
full text of the file. A malformed line is where a pasted credential usually is. The safe loader of
PyYAML also raises `ValueError`, `KeyError` or `AttributeError` for a tagged value that it cannot
build, with the value in the message, and the decode of a file that is not UTF-8 raises
`UnicodeDecodeError`, whose `object` holds the bytes of the file.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest

from devops_cli.config.settings import load_settings, reset_settings_cache
from devops_cli.exceptions import ConfigurationError

_CREDENTIAL = "FAKE-value"
_NOT_YAML = f"ai:\n  api_key: {_CREDENTIAL}: x\n"


def _load_error() -> tuple[ConfigurationError, str]:
    """The error of a load of the settings, and its traceback with the local variables of each
    frame from this function to the frame that raised it. The test that calls this function holds
    the text of the file, so its frame is not in the traceback."""
    reset_settings_cache()
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    error = raised.value
    shown = traceback.TracebackException.from_exception(error, capture_locals=True)
    return error, "".join(shown.format())


def test_a_config_file_that_is_not_yaml_names_its_file_line_and_column_and_quotes_no_text(
    isolate_devops_cli_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The error has no cause and no context, so no traceback and no tool that walks the chain
    gets the error of PyYAML. No frame of the traceback holds the error or its mark."""
    isolate_devops_cli_config.write_text(_NOT_YAML, encoding="utf-8")

    error, shown = _load_error()

    captured = capsys.readouterr()
    assert (error.message, error.exit_code, error.error_code) == (
        f"Cannot load the settings: {isolate_devops_cli_config} is not valid YAML (ScannerError) "
        "at line 2, column 22.",
        1,
        "CONFIGURATION_ERROR",
    )
    assert (error.__cause__, error.__context__) == (None, None)
    assert [text for text in (shown, captured.out, captured.err) if _CREDENTIAL in text] == []


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        pytest.param(f"ai:\n  api_key: !!int {_CREDENTIAL}\n".encode(), "ValueError", id="int"),
        pytest.param(f"ai:\n  api_key: !!bool {_CREDENTIAL}\n".encode(), "KeyError", id="bool"),
        pytest.param(
            f"ai:\n  api_key: !!timestamp {_CREDENTIAL}\n".encode(),
            "AttributeError",
            id="timestamp",
        ),
        pytest.param(
            f"ai:\n  api_key: {_CREDENTIAL}\xe9\n".encode("latin-1"),
            "UnicodeDecodeError",
            id="not-utf-8",
        ),
    ],
)
def test_a_config_file_that_the_yaml_loader_cannot_load_names_its_file_and_quotes_no_text(
    isolate_devops_cli_config: Path,
    capsys: pytest.CaptureFixture[str],
    content: bytes,
    error_type: str,
) -> None:
    """These errors have no mark, so the message names the file and the type of the error. The
    error of `!!bool` quotes the value in lowercase, so the check ignores the case."""
    isolate_devops_cli_config.write_bytes(content)

    error, shown = _load_error()

    captured = capsys.readouterr()
    assert (error.message, error.__cause__, error.__context__) == (
        f"Cannot load the settings: {isolate_devops_cli_config} is not valid YAML ({error_type}).",
        None,
        None,
    )
    assert [
        text
        for text in (shown, captured.out, captured.err)
        if _CREDENTIAL.casefold() in text.casefold()
    ] == []
