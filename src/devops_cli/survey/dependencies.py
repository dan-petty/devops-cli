"""Upstream dependency maturity inspection and mechanical signals collection."""

from __future__ import annotations

import importlib.metadata
import logging
import re
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
from packaging.requirements import Requirement

from devops_cli.config.constants import CONST_PYPROJECT_FILENAME
from devops_cli.core.repo import find_repo_root
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.survey.models import DependencyMaturity, DependencyPin

logger = logging.getLogger(__name__)

_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#?]+)", re.IGNORECASE
)


def read_pinned_dependencies(pyproject_path: Path | None = None) -> list[DependencyPin]:
    """Read pinned runtime dependencies from pyproject.toml."""
    path = pyproject_path or (find_repo_root() / CONST_PYPROJECT_FILENAME)
    if not path.is_file():
        return []
    with path.open("rb") as f:
        data = tomllib.load(f)
    raw_dependencies = data.get("project", {}).get("dependencies", [])
    pins: list[DependencyPin] = []
    for raw in raw_dependencies:
        req = Requirement(raw)
        version = ""
        for spec in req.specifier:
            if spec.operator in ("==", "==="):
                version = spec.version
                break
            version = spec.version
        pins.append(DependencyPin(name=req.name, version=version))
    return sorted(pins, key=lambda p: p.name.lower())


def _read_lockfile_packages() -> dict[str, dict[str, Any]]:
    """Read locked package metadata from uv.lock if available."""
    lock_path = find_repo_root() / "uv.lock"
    if not lock_path.is_file():
        return {}
    try:
        with lock_path.open("rb") as f:
            data = tomllib.load(f)
        packages = data.get("package", [])
        return {p["name"].lower(): p for p in packages if isinstance(p, dict) and "name" in p}
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.debug("Failed reading uv.lock: %s", exc)
        return {}


def compute_release_cadence(release_timestamps: list[str]) -> str:
    """Calculate the release cadence from release upload timestamps."""
    if not release_timestamps:
        return "1.0 releases/year"
    if len(release_timestamps) == 1:
        return "1 release"

    dates: list[datetime] = []
    for ts in release_timestamps:
        try:
            clean_ts = ts.replace("Z", "+00:00")
            dates.append(datetime.fromisoformat(clean_ts))
        except ValueError:
            continue

    if len(dates) < 2:
        return f"{len(dates)} release"

    dates.sort()
    span_days = max((dates[-1] - dates[0]).days, 1)
    years = span_days / 365.25
    rate = len(dates) / max(years, 0.1)

    if years >= 1.0:
        return f"{rate:.1f} releases/year"
    avg_days = span_days / max(len(dates) - 1, 1)
    return f"{avg_days:.0f} days/release"


def _score_commit_recency(days: int | None) -> float:
    if days is None:
        return 50.0
    thresholds = (
        (30, 100.0),
        (90, 90.0),
        (180, 75.0),
        (365, 50.0),
        (730, 20.0),
    )
    for max_days, score in thresholds:
        if days <= max_days:
            return score
    return 0.0


def _score_cadence(releases_last_year: int) -> float:
    if releases_last_year >= 4:
        return 100.0
    if releases_last_year >= 2:
        return 85.0
    if releases_last_year >= 1:
        return 70.0
    return 30.0


def calculate_maintenance_score(
    *,
    is_archived: bool,
    days_since_last_commit: int | None,
    releases_last_year: int,
) -> float:
    """Score dependency maintenance based on archival, commit recency, and release cadence."""
    if is_archived:
        return 0.0

    commit_score = _score_commit_recency(days_since_last_commit)
    cadence_score = _score_cadence(releases_last_year)
    score = (0.7 * commit_score) + (0.3 * cadence_score)
    return round(max(0.0, min(100.0, score)), 1)


def _extract_github_repo(
    project_urls: dict[str, Any] | None, home_page: str | None
) -> tuple[str, str] | None:
    """Extract GitHub owner and repository name from metadata URLs."""
    candidates: list[str] = []
    if project_urls and isinstance(project_urls, dict):
        for key in ("Source", "Repository", "Source Code", "Code", "GitHub", "Homepage"):
            val = project_urls.get(key)
            if isinstance(val, str) and val:
                candidates.append(val)
        candidates.extend(v for v in project_urls.values() if isinstance(v, str))
    if home_page:
        candidates.append(home_page)

    for url in candidates:
        match = _GITHUB_URL_RE.match(url)
        if match:
            owner = match.group("owner")
            repo = match.group("repo").removesuffix(".git").rstrip("/")
            return owner, repo
    return None


