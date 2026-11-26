"""Tests for loading cluster-secrets.toml into ClusterSecret dataclasses (#6685)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.k8s.cluster_secrets import (
    ClusterSecret,
    DerivedSource,
    KeyringSource,
    LiteralSource,
    SecretEntry,
    SecretGenerator,
    SecretKeyRef,
    SettingSource,
    Workload,
    load_cluster_secrets,
)
from tests.support.paths import REPO_ROOT

FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "cluster-secrets.toml"


def test_fixture_file_loads_into_cluster_secret_dataclasses() -> None:
    """The loader SHALL build the existing ClusterSecret dataclasses from cluster-secrets.toml."""
    secrets = load_cluster_secrets(FIXTURE_PATH)
    assert len(secrets) == 13
    assert all(isinstance(s, ClusterSecret) for s in secrets)

    by_ref = {s.ref: s for s in secrets}

    # 1. Keyring source (with generator & value_prefix)
    gateway = by_ref["llm/llm-gateway-secrets"]
    assert gateway == ClusterSecret(
        namespace="llm",
        name="llm-gateway-secrets",
        stack="llm",
        entries=(
            SecretEntry(
                "master-key",
                KeyringSource("llm_gateway_master_key"),
                generator=SecretGenerator("hex", 24, prefix="sk-"),
                value_prefix="sk-",
            ),
            SecretEntry(
                "gemini-api-key",
                KeyringSource.for_credential("gemini.api_key"),
                required=False,
            ),
            SecretEntry(
                "anthropic-api-key",
                KeyringSource.for_credential("anthropic.api_key"),
                required=False,
            ),
            SecretEntry(
                "openrouter-api-key",
                KeyringSource.for_credential("openrouter.api_key"),
                required=False,
            ),
        ),
        restarts=(Workload("deployment", "llm-gateway"),),
        labels={"app.kubernetes.io/name": "llm-gateway"},
        change_note=(
            "Open WebUI keeps the gateway connection stored in its database: update the key "
            "under Admin Panel > Settings > Connections."
        ),
    )

    # 2. Setting source
    argocd_notif = by_ref["argocd/argocd-notifications-secret"]
    app_id_entry = next(e for e in argocd_notif.entries if e.key == "github-appID")
    assert app_id_entry == SecretEntry("github-appID", SettingSource("argocd.github_app_id"))

    # 3. Literal source
    seaweed_s3 = by_ref["object-store/seaweedfs-s3"]
    assert seaweed_s3 == ClusterSecret(
        namespace="object-store",
        name="seaweedfs-s3",
        stack="infra",
        entries=(SecretEntry("s3.json", LiteralSource('{"identities": []}')),),
        restarts=(Workload("deployment", "seaweedfs-s3"),),
        labels={"app.kubernetes.io/name": "seaweedfs"},
    )

    # 4. Derived source with generator and adopt_from
    mattermost_db = by_ref["mattermost/mattermost-db"]
    assert mattermost_db == ClusterSecret(
        namespace="mattermost",
        name="mattermost-db",
        stack="chat",
        secret_type="kubernetes.io/basic-auth",
        entries=(
            SecretEntry("username", LiteralSource("mattermost")),
            SecretEntry(
                "password",
                KeyringSource("mattermost_db_password"),
                generator=SecretGenerator("urlsafe", 32),
                adopt_from=SecretKeyRef("mattermost", "mattermost-db", "password"),
            ),
            SecretEntry(
                "DB_CONNECTION_STRING",
                DerivedSource(
                    "postgres://{username}:{password}@mattermost-db-rw.mattermost.svc.cluster.local:5432/mattermost?sslmode=require&connect_timeout=10",
                    {
                        "username": LiteralSource("mattermost"),
                        "password": KeyringSource("mattermost_db_password"),
                    },
                ),
            ),
        ),
        labels={"app.kubernetes.io/name": "mattermost-db"},
    )


def test_generator_and_adopt_from_tables_load() -> None:
    """The file model SHALL read the generator and adopt_from tables for each row."""
    secrets = load_cluster_secrets(FIXTURE_PATH)
    mattermost_db = next(s for s in secrets if s.ref == "mattermost/mattermost-db")
    pw_entry = next(e for e in mattermost_db.entries if e.key == "password")
    assert pw_entry.generator == SecretGenerator("urlsafe", 32)
    assert pw_entry.adopt_from == SecretKeyRef("mattermost", "mattermost-db", "password")


def test_invalid_source_configuration_fails(tmp_path: Path) -> None:
    """An entry with no source or multiple sources must fail validation."""
    no_source = tmp_path / "no_source.toml"
    no_source.write_text(
        """
