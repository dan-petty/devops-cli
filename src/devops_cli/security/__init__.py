"""Security tools, reference extractors, and vulnerability lookup integrations."""

from __future__ import annotations

from devops_cli.security.bandit import run_bandit_scan
from devops_cli.security.kubelinter import run_kubelinter_scan
from devops_cli.security.pluto import run_pluto_scan
from devops_cli.security.popeye import run_popeye_scan
from devops_cli.security.reference_extractor import (
    extract_dependencies_from_text,
    extract_network_references,
    is_file_reference,
    is_network_domain,
    is_public_ip,
)
from devops_cli.security.trivy import run_trivy_scan
from devops_cli.security.vulnerability_lookup import (
    CloudflareRadarClient,
    NVDClient,
    OSVClient,
    ShodanInternetDBClient,
)

__all__ = [
    "CloudflareRadarClient",
    "NVDClient",
    "OSVClient",
    "ShodanInternetDBClient",
    "extract_dependencies_from_text",
    "extract_network_references",
    "is_file_reference",
    "is_network_domain",
    "is_public_ip",
    "run_bandit_scan",
    "run_kubelinter_scan",
    "run_pluto_scan",
    "run_popeye_scan",
    "run_trivy_scan",
]
