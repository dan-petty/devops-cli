"""Security tools, reference extractors, and vulnerability lookup integrations."""

from __future__ import annotations

from devops_cli.security.bandit import BanditScanner, run_bandit_scan
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.security.checkov import CheckovScanner, run_checkov_scan
from devops_cli.security.dive import DiveScanner, run_dive_analysis
from devops_cli.security.gitleaks import GitleaksScanner, run_gitleaks_scan
from devops_cli.security.kubeconform import KubeconformScanner, run_kubeconform_validation
from devops_cli.security.kubelinter import KubelinterScanner, run_kubelinter_scan
from devops_cli.security.pluto import PlutoScanner, run_pluto_scan
from devops_cli.security.popeye import PopeyeScanner, run_popeye_scan
from devops_cli.security.reference_extractor import (
    extract_dependencies_from_text,
    extract_network_references,
    is_file_reference,
    is_network_domain,
    is_public_ip,
)
from devops_cli.security.registry import ScannerRegistry, global_scanner_registry
from devops_cli.security.sanitizer import (
    mask_dict_secrets,
    mask_secrets,
    mask_uri_credentials,
    redact_text,
    sanitize_command_args_for_display,
    sanitize_prompt_boundary_tags,
    sanitize_prompt_injection,
    sanitize_telemetry_endpoint,
)
from devops_cli.security.semgrep import SemgrepScanner, run_semgrep_scan
from devops_cli.security.tflint import TflintScanner, run_tflint_scan
from devops_cli.security.trivy import TrivyScanner, run_trivy_scan
from devops_cli.security.vulnerability_lookup import (
    CloudflareRadarClient,
    NVDClient,
    OSVClient,
    ShodanInternetDBClient,
)

__all__ = [
    "BanditScanner",
    "BaseSecurityScanner",
    "CheckovScanner",
    "CloudflareRadarClient",
    "DiveScanner",
    "GitleaksScanner",
    "KubeconformScanner",
    "KubelinterScanner",
    "NVDClient",
    "OSVClient",
    "PlutoScanner",
    "PopeyeScanner",
    "ScannerRegistry",
    "SemgrepScanner",
    "ShodanInternetDBClient",
    "TflintScanner",
    "TrivyScanner",
    "extract_dependencies_from_text",
    "extract_network_references",
    "global_scanner_registry",
    "is_file_reference",
    "is_network_domain",
    "is_public_ip",
    "mask_dict_secrets",
    "mask_secrets",
    "mask_uri_credentials",
    "redact_text",
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
    "sanitize_command_args_for_display",
    "sanitize_prompt_boundary_tags",
    "sanitize_prompt_injection",
    "sanitize_telemetry_endpoint",
]
