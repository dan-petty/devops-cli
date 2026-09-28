"""CLI command group for Cloudflare Zero Trust tunnels and DNS management."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.config.constants import (
    CONST_CLOUDFLARE_DEFAULT_SERVICE,
    CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS,
)
from devops_cli.config.settings import Settings, get_cloudflare_api_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.cloudflare import CloudflareAuthError, CloudflareError
from devops_cli.lang import HELP
from devops_cli.models.cloudflare import CloudflareDNSRecord
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


def _find_matching_records(
    existing: list[CloudflareDNSRecord],
    target: str,
    domain: str,
) -> list[CloudflareDNSRecord]:
    """Find existing DNS records matching a target name or ID."""
    full_target = f"{target}.{domain}" if "." not in target and target != "@" else target
    if target == "@":
        full_target = domain
    target_lower = target.lower()
    full_target_lower = full_target.lower()
    return [
        r
        for r in existing
        if r.id == target or r.name.lower() == target_lower or r.name.lower() == full_target_lower
    ]


def _execute_dns_deletions(
    client: CloudflareClient,
    targets: list[str],
    domain: str,
    zone_id: str | None,
    dry_run: bool,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Delete matched DNS records or preview deletion."""
    existing = client.list_dns_records(zone_id=zone_id)
    deleted: list[tuple[str, str]] = []
    not_found: list[str] = []

    for target in targets:
        matched = _find_matching_records(existing, target, domain)
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
) -> None:
    """Display dry-run preview of tunnel ingress route synchronization."""
    print_info(f"[yellow][DRY RUN][/yellow] Would configure tunnel {tunnel} ingress routes:")
    for sub in subs:
        hostname = _format_subdomain_hostname(sub, domain)
        print_info(f"  • {hostname} -> {service}")
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
        _preview_tunnel_sync(eff_domain, eff_tunnel, service, subs)
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

    if not emails:
        print_error(
            "Allowed emails are required. Set 'cloudflare.access.allowed_emails' or specify --allowed-emails."
        )
        raise typer.Exit(1)

    is_dry = dry_run or is_dry_run()
    if is_dry:
        print_info(
            f"[yellow][DRY RUN][/yellow] Would protect {eff_domain} with Cloudflare Access for: {', '.join(emails)}"
        )
        return

    try:
        client = _resolve_client(settings)
        summary = client.sync_access_application(
            domain=eff_domain,
            allowed_emails=emails,
            account_id=account_id,
        )
        if json_output:
            write_stdout(format_json(summary) + "\n")
            return
        print_success(
            f"Configured Cloudflare Access application '{summary['app_name']}' for {eff_domain}."
        )
        print_info(f"Authorized emails: {', '.join(summary['allowed_emails'])}")
    except CloudflareError as exc:
        _print_cloudflare_error("Access synchronization failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc
