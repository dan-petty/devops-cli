"""TLS certificate management and enablement subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from devops_cli.config.constants import (
    CONST_CA_CERT_NAME,
    CONST_CA_KEY_NAME,
    CONST_SERVER_CERT_NAME,
    CONST_SERVER_KEY_NAME,
)
from devops_cli.config.defaults import (
    DEFAULT_CA_VALIDITY_DAYS,
    DEFAULT_HOMELAB_DOMAINS,
    DEFAULT_HOMELAB_IPS,
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
from devops_cli.lang.en import MESSAGES
from devops_cli.models.tls import KubernetesTLSSecretResult
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
)

app = new_typer(
    help="X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.",
    no_args_is_help=True,
)


# =============================================================================
# Command: devops tls ca
# =============================================================================


@app.command("ca")
def cmd_ca(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory to save CA certificate and key"),
    ] = DEFAULT_TLS_DIR,
    common_name: Annotated[
        str,
        typer.Option("--common-name", "-cn", help="Common Name for the Root CA"),
    ] = f"{DEFAULT_TLS_ORGANIZATION} Root CA",
    organization: Annotated[
        str,
        typer.Option("--organization", "-org", help="Organization name"),
    ] = DEFAULT_TLS_ORGANIZATION,
    country: Annotated[
        str,
        typer.Option("--country", "-c", help="2-letter country code"),
    ] = DEFAULT_TLS_COUNTRY,
    validity_days: Annotated[
        int,
        typer.Option("--validity-days", "-d", help="Validity period in days"),
    ] = DEFAULT_CA_VALIDITY_DAYS,
    key_size: Annotated[
        int,
        typer.Option("--key-size", "-k", help="RSA key size in bits (2048 or 4096)"),
    ] = DEFAULT_TLS_KEY_SIZE,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help="Overwrite existing files"),
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

    table = Table(title="Generated Root Certificate Authority (CA)", title_style="bold green")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("CA Certificate", str(ca_cert))
    table.add_row("CA Private Key (0600)", str(ca_key))
    table.add_row("Common Name", common_name)
    table.add_row("Organization", organization)
    expires_str = info.not_after.strftime("%Y-%m-%d") if info.not_after else "N/A"
    table.add_row(
        "Validity",
        f"{validity_days} days (Expires {expires_str})",
    )
    table.add_row("Key Size", f"{key_size}-bit RSA")
    table.add_row("SHA-256 Fingerprint", info.fingerprint_sha256[:32] + "...")

    print_table(table)


# =============================================================================
# Command: devops tls cert
# =============================================================================


@app.command("cert")
def generate_cert_cmd(
    common_name: Annotated[
        str,
        typer.Option("--common-name", "-cn", help="Primary Common Name or domain"),
    ] = "localhost",
    san: Annotated[
        list[str] | None,
        typer.Option("--san", "-s", help="Subject Alternative Names (DNS names or IP addresses)"),
    ] = None,
    ca_cert: Annotated[
        Path | None,
        typer.Option("--ca-cert", help="Path to signing CA certificate (ca.crt)"),
    ] = None,
    ca_key: Annotated[
        Path | None,
        typer.Option("--ca-key", help="Path to signing CA private key (ca.key)"),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory to save certificate and key"),
    ] = DEFAULT_TLS_DIR,
    validity_days: Annotated[
        int,
        typer.Option("--validity-days", "-d", help="Validity period in days"),
    ] = DEFAULT_TLS_VALIDITY_DAYS,
    key_size: Annotated[
        int,
        typer.Option("--key-size", "-k", help="RSA key size in bits (2048 or 4096)"),
    ] = DEFAULT_TLS_KEY_SIZE,
    organization: Annotated[
        str,
        typer.Option("--organization", "-org", help="Organization name"),
    ] = DEFAULT_TLS_ORGANIZATION,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help="Overwrite existing files"),
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

    table = Table(title="Generated TLS Certificate", title_style="bold green")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Server Certificate", str(cert_path))
    table.add_row("Private Key (0600)", str(key_path))
    if fullchain:
        table.add_row("Full Chain Certificate", str(fullchain))
    table.add_row("Common Name", common_name)
    table.add_row("Subject Alternative Names", ", ".join(info.sans_dns + info.sans_ip))
    table.add_row("Signed By", info.issuer.get("commonName", "Self-Signed"))
    expires_str = info.not_after.strftime("%Y-%m-%d") if info.not_after else "N/A"
    table.add_row(
        "Validity",
        f"{validity_days} days (Expires {expires_str})",
    )
    table.add_row("Fingerprint", info.fingerprint_sha256[:32] + "...")

    print_table(table)


# =============================================================================
# Command: devops tls homelab
# =============================================================================


@app.command("homelab")
def generate_homelab_cmd(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory to save certificates"),
    ] = DEFAULT_TLS_DIR,
    domain: Annotated[
        list[str] | None,
        typer.Option("--domain", "-d", help="Additional custom domains to include in SANs"),
    ] = None,
    ip: Annotated[
        list[str] | None,
        typer.Option("--ip", "-i", help="Additional custom IP addresses to include in SANs"),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help="Regenerate all existing certificates"),
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

    table = Table(title="Homelab TLS Certificate Bundle Generated", title_style="bold blue")
    table.add_column("Asset", style="cyan")
    table.add_column("Path / Details", style="white")
    table.add_row("Root CA Cert", summary.ca_cert_path)
    table.add_row("Root CA Key", summary.ca_key_path)
    table.add_row("Server Cert (tls.crt)", summary.server_cert_path)
    table.add_row("Server Key (tls.key)", summary.server_key_path)
    table.add_row("Full Chain (fullchain.crt)", summary.fullchain_path)
    table.add_row("Configured Services", ", ".join(summary.services_configured))
    table.add_row("Total SANs Included", str(len(summary.sans)))

    print_table(table)
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
        typer.Argument(help="Path to X.509 certificate file (.crt or .pem)"),
    ],
) -> None:
    """Inspect and display metadata of an X.509 certificate."""
    if not cert_path.exists():
        print_error(f"Error: Certificate file not found: {cert_path}", prefix=False)
        raise typer.Exit(1)

    info = inspect_certificate(cert_path)

    table = Table(title=f"Certificate Inspection: {cert_path.name}", title_style="bold cyan")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    subject_str = ", ".join(f"{k}={v}" for k, v in info.subject.items())
    issuer_str = ", ".join(f"{k}={v}" for k, v in info.issuer.items())
    table.add_row("Subject", subject_str)
    table.add_row("Issuer", issuer_str)
    table.add_row("Is Root CA", "[green]Yes[/green]" if info.is_ca else "No")
    table.add_row("Serial Number", info.serial_number)
    table.add_row(
        "Not Before (UTC)",
        info.not_before.strftime("%Y-%m-%d %H:%M:%S") if info.not_before else "N/A",
    )
    table.add_row(
        "Not After (UTC)", info.not_after.strftime("%Y-%m-%d %H:%M:%S") if info.not_after else "N/A"
    )

    status_str = (
        "[red]EXPIRED[/red]"
        if info.is_expired
        else f"[green]VALID[/green] ({info.days_remaining} days remaining)"
    )
    table.add_row("Status", status_str)
    table.add_row("Public Key", f"{info.key_size}-bit {info.key_type}")
    table.add_row("Signature Algorithm", info.signature_algorithm)
    if info.sans_dns:
        table.add_row("DNS SANs", ", ".join(info.sans_dns))
    if info.sans_ip:
        table.add_row("IP SANs", ", ".join(info.sans_ip))
    table.add_row("SHA-256 Fingerprint", info.fingerprint_sha256)

    print_table(table)


# =============================================================================
# Command: devops tls verify
# =============================================================================


@app.command("verify")
def verify_cmd(
    cert_path: Annotated[
        Path,
        typer.Argument(help="Path to leaf certificate file (.crt or .pem)"),
    ],
    ca_cert: Annotated[
        Path,
        typer.Option("--ca-cert", "-ca", help="Path to Root CA certificate file (ca.crt)"),
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
        typer.Option("--context", "-c", help="Kubernetes cluster context (e.g. minikube, default)"),
    ] = None,
    tls_dir: Annotated[
        Path,
        typer.Option("--tls-dir", help="Directory with generated TLS certificates"),
    ] = DEFAULT_TLS_DIR,
    secret_name: Annotated[
        str,
        typer.Option("--secret-name", help="Kubernetes TLS secret name to create"),
    ] = "homelab-tls",
    namespaces: Annotated[
        list[str] | None,
        typer.Option("--namespace", "-n", help="Target namespaces to deploy TLS secret into"),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help="Regenerate certs if missing"),
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

    table = Table(title="Kubernetes TLS Secret Deployment", title_style="bold blue")
    table.add_column("Namespace", style="cyan")
    table.add_column("Secret Name", style="white")
    table.add_column("Status", style="bold")

    for r in results:
        status_display = (
            "[green]✓ Created[/green]" if r.created else f"[red]✗ Failed: {r.error}[/red]"
        )
        table.add_row(r.namespace, r.secret_name, status_display)

    print_table(table)
