"""Software Bill of Materials (SBOM) Generator in CycloneDX, SPDX, and JSON formats."""

from __future__ import annotations

import importlib.metadata
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class SBOMComponent:
    """A single software component in an SBOM."""

    name: str
    version: str
    purl: str
    type: str = "library"
    description: str = ""
    licenses: list[str] = field(default_factory=list)


@dataclass
class SBOMDocument:
    """Structured SBOM metadata document."""

    format: str
    spec_version: str
    timestamp: str
    root_component: str
    components: list[SBOMComponent] = field(default_factory=list)


def extract_workspace_components(workspace_dir: Path) -> list[SBOMComponent]:
    """Extract installed or locked dependencies from uv.lock or active Python runtime."""
    components: list[SBOMComponent] = []
    uv_lock = workspace_dir / "uv.lock"

    if uv_lock.exists():
        try:
            lock_data = tomllib.loads(uv_lock.read_text(encoding="utf-8"))
            for pkg in lock_data.get("package", []):
                name = pkg.get("name", "")
                version = pkg.get("version", "")
                if name:
                    purl = f"pkg:pypi/{name}@{version}" if version else f"pkg:pypi/{name}"
                    components.append(
                        SBOMComponent(
                            name=name,
                            version=version,
                            purl=purl,
                            type="library",
                        )
                    )
            return sorted(components, key=lambda c: c.name.lower())
        except Exception:
            pass

    # Fallback to runtime installed distributions
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name", "")
        version = dist.metadata.get("Version", "")
        if name:
            purl = f"pkg:pypi/{name}@{version}" if version else f"pkg:pypi/{name}"
            components.append(
                SBOMComponent(
                    name=name,
                    version=version,
                    purl=purl,
                    description=dist.metadata.get("Summary", ""),
                )
            )

    return sorted(components, key=lambda c: c.name.lower())


def generate_cyclonedx_sbom(
    workspace_dir: Path,
    project_name: str = "devops-cli",
    project_version: str = "0.2.6",
) -> dict[str, Any]:
    """Generate CycloneDX 1.5 JSON SBOM representation."""
    components = extract_workspace_components(workspace_dir)
    timestamp = datetime.now(UTC).isoformat()

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": [
                {
                    "vendor": "devops-cli",
                    "name": "devops scan sbom",
                    "version": project_version,
                }
            ],
            "component": {
                "name": project_name,
                "version": project_version,
                "type": "application",
                "purl": f"pkg:pypi/{project_name}@{project_version}",
            },
        },
        "components": [
            {
                "type": c.type,
                "name": c.name,
                "version": c.version,
                "purl": c.purl,
                "description": c.description,
            }
            for c in components
        ],
    }


def generate_spdx_sbom(
    workspace_dir: Path,
    project_name: str = "devops-cli",
    project_version: str = "0.2.6",
) -> dict[str, Any]:
    """Generate SPDX 2.3 JSON SBOM representation."""
    components = extract_workspace_components(workspace_dir)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    spdx_id_root = f"SPDXRef-Package-{project_name}"

    packages: list[dict[str, Any]] = [
        {
            "SPDXID": spdx_id_root,
            "name": project_name,
            "versionInfo": project_version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
        }
    ]

    relationships: list[dict[str, Any]] = []

    for i, c in enumerate(components, start=1):
        pkg_id = f"SPDXRef-Package-{c.name}-{i}"
        packages.append(
            {
                "SPDXID": pkg_id,
                "name": c.name,
                "versionInfo": c.version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": c.purl,
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": spdx_id_root,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": pkg_id,
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{project_name}-sbom",
        "documentNamespace": f"https://spdx.org/spdxdocs/{project_name}-{project_version}-{timestamp}",
        "creationInfo": {
            "created": timestamp,
            "creators": ["Tool: devops-cli scan sbom"],
        },
        "packages": packages,
        "relationships": relationships,
    }
