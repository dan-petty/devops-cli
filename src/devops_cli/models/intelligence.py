"""Pydantic data models for dependency vulnerability records and network reference reputation.

Deprecated: Import directly from `devops_cli.models.vulnerability` instead.
"""

from __future__ import annotations

from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    VulnerabilityRecord,
)

__all__ = [
    "DependencySpec",
    "NetworkReference",
    "NetworkReputationRecord",
    "VulnerabilityRecord",
]