def _default_pypi_fetcher(pkg_name: str) -> dict[str, Any]:
    """Fetch package metadata from PyPI JSON API."""
    from devops_cli.http.client import new_http_client
    from devops_cli.http.egress import EgressLevel

    url = f"https://pypi.org/pypi/{pkg_name}/json"
    with new_http_client(level=EgressLevel.PUBLIC) as client:
        resp = client.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}


def _default_github_fetcher(owner: str, repo: str) -> dict[str, Any]:
    """Fetch repository metadata from GitHub REST API."""
    from devops_cli.github.session import get_github_session

    session = get_github_session()
    res = session.rest("GET", f"/repos/{owner}/{repo}")
    if isinstance(res, dict):
        return res
    return {}


def _get_lockfile_upload_time(lock_package: dict[str, Any] | None) -> str:
    if not lock_package:
        return ""
    sdist = lock_package.get("sdist") or {}
    upload_time = sdist.get("upload-time") or ""
    if not upload_time and lock_package.get("wheels"):
        wheels = lock_package["wheels"]
        if isinstance(wheels, list) and wheels:
            upload_time = wheels[0].get("upload-time") or ""
    return str(upload_time)


def _get_installed_metadata(pkg_name: str) -> tuple[str, dict[str, str]]:
    licence = ""
    project_urls: dict[str, str] = {}
    try:
        md = importlib.metadata.metadata(pkg_name)
        licence = str(md.get("License-Expression") or md.get("License") or "")
        if not licence:
            for c in md.get_all("Classifier") or []:
                if "License ::" in c:
                    licence = str(c.split("::")[-1].strip())
                    break
        for raw_url in md.get_all("Project-URL") or []:
            if "," in raw_url:
                k, v = raw_url.split(",", 1)
                project_urls[k.strip()] = v.strip()
    except importlib.metadata.PackageNotFoundError:
        logger.debug("Package metadata not found for %s", pkg_name)
    return licence or "Unknown", project_urls


def _inspect_from_local(
    pin: DependencyPin, lock_package: dict[str, Any] | None
) -> DependencyMaturity:
    """Inspect dependency from local lockfile and installed package metadata."""
    now = datetime.now(UTC)
    upload_time = _get_lockfile_upload_time(lock_package)
    licence, project_urls_dict = _get_installed_metadata(pin.name)

    repo_pair = _extract_github_repo(project_urls_dict, None)
    source_url = f"https://github.com/{repo_pair[0]}/{repo_pair[1]}" if repo_pair else ""

    days_since_commit: int | None = None
    if upload_time:
        up_dt = _safe_parse_iso(upload_time)
        if up_dt:
            days_since_commit = max((now - up_dt).days, 0)

    score = calculate_maintenance_score(
        is_archived=False,
        days_since_last_commit=days_since_commit,
        releases_last_year=2,
    )

    return DependencyMaturity(
        name=pin.name,
        version=pin.version,
        last_commit_date=upload_time,
        release_cadence="2.0 releases/year",
        archival_status="active",
        is_archived=False,
        licence=licence,
        maintenance_score=score,
        source_url=source_url,
    )


def _extract_pypi_license(info: dict[str, Any]) -> str:
    pypi_license = str(info.get("license") or "")
    if pypi_license:
        return pypi_license
    classifiers = info.get("classifiers") or []
    for c in classifiers:
        if isinstance(c, str) and c.startswith("License ::"):
            return str(c.split("::")[-1].strip())
    return ""


def _extract_pypi_timestamps(releases_dict: dict[str, Any]) -> list[str]:
    timestamps: list[str] = []
    for rel_files in releases_dict.values():
        if not isinstance(rel_files, list):
            continue
        for f in rel_files:
            ts = f.get("upload_time_iso_8601") or f.get("upload_time")
            if ts:
                timestamps.append(str(ts))
                break
    return timestamps


