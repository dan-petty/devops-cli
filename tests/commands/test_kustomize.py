"""Unit tests for kustomize CLI commands (devops_cli.commands.kustomize)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.process import ProcessFake


def test_kustomize_commands(
    tmp_path: Path, cli: Any, process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify kustomize build, diff, and apply subcommands."""
    kust_dir = tmp_path / "overlay"
    kust_dir.mkdir()
    (kust_dir / "kustomization.yaml").write_text(
        "resources:\n  - deployment.yaml\n", encoding="utf-8"
    )

    res_build = cli("kustomize", "build", str(kust_dir))
    assert res_build.exit_code == 0

    res_build_out = cli("kustomize", "build", str(kust_dir), "--output", "out.yaml")
    assert res_build_out.exit_code == 0

    res_diff = cli("kustomize", "diff", str(kust_dir))
    assert res_diff.exit_code == 0

    res_apply = cli("kustomize", "apply", str(kust_dir), "--dry-run", "--namespace", "staging")
    assert res_apply.exit_code == 0

    # Apply without dry-run and without namespace
    res_apply_direct = cli("kustomize", "apply", str(kust_dir))
    assert res_apply_direct.exit_code == 0

    # Default path invocation when directory exists
    monkeypatch.chdir(kust_dir)
    res_build_default = cli("kustomize", "build")
    assert res_build_default.exit_code == 0

    assert [call.argv for call in process_fake.calls] == [
        ("kustomize", "build", str(kust_dir)),
        ("kustomize", "build", str(kust_dir), "--output", "out.yaml"),
        ("kubectl", "diff", "-k", str(kust_dir)),
        ("kubectl", "apply", "-k", str(kust_dir)),
        ("kustomize", "build", "."),
    ]

    # Invalid namespace
    res_bad_ns = cli("kustomize", "apply", str(kust_dir), "--namespace", "INVALID_NAMESPACE!@#")
    assert res_bad_ns.exit_code != 0
