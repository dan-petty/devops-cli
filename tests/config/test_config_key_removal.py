"""A removal of a key from the config file deletes the lines of the key alone, keeps a copy of the
file and records the change, also when the settings do not load because of that key (#2201).

Before, `devops config` had no way to remove a key, so a person edited the file by hand to remove a
key that stopped every command from loading the settings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from devops_cli.config.settings import load_settings, remove_config_key, reset_settings_cache
from devops_cli.exceptions import ConfigurationError
from devops_cli.models.config import ConfigKeyRemoval
from tests.support.config_writes import written_keys
from tests.support.fakes.clock import ClockFake

_REMOVED_AT = datetime(2026, 10, 24, 23, 30, 5, tzinfo=UTC)
_STAMP = "20261024-233005"
_REMOVED_LINE = "  vllm_url: http://192.0.2.10:8000\n"
_WITH_REMOVED_KEY = f"""\
# devops-cli settings of this workstation
telemetry:
  enabled: false

ai:
  # The model of every task that does not set its own.
  provider: ollama
{_REMOVED_LINE}  model: qwen3   # the model of the chat task too
  tasks:
    chat:
      context_window: 16384

# The section of the GitHub owner.
github:
  default_org: example-org
"""


def _use(config_path: Path, text: str) -> None:
    """Make `text` the content of the active config file."""
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def _diff(path: Path, hunk: str, removed: str) -> str:
    """The unified diff, with no context lines, of a removal of the `removed` lines."""
    lines = "".join(f"-{line}\n" for line in removed.splitlines())
    return f"--- {path}\n+++ {path}\n@@ {hunk} @@\n{lines}"


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_a_removal_deletes_the_key_that_stops_the_load_and_keeps_every_other_line(
    isolate_devops_cli_config: Path, isolate_data_dir: Path, clock: ClockFake
) -> None:
    """The file before the removal is in the copy, the audit record names the removed key, and the
    settings load again."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    assert raised.value.error_code == "CONFIGURATION_ERROR"
    clock.move_to(_REMOVED_AT)
    backup = isolate_devops_cli_config.with_name(f"config.yaml.bak-{_STAMP}")

    removal = remove_config_key("ai.vllm_url")

    assert removal == ConfigKeyRemoval(
        path=str(isolate_devops_cli_config),
        key="ai.vllm_url",
        line=8,
        diff=_diff(isolate_devops_cli_config, "-8 +7,0", _REMOVED_LINE),
        backup=str(backup),
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY.replace(
        _REMOVED_LINE, ""
    )
    assert backup.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert written_keys(isolate_data_dir) == [["ai.vllm_url"]]
    assert load_settings().ai.model == "qwen3"


def test_a_removal_of_a_section_deletes_each_line_of_it(isolate_devops_cli_config: Path) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY.replace(_REMOVED_LINE, ""))

    removal = remove_config_key("ai.tasks")

    assert (removal.key, removal.line, isolate_devops_cli_config.read_text(encoding="utf-8")) == (
        "ai.tasks",
        9,
        _WITH_REMOVED_KEY.replace(_REMOVED_LINE, "").replace(
            "  tasks:\n    chat:\n      context_window: 16384\n", ""
        ),
    )


def test_a_removal_finds_a_key_whose_name_holds_a_dot(isolate_devops_cli_config: Path) -> None:
    """A model name such as `qwen3.8:27b` is one key of `ai.gateway_weights`."""
    _use(
        isolate_devops_cli_config,
        "ai:\n  gateway_weights:\n    qwen3.8:27b: 2\n    gemma4:26b: 1\n",
    )

    removal = remove_config_key("ai.gateway_weights.qwen3.8:27b")

    assert (removal.key, removal.line, isolate_devops_cli_config.read_text(encoding="utf-8")) == (
        "ai.gateway_weights.qwen3.8:27b",
        3,
        "ai:\n  gateway_weights:\n    gemma4:26b: 1\n",
    )