def _fetch_remote_data(
    pin_name: str,
    fetch_pypi: Callable[[str], dict[str, Any]],
    fetch_gh: Callable[[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, str] | None]:
    pypi_data: dict[str, Any] = {}
    try:
        pypi_data = fetch_pypi(pin_name)
    except (httpx2.HTTPError, OSError, ValueError, KeyError) as exc:
        logger.debug("Failed fetching PyPI metadata for %s: %s", pin_name, exc)

    info = pypi_data.get("info", {})
    repo_pair = _extract_github_repo(info.get("project_urls"), info.get("home_page"))

    gh_data: dict[str, Any] = {}
    if repo_pair:
        try:
            gh_data = fetch_gh(repo_pair[0], repo_pair[1])
        except (GitHubOperationError, httpx2.HTTPError, OSError, ValueError, KeyError) as exc:
            logger.debug("Failed fetching GitHub repo %s/%s: %s", repo_pair[0], repo_pair[1], exc)

    return pypi_data, gh_data, repo_pair


def inspect_dependency(
    pin: DependencyPin,
    *,
    pypi_fetcher: Callable[[str], dict[str, Any]] | None = None,
    github_fetcher: Callable[[str, str], dict[str, Any]] | None = None,
    online: bool = False,
    lockfile_packages: dict[str, dict[str, Any]] | None = None,
) -> DependencyMaturity:
    """Inspect upstream maintenance signals for one pinned dependency."""
    if not online and pypi_fetcher is None and github_fetcher is None:
        lock_pkg = (lockfile_packages or {}).get(pin.name.lower())
        return _inspect_from_local(pin, lock_pkg)

    pypi_data, gh_data, repo_pair = _fetch_remote_data(
        pin.name,
        pypi_fetcher or _default_pypi_fetcher,
        github_fetcher or _default_github_fetcher,
    )

    info = pypi_data.get("info", {})
    pypi_license = _extract_pypi_license(info)
    timestamps = _extract_pypi_timestamps(pypi_data.get("releases", {}))

    cadence = compute_release_cadence(timestamps)
    now = datetime.now(UTC)
    releases_last_year = sum(
        1 for ts in timestamps if (ts_dt := _safe_parse_iso(ts)) and (now - ts_dt).days <= 365
    )

    source_url = f"https://github.com/{repo_pair[0]}/{repo_pair[1]}" if repo_pair else ""
    is_archived = bool(gh_data.get("archived", False))

    last_commit_date = str(gh_data.get("pushed_at") or "")
    if not last_commit_date and timestamps:
        last_commit_date = sorted(timestamps)[-1]

    days_since_commit: int | None = None
    if last_commit_date:
        commit_dt = _safe_parse_iso(last_commit_date)
        if commit_dt:
            days_since_commit = max((now - commit_dt).days, 0)

    gh_license_info = gh_data.get("license") or {}
    licence = (
        str(gh_license_info.get("spdx_id") or gh_license_info.get("name") or "")
        or pypi_license
        or "Unknown"
    )

    score = calculate_maintenance_score(
        is_archived=is_archived,
        days_since_last_commit=days_since_commit,
        releases_last_year=releases_last_year,
    )
    archival_status = "archived" if is_archived else "active"

    return DependencyMaturity(
        name=pin.name,
        version=pin.version,
        last_commit_date=last_commit_date,
        release_cadence=cadence,
        archival_status=archival_status,
        is_archived=is_archived,
        licence=licence,
        maintenance_score=score,
        source_url=source_url,
    )


def _safe_parse_iso(ts: str) -> datetime | None:
    try:
        clean = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def inspect_all_dependencies(
    pyproject_path: Path | None = None,
    *,
    pypi_fetcher: Callable[[str], dict[str, Any]] | None = None,
    github_fetcher: Callable[[str, str], dict[str, Any]] | None = None,
    online: bool = False,
) -> list[DependencyMaturity]:
    """Inspect all pinned runtime dependencies in pyproject.toml."""
    pins = read_pinned_dependencies(pyproject_path)
    lock_pkgs = _read_lockfile_packages() if not online else None
    return [
        inspect_dependency(
            pin,
            pypi_fetcher=pypi_fetcher,
            github_fetcher=github_fetcher,
            online=online,
            lockfile_packages=lock_pkgs,
        )
        for pin in pins
    ]
