"""Unit and integration tests for distributed threat intelligence Valkey L2 caching and batching."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.models.vulnerability import NetworkReputationRecord
from devops_cli.security.vulnerability_lookup import CloudflareRadarClient


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


def test_cloudflare_radar_valkey_offline_fallback() -> None:
    broken_valkey = MagicMock()
    broken_valkey.get.side_effect = RuntimeError("Valkey socket connection refused")
    broken_valkey.set.side_effect = RuntimeError("Valkey broken pipe")

    client = CloudflareRadarClient(valkey_client=broken_valkey)
    with patch("httpx2.Client.get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"result": {"categories": [{"name": "Utility"}]}}
        mock_get.return_value = mock_resp

        # Should not raise; gracefully falls back to direct lookup
        rec = client.check_domain("fallback-domain.org")
        assert rec.target == "fallback-domain.org"
        assert "Utility" in rec.tags
        assert mock_get.call_count == 1

        # Second call hits L1 cache without error
        rec2 = client.check_domain("fallback-domain.org")
        assert rec2.target == "fallback-domain.org"
        assert mock_get.call_count == 1


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
