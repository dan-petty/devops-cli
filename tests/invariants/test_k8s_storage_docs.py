"""The documentation of the `local-path-retain` StorageClass and the volume patch command (#6341)."""

from __future__ import annotations

from tests.support.paths import REPO_ROOT

K8S_README = REPO_ROOT / "k8s" / "README.md"
SERVICE_PATTERNS = REPO_ROOT / "docs" / "SERVICE_PATTERNS.md"


def test_k8s_storage_docs_name_the_retain_class_and_the_patch_step() -> None:
    """`k8s/README.md` and `docs/SERVICE_PATTERNS.md` name `local-path-retain` as the class for a
    new stateful workload, and `k8s/README.md` gives the `kubectl patch pv` command for a bound
    volume (#6341)."""
    k8s_readme = K8S_README.read_text(encoding="utf-8")
    service_patterns = SERVICE_PATTERNS.read_text(encoding="utf-8")

    assert "local-path-retain" in k8s_readme
    assert "local-path-retain" in service_patterns
    assert (
        'kubectl patch pv <name> -p \'{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}\''
        in k8s_readme
    )
