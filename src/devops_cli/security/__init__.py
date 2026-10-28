"""Security tools, reference extractors, and vulnerability lookup integrations."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.security.bandit import BanditScanner, run_bandit_scan
    from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
    from devops_cli.security.dive import DiveScanner, run_dive_analysis, run_dive_scan
    from devops_cli.security.gitleaks import GitleaksScanner, run_gitleaks_scan
    from devops_cli.security.kubeconform import (
        KubeconformScanner,
        is_kubernetes_manifest,
        run_kubeconform_validation,
    )
    from devops_cli.security.kubelinter import KubelinterScanner, run_kubelinter_scan
    from devops_cli.security.osv_scanner import OsvScanner, run_osv_scan
    from devops_cli.security.pluto import PlutoScanner, run_pluto_scan
    from devops_cli.security.popeye import PopeyeScanner, run_popeye_scan
    from devops_cli.security.reference_extractor import (
        deduplicate_network_references,
        extract_network_references,
        is_example_ip,
        is_example_or_invalid_domain,
        is_example_or_invalid_network_target,
        is_example_phone_number,
        is_local_or_reserved_domain,
        is_private_or_local_ip,
        is_public_ip,
        sort_network_references,
    )
    from devops_cli.security.registry import ScannerRegistry, global_scanner_registry
    from devops_cli.security.sanitizer import (
        mask_dict_secrets,
        mask_secrets,
        mask_uri_credentials,
        redact_text,
        sanitize_command_args_for_display,
        sanitize_prompt_boundary_tags,
        sanitize_telemetry_endpoint,
    )
    from devops_cli.security.semgrep import SemgrepScanner, run_semgrep_scan
    from devops_cli.security.tflint import TflintScanner, run_tflint_scan
    from devops_cli.security.trivy import TrivyConfigScanner, TrivyScanner, run_trivy_scan
    from devops_cli.security.vulnerability_lookup import (
        CloudflareRadarClient,
        OSVClient,
        ShodanInternetDBClient,
    )

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "BanditScanner": ("devops_cli.security.bandit", "BanditScanner"),
    "run_bandit_scan": ("devops_cli.security.bandit", "run_bandit_scan"),
    "BaseSecurityScanner": ("devops_cli.security.base", "BaseSecurityScanner"),
    "ScanOutcome": ("devops_cli.security.base", "ScanOutcome"),
    "DiveScanner": ("devops_cli.security.dive", "DiveScanner"),
    "run_dive_analysis": ("devops_cli.security.dive", "run_dive_analysis"),
    "run_dive_scan": ("devops_cli.security.dive", "run_dive_scan"),
    "GitleaksScanner": ("devops_cli.security.gitleaks", "GitleaksScanner"),
    "run_gitleaks_scan": ("devops_cli.security.gitleaks", "run_gitleaks_scan"),
    "KubeconformScanner": ("devops_cli.security.kubeconform", "KubeconformScanner"),
    "is_kubernetes_manifest": ("devops_cli.security.kubeconform", "is_kubernetes_manifest"),
    "run_kubeconform_validation": ("devops_cli.security.kubeconform", "run_kubeconform_validation"),
    "KubelinterScanner": ("devops_cli.security.kubelinter", "KubelinterScanner"),
    "run_kubelinter_scan": ("devops_cli.security.kubelinter", "run_kubelinter_scan"),
    "OsvScanner": ("devops_cli.security.osv_scanner", "OsvScanner"),
    "run_osv_scan": ("devops_cli.security.osv_scanner", "run_osv_scan"),
    "PlutoScanner": ("devops_cli.security.pluto", "PlutoScanner"),
    "run_pluto_scan": ("devops_cli.security.pluto", "run_pluto_scan"),
    "PopeyeScanner": ("devops_cli.security.popeye", "PopeyeScanner"),
    "run_popeye_scan": ("devops_cli.security.popeye", "run_popeye_scan"),
    "deduplicate_network_references": (
        "devops_cli.security.reference_extractor",
        "deduplicate_network_references",
    ),
    "extract_network_references": (
        "devops_cli.security.reference_extractor",
        "extract_network_references",
    ),
    "is_example_ip": ("devops_cli.security.reference_extractor", "is_example_ip"),
    "is_example_or_invalid_domain": (
        "devops_cli.security.reference_extractor",
        "is_example_or_invalid_domain",
    ),
    "is_example_or_invalid_network_target": (
        "devops_cli.security.reference_extractor",
        "is_example_or_invalid_network_target",
    ),
    "is_example_phone_number": (
        "devops_cli.security.reference_extractor",
        "is_example_phone_number",
    ),
    "is_local_or_reserved_domain": (
        "devops_cli.security.reference_extractor",
        "is_local_or_reserved_domain",
    ),
    "is_private_or_local_ip": ("devops_cli.security.reference_extractor", "is_private_or_local_ip"),
    "is_public_ip": ("devops_cli.security.reference_extractor", "is_public_ip"),
    "sort_network_references": (
        "devops_cli.security.reference_extractor",
        "sort_network_references",
    ),
    "ScannerRegistry": ("devops_cli.security.registry", "ScannerRegistry"),
    "global_scanner_registry": ("devops_cli.security.registry", "global_scanner_registry"),
    "mask_dict_secrets": ("devops_cli.security.sanitizer", "mask_dict_secrets"),
    "mask_secrets": ("devops_cli.security.sanitizer", "mask_secrets"),
    "mask_uri_credentials": ("devops_cli.security.sanitizer", "mask_uri_credentials"),
    "redact_text": ("devops_cli.security.sanitizer", "redact_text"),
    "sanitize_command_args_for_display": (
        "devops_cli.security.sanitizer",
        "sanitize_command_args_for_display",
    ),
    "sanitize_prompt_boundary_tags": (
        "devops_cli.security.sanitizer",
        "sanitize_prompt_boundary_tags",
    ),
    "sanitize_telemetry_endpoint": ("devops_cli.security.sanitizer", "sanitize_telemetry_endpoint"),
    "SemgrepScanner": ("devops_cli.security.semgrep", "SemgrepScanner"),
    "run_semgrep_scan": ("devops_cli.security.semgrep", "run_semgrep_scan"),
    "TflintScanner": ("devops_cli.security.tflint", "TflintScanner"),
    "run_tflint_scan": ("devops_cli.security.tflint", "run_tflint_scan"),
    "TrivyConfigScanner": ("devops_cli.security.trivy", "TrivyConfigScanner"),
    "TrivyScanner": ("devops_cli.security.trivy", "TrivyScanner"),
    "run_trivy_scan": ("devops_cli.security.trivy", "run_trivy_scan"),
    "CloudflareRadarClient": ("devops_cli.security.vulnerability_lookup", "CloudflareRadarClient"),
    "OSVClient": ("devops_cli.security.vulnerability_lookup", "OSVClient"),
    "ShodanInternetDBClient": (
        "devops_cli.security.vulnerability_lookup",
        "ShodanInternetDBClient",
    ),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BanditScanner",
    "BaseSecurityScanner",
    "CloudflareRadarClient",
    "DiveScanner",
    "GitleaksScanner",
    "KubeconformScanner",
    "KubelinterScanner",
    "OSVClient",
    "OsvScanner",
    "PlutoScanner",
    "PopeyeScanner",
    "ScanOutcome",
    "ScannerRegistry",
    "SemgrepScanner",
    "ShodanInternetDBClient",
    "TflintScanner",
    "TrivyConfigScanner",
    "TrivyScanner",
    "deduplicate_network_references",
    "extract_network_references",
    "global_scanner_registry",
    "is_example_ip",
    "is_example_or_invalid_domain",
    "is_example_or_invalid_network_target",
    "is_example_phone_number",
    "is_kubernetes_manifest",
    "is_local_or_reserved_domain",
    "is_private_or_local_ip",
    "is_public_ip",
    "mask_dict_secrets",
    "mask_secrets",
    "mask_uri_credentials",
    "redact_text",
    "run_bandit_scan",
    "run_dive_analysis",
    "run_dive_scan",
    "run_gitleaks_scan",
    "run_kubeconform_validation",
    "run_kubelinter_scan",
    "run_osv_scan",
    "run_pluto_scan",
    "run_popeye_scan",
    "run_semgrep_scan",
    "run_tflint_scan",
    "run_trivy_scan",
    "sanitize_command_args_for_display",
    "sanitize_prompt_boundary_tags",
    "sanitize_telemetry_endpoint",
    "sort_network_references",
]
