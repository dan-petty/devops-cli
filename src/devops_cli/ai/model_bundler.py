"""Air-gapped model archive bundler for devops-cli."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli import __version__
from devops_cli.config.defaults import DEFAULT_BUNDLE_MODELS, DEFAULT_MODELS_DATA_DIR
from devops_cli.exceptions.ai import ModelBundleError


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
    if output_dir is not None:
        from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal

        target = validate_no_path_traversal(
            output_dir, error_cls=ModelBundleError, label="output directory"
        )
        if target.is_absolute():
            if is_forbidden_system_path(target):
                raise ModelBundleError(f"Output directory outside allowed workspace: {output_dir}")
            target = target.resolve()
        else:
            from devops_cli.core.paths import safe_resolve_subpath
            from devops_cli.core.repo import find_top_level_repo_root

            repo_root = find_top_level_repo_root()
            target = safe_resolve_subpath(repo_root, target, error_cls=ModelBundleError)
    else:
        target = DEFAULT_MODELS_DATA_DIR
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
