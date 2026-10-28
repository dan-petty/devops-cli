"""Cloudflare REST API client for Zero Trust and DNS configuration."""

from __future__ import annotations

import datetime
import ipaddress
import json
import logging
from collections.abc import Callable, Sequence
from email.utils import parsedate_to_datetime
from typing import Any

import httpx2
import tenacity

from devops_cli.config.constants import (
    CONST_CLOUDFLARE_ALLOW_POLICY_NAME,
    CONST_CLOUDFLARE_BYPASS_POLICY_NAME,
    CONST_CLOUDFLARE_CATCHALL_SERVICE,
    CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX,
    CONST_CLOUDFLARE_DEFAULT_SERVICE,
    CONST_CLOUDFLARE_DEFAULT_SESSION_DURATION,
    CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS,
    CONST_CLOUDFLARE_RECORD_COMMENT,
    CONST_CLOUDFLARE_WILDCARD_PREFIX,
    CONST_URL_CLOUDFLARE_API_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_CLOUDFLARE_MAX_RETRIES,
    DEFAULT_CLOUDFLARE_RETRY_MAX_WAIT,
    DEFAULT_CLOUDFLARE_RETRY_MIN_WAIT,
)
from devops_cli.core import clock
from devops_cli.exceptions.cloudflare import CloudflareAPIError, CloudflareAuthError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
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
            origin_request=r.get("originRequest") or r.get("origin_request"),
        )
        for r in raw_ingress
        if isinstance(r, dict) and "service" in r
    ]
    warp_routing = cfg.get("warp-routing") if isinstance(cfg, dict) else None
    return CloudflareTunnelConfig(
        tunnel_id=tunnel_id,
        version=version,
        ingress=rules,
        warp_routing=warp_routing if isinstance(warp_routing, dict) else None,
    )


def _rule_routing_key(
    r: CloudflareTunnelIngressRule,
) -> tuple[str | None, str | None] | None:
    """Return routing key for rule, or None if rule is a catch-all."""
    if not r.hostname and not r.path:
        return None
    return (r.hostname.lower() if r.hostname else None, r.path)


def _merge_existing_and_target_rules(
    current_rules: list[CloudflareTunnelIngressRule],
    target_by_key: dict[tuple[str | None, str | None], CloudflareTunnelIngressRule],
    seen_keys: set[tuple[str | None, str | None]],
) -> list[CloudflareTunnelIngressRule]:
    """Preserve current rules or override with target rules when keys match."""
    merged: list[CloudflareTunnelIngressRule] = []
    for r in current_rules:
        key = _rule_routing_key(r)
        if key is None:
            continue
        if key in target_by_key:
            merged.append(target_by_key[key])
            seen_keys.add(key)
        else:
            merged.append(r)
    return merged


def _wildcard_matches(pattern: str | None, hostname: str | None) -> bool:
    """Whether cloudflared matches `hostname` to the rule hostname `pattern`: a leading `*.`
    matches any name ending in the rest (`matchHost` in cloudflared's ingress/rule.go)."""
    if not pattern or not hostname or not pattern.startswith(CONST_CLOUDFLARE_WILDCARD_PREFIX):
        return False
    return hostname.lower().endswith(pattern[1:].lower())


def _insertion_index(rules: list[CloudflareTunnelIngressRule], hostname: str | None) -> int:
    """Where a new rule for `hostname` goes: before the first rule whose wildcard would match it,
    since cloudflared takes the first match, else after every rule (#1595)."""
    return next(
        (i for i, rule in enumerate(rules) if _wildcard_matches(rule.hostname, hostname)),
        len(rules),
    )


def _merge_tunnel_ingress_rules(
    current_rules: list[CloudflareTunnelIngressRule],
    target_rules: list[CloudflareTunnelIngressRule],
) -> list[CloudflareTunnelIngressRule]:
    """Merge target ingress rules into current rules, preserving other routes and catch-all. A
    new hostname goes before any wildcard rule that would otherwise take its traffic."""
    target_by_key = {key: r for r in target_rules if (key := _rule_routing_key(r)) is not None}
    seen_keys: set[tuple[str | None, str | None]] = set()
    merged = _merge_existing_and_target_rules(current_rules, target_by_key, seen_keys)

    for r in target_rules:
        key = _rule_routing_key(r)
        if key is not None and key not in seen_keys:
            merged.insert(_insertion_index(merged, r.hostname), r)
            seen_keys.add(key)

    existing_catchall = next((r for r in current_rules if not r.hostname and not r.path), None)
    if existing_catchall is not None:
        merged.append(existing_catchall)
    else:
        merged.append(CloudflareTunnelIngressRule(service=CONST_CLOUDFLARE_CATCHALL_SERVICE))
    return merged


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


