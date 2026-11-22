"""The remote targets of a kustomization: what `kubectl kustomize` fetches to build it (#6681)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.kustomize_remotes import remote_targets

_VALKEY = "https://example.com/infra.git//k8s/bases/valkey?ref=v0.1.0"
_DENY = "github.com/example/infra/k8s/components/deny?ref=v0.1.0"
_LEGACY = "git@example.com:example/infra.git//k8s/legacy"


def _kustomization(folder: Path, body: dict[str, object], name: str = "kustomization.yaml") -> Path:
    """Write the kustomization `body` in `folder` and return the folder."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(yaml.safe_dump(body), "utf-8")
    return folder


def test_a_kustomization_reaches_the_remote_targets_of_its_local_bases_and_components(
    tmp_path: Path,
) -> None:
    """A remote target of a local base, of a local component and of a folder of the deprecated
    field `bases` counts, in the order of the read, each once."""
    _kustomization(tmp_path / "base", {"resources": ["service.yaml", _VALKEY]})
    _kustomization(
        tmp_path / "components" / "perimeter",
        {
            "apiVersion": "kustomize.config.k8s.io/v1alpha1",
            "kind": "Component",
            "resources": [_DENY],
        },
    )
    _kustomization(tmp_path / "legacy", {"resources": [_LEGACY, _VALKEY]}, "kustomization.yml")
    app = _kustomization(
        tmp_path / "app",
        {
            "resources": ["deployment.yaml", "../base"],
            "bases": ["../legacy"],
            "components": ["../components/perimeter"],
        },
    )

    assert remote_targets(app) == [_VALKEY, _LEGACY, _DENY]


@pytest.mark.parametrize(
    ("entry", "remote"),
    [
        ("https://example.com/infra.git//k8s?ref=v1", True),
        ("http://example.com/deployment.yaml", True),
        ("HTTPS://example.com/deployment.yaml", True),
        ("git::https://example.com/infra.git//k8s", True),
        ("ssh://git@example.com/example/infra.git", True),
        ("file:///srv/git/infra.git//k8s", True),
        ("git@example.com:example/infra.git", True),
        ("github.com/example/infra/k8s?ref=v1", True),
        ("GitHub.com:example/infra", True),
        ("deployment.yaml", False),
        ("../base", False),
        ("example.com/infra/k8s", False),
        ("/srv/k8s/base", False),
    ],
)
def test_kustomize_takes_an_entry_as_remote_by_its_form(
    tmp_path: Path, entry: str, remote: bool
) -> None:
    """An http or https URL and a git repository spec are remote; a local path is not, also when
    it looks like a host name."""
    folder = _kustomization(tmp_path, {"resources": [entry]})

    assert remote_targets(folder) == ([entry] if remote else [])


def test_a_kustomization_reaches_a_remote_file_of_a_patch_or_a_generator(tmp_path: Path) -> None:
    """Kustomize fetches a file that is an http or https URL, and reads a file path that looks like
    a repository from the folder."""
    folder = _kustomization(
        tmp_path,
        {
            "crds": ["https://example.com/crd.yaml"],
            "patches": [
                {"path": "https://example.com/patch.yaml"},
                {"path": "github.com/example/patch.yaml"},
                {"patch": "- op: remove\n  path: /spec/replicas\n"},
            ],
            "configMapGenerator": [
                {"name": "app", "files": ["config=https://example.com/app.conf", "local.conf"]}
            ],
        },
    )

    assert remote_targets(folder) == [
        "https://example.com/crd.yaml",
        "https://example.com/patch.yaml",
        "https://example.com/app.conf",
    ]


def test_a_cycle_of_local_bases_ends(tmp_path: Path) -> None:
    """Two folders that take each other as a base are each read once."""
    _kustomization(tmp_path / "b", {"resources": ["../a", _VALKEY]})
    a = _kustomization(tmp_path / "a", {"resources": ["../b"]})

    assert remote_targets(a) == [_VALKEY]


def test_a_folder_with_no_kustomization_has_no_remote_target(tmp_path: Path) -> None:
    """A folder of plain manifests, which deploy-stack reads with no kustomize, names nothing."""
    (tmp_path / "deployment.yaml").write_text("kind: Deployment\n", "utf-8")

    assert remote_targets(tmp_path) == []


def test_a_kustomization_that_is_not_a_mapping_stops_the_read(tmp_path: Path) -> None:
    """A kustomization that is not a YAML mapping stops the read with its path."""
    (tmp_path / "kustomization.yaml").write_text("- resources\n", "utf-8")

    with pytest.raises(KubernetesContextError) as raised:
        remote_targets(tmp_path)

    assert (
        raised.value.exit_code,
        raised.value.error_code,
        str(tmp_path / "kustomization.yaml") in str(raised.value),
    ) == (1, "K8S_CONTEXT_ERROR", True)
