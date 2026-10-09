"""The Qdrant request timeout is the `qdrant.timeout` setting, read by every client built (#975).

60 s is too short for a homelab Qdrant search, and the owner set 300 to 600 s as the range
(2026-10-02). The client took a timeout, but no caller passed one, and a floor of 60 s kept
any smaller value from reaching the native client.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.ai.rag import embeddings as embeddings_module
from devops_cli.ai.rag import indexer as indexer_module
from devops_cli.ai.rag import investigator as investigator_module
from devops_cli.ai.tools import builtin_tools
from devops_cli.commands import rag as rag_commands
from devops_cli.config import settings as settings_module
from devops_cli.config.settings import QdrantConfig
from devops_cli.exceptions import ConfigurationError


def _configure_qdrant(config: Path, timeout: float) -> None:
    """Append a `qdrant` section to the test's config file, at an address that needs no DNS."""
    section = f"qdrant:\n  url: http://127.0.0.1:6333\n  timeout: {timeout}\n"
    config.write_text(config.read_text(encoding="utf-8") + section, encoding="utf-8")


@pytest.fixture
def no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve the API keys without the keyring, and probe no Valkey."""
    monkeypatch.setattr(settings_module, "get_qdrant_api_key", lambda settings: "test-key")
    monkeypatch.setattr(settings_module, "get_ai_api_key", lambda settings: None)
    monkeypatch.setattr(
        embeddings_module.EmbeddingsEngine, "_init_valkey", lambda self, client: None
    )


def test_the_qdrant_timeout_is_read_from_the_config_file_and_the_environment(
    isolate_devops_cli_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the default is 300 s, a config file sets it, and the environment overrides that."""
    default = settings_module.load_settings().qdrant.timeout
    _configure_qdrant(isolate_devops_cli_config, 450)
    from_file = settings_module.load_settings().qdrant.timeout
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_TIMEOUT", "600")
    from_env = settings_module.load_settings().qdrant.timeout

    assert (default, from_file, from_env, type(from_env)) == (300.0, 450.0, 600.0, float)


@pytest.mark.parametrize("value", ["0", "-5", "soon", "inf", "nan"])
def test_a_qdrant_timeout_from_the_environment_must_be_a_positive_number(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an override that is not a positive number fails to load, naming the variable."""
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_TIMEOUT", value)

    with pytest.raises(ConfigurationError) as refused:
        settings_module.load_settings()

    assert str(refused.value).startswith(
        "Environment variable DEVOPS_CLI_QDRANT_TIMEOUT cannot set qdrant.timeout"
    )


def test_a_qdrant_timeout_in_the_config_file_must_be_positive() -> None:
    """Verify a config file's zero timeout is refused, as a request that never waits would be."""
    with pytest.raises(ValidationError) as refused:
        QdrantConfig.model_validate({"timeout": 0})

    assert [(error["loc"], error["type"]) for error in refused.value.errors()] == [
        (("timeout",), "greater_than")
    ]


def _investigation() -> object:
    return investigator_module._get_or_create_retriever(settings_module.load_settings(), None, None)


CALLERS: dict[str, Callable[[], object]] = {
    "review investigation": _investigation,
    "rag_search tool": lambda: builtin_tools.rag_search("retry policy"),
    "devops ai rag query": rag_commands._get_rag_components,
    "indexing": indexer_module.resolve_qdrant_client,
}


@pytest.mark.usefixtures("no_secrets")
@pytest.mark.parametrize("caller", list(CALLERS), ids=list(CALLERS))
def test_each_caller_builds_its_qdrant_client_with_the_configured_timeout(
    caller: str, isolate_devops_cli_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify each place that builds a Qdrant client passes `qdrant.timeout`, not the default.

    Indexing's upserts and deletes go through the client `resolve_qdrant_client` builds.
    """
    _configure_qdrant(isolate_devops_cli_config, 450)
    timeouts: list[Any] = []

    class RecordingQdrant:
        """Records the timeout each client is built with, and reports Qdrant unreachable."""

        def __init__(self, base_url: str, **kwargs: Any) -> None:
            timeouts.append(kwargs.get("timeout"))

        def is_alive(self, **kwargs: Any) -> bool:
            return False

    from devops_cli.ai.rag import qdrant as qdrant_module

    monkeypatch.setattr(qdrant_module, "QdrantClient", RecordingQdrant)
    monkeypatch.setattr(investigator_module, "QdrantClient", RecordingQdrant)
    monkeypatch.setattr(indexer_module, "QdrantClient", RecordingQdrant)
    monkeypatch.setattr(investigator_module, "_RETRIEVER_CACHE", None)

    CALLERS[caller]()

    assert timeouts == [450.0]


@pytest.mark.parametrize(("configured", "sent"), [(600, 600), (30, 30), (0.5, 1)])
def test_a_configured_timeout_reaches_the_native_client(
    configured: float,
    sent: int,
    isolate_devops_cli_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the configured timeout is what the native client waits, with no floor under it.

    The native client takes whole seconds, so a fraction rounds up rather than down to 0.
    """
    _configure_qdrant(isolate_devops_cli_config, configured)
    native: list[dict[str, Any]] = []

    def native_client(**kwargs: Any) -> SimpleNamespace:
        native.append(kwargs)
        return SimpleNamespace()

    from devops_cli.ai.rag import qdrant as qdrant_module

    monkeypatch.setattr(settings_module, "get_qdrant_api_key", lambda settings: "test-key")
    monkeypatch.setattr(qdrant_module, "NativeQdrantClient", native_client)

    client = indexer_module.resolve_qdrant_client()
    client._get_client()

    assert (client.timeout, [kwargs["timeout"] for kwargs in native]) == (
        float(configured),
        [sent],
    )
