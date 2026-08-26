"""Security tools, reference extractors, and vulnerability lookup integrations."""

from __future__ import annotations

from devops_cli.security.bandit import run_bandit_scan
from devops_cli.security.checkov import run_checkov_scan
from devops_cli.security.dive import run_dive_analysis
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.kubeconform import run_kubeconform_validation
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
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.tflint import run_tflint_scan
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
    "run_checkov_scan",
    "run_dive_analysis",
    "run_gitleaks_scan",
    "run_kubeconform_validation",
    "run_kubelinter_scan",
    "run_pluto_scan",
    "run_popeye_scan",
    "run_semgrep_scan",
    "run_tflint_scan",
    "run_trivy_scan",
]
