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


class TFCostResource(BaseModel):
    """Single cloud infrastructure resource cost estimate."""

    name: str = Field(..., description="Resource name/identifier")
    resource_type: str = Field(
        default="", alias="resourceType", description="Terraform resource type"
    )
    hourly_cost: float = Field(default=0.0, alias="hourlyCost", description="Hourly cost estimate")
    monthly_cost: float = Field(
        default=0.0, alias="monthlyCost", description="Monthly cost estimate"
    )

    model_config = {"populate_by_name": True}


class TFCostBreakdownResult(BaseModel):
    """Execution report and cost breakdown from Infracost."""

    directory: str = Field(default="tf", description="Target IaC directory")
    currency: str = Field(default="USD", description="Billing currency")
    total_hourly_cost: float = Field(default=0.0, description="Total estimated hourly cost")
    total_monthly_cost: float = Field(default=0.0, description="Total estimated monthly cost")
    past_monthly_cost: float | None = Field(
        default=None, description="Previous baseline monthly cost"
    )
    diff_monthly_cost: float | None = Field(default=None, description="Delta monthly cost change")
    budget_exceeded: bool = Field(
        default=False, description="Whether budget threshold was exceeded"
    )
    resources: list[TFCostResource] = Field(
        default_factory=list, description="Resource cost line items"
    )
    source: str = Field(
        default="infracost", description="Execution engine source (infracost, mock)"
    )
    raw_json: dict[str, Any] | None = Field(default=None, description="Raw JSON data payload")

    model_config = {"populate_by_name": True}
