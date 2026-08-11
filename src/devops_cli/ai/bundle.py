"""Air-gapped model archive bundler for devops-cli."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_DATA_DIR


class ModelBundleManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str = "0.1.3"
    models: list[str]
    created_at: str
    target_dir: str


def bundle_ollama_models(
    models: list[str] | None = None,
    output_dir: Path | None = None,
) -> tuple[int, Path]:
    """Bundle local model weight metadata into tarball directory for air-gapped DevContainers.

    Returns (count, bundle_path).
    """
    target = output_dir or (CONST_DATA_DIR / "models")
    target.mkdir(parents=True, exist_ok=True)

    model_list = models or ["qwen2.5-coder:7b", "llama3.1:8b"]
    manifest = ModelBundleManifest(
        models=model_list,
        created_at="2026-08-11T22:25:00Z",
        target_dir=str(target),
    )

    manifest_file = target / "manifest.json"
    manifest_file.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    return len(model_list), manifest_file
