"""AI Bill of Materials (AIBOM) generator and model curation security analyzer."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.telemetry.tracer import trace_span


class ModelLicenseType(StrEnum):
    """Categorization of open and commercial model licensing models."""

    PERMISSIVE_OPEN_WEIGHT = "Permissive Open Weight"
    OPEN_SOURCE = "True Open Source"
    OPEN_WEIGHT_CAPPED = "Open Weight (Commercial Cap)"
    RAIL = "Responsible AI License (RAIL)"
    PROPRIETARY = "Proprietary Commercial"
    UNKNOWN = "Unknown / Custom"


class ModelHardwareEstimate(BaseModel):
    """Estimated hardware footprints for model serving and inference."""

    model_config = ConfigDict(frozen=True)

    parameters_billion: float
    quantization_bits: int = 16
    context_window: int = 8192
    is_moe: bool = False
    active_experts: int = 1
    total_experts: int = 1
    estimated_disk_gb: float
    estimated_vram_gb: float
    estimated_ram_gb: float


class AIBOMComponent(BaseModel):
    """Component descriptor for an AI model within an AIBOM manifest."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str = "latest"
    publisher: str = "local"
    purl: str = ""
    parameters_billion: float = 0.0
    license_type: ModelLicenseType = ModelLicenseType.UNKNOWN
    license_id: str = "NOASSERTION"
    trust_remote_code: bool = False
    has_safe_weights: bool = True
    file_digests: dict[str, str] = Field(default_factory=dict)
    hardware_estimate: ModelHardwareEstimate | None = None


def estimate_hardware_requirements(
    parameters_billion: float,
    quantization_bits: int = 16,
    context_window: int = 8192,
    *,
    is_moe: bool = False,
    active_experts: int = 1,
    total_experts: int = 1,
) -> ModelHardwareEstimate:
    """Calculate serving hardware estimates dynamically based on parameters and quantization."""
    if parameters_billion <= 0:
        return ModelHardwareEstimate(
            parameters_billion=0.0,
            quantization_bits=quantization_bits,
            context_window=context_window,
            is_moe=is_moe,
            active_experts=active_experts,
            total_experts=total_experts,
            estimated_disk_gb=0.0,
            estimated_vram_gb=0.0,
            estimated_ram_gb=0.0,
        )

    # Base weight memory: 1 billion params at 16-bit = 2.0 GB (at 8-bit = 1.0 GB, at 4-bit = 0.5 GB)
    bytes_per_param = quantization_bits / 8.0
    raw_weights_gb = round(parameters_billion * bytes_per_param * 1.05, 2)

    # KV Cache and activation overhead scaling with context window
    kv_overhead_gb = round((context_window / 8192.0) * (parameters_billion * 0.15), 2)

    if is_moe and total_experts > 1:
        # MoE VRAM serving requires all weights in VRAM, but active computation VRAM scales with active experts
        effective_active_ratio = min(1.0, (active_experts / float(total_experts)) + 0.2)
        vram_gb = round((raw_weights_gb * effective_active_ratio) + kv_overhead_gb + 1.0, 2)
    else:
        vram_gb = round(raw_weights_gb + kv_overhead_gb + 0.8, 2)

    ram_gb = round(raw_weights_gb * 1.35 + 2.0, 2)

    return ModelHardwareEstimate(
        parameters_billion=parameters_billion,
        quantization_bits=quantization_bits,
        context_window=context_window,
        is_moe=is_moe,
        active_experts=active_experts,
        total_experts=total_experts,
        estimated_disk_gb=raw_weights_gb,
        estimated_vram_gb=vram_gb,
        estimated_ram_gb=ram_gb,
    )


