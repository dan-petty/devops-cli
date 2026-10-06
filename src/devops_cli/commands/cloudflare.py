"""CLI command group for Cloudflare Zero Trust tunnels and DNS management."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.config.constants import (
    CONST_CLOUDFLARE_BYPASS_POLICY_NAME,
    CONST_CLOUDFLARE_DEFAULT_SERVICE,
    CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS,
    CONST_CLOUDFLARE_RECORD_COMMENT,
)
from devops_cli.config.settings import Settings, get_cloudflare_api_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.cloudflare import CloudflareAuthError, CloudflareError
from devops_cli.lang import HELP
from devops_cli.models.cloudflare import CloudflareDNSRecord, CloudflareTunnelIngressRule
from devops_cli.output import (
    format_json,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

app = new_typer(help=HELP.cloudflare.app, no_args_is_help=True)
dns_app = new_typer(help=HELP.cloudflare.dns, no_args_is_help=True)
tunnel_app = new_typer(help=HELP.cloudflare.tunnel, no_args_is_help=True)
access_app = new_typer(help="Cloudflare Zero Trust Access management", no_args_is_help=True)

app.add_typer(dns_app, name="dns")
app.add_typer(tunnel_app, name="tunnel")
app.add_typer(access_app, name="access")


def _print_cloudflare_error(action: str, exc: CloudflareError) -> None:
    """Print sanitized Cloudflare error message masking any tokens or keys."""
    safe_msg = mask_secrets(exc.message)
    print_error(f"{action}: {safe_msg}")


def _resolve_client(settings: Settings | None = None) -> CloudflareClient:
    """Resolve and instantiate CloudflareClient from configuration and keyring."""
    cfg_settings = settings or load_settings()
    token = get_cloudflare_api_token(cfg_settings)
    if not token:
        raise CloudflareAuthError(
            "Cloudflare API token is not configured. "
            "Set it using 'devops config set cloudflare.api_token <token>' "
            "or export DEVOPS_CLI_CLOUDFLARE_API_TOKEN."
        )
    return CloudflareClient(
        token=token,
        account_id=cfg_settings.cloudflare.account_id,
        zone_id=cfg_settings.cloudflare.zone_id,
    )


def _render_status_table(
    token_status: Any,
    account_id: str | None,
    zone: Any | None,
    tunnel_id: str | None,
) -> None:
    """Display Cloudflare status overview in a structured table."""
    columns = [("Component", "bold cyan"), "Value"]
    rows = [
        ["API Token Status", f"[green]{token_status.status}[/green] (ID: {token_status.id})"],
        ["Account ID", account_id or "[dim](not set)[/dim]"],
    ]
    if zone:
        rows.extend(
            [
                ["Zone ID", zone.id],
                ["Zone Name", zone.name],
                ["Zone Status", f"[green]{zone.status}[/green]"],
                [
                    "Name Servers",
                    ", ".join(zone.name_servers) if zone.name_servers else "[dim](default)[/dim]",
                ],
            ]
        )
    else:
        rows.append(["Zone", "[dim](not configured)[/dim]"])

    rows.append(["Tunnel Identifier", tunnel_id or "[dim](not set)[/dim]"])
    print_table("Cloudflare Zero Trust & DNS Status", columns=columns, rows=rows)


@app.command("status")
@trace_span("cloudflare.status")
def cloudflare_status(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output status details in JSON format"),
    ] = False,
) -> None:
    """Verify Cloudflare API token authentication and inspect zone status."""
    settings = load_settings()
    try:
        client = _resolve_client(settings)
        token_status = client.verify_token()
        zone = client.get_zone() if client.zone_id else None

        if json_output:
            payload: dict[str, Any] = {
                "token": {"id": token_status.id, "status": token_status.status},
                "account_id": client.account_id,
                "zone": zone.model_dump() if zone else None,
                "tunnel_id": settings.cloudflare.tunnel,
            }
            write_stdout(format_json(payload) + "\n")
            return

        _render_status_table(
            token_status=token_status,
            account_id=client.account_id,
            zone=zone,
            tunnel_id=settings.cloudflare.tunnel,
        )
    except CloudflareError as exc:
        _print_cloudflare_error("Cloudflare status check failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("service-status")
@trace_span("cloudflare.service_status")
def cloudflare_service_status(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output status details in JSON format"),
    ] = False,
    emit_telemetry: Annotated[
        bool,
        typer.Option(
            "--emit-telemetry",
            help="Emit operational service status metrics over OpenTelemetry to Prometheus",
        ),
    ] = False,
) -> None:
    """Display Cloudflare published operational status, key components, and active incidents."""
    from devops_cli.exceptions.telemetry import ServiceStatusError
    from devops_cli.telemetry.service_status import (
        emit_service_status_telemetry,
        fetch_cloudflare_status,
        record_service_status_in_registry,
        render_statuspage_summary,
    )

    try:
        summary = fetch_cloudflare_status()
    except ServiceStatusError as exc:
        print_error(f"Failed to fetch Cloudflare service status: {exc.message}")
        raise typer.Exit(1) from exc

    if emit_telemetry:
        emit_service_status_telemetry(summary, "cloudflare")
        record_service_status_in_registry(summary, "cloudflare")

    if json_output:
        write_stdout(format_json(summary.model_dump()) + "\n")
        return

    render_statuspage_summary(summary, "Cloudflare")

    if emit_telemetry:
        print_success("Emitted Cloudflare service status metrics to Prometheus.")


@dns_app.command("list")
@trace_span("cloudflare.dns.list")
def dns_list(
    record_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by DNS record type (e.g. CNAME, A, TXT)"),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by record hostname"),
    ] = None,
    zone_id: Annotated[
        str | None,
        typer.Option("--zone-id", "-z", help="Override Cloudflare Zone ID"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output DNS records in JSON format"),
    ] = False,
) -> None:
    """List DNS records in the designated Cloudflare zone."""
    try:
        client = _resolve_client()
        records = client.list_dns_records(zone_id=zone_id, record_type=record_type, name=name)

        if json_output:
            write_stdout(format_json([r.model_dump() for r in records]) + "\n")
            return

        columns = [("Type", "bold yellow"), ("Name", "bold cyan"), "Content", "Proxied", "TTL"]
        rows = [
            [
                r.type,
                r.name,
                r.content,
                "[green]Yes[/green]" if r.proxied else "[dim]No[/dim]",
                str(r.ttl),
            ]
            for r in records
        ]
        zid = zone_id or client.zone_id or ""
        print_table(f"DNS Records (Zone: {zid})", columns=columns, rows=rows)
    except CloudflareError as exc:
        _print_cloudflare_error("Listing DNS records failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


def _parse_subdomains_arg(subdomains: str | None) -> tuple[str, ...]:
    """Parse comma-separated subdomains or return defaults."""
    if not subdomains:
        return CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS
    return tuple(s.strip() for s in subdomains.split(",") if s.strip())


def _format_subdomain_hostname(sub: str, domain: str) -> str:
    """Format full hostname for a given subdomain and root domain."""
    if sub == "@":
        return domain
    if sub == "*":
        return f"*.{domain}"
    return f"{sub}.{domain}"


def _preview_dns_sync(domain: str, tunnel: str, subs: tuple[str, ...]) -> None:
    """Display dry-run preview of DNS synchronization."""
    print_info(
        f"[yellow][DRY RUN][/yellow] Would synchronize DNS records for {domain} to {tunnel}:"
    )
    for sub in subs:
        rec_name = _format_subdomain_hostname(sub, domain)
        print_info(f"  • {rec_name} -> {tunnel}")


def _render_dns_sync_results(
    domain: str,
    tunnel: str,
    summary: dict[str, str],
    json_output: bool,
) -> None:
    """Render DNS synchronization output in JSON or table format."""
    if json_output:
        write_stdout(format_json(summary) + "\n")
        return

    columns = [("Record Name", "bold cyan"), "Action", "Target Tunnel"]
    rows = [
        [
            name,
            f"[green]{action}[/green]"
            if action in ("created", "updated")
            else f"[dim]{action}[/dim]",
            tunnel,
        ]
        for name, action in summary.items()
    ]
    print_table(f"DNS Synchronization for {domain}", columns=columns, rows=rows)
    print_success(f"Synchronized {len(summary)} DNS records for {domain}.")


@dns_app.command("sync")
@trace_span("cloudflare.dns.sync")
def dns_sync(
    domain: Annotated[
        str | None,
        typer.Option("--domain", "-d", help="Root domain name (e.g. retric.click)"),
    ] = None,
    tunnel_cname: Annotated[
        str | None,
        typer.Option("--tunnel-cname", "-c", help="Target tunnel CNAME or Tunnel UUID"),
    ] = None,
    subdomains: Annotated[
        str | None,
        typer.Option("--subdomains", "-s", help="Comma-separated subdomains to route to tunnel"),
    ] = None,
    zone_id: Annotated[
        str | None,
        typer.Option("--zone-id", "-z", help="Override Cloudflare Zone ID"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Preview DNS record reconciliation without applying changes"
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output reconciliation summary in JSON format"),
    ] = False,
) -> None:
    """Synchronize CNAME records for root and subdomains to the Cloudflare tunnel."""
    settings = load_settings()
    eff_domain = domain or settings.cloudflare.domain
    eff_tunnel = tunnel_cname or settings.cloudflare.tunnel
    if not eff_domain:
        print_error("Domain is required. Set 'cloudflare.domain' or specify --domain.")
        raise typer.Exit(1)
    if not eff_tunnel:
        print_error(
            "Tunnel identifier is required. Set 'cloudflare.tunnel' or specify --tunnel-cname."
        )
        raise typer.Exit(1)

    subs = _parse_subdomains_arg(subdomains)

    if dry_run or is_dry_run():
        _preview_dns_sync(eff_domain, eff_tunnel, subs)
        return

    try:
        client = _resolve_client(settings)
        summary = client.sync_dns_records(
            domain=eff_domain,
            tunnel_id_or_cname=eff_tunnel,
            subdomains=subs,
            zone_id=zone_id,
        )
        _render_dns_sync_results(eff_domain, eff_tunnel, summary, json_output)
    except CloudflareError as exc:
        _print_cloudflare_error("DNS synchronization failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


def _resolve_dns_target_names(target: str, domain: str) -> tuple[str, str]:
    """Resolve target string into lowercase target name and full domain-qualified target."""
    if target == "@":
        full = domain
    elif "." not in target:
        full = f"{target}.{domain}"
    else:
        full = target
    return target.lower(), full.lower()


def _record_matches_filter(
    record: CloudflareDNSRecord,
    target_names: tuple[str, str],
    target: str,
    type_upper: str | None,
    force: bool,
) -> bool:
    """Check whether a single DNS record satisfies target, type, and managed predicates."""
    rec_name = record.name.lower()
    if record.id != target and rec_name not in target_names:
        return False
    if type_upper and record.type.upper() != type_upper:
        return False
    if not force and (record.comment or "").strip() != CONST_CLOUDFLARE_RECORD_COMMENT:
        return False
    return True


def _find_matching_records(
    existing: list[CloudflareDNSRecord],
    target: str,
    domain: str,
    record_type: str | None = None,
    force: bool = False,
) -> list[CloudflareDNSRecord]:
    """Find existing DNS records matching a target name or ID, type, and managed status."""
    target_names = _resolve_dns_target_names(target, domain)
    type_upper = record_type.upper() if record_type else None
    return [
        r for r in existing if _record_matches_filter(r, target_names, target, type_upper, force)
    ]


def _execute_dns_deletions(
    client: CloudflareClient,
    targets: list[str],
    domain: str,
    zone_id: str | None,
    dry_run: bool,
    record_type: str | None = None,
    force: bool = False,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Delete matched DNS records or preview deletion."""
    existing = client.list_dns_records(zone_id=zone_id)
    deleted: list[tuple[str, str]] = []
    not_found: list[str] = []

    for target in targets:
        matched = _find_matching_records(
            existing, target, domain, record_type=record_type, force=force
        )
        if not matched:
            not_found.append(target)
            continue
        for rec in matched:
            if not dry_run:
                client.delete_dns_record(rec.id, zone_id=zone_id)
            deleted.append((rec.name, rec.id))
    return deleted, not_found


