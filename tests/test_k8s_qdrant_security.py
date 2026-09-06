"""Unit and integration tests for Qdrant API key secret protection and ClusterIP defaults.

Validates:
1. k8s/llm/values-qdrant.yaml manifests (ClusterIP service, apiKey disabled auto-generation,
   extraEnv secretKeyRef injection).
2. Configuration & OS Keyring secret mappings for Qdrant API key.
3. RAG WorkspaceIndexer and QdrantClient automatic OS Keyring resolution.
4. Kubernetes secret discovery and synchronization for Qdrant stack credentials.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from devops_cli.config import env as env_mod
from devops_cli.config import options as opt
from devops_cli.config.settings import (
    QdrantConfig,
    Settings,
    dotted_set,
    get_qdrant_api_key,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_qdrant_helm_values_security() -> None:
    """Validate k8s/llm/values-qdrant.yaml zero-trust perimeter and secret protection."""
    values_path = REPO_ROOT / "k8s" / "llm" / "values-qdrant.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    content = values_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict), "values-qdrant.yaml must parse as dictionary"

    # 1. Zero-trust internal perimeter: service.type must be ClusterIP
    service = data.get("service", {})
    assert service.get("type") == "ClusterIP", (
        f"Expected service.type 'ClusterIP', got {service.get('type')}"
    )

    # 2. Disabled auto-generated secret to prevent unmanaged secret sprawl
    assert data.get("apiKey") is False, "apiKey must be false to disable chart auto-generation"

    # 3. Secret reference injection via extraEnv
    extra_env = data.get("extraEnv", [])
    assert isinstance(extra_env, list), "extraEnv must be a list"
    api_key_env = next(
        (
            e
            for e in extra_env
            if isinstance(e, dict) and e.get("name") == "QDRANT__SERVICE__API_KEY"
        ),
        None,
    )
    assert api_key_env is not None, "Missing QDRANT__SERVICE__API_KEY in extraEnv"

    value_from = api_key_env.get("valueFrom", {})
    secret_ref = value_from.get("secretKeyRef", {})
    assert secret_ref.get("name") == "qdrant-api-key", "Expected secretKeyRef.name 'qdrant-api-key'"
    assert secret_ref.get("key") == "api-key", "Expected secretKeyRef.key 'api-key'"

    # 4. Pod and container security contexts
    sec_ctx = data.get("securityContext", {})
    assert sec_ctx.get("allowPrivilegeEscalation") is False
    assert sec_ctx.get("capabilities", {}).get("drop") == ["ALL"]

    pod_sec_ctx = data.get("podSecurityContext", {})
    assert pod_sec_ctx.get("runAsNonRoot") is True


def test_qdrant_config_options_and_secret_registry() -> None:
    """Verify Qdrant config options and secret registry mappings."""
    assert opt.QDRANT_API_KEY in opt.CONFIG_OPTIONS
    assert opt.QDRANT_URL in opt.CONFIG_OPTIONS
    assert opt.QDRANT_COLLECTION_PREFIX in opt.CONFIG_OPTIONS

    assert opt.QDRANT_API_KEY in opt.SECRET_CONFIG_OPTIONS
    assert opt.KEYRING_KEYS[opt.QDRANT_API_KEY] == "qdrant_api_key"


def test_qdrant_env_variable_mappings() -> None:
    """Verify Qdrant environment variable mappings and secret specs."""
    assert env_mod.ENV_QDRANT_API_KEY == "DEVOPS_CLI_QDRANT_API_KEY"
    assert env_mod.OPTION_TO_ENV_VAR[opt.QDRANT_API_KEY] == env_mod.ENV_QDRANT_API_KEY
    assert env_mod.ENV_VAR_TO_OPTION[env_mod.ENV_QDRANT_API_KEY] == opt.QDRANT_API_KEY

    specs = {s.env_var: s for s in env_mod.get_all_env_var_specs()}
    spec = specs.get(env_mod.ENV_QDRANT_API_KEY)
    assert spec is not None
    assert spec.is_secret is True
    assert spec.option_key == opt.QDRANT_API_KEY


def test_get_qdrant_api_key_precedence() -> None:
    """Verify get_qdrant_api_key prioritizes OS Keyring over settings fallback."""
    settings = Settings(qdrant=QdrantConfig(api_key="fallback-key"))

    with patch("devops_cli.config.settings._keyring_get", return_value="keyring-vault-key"):
        assert get_qdrant_api_key(settings) == "keyring-vault-key"

    with patch("devops_cli.config.settings._keyring_get", return_value=None):
        assert get_qdrant_api_key(settings) == "fallback-key"


def test_dotted_set_routes_qdrant_api_key_to_keyring() -> None:
    """Verify dotted_set routes qdrant.api_key exclusively to the OS Keyring."""
    settings = Settings()
    with patch("devops_cli.config.settings._keyring_set") as mock_set:
        dotted_set(settings, "qdrant.api_key", "super-secret-vector-token")
        mock_set.assert_called_once_with("qdrant_api_key", "super-secret-vector-token")


def test_qdrant_client_resolves_keyring_secret() -> None:
    """Verify QdrantClient automatically resolves API key from OS Keyring when omitted."""
    from devops_cli.ai.rag.qdrant import QdrantClient

    with patch(
        "devops_cli.config.settings.get_qdrant_api_key", return_value="resolved-keyring-key"
    ):
        client = QdrantClient("http://localhost:6333", allow_private_network=True)
        assert client.api_key == "resolved-keyring-key"

    # Explicit api_key overrides keyring lookup
    client_explicit = QdrantClient(
        "http://localhost:6333", api_key="explicit-key", allow_private_network=True
    )
    assert client_explicit.api_key == "explicit-key"


def test_workspace_indexer_resolves_keyring_authenticated_client(tmp_path: Path) -> None:
    """Verify WorkspaceIndexer and resolve_qdrant_client authenticate via OS Keyring."""
    from devops_cli.ai.rag.indexer import WorkspaceIndexer, resolve_qdrant_client
    from devops_cli.ai.rag.qdrant import QdrantClient

    with patch("devops_cli.config.settings.get_qdrant_api_key", return_value="vault-qdrant-token"):
        client = resolve_qdrant_client("http://localhost:6333", allow_private_network=True)
        assert client.api_key == "vault-qdrant-token"

        mock_embedder = MagicMock()
        mock_embedder.model = "test-model"

        # 1. When qdrant client is omitted, it must resolve automatically via Keyring
        indexer = WorkspaceIndexer(qdrant=None, embedder=mock_embedder, cache_dir=tmp_path)
        assert indexer.qdrant is not None
        assert indexer.qdrant.api_key == "vault-qdrant-token"

        # 2. When an unauthenticated qdrant client is provided, it must backfill from Keyring
        unauth_client = QdrantClient(
            "http://localhost:6333", api_key=None, allow_private_network=True
        )
        unauth_client.api_key = None  # force null
        indexer_backfill = WorkspaceIndexer(
            qdrant=unauth_client, embedder=mock_embedder, cache_dir=tmp_path
        )
        assert indexer_backfill.qdrant.api_key == "vault-qdrant-token"


def test_fetch_qdrant_api_key_from_k8s() -> None:
    """Verify fetch_qdrant_api_key decodes Secret field and synchronizes to Keyring."""
    from devops_cli.k8s.credentials import fetch_qdrant_api_key

    mock_secret_data = {"api-key": "k8s-cluster-secret-key"}
    with (
        patch("devops_cli.k8s.credentials.fetch_secret_data", return_value=mock_secret_data),
        patch("devops_cli.k8s.credentials._keyring_set") as mock_keyring_set,
        patch("devops_cli.k8s.credentials.GLOBAL_METRICS.increment_counter") as mock_metric,
    ):
        key = fetch_qdrant_api_key(namespace="llm", save_to_keyring=True)
        assert key == "k8s-cluster-secret-key"
        mock_keyring_set.assert_called_once_with("qdrant_api_key", "k8s-cluster-secret-key")
        mock_metric.assert_called_once()


def test_sync_k8s_credentials_llm_stack() -> None:
    """Verify sync_k8s_credentials synchronizes Qdrant API key when stack is llm or all."""
    from devops_cli.k8s.credentials import sync_k8s_credentials

    with patch(
        "devops_cli.k8s.credentials.fetch_qdrant_api_key", return_value="synced-qdrant-key"
    ) as mock_fetch:
        results = sync_k8s_credentials(stack="llm", save_to_keyring=True)
        assert results == {"qdrant": True}
        mock_fetch.assert_called_once()

    with patch("devops_cli.k8s.credentials.fetch_qdrant_api_key", return_value=None) as mock_fetch:
        results = sync_k8s_credentials(stack="llm", save_to_keyring=True)
        assert results == {"qdrant": False}


def test_ensure_qdrant_api_key_secret_lifecycle() -> None:
    """Verify _ensure_qdrant_api_key_secret provisions Secret in K8s and syncs to Keyring."""
    from devops_cli.commands.k8s.stack_lifecycle import _ensure_qdrant_api_key_secret

    # Scenario A: Secret already exists in Kubernetes -> fetch and sync to Keyring
    with (
        patch("devops_cli.commands.k8s.stack_lifecycle.run_subprocess") as mock_run,
        patch("devops_cli.k8s.credentials.fetch_qdrant_api_key", return_value="existing-key"),
    ):
        mock_run.return_value = MagicMock(returncode=0)
        key = _ensure_qdrant_api_key_secret(namespace="llm")
        assert key == "existing-key"

    # Scenario B: Secret does not exist -> generate new key, create Secret, and store in Keyring
    with (
        patch("devops_cli.commands.k8s.stack_lifecycle.run_subprocess") as mock_run,
        patch("devops_cli.config.settings._keyring_get", return_value=None),
        patch("devops_cli.config.settings._keyring_set") as mock_keyring_set,
    ):
        # First call: kubectl get secret -> returncode 1 (not found)
        # Second call: kubectl create secret -> returncode 0
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="Error: secrets 'qdrant-api-key' not found"),
            MagicMock(returncode=0, stdout="secret/qdrant-api-key created"),
        ]
        key = _ensure_qdrant_api_key_secret(namespace="llm")
        assert key is not None
        assert len(key) >= 32
        mock_keyring_set.assert_called_once_with("qdrant_api_key", key)
