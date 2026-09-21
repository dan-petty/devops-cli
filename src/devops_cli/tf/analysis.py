"""In-process Terraform/OpenTofu HCL AST analysis and state introspection.

Read-only IaC queries — resource graphs, blast radius, and configuration drift — are
answered by parsing HCL and the state file directly, without paying `tofu`/`terraform`
binary startup cost or requiring an initialized working directory.
"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_HCL_BLOCK_DATA,
    CONST_HCL_BLOCK_MARKER,
    CONST_HCL_BLOCK_MODULE,
    CONST_HCL_BLOCK_OUTPUT,
    CONST_HCL_BLOCK_RESOURCE,
    CONST_HCL_BLOCK_VARIABLE,
    CONST_HCL_FILE_EXTENSIONS,
    CONST_HCL_NON_RESOURCE_NAMESPACES,
    CONST_TF_STATE_FILE_NAMES,
)
from devops_cli.models.tf import (
    IaCBlastRadius,
    IaCConfiguration,
    IaCDriftReport,
    IaCModule,
    IaCResource,
    IaCState,
    IaCStateResource,
)

logger = logging.getLogger(__name__)

# `${...}` interpolations and bare traversals such as `aws_vpc.main.id`.
_INTERPOLATION_REGEX = re.compile(r"\$\{([^}]*)\}")
_TRAVERSAL_REGEX = re.compile(r"\b([A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)+)\b")


# =============================================================================
# HCL Normalisation
# =============================================================================


def _unquote(value: str) -> str:
    """Strip the literal quotes `python-hcl2` preserves around strings and block labels."""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _strip_block_markers(value: Any) -> Any:
    """Recursively drop the `__is_block__` marker and unquote string literals."""
    if isinstance(value, dict):
        return {
            _unquote(str(k)): _strip_block_markers(v)
            for k, v in value.items()
            if k != CONST_HCL_BLOCK_MARKER
        }
    if isinstance(value, list):
        return [_strip_block_markers(item) for item in value]
    if isinstance(value, str):
        return _unquote(value)
    return value


def _reference_root(traversal: str) -> str | None:
    """Reduce a traversal such as `aws_vpc.main.id` to the address it depends on.

    Returns ``None`` for traversals that do not address another declaration, such as
    attribute access on a local value or an each/count expression.
    """
    parts = [p for p in traversal.split(".") if p]
    if len(parts) < 2:
        return None

    head = parts[0]
    if head in {CONST_HCL_BLOCK_MODULE, CONST_HCL_BLOCK_DATA}:
        # module.db / data.aws_ami.ubuntu
        needed = 2 if head == CONST_HCL_BLOCK_MODULE else 3
        return ".".join(parts[:needed]) if len(parts) >= needed else None
    if head in CONST_HCL_NON_RESOURCE_NAMESPACES:
        return None
    return f"{parts[0]}.{parts[1]}"


def extract_references(value: Any) -> set[str]:
    """Collect every declaration address referenced within an attribute value tree."""
    references: set[str] = set()

    if isinstance(value, dict):
        for nested in value.values():
            references |= extract_references(nested)
        return references
    if isinstance(value, list):
        for item in value:
            references |= extract_references(item)
        return references
    if not isinstance(value, str):
        return references

    for expression in _INTERPOLATION_REGEX.findall(value):
        for traversal in _TRAVERSAL_REGEX.findall(expression):
            address = _reference_root(traversal)
            if address:
                references.add(address)
    return references


# =============================================================================
# Configuration Parsing
# =============================================================================


def _iter_labelled_blocks(entries: Any) -> Any:
    """Yield `(label, body)` pairs from a `python-hcl2` labelled block list."""
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        for label, body in entry.items():
            yield _unquote(str(label)), body


def _parse_resource_blocks(
    document: dict[str, Any], block_type: str, source_file: str
) -> list[IaCResource]:
    """Project `resource` or `data` blocks into typed resource declarations."""
    resources: list[IaCResource] = []
    prefix = f"{CONST_HCL_BLOCK_DATA}." if block_type == CONST_HCL_BLOCK_DATA else ""

    for resource_type, named in _iter_labelled_blocks(document.get(block_type)):
        for name, body in _iter_labelled_blocks([named]) if isinstance(named, dict) else []:
            attributes = _strip_block_markers(body) if isinstance(body, dict) else {}
            resources.append(
                IaCResource(
                    address=f"{prefix}{resource_type}.{name}",
                    block_type=block_type,
                    resource_type=resource_type,
                    name=name,
                    source_file=source_file,
                    provider=resource_type.split("_", 1)[0],
                    references=sorted(extract_references(body)),
                    attributes=attributes if isinstance(attributes, dict) else {},
                )
            )
    return resources


def _parse_module_blocks(document: dict[str, Any], source_file: str) -> list[IaCModule]:
    """Project `module` blocks into typed module invocations."""
    return [
        IaCModule(
            address=f"{CONST_HCL_BLOCK_MODULE}.{name}",
            name=name,
            source=str(_strip_block_markers(body.get("source", "")))
            if isinstance(body, dict)
            else "",
            source_file=source_file,
            references=sorted(extract_references(body)),
        )
        for name, body in _iter_labelled_blocks(document.get(CONST_HCL_BLOCK_MODULE))
    ]


def _hcl_files(directory: Path) -> list[Path]:
    """List HCL configuration files in a directory, excluding module subdirectories."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix in CONST_HCL_FILE_EXTENSIONS
    )


