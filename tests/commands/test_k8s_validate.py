"""`devops k8s validate` passes only when the pinned kubeconform ran and found nothing (#2214)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer

_VALID = "are valid schemas"


def test_a_validation_that_did_not_run_says_so_and_fails(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no kubeconform on PATH, the command says that the validation did not run and why, says
    no pass, and exits 1. The PATH holds git, which the command loads GitPython for, and no
    scanner."""
    no_scanners = tmp_path / "no-scanners"
    no_scanners.mkdir()
    (no_scanners / "git").symlink_to(str(shutil.which("git")))
    monkeypatch.setenv("PATH", str(no_scanners))
    (tmp_path / "deploy.yaml").write_text("apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8")

    result = cli("k8s", "validate", str(tmp_path))

    assert (result.exit_code, _VALID in result.output, " ".join(result.output.split())) == (
        1,
        False,
        "Validating Kubernetes manifests at "
        f"'{tmp_path}' (k8s: master)... ✗ Kubeconform validation unavailable: Binary "
        "'kubeconform' not found on PATH. The manifests were not validated, so the check did "
        "not pass.",
    )


def test_a_clean_validation_passes(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """kubeconform writes an empty `resources` list and exits 0, so the command passes."""
    scanner_fake.script("kubeconform", ToolAnswer(stdout='{\n  "resources": []\n}\n'))
    (tmp_path / "deploy.yaml").write_text("apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8")

    result = cli("k8s", "validate", str(tmp_path))

    assert (result.exit_code, _VALID in result.output) == (0, True)


def test_a_target_with_no_manifest_says_so_and_fails(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """kubeconform starts only for a target that holds a manifest. With no manifest, such as a
    directory with a Helm values file alone, the command says why kubeconform did not run, says no
    pass, and exits 1."""
    scanner_fake.script("kubeconform", ToolAnswer(stdout='{\n  "resources": []\n}\n'))
    (tmp_path / "values.yaml").write_text("replicaCount: 2\n", encoding="utf-8")

    result = cli("k8s", "validate", str(tmp_path))

    assert (
        result.exit_code,
        _VALID in result.output,
        "No Kubernetes manifest in the target" in " ".join(result.output.split()),
        scanner_fake.runs,
    ) == (1, False, True, [])


def test_a_finding_shows_the_text_of_the_manifest_as_text(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The kind, the name and the schema errors of a finding come from the manifest. The table
    shows them as text, also a name that looks like Rich markup."""
    manifest = tmp_path / "svc.yaml"
    manifest.write_text("apiVersion: v1\nkind: Service\nmetadata:\n  name: x\n", encoding="utf-8")
    resource = {
        "filename": str(manifest),
        "kind": "Service",
        "name": "web[/bold]",
        "version": "v1",
        "status": "statusInvalid",
        "msg": "problem validating schema",
        "validationErrors": [{"path": "/spec/ports/0/port", "msg": "got [red]string[/red]"}],
    }
    scanner_fake.script(
        "kubeconform", ToolAnswer(exit_code=1, stdout=json.dumps({"resources": [resource]}))
    )

    result = cli("k8s", "validate", str(tmp_path))

    output = "".join(result.output.split())
    assert (result.exit_code, "web[/bold]" in output, "got[red]string[/red]" in output) == (
        0,
        True,
        True,
    )
