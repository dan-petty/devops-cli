"""Tests for environment variable overrides in configuration loading."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai import run_store
from devops_cli.config import settings
from devops_cli.exceptions import ConfigurationError
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_load_settings_applies_env_overrides_for_non_secret_fields(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config(
        ai={"provider": "ollama", "model": "gemma4:26b", "ollama_urls": ["http://localhost:11434"]}
    )
    monkeypatch.setenv("DEVOPS_CLI_AI_MODEL", "qwen3.6:35b")
    monkeypatch.setenv("DEVOPS_CLI_AI_REASONING_EFFORT", "low")
    monkeypatch.setenv("DEVOPS_CLI_AI_OLLAMA_URLS", "http://10.0.0.10:11434")

    loaded_settings = settings.load_settings()

    assert loaded_settings.ai.model == "qwen3.6:35b"
    assert loaded_settings.ai.reasoning_effort == "low"
    assert loaded_settings.ai.get_ollama_urls == ["http://10.0.0.10:11434"]


def test_the_environment_pins_review_analysis_to_one_model(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch, web: WebFake
) -> None:
    """Verify the task environment override reaches a configured analysis model, so one shell
    pins a review's analysis to one gateway group (#475)."""
    config(ai={"tasks": {"analysis": {"provider": "gateway", "model": "devops-review"}}})
    web.respond(
        "GET",
        "http://localhost:4000/v1/model/info",
        200,
        {
            "data": [
                {
                    "model_name": "gpt-oss:20b",
                    "litellm_params": {
                        "model": "ollama_chat/gpt-oss:20b",
                        "api_base": "http://ollama-16gib.example.com:11434",
                        "weight": 8,
                    },
                    "model_info": {"id": "a", "max_input_tokens": 8192},
                }
            ]
        },
    )
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL", "gpt-oss:20b")

    loaded_settings = settings.load_settings()
    analysis = loaded_settings.ai.for_task("analysis")
    setup = run_store.review_setup()

    pool = [
        {
            "backend": "ollama-16gib",
            "model": "ollama_chat/gpt-oss:20b",
            "weight": 8,
            "max_input_tokens": 8192,
        }
    ]
    assert (
        (analysis.provider, analysis.model),
        setup["models"]["analysis"],
        setup["pools"],
    ) == (("gateway", "gpt-oss:20b"), "gateway/gpt-oss:20b", {"gpt-oss:20b": pool})


def test_load_settings_applies_embedding_task_and_rag_url_overrides(
    config: Callable[..., Path], web: WebFake
) -> None:
    config(
        ai={
            "provider": "ollama",
            "model": "qwen3.8:27b",
            "tasks": {"embedding": {"ollama_urls": ["http://192.0.2.10:11434"]}},
        }
    )
    loaded_settings = settings.load_settings()

    assert loaded_settings.ai.tasks.embedding.ollama_urls == ["http://192.0.2.10:11434"]

    # Verify EmbeddingsEngine utilizes embedding task override
    from devops_cli.ai.rag.embeddings import EmbeddingsEngine

    web.respond("POST", "http://192.0.2.10:11434/api/embed", 200, {"embeddings": [[0.5, 0.25]]})
    embedder = EmbeddingsEngine(ai_config=loaded_settings.ai)

    assert (embedder.embed_texts(["sample text"]), web.requested) == (
        [[0.5, 0.25]],
        ["http://192.0.2.10:11434/api/embed"],
    )


def test_ai_config_for_task_with_context_window_overrides() -> None:
    from devops_cli.config.settings import AIConfig, AITaskOverride

    base_ai = AIConfig(
        provider="ollama",
        model="base-model",
        context_window=32768,
        temperature=0.1,
    )
    base_ai.tasks.analysis = AITaskOverride(
        model="analysis-model",
        context_window=40960,
        num_ctx=40960,
        temperature=0.0,
    )

    analysis_cfg = base_ai.for_task("analysis")
    assert analysis_cfg.model == "analysis-model"
    assert analysis_cfg.context_window == 40960
    assert analysis_cfg.num_ctx == 40960
    assert analysis_cfg.temperature == 0.0

    chat_cfg = base_ai.for_task("chat")
    assert chat_cfg.model == "base-model"
    assert chat_cfg.context_window == 32768


