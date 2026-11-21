"""The chart sources that deploy-stack reads from the Argo CD Applications of a tree: the chart
version (#6060), the values files and the sources with a ref (#6680).

The Applications are files that each test writes, in the shape that Argo CD reads.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devops_cli.k8s.app_sources import ChartSource, chart_sources

# The sources of an Application that the values files name by their ref.
_TEMPLATES = {
    "repoURL": "https://git.example.com/templates.git",
    "targetRevision": "v1",
    "ref": "t",
}
_VALUES = {"repoURL": "https://git.example.com/repo.git", "targetRevision": "main", "ref": "v"}


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


def test_each_application_with_a_chart_source_gives_its_version_values_files_and_refs(
    tmp_path: Path,
) -> None:
    """A chart source gives its `targetRevision` and its values files in their order, with the
    sources of its Application that have a ref. A path source and another kind give none, and the
    Applications of each folder count."""
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
                    "helm": {"valueFiles": ["$t/helm/alpha.yaml", "$v/env/alpha.yaml"]},
                },
                _TEMPLATES,
                _VALUES,
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

    assert chart_sources([leaves, roots]) == {
        "alpha": ChartSource(
            version="1.2.3",
            value_files=("$t/helm/alpha.yaml", "$v/env/alpha.yaml"),
            refs={"t": _TEMPLATES, "v": _VALUES},
        ),
        "gamma": ChartSource(version="v4.5.6", value_files=(), refs={}),
    }


def test_a_chart_source_with_no_revision_gives_no_chart_source(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "alpha.yaml",
        _application("alpha", source={"repoURL": "https://charts.example.com", "chart": "alpha"}),
    )

    assert chart_sources([tmp_path]) == {}
