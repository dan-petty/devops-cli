"""Unit and integration tests for distributed threat intelligence Valkey L2 caching and batching."""

from __future__ import annotations

import json

import httpx2
import pytest
from fakeredis import FakeServer

from devops_cli.config.constants import CONST_THREAT_INTEL_CACHE_PREFIX
from devops_cli.models.vulnerability import NetworkReputationRecord
from devops_cli.security.vulnerability_lookup import CloudflareRadarClient
from devops_cli.valkey.client import ValkeyClient
from tests.support.fakes.clock import ClockFake
from tests.web_fakes import StubWeb

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def mock_cf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set configured Cloudflare token for threat intel cache tests."""
    monkeypatch.setenv("DEVOPS_CLI_CLOUDFLARE_API_TOKEN", "mock-cf-token")


def _l2_key(domain: str) -> str:
    return f"{CONST_THREAT_INTEL_CACHE_PREFIX}:{domain}"


def _stored_tags(valkey_client: ValkeyClient, domain: str) -> list[str]:
    raw = valkey_client.get(_l2_key(domain))
    assert raw is not None
    return NetworkReputationRecord.model_validate_json(raw).tags


def _serve_radar(stub_web: StubWeb, category: str = "Live") -> None:
    """Serve a 200 response that classifies any domain into category."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"result": {"categories": [{"name": category}]}})

    stub_web.serve(handler)


def test_cloudflare_radar_l1_cache_hit(stub_web: StubWeb) -> None:
    client = CloudflareRadarClient(valkey_client=None)
    stub_web.respond(
        "GET",
        f"{CloudflareRadarClient.BASE_URL}/ranking/domain/safe-target.org",
        200,
        {"result": {"categories": [{"name": "Technology"}, {"name": "Security"}]}},
    )

    rec1 = client.check_domain("safe-target.org")
    assert rec1.target == "safe-target.org"
    assert "Technology" in rec1.tags
    assert len(stub_web.sent) == 1

    # Second call hits in-memory L1 cache
    rec2 = client.check_domain("safe-target.org")
    assert rec2.target == "safe-target.org"
    assert len(stub_web.sent) == 1


def test_cloudflare_radar_valkey_l2_cache_hit(
    stub_web: StubWeb, valkey_client: ValkeyClient
) -> None:
    cached_record = NetworkReputationRecord(
        target="cached-domain.net",
        ip="",
        source="Cloudflare Radar",
        tags=["Cloud Services"],
        reputation_summary="Categorized domain: Cloud Services",
        outcome="ok",
    )
    valkey_client.set(_l2_key("cached-domain.net"), cached_record.model_dump_json())

    client = CloudflareRadarClient(valkey_client=valkey_client)
    rec = client.check_domain("cached-domain.net")
    assert rec.target == "cached-domain.net"
    assert "Cloud Services" in rec.tags
    # HTTP client should NOT be called
    assert stub_web.sent == []


def test_cloudflare_radar_valkey_l2_cache_miss_populates_l2(
    stub_web: StubWeb, valkey_client: ValkeyClient
) -> None:
    client = CloudflareRadarClient(valkey_client=valkey_client)
    stub_web.respond(
        "GET",
        f"{CloudflareRadarClient.BASE_URL}/ranking/domain/new-domain.io",
        200,
        {"result": {"categories": [{"name": "Software"}, {"name": "DevOps"}]}},
    )

    rec = client.check_domain("new-domain.io")
    assert rec.target == "new-domain.io"
    assert "Software" in rec.tags
    assert len(stub_web.sent) == 1

    # Should write through to Valkey L2 with TTL
    raw = valkey_client.get(_l2_key("new-domain.io"))
    assert raw is not None
    stored_payload = json.loads(raw)
    assert stored_payload["target"] == "new-domain.io"
    assert "Software" in stored_payload["tags"]
    assert int(valkey_client.execute("TTL", _l2_key("new-domain.io"))) > 0


