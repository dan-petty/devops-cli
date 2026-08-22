"""Security reference extractors and vulnerability lookups.

Deprecated: Import from `devops_cli.security.reference_extractor` or
`devops_cli.security.vulnerability_lookup` instead.
"""

from __future__ import annotations

from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    VulnerabilityRecord,
)
from devops_cli.security.reference_extractor import (
    extract_dependencies_from_text,
    extract_network_references,
    is_file_reference,
    is_network_domain,
    is_public_ip,
)
from devops_cli.security.vulnerability_lookup import (
    CloudflareRadarClient,
    NVDClient,
    OSVClient,
    ShodanInternetDBClient,
)

__all__ = [
    "CloudflareRadarClient",
    "DependencySpec",
    "NVDClient",
    "NetworkReference",
    "NetworkReputationRecord",
    "OSVClient",
    "ShodanInternetDBClient",
    "VulnerabilityRecord",
    "extract_dependencies_from_text",
    "extract_network_references",
    "is_file_reference",
    "is_network_domain",
    "is_public_ip",
]
