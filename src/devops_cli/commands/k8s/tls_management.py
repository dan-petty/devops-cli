"""Kubernetes TLS secret management and cluster-wide TLS enablement."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
import devops_cli.commands.k8s.networking as net
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SERVER_CERT_NAME,
    CONST_SERVER_KEY_NAME,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_ALL_STACK,
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_K8S_TLS_SECRET_NAME,
    DEFAULT_TLS_DIR,
)
from devops_cli.crypto.tls_certificates import generate_homelab_tls_bundle
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP
from devops_cli.models.tls import KubernetesTLSSecretResult
from devops_cli.output import (
    format_k8s_tls_secrets_table,
    print,
    print_error,
    print_info,
    print_success,
)

if TYPE_CHECKING:
    import subprocess


def _kubectl_error(result: subprocess.CompletedProcess[str]) -> str:
    """Return what kubectl wrote to stderr, bounded, or a generic note when it wrote nothing."""
    return (result.stderr or "").strip()[:CONST_MAX_ERROR_DETAIL_LENGTH] or "kubectl failed"


def _apply_tls_secret(
    secret_name: str,
    namespace: str,
    cert_path: Path,
    key_path: Path,
    kubectl_ctx: list[str],
) -> str | None:
    """Create the TLS secret, or update the one in place, and return kubectl's error if any.

    The secret is rendered with a client-side dry run first, which is where kubectl rejects a
    certificate and key that do not match, and applied only once it renders. The secret already
    in the namespace is never deleted, so a failure leaves it serving.
    """
    rendered = runtime._run_cmd(
        ["kubectl", "create", "secret", "tls", secret_name]
        + [f"--cert={cert_path}", f"--key={key_path}", "-n", namespace]
        + ["--dry-run=client", "-o", "yaml"]
        + kubectl_ctx,
        check=False,
        capture=True,
    )
    if rendered.returncode != 0:
        return _kubectl_error(rendered)
    applied = runtime._run_cmd(
        ["kubectl", "apply", "-f", "-", "-n", namespace] + kubectl_ctx,
        input=rendered.stdout,
        check=False,
        capture=True,
    )
    return None if applied.returncode == 0 else _kubectl_error(applied)


def _deploy_tls_secret(
    secret_name: str,
    namespace: str,
    cert_path: Path,
    key_path: Path,
    kubectl_ctx: list[str],
    *,
    overwrite: bool,
) -> str | None:
    """Put the TLS secret in one namespace, replacing one already there only with overwrite."""
    if overwrite:
        return _apply_tls_secret(secret_name, namespace, cert_path, key_path, kubectl_ctx)
    create_cmd = [
        "kubectl",
        "create",
        "secret",
        "tls",
        secret_name,
        f"--cert={cert_path}",
        f"--key={key_path}",
        "-n",
        namespace,
    ] + kubectl_ctx
    created = runtime._run_cmd(create_cmd, check=False)
    return None if created.returncode == 0 else "Failed to create secret via kubectl"


def create_tls_secret(
    secret_name: Annotated[
        str,
        typer.Argument(help=HELP.k8s.secret_name),
    ],
    namespace: Annotated[
        str,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = DEFAULT_K8S_NAMESPACE,
    cert_path: Annotated[
        Path,
        typer.Option("--cert", help=HELP.k8s.cert_path),
    ] = DEFAULT_TLS_DIR / CONST_SERVER_CERT_NAME,
    key_path: Annotated[
        Path,
        typer.Option("--key", help=HELP.k8s.key_path),
    ] = DEFAULT_TLS_DIR / CONST_SERVER_KEY_NAME,
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help=HELP.options.context),
    ] = None,
) -> None:
    """Create or update a kubernetes.io/tls secret from certificate and private key files."""
    if context:
        runtime._validate_k8s_identifier(context, "context")
    runtime._validate_k8s_identifier(namespace, "namespace", namespace=True)
    runtime._validate_k8s_identifier(secret_name, "secret_name")

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s create-tls-secret",
            target=secret_name,
            action="create_k8s_tls_secret",
            details={
                "secret_name": secret_name,
                "namespace": namespace,
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "context": context,
            },
        )
        return

    if not cert_path.exists():
        print_error(f"Certificate file not found: {cert_path}", prefix=False)
        raise typer.Exit(1)
    if not key_path.exists():
        print_error(f"Key file not found: {key_path}", prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", context] if context else []

    # Ensure namespace exists
    ns_check = runtime._run_cmd(
        ["kubectl", "get", "namespace", namespace] + kubectl_ctx, check=False
    )
    if ns_check.returncode != 0:
        runtime._run_cmd(["kubectl", "create", "namespace", namespace] + kubectl_ctx, check=True)

    error = _apply_tls_secret(secret_name, namespace, cert_path, key_path, kubectl_ctx)
    if error is not None:
        print_error(
            f"Failed to apply TLS secret {secret_name} in namespace {namespace}; "
            f"any existing secret is unchanged: {error}",
            prefix=False,
        )
        raise typer.Exit(1)
    print_success(
        f"Applied TLS secret [cyan]{secret_name}[/cyan] in namespace [magenta]{namespace}[/magenta]"
    )


def enable_tls_stack(
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help=HELP.options.context),
    ] = None,
    tls_dir: Annotated[
        Path,
        typer.Option("--tls-dir", help=HELP.tls.tls_dir),
    ] = DEFAULT_TLS_DIR,
    secret_name: Annotated[
        str,
        typer.Option("--secret-name", help=HELP.k8s.secret_name),
    ] = DEFAULT_K8S_TLS_SECRET_NAME,
    stack: Annotated[
        str,
        typer.Option("--stack", "-s", help=HELP.k8s.stack),
    ] = DEFAULT_K8S_ALL_STACK,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help=HELP.options.overwrite),
    ] = False,
) -> None:
    """Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces."""
    if context:
        runtime._validate_k8s_identifier(context, "context")

    selected_stacks = net._resolve_stacks(stack)

    # Resolve target namespaces based on selected stacks
    namespaces_to_target: list[str] = [DEFAULT_K8S_NAMESPACE]
    if "infra" in selected_stacks:
        namespaces_to_target.extend(["argocd", "monitoring", "otel"])
    if "llm" in selected_stacks:
        namespaces_to_target.extend(["llm"])

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s enable-tls",
            target=stack,
            action="enable_k8s_tls_stack",
            details={
                "tls_dir": str(tls_dir),
                "secret_name": secret_name,
                "stack": stack,
                "namespaces": namespaces_to_target,
                "context": context,
            },
        )
        return

    # Check if certificates exist; if not and overwrite is requested, generate bundle
    cert_path = tls_dir / CONST_SERVER_CERT_NAME
    key_path = tls_dir / CONST_SERVER_KEY_NAME

    if not (cert_path.exists() and key_path.exists()):
        print_info(f"Certificates missing under {tls_dir}. Generating bundle...")
        generate_homelab_tls_bundle(output_dir=tls_dir, overwrite=overwrite)

    results: list[KubernetesTLSSecretResult] = []
    kubectl_ctx = ["--context", context] if context else []

    for ns in namespaces_to_target:
        # Check if namespace exists before attempting secret creation
        ns_check = runtime._run_cmd(["kubectl", "get", "namespace", ns] + kubectl_ctx, check=False)
        if ns_check.returncode != 0:
            results.append(
                KubernetesTLSSecretResult(
                    secret_name=secret_name,
                    namespace=ns,
                    created=False,
                    cert_path=str(cert_path),
                    key_path=str(key_path),
                    error=f"Namespace {ns} does not exist in cluster",
                )
            )
            continue

        error = _deploy_tls_secret(
            secret_name, ns, cert_path, key_path, kubectl_ctx, overwrite=overwrite
        )
        results.append(
            KubernetesTLSSecretResult(
                secret_name=secret_name,
                namespace=ns,
                created=error is None,
                cert_path=str(cert_path),
                key_path=str(key_path),
                error=error,
            )
        )

    print(format_k8s_tls_secrets_table(results))
