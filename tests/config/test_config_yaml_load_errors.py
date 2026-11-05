"""A read of a config file that PyYAML or ruamel.yaml cannot load shows no text of the file (#2451).

The settings load does this since #1468. These paths read a config file without the settings load:
the audit record of a write (`write_history`), the round trip that edits a file (`round_trip`) and
`devops config unset`. ruamel.yaml accepts a local tag such as `!vault`, and PyYAML does not. Both
parsers raise `ValueError` or `KeyError` for a tagged value that they cannot build, and the message
quotes the value. A config file can hold a credential, so the error names the file, the type of the
error and its position, and quotes no text. It has no cause and no context.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from devops_cli.config import round_trip
from devops_cli.config.write_history import _mapping, redact_credentials
from devops_cli.config.yaml_errors import load_yaml
from devops_cli.exceptions import ConfigurationError

_CREDENTIAL = "FAKE-value"
_VAULT = f"ai:\n  provider: ollama\n  api_key: !vault {_CREDENTIAL}-tag\n"
_INT = f"ai:\n  api_key: !!int {_CREDENTIAL}-int\n"
_BOOL = f"ai:\n  api_key: !!bool {_CREDENTIAL}-bool\n"
_NOT_YAML = f"ai:\n  api_key: {_CREDENTIAL}: x\n"


def _refusal(action: Callable[[], object]) -> tuple[ConfigurationError, str]:
    """The error that `action` raises, and the traceback that Python prints for it, which shows the
    message of the error and of each error in its chain."""
    with pytest.raises(ConfigurationError) as raised:
        action()
    shown = traceback.TracebackException.from_exception(raised.value)
    return raised.value, "".join(shown.format())


def _leaks(*texts: str) -> list[str]:
    """The texts that hold the credential, in any case: PyYAML quotes a `!!bool` value in lowercase."""
    return [text for text in texts if _CREDENTIAL.casefold() in text.casefold()]


def test_the_helper_names_the_file_the_type_and_the_position_of_a_marked_error() -> None:
    error, shown = _refusal(
        lambda: load_yaml(
            lambda: yaml.safe_load(_NOT_YAML), name="config.yaml", action="Cannot read"
        )
    )

    assert (error.message, error.__cause__, error.__context__) == (
        "Cannot read: config.yaml is not valid YAML (ScannerError) at line 2, column 22.",
        None,
        None,
    )
    assert _leaks(error.message, shown) == []


@pytest.mark.parametrize(
    ("parse", "error_type", "location"),
    [
        pytest.param(
            lambda: yaml.safe_load(_VAULT),
            "ConstructorError",
            " at line 3, column 12",
            id="pyyaml-tag",
        ),
        pytest.param(lambda: yaml.safe_load(_INT), "ValueError", "", id="pyyaml-int"),
        pytest.param(lambda: yaml.safe_load(_BOOL), "KeyError", "", id="pyyaml-bool"),
        pytest.param(
            lambda: yaml.safe_load(b"a: \xe9"),
            "ReaderError",
            "",
            id="pyyaml-bytes",
        ),
    ],
)
def test_the_helper_turns_each_error_of_pyyaml_into_one_error_without_text(
    parse: Callable[[], object], error_type: str, location: str
) -> None:
    error, shown = _refusal(lambda: load_yaml(parse, name="f.yaml", action="Cannot read"))

    assert (error.message, error.__cause__, error.__context__) == (
        f"Cannot read: f.yaml is not valid YAML ({error_type}){location}.",
        None,
        None,
    )
    assert _leaks(error.message, shown) == []


def test_the_helper_returns_the_value_of_a_parse_that_works() -> None:
    assert load_yaml(lambda: yaml.safe_load("a: 1\n"), name="f", action="Cannot read") == {"a": 1}


def test_the_helper_lets_an_error_that_is_not_a_load_error_go_up() -> None:
    def fail() -> object:
        raise OSError("disk")

    with pytest.raises(OSError, match="disk"):
        load_yaml(fail, name="f", action="Cannot read")


@pytest.mark.parametrize(
    "text",
    [pytest.param(_VAULT, id="tag"), pytest.param(_INT, id="int"), pytest.param(_BOOL, id="bool")],
)
def test_the_audit_record_of_a_write_quotes_no_text_of_the_file(text: str) -> None:
    error, shown = _refusal(lambda: _mapping(text.encode(), name="config.yaml"))

    assert (error.__cause__, error.__context__, _leaks(error.message, shown)) == (None, None, [])
    assert error.message.startswith("Cannot read the config file: config.yaml is not valid YAML (")


def test_the_redaction_of_a_credential_quotes_no_text_of_the_file() -> None:
    error, shown = _refusal(
        lambda: redact_credentials(_BOOL.encode(), [("ai", "api_key")], name="c.yaml")
    )

    assert (error.__cause__, error.__context__, _leaks(error.message, shown)) == (None, None, [])


@pytest.mark.parametrize("text", [pytest.param(_INT, id="int"), pytest.param(_BOOL, id="bool")])
def test_the_round_trip_quotes_no_text_of_a_file_with_a_tag_it_cannot_build(text: str) -> None:
    found, found_shown = _refusal(lambda: round_trip.find(text, "ai.provider", name="c.yaml"))
    edited, edited_shown = _refusal(
        lambda: round_trip.edit(text, {("ai", "provider"): "x"}, name="c.yaml")
    )

    assert [(e.__cause__, e.__context__) for e in (found, edited)] == [(None, None)] * 2
    assert _leaks(found.message, found_shown, edited.message, edited_shown) == []
    assert found.message.startswith("Cannot read the config file: c.yaml is not valid YAML (")
    assert edited.message.startswith("Cannot save the settings: c.yaml is not valid YAML (")


def test_unset_stops_for_a_file_with_a_local_tag_and_shows_no_text_of_it(
    isolate_devops_cli_config: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`ruamel.yaml` accepts `!vault`, and PyYAML does not. The command stops before it writes."""
    from devops_cli.config.settings import remove_config_key

    isolate_devops_cli_config.write_text(_VAULT, encoding="utf-8")

    error, shown = _refusal(lambda: remove_config_key("ai.provider"))

    captured = capsys.readouterr()
    assert (
        error.message,
        error.__cause__,
        error.__context__,
        isolate_devops_cli_config.read_text(encoding="utf-8"),
        _leaks(shown, captured.out, captured.err),
    ) == (
        f"Cannot read the config file: {isolate_devops_cli_config} is not valid YAML "
        "(ConstructorError) at line 3, column 12.",
        None,
        None,
        _VAULT,
        [],
    )


def test_the_round_trip_names_the_line_and_column_of_a_ruamel_error() -> None:
    error, shown = _refusal(lambda: round_trip.find(_NOT_YAML, "ai.provider", name="c.yaml"))

    assert (error.message, error.__cause__, error.__context__, _leaks(shown)) == (
        "Cannot read the config file: c.yaml is not valid YAML (ScannerError) at line 2, column 22.",
        None,
        None,
        [],
    )
