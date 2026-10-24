"""Tests for upstream dependency maturity survey and mechanical signals."""

from __future__ import annotations

from devops_cli.survey.dependencies import (
    DependencyMaturity,
    DependencyPin,
    calculate_maintenance_score,
    compute_release_cadence,
    inspect_dependency,
    read_pinned_dependencies,
)
from tests.support.paths import REPO_ROOT


def test_read_pinned_dependencies_extracts_runtime_pins() -> None:
    """Reading pyproject.toml extracts direct runtime dependencies with exact version pins."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    deps = read_pinned_dependencies(pyproject_path)
    assert len(deps) >= 30
    assert all(isinstance(dep, DependencyPin) for dep in deps)
    click_dep = next(d for d in deps if d.name == "click")
    assert click_dep.version != ""


def test_compute_release_cadence_from_timestamps() -> None:
    """Release cadence calculates average interval or annual rate from release upload dates."""
    timestamps = [
        "2026-01-01T00:00:00Z",
        "2026-04-01T00:00:00Z",
        "2026-07-01T00:00:00Z",
        "2026-10-01T00:00:00Z",
    ]
    cadence = compute_release_cadence(timestamps)
    assert "releases/year" in cadence or "days/release" in cadence or "quarterly" in cadence.lower()


def test_calculate_maintenance_score_healthy() -> None:
    """An active dependency with recent commits and healthy cadence receives a high score."""
    score = calculate_maintenance_score(
        is_archived=False,
        days_since_last_commit=15,
        releases_last_year=4,
    )
    assert score >= 80.0


def test_calculate_maintenance_score_archived() -> None:
    """An archived repository receives a zero maintenance score."""
    score = calculate_maintenance_score(
        is_archived=True,
        days_since_last_commit=10,
        releases_last_year=5,
    )
    assert score == 0.0


def test_inspect_dependency_reports_four_mechanical_signals() -> None:
    """Inspecting a dependency produces last commit date, release cadence, archival status, and licence."""
    mock_pypi_data = {
        "info": {
            "name": "example-pkg",
            "version": "1.2.0",
            "license": "Apache-2.0",
            "project_urls": {"Source": "https://github.com/example-org/example-pkg"},
        },
        "releases": {
            "1.0.0": [{"upload_time_iso_8601": "2025-01-01T12:00:00Z"}],
            "1.1.0": [{"upload_time_iso_8601": "2025-06-01T12:00:00Z"}],
            "1.2.0": [{"upload_time_iso_8601": "2026-01-01T12:00:00Z"}],
        },
    }
    mock_github_data = {
        "archived": False,
        "pushed_at": "2026-09-15T10:00:00Z",
        "license": {"spdx_id": "Apache-2.0", "name": "Apache License 2.0"},
    }

    def fake_pypi_client(pkg_name: str) -> dict:
        return mock_pypi_data

    def fake_github_client(owner: str, repo: str) -> dict:
        return mock_github_data

    pin = DependencyPin(name="example-pkg", version="1.2.0")
    maturity = inspect_dependency(
        pin,
        pypi_fetcher=fake_pypi_client,
        github_fetcher=fake_github_client,
    )

    assert isinstance(maturity, DependencyMaturity)
    assert maturity.name == "example-pkg"
    assert maturity.last_commit_date == "2026-09-15T10:00:00Z"
    assert maturity.release_cadence != ""
    assert maturity.archival_status == "active"
    assert maturity.is_archived is False
    assert maturity.licence == "Apache-2.0"
    assert maturity.maintenance_score > 0.0
