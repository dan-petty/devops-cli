"""Workspace and configuration REST API endpoints."""

from __future__ import annotations

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


@router.get("/workspaces", response_model=WorkspacesResponse, summary="List workspace repositories")
async def list_workspaces() -> dict[str, Any]:
    """Discover repositories and devcontainer configurations in the current workspace."""
    root = find_top_level_repo_root()
    repos_dir = root / "repos"
    repositories: list[dict[str, Any]] = []

    if repos_dir.is_dir():
        for owner_dir in repos_dir.iterdir():
            if not owner_dir.is_dir() or owner_dir.name.startswith("."):
                continue
            if (owner_dir / ".git").exists() or (owner_dir / "pyproject.toml").is_file():
                repositories.append(
                    {
                        "name": owner_dir.name,
                        "path": str(owner_dir.resolve()),
                        "has_git": (owner_dir / ".git").exists(),
                        "has_devcontainer": (owner_dir / ".devcontainer").is_dir(),
                        "has_pyproject": (owner_dir / "pyproject.toml").is_file(),
                    }
                )
            else:
                for repo_dir in owner_dir.iterdir():
                    if not repo_dir.is_dir() or repo_dir.name.startswith("."):
                        continue
                    if (repo_dir / ".git").exists() or (repo_dir / "pyproject.toml").is_file():
                        repositories.append(
                            {
                                "name": f"{owner_dir.name}/{repo_dir.name}",
                                "path": str(repo_dir.resolve()),
                                "has_git": (repo_dir / ".git").exists(),
                                "has_devcontainer": (repo_dir / ".devcontainer").is_dir(),
                                "has_pyproject": (repo_dir / "pyproject.toml").is_file(),
                            }
                        )

    return {
        "workspace_root": str(root.resolve()),
        "repositories": repositories,
    }


@router.get("/config", summary="Get sanitized configuration")
async def get_configuration() -> dict[str, Any]:
    """Retrieve active non-secret configuration parameters."""
    settings = Settings()
    config_dict = settings.model_dump(mode="json")

    # Sanitize any sensitive tokens/keys
    if "github" in config_dict and "token" in config_dict["github"]:
        gh_tok = config_dict["github"]["token"]
        config_dict["github"]["token"] = "***REDACTED***" if gh_tok else None

    return {
        "status": "ok",
        "config": config_dict,
    }
