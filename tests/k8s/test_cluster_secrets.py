"""Tests for cluster secrets row definitions (#6684)."""

from __future__ import annotations

from devops_cli.config.env import env_var_for_option
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    OPTIONAL_FEATURE_SECRETS,
    KeyringSource,
    SettingSource,
)

SETTINGS = (
    "renovate.github_app_id",
    "renovate.github_app_installation_id",
    "renovate.github_app_private_key",
)


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
