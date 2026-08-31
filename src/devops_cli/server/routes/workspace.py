"""Workspace and configuration REST API endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from devops_cli.config.settings import Settings
from devops_cli.core.repo import find_top_level_repo_root

router = APIRouter(prefix="/api/v1", tags=["Workspaces & Config"])


class RepositoryInfo(BaseModel):
    """Repository metadata."""

    name: str = Field(..., description="Repository folder name or relative path")
    path: str = Field(..., description="Absolute path on disk")
    has_git: bool = Field(..., description="Whether .git directory exists")
    has_devcontainer: bool = Field(..., description="Whether .devcontainer exists")
    has_pyproject: bool = Field(..., description="Whether pyproject.toml exists")


class WorkspacesResponse(BaseModel):
    """Workspaces listing response."""

    workspace_root: str = Field(..., description="Workspace root directory")
    repositories: list[RepositoryInfo] = Field(
        default_factory=list,
        description="Child repositories",
    )


class ConfigResponse(BaseModel):
    """Sanitized configuration response schema."""

    status: str = "ok"
    config: dict[str, Any] = Field(default_factory=dict)


def _inspect_repo_metadata(path: Path, name: str) -> RepositoryInfo:
    """Inspect and format metadata for a repository directory."""
    return RepositoryInfo(
        name=name,
        path=str(path.resolve()),
        has_git=(path / ".git").exists(),
        has_devcontainer=(path / ".devcontainer").is_dir(),
        has_pyproject=(path / "pyproject.toml").is_file(),
    )


def _scan_owner_directory(owner_dir: Path) -> list[RepositoryInfo]:
    """Scan subdirectories or single repository under an owner folder."""
    if (owner_dir / ".git").exists() or (owner_dir / "pyproject.toml").is_file():
        return [_inspect_repo_metadata(owner_dir, owner_dir.name)]

    repos: list[RepositoryInfo] = []
    for repo_dir in owner_dir.iterdir():
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue
        if (repo_dir / ".git").exists() or (repo_dir / "pyproject.toml").is_file():
            repos.append(_inspect_repo_metadata(repo_dir, f"{owner_dir.name}/{repo_dir.name}"))
    return repos


def _discover_workspace_repositories(repos_dir: Path) -> list[RepositoryInfo]:
    """Discover all repositories under workspace repos directory."""
    if not repos_dir.is_dir():
        return []
    repos: list[RepositoryInfo] = []
    for owner_dir in repos_dir.iterdir():
        if not owner_dir.is_dir() or owner_dir.name.startswith("."):
            continue
        repos.extend(_scan_owner_directory(owner_dir))
    return repos


@router.get("/workspaces", response_model=WorkspacesResponse, summary="List workspace repositories")
async def list_workspaces() -> WorkspacesResponse:
    """Discover repositories and devcontainer configurations in the current workspace."""
    root = find_top_level_repo_root()
    return WorkspacesResponse(
        workspace_root=str(root.resolve()),
        repositories=_discover_workspace_repositories(root / "repos"),
    )


@router.get("/config", response_model=ConfigResponse, summary="Get sanitized configuration")
async def get_configuration() -> ConfigResponse:
    """Retrieve active non-secret configuration parameters."""
    settings = Settings()
    config_dict = settings.model_dump(mode="json")

    # Sanitize any sensitive tokens/keys
    if "github" in config_dict and "token" in config_dict["github"]:
        gh_tok = config_dict["github"]["token"]
        config_dict["github"]["token"] = "***REDACTED***" if gh_tok else None

    return ConfigResponse(
        status="ok",
        config=config_dict,
    )