def parse_hcl_directory(directory: Path) -> IaCConfiguration:
    """Parse every HCL file in a directory into a typed configuration projection.

    A file that fails to parse is recorded rather than aborting the scan, so a single
    malformed manifest cannot hide the rest of the configuration.
    """
    import hcl2

    config = IaCConfiguration(directory=str(directory))
    if not directory.is_dir():
        return config

    for path in _hcl_files(directory):
        try:
            with path.open(encoding="utf-8") as handle:
                document = hcl2.load(handle)
        except Exception as exc:
            config.failed_files[path.name] = str(exc)[:256]
            logger.debug("Failed parsing HCL file %s: %s", path, exc)
            continue

        if not isinstance(document, dict):
            config.failed_files[path.name] = "Document root is not an HCL body"
            continue

        config.parsed_files.append(path.name)
        config.resources.extend(
            _parse_resource_blocks(document, CONST_HCL_BLOCK_RESOURCE, path.name)
        )
        config.resources.extend(_parse_resource_blocks(document, CONST_HCL_BLOCK_DATA, path.name))
        config.modules.extend(_parse_module_blocks(document, path.name))
        config.variables.extend(
            name for name, _ in _iter_labelled_blocks(document.get(CONST_HCL_BLOCK_VARIABLE))
        )
        config.outputs.extend(
            name for name, _ in _iter_labelled_blocks(document.get(CONST_HCL_BLOCK_OUTPUT))
        )

    return config


# =============================================================================
# State Introspection
# =============================================================================


def resolve_state_file(directory: Path) -> Path | None:
    """Locate the state file backing a configuration directory, if one exists."""
    for candidate in CONST_TF_STATE_FILE_NAMES:
        path = directory / candidate
        if path.is_file():
            return path
    return None


def _project_state_resource(entry: dict[str, Any]) -> IaCStateResource:
    """Project one state resource record into a typed model."""
    module = str(entry.get("module", "") or "")
    resource_type = str(entry.get("type", ""))
    name = str(entry.get("name", ""))
    mode = str(entry.get("mode", "managed"))

    bare = f"{resource_type}.{name}"
    address = bare if mode == "managed" else f"{CONST_HCL_BLOCK_DATA}.{bare}"
    instances = entry.get("instances")

    return IaCStateResource(
        address=f"{module}.{address}" if module else address,
        mode=mode,
        resource_type=resource_type,
        name=name,
        provider=str(entry.get("provider", "")),
        module=module,
        instance_count=len(instances) if isinstance(instances, list) else 0,
    )


