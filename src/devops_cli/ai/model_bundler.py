"""Air-gapped model archive bundler for devops-cli."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli import __version__
from devops_cli.config.constants import CONST_MODELS_DATA_DIR
from devops_cli.config.defaults import DEFAULT_BUNDLE_MODELS


class ModelBundleManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str = __version__
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
    target = output_dir or CONST_MODELS_DATA_DIR
    target.mkdir(parents=True, exist_ok=True)

    model_list = models or list(DEFAULT_BUNDLE_MODELS)
    manifest = ModelBundleManifest(
        version=__version__,
        models=model_list,
        created_at=datetime.now(UTC).isoformat(),
        target_dir=str(target),
    )

    manifest_file = target / "manifest.json"
    manifest_file.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    return len(model_list), manifest_file
