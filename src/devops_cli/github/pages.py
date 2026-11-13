"""GitHub Pages site status and local verification of the docs site settings."""

from __future__ import annotations

import json
import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.dry_run.requests import PlannedRequest

from pydantic import BaseModel

from devops_cli.config.constants import CONST_DOCS_SITE_CONFIG_FILE, CONST_GH_CLI
from devops_cli.github.rate_limiter import run_gh

logger = logging.getLogger(__name__)


class GitHubPagesInfo(BaseModel):
    """GitHub Pages deployment status and configuration metadata."""

    status: str
    html_url: str
    # GitHub gives `source` also for a `workflow` build, but uses it only for a `legacy` build.
    build_type: str | None = None
    branch: str | None = None
    path: str | None = None
    cname: str | None = None
    custom_404: bool = False
    https_enforced: bool = True


def pages_status_args(repo: str) -> list[str]:
    """Arguments for fetching GitHub Pages site configuration and status via gh api."""
    return ["api", f"repos/{repo}/pages"]


def pages_status_requests(repo: str) -> list[PlannedRequest]:
    """Planned requests for fetching GitHub Pages site configuration."""
    from devops_cli.roadmap.request_plan import planned_gh

    return [planned_gh(pages_status_args(repo), f"repos/{repo}/pages")]


def get_pages_status(repo: str) -> GitHubPagesInfo | None:
    """Fetch GitHub Pages site configuration and status via gh api."""
    cmd = [CONST_GH_CLI, *pages_status_args(repo)]
    res = run_gh(cmd, check=False, quiet=True)
    if res.returncode != 0 or not res.stdout.strip():
        return None

    try:
        data = json.loads(res.stdout)
        source = data.get("source") or {}
        return GitHubPagesInfo(
            status=data.get("status", "unknown"),
            html_url=data.get("html_url", ""),
            build_type=data.get("build_type"),
            branch=source.get("branch"),
            path=source.get("path"),
            cname=data.get("cname"),
            custom_404=data.get("custom_404", False),
            https_enforced=data.get("https_enforced", True),
        )
    except Exception as exc:
        logger.debug("Failed to parse pages status: %s", exc)
        return None


# The settings that the site build needs: the name, the published URL and the repository whose
# files the pages link to.
_REQUIRED_SITE_SETTINGS = ("site_name", "site_url", "repo_url")


def _check_site_config(config_path: Path) -> tuple[bool, list[str]]:
    """Validate the TOML syntax and the required settings of `zensical.toml`.

    `devops docs site build` reads this file and no other: a setting in `mkdocs.yml` or in
    `docs/` has no effect on the site.
    """
    name = config_path.name
    if not config_path.is_file():
        return False, [f"Missing {name} at the repository root."]
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return False, [f"Invalid TOML syntax in {name}: {exc}"]
    project = data.get("project", data)
    missing = [key for key in _REQUIRED_SITE_SETTINGS if not project.get(key)]
    if missing:
        return False, [f"Missing required Zensical settings in {name}: {', '.join(missing)}"]
    return True, [
        f"✓ Zensical configuration valid (site_name='{project['site_name']}', "
        f"site_url='{project['site_url']}')"
    ]


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
    config_ok, config_diags = _check_site_config(resolved / CONST_DOCS_SITE_CONFIG_FILE)
    docs_ok, docs_diags = _check_docs_directory(resolved / "docs")

    all_ok = config_ok and docs_ok
    return all_ok, config_diags + docs_diags
