"""Tests for settings field types, constraints, and validation on load and assignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from devops_cli.commands.config import app as config_app
from devops_cli.config.env import setting_variables
from devops_cli.config.settings import (
    Settings,
    dotted_get,
    dotted_set,
    load_settings,
    reset_settings_cache,
    telemetry_from_environment,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.telemetry.tracer import _resolve_telemetry_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    reset_settings_cache()


def _set_project_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(content, encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    reset_settings_cache()
    return cfg


_NUMERIC_CASES = [
    ("ssh.rotation_days", "30", int, 30, ["0", "-1", "inf", "x"]),
    ("ai.ollama_max_parallel", "4", int, 4, ["0", "-1", "inf", "x"]),
    ("ai.max_retries", "3", int, 3, ["-1", "inf", "x"]),
    ("ai.tasks.embedding.timeout", "15.5", float, 15.5, ["0", "-1", "inf", "nan", "x"]),
    ("ai.rag.top_k", "5", int, 5, ["0", "-1", "inf", "x"]),
    ("ai.rag.score_threshold", "0.7", float, 0.7, ["-1", "inf", "nan", "x"]),
    ("qdrant.timeout", "20.0", float, 20.0, ["0", "-1", "inf", "nan", "x"]),
    ("valkey.timeout", "5.0", float, 5.0, ["0", "-1", "inf", "nan", "x"]),
    ("service.poll_interval_seconds", "120", int, 120, ["0", "-1", "inf", "x", "59"]),
    ("service.drain_timeout_seconds", "30", int, 30, ["0", "-1", "inf", "x"]),
    ("ci.gate_slots", "2", int, 2, ["0", "-1", "inf", "x"]),
]


@pytest.mark.parametrize(
    ("option_key", "valid_str", "expected_type", "expected_val", "invalid_values"),
    _NUMERIC_CASES,
)
def test_numeric_setting_environment_override_valid(
    monkeypatch: pytest.MonkeyPatch,
    option_key: str,
    valid_str: str,
    expected_type: type,
    expected_val: Any,
    invalid_values: list[str],
) -> None:
    """A valid numeric environment override loads as its declared type."""
    env_var = setting_variables()[option_key]
    monkeypatch.setenv(env_var, valid_str)
    settings = load_settings()
    actual = dotted_get(settings, option_key)
    assert type(actual) is expected_type
    assert actual == expected_val


@pytest.mark.parametrize(
    ("option_key", "valid_str", "expected_type", "expected_val", "invalid_values"),
    _NUMERIC_CASES,
)
def test_numeric_setting_environment_override_invalid(
    monkeypatch: pytest.MonkeyPatch,
    option_key: str,
    valid_str: str,
    expected_type: type,
    expected_val: Any,
    invalid_values: list[str],
) -> None:
    """An invalid numeric environment override is refused and names the environment variable."""
    env_var = setting_variables()[option_key]
    for bad in invalid_values:
        monkeypatch.setenv(env_var, bad)
        with pytest.raises(ConfigurationError) as exc_info:
            load_settings()
        assert env_var in str(exc_info.value)


@pytest.mark.parametrize(
    ("env_var", "val"),
    [
        ("DEVOPS_CLI_TELEMETRY_ENABLED", "bogus"),
        ("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "bogus"),
        ("DEVOPS_CLI_TELEMETRY_ENABLED", " true "),
        ("DEVOPS_CLI_TELEMETRY_ENABLED", "true\r"),
    ],
)
def test_boolean_environment_overrides_refused(
    monkeypatch: pytest.MonkeyPatch, env_var: str, val: str
) -> None:
    """Non-standard or whitespace-padded booleans from environment are refused."""
    monkeypatch.setenv(env_var, val)
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    assert env_var in str(exc_info.value)


def test_boolean_environment_override_y_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pydantic boolean parsing accepts 'y' as True."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "y")
    settings = load_settings()
    assert settings.ai.allow_private_network is True


def test_ollama_urls_schemeless_in_environment_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A schemeless URL in DEVOPS_CLI_AI_OLLAMA_URLS is refused with the list index in the error."""
    monkeypatch.setenv("DEVOPS_CLI_AI_OLLAMA_URLS", "localhost:11434")
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    assert "ai.ollama_urls.0" in str(exc_info.value)


