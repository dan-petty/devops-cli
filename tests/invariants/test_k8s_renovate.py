"""The self-hosted Renovate of the cluster: its row of the cluster Secret table, and the records
of its license exception (#4905, ADR 0027).

The form of the manifests under `k8s/devops/renovate/` is the work of the `k8s` row of `devops ci`
and of kube-linter, and no test asserts a value of them (#6060).
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.env import env_var_for_option
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    OPTIONAL_FEATURE_SECRETS,
    KeyringSource,
    SettingSource,
)
from tests.support.paths import REPO_ROOT

SETTINGS = (
    "renovate.github_app_id",
    "renovate.github_app_installation_id",
    "renovate.github_app_private_key",
)
ADR = REPO_ROOT / "docs" / "adr" / "0027-dependency-updates-come-from-self-hosted-renovate.md"


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
