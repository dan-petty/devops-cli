"""Homelab GPU matrix inspection and service alias discovery commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.k8s.gpu_matrix import (
    VALID_BACKENDS,
    VALID_GPU_COUNTS,
    VALID_VRAM_SIZES,
    GpuProfile,
    get_service_aliases,
    list_gpu_profiles,
)
from devops_cli.output import print_error, print_section, print_table, render_table
from devops_cli.output.serialization import emit_serialized, normalize_format


def _format_profile_row(profile: GpuProfile) -> list[str]:
    """Format a single GpuProfile into table cell strings."""
    gpu_label = f"{profile.gpu_count}x {profile.vram_per_gpu_gib}GiB ({profile.total_vram_gib}GiB)"
    context_k = f"{profile.max_model_len // 1024}K"
    return [
        gpu_label,
        profile.backend,
        profile.model_id,
        profile.quantization,
        context_k,
        str(profile.tensor_parallel_size),
        profile.service_alias,
        profile.virtual_gateway_model,
    ]


def _build_profiles_table(profiles: list[GpuProfile]) -> Any:
    """Render Rich table of GPU profiles."""
    columns = [
        ("GPUs (Total VRAM)", "cyan"),
        ("Backend", "green"),
        ("Model ID", "bold"),
        ("Quant", "yellow"),
        ("Context", "magenta"),
        ("TP", "blue"),
        ("Service Alias", "white"),
        ("Virtual Model", "cyan"),
    ]
    rows = [_format_profile_row(p) for p in profiles]
    return render_table(
        title="Homelab GPU Configuration Matrix & Service Aliases",
        columns=columns,
        rows=rows,
    )


def _build_aliases_table(aliases: dict[str, dict[str, Any]]) -> Any:
    """Render Rich table of Kubernetes Provider-VRAM Service Aliases."""
    columns = [
        ("Service Alias", "cyan"),
        ("Service Name", "bold"),
        ("Virtual Model", "magenta"),
        ("Target Model", "green"),
        ("Ports", "yellow"),
        ("Description", "white"),
    ]
    rows = []
    for alias_key, info in aliases.items():
        ports_str = ", ".join(f"{b}:{p}" for b, p in info.get("ports", {}).items())
        target_model = str(info.get("default_model") or info.get("model_id", ""))
        rows.append(
            [
                alias_key,
                str(info.get("service_name", "")),
                str(info.get("virtual_model", "")),
                target_model,
                ports_str,
                str(info.get("description", "")),
            ]
        )
    return render_table(
        title="Kubernetes Provider-VRAM Service Aliases",
        columns=columns,
        rows=rows,
    )


def _validate_filter_options(
    gpus: int | None,
    vram: int | None,
    backend: str | None,
) -> None:
    """Validate CLI filter arguments against allowed matrix values."""
    if gpus is not None and gpus not in VALID_GPU_COUNTS:
        print_error(
            f"Invalid --gpus {gpus}. Allowed GPU counts: {list(VALID_GPU_COUNTS)}",
            prefix=False,
        )
        raise typer.Exit(1)
    if vram is not None and vram not in VALID_VRAM_SIZES:
        print_error(
            f"Invalid --vram {vram}. Allowed VRAM sizes: {list(VALID_VRAM_SIZES)} GiB",
            prefix=False,
        )
        raise typer.Exit(1)
    if backend is not None and backend.lower().strip() not in VALID_BACKENDS:
        print_error(
            f"Invalid --backend '{backend}'. Allowed backends: {list(VALID_BACKENDS)}",
            prefix=False,
        )
        raise typer.Exit(1)


def gpu_matrix_cmd(
    gpus: Annotated[
        int | None,
        typer.Option("--gpus", "-g", help="Filter by GPU count (1, 2, 3, 4)."),
    ] = None,
    vram: Annotated[
        int | None,
        typer.Option("--vram", "-v", help="Filter by VRAM per GPU in GiB (16, 24, 32)."),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option("--backend", "-b", help="Filter by inference backend (e.g. ollama)."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table, json, yaml."),
    ] = "table",
    aliases: Annotated[
        bool,
        typer.Option("--aliases", "-a", help="Include Kubernetes model service aliases mapping."),
    ] = False,
) -> None:
    """Query traditional homelab GPU matrix and model service alias mappings."""
    _validate_filter_options(gpus, vram, backend)

    profiles = list_gpu_profiles(
        gpu_count=gpus,
        vram_per_gpu_gib=vram,
        backend=backend,
    )
    service_aliases = get_service_aliases()

    resolved_fmt = normalize_format(output_format)
    if resolved_fmt != CONST_OUTPUT_FORMAT_TABLE:
        payload: Any = (
            {"profiles": [p.model_dump() for p in profiles], "service_aliases": service_aliases}
            if aliases
            else [p.model_dump() for p in profiles]
        )
        emit_serialized(payload, resolved_fmt)
        return

    print_section("Homelab GPU Inference Matrix")
    print_table(_build_profiles_table(profiles))

    if aliases:
        print_table(_build_aliases_table(service_aliases))


__all__ = [
    "gpu_matrix_cmd",
]
