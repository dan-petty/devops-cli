"""Executable markdown specification contracts and architectural invariant verifier."""

from __future__ import annotations

from devops_cli.ai.spec.verifier import (
    ArchitectureSpecReport,
    SpecContractRule,
    verify_architecture_spec,
)

__all__ = [
    "ArchitectureSpecReport",
    "SpecContractRule",
    "verify_architecture_spec",
]
