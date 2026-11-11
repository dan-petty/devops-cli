"""The Qdrant request timeout is the `qdrant.timeout` setting, read by every client built (#975).

60 s is too short for a homelab Qdrant search, and the owner set 300 to 600 s as the range
(2026-10-02). The client took a timeout, but no caller passed one, and a floor of 60 s kept
any smaller value from reaching the native client.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.ai.rag.indexer import resolve_qdrant_client, resolve_rag_components
from devops_cli.ai.rag.qdrant import create_native_qdrant_client
from devops_cli.config import settings as settings_module
from devops_cli.config.settings import QdrantConfig
from devops_cli.exceptions import ConfigurationError

pytestmark = pytest.mark.usefixtures("keyring_store")


def _configure_qdrant(config: Callable[..., Path], timeout: float) -> None:
    """Merge a `qdrant` address that needs no DNS and `timeout` into the `qdrant` section of the
    test's config file. A second `qdrant` key in the file would stop the load (#4481)."""
    config(qdrant={"url": "http://127.0.0.1:6333", "timeout": timeout})


def test_the_qdrant_timeout_is_read_from_the_config_file_and_the_environment(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the default is 300 s, a config file sets it, and the environment overrides that."""
    default = settings_module.load_settings().qdrant.timeout
    _configure_qdrant(config, 450)
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


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: resolve_rag_components().qdrant, id="rag components"),
        pytest.param(resolve_qdrant_client, id="indexing"),
    ],
)
def test_each_builder_gives_its_qdrant_client_the_configured_timeout(
    build: object, config: Callable[..., Path]
) -> None:
    """The review investigation, the `rag_search` tool, `devops ai rag query` and the library
    vector store build their client with `resolve_rag_components`; indexing's upserts and
    deletes go through `resolve_qdrant_client`. Both pass `qdrant.timeout`, not the default."""
    _configure_qdrant(config, 450)

    client = build()  # type: ignore[operator]

    assert client.timeout == 450.0


@pytest.mark.parametrize(("configured", "sent"), [(600, 600), (30, 30), (0.5, 1)])
def test_the_native_client_waits_the_configured_timeout_with_no_floor(
    configured: float, sent: int
) -> None:
    """The native client takes whole seconds, so a fraction rounds up rather than down to 0."""
    native = create_native_qdrant_client("http://127.0.0.1:6333", timeout=float(configured))

    assert native._client._timeout == sent