def test_grafana_url_schemeless_in_environment_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A schemeless URL in DEVOPS_CLI_GRAFANA_URL is refused naming grafana.url."""
    monkeypatch.setenv("DEVOPS_CLI_GRAFANA_URL", "example.com")
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    assert "grafana.url" in str(exc_info.value)


def test_config_set_ollama_urls_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """config set on ai.ollama_urls with a bad entry leaves config.yaml unchanged and names the index."""
    cfg = _set_project_config(
        tmp_path, monkeypatch, "ai:\n  ollama_urls:\n    - http://example.com:11434\n"
    )
    initial_content = cfg.read_text(encoding="utf-8")
    result = runner.invoke(
        config_app, ["set", "ai.ollama_urls", "http://example.com:11434, localhost:11434"]
    )
    assert result.exit_code == 1
    assert "ai.ollama_urls.1" in result.output
    assert cfg.read_text(encoding="utf-8") == initial_content


def test_uppercase_http_scheme_in_file_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uppercase HTTP scheme in config.yaml loads and get_ollama_urls adds no scheme."""
    _set_project_config(
        tmp_path, monkeypatch, "ai:\n  ollama_urls:\n    - HTTP://example.com:11434\n"
    )
    settings = load_settings()
    assert settings.ai.ollama_urls == ["HTTP://example.com:11434"]
    assert settings.ai.get_ollama_urls == ["http://example.com:11434"]


def test_url_without_trailing_slash_preserved_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A URL without trailing slash is stored and saved without adding a trailing slash."""
    _set_project_config(
        tmp_path, monkeypatch, "ai:\n  ollama_urls:\n    - http://example.com:11434\n"
    )
    settings = load_settings()
    assert settings.ai.ollama_urls == ["http://example.com:11434"]


def test_url_with_trailing_slash_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A URL with trailing slash is saved as written and get_ollama_urls strips it."""
    _set_project_config(
        tmp_path, monkeypatch, "ai:\n  ollama_urls:\n    - http://example.com:11434/\n"
    )
    settings = load_settings()
    assert settings.ai.ollama_urls == ["http://example.com:11434/"]
    assert settings.ai.get_ollama_urls == ["http://example.com:11434"]


@pytest.mark.parametrize(
    "bad_url",
    [
        "http:example.com",
        "http://example.com\\v1",
        "http://2852039166:11434",
    ],
)
def test_disagreement_urls_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_url: str
) -> None:
    """URLs where Pydantic and httpx2 disagree are refused on load and config set."""
    _set_project_config(tmp_path, monkeypatch, f"ai:\n  gateway_url: {bad_url}\n")
    with pytest.raises(ValidationError):
        load_settings()

    settings = Settings()
    with pytest.raises(ValueError, match=r"ai\.gateway_url"):
        dotted_set(settings, "ai.gateway_url", bad_url)


def test_url_with_embedded_tab_refused_no_invalidurl_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An embedded tab in a URL is refused as a validation error without unhandled InvalidURL."""
    bad_url = "http://exa\tmple.com:11434"
    _set_project_config(tmp_path, monkeypatch, f"ai:\n  gateway_url: '{bad_url}'\n")
    with pytest.raises(ValidationError) as exc_info:
        load_settings()
    assert "ai.gateway_url" in str(exc_info.value)

    settings = Settings()
    with pytest.raises(ValueError, match=r"ai\.gateway_url") as exc_info2:
        dotted_set(settings, "ai.gateway_url", bad_url)
    assert "ai.gateway_url" in str(exc_info2.value)


def test_url_with_mismatched_origin_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """https://api.openai.com\\@example.com/v1 is refused as mismatched origin."""
    bad_url = "https://api.openai.com\\@example.com/v1"
    _set_project_config(tmp_path, monkeypatch, f"ai:\n  api_base_url: '{bad_url}'\n")
    with pytest.raises(ValidationError) as exc_info:
        load_settings()
    assert "ai.api_base_url" in str(exc_info.value)


def test_k8s_service_urls_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid k8s:// and k8s+https:// URLs are accepted unchanged in service URL fields."""
    _set_project_config(
        tmp_path,
        monkeypatch,
        "prometheus:\n  url: k8s://monitoring/prometheus:9090\nargocd:\n  url: k8s+https://argocd/argocd-server:443\n",
    )
    settings = load_settings()
    assert settings.prometheus.url == "k8s://monitoring/prometheus:9090"
    assert settings.argocd.url == "k8s+https://argocd/argocd-server:443"


def test_k8s_service_url_without_port_refused_without_url_text() -> None:
    """A k8s:// URL without port is refused with parse_service_url's reason and no URL string."""
    settings = Settings()
    with pytest.raises(ValueError, match="port") as exc_info:
        dotted_set(settings, "prometheus.url", "k8s://monitoring/prometheus")
    assert "port" in str(exc_info.value)
    assert "k8s://" not in str(exc_info.value)


def test_k8s_service_url_with_credentials_does_not_leak_secret() -> None:
    """A malformed k8s:// URL with user credentials never prints the password in error messages."""
    secret = "s3cret_pass"
    url = f"k8s://admin:{secret}@monitoring/prometheus"
    settings = Settings()
    with pytest.raises(ValueError, match=r"prometheus\.url") as exc_info:
        dotted_set(settings, "prometheus.url", url)
    assert secret not in str(exc_info.value)


