"""Cloudflare REST API client for Zero Trust and DNS configuration."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

import httpx2

from devops_cli.config.constants import (
    CONST_CLOUDFLARE_CATCHALL_SERVICE,
    CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX,
    CONST_CLOUDFLARE_DEFAULT_SERVICE,
    CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS,
    CONST_URL_CLOUDFLARE_API_BASE,
)
from devops_cli.exceptions.cloudflare import CloudflareAPIError, CloudflareAuthError
from devops_cli.http.client import request_timeout
from devops_cli.models.cloudflare import (
    CloudflareAccessApplication,
    CloudflareAccessPolicy,
    CloudflareDNSRecord,
    CloudflareTokenStatus,
    CloudflareTunnelConfig,
    CloudflareTunnelIngressRule,
    CloudflareZone,
)

logger = logging.getLogger(__name__)


def _build_auth_headers(token: str) -> dict[str, str]:
    """Construct authentication and content headers for Cloudflare API."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _extract_error_message(data: dict[str, Any], default: str) -> str:
    """Extract first descriptive error message from Cloudflare response payload."""
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict) and "message" in first:
            return str(first["message"])
        return str(first)
    return default


def _is_uuid(val: str) -> bool:
    """Check if a string matches UUID format."""
    import uuid

    try:
        uuid.UUID(val)
        return True
    except ValueError, AttributeError:
        return False


def _parse_dns_record(item: dict[str, Any]) -> CloudflareDNSRecord:
    """Parse raw JSON DNS record into CloudflareDNSRecord model."""
    return CloudflareDNSRecord(
        id=str(item.get("id", "")),
        type=str(item.get("type", "CNAME")),
        name=str(item.get("name", "")),
        content=str(item.get("content", "")),
        proxiable=bool(item.get("proxiable", False)),
        proxied=bool(item.get("proxied", False)),
        ttl=int(item.get("ttl", 1)),
        comment=item.get("comment"),
    )


def _parse_tunnel_config(tunnel_id: str, data: dict[str, Any]) -> CloudflareTunnelConfig:
    """Parse raw JSON tunnel configuration into CloudflareTunnelConfig model."""
    cfg = data.get("config", {}) if isinstance(data, dict) else {}
    version = int(data.get("version", 1)) if isinstance(data, dict) else 1
    raw_ingress = cfg.get("ingress", []) if isinstance(cfg, dict) else []
    rules: list[CloudflareTunnelIngressRule] = [
        CloudflareTunnelIngressRule(
            service=str(r.get("service", "")),
            hostname=r.get("hostname"),
            path=r.get("path"),
        )
        for r in raw_ingress
        if isinstance(r, dict) and "service" in r
    ]
    return CloudflareTunnelConfig(
        tunnel_id=tunnel_id,
        version=version,
        ingress=rules,
    )


def _parse_access_application(data: dict[str, Any]) -> CloudflareAccessApplication:
    """Parse Access application dictionary payload into model."""
    return CloudflareAccessApplication(
        id=str(data.get("id", "")),
        name=str(data.get("name", "")),
        domain=str(data.get("domain", "")),
        type=str(data.get("type", "self_hosted")),
        session_duration=str(data.get("session_duration", "24h")),
        allowed_idps=list(data.get("allowed_idps") or []),
    )


def _extract_policy_include_email(item: Any) -> dict[str, str] | None:
    """Extract email dictionary from raw include item."""
    if not isinstance(item, dict):
        return None
    email_obj = item.get("email")
    if isinstance(email_obj, dict) and "email" in email_obj:
        return {"email": str(email_obj["email"])}
    if "email" in item:
        return {"email": str(item["email"])}
    return None


def _parse_access_policy(data: dict[str, Any]) -> CloudflareAccessPolicy:
    """Parse Access policy dictionary payload into model."""
    raw_include = data.get("include")
    items = raw_include if isinstance(raw_include, list) else []
    extracted = [_extract_policy_include_email(i) for i in items]
    include_list = [e for e in extracted if e is not None]
    return CloudflareAccessPolicy(
        id=str(data["id"]) if data.get("id") else None,
        name=str(data.get("name", "")),
        decision=str(data.get("decision", "allow")),
        include=include_list,
    )


