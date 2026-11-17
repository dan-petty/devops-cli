"""The IaC scan reads the ignore file of the repository that has a reason and an expiry (#4401).

`.trivyignore.yaml` holds the entries of a finding in an IaC file: Trivy takes the path, the
`statement` and `expired_at` of an entry only from the YAML form, and reads that file only when it
is named with `--ignorefile`.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.security.trivy import TrivyConfigScanner, TrivyScanner


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
