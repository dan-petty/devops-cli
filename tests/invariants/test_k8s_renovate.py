"""The self-hosted Renovate of the cluster: its row of the cluster Secret table, and the records
of its license exception (#4905, ADR 0027).

The form of the manifests under `k8s/devops/renovate/` is the work of the `k8s` row of `devops ci`
and of kube-linter, and no test asserts a value of them (#6060).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from devops_cli.config.env import env_var_for_option
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    OPTIONAL_FEATURE_SECRETS,
    KeyringSource,
    SettingSource,
)
from tests.support.paths import REPO_ROOT
from tests.support.renovate import renovate_configmap_data

SETTINGS = (
    "renovate.github_app_id",
    "renovate.github_app_installation_id",
    "renovate.github_app_private_key",
)
ADR = REPO_ROOT / "docs" / "adr" / "0027-dependency-updates-come-from-self-hosted-renovate.md"


@pytest.mark.live("node")
def test_the_config_removes_the_token_before_a_child_process_can_read_it(
    tmp_path: Path,
) -> None:
    """The config script reads the token from disk and removes the file at once."""
    data = renovate_configmap_data()
    (tmp_path / "config.js").write_text(data["config.js"], encoding="utf-8")
    (tmp_path / "config.json").write_text(data["config.json"], encoding="utf-8")
    token_file = tmp_path / "github-token"
    token_file.write_text("test-token\n", encoding="utf-8")

    env = {**os.environ, "DEVOPS_CLI_TOKEN_FILE": str(token_file)}
    exported = subprocess.run(
        ["node", "-e", "console.log(JSON.stringify(require('./config.js')))", "-"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout
    config = json.loads(exported)
    assert config["token"] == "test-token\n"

    child = subprocess.run(
        [
            "node",
            "-e",
            f"const {{ readFileSync }} = require('node:fs'); readFileSync({json.dumps(str(token_file))});",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert child.returncode != 0
    assert "ENOENT" in child.stderr


def test_the_secret_row_holds_the_two_ids_and_the_key_under_their_variables() -> None:
    """The keys are the variables of the settings, so the init container takes the Secret with
    `envFrom`. A run reads the token at its start, so no workload restarts. Renovate is an optional
    feature: a push with no Renovate settings skips the three keys and does not fail the stack."""
    (row,) = (secret for secret in CLUSTER_SECRETS if secret.ref == "devops/renovate")
    entries = {entry.key: entry for entry in row.entries}
    app_id, installation_id, private_key = SETTINGS

    assert (
        row.stack,
        row.restarts,
        list(entries),
        entries[env_var_for_option(app_id) or ""].source,
        entries[env_var_for_option(installation_id) or ""].source,
        entries[env_var_for_option(private_key) or ""].source,
        [entry.key for entry in row.entries if entry.required],
        row.ref in OPTIONAL_FEATURE_SECRETS,
    ) == (
        "devops",
        (),
        [env_var_for_option(setting) for setting in SETTINGS],
        SettingSource(app_id),
        SettingSource(installation_id),
        KeyringSource.for_credential(private_key),
        [],
        True,
    )


def _license_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if "Renovate" in line and "AGPL-3.0-only" in line
    ]


def test_the_records_of_the_license_exception_agree() -> None:
    """The record, the open-tools rule and the Renovate section name one exception: the
    unmodified official image, and a patch to it is a new decision."""
    places = {
        "adr": ADR,
        "contributing": REPO_ROOT / "CONTRIBUTING.md",
        "cluster": REPO_ROOT / "docs" / "CLUSTER.md",
    }
    found = {name: _license_lines(path) for name, path in places.items()}

    assert {
        name: (
            bool(lines),
            any("unmodified" in line for line in lines),
            any("new decision" in line for line in lines),
            name == "adr" or any(ADR.name in line for line in lines),
        )
        for name, lines in found.items()
    } == {name: (True, True, True, True) for name in places}


def test_the_adr_names_the_token_in_memory_as_the_residual_risk() -> None:
    """ADR 0027 names the residual risk in memory and drops the false claim (#6020)."""
    lines = ADR.read_text(encoding="utf-8").splitlines()
    assert any("memory" in line and "one hour" in line for line in lines)
    assert not any("a repository command that goes wrong reaches no key" in line for line in lines)
