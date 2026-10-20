"""Tests for Google OSV-Scanner dependency vulnerability and SBOM integration (#1146).

Validates offline database snapshot caching with 24h TTL, AdvisoryAnchor generation,
preservation of advisory severities without HIGH default, CycloneDX 1.5 inventory in
EnvironmentFacts, missing-lock coverage gaps, and opt-in threat intelligence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review.pipeline import _STATIC_ANALYZERS, ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import DefectClass, Finding
from devops_cli.config.commands import BIN_OSV_SCANNER, build_osv_scan_cmd
from devops_cli.config.constants import CONST_OSV_OFFLINE_DB_TTL_SECONDS
from devops_cli.models.vulnerability import NetworkReputationRecord
from devops_cli.review.analysis import default_environment_facts
from devops_cli.review.anchors import AdvisoryAnchor
from devops_cli.security.osv_scanner import (
    OsvScanner,
    _extract_osv_severity,
    detect_manifest_coverage_gaps,
    get_or_compute_snapshot_digest,
    parse_osv_scanner_output,
    run_osv_scan,
)
from devops_cli.security.reference_extractor import NetworkReference
from devops_cli.security.registry import global_scanner_registry
from tests.support.fakes.scanners import ScannerFake


def test_osv_scanner_command_builder(tmp_path: Path) -> None:
    """build_osv_scan_cmd builds offline JSON command over target lockfiles."""
    lock = tmp_path / "poetry.lock"
    cmd = build_osv_scan_cmd(lock, lockfiles=[lock], offline=True)
    assert cmd == [
        BIN_OSV_SCANNER,
        "scan",
        "source",
        "--format",
        "json",
        "--offline",
        "--offline-vulnerabilities",
        "--all-packages",
        "--all-vulns",
        "--lockfile",
        str(lock),
    ]


def test_osv_severity_extraction_never_defaults_to_high() -> None:
    """Severities map directly from advisory database/ecosystem fields, falling back to UNKNOWN."""
    # Database specific severity
    assert _extract_osv_severity({"database_specific": {"severity": "MODERATE"}}) == "MEDIUM"
    assert _extract_osv_severity({"database_specific": {"severity": "CRITICAL"}}) == "CRITICAL"
    assert _extract_osv_severity({"database_specific": {"severity": "LOW"}}) == "LOW"

    # Ecosystem specific severity
    assert _extract_osv_severity({"ecosystem_specific": {"severity": "HIGH"}}) == "HIGH"

    # Missing severity never defaults to HIGH
    assert _extract_osv_severity({}) == "UNKNOWN"
    assert _extract_osv_severity({"database_specific": {}}) == "UNKNOWN"
    assert (
        _extract_osv_severity(
            {"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N"}]}
        )
        == "UNKNOWN"
    )


def test_osv_snapshot_digest_cached_with_24h_ttl(tmp_path: Path) -> None:
    """get_or_compute_snapshot_digest respects 24h TTL and caches deterministically."""
    cache_dir = tmp_path / "osv_cache"
    cache_dir.mkdir()
    (cache_dir / "vulns.db").write_text("dummy-db-v1", encoding="utf-8")

    digest1 = get_or_compute_snapshot_digest(cache_dir)
    assert digest1.startswith("sha256:")

    stamp_file = cache_dir / ".snapshot_digest"
    assert stamp_file.exists()

    # Second call returns cached digest without recomputing
    digest2 = get_or_compute_snapshot_digest(cache_dir)
    assert digest2 == digest1

    # Simulate expired TTL (> 24 hours)
    old_time = time.time() - (CONST_OSV_OFFLINE_DB_TTL_SECONDS + 100)
    stamp_file.write_text(
        json.dumps({"timestamp": old_time, "digest": "sha256:expired"}), encoding="utf-8"
    )

    digest3 = get_or_compute_snapshot_digest(cache_dir)
    assert digest3 != "sha256:expired"
    assert digest3 == digest1


def test_parse_osv_scanner_output_anchors_and_cyclonedx(tmp_path: Path) -> None:
    """parse_osv_scanner_output produces AdvisoryAnchor models and CycloneDX 1.5 inventory."""
    raw_payload = {
        "results": [
            {
                "packageSource": {"path": "poetry.lock", "type": "lockfile"},
                "packages": [
                    {
                        "package": {
                            "name": "urllib3",
                            "version": "1.26.4",
                            "ecosystem": "PyPI",
                            "purl": "pkg:pypi/urllib3@1.26.4",
                        },
                        "vulnerabilities": [
                            {
                                "id": "GHSA-q2q7-5pp4-w6pg",
                                "summary": "Improper Removal of Sensitive Information before Storage or Transfer",
                                "database_specific": {"severity": "MODERATE"},
                                "affected": [
                                    {
                                        "ranges": [
                                            {
                                                "type": "ECOSYSTEM",
                                                "events": [
                                                    {"introduced": "0"},
                                                    {"fixed": "1.26.5"},
                                                ],
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "package": {
                            "name": "certifi",
                            "version": "2021.5.30",
                            "ecosystem": "PyPI",
                            "purl": "pkg:pypi/certifi@2021.5.30",
                        },
                        "vulnerabilities": [],
                    },
                ],
            }
        ]
    }

    findings, cdx, locked = parse_osv_scanner_output(raw_payload, snapshot_digest="sha256:testsnap")

    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "MEDIUM"
    assert f.category == DefectClass.SUPPLY_CHAIN.value
    assert f.title == "Vulnerable Dependency: urllib3 (GHSA-q2q7-5pp4-w6pg)"
    assert f.properties.get("fixed_versions") == ["1.26.5"]

    anchor = getattr(f, "_anchor")
    assert isinstance(anchor, AdvisoryAnchor)
    assert anchor.db == "OSV"
    assert anchor.advisory_id == "GHSA-q2q7-5pp4-w6pg"
    assert anchor.purl == "pkg:pypi/urllib3@1.26.4"
    assert anchor.locked_version == "1.26.4"
    assert anchor.snapshot == "sha256:testsnap"

    # CycloneDX 1.5 SBOM inventory check
    assert cdx["bomFormat"] == "CycloneDX"
    assert cdx["specVersion"] == "1.5"
    assert len(cdx["components"]) == 2
    comp_names = {c["name"] for c in cdx["components"]}
    assert comp_names == {"urllib3", "certifi"}

    assert locked == {
        "pkg:pypi/urllib3@1.26.4": ["1.26.4"],
        "pkg:pypi/certifi@2021.5.30": ["2021.5.30"],
    }


def test_detect_manifest_coverage_gaps(tmp_path: Path) -> None:
    """Missing lockfile for an existing project manifest is identified as a coverage gap."""
    # Tree with pyproject.toml and poetry.lock (clean) + package.json without lock (gap)
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n", encoding="utf-8")
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text("# poetry lock", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "app"}', encoding="utf-8")

    gaps = detect_manifest_coverage_gaps(tmp_path, known_lockfiles=[poetry_lock])
    assert len(gaps) == 1
    assert "package.json" in gaps[0]


def test_osv_scanner_scan_reports_coverage_gap_when_manifest_unlocked(tmp_path: Path) -> None:
    """OsvScanner returns coverage_gap outcome when manifests exist without lockfiles."""
    (tmp_path / "package.json").write_text('{"name": "app"}', encoding="utf-8")
    scanner = OsvScanner(snapshot_digest="sha256:mock")
    outcome = scanner.scan(tmp_path, tree=tmp_path)

    assert outcome.status == "coverage_gap"
    assert "missing lockfile for package.json" in outcome.reason
    assert outcome.findings == []


def test_osv_scanner_registered_in_registry() -> None:
    """OsvScanner is registered in global_scanner_registry."""
    scanner = global_scanner_registry.get("osv-scanner")
    assert scanner is not None
    assert isinstance(scanner, OsvScanner)
    assert scanner.binary_name == "osv-scanner"


def test_environment_facts_carries_cyclonedx_inventory() -> None:
    """default_environment_facts preserves CycloneDX inventory from findings or arguments."""
    inv = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [{"name": "fastapi", "version": "0.115.0"}],
    }

    finding = Finding(
        severity="MEDIUM",
        location="poetry.lock:requests",
        title="Vulnerable requests",
        properties={"cyclonedx_inventory": inv},
    )

    env = default_environment_facts([finding])
    assert env.cyclonedx_inventory == inv

    # Direct argument precedence
    direct_inv = {"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}
    env2 = default_environment_facts([], cyclonedx_inventory=direct_inv)
    assert env2.cyclonedx_inventory == direct_inv


def test_review_pipeline_has_osv_scanner_in_static_analyzers() -> None:
    """_STATIC_ANALYZERS includes osv-scanner targeting lockfiles."""
    scanner_names = [name for name, _, _ in _STATIC_ANALYZERS]
    assert "osv-scanner" in scanner_names
    lock_analyzer = next(entry for entry in _STATIC_ANALYZERS if entry[0] == "osv-scanner")
    assert lock_analyzer == ("osv-scanner", BIN_OSV_SCANNER, "lockfiles")


def test_run_osv_scan_invokes_scanner(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """run_osv_scan invokes OsvScanner over target lockfiles."""
    lock = tmp_path / "poetry.lock"
    lock.write_text("# lock", encoding="utf-8")
    outcome = run_osv_scan([lock], tree=tmp_path)
    assert outcome.status in ("ran", "clean", "skipped")


def test_threat_intel_opt_in_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scanner_fake: ScannerFake
) -> None:
    """ReviewPipelineOrchestrator threat_intel defaults to False and makes no external lookups."""
    src_file = tmp_path / "app.py"
    src_file.write_text('REMOTE = "198.51.100.1"\n', encoding="utf-8")

    sample_net = NetworkReference(
        target="198.51.100.1",
        reference_type="ip",
        source_file="app.py",
        line_number=1,
    )
    monkeypatch.setattr(
        "devops_cli.ai.review.pipeline.extract_network_references",
        lambda content, fpath: [sample_net],
    )

    called_shodan = False

    def _mock_shodan(client: Any, ip: str) -> tuple[str, NetworkReputationRecord]:
        nonlocal called_shodan
        called_shodan = True
        return (ip, NetworkReputationRecord(target=ip, ip=ip))

    monkeypatch.setattr(
        "devops_cli.ai.review.pipeline._fetch_ip_threat_intel",
        _mock_shodan,
    )

    # 1. Default (threat_intel=False): no threat lookups run
    orch = ReviewPipelineOrchestrator(
        session_id="test-ti-off",
        target_dir=tmp_path,
        threat_intel=False,
    )
    assert orch.threat_intel is False
    payloads = orch.init_per_file_payloads(["app.py"], {})
    assert called_shodan is False
    assert len(payloads) == 1
    assert payloads[0].network_references == []

    # 2. Opt-in (threat_intel=True): threat lookups run
    orch_on = ReviewPipelineOrchestrator(
        session_id="test-ti-on",
        target_dir=tmp_path,
        threat_intel=True,
    )
    assert orch_on.threat_intel is True
    payloads_on = orch_on.init_per_file_payloads(["app.py"], {})
    assert called_shodan is True
    assert len(payloads_on) == 1
    assert len(payloads_on[0].network_references) >= 1
