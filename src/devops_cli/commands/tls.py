"""TLS certificate management and enablement subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import (
    CONST_CA_CERT_NAME,
    CONST_CA_KEY_NAME,
    CONST_SERVER_CERT_NAME,
    CONST_SERVER_KEY_NAME,
)
from devops_cli.config.defaults import (
    DEFAULT_CA_VALIDITY_DAYS,
    DEFAULT_CERT_COMMON_NAME,
    DEFAULT_HOMELAB_DOMAINS,
    DEFAULT_HOMELAB_IPS,
    DEFAULT_K8S_TLS_SECRET_NAME,
    DEFAULT_TLS_COUNTRY,
    DEFAULT_TLS_DIR,
    DEFAULT_TLS_KEY_SIZE,
    DEFAULT_TLS_ORGANIZATION,
    DEFAULT_TLS_VALIDITY_DAYS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_k8s_name
from devops_cli.crypto.tls_certificates import (
    generate_ca_certificate,
    generate_homelab_tls_bundle,
    generate_server_certificate,
    inspect_certificate,
    verify_certificate,
)
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.tls import KubernetesTLSSecretResult
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
)

app = new_typer(
    help=HELP.tls.app,
    no_args_is_help=True,
)


# =============================================================================
# Command: devops tls ca
# =============================================================================


@app.command("ca")
def cmd_ca(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help=HELP.tls.output_dir),
    ] = DEFAULT_TLS_DIR,
    common_name: Annotated[
        str,
        typer.Option("--common-name", "-cn", help=HELP.tls.common_name),
    ] = f"{DEFAULT_TLS_ORGANIZATION} Root CA",
    organization: Annotated[
        str,
        typer.Option("--organization", "-org", help=HELP.tls.organization),
    ] = DEFAULT_TLS_ORGANIZATION,
    country: Annotated[
        str,
        typer.Option("--country", "-c", help=HELP.tls.country),
    ] = DEFAULT_TLS_COUNTRY,
    validity_days: Annotated[
        int,
        typer.Option("--validity-days", "-d", help=HELP.tls.validity_days),
    ] = DEFAULT_CA_VALIDITY_DAYS,
    key_size: Annotated[
        int,
        typer.Option("--key-size", "-k", help=HELP.tls.key_size),
    ] = DEFAULT_TLS_KEY_SIZE,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help=HELP.tls.overwrite),
    ] = False,
) -> None:
    """Generate a self-signed Root Certificate Authority (CA) key pair."""
    if is_dry_run():
        render_dry_run_result(
            command="devops tls ca",
            action="generate_root_ca",
            target=str(output_dir),
            details={
                "common_name": common_name,
                "organization": organization,
                "validity_days": validity_days,
                "key_size": key_size,
                "ca_cert": str(output_dir / CONST_CA_CERT_NAME),
                "ca_key": str(output_dir / CONST_CA_KEY_NAME),
            },
        )
        return

    ca_cert, ca_key = generate_ca_certificate(
        output_dir=output_dir,
        common_name=common_name,
        organization=organization,
        country=country,
        validity_days=validity_days,
        key_size=key_size,
        overwrite=overwrite,
    )

    info = inspect_certificate(ca_cert)
    expires_str = info.not_after.strftime("%Y-%m-%d") if info.not_after else "N/A"

    rows = [
        ["CA Certificate", str(ca_cert)],
        ["CA Private Key (0600)", str(ca_key)],
        ["Common Name", common_name],
        ["Organization", organization],
        ["Validity", f"{validity_days} days (Expires {expires_str})"],
        ["Key Size", f"{key_size}-bit RSA"],
        ["SHA-256 Fingerprint", info.fingerprint_sha256[:32] + "..."],
    ]

    print_table(
        title="Generated Root Certificate Authority (CA)",
        columns=[("Property", "cyan"), ("Value", "white")],
        rows=rows,
    )


# =============================================================================
# Command: devops tls cert
# =============================================================================


@app.command("cert")
def generate_cert_cmd(
    common_name: Annotated[
        str,
        typer.Option("--common-name", "-cn", help=HELP.tls.common_name),
    ] = DEFAULT_CERT_COMMON_NAME,
    san: Annotated[
        list[str] | None,
        typer.Option("--san", "-s", help=HELP.tls.san),
    ] = None,
    ca_cert: Annotated[
        Path | None,
        typer.Option("--ca-cert", help=HELP.tls.ca_cert),
    ] = None,
    ca_key: Annotated[
        Path | None,
        typer.Option("--ca-key", help=HELP.tls.ca_key),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help=HELP.tls.output_dir),
    ] = DEFAULT_TLS_DIR,
    validity_days: Annotated[
        int,
        typer.Option("--validity-days", "-d", help=HELP.tls.validity_days),
    ] = DEFAULT_TLS_VALIDITY_DAYS,
    key_size: Annotated[
        int,
        typer.Option("--key-size", "-k", help=HELP.tls.key_size),
    ] = DEFAULT_TLS_KEY_SIZE,
    organization: Annotated[
        str,
        typer.Option("--organization", "-org", help=HELP.tls.organization),
    ] = DEFAULT_TLS_ORGANIZATION,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help=HELP.tls.overwrite),
    ] = False,
) -> None:
    """Generate an X.509 TLS certificate signed by local CA or self-signed."""
    # Default to standard CA path if it exists and no CA specified
    resolved_ca_cert = ca_cert or (output_dir / CONST_CA_CERT_NAME)
    resolved_ca_key = ca_key or (output_dir / CONST_CA_KEY_NAME)

    use_ca = (
        resolved_ca_cert.exists() and resolved_ca_key.exists()
        if (ca_cert or ca_key or (output_dir / CONST_CA_CERT_NAME).exists())
        else False
    )

    san_list = list(san or [])
    if not san_list:
        san_list = [common_name, "127.0.0.1"]

    if is_dry_run():
        render_dry_run_result(
            command="devops tls cert",
            action="generate_tls_certificate",
            target=str(output_dir),
            details={
                "common_name": common_name,
                "sans": san_list,
                "signed_by_ca": use_ca,
                "validity_days": validity_days,
                "cert_path": str(output_dir / CONST_SERVER_CERT_NAME),
                "key_path": str(output_dir / CONST_SERVER_KEY_NAME),
            },
        )
        return

    cert_path, key_path, fullchain = generate_server_certificate(
        common_name=common_name,
        sans=san_list,
        ca_cert_path=resolved_ca_cert if use_ca else None,
        ca_key_path=resolved_ca_key if use_ca else None,
        output_dir=output_dir,
        validity_days=validity_days,
        key_size=key_size,
        organization=organization,
        overwrite=overwrite,
    )

    info = inspect_certificate(cert_path)

    expires_str = info.not_after.strftime("%Y-%m-%d") if info.not_after else "N/A"
    rows = [
        ["Server Certificate", str(cert_path)],
        ["Private Key (0600)", str(key_path)],
    ]
    if fullchain:
        rows.append(["Full Chain Certificate", str(fullchain)])
    rows.extend(
        [
            ["Common Name", common_name],
            ["Subject Alternative Names", ", ".join(info.sans_dns + info.sans_ip)],
            ["Signed By", info.issuer.get("commonName", "Self-Signed")],
            ["Validity", f"{validity_days} days (Expires {expires_str})"],
            ["Fingerprint", info.fingerprint_sha256[:32] + "..."],
        ]
    )

    print_table(
        title="Generated TLS Certificate",
        columns=[("Property", "cyan"), ("Value", "white")],
        rows=rows,
    )


# =============================================================================
# Command: devops tls homelab
# =============================================================================


@app.command("homelab")
def generate_homelab_cmd(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help=HELP.tls.output_dir),
    ] = DEFAULT_TLS_DIR,
    domain: Annotated[
        list[str] | None,
        typer.Option("--domain", "-d", help=HELP.tls.domain),
    ] = None,
    ip: Annotated[
        list[str] | None,
        typer.Option("--ip", "-i", help=HELP.tls.ip),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help=HELP.tls.overwrite),
    ] = False,
) -> None:
    """Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert)."""
    if is_dry_run():
        render_dry_run_result(
            command="devops tls homelab",
            action="generate_homelab_tls_bundle",
            target=str(output_dir),
            details={
                "output_dir": str(output_dir),
                "custom_domains": domain or [],
                "custom_ips": ip or [],
                "default_domains": list(DEFAULT_HOMELAB_DOMAINS),
                "default_ips": list(DEFAULT_HOMELAB_IPS),
            },
        )
        return

    summary = generate_homelab_tls_bundle(
        output_dir=output_dir,
        custom_domains=domain,
        custom_ips=ip,
        overwrite=overwrite,
    )

    rows = [
        ["Root CA Cert", summary.ca_cert_path],
        ["Root CA Key", summary.ca_key_path],
        ["Server Cert (tls.crt)", summary.server_cert_path],
        ["Server Key (tls.key)", summary.server_key_path],
        ["Full Chain (fullchain.crt)", summary.fullchain_path],
        ["Configured Services", ", ".join(summary.services_configured)],
        ["Total SANs Included", str(len(summary.sans))],
    ]

    print_table(
        title="Homelab TLS Certificate Bundle Generated",
        columns=[("Asset", "cyan"), ("Path / Details", "white")],
        rows=rows,
    )
    print_info(
        "\n[dim]To install CA trust on Linux: sudo cp "
        + summary.ca_cert_path
        + " /usr/local/share/ca-certificates/ && sudo update-ca-certificates[/dim]",
        prefix=False,
    )


# =============================================================================
# Command: devops tls inspect
# =============================================================================


@app.command("inspect")
def inspect_cmd(
    cert_path: Annotated[
        Path,
        typer.Argument(help=HELP.tls.cert_file),
    ],
) -> None:
    """Inspect and display metadata of an X.509 certificate."""
    if not cert_path.exists():
        print_error(f"Error: Certificate file not found: {cert_path}", prefix=False)
        raise typer.Exit(1)

    info = inspect_certificate(cert_path)

    subject_str = ", ".join(f"{k}={v}" for k, v in info.subject.items())
    issuer_str = ", ".join(f"{k}={v}" for k, v in info.issuer.items())
    not_before_str = info.not_before.strftime("%Y-%m-%d %H:%M:%S") if info.not_before else "N/A"
    not_after_str = info.not_after.strftime("%Y-%m-%d %H:%M:%S") if info.not_after else "N/A"
    status_str = (
        "[red]EXPIRED[/red]"
        if info.is_expired
        else f"[green]VALID[/green] ({info.days_remaining} days remaining)"
    )

    rows = [
        ["Subject", subject_str],
        ["Issuer", issuer_str],
        ["Is Root CA", "[green]Yes[/green]" if info.is_ca else "No"],
        ["Serial Number", info.serial_number],
        ["Not Before (UTC)", not_before_str],
        ["Not After (UTC)", not_after_str],
        ["Status", status_str],
        ["Public Key", f"{info.key_size}-bit {info.key_type}"],
        ["Signature Algorithm", info.signature_algorithm],
    ]
    if info.sans_dns:
        rows.append(["DNS SANs", ", ".join(info.sans_dns)])
    if info.sans_ip:
        rows.append(["IP SANs", ", ".join(info.sans_ip)])
    rows.append(["SHA-256 Fingerprint", info.fingerprint_sha256])

    print_table(
        title=f"Certificate Inspection: {cert_path.name}",
        columns=[("Field", "cyan"), ("Value", "white")],
        rows=rows,
    )


# =============================================================================
# Command: devops tls verify
# =============================================================================


@app.command("verify")
def verify_cmd(
    cert_path: Annotated[
        Path,
        typer.Argument(help=HELP.tls.leaf_cert),
    ],
    ca_cert: Annotated[
        Path,
        typer.Option("--ca-cert", "-ca", help=HELP.tls.ca_cert),
    ] = DEFAULT_TLS_DIR / CONST_CA_CERT_NAME,
) -> None:
    """Verify an X.509 certificate cryptographic chain against a CA certificate."""
    if not cert_path.exists():
        print_error(f"Error: Certificate file not found: {cert_path}", prefix=False)
        raise typer.Exit(1)
    if not ca_cert.exists():
        print_error(f"Error: CA certificate file not found: {ca_cert}", prefix=False)
        raise typer.Exit(1)

    valid = verify_certificate(cert_path, ca_cert)
    if valid:
        print_success(
            f"Verified: [cyan]{cert_path.name}[/cyan] is valid and signed by "
            f"[cyan]{ca_cert.name}[/cyan]"
        )
    else:
        print_error(
            f"Verification Failed: [cyan]{cert_path.name}[/cyan] is invalid or not signed by "
            f"[cyan]{ca_cert.name}[/cyan]"
        )
        raise typer.Exit(1)


# =============================================================================
# Command: devops tls enable-k8s
# =============================================================================


@app.command("enable-k8s")
def enable_k8s_cmd(
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
        typer.Option("--secret-name", help=HELP.tls.secret_name),
    ] = DEFAULT_K8S_TLS_SECRET_NAME,
    namespaces: Annotated[
        list[str] | None,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help=HELP.tls.overwrite),
    ] = False,
) -> None:
    """Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces."""
    target_namespaces = namespaces or ["argocd", "monitoring", "llm", "otel", "default"]

    if context:
        validate_k8s_name(context, "context")
    for ns in target_namespaces:
        validate_k8s_name(ns, "namespace", namespace=True)

    cert_path = tls_dir / CONST_SERVER_CERT_NAME
    key_path = tls_dir / CONST_SERVER_KEY_NAME

    if is_dry_run():
        render_dry_run_result(
            command="devops tls enable-k8s",
            action="apply_k8s_tls_secrets",
            target=context or "current-context",
            details={
                "secret_name": secret_name,
                "namespaces": target_namespaces,
                "cert_path": str(cert_path),
                "key_path": str(key_path),
            },
        )
        return

    # Generate homelab bundle if certificates don't exist
    if not cert_path.exists() or not key_path.exists() or overwrite:
        print_info(MESSAGES.tls.generating_bundle, prefix=False)
        generate_homelab_tls_bundle(output_dir=tls_dir, overwrite=overwrite)

    print_info(
        f"[bold]Deploying TLS secret '[cyan]{secret_name}[/cyan]' "
        "to Kubernetes namespaces...[/bold]",
        prefix=False,
    )
    results: list[KubernetesTLSSecretResult] = []

    kubectl_ctx = ["--context", context] if context else []

    for ns in target_namespaces:
        # Check if namespace exists or create it
        ns_check = run_subprocess(
            ["kubectl", "get", "namespace", ns] + kubectl_ctx, capture_output=True
        )
        if ns_check.returncode != 0:
            run_subprocess(
                ["kubectl", "create", "namespace", ns] + kubectl_ctx, capture_output=True
            )

        # Delete existing secret before re-creating
        run_subprocess(
            ["kubectl", "delete", "secret", secret_name, "-n", ns] + kubectl_ctx,
            capture_output=True,
        )

        create_cmd = [
            "kubectl",
            "create",
            "secret",
            "tls",
            secret_name,
            f"--cert={cert_path}",
            f"--key={key_path}",
            "-n",
            ns,
        ] + kubectl_ctx

        proc = run_subprocess(create_cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            results.append(
                KubernetesTLSSecretResult(
                    secret_name=secret_name,
                    namespace=ns,
                    created=True,
                    cert_path=str(cert_path),
                    key_path=str(key_path),
                )
            )
        else:
            results.append(
                KubernetesTLSSecretResult(
                    secret_name=secret_name,
                    namespace=ns,
                    created=False,
                    error=proc.stderr.strip() or "Failed to create secret",
                )
            )

    rows: list[list[str]] = []
    for r in results:
        status_display = (
            "[green]✓ Created[/green]" if r.created else f"[red]✗ Failed: {r.error}[/red]"
        )
        rows.append([r.namespace, r.secret_name, status_display])

    print_table(
        title="Kubernetes TLS Secret Deployment",
        columns=[("Namespace", "cyan"), ("Secret Name", "white"), ("Status", "bold")],
        rows=rows,
    )