class CloudflareClient:
    """Synchronous REST client for Cloudflare API v4."""

    def __init__(
        self,
        token: str,
        account_id: str | None = None,
        zone_id: str | None = None,
        base_url: str = CONST_URL_CLOUDFLARE_API_BASE,
    ) -> None:
        self._token = token
        self._account_id = account_id
        self._zone_id = zone_id
        self._base_url = base_url.rstrip("/")

    @property
    def account_id(self) -> str | None:
        return self._account_id

    @property
    def zone_id(self) -> str | None:
        return self._zone_id

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute HTTP request against Cloudflare API with error handling."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = _build_auth_headers(self._token)
        timeout = request_timeout(read=30.0)

        with httpx2.Client(timeout=timeout) as client:
            try:
                resp = client.request(method, url, headers=headers, json=json_data, params=params)
            except httpx2.HTTPError as exc:
                raise CloudflareAPIError(
                    f"Cloudflare HTTP request to {path} failed: {exc}",
                    details={"path": path, "method": method},
                ) from exc

        return self._handle_response(resp, path, method)

    def _handle_response(self, resp: httpx2.Response, path: str, method: str) -> Any:
        """Parse response status and JSON payload."""
        if resp.status_code in (401, 403):
            raise CloudflareAuthError(
                "Cloudflare API authentication failed. Verify your API token.",
                details={"status_code": resp.status_code, "path": path},
            )

        try:
            body = resp.json()
        except ValueError, json.JSONDecodeError:
            body = {}

        if not resp.is_success:
            msg = _extract_error_message(body, f"Cloudflare API returned HTTP {resp.status_code}")
            raise CloudflareAPIError(
                msg,
                status_code=resp.status_code,
                details={"path": path, "method": method, "errors": body.get("errors")},
            )

        if isinstance(body, dict) and not body.get("success", True):
            msg = _extract_error_message(body, "Cloudflare API request was not successful")
            raise CloudflareAPIError(msg, details={"path": path, "method": method})

        return body.get("result") if isinstance(body, dict) else body

    def verify_token(self) -> CloudflareTokenStatus:
        """Verify API token validity and status."""
        result = self._request("GET", "user/tokens/verify")
        if not isinstance(result, dict):
            raise CloudflareAPIError("Invalid response from token verification.")
        return CloudflareTokenStatus(
            id=str(result.get("id", "")),
            status=str(result.get("status", "unknown")),
        )

    def get_zone(self, zone_id: str | None = None) -> CloudflareZone:
        """Fetch details for a managed DNS zone."""
        zid = zone_id or self._zone_id
        if not zid:
            raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
        result = self._request("GET", f"zones/{zid}")
        if not isinstance(result, dict):
            raise CloudflareAPIError(f"Zone {zid} returned invalid details.")
        return CloudflareZone(
            id=str(result.get("id", zid)),
            name=str(result.get("name", "")),
            status=str(result.get("status", "unknown")),
            paused=bool(result.get("paused", False)),
            name_servers=list(result.get("name_servers") or []),
        )

    def list_dns_records(
        self,
        zone_id: str | None = None,
        record_type: str | None = None,
        name: str | None = None,
    ) -> list[CloudflareDNSRecord]:
        """List DNS records in the designated zone."""
        zid = zone_id or self._zone_id
        if not zid:
            raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
        params: dict[str, Any] = {"per_page": 100}
        if record_type:
            params["type"] = record_type
        if name:
            params["name"] = name
        result = self._request("GET", f"zones/{zid}/dns_records", params=params)
        if not isinstance(result, list):
            return []
        return [_parse_dns_record(item) for item in result if isinstance(item, dict)]

    def create_dns_record(
        self,
        *,
        name: str,
        content: str,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
        comment: str | None = None,
        zone_id: str | None = None,
    ) -> CloudflareDNSRecord:
        """Create a new DNS record."""
        zid = zone_id or self._zone_id
        if not zid:
            raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
        payload: dict[str, Any] = {
            "type": record_type,
            "name": name,
            "content": content,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            payload["comment"] = comment
        result = self._request("POST", f"zones/{zid}/dns_records", json_data=payload)
        return _parse_dns_record(result)

    def update_dns_record(
        self,
        record_id: str,
        *,
        name: str,
        content: str,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
        comment: str | None = None,
        zone_id: str | None = None,
    ) -> CloudflareDNSRecord:
        """Update an existing DNS record."""
        zid = zone_id or self._zone_id
        if not zid:
            raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
        payload: dict[str, Any] = {
            "type": record_type,
            "name": name,
            "content": content,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            payload["comment"] = comment
        result = self._request("PUT", f"zones/{zid}/dns_records/{record_id}", json_data=payload)
        return _parse_dns_record(result)

    def delete_dns_record(self, record_id: str, zone_id: str | None = None) -> bool:
        """Delete a DNS record by ID."""
        zid = zone_id or self._zone_id
        if not zid:
            raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
        self._request("DELETE", f"zones/{zid}/dns_records/{record_id}")
        return True

    def resolve_tunnel_id(
        self,
        tunnel_name_or_id: str,
        account_id: str | None = None,
    ) -> str:
        """Resolve a tunnel name or ID to its canonical UUID."""
        if _is_uuid(tunnel_name_or_id):
            return tunnel_name_or_id
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        result = self._request(
            "GET", f"accounts/{aid}/cfd_tunnel", params={"name": tunnel_name_or_id}
        )
        if isinstance(result, list) and result:
            first_id = result[0].get("id")
            if first_id:
                return str(first_id)
        raise CloudflareAPIError(f"No Cloudflare tunnel found matching name '{tunnel_name_or_id}'.")

    def get_tunnel_configuration(
        self,
        tunnel_id: str,
        account_id: str | None = None,
    ) -> CloudflareTunnelConfig:
        """Fetch tunnel ingress configuration rules."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        resolved_id = self.resolve_tunnel_id(tunnel_id, account_id=aid)
        result = self._request("GET", f"accounts/{aid}/cfd_tunnel/{resolved_id}/configurations")
        return _parse_tunnel_config(resolved_id, result if isinstance(result, dict) else {})

    def update_tunnel_configuration(
        self,
        tunnel_id: str,
        ingress_rules: list[CloudflareTunnelIngressRule],
        account_id: str | None = None,
    ) -> CloudflareTunnelConfig:
        """Update tunnel ingress configuration rules."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        resolved_id = self.resolve_tunnel_id(tunnel_id, account_id=aid)
        payload = {
            "config": {
                "ingress": [
                    {
                        "service": r.service,
                        **({"hostname": r.hostname} if r.hostname else {}),
                        **({"path": r.path} if r.path else {}),
                    }
                    for r in ingress_rules
                ]
            }
        }
        result = self._request(
            "PUT",
            f"accounts/{aid}/cfd_tunnel/{resolved_id}/configurations",
            json_data=payload,
        )
        return _parse_tunnel_config(resolved_id, result if isinstance(result, dict) else {})

    def sync_dns_records(
        self,
        domain: str,
        tunnel_id_or_cname: str,
        subdomains: Sequence[str] | None = None,
        zone_id: str | None = None,
    ) -> dict[str, str]:
        """Ensure designated subdomains point to the tunnel CNAME target."""
        if CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX in tunnel_id_or_cname:
            target_cname = tunnel_id_or_cname
        else:
            resolved_id = self.resolve_tunnel_id(tunnel_id_or_cname)
            target_cname = f"{resolved_id}{CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX}"
        subs = subdomains if subdomains is not None else CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS

        existing_records = {
            r.name: r for r in self.list_dns_records(zone_id=zone_id, record_type="CNAME")
        }

        summary: dict[str, str] = {}
        for sub in subs:
            rec_name = (
                domain if sub == "@" else (f"*.{domain}" if sub == "*" else f"{sub}.{domain}")
            )
            existing = existing_records.get(rec_name)
            summary[rec_name] = self._reconcile_dns_record(
                existing=existing,
                name=rec_name,
                content=target_cname,
                zone_id=zone_id,
            )
        return summary

    def _reconcile_dns_record(
        self,
        existing: CloudflareDNSRecord | None,
        name: str,
        content: str,
        zone_id: str | None,
    ) -> str:
        """Create or update DNS record if drift is detected."""
        if existing is None:
            self.create_dns_record(
                name=name,
                content=content,
                proxied=True,
                zone_id=zone_id,
                comment="Managed by devops-cli",
            )
            return "created"
        if existing.content == content and existing.proxied is True:
            return "unchanged"
        self.update_dns_record(
            record_id=existing.id,
            name=name,
            content=content,
            proxied=True,
            zone_id=zone_id,
            comment="Managed by devops-cli",
        )
        return "updated"

    def sync_tunnel_routes(
        self,
        tunnel_id: str,
        domain: str,
        service: str = CONST_CLOUDFLARE_DEFAULT_SERVICE,
        subdomains: Sequence[str] | None = None,
        account_id: str | None = None,
    ) -> CloudflareTunnelConfig:
        """Ensure tunnel ingress rules route domain traffic to cluster ingress controller."""
        subs = subdomains if subdomains is not None else CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS
        rules: list[CloudflareTunnelIngressRule] = []

        for sub in subs:
            hostname = (
                domain if sub == "@" else (f"*.{domain}" if sub == "*" else f"{sub}.{domain}")
            )
            rules.append(CloudflareTunnelIngressRule(hostname=hostname, service=service))

        # Always terminate with catch-all 404
        rules.append(CloudflareTunnelIngressRule(service=CONST_CLOUDFLARE_CATCHALL_SERVICE))
        return self.update_tunnel_configuration(tunnel_id, rules, account_id=account_id)

    def list_access_applications(
        self, account_id: str | None = None
    ) -> list[CloudflareAccessApplication]:
        """List Cloudflare Zero Trust Access applications for the account."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        result = self._request("GET", f"accounts/{aid}/access/apps")
        if not isinstance(result, list):
            return []
        return [_parse_access_application(item) for item in result if isinstance(item, dict)]

    def create_access_application(
        self,
        *,
        name: str,
        domain: str,
        session_duration: str = "24h",
        account_id: str | None = None,
    ) -> CloudflareAccessApplication:
        """Create a self-hosted Cloudflare Zero Trust Access application."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        payload = {
            "name": name,
            "domain": domain,
            "type": "self_hosted",
            "session_duration": session_duration,
        }
        result = self._request("POST", f"accounts/{aid}/access/apps", json_data=payload)
        return _parse_access_application(result if isinstance(result, dict) else {})

    def get_access_policies(
        self, app_id: str, account_id: str | None = None
    ) -> list[CloudflareAccessPolicy]:
        """List policies for a designated Access application."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        result = self._request("GET", f"accounts/{aid}/access/apps/{app_id}/policies")
        if not isinstance(result, list):
            return []
        return [_parse_access_policy(item) for item in result if isinstance(item, dict)]

    def create_or_update_access_policy(
        self,
        *,
        app_id: str,
        name: str,
        allowed_emails: Sequence[str],
        decision: str = "allow",
        account_id: str | None = None,
    ) -> CloudflareAccessPolicy:
        """Create or update an Access policy restricting access to specific email addresses."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        include_rules = [{"email": {"email": email}} for email in allowed_emails]
        payload = {
            "name": name,
            "decision": decision,
            "include": include_rules,
        }
        existing_policies = self.get_access_policies(app_id, account_id=aid)
        existing = next((p for p in existing_policies if p.name == name), None)
        if existing and existing.id:
            result = self._request(
                "PUT",
                f"accounts/{aid}/access/apps/{app_id}/policies/{existing.id}",
                json_data=payload,
            )
        else:
            result = self._request(
                "POST",
                f"accounts/{aid}/access/apps/{app_id}/policies",
                json_data=payload,
            )
        return _parse_access_policy(result if isinstance(result, dict) else {})

    def sync_access_application(
        self,
        *,
        domain: str,
        allowed_emails: Sequence[str],
        name: str = "Homelab Ingress",
        session_duration: str = "24h",
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Ensure an Access application and email allow-list policy protect the domain."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        apps = self.list_access_applications(account_id=aid)
        app = next((a for a in apps if a.domain == domain), None)
        if app is None:
            app = self.create_access_application(
                name=name,
                domain=domain,
                session_duration=session_duration,
                account_id=aid,
            )
            app_action = "created"
        else:
            app_action = "existing"

        policy = self.create_or_update_access_policy(
            app_id=app.id,
            name="Allow homelab authorized emails",
            allowed_emails=allowed_emails,
            decision="allow",
            account_id=aid,
        )
        return {
            "app_id": app.id,
            "app_name": app.name,
            "domain": app.domain,
            "app_action": app_action,
            "policy_id": policy.id,
            "allowed_emails": list(allowed_emails),
        }


__all__ = ["CloudflareClient"]
