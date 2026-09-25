"""Air-gapped model archive bundler for devops-cli."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli import __version__
from devops_cli.config.defaults import DEFAULT_BUNDLE_MODELS
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import (
    is_forbidden_system_path,
    safe_resolve_subpath,
    validate_no_path_traversal,
)
from devops_cli.core.repo import main_worktree_root, resolve_data_path
from devops_cli.exceptions.ai import ModelBundleError


class ModelBundleManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str = __version__
    models: list[str]
    created_at: str
    target_dir: str


def _bundle_directory(output_dir: Path | None) -> Path:
    """The directory a bundle is written to: `output_dir`, else the configured models directory.

    `output_dir` overrides `data.models_dir`, so a relative one is a data path like it: the same
    value names the same directory under the main worktree, shared by every worktree.
    """
    if output_dir is None:
        return resolve_data_path(load_settings().data.models_dir)
    target = validate_no_path_traversal(
        output_dir, error_cls=ModelBundleError, label="output directory"
    )
    if not target.is_absolute():
        return safe_resolve_subpath(main_worktree_root(), target, error_cls=ModelBundleError)
    if is_forbidden_system_path(target):
        raise ModelBundleError(f"Output directory outside allowed workspace: {output_dir}")
    return target.resolve()


def bundle_ollama_models(
    models: list[str] | None = None,
    output_dir: Path | None = None,
) -> tuple[int, Path]:
    """Bundle local model weight metadata into tarball directory for air-gapped DevContainers.

    Returns (count, bundle_path).
    """
    target = _bundle_directory(output_dir)
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