def test_a_dry_run_returns_the_removal_and_writes_nothing(
    isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    removal = remove_config_key("ai.vllm_url", dry_run=True)

    assert removal == ConfigKeyRemoval(
        path=str(isolate_devops_cli_config),
        key="ai.vllm_url",
        line=8,
        diff=_diff(isolate_devops_cli_config, "-8 +7,0", _REMOVED_LINE),
        backup=None,
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]
    assert written_keys(isolate_data_dir) == []


@pytest.mark.parametrize("key", ["ai.no_such_key", "ai.provider.model", "no_such_section"])
def test_a_removal_refuses_a_key_that_the_file_does_not_hold(
    isolate_devops_cli_config: Path, isolate_data_dir: Path, key: str
) -> None:
    """`ai.provider` holds a value and no keys, so the file holds no `ai.provider.model`."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key(key)

    assert (raised.value.message, raised.value.exit_code, raised.value.error_code) == (
        f"The config file {isolate_devops_cli_config} does not hold the key '{key}'. "
        "Nothing changed.",
        1,
        "CONFIGURATION_ERROR",
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]
    assert written_keys(isolate_data_dir) == []


def test_a_removal_from_a_file_that_does_not_exist_refuses_the_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    missing = project / "config.yaml"

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.vllm_url", missing)

    assert (raised.value.message, _names(project)) == (
        f"The config file {missing} does not hold the key 'ai.vllm_url'. Nothing changed.",
        [],
    )


def test_a_removal_from_a_file_that_is_not_yaml_names_the_file_and_quotes_no_line(
    isolate_devops_cli_config: Path,
) -> None:
    """The text can hold a credential, so the error quotes none of it."""
    _use(isolate_devops_cli_config, "ai:\n  api_key: FAKE-value: x\n")

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.api_key")

    assert (raised.value.message, raised.value.exit_code) == (
        f"Cannot read {isolate_devops_cli_config}: it is not valid YAML (ScannerError).",
        1,
    )


_SECRET = "FAKE-2645-value"
_WITH_SECRET = f"""\
# devops-cli settings of this workstation
ai:
  provider: ollama
  api_key: {_SECRET}
  model: qwen3   # the model of every task
"""
_REDACTED = "'***REDACTED***'"


def _copies(directory: Path) -> list[Path]:
    return sorted(directory.glob("config.yaml.bak-*"))


def _holders_of(directory: Path, text: str) -> list[str]:
    """The names of the files in `directory` that hold `text`."""
    return [path.name for path in sorted(directory.iterdir()) if text in path.read_text("utf-8")]


def test_a_removal_of_a_credential_leaves_no_file_that_holds_its_value(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """The copy shows the removed credential as a placeholder, and it keeps every other line, so
    a person can still undo the removal of another key (#2645)."""
    _use(isolate_devops_cli_config, _WITH_SECRET)
    clock.move_to(_REMOVED_AT)

    removal = remove_config_key("ai.api_key")

    assert removal.backup == str(isolate_devops_cli_config.with_name(f"config.yaml.bak-{_STAMP}"))
    assert _holders_of(isolate_devops_cli_config.parent, _SECRET) == []
    assert Path(removal.backup).read_text(encoding="utf-8") == _WITH_SECRET.replace(
        _SECRET, _REDACTED
    )


def test_a_removal_of_a_credential_redacts_it_in_each_copy_that_an_earlier_write_made(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """A write of another key before the removal copied the file with the credential in it. The
    removal redacts the credential there too, and keeps the newest ten copies."""
    _use(isolate_devops_cli_config, _WITH_SECRET)
    directory = isolate_devops_cli_config.parent
    older = [f"config.yaml.bak-20261001-0000{second:02d}" for second in range(10)]
    for name in older:
        (directory / name).write_text(_WITH_SECRET, encoding="utf-8")
    without_key = "ai:\n  provider: ollama\n"
    (directory / older[3]).write_text(without_key, encoding="utf-8")
    clock.move_to(_REMOVED_AT)

    remove_config_key("ai.api_key")

    assert [path.name for path in _copies(directory)] == [*older[1:], f"config.yaml.bak-{_STAMP}"]
    assert _holders_of(directory, _SECRET) == []
    assert (directory / older[3]).read_text(encoding="utf-8") == without_key
    assert (directory / older[4]).read_text(encoding="utf-8") == _WITH_SECRET.replace(
        _SECRET, _REDACTED
    )


def test_a_removal_of_a_section_redacts_each_credential_in_it(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    _use(isolate_devops_cli_config, f"{_WITH_SECRET}grafana:\n  token: {_SECRET}-grafana\n")
    clock.move_to(_REMOVED_AT)

    remove_config_key("ai")

    [copy] = _copies(isolate_devops_cli_config.parent)
    assert copy.read_text(encoding="utf-8") == (
        f"{_WITH_SECRET.replace(_SECRET, _REDACTED)}grafana:\n  token: {_SECRET}-grafana\n"
    )


def test_a_removal_of_a_key_that_is_no_credential_keeps_the_copy_as_the_file_was(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    _use(isolate_devops_cli_config, _WITH_SECRET)
    clock.move_to(_REMOVED_AT)

    removal = remove_config_key("ai.model")

    assert Path(removal.backup or "").read_text(encoding="utf-8") == _WITH_SECRET


def test_a_copy_of_a_credential_removal_keeps_the_mode_of_the_file(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    _use(isolate_devops_cli_config, _WITH_SECRET)
    isolate_devops_cli_config.chmod(0o600)
    clock.move_to(_REMOVED_AT)

    removal = remove_config_key("ai.api_key")

    assert Path(removal.backup or "").stat().st_mode & 0o777 == 0o600


def test_a_removal_leaves_a_copy_that_holds_no_value_to_hide_as_it_is(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """A copy with an empty credential, or with the placeholder, holds nothing to redact."""
    _use(isolate_devops_cli_config, _WITH_SECRET)
    directory = isolate_devops_cli_config.parent
    empty = "ai:\n  api_key: ''\n"
    placeholder = f"ai:\n  api_key: {_REDACTED}\n"
    (directory / "config.yaml.bak-20261001-000000").write_text(empty, encoding="utf-8")
    (directory / "config.yaml.bak-20261001-000001").write_text(placeholder, encoding="utf-8")
    clock.move_to(_REMOVED_AT)

    remove_config_key("ai.api_key")

    assert [path.read_text(encoding="utf-8") for path in _copies(directory)[:2]] == [
        empty,
        placeholder,
    ]


def test_a_removal_of_a_credential_stops_when_a_copy_is_not_yaml_and_changes_nothing(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """A copy that the command cannot read could hold the credential, so the command does not
    remove the credential from the file and leave that copy."""
    _use(isolate_devops_cli_config, _WITH_SECRET)
    directory = isolate_devops_cli_config.parent
    broken = directory / "config.yaml.bak-20261001-000000"
    broken.write_text(f"ai:\n  api_key: {_SECRET}: x\n", encoding="utf-8")
    clock.move_to(_REMOVED_AT)

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.api_key")

    assert (raised.value.message, isolate_devops_cli_config.read_text(encoding="utf-8")) == (
        f"Cannot read {broken}: it is not valid YAML (ScannerError).",
        _WITH_SECRET,
    )
    assert _SECRET not in raised.value.message


def test_a_removal_of_a_credential_drops_each_comment_that_holds_its_value(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """A note such as `# was <value>` is part of the copy, so the copy drops it. Every other
    comment stays."""
    _use(
        isolate_devops_cli_config,
        f"ai:\n  # the old key was {_SECRET}\n  api_key: {_SECRET}  # was {_SECRET}\n"
        "  # the next line holds the model\n  model: qwen3  # keep\n"
        f"github:\n  accounts:\n    - one  # {_SECRET}\n    - two  # keep too\n",
    )
    clock.move_to(_REMOVED_AT)

    remove_config_key("ai.api_key")

    [copy] = _copies(isolate_devops_cli_config.parent)
    text = copy.read_text(encoding="utf-8")
    assert _SECRET not in text
    assert yaml.safe_load(text) == {
        "ai": {"api_key": "***REDACTED***", "model": "qwen3"},
        "github": {"accounts": ["one", "two"]},
    }
    assert "- two  # keep too\n" in text
    assert "# the next line holds the model\n  model: qwen3  # keep\n" in text


@pytest.mark.parametrize(
    ("copy", "message"),
    [
        (b"ai:\n  api_key: \xff\xfe\n", "it is not valid YAML (UnicodeDecodeError)."),
        (b"- ai.api_key\n- other\n", "it does not hold a YAML mapping."),
        (f"ai.api_key={_SECRET}\n".encode(), "it does not hold a YAML mapping."),
    ],
    ids=["not-utf-8", "list", "text-line"],
)
def test_a_removal_of_a_credential_stops_when_a_copy_is_not_a_yaml_mapping(
    isolate_devops_cli_config: Path, clock: ClockFake, copy: bytes, message: str
) -> None:
    """The command cannot find a credential in such a copy, so it stops before the file changes,
    with an error that names the copy and quotes no text."""
    _use(isolate_devops_cli_config, _WITH_SECRET)
    broken = isolate_devops_cli_config.parent / "config.yaml.bak-20261001-000000"
    broken.write_bytes(copy)
    clock.move_to(_REMOVED_AT)

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.api_key")

    assert raised.value.message == f"Cannot read {broken}: {message}"
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_SECRET
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml", broken.name]


def test_a_removal_of_a_credential_keeps_the_line_ends_of_each_copy(
    isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """A file with CRLF line ends gives a copy with CRLF line ends, and only the credential
    changes."""
    crlf = _WITH_SECRET.replace("\n", "\r\n")
    isolate_devops_cli_config.write_bytes(crlf.encode())
    reset_settings_cache()
    older = isolate_devops_cli_config.parent / "config.yaml.bak-20261001-000000"
    older.write_bytes(crlf.encode())
    clock.move_to(_REMOVED_AT)

    remove_config_key("ai.api_key")

    expected = crlf.replace(_SECRET, _REDACTED).encode()
    [first, second] = _copies(isolate_devops_cli_config.parent)
    assert (first.read_bytes(), second.read_bytes()) == (expected, expected)


def test_a_removal_of_a_key_from_a_yaml_merge_key_raises_configuration_error(
    isolate_devops_cli_config: Path,
) -> None:
    """A key provided via a YAML merge key cannot be pinpointed or removed without altering
    the anchor, and devops config unset stops with ConfigurationError naming the merge key."""
    text = """\
a:
  b: &d
    api_key: secret-value
ai:
  <<: *d
"""
    _use(isolate_devops_cli_config, text)

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.api_key")

    assert (
        "config.yaml" in raised.value.message,
        "merge key" in raised.value.message,
        "'api_key'" in raised.value.message,
    ) == (True, True, True)
