"""GitHub Pages configuration inspection, build lifecycle, and verification."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)


class GitHubPagesInfo(BaseModel):
    """GitHub Pages deployment status and configuration metadata."""

    status: str
    html_url: str
    build_type: str = "legacy"
    branch: str = "main"
    path: str = "/"
    cname: str | None = None
    custom_404: bool = False
    https_enforced: bool = True


class GitHubPagesBuildInfo(BaseModel):
    """GitHub Pages historical or recent build record."""

    model_config = ConfigDict(populate_by_name=True)

    status: str
    commit: str = ""
    duration_ms: int = Field(default=0, alias="duration")
    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""


def get_pages_status(repo: str) -> GitHubPagesInfo | None:
    """Fetch GitHub Pages site configuration and status via gh api."""
    cmd = [CONST_GH_CLI, "api", f"repos/{repo}/pages"]
    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode != 0 or not res.stdout.strip():
        return None

    try:
        data = json.loads(res.stdout)
        source = data.get("source", {})
        return GitHubPagesInfo(
            status=data.get("status", "unknown"),
            html_url=data.get("html_url", ""),
            build_type=data.get("build_type", "legacy"),
            branch=source.get("branch", "main"),
            path=source.get("path", "/"),
            cname=data.get("cname"),
            custom_404=data.get("custom_404", False),
            https_enforced=data.get("https_enforced", True),
        )
    except Exception as exc:
        logger.debug("Failed to parse pages status: %s", exc)
        return None


def _parse_single_build(item: dict[str, Any]) -> GitHubPagesBuildInfo:
    """Transform raw GitHub Pages build payload into a typed model."""
    err = item.get("error")
    err_msg = err.get("message") if isinstance(err, dict) else (str(err) if err else None)
    return GitHubPagesBuildInfo(
        status=item.get("status", "unknown"),
        commit=item.get("commit", ""),
        duration=item.get("duration", 0),
        error_message=err_msg,
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at", ""),
    )


def get_pages_builds(repo: str, limit: int = 5) -> list[GitHubPagesBuildInfo]:
    """Retrieve historical Pages build records for the repository."""
    cmd = [CONST_GH_CLI, "api", f"repos/{repo}/pages/builds?per_page={limit}"]
    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode != 0 or not res.stdout.strip():
        return []

    try:
        raw_list = json.loads(res.stdout)
        if not isinstance(raw_list, list):
            return []
        return [_parse_single_build(item) for item in raw_list if isinstance(item, dict)]
    except Exception as exc:
        logger.debug("Failed to parse pages builds: %s", exc)
        return []


def request_pages_build(repo: str) -> bool:
    """Request a new deployment build for GitHub Pages."""
    cmd = [CONST_GH_CLI, "api", "-X", "POST", f"repos/{repo}/pages/builds"]
    res = run_subprocess(cmd, check=False, quiet=True)
    return res.returncode == 0


def _check_jekyll_config(config_path: Path) -> tuple[bool, list[str]]:
    """Validate required Jekyll keys and configuration properties."""
    diagnostics: list[str] = []
    if not config_path.is_file():
        diagnostics.append("Missing _config.yml in root directory.")
        return False, diagnostics

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        diagnostics.append(f"Invalid YAML syntax in _config.yml: {exc}")
        return False, diagnostics

    required_keys = ["title", "url", "baseurl", "markdown"]
    missing = [k for k in required_keys if k not in data or not data[k]]
    if missing:
        diagnostics.append(f"Missing required Jekyll config keys: {', '.join(missing)}")
        return False, diagnostics

    diagnostics.append(
        f"✓ Jekyll configuration valid (title='{data.get('title')}', baseurl='{data.get('baseurl')}')"
    )
    return True, diagnostics


def _check_docs_directory(docs_dir: Path) -> tuple[bool, list[str]]:
    """Verify docs directory exists and contains markdown source files."""
    diagnostics: list[str] = []
    if not docs_dir.is_dir():
        diagnostics.append("Missing docs/ directory containing GitHub Pages content.")
        return False, diagnostics

    md_files = list(docs_dir.glob("*.md"))
    if not md_files:
        diagnostics.append("docs/ directory contains no markdown (.md) documents.")
        return False, diagnostics

    diagnostics.append(f"✓ Found {len(md_files)} markdown files in docs/")
    return True, diagnostics


def verify_pages_configuration(root_dir: Path = Path(".")) -> tuple[bool, list[str]]:
    """Verify local repository readiness for GitHub Pages publishing."""
    resolved = root_dir.resolve()
    config_ok, config_diags = _check_jekyll_config(resolved / "_config.yml")
    docs_ok, docs_diags = _check_docs_directory(resolved / "docs")

    all_ok = config_ok and docs_ok
    return all_ok, config_diags + docs_diags
