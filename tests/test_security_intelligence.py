"""Unit tests for security intelligence clients and dependency/network reference extractors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from devops_cli.security.intelligence import (
    CloudflareRadarClient,
    NVDClient,
    OSVClient,
    ShodanInternetDBClient,
    extract_dependencies_from_text,
    extract_network_references,
    is_public_ip,
)


def test_is_public_ip() -> None:
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("1.1.1.1") is True
    assert is_public_ip("127.0.0.1") is False
    assert is_public_ip("192.168.1.1") is False
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip("172.16.0.1") is False
    assert is_public_ip("invalid-ip") is False


def test_extract_dependencies_requirements_txt() -> None:
    content = """
    # Comments
    pydantic>=2.10.0
    httpx==0.28.1
    typer~=0.15.0
    pytest
    """
    deps = extract_dependencies_from_text(content, "requirements.txt")
    assert len(deps) == 4
    names = {d.name: d.version_range for d in deps}
    assert names["pydantic"] == ">=2.10.0"
    assert names["httpx"] == "==0.28.1"
    assert names["typer"] == "~=0.15.0"
    assert names["pytest"] == "*"


def test_extract_dependencies_package_json() -> None:
    content = """{
        "dependencies": {
            "react": "^18.2.0",
            "next": "14.1.0"
        },
        "devDependencies": {
            "typescript": "^5.0.0"
        }
    }"""
    deps = extract_dependencies_from_text(content, "package.json")
    assert len(deps) == 3
    assert all(d.ecosystem == "npm" for d in deps)


def test_extract_dependencies_cargo_and_go() -> None:
    cargo_content = """[dependencies]
    serde = "1.0"
    tokio = "1.35"
    """
    cargo_deps = extract_dependencies_from_text(cargo_content, "Cargo.toml")
    assert len(cargo_deps) == 2
    assert cargo_deps[0].ecosystem == "crates.io"

    go_content = """module example.com/foo
    go 1.22
    require (
        github.com/gin-gonic/gin v1.9.1
    )
    """
    go_deps = extract_dependencies_from_text(go_content, "go.mod")
    assert len(go_deps) == 1
    assert go_deps[0].ecosystem == "Go"


def test_extract_network_references() -> None:
    doc = """
    # Deployment Guide
    Access the cluster at https://api.prod.example-corp.com/v1
    Public ingress IP: 93.184.216.34
    Private internal IP: 192.168.1.100 (should be skipped)
    Test host: test.example.com (should be skipped)
    External endpoint: https://auth.vendor-service.io/oauth/token
    """
    refs = extract_network_references(doc, "docs/deploy.md")
    targets = {r.target for r in refs}
    assert "https://api.prod.example-corp.com/v1" in targets
    assert "93.184.216.34" in targets
    assert "192.168.1.100" not in targets
    assert "https://auth.vendor-service.io/oauth/token" in targets


@patch("httpx.Client.post")
def test_osv_client(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "vulns": [
            {
                "id": "GHSA-1234",
                "summary": "Sample RCE vulnerability",
                "severity": [
                    {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
                ],
            }
        ]
    }
    mock_post.return_value = mock_resp

    client = OSVClient()
    records = client.check_vulnerability("insecure-pkg", "1.0.0", "PyPI")
    assert len(records) == 1
    assert records[0].id == "GHSA-1234"
    assert records[0].severity == "CRITICAL"


@patch("httpx.Client.get")
def test_shodan_internetdb_client(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ip": "93.184.216.34",
        "ports": [80, 443],
        "vulns": ["CVE-2023-12345"],
        "tags": ["web-server"],
    }
    mock_get.return_value = mock_resp

    client = ShodanInternetDBClient()
    rec = client.check_ip("93.184.216.34")
    assert rec.ports == [80, 443]
    assert rec.cves == ["CVE-2023-12345"]
    assert rec.is_malicious is True


@patch("httpx.Client.get")
def test_nvd_client(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "vulnerabilities": [
            {
                "cve": {
                    "id": "CVE-2024-9999",
                    "descriptions": [{"lang": "en", "value": "NVD test description"}],
                }
            }
        ]
    }
    mock_get.return_value = mock_resp

    client = NVDClient()
    records = client.search_cve("vulnerable-pkg")
    assert len(records) == 1
    assert records[0].id == "CVE-2024-9999"
    assert records[0].source == "NVD"


@patch("httpx.Client.get")
def test_cloudflare_radar_client(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {"categories": [{"name": "Technology"}, {"name": "Cloud Platform"}]}
    }
    mock_get.return_value = mock_resp

    client = CloudflareRadarClient()
    rec = client.check_domain("api.cloudservice.io")
    assert "Technology" in rec.tags
    assert rec.source == "Cloudflare Radar"
