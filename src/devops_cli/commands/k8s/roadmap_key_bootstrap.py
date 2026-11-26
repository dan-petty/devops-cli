"""Bootstrap LiteLLM virtual key and Secret for roadmap-service (#5741)."""

from __future__ import annotations

from typing import Annotated

import httpx2
import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.commands.k8s.cluster_secret_push import run_push
from devops_cli.config.defaults import DEFAULT_AI_GATEWAY_URL, DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.config.env import credential
from devops_cli.config.os_keyring import keyring_read, keyring_write
from devops_cli.config.settings import load_settings
from devops_cli.dry_run import dry_run_class, is_dry_run, render_dry_run_result
from devops_cli.exceptions.k8s import ClusterSecretPushError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS, SecretKeyRef, secrets_by_ref
from devops_cli.k8s.secret_push import PushMode, PushOptions, _LiveSecrets
from devops_cli.lang import HELP
from devops_cli.output import print_info, print_success
from devops_cli.security.sanitizer import mask_secrets

KEYRING_ENTRY = credential("roadmap_service.llm_key").keyring_name
TARGET_REF = "devops/roadmap-service-llm-key"


def _resolve_master_key(context: str | None) -> str:
    """Read the master key of the LLM gateway from Secret llm/llm-gateway-secrets."""
    lives = _LiveSecrets(context)
    key = lives.value(SecretKeyRef("llm", "llm-gateway-secrets", "master-key"))
    if not key:
        raise ClusterSecretPushError(
            "Master key not found in Secret llm/llm-gateway-secrets (key: master-key)."
        )
    return key


def _generate_virtual_key(
    gateway_url: str | None,
    master_key: str,
    *,
    alias: str,
    budget: float,
    rpm: int,
    models: str,
) -> str:
    """Call the LiteLLM gateway admin API to mint a scoped virtual key."""
    ai_config = load_settings().ai
    raw_url = gateway_url or ai_config.gateway_url or DEFAULT_AI_GATEWAY_URL
    base_url = raw_url.removesuffix("/v1").rstrip("/")
    endpoint = f"{base_url}/key/generate"

    model_list = [m.strip() for m in models.split(",") if m.strip()]
    payload = {
        "key_alias": alias,
        "max_budget": budget,
        "rpm_limit": rpm,
        "models": model_list,
    }
    level = EgressLevel.PRIVATE if ai_config.allow_private_network else EgressLevel.LOOPBACK
    try:
        with http_client(level, timeout=httpx2.Timeout(DEFAULT_HTTP_TIMEOUT_SECONDS)) as client:
            resp = client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {master_key}"},
            )
            if resp.status_code not in (200, 201):
                raise ClusterSecretPushError(
                    f"Gateway refused key generation ({resp.status_code}): {resp.text[:200]}"
                )
            data = resp.json()
            key = data.get("key")
            if not key or not isinstance(key, str):
                raise ClusterSecretPushError("Gateway response contained no virtual key string.")
            return key
    except httpx2.HTTPError as exc:
        raise ClusterSecretPushError(f"HTTP error communicating with gateway: {exc}") from exc


def _push_roadmap_secret(context: str | None) -> None:
    """Push Secret devops/roadmap-service-llm-key to the cluster."""
    secrets, _ = secrets_by_ref([TARGET_REF], table=CLUSTER_SECRETS)
    run_push(secrets, PushOptions(context=context), mode=PushMode.PUSH)


@dry_run_class("request-plan")
def bootstrap_roadmap_key(
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    models: Annotated[
        str,
        typer.Option(
            "--models",
            "-m",
            help="Allowed models for the virtual key (comma-separated or pattern).",
        ),
    ] = "devops-*",
    budget: Annotated[
        float, typer.Option("--budget", "-b", help="Max spend budget in USD for the virtual key.")
    ] = 50.0,
    rpm: Annotated[
        int, typer.Option("--rpm", help="Requests-per-minute rate limit for the virtual key.")
    ] = 60,
    alias: Annotated[
        str, typer.Option("--alias", help="Key alias on the LiteLLM gateway.")
    ] = "roadmap-service",
    gateway_url: Annotated[
        str | None, typer.Option("--gateway-url", "-u", help="Gateway URL override.")
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Mint a new key and overwrite existing keyring entry and Secret.",
        ),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Bootstrap LiteLLM virtual key and Secret for roadmap-service."""
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    stored_key = keyring_read(KEYRING_ENTRY)
    if stored_key and not force:
        if dry_run or is_dry_run():
            render_dry_run_result(
                command="devops k8s bootstrap-roadmap-key",
                target=TARGET_REF,
                action="bootstrap_roadmap_key_existing",
                details={
                    "alias": alias,
                    "models": models,
                    "context": effective_context,
                    "existing_key": True,
                },
            )
            return
        print_info(f"Using existing roadmap service key from keyring: {mask_secrets(stored_key)}")
        _push_roadmap_secret(effective_context)
        print_success(f"Secret {TARGET_REF} verified and pushed to cluster.")
        return

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops k8s bootstrap-roadmap-key",
            target=TARGET_REF,
            action="bootstrap_roadmap_key",
            details={
                "alias": alias,
                "budget": budget,
                "rpm": rpm,
                "models": models,
                "context": effective_context,
                "existing_key": False,
            },
        )
        return

    master_key = _resolve_master_key(effective_context)
    virtual_key = _generate_virtual_key(
        gateway_url,
        master_key,
        alias=alias,
        budget=budget,
        rpm=rpm,
        models=models,
    )
    keyring_write(KEYRING_ENTRY, virtual_key)
    _push_roadmap_secret(effective_context)
    print_success(f"Minted and pushed roadmap service virtual key: {mask_secrets(virtual_key)}")
