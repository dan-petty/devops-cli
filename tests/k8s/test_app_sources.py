"""The chart versions that deploy-stack reads from the Argo CD Applications of a tree (#6060).

The Applications are files that each test writes, in the shape that Argo CD reads.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devops_cli.k8s.app_sources import chart_versions


def _write(folder: Path, name: str, *documents: dict[str, object]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(yaml.safe_dump_all(documents), encoding="utf-8")


def _application(name: str, **spec: object) -> dict[str, object]:
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": spec,
    }


def test_each_application_with_a_chart_source_gives_the_version_that_it_pins(
    tmp_path: Path,
) -> None:
    """A chart source gives its `targetRevision`, a path source and another kind give none, and
    the Applications of each folder count."""
    leaves, roots = tmp_path / "apps", tmp_path / "bootstrap"
    _write(
        leaves,
        "alpha.yaml",
        _application(
            "alpha",
            sources=[
                {
                    "repoURL": "https://charts.example.com",
                    "chart": "alpha",
                    "targetRevision": "1.2.3",
                },
                {
                    "repoURL": "https://git.example.com/repo.git",
                    "targetRevision": "main",
                    "ref": "v",
                },
            ],
        ),
    )
    _write(
        leaves,
        "beta.yaml",
        _application(
            "beta", source={"repoURL": "https://git.example.com/repo.git", "path": "k8s/beta"}
        ),
        {"apiVersion": "argoproj.io/v1alpha1", "kind": "AppProject", "metadata": {"name": "p"}},
    )
    _write(
        roots,
        "gamma.yaml",
        _application(
            "gamma",
            source={
                "repoURL": "https://charts.example.com",
                "chart": "gamma",
                "targetRevision": "v4.5.6",
            },
        ),
    )

    assert chart_versions([leaves, roots]) == {"alpha": "1.2.3", "gamma": "v4.5.6"}


def test_a_chart_source_with_no_revision_gives_no_version(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "alpha.yaml",
        _application("alpha", source={"repoURL": "https://charts.example.com", "chart": "alpha"}),
    )

    assert chart_versions([tmp_path]) == {}
