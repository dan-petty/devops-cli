"""Core CLI infrastructure: application creation and execution context."""

from __future__ import annotations

from typing import Any

from devops_cli.core.cli import new_typer, repo_label

_CORE_EXPORTS: dict[str, tuple[str, str]] = {
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "find_repo_root": ("devops_cli.core.repo", "find_repo_root"),
    "find_top_level_repo_root": ("devops_cli.core.repo", "find_top_level_repo_root"),
    "is_ignored_by_git": ("devops_cli.core.repo", "is_ignored_by_git"),
    "list_repo_files": ("devops_cli.core.repo", "list_repo_files"),
    "read_gitignore_patterns": ("devops_cli.core.repo", "read_gitignore_patterns"),
    "is_non_public_ip": ("devops_cli.core.validation", "is_non_public_ip"),
    "validate_dir": ("devops_cli.core.validation", "validate_dir"),
    "validate_file": ("devops_cli.core.validation", "validate_file"),
    "validate_k8s_name": ("devops_cli.core.validation", "validate_k8s_name"),
    "validate_path": ("devops_cli.core.validation", "validate_path"),
    "validate_safe_key_path": ("devops_cli.core.validation", "validate_safe_key_path"),
    "validate_service_url": ("devops_cli.core.validation", "validate_service_url"),
    "validate_url": ("devops_cli.core.validation", "validate_url"),
    "validate_version_str": ("devops_cli.core.validation", "validate_version_str"),
    "format_command": ("devops_cli.dry_run", "format_command"),
    "is_dry_run": ("devops_cli.dry_run", "is_dry_run"),
    "set_dry_run": ("devops_cli.dry_run", "set_dry_run"),
}


def __getattr__(name: str) -> Any:
    if name in _CORE_EXPORTS:
        mod_name, attr_name = _CORE_EXPORTS[name]
        from importlib import import_module

        mod = import_module(mod_name)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "find_repo_root",
    "find_top_level_repo_root",
    "format_command",
    "is_dry_run",
    "is_ignored_by_git",
    "is_non_public_ip",
    "list_repo_files",
    "new_typer",
    "read_gitignore_patterns",
    "repo_label",
    "run_subprocess",
    "set_dry_run",
    "validate_dir",
    "validate_file",
    "validate_k8s_name",
    "validate_path",
    "validate_safe_key_path",
    "validate_service_url",
    "validate_url",
    "validate_version_str",
]