def _normalize_ip_cidr(raw_ip: str) -> str:
    """Normalize an IP address or CIDR string into canonical CIDR notation."""
    clean = raw_ip.strip()
    try:
        net = ipaddress.ip_network(clean, strict=False)
        if getattr(net.network_address, "scope_id", None) is not None or "%" in clean:
            raise ValueError("IPv6 zone index is not permitted")
        return net.with_prefixlen
    except ValueError as exc:
        raise CloudflareAPIError(f"Invalid IP address or CIDR block '{clean}': {exc}") from exc


def _extract_policy_include_rule(item: Any) -> dict[str, Any] | None:
    """Extract email or IP dictionary from raw include item."""
    if not isinstance(item, dict):
        return None
    if "email" in item:
        email_obj = item["email"]
        if isinstance(email_obj, dict) and "email" in email_obj:
            return {"email": {"email": str(email_obj["email"])}}
        return {"email": {"email": str(email_obj)}}
    if "ip" in item:
        ip_obj = item["ip"]
        if isinstance(ip_obj, dict) and "ip" in ip_obj:
            return {"ip": {"ip": str(ip_obj["ip"])}}
        return {"ip": {"ip": str(ip_obj)}}
    return item


def _extract_policy_include_email(item: Any) -> dict[str, str] | None:
    """Extract email dictionary from raw include item."""
    rule = _extract_policy_include_rule(item)
    if rule and "email" in rule:
        inner = rule["email"]
        return {"email": str(inner["email"] if isinstance(inner, dict) else inner)}
    return None


def _parse_access_policy(data: dict[str, Any]) -> CloudflareAccessPolicy:
    """Parse Access policy dictionary payload into model."""
    raw_include = data.get("include")
    items = raw_include if isinstance(raw_include, list) else []
    extracted = [_extract_policy_include_rule(i) for i in items]
    include_list = [e for e in extracted if e is not None]
    return CloudflareAccessPolicy(
        id=str(data["id"]) if data.get("id") else None,
        name=str(data.get("name", "")),
        decision=str(data.get("decision", "allow")),
        include=include_list,
    )


def _build_policy_include_rules(
    allowed_emails: Sequence[str] | None,
    bypass_ips: Sequence[str] | None,
) -> list[dict[str, Any]]:
    """Construct include rules for Access policy from emails and/or bypass IPs."""
    rules: list[dict[str, Any]] = []
    if allowed_emails:
        rules.extend({"email": {"email": email}} for email in allowed_emails)
    if bypass_ips:
        for ip_val in bypass_ips:
            normalized = _normalize_ip_cidr(ip_val)
            rules.append({"ip": {"ip": normalized}})
    return rules


