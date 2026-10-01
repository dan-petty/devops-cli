"""Kubernetes stack credential discovery and secure OS Keyring synchronization."""

from __future__ import annotations

import base64
import binascii
import itertools
import logging
from typing import Any

from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_BOOTSTRAP_STACK,
    DEFAULT_LLM_NAMESPACE,
    DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import _keyring_set
from devops_cli.core.process import run_subprocess
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


def _clean_service_base_url(base_url: str) -> str:
    """Ensure base URL has scheme and no trailing slash."""
    clean = (base_url or "").strip().rstrip("/")
    if not clean:
        return ""
    if not clean.startswith(("http://", "https://")):
        return f"http://{clean}"
    return clean


def _safe_keyring_set(key: str, value: str) -> None:
    """Store secret in OS Keyring and record telemetry metric."""
    try:
        _keyring_set(key, value)
        GLOBAL_METRICS.increment_counter("k8s_credentials_synced_total", labels={"service": key})
    except Exception as exc:
        logger.debug("Could not store %s in OS Keyring: %s", key, exc)


def _decode_k8s_secret_field(raw_b64: str) -> str | None:
    """Safely decode base64 secret field into string."""
    cleaned = raw_b64.strip()
    if not cleaned:
        return None
    try:
        decoded_bytes = base64.b64decode(cleaned)
        return decoded_bytes.decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        logger.debug("Failed to decode k8s secret field as utf-8: %s", type(exc).__name__)
        return None


