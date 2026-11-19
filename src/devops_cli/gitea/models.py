"""Pydantic models for Gitea API responses (#1090)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class GiteaModel(BaseModel):
    """Base class for Gitea models ignoring extra fields."""

    model_config = ConfigDict(extra="ignore")


class GiteaVersion(GiteaModel):
    """Gitea version response."""

    version: str


class GiteaUser(GiteaModel):
    """Gitea user response."""

    id: int
    login: str
    username: str | None = None
    email: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_username_or_login(cls, data: object) -> object:
        if isinstance(data, dict):
            if "login" not in data and "username" in data:
                data["login"] = data["username"]
            elif "username" not in data and "login" in data:
                data["username"] = data["login"]
        return data


class GiteaOrg(GiteaModel):
    """Gitea organization response."""

    id: int | None = None
    name: str = ""
    username: str = ""
    description: str | None = None
    visibility: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_name_or_username(cls, data: object) -> object:
        if isinstance(data, dict):
            if not data.get("name") and data.get("username"):
                data["name"] = data["username"]
            elif not data.get("username") and data.get("name"):
                data["username"] = data["name"]
        return data


class GiteaRepo(GiteaModel):
    """Gitea repository response."""

    id: int | None = None
    name: str
    full_name: str | None = None
    private: bool = True
    default_branch: str = "main"
    clone_url: str | None = None
    html_url: str | None = None


class GiteaBranchProtection(GiteaModel):
    """Gitea branch protection rule response."""

    id: int | None = None
    rule_name: str
    enable_push: bool = True
    enable_force_push: bool = False
    priority: int = 0
