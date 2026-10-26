"""Unit and integration tests for distributed threat intelligence Valkey L2 caching and batching."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fakeredis import FakeServer

from devops_cli.config.constants import CONST_THREAT_INTEL_CACHE_PREFIX
from devops_cli.models.vulnerability import NetworkReputationRecord
from devops_cli.security.vulnerability_lookup import CloudflareRadarClient
from devops_cli.valkey.client import ValkeyClient
from tests.support.fakes.clock import ClockFake

pytestmark = pytest.mark.usefixtures("mock_keyring")


@pytest.fixture(autouse=True)
def mock_cf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set configured Cloudflare token for threat intel cache tests."""
    monkeypatch.setenv("DEVOPS_CLI_CLOUDFLARE_API_TOKEN", "mock-cf-token")


@pytest.fixture
def mock_valkey() -> MagicMock:
    valkey = MagicMock()
    valkey.get.return_value = None
    valkey.set.return_value = True
    valkey.execute.return_value = None
    return valkey


def test_cloudflare_radar_l1_cache_hit() -> None:
    client = CloudflareRadarClient(valkey_client=None)
    with patch("httpx2.Client.get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "result": {"categories": [{"name": "Technology"}, {"name": "Security"}]}
        }
        mock_get.return_value = mock_resp

        rec1 = client.check_domain("safe-target.org")
        assert rec1.target == "safe-target.org"
        assert "Technology" in rec1.tags
        assert mock_get.call_count == 1

        # Second call hits in-memory L1 cache
        rec2 = client.check_domain("safe-target.org")
        assert rec2.target == "safe-target.org"
        assert mock_get.call_count == 1


def test_cloudflare_radar_valkey_l2_cache_hit(mock_valkey: MagicMock) -> None:
    cached_record = NetworkReputationRecord(
        target="cached-domain.net",
        ip="",
        source="Cloudflare Radar",
        tags=["Cloud Services"],
        reputation_summary="Categorized domain: Cloud Services",
    )
    mock_valkey.get.return_value = cached_record.model_dump_json()

    client = CloudflareRadarClient(valkey_client=mock_valkey)
    with patch("httpx2.Client.get") as mock_get:
        rec = client.check_domain("cached-domain.net")
        assert rec.target == "cached-domain.net"
        assert "Cloud Services" in rec.tags
        # HTTP client should NOT be called
        mock_get.assert_not_called()
        mock_valkey.get.assert_called_with("valkey:threat_intel:domain:cached-domain.net")


def test_cloudflare_radar_valkey_l2_cache_miss_populates_l2(mock_valkey: MagicMock) -> None:
    mock_valkey.get.return_value = None

    client = CloudflareRadarClient(valkey_client=mock_valkey)
    with patch("httpx2.Client.get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "result": {"categories": [{"name": "Software"}, {"name": "DevOps"}]}
        }
        mock_get.return_value = mock_resp

        rec = client.check_domain("new-domain.io")
        assert rec.target == "new-domain.io"
        assert "Software" in rec.tags
        assert mock_get.call_count == 1

        # Should write through to Valkey L2 with TTL
        mock_valkey.set.assert_called_once()
        call_args = mock_valkey.set.call_args
        assert call_args[0][0] == "valkey:threat_intel:domain:new-domain.io"
        stored_payload = json.loads(call_args[0][1])
        assert stored_payload["target"] == "new-domain.io"
        assert "Software" in stored_payload["tags"]
        assert call_args[1].get("ex") == 86400 or call_args[1].get("ttl") == 86400