def test_the_project_config_skips_a_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "somedir"
    config_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config_dir))

    # Existing directory must be skipped rather than causing IsADirectoryError
    skipped = settings.config_layer_paths()[1]

    # Non-existent file path is accepted for isolated configuration
    non_existent = tmp_path / "nonexistent_config.yaml"
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(non_existent))

    assert (skipped, settings.config_layer_paths()[1]) == (None, non_existent.resolve())


_TELEMETRY_VARIABLES = (
    "DEVOPS_CLI_TELEMETRY_ENABLED",
    "DEVOPS_CLI_TELEMETRY_ENDPOINT",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
)


def _only_this_telemetry_config(
    config_file: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """Make `body` every configuration layer, with no telemetry variable set and no tracer built."""
    from devops_cli.telemetry.tracer import reset_tracer

    config_file.write_text(body, encoding="utf-8")
    for name in _TELEMETRY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    settings.reset_settings_cache()
    reset_tracer()


def _tracer_switch_and_endpoint() -> tuple[bool, str]:
    """Build the process tracer from the current environment and configuration, then drop it."""
    from devops_cli.telemetry.tracer import get_tracer, reset_tracer

    tracer = get_tracer()
    reset_tracer()
    return tracer.enabled, tracer.endpoint


def test_the_registered_telemetry_variables_reach_the_settings_and_the_tracer(
    isolate_devops_cli_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`DEVOPS_CLI_TELEMETRY_ENABLED` and `DEVOPS_CLI_TELEMETRY_ENDPOINT` are the registered names
    for `telemetry.enabled` and `telemetry.endpoint`, and the tracer takes both from the settings
    (#956)."""
    _only_this_telemetry_config(
        isolate_devops_cli_config,
        monkeypatch,
        "telemetry:\n  enabled: true\n  endpoint: http://localhost:4318\n",
    )
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", "http://127.0.0.1:4319")

    loaded = settings.load_settings().telemetry

    assert (loaded.enabled, loaded.endpoint, _tracer_switch_and_endpoint()) == (
        False,
        "http://127.0.0.1:4319",
        (False, "http://127.0.0.1:4319"),
    )


def test_unregistered_telemetry_variables_configure_nothing(
    isolate_devops_cli_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tracer's own names, and the nested form `Settings` used to accept, are gone without a
    shim: none of them turns telemetry off or moves it (#956)."""
    _only_this_telemetry_config(
        isolate_devops_cli_config,
        monkeypatch,
        "telemetry:\n  enabled: true\n  endpoint: http://localhost:4318\n",
    )
    monkeypatch.setenv("DEVOPS_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("DEVOPS_OTEL_ENDPOINT", "http://127.0.0.1:4319")
    monkeypatch.setenv("DEVOPS_CLI_OTEL_ENDPOINT", "http://127.0.0.1:4320")
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY__ENABLED", "false")

    assert (_tracer_switch_and_endpoint(), settings.Settings().telemetry.enabled) == (
        (True, "http://localhost:4318"),
        True,
    )


def test_the_otel_standard_endpoint_is_only_the_fallback(
    isolate_devops_cli_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`OTEL_EXPORTER_OTLP_ENDPOINT` names the collector only when devops-cli's own configuration
    names none; the built-in endpoint is the last resort (#956)."""
    from devops_cli.config.defaults import DEFAULT_OTEL_ENDPOINT

    _only_this_telemetry_config(
        isolate_devops_cli_config, monkeypatch, "telemetry:\n  enabled: false\n"
    )
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4319")
    fallback = _tracer_switch_and_endpoint()[1]
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", "http://127.0.0.1:4320")
    registered = _tracer_switch_and_endpoint()[1]
    monkeypatch.delenv("DEVOPS_CLI_TELEMETRY_ENDPOINT")
    _only_this_telemetry_config(
        isolate_devops_cli_config,
        monkeypatch,
        "telemetry:\n  enabled: false\n  endpoint: http://127.0.0.1:4321\n",
    )
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4319")
    configured = _tracer_switch_and_endpoint()[1]
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    _only_this_telemetry_config(
        isolate_devops_cli_config, monkeypatch, "telemetry:\n  enabled: false\n"
    )
    built_in = _tracer_switch_and_endpoint()[1]

    assert (fallback, registered, configured, built_in) == (
        "http://127.0.0.1:4319",
        "http://127.0.0.1:4320",
        "http://127.0.0.1:4321",
        DEFAULT_OTEL_ENDPOINT,
    )


@pytest.mark.parametrize(
    ("body", "broken_variable"),
    [
        pytest.param("telemetry: [\n", None, id="malformed-configuration"),
        pytest.param(
            "telemetry:\n  enabled: false\n",
            ("DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL", "abc"),
            id="unrelated-variable-cannot-apply",
        ),
    ],
)
def test_the_telemetry_variables_hold_when_the_settings_cannot_load(
    isolate_devops_cli_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    broken_variable: tuple[str, str] | None,
) -> None:
    """Settings that cannot load still leave `DEVOPS_CLI_TELEMETRY_ENABLED` and
    `DEVOPS_CLI_TELEMETRY_ENDPOINT` deciding. With neither switch set, export stays off, since the
    layer that cannot be read may be the one turning it off; it never fails open to OpenTelemetry's
    own variable (#956)."""
    _only_this_telemetry_config(isolate_devops_cli_config, monkeypatch, body)
    if broken_variable is not None:
        monkeypatch.setenv(*broken_variable)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4320")
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", "http://127.0.0.1:4319")
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    switched_off = _tracer_switch_and_endpoint()
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "true")
    switched_on = _tracer_switch_and_endpoint()
    monkeypatch.delenv("DEVOPS_CLI_TELEMETRY_ENABLED")
    unset = _tracer_switch_and_endpoint()

    with pytest.raises(ConfigurationError) as raised:
        settings.load_settings()
    assert raised.value.error_code == "CONFIGURATION_ERROR"
    assert (switched_off, switched_on, unset) == (
        (False, "http://127.0.0.1:4319"),
        (True, "http://127.0.0.1:4319"),
        (False, "http://127.0.0.1:4319"),
    )


@pytest.mark.parametrize(
    ("env_var", "val"),
    [
        ("DEVOPS_CLI_TELEMETRY_ENABLED", "bogus"),
        ("DEVOPS_CLI_TELEMETRY_ENDPOINT", "localhost:4318"),
    ],
)
def test_telemetry_invalid_variables_fail_load_settings_but_keep_export_off(
    isolate_devops_cli_config: Path, monkeypatch: pytest.MonkeyPatch, env_var: str, val: str
) -> None:
    """Invalid telemetry variables fail load_settings but keep tracer export off without raising."""
    _only_this_telemetry_config(
        isolate_devops_cli_config, monkeypatch, "telemetry:\n  enabled: true\n"
    )
    monkeypatch.setenv(env_var, val)
    with pytest.raises(ConfigurationError) as exc_info:
        settings.load_settings()
    assert env_var in str(exc_info.value)

    from devops_cli.telemetry.tracer import get_tracer, reset_tracer

    assert settings.telemetry_from_environment().enabled is False
    tracer = get_tracer()
    reset_tracer()
    assert tracer.enabled is False


def test_ai_gateway_url_environment_variable_override_and_spec(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify DEVOPS_CLI_AI_GATEWAY_URL overrides ai.gateway_url and is registered as non-secret."""
    from devops_cli.config import env as env_mod

    config(ai={"gateway_url": "http://localhost:4000/v1"})
    monkeypatch.setenv("DEVOPS_CLI_AI_GATEWAY_URL", "https://example.com/v1")

    loaded = settings.load_settings()
    assert loaded.ai.gateway_url == "https://example.com/v1"

    specs = {s.env_var: s for s in env_mod.get_all_env_var_specs()}
    spec = specs.get("DEVOPS_CLI_AI_GATEWAY_URL")
    assert spec is not None
    assert (spec.is_secret, spec.option_key) == (False, "ai.gateway_url")
