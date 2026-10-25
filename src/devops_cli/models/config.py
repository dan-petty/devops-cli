"""Pydantic resource models for configuration and environment inspection."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConfigShowRequest(BaseModel):
    """Request parameters for showing active DevOps CLI configuration."""

    include_defaults: bool = Field(default=True, description="Include default values in output")
    redact_secrets: bool = Field(default=True, description="Redact sensitive credentials in output")


class ConfigShowResult(BaseModel):
    """Active configuration settings payload."""

    config_path: str = Field(default="", description="Path to resolved configuration file")
    settings: dict[str, Any] = Field(
        default_factory=dict, description="Resolved hierarchical configuration values"
    )


class ConfigOptionSpec(BaseModel):
    """Specification metadata for a configuration option."""

    key: str = Field(..., description="Configuration dot-notation key (e.g. ai.provider)")
    env_var: str = Field(..., description="Corresponding environment variable name")
    type_name: str = Field(default="str", description="Value data type")
    default_value: Any = Field(default=None, description="Default value")
    description: str = Field(default="", description="Configuration option description")


class ConfigOutputRequest(BaseModel):
    """Request parameters for generating configuration documentation and environment specs."""

    format: str = Field(default="json", description="Output format (json, yaml, table, markdown)")


class ConfigOutputResult(BaseModel):
    """Exported configuration options and environment variable specifications."""

    total_options: int = Field(default=0, description="Total count of supported options")
    options: list[ConfigOptionSpec] = Field(
        default_factory=list, description="Supported option specifications"
    )


class ConfigKeyRemoval(BaseModel):
    """The removal of one key from a config file by `devops config unset` (#2201)."""

    path: str = Field(..., description="Config file that held the key")
    key: str = Field(..., description="Dotted key as the file holds it")
    line: int = Field(..., description="Line of the key before the removal, counted from 1")
    diff: str = Field(..., description="Unified diff of the removal, with no context lines")
    backup: str | None = Field(
        default=None, description="Copy of the file before the removal, or None for a dry run"
    )