def test_cloudflare_radar_batch_domains(mock_valkey: MagicMock) -> None:
    cached_record = NetworkReputationRecord(
        target="domain-a.org",
        ip="",
        source="Cloudflare Radar",
        tags=["Infrastructure"],
    )

    def valkey_get_side_effect(key: str) -> str | None:
        if "domain-a.org" in key:
            return cached_record.model_dump_json()
        return None

    mock_valkey.get.side_effect = valkey_get_side_effect

    client = CloudflareRadarClient(valkey_client=mock_valkey)
    with patch("httpx2.Client.get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"result": {"categories": [{"name": "Analytics"}]}}
        mock_get.return_value = mock_resp

        results = client.check_domains_batch(["domain-a.org", "domain-b.org", "domain-c.org"])
        assert len(results) == 3
        assert "domain-a.org" in results
        assert "domain-b.org" in results
        assert "domain-c.org" in results
        assert results["domain-a.org"].tags == ["Infrastructure"]
        assert results["domain-b.org"].tags == ["Analytics"]

        # Only domain-b and domain-c should have been queried over HTTP
        assert mock_get.call_count == 2


def test_cloudflare_radar_batch_empty_and_examples() -> None:
    client = CloudflareRadarClient(valkey_client=None)
    with patch("httpx2.Client.get") as mock_get:
        # Empty batch returns empty map
        assert client.check_domains_batch([]) == {}
        mock_get.assert_not_called()

        # Example / RFC reserved domains return immediately without HTTP
        results = client.check_domains_batch(["example.com", "example.org"])
        assert len(results) == 2
        assert "example" in results["example.com"].tags
        assert "reserved" in results["example.com"].tags
        mock_get.assert_not_called()


def test_cloudflare_radar_cache_hit_ratio_metric(mock_valkey: MagicMock) -> None:
    cached_rec = NetworkReputationRecord(target="hit.org", ip="", source="Cloudflare Radar")
    mock_valkey.get.return_value = cached_rec.model_dump_json()

    client = CloudflareRadarClient(valkey_client=mock_valkey)
    client.check_domain("hit.org")
    client.check_domain("hit.org")

    # Verify hit count / ratio statistics
    stats = client.get_cache_stats()
    assert stats["requests"] == 2
    assert stats["hits"] == 2
    assert stats["hit_ratio"] == 1.0


def test_cloudflare_radar_error_not_saved_to_valkey_l2(mock_valkey: MagicMock) -> None:
    mock_valkey.get.return_value = None

    client = CloudflareRadarClient(valkey_client=mock_valkey)
    with patch("httpx2.Client.get") as mock_get:
        mock_get.side_effect = RuntimeError("Radar API network connection timeout")

        rec = client.check_domain("transient-error-domain.org")
        assert rec.target == "transient-error-domain.org"
        assert rec.outcome == "failed"
        assert "Verified domain reference" not in rec.reputation_summary

        # Transient error fallback must NOT be saved to distributed L2 cache
        mock_valkey.set.assert_not_called()


def test_cloudflare_radar_configurable_ttl(mock_valkey: MagicMock) -> None:
    mock_valkey.get.return_value = None

    client = CloudflareRadarClient(valkey_client=mock_valkey, ttl=3600)
    with patch("httpx2.Client.get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"result": {"categories": [{"name": "Security"}]}}
        mock_get.return_value = mock_resp

        client.check_domain("custom-ttl.org")
        mock_valkey.set.assert_called_once()
        assert mock_valkey.set.call_args[1].get("ex") == 3600


def test_cloudflare_radar_batch_size_validation() -> None:
    from devops_cli.exceptions import ValidationError

    client = CloudflareRadarClient(valkey_client=None)

    with pytest.raises(ValidationError, match="batch_size must be a positive integer"):
        client.check_domains_batch(["example.org"], batch_size=0)

    with pytest.raises(ValidationError, match="batch_size must be a positive integer"):
        client.check_domains_batch(["example.org"], batch_size=-1)


def _cooldown() -> float:
    """The cooldown of the breaker of the Valkey cache tier, in seconds.

    The import is local, so the module loads on a base without the default.
    """
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS

    return DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS


def _l2_key(domain: str) -> str:
    return f"{CONST_THREAT_INTEL_CACHE_PREFIX}:{domain}"


def _radar_reply(category: str) -> MagicMock:
    """A Radar reply of 200 that puts the domain in one category."""
    reply = MagicMock(status_code=200)
    reply.json.return_value = {"result": {"categories": [{"name": category}]}}
    return reply


def _stored_tags(valkey_client: ValkeyClient, domain: str) -> list[str]:
    raw = valkey_client.get(_l2_key(domain))
    assert raw is not None
    return NetworkReputationRecord.model_validate_json(raw).tags


def test_a_valkey_outage_turns_the_threat_intel_l2_cache_off_for_a_cooldown(
    valkey_server: FakeServer, valkey_client: ValkeyClient, clock: ClockFake
) -> None:
    """A failed read sends lookups to Radar for the cooldown; a read after it serves from Valkey.

    Valkey holds a `Cached` record of each of the first three domains, and Radar answers `Live`.
    So the tags of a lookup show which tier answered it.
    """
    for domain in ("outage.org", "cooldown.org", "trial.org"):
        cached = NetworkReputationRecord(
            target=domain, ip="", source="Cloudflare Radar", tags=["Cached"]
        )
        valkey_client.set(_l2_key(domain), cached.model_dump_json())
    client = CloudflareRadarClient(valkey_client=valkey_client)

    with patch("httpx2.Client.get") as radar_get:
        radar_get.return_value = _radar_reply("Live")
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
        radar_get.call_count,
        _stored_tags(valkey_client, "cooldown.org"),
        _stored_tags(valkey_client, "new.org"),
    ) == (3, ["Cached"], ["Live"])


def test_a_corrupt_threat_intel_entry_is_a_miss_and_keeps_the_l2_cache_on(
    valkey_client: ValkeyClient,
) -> None:
    """Radar answers the lookup, and its record replaces the corrupt entry in Valkey."""
    valkey_client.set(_l2_key("corrupt-domain.org"), "not valid json {{")
    client = CloudflareRadarClient(valkey_client=valkey_client)

    with patch("httpx2.Client.get") as radar_get:
        radar_get.return_value = _radar_reply("Live")
        record = client.check_domain("corrupt-domain.org")

    assert (record.tags, _stored_tags(valkey_client, "corrupt-domain.org")) == (
        ["Live"],
        ["Live"],
    )
