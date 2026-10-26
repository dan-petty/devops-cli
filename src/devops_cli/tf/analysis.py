"""In-process Terraform/OpenTofu HCL AST analysis and state introspection.

Read-only IaC queries — resource graphs, blast radius, and configuration drift — are
answered by parsing HCL and the state file directly, without paying `tofu`/`terraform`
binary startup cost or requiring an initialized working directory.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections import deque
from collections.abc import Sequence
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
    CONST_TF_BACKEND_CACHE_KEY,
    CONST_TF_STATE_FILE_NAMES,
)
from devops_cli.core.process import run_subprocess
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
            provider = ""
            if isinstance(body, dict) and "provider" in body:
                provider = _unquote(str(body["provider"]))
                if provider.startswith("${") and provider.endswith("}"):
                    provider = provider[2:-1].strip()
            resources.append(
                IaCResource(
                    address=f"{prefix}{resource_type}.{name}",
                    block_type=block_type,
                    resource_type=resource_type,
                    name=name,
                    source_file=source_file,
                    provider=provider,
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


def is_directory_initialized(directory: Path) -> bool:
    """Report whether a configuration directory has been initialized with OpenTofu or Terraform."""
    return (directory / ".terraform").is_dir()


def _is_backend_configuration_cache(path: Path) -> bool:
    """Whether a state file is the backend configuration `init` caches, not resource state."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    return isinstance(payload, dict) and CONST_TF_BACKEND_CACHE_KEY in payload


def holds_local_resource_state(directory: Path) -> bool:
    """Report whether a configuration directory keeps resource state on local disk.

    With a configured backend, `init` writes `.terraform/terraform.tfstate` to cache that
    backend's settings; the resources live in the backend, so that file does not count. A
    state file that cannot be read counts, since it may still hold resources.
    """
    return any(
        path.is_file() and not _is_backend_configuration_cache(path)
        for path in (directory / name for name in CONST_TF_STATE_FILE_NAMES)
    )


def _extract_show_resources(
    module_node: dict[str, Any], module_prefix: str = ""
) -> list[IaCStateResource]:
    """Recursively collect managed and data resource instances from show module nodes."""
    resources: list[IaCStateResource] = []
    current_module = str(module_node.get("address", "") or module_prefix)

    for item in module_node.get("resources", []):
        if not isinstance(item, dict):
            continue
        address = str(item.get("address", ""))
        mode = str(item.get("mode", "managed"))
        resource_type = str(item.get("type", ""))
        name = str(item.get("name", ""))
        provider = str(item.get("provider_name", "") or item.get("provider", ""))
        resources.append(
            IaCStateResource(
                address=address,
                mode=mode,
                resource_type=resource_type,
                name=name,
                provider=provider,
                module=current_module,
                instance_count=1,
            )
        )

    for child in module_node.get("child_modules", []):
        if isinstance(child, dict):
            child_address = str(child.get("address", ""))
            resources.extend(_extract_show_resources(child, child_address))

    return resources


def parse_show_state(payload: dict[str, Any] | str) -> IaCState:
    """Project `tofu show -json` output into typed state models."""
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return IaCState()
    else:
        data = payload

    if not isinstance(data, dict):
        return IaCState()

    values = data.get("values")
    root_module = values.get("root_module") if isinstance(values, dict) else None
    resources = _extract_show_resources(root_module) if isinstance(root_module, dict) else []
    outputs = values.get("outputs") if isinstance(values, dict) else {}

    format_version = str(data.get("format_version", "1")).split(".")[0]
    version = int(format_version) if format_version.isdigit() else 1

    return IaCState(
        version=version,
        terraform_version=str(data.get("terraform_version", "") or ""),
        serial=int(data.get("serial", 0) or 0),
        lineage=str(data.get("lineage", "") or ""),
        resources=resources,
        outputs=outputs if isinstance(outputs, dict) else {},
    )


def read_state(directory: Path, binary: str | None = None) -> IaCState | None:
    """Read and project state by executing `tofu show -json` in the target directory."""
    if not is_directory_initialized(directory):
        return None

    tf_binary = binary or "tofu"
    cmd = [tf_binary, "show", "-json"]
    try:
        res = run_subprocess(cmd, cwd=directory, capture_output=True, check=False)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("Failed running %s in %s: %s", cmd, directory, exc)
        return None

    if res.returncode != 0:
        logger.debug("%s exited %s: %s", cmd, res.returncode, res.stderr)
        return None

    stdout = (res.stdout or "").strip()
    if not stdout:
        return None

    return parse_show_state(stdout)


