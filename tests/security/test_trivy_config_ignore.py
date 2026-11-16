"""The IaC scan reads the ignore file of the repository that has a reason and an expiry (#4401).

`.trivyignore.yaml` holds the entries of a finding in an IaC file: Trivy takes the path, the
`statement` and `expired_at` of an entry only from the YAML form, and reads that file only when it
is named with `--ignorefile`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from devops_cli.security.trivy import TrivyConfigScanner, TrivyScanner
from tests.support.paths import REPO_ROOT


def test_the_config_scan_names_the_yaml_ignore_file_of_its_directory(tmp_path: Path) -> None:
    ignore = tmp_path / ".trivyignore.yaml"
    ignore.write_text("misconfigurations: []\n", encoding="utf-8")

    cmd = TrivyConfigScanner().build_command(tmp_path, cwd=tmp_path)

    assert cmd[cmd.index("--ignorefile") + 1] == str(ignore)


def test_the_config_scan_names_no_ignore_file_when_the_directory_has_none(tmp_path: Path) -> None:
    cmd = TrivyConfigScanner().build_command(tmp_path, cwd=tmp_path)

    assert "--ignorefile" not in cmd


def test_the_other_trivy_scans_keep_the_plain_ignore_file(tmp_path: Path) -> None:
    (tmp_path / ".trivyignore.yaml").write_text("misconfigurations: []\n", encoding="utf-8")

    cmd = TrivyScanner().build_command(tmp_path, cwd=tmp_path)

    assert "--ignorefile" not in cmd


def test_the_repository_ignore_file_holds_the_privileged_gpu_entry() -> None:
    path = REPO_ROOT / ".trivyignore.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in data.get("misconfigurations", [])
        if entry.get("id") == "KSV-0017"
        and "k8s/gpu-feature-discovery/daemonset.yaml" in entry.get("paths", [])
    ]
    assert len(entries) >= 1
    entry = entries[0]
    assert "#5646" in entry.get("statement", "")
    exp = entry.get("expired_at")
    assert exp is not None
    assert isinstance(exp, date) or date.fromisoformat(str(exp))


def test_the_repository_ignore_file_holds_the_sysfs_mount_entry() -> None:
    path = REPO_ROOT / ".trivyignore.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in data.get("misconfigurations", [])
        if entry.get("id") == "KSV-0121"
        and "k8s/gpu-feature-discovery/daemonset.yaml" in entry.get("paths", [])
    ]
    assert len(entries) >= 1
    entry = entries[0]
    assert "#5646" in entry.get("statement", "")
    exp = entry.get("expired_at")
    assert exp is not None
    assert isinstance(exp, date) or date.fromisoformat(str(exp))


def test_the_repository_ignore_file_holds_the_pod_security_context_entry() -> None:
    path = REPO_ROOT / ".trivyignore.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in data.get("misconfigurations", [])
        if entry.get("id") == "KSV-0118"
        and "k8s/gpu-feature-discovery/daemonset.yaml" in entry.get("paths", [])
    ]
    assert len(entries) >= 1
    entry = entries[0]
    assert "#5646" in entry.get("statement", "")
    exp = entry.get("expired_at")
    assert exp is not None
    assert isinstance(exp, date) or date.fromisoformat(str(exp))


def test_the_repository_ignore_file_holds_the_harbor_entry() -> None:
    path = REPO_ROOT / ".trivyignore.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in data.get("misconfigurations", [])
        if entry.get("id", "").endswith("DS-0029")
        and ".venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile"
        in entry.get("paths", [])
    ]
    assert len(entries) == 1
    entry = entries[0]
    statement = entry.get("statement", "")
    assert "harbor" in statement.lower()
    assert "#5947" in statement
    exp = entry.get("expired_at")
    assert exp is not None
    parsed_date = exp if isinstance(exp, date) else date.fromisoformat(str(exp))
    assert parsed_date >= date(2026, 11, 16)
    assert not any("*" in p for p in entry.get("paths", []))