def load_state(directory: Path) -> IaCState | None:
    """Load and project a state file, returning ``None`` when none is present."""
    state_path = resolve_state_file(directory)
    if state_path is None:
        return None

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Failed reading state file %s: %s", state_path, exc)
        return None

    if not isinstance(payload, dict):
        return None

    raw_resources = payload.get("resources")
    outputs = payload.get("outputs")
    return IaCState(
        version=int(payload.get("version", 0) or 0),
        terraform_version=str(payload.get("terraform_version", "") or ""),
        serial=int(payload.get("serial", 0) or 0),
        lineage=str(payload.get("lineage", "") or ""),
        resources=[
            _project_state_resource(entry)
            for entry in (raw_resources if isinstance(raw_resources, list) else [])
            if isinstance(entry, dict)
        ],
        outputs=outputs if isinstance(outputs, dict) else {},
    )


# =============================================================================
# Dependency Graph, Blast Radius & Drift
# =============================================================================


def build_dependency_graph(config: IaCConfiguration) -> dict[str, list[str]]:
    """Build an address-to-dependencies mapping spanning resources and modules."""
    declared = {resource.address for resource in config.resources} | {
        module.address for module in config.modules
    }
    graph: dict[str, list[str]] = {}

    for resource in config.resources:
        graph[resource.address] = sorted(set(resource.references) & declared)
    for module in config.modules:
        graph[module.address] = sorted(set(module.references) & declared)
    return graph


def _invert_graph(graph: dict[str, list[str]]) -> dict[str, set[str]]:
    """Invert dependencies into dependents, so impact can be traversed forwards."""
    dependents: dict[str, set[str]] = {address: set() for address in graph}
    for address, dependencies in graph.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, set()).add(address)
    return dependents


def compute_blast_radius(graph: dict[str, list[str]], address: str) -> IaCBlastRadius:
    """Compute every address transitively impacted by changing one resource."""
    dependents = _invert_graph(graph)
    direct = sorted(dependents.get(address, set()))

    transitive: set[str] = set()
    queue = deque(direct)
    while queue:
        current = queue.popleft()
        if current in transitive or current == address:
            continue
        transitive.add(current)
        queue.extend(dependents.get(current, set()))

    return IaCBlastRadius(
        address=address,
        direct_dependents=direct,
        transitive_dependents=sorted(transitive),
        depends_on=sorted(graph.get(address, [])),
        impact_count=len(transitive),
    )


def detect_drift(config: IaCConfiguration, state: IaCState | None) -> IaCDriftReport:
    """Compare declared configuration against recorded state.

    This reports *structural* drift — resources declared but never applied, and resources
    still tracked in state after their declaration was removed. It does not compare
    attribute values against live infrastructure, which requires a provider refresh.
    """
    declared = {
        resource.address
        for resource in config.resources
        if resource.block_type == CONST_HCL_BLOCK_RESOURCE
    }
    recorded = {
        resource.address
        for resource in (state.resources if state else [])
        if resource.mode == "managed"
    }

    missing = sorted(declared - recorded)
    orphaned = sorted(recorded - declared)
    return IaCDriftReport(
        directory=config.directory,
        declared_count=len(declared),
        state_count=len(recorded),
        missing_from_state=missing,
        orphaned_in_state=orphaned,
        in_sync=sorted(declared & recorded),
        drift_detected=bool(missing or orphaned),
        state_present=state is not None,
    )


def analyze_directory(directory: Path) -> tuple[IaCConfiguration, IaCState | None]:
    """Parse a configuration directory and load its state in one pass."""
    return parse_hcl_directory(directory), load_state(directory)


__all__ = [
    "analyze_directory",
    "build_dependency_graph",
    "compute_blast_radius",
    "detect_drift",
    "extract_references",
    "load_state",
    "parse_hcl_directory",
    "resolve_state_file",
]
