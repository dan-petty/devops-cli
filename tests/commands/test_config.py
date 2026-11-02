"""Verify what the `devops config` commands tell the user about the config file and its keys."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.settings import reset_settings_cache
from tests.support.config_writes import written_keys
from tests.support.fakes.clock import ClockFake

_REMOVED_LINE = "  vllm_url: http://192.0.2.10:8000\n"
_WITH_REMOVED_KEY = (
    "# devops-cli settings of this workstation\n"
    "telemetry:\n"
    "  enabled: false\n"
    "ai:\n"
    "  # The provider of every task.\n"
    "  provider: ollama\n"
    f"{_REMOVED_LINE}"
)


def _use(config_path: Path, text: str) -> None:
    """Make `text` the content of the active config file."""
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_config_init_names_the_active_config_file_it_writes(
    cli: Any, config: Any, tmp_path: Path, isolate_data_dir: Path
) -> None:
    """The wizard wrote the active config file but named the default config path (#1998). It
    writes only the keys that the answers change (#1999).

    The floor's `DEVOPS_CLI_CONFIG` makes a file under `tmp_path` the active config. An empty
    PATH holds no gh, so the wizard asks no gh question and starts no program.
    """
    active = config(github={"default_org": "old-org"})
    no_programs = tmp_path / "no-programs"
    no_programs.mkdir()
    answers = f"new-org\n{tmp_path / 'repos'}\n\n\n\n"

    result = cli("config", "init", input=answers, env={"PATH": str(no_programs)})

    named = [line for line in result.output.splitlines() if line.startswith("Config file:")]
    written = yaml.safe_load(active.read_text(encoding="utf-8"))["github"]["default_org"]
    assert (result.exit_code, named, written, written_keys(isolate_data_dir)) == (
        0,
        [f"Config file: {active}"],
        "new-org",
        [["github.default_org", "repos.base_dir"]],
    )


def test_config_unset_removes_a_key_that_stops_every_command_from_loading_the_settings(
    cli: Any, isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """`ai.vllm_url` stops `devops config get` from loading the settings. `devops config unset`
    does not load them: it removes the line of the key, keeps the comments and copies the file."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)
    clock.move_to(datetime(2026, 10, 24, 23, 30, 5, tzinfo=UTC))
    backup = isolate_devops_cli_config.with_name("config.yaml.bak-20261024-233005")

    refused = cli("config", "get", "ai.provider")
    result = cli("config", "unset", "ai.vllm_url")
    loaded = cli("config", "get", "ai.provider")

    assert (refused.exit_code, refused.output) == (
        1,
        f"✗ Unknown configuration key 'ai.vllm_url' at {isolate_devops_cli_config}:7. "
        "Release 0.2.34 removed it. Remove it with: devops config unset ai.vllm_url\n",
    )
    assert (result.exit_code, result.output) == (
        0,
        f"Removed ai.vllm_url from {isolate_devops_cli_config}:7.\n"
        f"The file before the change is in {backup}.\n",
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY.replace(
        _REMOVED_LINE, ""
    )
    assert backup.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert (loaded.exit_code, loaded.output) == (0, "ollama\n")


def test_config_unset_of_a_credential_leaves_no_file_that_holds_its_value(
    cli: Any, isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """The copy that the command names shows the removed credential as a placeholder (#2645)."""
    _use(isolate_devops_cli_config, "ai:\n  provider: ollama\n  api_key: FAKE-2645-value\n")
    clock.move_to(datetime(2026, 10, 24, 23, 30, 5, tzinfo=UTC))
    backup = isolate_devops_cli_config.with_name("config.yaml.bak-20261024-233005")

    result = cli("config", "unset", "ai.api_key")

    assert (result.exit_code, result.output) == (
        0,
        f"Removed ai.api_key from {isolate_devops_cli_config}:3.\n"
        f"The file before the change is in {backup}.\n",
    )
    assert [
        path.name
        for path in isolate_devops_cli_config.parent.iterdir()
        if "FAKE-2645" in path.read_text("utf-8")
    ] == []
    assert backup.read_text(encoding="utf-8") == (
        "ai:\n  provider: ollama\n  api_key: '***REDACTED***'\n"
    )


def test_config_get_reports_a_config_file_that_is_not_yaml_on_one_line_with_no_file_text(
    cli: Any, isolate_devops_cli_config: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`devops config get` printed the error and the traceback of PyYAML, which quote the line
    that does not parse, value included (#1468).

    A settings load that fails leaves telemetry off, so no handler is on the root logger, and
    Python prints a record with its traceback on stderr. Thus the command logs no record with a
    traceback, also not for its own exit 1."""
    _use(isolate_devops_cli_config, "ai:\n  api_key: FAKE-value: x\n")

    result = cli("config", "get", "ai.provider")

    assert (result.exit_code, type(result.exception), result.output) == (
        1,
        SystemExit,
        f"✗ Cannot load the settings: {isolate_devops_cli_config} is not valid YAML "
        "(ScannerError) at line 2, column 22.\n",
    )
    assert [record.getMessage() for record in caplog.records if record.exc_info] == []
    assert "FAKE-value" not in caplog.text


def test_config_unset_of_a_key_that_the_file_does_not_hold_exits_1_and_changes_nothing(
    cli: Any, isolate_devops_cli_config: Path
) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    result = cli("config", "unset", "ai.no_such_key")

    assert (result.exit_code, result.output) == (
        1,
        f"✗ The config file {isolate_devops_cli_config} does not hold the key "
        "'ai.no_such_key'. Nothing changed.\n",
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]


def test_config_unset_dry_run_runs_as_no_external_request(
    cli: Any, isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    result = cli("--dry-run", "config", "unset", "ai.vllm_url")
    assert result.exit_code == 0
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY.replace(
        _REMOVED_LINE, ""
    )


def test_the_unset_command_that_the_error_names_for_the_other_config_file_removes_the_key(
    cli: Any, tmp_path: Path
) -> None:
    """For a key in a config file that is not the active one, the error names the command with
    `DEVOPS_CLI_CONFIG` set to that file."""
    other = tmp_path / "global" / "config.yaml"
    other.parent.mkdir()
    other.write_text("github:\n  default_org: example-org\nai:\n  vllm_url: x\n", encoding="utf-8")

    result = cli("config", "unset", "ai.vllm_url", env={"DEVOPS_CLI_CONFIG": str(other)})

    assert (result.exit_code, other.read_text(encoding="utf-8")) == (
        0,
        "github:\n  default_org: example-org\nai: {}\n",
    )


_SIMILAR_TO_AN_API_KEY = "ai.api_key, firecrawl.api_key, anthropic.api_key"


@pytest.mark.parametrize(
    ("args", "output"),
    [
        pytest.param(["no.such_key"], "Unknown config key: 'no.such_key'\n", id="no-value"),
        pytest.param(
            ["tavily.api_key", "example-value"],
            "Unknown config key: 'tavily.api_key'\n"
            f"Known keys with a similar name: {_SIMILAR_TO_AN_API_KEY}\n",
            id="value",
        ),
        pytest.param(
            ["firecrawl.apikey", "--from-file", "-"],
            "Unknown config key: 'firecrawl.apikey'\n"
            "Known keys with a similar name: firecrawl.api_key, ai.api_key, qdrant.api_key\n",
            id="from-stdin",
        ),
    ],
)
def test_config_set_of_an_unknown_key_exits_1_before_any_prompt_and_names_the_similar_keys(
    cli: Any, keyring_store: Any, isolate_devops_cli_config: Path, args: list[str], output: str
) -> None:
    """Without a VALUE, an unknown key got the message of a known key that is no credential and
    exit 2. With a VALUE, it got the text of the error of the settings walk (#2448)."""
    config_before = isolate_devops_cli_config.read_text(encoding="utf-8")

    result = cli("config", "set", *args, input="example-value\n")

    assert (result.exit_code, result.output) == (1, output)
    assert keyring_store.writes == {}
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == config_before


def test_config_get_of_an_unknown_key_names_the_similar_keys(cli: Any) -> None:
    result = cli("config", "get", "firecrawl.apikey")

    assert (result.exit_code, result.output) == (
        1,
        "Unknown config key: 'firecrawl.apikey'\n"
        "Known keys with a similar name: firecrawl.api_key, ai.api_key, qdrant.api_key\n",
    )


def test_validate_wizard_service_url_validation_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.config import _validate_wizard_service_url
    from tests.web_fakes import PUBLIC_ADDRESS, scripted_resolver

    scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})

    _validate_wizard_service_url("http://example.com:8080", "Grafana", allow_private=True)

    with pytest.raises(ValueError, match="Invalid Grafana URL: Invalid port: 'notaport'"):
        _validate_wizard_service_url("http://example.com:notaport", "Grafana", allow_private=True)

    with pytest.raises(ValueError, match="Invalid Grafana URL scheme 'ftp': must be http or https"):
        _validate_wizard_service_url("ftp://example.com:8080", "Grafana", allow_private=True)

    with pytest.raises(ValueError, match="Grafana URL missing valid hostname"):
        _validate_wizard_service_url("http://:8080", "Grafana", allow_private=True)

    with pytest.raises(ValueError, match="Grafana URL egress check failed"):
        _validate_wizard_service_url("http://192.168.1.1:8080", "Grafana", allow_private=False)