def _extract_drift_addr(item: dict[str, Any]) -> str:
    """Extract address string from a drift event payload."""
    change = item.get("change")
    if isinstance(change, dict):
        resource = change.get("resource")
        if isinstance(resource, dict):
            addr = resource.get("addr") or resource.get("resource")
            if addr:
                return str(addr)
    return str(item.get("address", "") or "")


def _extract_drift_from_dict(data: dict[str, Any]) -> list[str]:
    """Collect addresses from a static plan JSON structure."""
    drifted: list[str] = []
    for entry in data.get("resource_drift", []):
        if not isinstance(entry, dict):
            continue
        addr = str(entry.get("address", "") or _extract_drift_addr(entry))
        if addr:
            drifted.append(addr)
    return sorted(set(drifted))


def _drift_from_record(item: Any) -> list[str]:
    """Extract drifted addresses from a decoded JSON record."""
    if not isinstance(item, dict):
        return []
    if "resource_drift" in item:
        return _extract_drift_from_dict(item)
    if item.get("type") == "resource_drift":
        addr = _extract_drift_addr(item)
        return [addr] if addr else []
    return []


def parse_plan_drift(raw_output: str | dict[str, Any]) -> list[str]:
    """Extract drifted resource addresses from `tofu plan -refresh-only -json` output."""
    if isinstance(raw_output, dict):
        return _drift_from_record(raw_output)

    text = raw_output.strip()
    if not text:
        return []

    drifted: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        drifted.extend(_drift_from_record(item))

    return sorted(set(drifted))


def read_plan_drift(directory: Path, binary: str | None = None) -> list[str]:
    """Execute `tofu plan -refresh-only -json` and return drifted resource addresses."""
    if not is_directory_initialized(directory):
        return []

    tf_binary = binary or "tofu"
    cmd = [tf_binary, "plan", "-refresh-only", "-json"]
    try:
        res = run_subprocess(cmd, cwd=directory, capture_output=True, check=False)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("Failed running %s in %s: %s", cmd, directory, exc)
        return []

    return parse_plan_drift(res.stdout or "")


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


def detect_drift(
    config: IaCConfiguration,
    state: IaCState | None,
    *,
    drifted_addresses: Sequence[str] | None = None,
) -> IaCDriftReport:
    """Compare declared configuration against recorded state and live drift.

    State comes from `tofu show -json` and live attribute changes come from
    `tofu plan -refresh-only -json`. An uninitialized directory has state None.
    """
    declared = {
        resource.address
        for resource in config.resources
        if resource.block_type == CONST_HCL_BLOCK_RESOURCE
    }

    if state is None:
        return IaCDriftReport(
            directory=config.directory,
            declared_count=len(declared),
            state_count=0,
            missing_from_state=sorted(declared),
            orphaned_in_state=[],
            drifted=[],
            in_sync=[],
            drift_detected=bool(declared),
            state_present=False,
        )

    declared_modules = {module.address for module in config.modules}
    recorded_resources = [r for r in state.resources if r.mode == "managed"]
    recorded_addresses = {r.address for r in recorded_resources}
    drifted_set = set(drifted_addresses or ())

    missing = sorted(declared - recorded_addresses)
    orphaned: list[str] = []
    in_sync: list[str] = []
    drifted: list[str] = []

    for resource in recorded_resources:
        is_module_resource = bool(resource.module and resource.module in declared_modules) or any(
            resource.address.startswith(f"{m}.") for m in declared_modules
        )
        is_declared = resource.address in declared or is_module_resource

        if not is_declared:
            orphaned.append(resource.address)
        elif resource.address in drifted_set:
            drifted.append(resource.address)
        else:
            in_sync.append(resource.address)

    return IaCDriftReport(
        directory=config.directory,
        declared_count=len(declared),
        state_count=len(recorded_addresses),
        missing_from_state=missing,
        orphaned_in_state=sorted(orphaned),
        drifted=sorted(drifted),
        in_sync=sorted(in_sync),
        drift_detected=bool(missing or orphaned or drifted),
        state_present=True,
    )


def analyze_directory(
    directory: Path, binary: str | None = None
) -> tuple[IaCConfiguration, IaCState | None]:
    """Parse a configuration directory and load its state through tofu show -json."""
    return parse_hcl_directory(directory), read_state(directory, binary=binary)


__all__ = [
    "analyze_directory",
    "build_dependency_graph",
    "compute_blast_radius",
    "detect_drift",
    "extract_references",
    "holds_local_resource_state",
    "is_directory_initialized",
    "parse_hcl_directory",
    "parse_plan_drift",
    "parse_show_state",
    "read_plan_drift",
    "read_state",
]
