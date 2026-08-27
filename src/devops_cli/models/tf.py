"""Pydantic resource models for OpenTofu and Terraform operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TFPlanRequest(BaseModel):
    """Request parameters for generating OpenTofu/Terraform infrastructure plans."""

    directory: str = Field(default="tf", description="Target IaC directory containing manifests")
    var_file: str | None = Field(default=None, description="Optional path to tfvars file")
    detailed_exitcode: bool = Field(
        default=False, description="Return detailed exit codes (0=clean, 1=error, 2=diff)"
    )


class TFPlanResult(BaseModel):
    """Results from OpenTofu/Terraform plan execution."""

    directory: str = Field(..., description="Target IaC directory")
    has_changes: bool = Field(default=False, description="Whether plan includes resource changes")
    resources_to_add: int = Field(default=0, description="Count of resources to create")
    resources_to_change: int = Field(default=0, description="Count of resources to modify in-place")
    resources_to_destroy: int = Field(default=0, description="Count of resources to destroy")
    plan_output: str = Field(default="", description="Formatted plan summary text")
    success: bool = Field(default=True, description="Whether plan generated successfully")


class TFApplyRequest(BaseModel):
    """Request parameters for applying OpenTofu/Terraform infrastructure changes."""

    directory: str = Field(default="tf", description="Target IaC directory")
    auto_approve: bool = Field(default=False, description="Skip interactive approval prompt")
    var_file: str | None = Field(default=None, description="Optional path to tfvars file")


class TFApplyResult(BaseModel):
    """Execution report from OpenTofu/Terraform apply."""

    directory: str = Field(..., description="Applied IaC directory")
    resources_added: int = Field(default=0, description="Count of resources created")
    resources_changed: int = Field(default=0, description="Count of resources updated")
    resources_destroyed: int = Field(default=0, description="Count of resources destroyed")
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Terraform outputs produced after apply"
    )
    success: bool = Field(default=True, description="Whether apply completed successfully")


class TFOutputRequest(BaseModel):
    """Request parameters for querying OpenTofu/Terraform outputs."""

    directory: str = Field(default="tf", description="Target IaC directory")
    output_name: str | None = Field(
        default=None, description="Specific output variable name (None for all)"
    )


class TFOutputResult(BaseModel):
    """Query results for OpenTofu/Terraform output variables."""

    directory: str = Field(..., description="Target IaC directory")
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Discovered output variable values"
    )
    success: bool = Field(default=True, description="Whether output query succeeded")


class TFLintRequest(BaseModel):
    """Request parameters for TFLint static provider and syntax checks."""

    directory: str = Field(default="tf", description="Target IaC directory")


class TFLintIssue(BaseModel):
    """Single lint issue reported by TFLint."""

    rule_name: str = Field(..., description="TFLint rule identifier")
    message: str = Field(..., description="Lint failure message")
    location: str = Field(..., description="File location in canonical file.ext:line format")
    severity: str = Field(default="WARNING", description="Issue severity")


class TFLintResult(BaseModel):
    """Execution report from TFLint static checks."""

    directory: str = Field(..., description="Target IaC directory")
    passed: bool = Field(default=True, description="Whether all static rules passed")
    issues_count: int = Field(default=0, description="Total count of lint issues found")
    issues: list[TFLintIssue] = Field(default_factory=list, description="Discovered lint issues")
