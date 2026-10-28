"""Verify the one order in which a setting resolves, and the chain in which a credential resolves."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from devops_cli.config.constants import CONST_CONFIG_PATH
from devops_cli.config.defaults import DEFAULT_RAG_EMBEDDING_MODEL
from devops_cli.config.settings import Settings, load_settings, reset_settings_cache
from devops_cli.exceptions import ConfigurationError
from devops_cli.security.secrets import VaultProvider, build_default_resolver, build_secret_registry
from tests.cluster_secret_fakes import FakeKeyring

_DEFAULT_REFERENCE_MODEL = Settings().ai.reference_model


@pytest.fixture
def global_config() -> Iterator[Callable[[dict[str, Any]], None]]:
    """Write the global config file, which the floor keeps under the run's own HOME, then remove it
    and each directory that the write made."""
    made = [
        d for d in (CONST_CONFIG_PATH.parent, *CONST_CONFIG_PATH.parent.parents) if not d.exists()
    ]

    def write(data: dict[str, Any]) -> None:
        CONST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONST_CONFIG_PATH.write_text(yaml.safe_dump(data), encoding="utf-8")
        reset_settings_cache()

    yield write
    CONST_CONFIG_PATH.unlink(missing_ok=True)
    for directory in made:
        if directory.exists():
            directory.rmdir()
    reset_settings_cache()


@pytest.mark.parametrize(
    ("variable", "project", "global_", "expected"),
    [
        pytest.param(
            "variable-model", "project-model", "global-model", "variable-model", id="variable"
        ),
        pytest.param(None, "project-model", "global-model", "project-model", id="project-file"),
        pytest.param(None, None, "global-model", "global-model", id="global-file"),
        pytest.param(None, None, None, _DEFAULT_REFERENCE_MODEL, id="default"),
    ],
)
def test_a_setting_takes_the_variable_then_the_project_file_then_the_global_file_then_its_default(
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
    global_config: Callable[[dict[str, Any]], None],
    variable: str | None,
    project: str | None,
    global_: str | None,
    expected: str,
) -> None:
    if variable is None:
        monkeypatch.delenv("DEVOPS_CLI_AI_REFERENCE_MODEL", raising=False)
    else:
        monkeypatch.setenv("DEVOPS_CLI_AI_REFERENCE_MODEL", variable)
    if project is not None:
        config(ai={"reference_model": project})
    if global_ is not None:
        global_config({"ai": {"reference_model": global_}})

    assert load_settings().ai.reference_model == expected


@pytest.mark.parametrize(
    ("in_keyring", "in_vault", "variable", "in_file", "expected"),
    [
        pytest.param(
            "keyring-key", "vault-key", "variable-key", "file-key", "keyring-key", id="keyring"
        ),
        pytest.param(None, "vault-key", "variable-key", "file-key", "vault-key", id="vault"),
        pytest.param(None, None, "variable-key", "file-key", "variable-key", id="variable"),
        pytest.param(None, None, None, "file-key", "file-key", id="config-file"),
        pytest.param(None, None, None, None, None, id="none"),
    ],
)
def test_a_credential_takes_the_keyring_then_vault_then_the_variable_then_the_config_file(
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
    mock_keyring: FakeKeyring,
    in_keyring: str | None,
    in_vault: str | None,
    variable: str | None,
    in_file: str | None,
    expected: str | None,
) -> None:
    if in_keyring is not None:
        mock_keyring.values["qdrant_api_key"] = in_keyring
    if variable is None:
        monkeypatch.delenv("DEVOPS_CLI_QDRANT_API_KEY", raising=False)
    else:
        monkeypatch.setenv("DEVOPS_CLI_QDRANT_API_KEY", variable)
    if in_file is not None:
        config(qdrant={"api_key": in_file})
    broker = SimpleNamespace(
        vault_token="vault-token" if in_vault else None,
        read_secret=lambda path, key=None: in_vault,
    )
    resolver = build_default_resolver(settings_source=load_settings)
    resolver.providers = [
        VaultProvider(broker=broker) if provider.name == "vault" else provider
        for provider in resolver.providers
    ]

    assert resolver.resolve(build_secret_registry()["qdrant.api_key"]) == expected


def test_settings_built_in_code_hold_their_arguments_and_the_defaults(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Verify `Settings(...)` reads no variable and no config file: only `load_settings` does."""
    monkeypatch.setenv("DEVOPS_CLI_DOMAIN", "example.com")
    monkeypatch.setenv("DEVOPS_CLI_AI_REFERENCE_MODEL", "variable-model")
    config(ai={"model": "file-model"})

    built = Settings(github={"default_org": "example-org"})

    assert (
        built.domain,
        built.ai.reference_model,
        built.ai.model,
        built.github.default_org,
        load_settings().domain,
    ) == (None, _DEFAULT_REFERENCE_MODEL, Settings().ai.model, "example-org", None)


@pytest.mark.parametrize(
    "layer",
    [pytest.param("variable", id="variable"), pytest.param("config-file", id="config-file")],
)
def test_the_embedding_task_keeps_its_model_when_a_layer_sets_another_of_its_fields(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path], layer: str
) -> None:
    if layer == "variable":
        monkeypatch.setenv("DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT", "45")
    else:
        config(ai={"tasks": {"embedding": {"timeout": 45}}})

    embedding = load_settings().ai.tasks.embedding

    assert (embedding.model, embedding.timeout) == (DEFAULT_RAG_EMBEDDING_MODEL, 45.0)


def test_a_variable_replaces_a_config_file_value_before_the_value_is_checked(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Verify the order decides the value first, so a file value that a variable replaces is never checked."""
    config(qdrant={"timeout": 0})
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_TIMEOUT", "45")

    assert load_settings().qdrant.timeout == 45.0


def test_a_config_file_value_that_does_not_validate_names_no_variable(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Verify only a value that a variable gave is reported as the variable's error."""
    monkeypatch.delenv("DEVOPS_CLI_QDRANT_TIMEOUT", raising=False)
    monkeypatch.setenv("DEVOPS_CLI_AI_REFERENCE_MODEL", "variable-model")
    config(qdrant={"timeout": 0})

    with pytest.raises(ValidationError) as refused:
        load_settings()

    assert (
        [error["loc"] for error in refused.value.errors()],
        "DEVOPS_CLI" in str(refused.value),
    ) == ([("qdrant", "timeout")], False)


@pytest.mark.parametrize(
    "layer", [pytest.param("project", id="project-file"), pytest.param("global", id="global-file")]
)
def test_a_config_file_that_holds_no_mapping_stops_the_load_and_names_the_file(
    config: Callable[..., Path], global_config: Callable[[dict[str, Any]], None], layer: str
) -> None:
    path = config() if layer == "project" else CONST_CONFIG_PATH
    if layer == "global":
        global_config({})
    path.write_text("- reference_model\n- model\n", encoding="utf-8")
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as refused:
        load_settings()

    assert str(refused.value) == (
        f"Cannot load the settings: {path} does not hold a mapping of keys to values."
    )