[[secret]]
namespace = "test"
name = "bad"
stack = "test"
[[secret.entry]]
key = "foo"
required = true
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="secret entry must specify exactly one of"):
        load_cluster_secrets(no_source)

    multi_source = tmp_path / "multi_source.toml"
    multi_source.write_text(
        """
[[secret]]
namespace = "test"
name = "bad"
stack = "test"
[[secret.entry]]
key = "foo"
required = true
[secret.entry.literal]
value = "bar"
[secret.entry.setting]
option = "baz"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="secret entry must specify exactly one of"):
        load_cluster_secrets(multi_source)


def test_load_cluster_secrets_table_resolves_fixture_when_installed_in_site_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When devops_cli is imported from site-packages (like in the Service image),
    load_cluster_secrets_table still locates the repository fixture."""
    import devops_cli.k8s.cluster_secrets as cs

    fake_pkg_file = Path(
        "/app/.venv/lib/python3.14/site-packages/devops_cli/k8s/cluster_secrets.py"
    )
    monkeypatch.setattr(cs, "__file__", str(fake_pkg_file))
    monkeypatch.setattr(
        cs,
        "_FIXTURE_SECRETS_FILE",
        fake_pkg_file.parents[3] / "tests" / "fixtures" / "cluster-secrets.toml",
    )

    table = cs.load_cluster_secrets_table()
    assert len(table) == 24
    assert any(s.ref == "object-store/seaweedfs-admin" for s in table)
    assert any(s.ref == "argocd/argocd-notifications-secret" for s in table)


def test_resolve_fixture_secrets_file_variants(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test resolution of fixture secrets file across primary, fallback, and absent paths."""
    import devops_cli.k8s.cluster_secrets as cs

    # Primary exists
    fake_primary = tmp_path / "primary.toml"
    fake_primary.write_text("[[secret]]\n", encoding="utf-8")
    monkeypatch.setattr(cs, "_FIXTURE_SECRETS_FILE", fake_primary)
    assert cs._resolve_fixture_secrets_file() == fake_primary

    # Primary missing, fallback exists
    monkeypatch.setattr(cs, "_FIXTURE_SECRETS_FILE", tmp_path / "missing1.toml")
    fake_fallback = tmp_path / "fallback.toml"
    fake_fallback.write_text("[[secret]]\n", encoding="utf-8")
    monkeypatch.setattr(cs, "_FALLBACK_FIXTURE_SECRETS_FILE", fake_fallback)
    assert cs._resolve_fixture_secrets_file() == fake_fallback

    # Both missing
    monkeypatch.setattr(cs, "_FALLBACK_FIXTURE_SECRETS_FILE", tmp_path / "missing2.toml")
    assert cs._resolve_fixture_secrets_file() is None


def test_load_cluster_secrets_table_resolves_fixture_when_env_lacks_secrets() -> None:
    """When env has no cluster_secrets, load_cluster_secrets_table falls back to fixture."""
    import devops_cli.k8s.cluster_secrets as cs

    table = cs.load_cluster_secrets_table(object())
    assert len(table) == 24
    assert any(s.ref == "object-store/seaweedfs-admin" for s in table)


def test_load_cluster_secrets_table_resolves_fixture_when_k8s_dir_lacks_secrets(
    tmp_path: Path,
) -> None:
    """When k8s_dir has no cluster-secrets.toml, load_cluster_secrets_table falls back to fixture."""
    import devops_cli.k8s.cluster_secrets as cs

    empty_k8s = tmp_path / "k8s"
    empty_k8s.mkdir()
    table = cs.load_cluster_secrets_table(k8s_dir=empty_k8s)
    assert len(table) == 24
    assert any(s.ref == "object-store/seaweedfs-admin" for s in table)