def test_cloudflare_radar_batch_domains(stub_web: StubWeb, valkey_client: ValkeyClient) -> None:
    cached_record = NetworkReputationRecord(
        target="domain-a.org",
        ip="",
        source="Cloudflare Radar",
        tags=["Infrastructure"],
        outcome="ok",
    )
    valkey_client.set(_l2_key("domain-a.org"), cached_record.model_dump_json())

    client = CloudflareRadarClient(valkey_client=valkey_client)
    _serve_radar(stub_web, category="Analytics")

    results = client.check_domains_batch(["domain-a.org", "domain-b.org", "domain-c.org"])
    assert len(results) == 3
    assert "domain-a.org" in results
    assert "domain-b.org" in results
    assert "domain-c.org" in results
    assert results["domain-a.org"].tags == ["Infrastructure"]
    assert results["domain-b.org"].tags == ["Analytics"]

    # Only domain-b and domain-c should have been queried over HTTP
    assert len(stub_web.sent) == 2


def test_cloudflare_radar_batch_empty_and_examples(stub_web: StubWeb) -> None:
    client = CloudflareRadarClient(valkey_client=None)

    # Empty batch returns empty map
    assert client.check_domains_batch([]) == {}
    assert stub_web.sent == []

    # Example / RFC reserved domains return immediately without HTTP
    results = client.check_domains_batch(["example.com", "example.org"])
    assert len(results) == 2
    assert "example" in results["example.com"].tags
    assert "reserved" in results["example.com"].tags
    assert stub_web.sent == []


def test_cloudflare_radar_cache_hit_ratio_metric(valkey_client: ValkeyClient) -> None:
    cached_rec = NetworkReputationRecord(
        target="hit.org", ip="", source="Cloudflare Radar", outcome="ok"
    )
    valkey_client.set(_l2_key("hit.org"), cached_rec.model_dump_json())

    client = CloudflareRadarClient(valkey_client=valkey_client)
    client.check_domain("hit.org")
    client.check_domain("hit.org")

    # Verify hit count / ratio statistics
    stats = client.get_cache_stats()
    assert stats["requests"] == 2
    assert stats["hits"] == 2
    assert stats["hit_ratio"] == 1.0


def test_cloudflare_radar_error_not_saved_to_valkey_l2(
    stub_web: StubWeb, valkey_client: ValkeyClient
) -> None:
    client = CloudflareRadarClient(valkey_client=valkey_client)
    stub_web.fail(
        f"{CloudflareRadarClient.BASE_URL}/ranking/domain/transient-error-domain.org",
        httpx2.ConnectError("Radar API network connection timeout"),
    )

    rec = client.check_domain("transient-error-domain.org")
    assert rec.target == "transient-error-domain.org"
    assert rec.outcome == "failed"
    assert "Verified domain reference" not in rec.reputation_summary

    # Transient error fallback must NOT be saved to distributed L2 cache
    assert valkey_client.get(_l2_key("transient-error-domain.org")) is None


def test_cloudflare_radar_configurable_ttl(stub_web: StubWeb, valkey_client: ValkeyClient) -> None:
    client = CloudflareRadarClient(valkey_client=valkey_client, ttl=3600)
    stub_web.respond(
        "GET",
        f"{CloudflareRadarClient.BASE_URL}/ranking/domain/custom-ttl.org",
        200,
        {"result": {"categories": [{"name": "Security"}]}},
    )

    client.check_domain("custom-ttl.org")
    assert valkey_client.get(_l2_key("custom-ttl.org")) is not None
    ttl = int(valkey_client.execute("TTL", _l2_key("custom-ttl.org")))
    assert 0 < ttl <= 3600


def test_cloudflare_radar_batch_size_validation() -> None:
    from devops_cli.exceptions import ValidationError

    client = CloudflareRadarClient(valkey_client=None)

    with pytest.raises(ValidationError, match="batch_size must be a positive integer"):
        client.check_domains_batch(["example.org"], batch_size=0)

    with pytest.raises(ValidationError, match="batch_size must be a positive integer"):
        client.check_domains_batch(["example.org"], batch_size=-1)


def _cooldown() -> float:
    """The cooldown of the breaker of the Valkey cache tier, in seconds."""
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS

    return DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS


