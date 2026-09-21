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


# =============================================================================
# In-Process HCL AST Analysis & State Introspection
# =============================================================================


class IaCResource(BaseModel):
    """A resource or data source declared in HCL configuration."""

    address: str = Field(..., description="Canonical address, e.g. aws_vpc.main")
    block_type: str = Field(default="resource", description="Declaring block type")
    resource_type: str = Field(default="", description="Provider resource type")
    name: str = Field(default="", description="Local resource name")
    source_file: str = Field(default="", description="File the declaration was parsed from")
    provider: str = Field(default="", description="Provider prefix derived from the resource type")
    references: list[str] = Field(
        default_factory=list, description="Addresses this resource interpolates or depends on"
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Declared attribute values"
    )


class IaCModule(BaseModel):
    """A module invocation declared in HCL configuration."""

    address: str = Field(..., description="Canonical module address, e.g. module.db")
    name: str = Field(default="", description="Module instance name")
    source: str = Field(default="", description="Module source location")
    source_file: str = Field(default="", description="File the invocation was parsed from")
    references: list[str] = Field(
        default_factory=list, description="Addresses this module's arguments reference"
    )


class IaCConfiguration(BaseModel):
    """Typed projection of a parsed Terraform/OpenTofu configuration directory."""

    directory: str = Field(default="", description="Parsed configuration directory")
    resources: list[IaCResource] = Field(
        default_factory=list, description="Declared resources and data sources"
    )
    modules: list[IaCModule] = Field(default_factory=list, description="Declared module calls")
    variables: list[str] = Field(default_factory=list, description="Declared input variable names")
    outputs: list[str] = Field(default_factory=list, description="Declared output names")
    parsed_files: list[str] = Field(default_factory=list, description="Files parsed successfully")
    failed_files: dict[str, str] = Field(
        default_factory=dict, description="Files that failed to parse, keyed by path"
    )


class IaCStateResource(BaseModel):
    """A resource instance recorded in a Terraform/OpenTofu state file."""

    address: str = Field(..., description="Canonical state address")
    mode: str = Field(default="managed", description="State mode (managed or data)")
    resource_type: str = Field(default="", description="Provider resource type")
    name: str = Field(default="", description="Local resource name")
    provider: str = Field(default="", description="Fully qualified provider reference")
    module: str = Field(default="", description="Owning module path, empty for the root module")
    instance_count: int = Field(default=0, description="Number of recorded instances")


class IaCState(BaseModel):
    """Typed projection of a Terraform/OpenTofu state file."""

    version: int = Field(default=0, description="State format version")
    terraform_version: str = Field(default="", description="Binary version that wrote the state")
    serial: int = Field(default=0, description="State serial number")
    lineage: str = Field(default="", description="State lineage identifier")
    resources: list[IaCStateResource] = Field(
        default_factory=list, description="Recorded resource instances"
    )
    outputs: dict[str, Any] = Field(default_factory=dict, description="Recorded output values")


class IaCDriftReport(BaseModel):
    """Divergence between declared configuration and recorded state."""

    directory: str = Field(default="", description="Analyzed configuration directory")
    declared_count: int = Field(default=0, description="Resources declared in configuration")
    state_count: int = Field(default=0, description="Managed resources recorded in state")
    missing_from_state: list[str] = Field(
        default_factory=list, description="Declared but absent from state (awaiting apply)"
    )
    orphaned_in_state: list[str] = Field(
        default_factory=list, description="Recorded in state but no longer declared"
    )
    in_sync: list[str] = Field(
        default_factory=list, description="Addresses present in both configuration and state"
    )
    drift_detected: bool = Field(default=False, description="Whether any divergence was found")
    state_present: bool = Field(default=False, description="Whether a state file was found")


class IaCBlastRadius(BaseModel):
    """Transitive impact of changing a single resource address."""

    address: str = Field(..., description="Resource address the analysis originates from")
    direct_dependents: list[str] = Field(
        default_factory=list, description="Addresses directly referencing this resource"
    )
    transitive_dependents: list[str] = Field(
        default_factory=list, description="All addresses transitively impacted"
    )
    depends_on: list[str] = Field(
        default_factory=list, description="Addresses this resource itself depends upon"
    )
    impact_count: int = Field(default=0, description="Total transitively impacted addresses")
