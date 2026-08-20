"""Pydantic data models for dependency vulnerability records and network reference reputation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DependencySpec(BaseModel):
    name: str
    version_range: str = "*"
    ecosystem: str = "PyPI"  # PyPI | npm | crates.io | Go
    source_file: str = ""


class VulnerabilityRecord(BaseModel):
    id: str
    summary: str = ""
    severity: str = "MEDIUM"
    package: str = ""
    affected_version_range: str = ""
    fixed_version: str = ""
    source: str = "OSV"  # OSV | NVD
    details_url: str = ""


class NetworkReference(BaseModel):
    target: str
    reference_type: str = "domain"  # ip | domain | url
    source_file: str = ""
    line_number: int | None = None


class NetworkReputationRecord(BaseModel):
    target: str
    ip: str = ""
    ports: list[int] = Field(default_factory=list)
    cves: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    hostnames: list[str] = Field(default_factory=list)
    reputation_score: float | None = None  # 0.0 (safe) - 1.0 (malicious)
    reputation_summary: str = "Clean"
    is_malicious: bool = False
    source: str = "Shodan InternetDB"