def _build_dns_records_params(record_type: str | None, name: str | None) -> dict[str, Any]:
    """Build query parameters dictionary for listing DNS records."""
    params: dict[str, Any] = {"per_page": 100, "page": 1}
    if record_type:
        params["type"] = record_type
    if name:
        params["name"] = name
    return params


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header as seconds or an HTTP date string."""
    if not value:
        return None
    try:
        seconds = float(value)
        if seconds >= 0:
            return seconds
    except ValueError:
        pass
    try:
        retry_time = parsedate_to_datetime(value)
        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(tzinfo=datetime.UTC)
        now = datetime.datetime.now(datetime.UTC)
        seconds = (retry_time - now).total_seconds()
        if seconds > 0:
            return seconds
    except ValueError, TypeError, AssertionError:
        pass
    return None


def _wait_cloudflare_retry_after(
    state: tenacity.RetryCallState,
    fallback_strategy: Callable[[tenacity.RetryCallState], float] | None = None,
) -> float:
    """Determine wait duration from the Retry-After header or exponential backoff."""
    outcome = state.outcome
    if outcome is not None and not outcome.failed:
        resp = outcome.result()
        if hasattr(resp, "headers") and resp.headers:
            retry_after_str = resp.headers.get("retry-after")
            delay = _parse_retry_after(retry_after_str)
            if delay is not None:
                return float(min(delay, DEFAULT_CLOUDFLARE_RETRY_MAX_WAIT))
    fallback = fallback_strategy or tenacity.wait_exponential(
        multiplier=DEFAULT_CLOUDFLARE_RETRY_MIN_WAIT, max=DEFAULT_CLOUDFLARE_RETRY_MAX_WAIT
    )
    return float(fallback(state))


def _should_retry_response(resp: Any) -> bool:
    """Check whether a response status code indicates a retryable rate limit or server error."""
    if not hasattr(resp, "status_code"):
        return False
    status = int(resp.status_code)
    return status == 429 or (500 <= status < 600)


class CloudflareClient:
    """Synchronous REST client for Cloudflare API v4."""

    def __init__(
        self,
        token: str,
        account_id: str | None = None,
        zone_id: str | None = None,
        base_url: str = CONST_URL_CLOUDFLARE_API_BASE,
        sleep: Callable[[float], None] = clock.sleep,
    ) -> None:
        self._token = token
        self._account_id = account_id
        self._zone_id = zone_id
        self._base_url = base_url.rstrip("/")
        self._sleep = sleep

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
        include_info: bool = False,
    ) -> Any:
        """Execute HTTP request against Cloudflare API with error handling and retries.

        The client dials only public addresses, whatever `ai.allow_private_network` says. A
        refused address raises SSRFBlockedError at the connect, and the request is not retried.
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = _build_auth_headers(self._token)

        def make_request() -> httpx2.Response:
            with new_http_client(level=EgressLevel.PUBLIC, read_timeout=30.0) as client:
                try:
                    return client.request(
                        method, url, headers=headers, json=json_data, params=params
                    )
                except httpx2.HTTPError as exc:
                    raise CloudflareAPIError(
                        f"Cloudflare HTTP request to {path} failed: {exc}",
                        details={"path": path, "method": method},
                    ) from exc

        retrying = tenacity.Retrying(
            stop=tenacity.stop_after_attempt(DEFAULT_CLOUDFLARE_MAX_RETRIES),
            retry=tenacity.retry_if_result(_should_retry_response),
            wait=_wait_cloudflare_retry_after,
            sleep=self._sleep,
            retry_error_callback=lambda state: (
                state.outcome.result() if state.outcome and not state.outcome.failed else None
            ),
        )
        resp = retrying(make_request)
        return self._handle_response(resp, path, method, include_info=include_info)

    def _handle_response(
        self,
        resp: httpx2.Response,
        path: str,
        method: str,
        include_info: bool = False,
    ) -> Any:
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

        if include_info:
            return (
                body.get("result") if isinstance(body, dict) else body,
                body.get("result_info") if isinstance(body, dict) else {},
            )
        return body.get("result") if isinstance(body, dict) else body

    def _get_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a collection endpoint with result_info pagination."""
        query_params = dict(params) if params else {}
        page = int(query_params.get("page", 1))
        all_items: list[dict[str, Any]] = []

        while True:
            query_params["page"] = page
            raw_res = self._request("GET", path, params=query_params, include_info=True)
            result = raw_res[0] if isinstance(raw_res, tuple) else raw_res
            info = raw_res[1] if isinstance(raw_res, tuple) and isinstance(raw_res[1], dict) else {}

            if not isinstance(result, list) or not result:
                break

            all_items.extend(item for item in result if isinstance(item, dict))

            curr_page = int(info.get("page", page)) if isinstance(info, dict) else page
            total_pages = info.get("total_pages") if isinstance(info, dict) else None

            if total_pages is not None:
                if curr_page >= int(total_pages):
                    break
            else:
                per_page = int(info.get("per_page", query_params.get("per_page", 20)))
                if len(result) < per_page:
                    break

            page = curr_page + 1

        return all_items

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
        """List DNS records in the designated zone with full pagination."""
        zid = zone_id or self._zone_id
        if not zid:
            raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
        params = _build_dns_records_params(record_type, name)
        raw_records = self._get_paginated(f"zones/{zid}/dns_records", params=params)
        return [_parse_dns_record(item) for item in raw_records]

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
            "GET",
            f"accounts/{aid}/cfd_tunnel",
            params={"name": tunnel_name_or_id, "is_deleted": "false"},
        )
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, dict):
                    continue
                if item.get("deleted_at") is not None or item.get("is_deleted") is True:
                    continue
                first_id = item.get("id")
                if first_id:
                    return str(first_id)
        raise CloudflareAPIError(
            f"No active Cloudflare tunnel found matching name '{tunnel_name_or_id}'."
        )

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
        base_config: dict[str, Any] | None = None,
    ) -> CloudflareTunnelConfig:
        """Update tunnel ingress configuration rules while preserving existing options."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        resolved_id = self.resolve_tunnel_id(tunnel_id, account_id=aid)
        cfg_payload = dict(base_config) if base_config else {}
        cfg_payload["ingress"] = [
            {
                "service": r.service,
                **({"hostname": r.hostname} if r.hostname else {}),
                **({"path": r.path} if r.path else {}),
                **({"originRequest": r.origin_request} if r.origin_request else {}),
            }
            for r in ingress_rules
        ]
        payload = {"config": cfg_payload}
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
                comment=CONST_CLOUDFLARE_RECORD_COMMENT,
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
            comment=CONST_CLOUDFLARE_RECORD_COMMENT,
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
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        resolved_id = self.resolve_tunnel_id(tunnel_id, account_id=aid)

        raw_cfg = self._request("GET", f"accounts/{aid}/cfd_tunnel/{resolved_id}/configurations")
        base_config: dict[str, Any] = (
            dict(raw_cfg.get("config", {}) or {}) if isinstance(raw_cfg, dict) else {}
        )
        current_parsed = _parse_tunnel_config(
            resolved_id, raw_cfg if isinstance(raw_cfg, dict) else {}
        )
        current_rules = current_parsed.ingress

        subs = subdomains if subdomains is not None else CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS
        target_rules: list[CloudflareTunnelIngressRule] = []
        for sub in subs:
            hostname = (
                domain if sub == "@" else (f"*.{domain}" if sub == "*" else f"{sub}.{domain}")
            )
            target_rules.append(CloudflareTunnelIngressRule(hostname=hostname, service=service))

        merged_rules = _merge_tunnel_ingress_rules(current_rules, target_rules)
        return self.update_tunnel_configuration(
            resolved_id,
            merged_rules,
            account_id=aid,
            base_config=base_config,
        )

    def list_access_applications(
        self, account_id: str | None = None
    ) -> list[CloudflareAccessApplication]:
        """List Cloudflare Zero Trust Access applications for the account."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        raw_apps = self._get_paginated(f"accounts/{aid}/access/apps")
        return [_parse_access_application(item) for item in raw_apps]

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
        raw_policies = self._get_paginated(f"accounts/{aid}/access/apps/{app_id}/policies")
        return [_parse_access_policy(item) for item in raw_policies]

    def _ensure_access_application(
        self,
        domain: str,
        name: str,
        session_duration: str,
        account_id: str,
    ) -> tuple[CloudflareAccessApplication, str]:
        """Find existing application by domain or create a new one."""
        apps = self.list_access_applications(account_id=account_id)
        app = next((a for a in apps if a.domain == domain), None)
        if app is None:
            created = self.create_access_application(
                name=name,
                domain=domain,
                session_duration=session_duration,
                account_id=account_id,
            )
            return created, "created"
        return app, "existing"

    def _sync_bypass_policy_if_configured(
        self,
        app_id: str,
        bypass_ips: Sequence[str] | None,
        account_id: str,
    ) -> str | None:
        """Create or update bypass policy when bypass IPs are provided."""
        if not bypass_ips:
            return None
        policy = self.create_or_update_access_policy(
            app_id=app_id,
            name=CONST_CLOUDFLARE_BYPASS_POLICY_NAME,
            bypass_ips=bypass_ips,
            decision="bypass",
            account_id=account_id,
        )
        return policy.id

    def create_or_update_access_policy(
        self,
        *,
        app_id: str,
        name: str,
        allowed_emails: Sequence[str] | None = None,
        bypass_ips: Sequence[str] | None = None,
        decision: str = "allow",
        account_id: str | None = None,
    ) -> CloudflareAccessPolicy:
        """Create or update an Access policy restricting or bypassing access."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        include_rules = _build_policy_include_rules(allowed_emails, bypass_ips)
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
        bypass_ips: Sequence[str] | None = None,
        name: str = "Homelab Ingress",
        session_duration: str = CONST_CLOUDFLARE_DEFAULT_SESSION_DURATION,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Ensure an Access application, allow policy, and optional IP bypass policy protect the domain."""
        aid = account_id or self._account_id
        if not aid:
            raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
        app, app_action = self._ensure_access_application(
            domain=domain,
            name=name,
            session_duration=session_duration,
            account_id=aid,
        )
        allow_policy = self.create_or_update_access_policy(
            app_id=app.id,
            name=CONST_CLOUDFLARE_ALLOW_POLICY_NAME,
            allowed_emails=allowed_emails,
            decision="allow",
            account_id=aid,
        )
        bypass_policy_id = self._sync_bypass_policy_if_configured(
            app_id=app.id,
            bypass_ips=bypass_ips,
            account_id=aid,
        )
        return {
            "app_id": app.id,
            "app_name": app.name,
            "domain": app.domain,
            "app_action": app_action,
            "policy_id": allow_policy.id,
            "allowed_emails": list(allowed_emails),
            "bypass_ips": list(bypass_ips) if bypass_ips else [],
            "bypass_policy_id": bypass_policy_id,
        }


__all__ = ["CloudflareClient"]