def detect_trust_remote_code(target_dir: Path) -> bool:
    """Detect whether a model directory contains or triggers trust_remote_code execution."""
    if not target_dir.exists():
        return False

    # 1. Inspect config.json for auto_map / custom code declarations
    config_file = target_dir / "config.json"
    if config_file.is_file():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if data.get("auto_map") or data.get("custom_pipelines"):
                    return True
                if "trust_remote_code" in data and bool(data["trust_remote_code"]):
                    return True
        except Exception:
            pass

    # 2. Inspect Python files for trust_remote_code keyword in AST or modeling definitions
    resolved_target = target_dir.resolve()
    for py_file in target_dir.glob("*.py"):
        try:
            resolved_py = py_file.resolve()
            if not resolved_py.is_relative_to(resolved_target):
                continue
            tree = ast.parse(resolved_py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "trust_remote_code":
                    if isinstance(node.value, ast.Constant) and bool(node.value.value):
                        return True
        except Exception:
            continue

    return False


def _classify_license(license_str: str) -> tuple[ModelLicenseType, str]:
    """Classify model license string into standard governance categories."""
    norm = (license_str or "").strip().lower()
    if not norm:
        return ModelLicenseType.UNKNOWN, "NOASSERTION"

    if any(k in norm for k in ("apache-2.0", "apache 2.0", "mit", "bsd")):
        return ModelLicenseType.PERMISSIVE_OPEN_WEIGHT, license_str
    if any(k in norm for k in ("llama-3", "llama 3", "falcon")):
        return ModelLicenseType.OPEN_WEIGHT_CAPPED, license_str
    if any(k in norm for k in ("rail", "bloom", "gemma")):
        return ModelLicenseType.RAIL, license_str
    if any(k in norm for k in ("gpl", "agpl", "lgpl", "open-source")):
        return ModelLicenseType.OPEN_SOURCE, license_str
    if any(k in norm for k in ("commercial", "proprietary")):
        return ModelLicenseType.PROPRIETARY, license_str

    return ModelLicenseType.UNKNOWN, license_str


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file concisely."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


@trace_span("extract_aibom_components")
def extract_aibom_components(workspace_dir: Path) -> list[AIBOMComponent]:
    """Extract AI model components and metadata from model manifests and configuration files."""
    components: list[AIBOMComponent] = []
    seen_names: set[str] = set()
    seen_dirs: set[Path] = set()

    # Look for model configuration manifests: config.json, model_card.json, Modelfile
    manifest_candidates: list[Path] = [
        *workspace_dir.glob("**/config.json"),
        *workspace_dir.glob("**/Modelfile"),
        *workspace_dir.glob("**/model_card.json"),
    ]

    resolved_workspace = workspace_dir.resolve()
    for candidate in manifest_candidates:
        try:
            resolved_cand = candidate.resolve()
            if not resolved_cand.is_relative_to(resolved_workspace):
                continue
        except ValueError, OSError:
            continue

        parent_dir = candidate.parent
        resolved_parent = parent_dir.resolve()
        name = parent_dir.name
        if resolved_parent in seen_dirs or name in seen_names or name.startswith("."):
            continue
        seen_dirs.add(resolved_parent)

        params = 0.0
        license_str = "NOASSERTION"
        publisher = "local"
        has_safetensors = any(parent_dir.glob("*.safetensors"))
        trust_remote = detect_trust_remote_code(parent_dir)

        # Parse config.json if present
        cfg_file = parent_dir / "config.json"
        if cfg_file.is_file():
            try:
                cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
                if isinstance(cfg_data, dict):
                    # Estimate parameters from architecture configuration
                    hidden = cfg_data.get("hidden_size", 0)
                    layers = cfg_data.get("num_hidden_layers", 0)
                    if hidden > 0 and layers > 0:
                        params = round((hidden * hidden * layers * 12) / 1_000_000_000.0, 1)
                    license_str = str(cfg_data.get("license", "NOASSERTION"))
                    publisher = str(cfg_data.get("_name_or_path", "local")).split("/")[0]
            except Exception:
                pass

        # Check Modelfile for FROM declaration
        modelfile = parent_dir / "Modelfile"
        if modelfile.is_file() and params == 0.0:
            try:
                for line in modelfile.read_text(encoding="utf-8").splitlines():
                    if line.strip().upper().startswith("FROM "):
                        model_tag = line.strip().split(maxsplit=1)[1]
                        name = model_tag
                        m = re.search(r":?(\d+)b", model_tag.lower())
                        if m:
                            params = float(m.group(1))
            except Exception:
                pass

        lic_type, lic_id = _classify_license(license_str)
        hw_est = estimate_hardware_requirements(params, quantization_bits=16)

        # Compute digests of key configuration files
        digests: dict[str, str] = {}
        for f in parent_dir.glob("*.json"):
            digest = _compute_sha256(f)
            if digest:
                digests[f.name] = digest

        components.append(
            AIBOMComponent(
                name=name,
                version="1.0.0",
                publisher=publisher,
                purl=f"pkg:ai/{publisher}/{name}@1.0.0",
                parameters_billion=params,
                license_type=lic_type,
                license_id=lic_id,
                trust_remote_code=trust_remote,
                has_safe_weights=has_safetensors,
                file_digests=digests,
                hardware_estimate=hw_est,
            )
        )
        seen_names.add(name)

    return components


@trace_span("generate_aibom")
def generate_aibom(
    workspace_dir: Path,
    project_name: str = "devops-cli-workspace",
    project_version: str = "0.2.7",
) -> dict[str, Any]:
    """Generate a CycloneDX 1.5 compliant AI Bill of Materials (AIBOM) JSON payload."""
    components = extract_aibom_components(workspace_dir)

    bom_components: list[dict[str, Any]] = []
    for comp in components:
        comp_dict: dict[str, Any] = {
            "type": "machine-learning-model",
            "name": comp.name,
            "version": comp.version,
            "purl": comp.purl,
            "licenses": [{"license": {"id": comp.license_id, "name": comp.license_type.value}}],
            "properties": [
                {"name": "devops:parameters_billion", "value": str(comp.parameters_billion)},
                {"name": "devops:trust_remote_code", "value": str(comp.trust_remote_code).lower()},
                {"name": "devops:safe_weights", "value": str(comp.has_safe_weights).lower()},
                {"name": "devops:license_category", "value": comp.license_type.value},
            ],
        }

        if comp.hardware_estimate and comp.parameters_billion > 0:
            comp_dict["properties"].extend(
                [
                    {
                        "name": "devops:estimated_vram_gb",
                        "value": str(comp.hardware_estimate.estimated_vram_gb),
                    },
                    {
                        "name": "devops:estimated_ram_gb",
                        "value": str(comp.hardware_estimate.estimated_ram_gb),
                    },
                    {
                        "name": "devops:estimated_disk_gb",
                        "value": str(comp.hardware_estimate.estimated_disk_gb),
                    },
                ]
            )

        if comp.file_digests:
            comp_dict["hashes"] = [
                {"alg": "SHA-256", "content": digest} for fname, digest in comp.file_digests.items()
            ]

        bom_components.append(comp_dict)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": {
                "type": "application",
                "name": project_name,
                "version": project_version,
            },
            "tools": [
                {"vendor": "DevOps CLI", "name": "devops-cli-aibom", "version": project_version}
            ],
        },
        "components": bom_components,
    }