def fetch_secret_data(
    secret_name: str,
    namespace: str,
    context: str | None = None,
) -> dict[str, str]:
    """Fetch and decode all data fields from a Kubernetes Secret in a single call."""
    import json

    from devops_cli.core.validation import validate_k8s_name

    validate_k8s_name(secret_name, "secret_name")
    validate_k8s_name(namespace, "namespace", namespace=True)
    if context:
        validate_k8s_name(context, "context")

    cmd = [
        "kubectl",
        "get",
        "secret",
        secret_name,
        "-n",
        namespace,
        "-o=json",
    ]
    if context:
        cmd.extend(["--context", context])

    res = run_subprocess(cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    if res.returncode != 0:
        stderr_msg = res.stderr.strip() if res.stderr else ""
        if "NotFound" in stderr_msg or "not found" in stderr_msg.lower():
            logger.debug("K8s secret resource not found in namespace %s", namespace)
        else:
            logger.warning(
                "kubectl get secret failed in namespace %s (exit %d)",
                namespace,
                res.returncode,
            )
        return {}
    if not res.stdout.strip():
        return {}

    try:
        payload = json.loads(res.stdout)
        data = payload.get("data", {})
        return {k: _decode_k8s_secret_field(v) or "" for k, v in data.items() if isinstance(v, str)}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as err:
        logger.warning(
            "Failed to parse secret payload in namespace %s: %s", namespace, type(err).__name__
        )
        return {}


def fetch_secret_field(
    secret_name: str,
    field: str,
    namespace: str,
    context: str | None = None,
) -> str | None:
    """Fetch and decode a specific field from a Kubernetes Secret."""
    data = fetch_secret_data(secret_name, namespace, context=context)
    val = data.get(field)
    return val if val else None


@trace_span("k8s.credentials.argocd")
def fetch_argocd_password(
    namespace: str = DEFAULT_ARGOCD_NAMESPACE,
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch initial ArgoCD admin password from Kubernetes and store in keyring."""
    pw = fetch_secret_field(
        secret_name="argocd-initial-admin-secret",
        field="password",
        namespace=namespace,
        context=context,
    )
    if pw and save_to_keyring:
        _keyring_set("argocd_password", pw)
        GLOBAL_METRICS.increment_counter(
            "k8s_credentials_synced_total", labels={"service": "argocd"}
        )
    return pw


def _find_grafana_field_in_secret(
    secret_name: str,
    namespace: str,
    candidate_fields: list[str],
    context: str | None,
) -> str | None:
    data = fetch_secret_data(secret_name, namespace, context=context)
    if not data:
        return None
    for field in candidate_fields:
        pw = data.get(field)
        if pw:
            return pw
    return None


@trace_span("k8s.credentials.grafana")
def fetch_grafana_password(
    namespaces: list[str] | None = None,
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch Grafana admin password from Kubernetes and store in keyring."""
    candidate_namespaces = namespaces or ["monitoring", "grafana", "default"]
    candidate_secrets = ["kube-prometheus-stack-grafana", "grafana", "grafana-admin-credentials"]
    candidate_fields = ["admin-password", "admin_password", "password"]

    for ns, secret_name in itertools.product(candidate_namespaces, candidate_secrets):
        pw = _find_grafana_field_in_secret(secret_name, ns, candidate_fields, context)
        if not pw:
            continue
        if save_to_keyring:
            _keyring_set("grafana_password", pw)
            GLOBAL_METRICS.increment_counter(
                "k8s_credentials_synced_total", labels={"service": "grafana"}
            )
        return pw
    return None


@trace_span("k8s.credentials.qdrant")
def fetch_qdrant_api_key(
    namespace: str = DEFAULT_LLM_NAMESPACE,
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch Qdrant API key from Kubernetes Secret and store in keyring."""
    key = fetch_secret_field(
        secret_name="qdrant-api-key",
        field="api-key",
        namespace=namespace,
        context=context,
    )
    if key and save_to_keyring:
        _keyring_set("qdrant_api_key", key)
        GLOBAL_METRICS.increment_counter(
            "k8s_credentials_synced_total", labels={"service": "qdrant"}
        )
    return key


@trace_span("k8s.credentials.argocd.token")
def mint_argocd_token(
    base_url: str,
    password: str,
    *,
    save_to_keyring: bool = True,
    allow_private_network: bool = True,
    timeout: float = DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
) -> str | None:
    """Acquire an ArgoCD session token by authenticating with the admin password."""
    import httpx2

    from devops_cli.http.validation import validate_service_url

    clean_base = _clean_service_base_url(base_url)
    if not clean_base or not password:
        return None
    try:
        validate_service_url(clean_base, "ArgoCD", allow=allow_private_network)
    except ValueError as exc:
        logger.debug("Invalid ArgoCD URL for token minting: %s", exc)
        return None

    url = f"{clean_base}/api/v1/session"
    payload = {"username": "admin", "password": password}
    try:
        with httpx2.Client(verify=False, timeout=timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token and isinstance(token, str):
                    if save_to_keyring:
                        _safe_keyring_set("argocd_token", token)
                    return token
            logger.debug("ArgoCD session creation returned status %d", resp.status_code)
    except Exception as exc:
        logger.debug("Failed to mint ArgoCD token via %s: %s", url, type(exc).__name__)
    return None


def _find_or_create_grafana_sa(
    client: Any,
    base_url: str,
) -> int | None:
    """Find existing or create new service account for devops-cli in Grafana."""
    sa_url = f"{base_url}/api/serviceaccounts"
    try:
        sa_resp = client.post(sa_url, json={"name": "devops-cli", "role": "Admin"})
        if sa_resp.status_code in (200, 201):
            sa_id = sa_resp.json().get("id")
            return int(sa_id) if sa_id is not None else None

        if sa_resp.status_code in (400, 409):
            search_resp = client.get(f"{sa_url}/search", params={"query": "devops-cli"})
            if search_resp.status_code == 200:
                accounts = search_resp.json().get("serviceAccounts", [])
                for sa in accounts:
                    if sa.get("name") == "devops-cli" and "id" in sa:
                        return int(sa["id"])
    except Exception as exc:
        logger.debug("Grafana service account discovery failed: %s", exc)
    return None


def _create_grafana_sa_token(
    client: Any,
    base_url: str,
    sa_id: int,
) -> str | None:
    """Create a token for the specified service account."""
    import time

    token_url = f"{base_url}/api/serviceaccounts/{sa_id}/tokens"
    token_name = f"devops-cli-{int(time.time())}"
    try:
        token_resp = client.post(token_url, json={"name": token_name})
        if token_resp.status_code in (200, 201):
            key = token_resp.json().get("key")
            return str(key) if key else None
    except Exception as exc:
        logger.debug("Grafana SA token creation failed: %s", exc)
    return None


def _create_grafana_legacy_key(
    client: Any,
    base_url: str,
) -> str | None:
    """Fallback token generation for legacy Grafana versions using /api/auth/keys."""
    import time

    key_url = f"{base_url}/api/auth/keys"
    key_name = f"devops-cli-{int(time.time())}"
    try:
        resp = client.post(key_url, json={"name": key_name, "role": "Admin"})
        if resp.status_code in (200, 201):
            key = resp.json().get("key")
            return str(key) if key else None
    except Exception as exc:
        logger.debug("Grafana legacy API key creation failed: %s", exc)
    return None


@trace_span("k8s.credentials.grafana.token")
def mint_grafana_token(
    base_url: str,
    password: str,
    *,
    save_to_keyring: bool = True,
    allow_private_network: bool = True,
    timeout: float = DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
) -> str | None:
    """Acquire a Grafana service account token by authenticating with the admin password."""
    import httpx2

    from devops_cli.http.validation import validate_service_url

    clean_base = _clean_service_base_url(base_url)
    if not clean_base or not password:
        return None
    try:
        validate_service_url(clean_base, "Grafana", allow=allow_private_network)
    except ValueError as exc:
        logger.debug("Invalid Grafana URL for token minting: %s", exc)
        return None

    try:
        with httpx2.Client(
            auth=("admin", password),
            verify=False,
            timeout=timeout,
        ) as client:
            sa_id = _find_or_create_grafana_sa(client, clean_base)
            token = (
                _create_grafana_sa_token(client, clean_base, sa_id) if sa_id is not None else None
            )
            if not token:
                token = _create_grafana_legacy_key(client, clean_base)

            if token and save_to_keyring:
                _safe_keyring_set("grafana_token", token)
            return token
    except Exception as exc:
        logger.debug("Failed to mint Grafana token via %s: %s", clean_base, type(exc).__name__)
    return None


def get_or_mint_argocd_token(settings: Any) -> str | None:
    """Resolve ArgoCD token, minting on-demand via admin password if token is missing."""
    from devops_cli.config.settings import get_argocd_password, get_argocd_token

    token = get_argocd_token(settings)
    if token and not token.startswith("*"):
        return token

    pw = get_argocd_password(settings)
    argo_url = getattr(getattr(settings, "argocd", None), "url", None)
    if pw and argo_url:
        allow = getattr(getattr(settings, "ai", None), "allow_private_network", True)
        return mint_argocd_token(
            argo_url,
            pw,
            save_to_keyring=True,
            allow_private_network=allow,
        )
    return None


def get_or_mint_grafana_auth(settings: Any) -> tuple[str | None, str | None]:
    """Resolve Grafana authentication, returning (bearer_token, basic_auth_header)."""
    from devops_cli.config.settings import get_grafana_password, get_grafana_token

    token = get_grafana_token(settings)
    if token and not token.startswith("*"):
        return token, None

    pw = get_grafana_password(settings)
    if not pw:
        return None, None

    graf_url = getattr(getattr(settings, "grafana", None), "url", None)
    if graf_url:
        allow = getattr(getattr(settings, "ai", None), "allow_private_network", True)
        minted = mint_grafana_token(
            graf_url,
            pw,
            save_to_keyring=True,
            allow_private_network=allow,
        )
        if minted:
            return minted, None

    auth_bytes = f"admin:{pw}".encode()
    return None, f"Basic {base64.b64encode(auth_bytes).decode('utf-8')}"


def _resolve_service_url(service: str, override_url: str | None) -> str | None:
    """Resolve service URL from explicit override or settings."""
    if override_url:
        return override_url
    try:
        from devops_cli.config.settings import load_settings

        settings = load_settings()
        if service == "argocd":
            return getattr(getattr(settings, "argocd", None), "url", None)
        if service == "grafana":
            return getattr(getattr(settings, "grafana", None), "url", None)
    except Exception:
        pass
    return None


@trace_span("k8s.credentials.sync")
def sync_k8s_credentials(
    context: str | None = None,
    stack: str = DEFAULT_BOOTSTRAP_STACK,
    save_to_keyring: bool = True,
    argocd_url: str | None = None,
    grafana_url: str | None = None,
) -> dict[str, bool]:
    """Discover and synchronize Kubernetes stack credentials into OS Keyring."""
    results: dict[str, bool] = {}
    if stack in ("infra", "all"):
        argo_pw = fetch_argocd_password(context=context, save_to_keyring=save_to_keyring)
        results["argocd"] = argo_pw is not None

        effective_argo_url = _resolve_service_url("argocd", argocd_url)
        if argo_pw and effective_argo_url:
            argo_tok = mint_argocd_token(
                effective_argo_url, argo_pw, save_to_keyring=save_to_keyring
            )
            if argo_tok:
                results["argocd_token"] = True

        grafana_pw = fetch_grafana_password(context=context, save_to_keyring=save_to_keyring)
        results["grafana"] = grafana_pw is not None

        effective_grafana_url = _resolve_service_url("grafana", grafana_url)
        if grafana_pw and effective_grafana_url:
            graf_tok = mint_grafana_token(
                effective_grafana_url, grafana_pw, save_to_keyring=save_to_keyring
            )
            if graf_tok:
                results["grafana_token"] = True

    if stack in ("llm", "all"):
        qdrant_key = fetch_qdrant_api_key(context=context, save_to_keyring=save_to_keyring)
        results["qdrant"] = qdrant_key is not None

    return results