def test_http_url_with_credentials_does_not_leak_secret() -> None:
    """A malformed http URL with user credentials never prints the password in error messages."""
    secret = "s3cret_token"
    url = f"http://admin:{secret}@exa mple.com"
    settings = Settings()
    with pytest.raises(ValueError, match=r"ai\.gateway_url") as exc_info:
        dotted_set(settings, "ai.gateway_url", url)
    assert secret not in str(exc_info.value)


@pytest.mark.parametrize("endpoint", ["grpc://example.com:4317", "example.com:4317"])
def test_telemetry_endpoint_refuses_grpc_and_bare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """telemetry.endpoint refuses grpc:// and bare host:port values, naming the key.

    The floor's `DEVOPS_CLI_TELEMETRY_ENDPOINT` is unset, so the value of the file applies: a value
    that a variable replaces is not checked.
    """
    monkeypatch.delenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", raising=False)
    _set_project_config(tmp_path, monkeypatch, f"telemetry:\n  endpoint: '{endpoint}'\n")
    with pytest.raises(ValidationError) as exc_info:
        load_settings()
    assert "telemetry.endpoint" in str(exc_info.value)


def test_ai_temperature_and_timeout_config_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ai.temperature parses as float and ai.timeout=abc is refused."""
    _set_project_config(tmp_path, monkeypatch, "")
    res1 = runner.invoke(config_app, ["set", "ai.temperature", "0.5"])
    assert res1.exit_code == 0
    settings = load_settings()
    assert settings.ai.temperature == 0.5
    assert type(settings.ai.temperature) is float

    res2 = runner.invoke(config_app, ["set", "ai.timeout", "abc"])
    assert res2.exit_code == 1
    assert "ai.timeout" in res2.output


@pytest.mark.parametrize("val", ["0", "-1", "inf", "nan"])
def test_ai_timeout_invalid_values_refused(val: str) -> None:
    """ai.timeout refuses 0, -1, inf, nan."""
    settings = Settings()
    with pytest.raises(ValueError, match=r"ai\.timeout") as exc_info:
        dotted_set(settings, "ai.timeout", val)
    assert "ai.timeout" in str(exc_info.value)


def test_cloudflare_public_ip_bypass_stays_string_in_config_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cloudflare.public_ip_bypass is stored as a string, not a list, by config set."""
    _set_project_config(tmp_path, monkeypatch, "")
    res = runner.invoke(config_app, ["set", "cloudflare.public_ip_bypass", "192.0.2.1"])
    assert res.exit_code == 0
    settings = load_settings()
    assert settings.cloudflare.public_ip_bypass == "192.0.2.1"
    assert isinstance(settings.cloudflare.public_ip_bypass, str)


def test_ai_gateway_weights_refuses_scalar_string_in_config_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ai.gateway_weights is a dict and refuses string assignment."""
    _set_project_config(tmp_path, monkeypatch, "")
    res = runner.invoke(config_app, ["set", "ai.gateway_weights", "a=1"])
    assert res.exit_code == 1
    assert "ai.gateway_weights" in res.output


def test_telemetry_stays_fail_closed_on_invalid_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid telemetry variables fail load_settings but keep tracer export off without raising."""
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "bogus")
    with pytest.raises(ConfigurationError):
        load_settings()
    assert _resolve_telemetry_settings().enabled is False
    assert telemetry_from_environment().enabled is False

    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", "localhost:4318")
    with pytest.raises(ConfigurationError):
        load_settings()
    assert _resolve_telemetry_settings().enabled is False
    assert telemetry_from_environment().enabled is False


def test_ci_gate_slots_is_unset_by_default() -> None:
    """Without a value, the number of gate slots comes from the CPU count (#2336)."""
    assert load_settings().ci.gate_slots is None


def test_ci_gate_slots_loads_from_the_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ci.gate_slots` in config.yaml loads as an integer (#2336)."""
    _set_project_config(tmp_path, monkeypatch, "ci:\n  gate_slots: 3\n")
    assert load_settings().ci.gate_slots == 3


@pytest.mark.parametrize("val", ["0", "-1", "inf", "x"])
def test_ci_gate_slots_below_one_is_refused_and_named(val: str) -> None:
    """`ci.gate_slots` refuses a value below 1 or a non-integer, and the error names the key."""
    settings = Settings()
    with pytest.raises(ValueError, match=r"ci\.gate_slots"):
        dotted_set(settings, "ci.gate_slots", val)


def test_config_set_stores_ci_gate_slots() -> None:
    """`config set ci.gate_slots 2` stores the integer 2 (#2336)."""
    settings = Settings()
    dotted_set(settings, "ci.gate_slots", "2")
    assert settings.ci.gate_slots == 2
