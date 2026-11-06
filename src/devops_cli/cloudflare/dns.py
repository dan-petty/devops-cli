"""Which Cloudflare DNS records a name or an ID selects, and their deletion."""

from __future__ import annotations

from typing import NamedTuple

from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.config.constants import CONST_CLOUDFLARE_RECORD_COMMENT
from devops_cli.models.cloudflare import CloudflareDNSRecord


class DnsDeletion(NamedTuple):
    """The outcome of a deletion run: each deleted record as (name, id), and the unmatched targets."""

    deleted: list[tuple[str, str]]
    not_found: list[str]


def _target_names(target: str, domain: str) -> tuple[str, str]:
    """The lower-case target, and the same target as a name qualified with `domain`."""
    if target == "@":
        full = domain
    elif "." not in target:
        full = f"{target}.{domain}"
    else:
        full = target
    return target.lower(), full.lower()


def find_matching_records(
    existing: list[CloudflareDNSRecord],
    target: str,
    domain: str,
    *,
    record_type: str | None = None,
    force: bool = False,
) -> list[CloudflareDNSRecord]:
    """The records that `target` selects, by record ID or by name.

    `target` is a record ID, `@` for the apex of `domain`, a label of `domain`, or a full name.
    A name is compared in lower case. A `record_type` keeps only records of that type. Unless
    `force` is set, a record matches only when devops-cli manages it, which its comment shows.
    """
    names = _target_names(target, domain)
    type_upper = record_type.upper() if record_type else None
    return [
        record
        for record in existing
        if (record.id == target or record.name.lower() in names)
        and (not type_upper or record.type.upper() == type_upper)
        and (force or (record.comment or "").strip() == CONST_CLOUDFLARE_RECORD_COMMENT)
    ]


def delete_dns_records(
    client: CloudflareClient,
    targets: list[str],
    domain: str,
    *,
    zone_id: str | None = None,
    record_type: str | None = None,
    force: bool = False,
) -> DnsDeletion:
    """Delete the records that each target selects, and list the targets that select none."""
    existing = client.list_dns_records(zone_id=zone_id)
    deleted: list[tuple[str, str]] = []
    not_found: list[str] = []

    for target in targets:
        matched = find_matching_records(
            existing, target, domain, record_type=record_type, force=force
        )
        if not matched:
            not_found.append(target)
            continue
        for record in matched:
            client.delete_dns_record(record.id, zone_id=zone_id)
            deleted.append((record.name, record.id))
    return DnsDeletion(deleted, not_found)


__all__ = ["DnsDeletion", "delete_dns_records", "find_matching_records"]
