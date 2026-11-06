"""Which DNS records a target selects, and their deletion, over the HTTP fake (#1335).

`find_matching_records` runs on records a test builds. `delete_dns_records` runs a real
`CloudflareClient` against `web`, a Cloudflare API that holds one zone of records, so each test
reads the DELETE requests that reached the API.
"""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.cloudflare.dns import DnsDeletion, delete_dns_records, find_matching_records
from devops_cli.models.cloudflare import CloudflareDNSRecord
from tests.support.fakes.http import WebFake

MANAGED = "Managed by devops-cli"
DOMAIN = "example.com"
ZONE = "zone-1"


def _record(
    record_id: str,
    name: str,
    *,
    record_type: str = "CNAME",
    comment: str | None = MANAGED,
) -> CloudflareDNSRecord:
    """A DNS record of the zone, managed by devops-cli unless `comment` says otherwise."""
    return CloudflareDNSRecord(
        id=record_id,
        type=record_type,
        name=name,
        content="target.cfargotunnel.com",
        comment=comment,
    )


def _ids(records: list[CloudflareDNSRecord]) -> list[str]:
    """The IDs of `records`, in order."""
    return [record.id for record in records]


# ─────────────────────────────────────────────────────────────────────────────
# find_matching_records
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param("chat.example.com", ["chat"], id="full-name"),
        pytest.param("CHAT.Example.COM", ["chat"], id="full-name-ignores-case"),
        pytest.param("chat", ["chat"], id="label-of-the-domain"),
        pytest.param("@", ["apex"], id="apex"),
        pytest.param("rec-docs", ["docs"], id="record-id"),
        pytest.param("missing.example.com", [], id="no-record-has-the-name"),
    ],
)
def test_a_target_selects_records_by_name_or_by_id(target: str, expected: list[str]) -> None:
    """A target is a full name, a label of the domain, `@` for the apex, or a record ID."""
    existing = [
        _record("rec-apex", DOMAIN),
        _record("rec-chat", "chat.example.com"),
        _record("rec-docs", "docs.example.com"),
    ]

    matched = find_matching_records(existing, target, DOMAIN)

    assert _ids(matched) == [f"rec-{name}" for name in expected]


def test_a_type_keeps_only_records_of_that_type() -> None:
    """The type filter compares in upper case, so `a` selects an A record."""
    existing = [
        _record("rec-cname", DOMAIN, record_type="CNAME"),
        _record("rec-a", DOMAIN, record_type="A"),
    ]

    assert _ids(find_matching_records(existing, DOMAIN, DOMAIN, record_type="a")) == ["rec-a"]
    assert _ids(find_matching_records(existing, DOMAIN, DOMAIN)) == ["rec-cname", "rec-a"]


def test_a_record_that_devops_cli_does_not_manage_is_kept_unless_forced() -> None:
    """A record without the managed comment, or with another comment, needs `force`."""
    existing = [
        _record("rec-none", "a.example.com", comment=None),
        _record("rec-other", "a.example.com", comment="made by hand"),
        _record("rec-padded", "a.example.com", comment=f"  {MANAGED} \n"),
    ]

    assert _ids(find_matching_records(existing, "a.example.com", DOMAIN)) == ["rec-padded"]
    assert _ids(find_matching_records(existing, "a.example.com", DOMAIN, force=True)) == [
        "rec-none",
        "rec-other",
        "rec-padded",
    ]


def test_a_name_selects_every_record_of_that_name() -> None:
    """Two records of one name, such as an A and an AAAA record, both match."""
    existing = [
        _record("rec-a", "multi.example.com", record_type="A"),
        _record("rec-aaaa", "multi.example.com", record_type="AAAA"),
    ]

    assert _ids(find_matching_records(existing, "multi", DOMAIN)) == ["rec-a", "rec-aaaa"]


# ─────────────────────────────────────────────────────────────────────────────
# delete_dns_records
# ─────────────────────────────────────────────────────────────────────────────


def _zone(web: WebFake, records: list[CloudflareDNSRecord]) -> CloudflareClient:
    """A client of a Cloudflare API whose zone holds `records`; DELETE removes a record."""
    held = {record.id: record for record in records}

    def api(request: httpx2.Request) -> httpx2.Response | None:
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/zones/{ZONE}/dns_records"):
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": [record.model_dump() for record in held.values()],
                    "result_info": {"page": 1, "per_page": 100, "total_pages": 1},
                },
            )
        if request.method == "DELETE" and f"/zones/{ZONE}/dns_records/" in path:
            held.pop(path.rsplit("/", 1)[1], None)
            return httpx2.Response(200, json={"success": True, "result": {}})
        return None

    web.serve(api)
    return CloudflareClient(token="test-token", zone_id=ZONE)


def _deleted_ids(web: WebFake) -> list[str]:
    """The record IDs of the DELETE requests that reached the API, in order."""
    return [r.url.rsplit("/", 1)[1] for r in web.recorded if r.method == "DELETE"]


def test_the_records_a_target_selects_are_deleted(web: WebFake) -> None:
    """Each matched record is deleted by its ID, and its name and ID are returned."""
    client = _zone(web, [_record("rec-1", DOMAIN), _record("rec-2", "chat.example.com")])

    outcome = delete_dns_records(client, ["chat.example.com"], DOMAIN)

    assert (outcome, _deleted_ids(web)) == (
        DnsDeletion(deleted=[("chat.example.com", "rec-2")], not_found=[]),
        ["rec-2"],
    )


def test_a_target_that_selects_nothing_is_reported_and_nothing_is_deleted(web: WebFake) -> None:
    """A target with no record is listed as not found; the other targets still run."""
    client = _zone(web, [_record("rec-1", "chat.example.com")])

    outcome = delete_dns_records(client, ["gone.example.com", "chat"], DOMAIN)

    assert (outcome.deleted, outcome.not_found, _deleted_ids(web)) == (
        [("chat.example.com", "rec-1")],
        ["gone.example.com"],
        ["rec-1"],
    )


def test_an_unmanaged_record_is_deleted_only_when_forced(web: WebFake) -> None:
    """Without `force` the record is reported as not found and is not deleted."""
    client = _zone(web, [_record("rec-unmanaged", DOMAIN, comment=None)])

    safe = delete_dns_records(client, [DOMAIN], DOMAIN)
    forced = delete_dns_records(client, [DOMAIN], DOMAIN, force=True)

    assert (safe, forced, _deleted_ids(web)) == (
        DnsDeletion(deleted=[], not_found=[DOMAIN]),
        DnsDeletion(deleted=[(DOMAIN, "rec-unmanaged")], not_found=[]),
        ["rec-unmanaged"],
    )


def test_a_type_limits_the_records_that_are_deleted(web: WebFake) -> None:
    """Only the record of the requested type is deleted."""
    client = _zone(
        web,
        [
            _record("rec-cname", DOMAIN, record_type="CNAME"),
            _record("rec-a", DOMAIN, record_type="A"),
        ],
    )

    outcome = delete_dns_records(client, [DOMAIN], DOMAIN, record_type="A")

    assert (outcome.deleted, _deleted_ids(web)) == ([(DOMAIN, "rec-a")], ["rec-a"])


def test_the_zone_is_listed_one_time_for_all_targets(web: WebFake) -> None:
    """The records are read before the first deletion, so each target sees the same zone."""
    client = _zone(web, [_record("rec-1", "a.example.com"), _record("rec-2", "b.example.com")])

    delete_dns_records(client, ["a", "b"], DOMAIN)

    assert [r.method for r in web.recorded] == ["GET", "DELETE", "DELETE"]
