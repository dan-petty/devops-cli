"""Pydantic resource models for continuous integration quality gate execution."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CICheckResult(BaseModel):
    """Result of a single CI quality gate check."""

    name: str = Field(..., description="Quality check name (e.g. test, lint, typecheck, coverage)")
    passed: bool = Field(default=True, description="Whether the check succeeded")
    duration_seconds: float = Field(default=0.0, description="Runtime in seconds")
    details: str = Field(default="", description="Summary output or failure message")


class CIRunRequest(BaseModel):
    """Request parameters for executing the devops ci quality gate."""

    checks: list[str] = Field(
        default_factory=list, description="Specific checks to run (empty for all 10 checks)"
    )
    fail_fast: bool = Field(default=False, description="Terminate execution on first failing check")


class CIRunResult(BaseModel):
    """Consolidated CI quality gate execution report."""

    passed: bool = Field(default=True, description="Whether all executed checks passed")
    total_checks: int = Field(default=0, description="Number of checks evaluated")
    passed_checks: int = Field(default=0, description="Number of passing checks")
    failed_checks: int = Field(default=0, description="Number of failing checks")
    total_duration_seconds: float = Field(default=0.0, description="Total elapsed runtime")
    checks: list[CICheckResult] = Field(
        default_factory=list, description="Individual check execution results"
    )