def _render_dns_delete_results(
    deleted: list[tuple[str, str]],
    not_found: list[str],
    dry_run: bool,
    json_output: bool,
) -> None:
    """Render deletion output in JSON or table format."""
    if json_output:
        payload = {
            "deleted": [{"name": name, "id": rid} for name, rid in deleted],
            "not_found": not_found,
            "dry_run": dry_run,
        }
        write_stdout(format_json(payload) + "\n")
        return

    prefix = "[yellow][DRY RUN][/yellow] " if dry_run else ""
    if deleted:
        columns = [("Record Name", "bold cyan"), "Record ID", "Status"]
        status_text = "Would Delete" if dry_run else "[green]Deleted[/green]"
        rows = [[name, rid, status_text] for name, rid in deleted]
        print_table(f"{prefix}DNS Deletion Results", columns=columns, rows=rows)
        print_success(f"{prefix}Processed {len(deleted)} DNS record(s).")
    if not_found:
        print_warning(f"Records not found: {', '.join(not_found)}")


@dns_app.command("delete")
@trace_span("cloudflare.dns.delete")
def dns_delete(
    targets: Annotated[
        list[str],
        typer.Argument(
            help="One or more DNS record names (e.g. chat.retric.click) or record IDs to delete"
        ),
    ],
    record_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by DNS record type (e.g. CNAME, A, TXT)"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force deletion of records not marked as 'Managed by devops-cli'",
        ),
    ] = False,
    zone_id: Annotated[
        str | None,
        typer.Option("--zone-id", "-z", help="Override Cloudflare Zone ID"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview DNS record deletions without applying changes"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output deletion results in JSON format"),
    ] = False,
) -> None:
    """Delete one or more DNS records by name or record ID."""
    settings = load_settings()
    eff_domain = settings.cloudflare.domain or ""
    is_dry = dry_run or is_dry_run()

    try:
        client = _resolve_client(settings)
        deleted, not_found = _execute_dns_deletions(
            client=client,
            targets=targets,
            domain=eff_domain,
            zone_id=zone_id,
            dry_run=is_dry,
            record_type=record_type,
            force=force,
        )
        _render_dns_delete_results(deleted, not_found, is_dry, json_output)
    except CloudflareError as exc:
        _print_cloudflare_error("DNS deletion failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@tunnel_app.command("routes")
@trace_span("cloudflare.tunnel.routes")
def tunnel_routes(
    tunnel_id: Annotated[
        str | None,
        typer.Option("--tunnel-id", "-t", help="Cloudflare Tunnel ID or name"),
    ] = None,
    account_id: Annotated[
        str | None,
        typer.Option("--account-id", "-a", help="Override Cloudflare Account ID"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output tunnel ingress routes in JSON format"),
    ] = False,
) -> None:
    """Inspect Cloudflare tunnel ingress routes configuration."""
    settings = load_settings()
    eff_tunnel = tunnel_id or settings.cloudflare.tunnel
    if not eff_tunnel:
        print_error(
            "Tunnel identifier is required. Set 'cloudflare.tunnel' or specify --tunnel-id."
        )
        raise typer.Exit(1)

    try:
        client = _resolve_client(settings)
        cfg = client.get_tunnel_configuration(tunnel_id=eff_tunnel, account_id=account_id)

        if json_output:
            write_stdout(format_json(cfg.model_dump()) + "\n")
            return

        columns = [("#", "dim"), ("Hostname", "bold cyan"), "Path", ("Service", "bold yellow")]
        rows = [
            [
                str(i + 1),
                r.hostname or "[dim](catch-all)[/dim]",
                r.path or "[dim]-[/dim]",
                r.service,
            ]
            for i, r in enumerate(cfg.ingress)
        ]
        print_table(
            f"Tunnel Ingress Configuration (Tunnel: {eff_tunnel})", columns=columns, rows=rows
        )
    except CloudflareError as exc:
        _print_cloudflare_error("Fetching tunnel routes failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


def _preview_tunnel_sync(
    domain: str,
    tunnel: str,
    service: str,
    subs: tuple[str, ...],
    current_ingress: list[CloudflareTunnelIngressRule] | None = None,
) -> None:
    """Display dry-run preview of tunnel ingress route synchronization."""
    print_info(f"[yellow][DRY RUN][/yellow] Would configure tunnel {tunnel} ingress routes:")
    target_hosts = {_format_subdomain_hostname(sub, domain).lower() for sub in subs}
    for sub in subs:
        hostname = _format_subdomain_hostname(sub, domain)
        print_info(f"  • [green]+[/green] {hostname} -> {service}")

    if current_ingress:
        for r in current_ingress:
            if not r.hostname and not r.path:
                continue
            if r.hostname and r.hostname.lower() in target_hosts:
                continue
            r_host = r.hostname or "(any)"
            print_info(f"  • [blue]=[/blue] {r_host} -> {r.service} (preserved)")

    print_info("  • (catch-all) -> http_status:404")


def _render_tunnel_sync_results(tunnel: str, updated_cfg: Any, json_output: bool) -> None:
    """Render tunnel route synchronization output in JSON or table format."""
    if json_output:
        write_stdout(format_json(updated_cfg.model_dump()) + "\n")
        return

    columns = [("#", "dim"), ("Hostname", "bold cyan"), ("Service", "bold yellow")]
    rows = [
        [str(i + 1), r.hostname or "[dim](catch-all)[/dim]", r.service]
        for i, r in enumerate(updated_cfg.ingress)
    ]
    print_table(f"Updated Tunnel Ingress Routes ({tunnel})", columns=columns, rows=rows)
    print_success(f"Configured {len(updated_cfg.ingress)} ingress rules for tunnel {tunnel}.")


@tunnel_app.command("sync")
@trace_span("cloudflare.tunnel.sync")
def tunnel_sync(
    tunnel_id: Annotated[
        str | None,
        typer.Option("--tunnel-id", "-t", help="Cloudflare Tunnel ID"),
    ] = None,
    domain: Annotated[
        str | None,
        typer.Option("--domain", "-d", help="Domain to route through tunnel (e.g. retric.click)"),
    ] = None,
    service: Annotated[
        str,
        typer.Option("--service", help="Cluster ingress destination service URL"),
    ] = CONST_CLOUDFLARE_DEFAULT_SERVICE,
    subdomains: Annotated[
        str | None,
        typer.Option("--subdomains", "-s", help="Comma-separated subdomains to route to service"),
    ] = None,
    account_id: Annotated[
        str | None,
        typer.Option("--account-id", "-a", help="Override Cloudflare Account ID"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview tunnel configuration without updating"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output updated tunnel configuration in JSON format"),
    ] = False,
) -> None:
    """Synchronize tunnel ingress rules to route subdomains to the cluster ingress controller."""
    settings = load_settings()
    eff_tunnel = tunnel_id or settings.cloudflare.tunnel
    eff_domain = domain or settings.cloudflare.domain
    if not eff_tunnel:
        print_error(
            "Tunnel identifier is required. Set 'cloudflare.tunnel' or specify --tunnel-id."
        )
        raise typer.Exit(1)
    if not eff_domain:
        print_error("Domain is required. Set 'cloudflare.domain' or specify --domain.")
        raise typer.Exit(1)

    subs = _parse_subdomains_arg(subdomains)

    if dry_run or is_dry_run():
        current_ingress: list[CloudflareTunnelIngressRule] | None = None
        try:
            client = _resolve_client(settings)
            cfg = client.get_tunnel_configuration(eff_tunnel, account_id=account_id)
            current_ingress = cfg.ingress
        except Exception:
            current_ingress = None
        _preview_tunnel_sync(eff_domain, eff_tunnel, service, subs, current_ingress=current_ingress)
        return

    try:
        client = _resolve_client(settings)
        updated_cfg = client.sync_tunnel_routes(
            tunnel_id=eff_tunnel,
            domain=eff_domain,
            service=service,
            subdomains=subs,
            account_id=account_id,
        )
        _render_tunnel_sync_results(eff_tunnel, updated_cfg, json_output)
    except CloudflareError as exc:
        _print_cloudflare_error("Tunnel route synchronization failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@access_app.command("status")
@trace_span("cloudflare.access.status")
def access_status(
    account_id: Annotated[
        str | None,
        typer.Option("--account-id", "-a", help="Override Cloudflare Account ID"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output access applications in JSON format"),
    ] = False,
) -> None:
    """Inspect Cloudflare Zero Trust Access applications and protected domains."""
    settings = load_settings()
    try:
        client = _resolve_client(settings)
        apps = client.list_access_applications(account_id=account_id)
        if json_output:
            write_stdout(format_json([a.model_dump() for a in apps]) + "\n")
            return
        if not apps:
            print_info("No Cloudflare Zero Trust Access applications configured.")
            return
        columns = [("App Name", "bold cyan"), "Domain", "Type", "Session Duration"]
        rows = [[a.name, a.domain, a.type, a.session_duration] for a in apps]
        print_table("Cloudflare Zero Trust Access Applications", columns=columns, rows=rows)
    except CloudflareError as exc:
        _print_cloudflare_error("Access status check failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


def _resolve_bypass_ips(
    cli_bypass_ips: str | None,
    settings: Settings,
) -> list[str]:
    """Resolve configured or passed public IP bypass addresses."""
    if cli_bypass_ips:
        return [ip.strip() for ip in cli_bypass_ips.split(",") if ip.strip()]
    if settings.cloudflare.access.bypass_ips:
        return list(settings.cloudflare.access.bypass_ips)
    raw = settings.cloudflare.access.public_ip_bypass or settings.cloudflare.public_ip_bypass
    if raw:
        return [ip.strip() for ip in raw.split(",") if ip.strip()]
    return []


def _preview_access_sync(domain: str, emails: list[str], bypass_ips: list[str]) -> None:
    """Preview access synchronization actions in dry-run mode."""
    details: list[str] = []
    if emails:
        details.append(f"emails: {', '.join(emails)}")
    if bypass_ips:
        details.append(f"bypassing IPs: {', '.join(bypass_ips)}")
    summary_str = f" ({'; '.join(details)})" if details else ""
    print_info(
        f"[yellow][DRY RUN][/yellow] Would protect {domain} with Cloudflare Access{summary_str}"
    )


def _render_access_sync_results(summary: dict[str, Any], json_output: bool) -> None:
    """Display Access synchronization summary in table or JSON format."""
    if json_output:
        write_stdout(format_json(summary) + "\n")
        return
    print_success(
        f"Configured Cloudflare Access application '{summary['app_name']}' for {summary['domain']}."
    )
    if summary.get("allowed_emails"):
        print_info(f"Authorized emails: {', '.join(summary['allowed_emails'])}")
    if summary.get("bypass_ips"):
        print_info(
            f"Public IP bypass: {', '.join(summary['bypass_ips'])} (policy '{CONST_CLOUDFLARE_BYPASS_POLICY_NAME}')"
        )


@access_app.command("sync")
@trace_span("cloudflare.access.sync")
def access_sync(
    domain: Annotated[
        str | None,
        typer.Option("--domain", "-d", help="Domain to protect with Cloudflare Access"),
    ] = None,
    allowed_emails: Annotated[
        str | None,
        typer.Option("--allowed-emails", "-e", help="Comma-separated emails permitted to access"),
    ] = None,
    bypass_ips: Annotated[
        str | None,
        typer.Option(
            "--bypass-ips",
            "-b",
            help="Comma-separated public IP addresses or CIDRs to bypass Access authentication (e.g. homelab public IP)",
        ),
    ] = None,
    account_id: Annotated[
        str | None,
        typer.Option("--account-id", "-a", help="Override Cloudflare Account ID"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview Access application changes without applying"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output Access sync summary in JSON format"),
    ] = False,
) -> None:
    """Synchronize Cloudflare Zero Trust Access application and email allow-list policy."""
    settings = load_settings()
    eff_domain = domain or settings.cloudflare.domain
    if not eff_domain:
        print_error("Domain is required. Set 'cloudflare.domain' or specify --domain.")
        raise typer.Exit(1)

    if allowed_emails:
        emails = [e.strip() for e in allowed_emails.split(",") if e.strip()]
    else:
        emails = list(settings.cloudflare.access.allowed_emails or [])

    eff_bypass_ips = _resolve_bypass_ips(bypass_ips, settings)

    if not emails and not eff_bypass_ips:
        print_error(
            "Allowed emails or bypass IPs are required. Set 'cloudflare.access.allowed_emails', "
            "'cloudflare.access.bypass_ips', or specify --allowed-emails / --bypass-ips."
        )
        raise typer.Exit(1)

    is_dry = dry_run or is_dry_run()
    if is_dry:
        _preview_access_sync(eff_domain, emails, eff_bypass_ips)
        return

    try:
        client = _resolve_client(settings)
        summary = client.sync_access_application(
            domain=eff_domain,
            allowed_emails=emails,
            bypass_ips=eff_bypass_ips,
            account_id=account_id,
        )
        _render_access_sync_results(summary, json_output)
    except CloudflareError as exc:
        _print_cloudflare_error("Access synchronization failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@access_app.command("policies")
@trace_span("cloudflare.access.policies")
def access_policies(
    app_id: Annotated[str, typer.Argument(help="Access application ID")],
    account_id: Annotated[
        str | None,
        typer.Option("--account-id", "-a", help="Override Cloudflare Account ID"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output policies in JSON format"),
    ] = False,
) -> None:
    """List Cloudflare Zero Trust Access policies for an application."""
    settings = load_settings()
    try:
        client = _resolve_client(settings)
        policies = client.get_access_policies(app_id, account_id=account_id)
        if json_output:
            write_stdout(format_json([p.model_dump() for p in policies]) + "\n")
            return
        if not policies:
            print_info(f"No Access policies configured for application {app_id}.")
            return
        columns = [("Policy ID", "dim"), ("Name", "bold cyan"), "Decision", "Rules"]
        rows = [
            [
                p.id or "-",
                p.name,
                p.decision,
                str(len(p.include)),
            ]
            for p in policies
        ]
        print_table(f"Access Policies for App {app_id}", columns=columns, rows=rows)
    except CloudflareError as exc:
        _print_cloudflare_error("Failed listing Access policies", exc)
        raise typer.Exit(code=exc.exit_code) from exc