def test_a_valkey_outage_turns_the_threat_intel_l2_cache_off_for_a_cooldown(
    stub_web: StubWeb, valkey_server: FakeServer, valkey_client: ValkeyClient, clock: ClockFake
) -> None:
    """A failed read sends lookups to Radar for the cooldown; a read after it serves from Valkey.

    Valkey holds a `Cached` record of each of the first three domains, and Radar answers `Live`.
    So the tags of a lookup show which tier answered it.
    """
    for domain in ("outage.org", "cooldown.org", "trial.org"):
        cached = NetworkReputationRecord(
            target=domain, ip="", source="Cloudflare Radar", tags=["Cached"], outcome="ok"
        )
        valkey_client.set(_l2_key(domain), cached.model_dump_json())
    client = CloudflareRadarClient(valkey_client=valkey_client)

    _serve_radar(stub_web, category="Live")
    valkey_server.connected = False
    in_the_outage = client.check_domain("outage.org")
    valkey_server.connected = True
    in_the_cooldown = client.check_domain("cooldown.org")
    clock.shift(_cooldown())
    after_the_cooldown = client.check_domain("trial.org")
    not_cached = client.check_domain("new.org")

    assert [
        record.tags for record in (in_the_outage, in_the_cooldown, after_the_cooldown, not_cached)
    ] == [["Live"], ["Live"], ["Cached"], ["Live"]]
    assert (
        len(stub_web.sent),
        _stored_tags(valkey_client, "cooldown.org"),
        _stored_tags(valkey_client, "new.org"),
    ) == (3, ["Cached"], ["Live"])


def test_a_corrupt_threat_intel_entry_is_a_miss_and_keeps_the_l2_cache_on(
    stub_web: StubWeb, valkey_client: ValkeyClient
) -> None:
    """Radar answers the lookup, and its record replaces the corrupt entry in Valkey."""
    valkey_client.set(_l2_key("corrupt-domain.org"), "not valid json {{")
    client = CloudflareRadarClient(valkey_client=valkey_client)

    _serve_radar(stub_web, category="Live")
    record = client.check_domain("corrupt-domain.org")

    assert (record.tags, _stored_tags(valkey_client, "corrupt-domain.org")) == (
        ["Live"],
        ["Live"],
    )


def test_a_threat_intel_entry_with_no_outcome_is_a_miss(
    stub_web: StubWeb, valkey_client: ValkeyClient
) -> None:
    """An entry written before records named an outcome would read as verified: it is a miss.

    Radar answers the lookup, and its record replaces the stale entry in Valkey.
    """
    stale = {
        "target": "stale-domain.org",
        "ip": "",
        "source": "Cloudflare Radar",
        "tags": ["Stale"],
        "reputation_summary": "Categorized domain: Stale",
    }
    valkey_client.set(_l2_key("stale-domain.org"), json.dumps(stale))
    client = CloudflareRadarClient(valkey_client=valkey_client)

    _serve_radar(stub_web, category="Live")
    record = client.check_domain("stale-domain.org")

    assert (record.outcome, record.tags, _stored_tags(valkey_client, "stale-domain.org")) == (
        "ok",
        ["Live"],
        ["Live"],
    )


def test_a_radar_record_expires_from_the_memory_tier_after_the_ttl(
    stub_web: StubWeb, clock: ClockFake
) -> None:
    """A record stays in memory for the client's TTL, and the lookup after it asks Radar again."""
    client = CloudflareRadarClient(valkey_client=None, ttl=60)

    _serve_radar(stub_web, category="Live")
    client.check_domain("ttl-target.org")
    clock.shift(59)
    client.check_domain("ttl-target.org")
    asked_within_the_ttl = len(stub_web.sent)
    clock.shift(1)
    client.check_domain("ttl-target.org")

    assert (asked_within_the_ttl, len(stub_web.sent)) == (1, 2)


def test_a_full_radar_memory_tier_drops_the_least_recently_used_record(stub_web: StubWeb) -> None:
    """1,000 later records push the first record out, so Radar is asked about it again."""
    client = CloudflareRadarClient(valkey_client=None)

    _serve_radar(stub_web, category="Live")
    client.check_domain("first-target.org")
    for index in range(1000):
        client.check_domain(f"host{index}.example.com")
    client.check_domain("first-target.org")

    assert len(stub_web.sent) == 2
