"""Unit tests for unified secret resolution, the access audit trail, and Vault leases."""

from __future__ import annotations

import json
import re
import time
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest

from devops_cli.config.constants import CONST_HTTP_EGRESS_POLICY_EXTENSION
from devops_cli.exceptions.vault import (
    VaultAuthenticationError,
    VaultLeaseError,
    VaultOperationError,
    VaultUnreachableError,
)
from devops_cli.models.vault import VaultAuthResult, VaultLease
from devops_cli.security.secrets import (
    EnvironmentProvider,
    KeyringProvider,
    SecretAuditLog,
    SecretProvider,
    SecretRef,
    SecretResolver,
    SettingsProvider,
    VaultProvider,
    build_default_resolver,
    build_secret_registry,
    get_resolver,
)
from devops_cli.security.vault_lease import (
    LeaseRegistry,
    login_approle,
    login_kubernetes,
    read_service_account_token,
)
from tests.support.fakes.keyring import FakeKeyring
from tests.web_fakes import StubWeb

pytestmark = pytest.mark.usefixtures("keyring_store")


def _ref(**overrides: Any) -> SecretRef:
    """Build a secret reference with test-friendly defaults."""
    base: dict[str, Any] = {
        "name": "test.secret",
        "keyring_key": "test_secret",
        "env_vars": ("TEST_SECRET",),
        "settings_path": "section.value",
        "vault_path": "secret/data/test",
        "vault_key": "test_secret",
    }
    base.update(overrides)
    return SecretRef(**base)


class _StubProvider:
    """A provider returning a fixed value, for chain ordering tests."""

    def __init__(self, name: str, value: str | None) -> None:
        self._name = name
        self._value = value

    @property
    def name(self) -> str:
        return self._name

    def get(self, ref: SecretRef) -> str | None:
        return self._value


# ─────────────────────────────────────────────────────────────────────────────
# 1. Resolver chain & precedence
# ─────────────────────────────────────────────────────────────────────────────


def test_resolver_returns_first_provider_that_answers() -> None:
    """The chain is walked in order and stops at the first provider with a value."""
    resolver = SecretResolver(
        providers=[
            _StubProvider("empty", None),
            _StubProvider("first", "from-first"),
            _StubProvider("second", "from-second"),
        ]
    )
    assert resolver.resolve(_ref()) == "from-first"


def test_resolver_returns_none_when_no_provider_answers() -> None:
    """An unresolvable secret yields None rather than raising."""
    resolver = SecretResolver(providers=[_StubProvider("a", None), _StubProvider("b", None)])
    assert resolver.resolve(_ref()) is None


def test_default_chain_order_is_keyring_vault_environment_settings() -> None:
    """Every secret shares one precedence order, fixed by the default chain."""
    resolver = build_default_resolver()
    assert [p.name for p in resolver.providers] == ["keyring", "vault", "environment", "settings"]


def test_keyring_outranks_environment_and_settings(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The OS keyring is canonical and wins over every other source."""
    settings = SimpleNamespace(section=SimpleNamespace(value="from-settings"))
    resolver = build_default_resolver(settings_source=lambda: settings)
    keyring_store.values["test_secret"] = "from-keyring"
    monkeypatch.setenv("TEST_SECRET", "from-env")

    assert resolver.resolve(_ref()) == "from-keyring"


def test_environment_outranks_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override committed configuration for every secret."""
    settings = SimpleNamespace(section=SimpleNamespace(value="from-settings"))
    resolver = build_default_resolver(settings_source=lambda: settings)
    monkeypatch.setenv("TEST_SECRET", "from-env")

    assert resolver.resolve(_ref()) == "from-env"


def test_settings_answer_only_as_last_resort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration supplies the value when nothing above it can."""
    settings = SimpleNamespace(section=SimpleNamespace(value="from-settings"))
    resolver = build_default_resolver(settings_source=lambda: settings)
    monkeypatch.setenv("TEST_SECRET", "")

    assert resolver.resolve(_ref()) == "from-settings"


def test_cached_resolver_never_serves_a_stale_settings_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-call settings source rebinds configuration on every lookup."""
    resolver = get_resolver()
    first = SimpleNamespace(section=SimpleNamespace(value="first-config"))
    second = SimpleNamespace(section=SimpleNamespace(value="second-config"))
    monkeypatch.setenv("TEST_SECRET", "")

    resolved = (
        resolver.resolve(_ref(), settings_source=lambda: first),
        resolver.resolve(_ref(), settings_source=lambda: second),
    )

    assert resolved == ("first-config", "second-config")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Individual providers
# ─────────────────────────────────────────────────────────────────────────────


def test_vault_provider_without_a_token_makes_no_request(
    stub_web: StubWeb, keyring_store: FakeKeyring
) -> None:
    """With no usable token, the chain's Vault provider asks nothing of Vault or the keyring."""
    assert VaultProvider().get(_ref()) is None
    assert stub_web.sent == []
    assert "test_secret" not in keyring_store.reads


def test_vault_provider_with_a_rejected_token_answers_none(
    monkeypatch: pytest.MonkeyPatch, stub_web: StubWeb, keyring_store: FakeKeyring
) -> None:
    """A 403 leaves the provider unable to supply, and the keyring is not read in its place."""
    monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.expired")
    stub_web.respond("GET", "http://127.0.0.1:8200/v1/secret/data/test", 403, {})

    assert VaultProvider().get(_ref()) is None
    assert len(stub_web.sent) == 1
    assert "test_secret" not in keyring_store.reads


def test_resolving_the_broker_token_builds_no_second_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker's token lookups carry no Vault path, so the chain never recurses into Vault."""
    from devops_cli.security import vault_broker

    monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
    built: list[object] = []
    original_init = vault_broker.VaultSecretBroker.__init__

    def counting_init(self: Any, *args: Any, **kwargs: Any) -> None:
        built.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(vault_broker.VaultSecretBroker, "__init__", counting_init)
    assert get_resolver().resolve(_ref(keyring_key=None, env_vars=(), settings_path=None)) is None

    names = [entry.credential_id for entry in get_resolver().audit.entries()]
    assert (len(built), names) == (1, ["vault.login", "vault.token", "test.secret"])


def test_providers_skip_references_they_cannot_serve() -> None:
    """A provider with no configured source for a secret declines rather than guessing."""
    bare = SecretRef(name="bare")
    assert KeyringProvider().get(bare) is None
    assert EnvironmentProvider().get(bare) is None
    assert SettingsProvider(lambda: SimpleNamespace()).get(bare) is None


def test_environment_provider_prefers_earlier_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first named variable that holds a value wins."""
    provider = EnvironmentProvider()
    ref = SecretRef(name="multi", env_vars=("PRIMARY_VAR", "FALLBACK_VAR"))
    monkeypatch.setenv("PRIMARY_VAR", "primary")
    monkeypatch.setenv("FALLBACK_VAR", "fallback")
    assert provider.get(ref) == "primary"


def test_environment_provider_ignores_whitespace_only_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty or whitespace-only environment values are treated as unset."""
    provider = EnvironmentProvider()
    ref = SecretRef(name="multi", env_vars=("PRIMARY_VAR", "FALLBACK_VAR"))
    monkeypatch.setenv("PRIMARY_VAR", "  ")
    monkeypatch.setenv("FALLBACK_VAR", "fallback")
    assert provider.get(ref) == "fallback"


def test_settings_provider_tolerates_attribute_errors() -> None:
    """A missing attribute along the path yields None rather than raising AttributeError."""
    provider = SettingsProvider(lambda: SimpleNamespace(wrong_section=SimpleNamespace()))
    assert provider.get(_ref()) is None


def test_settings_provider_tolerates_broken_settings_source() -> None:
    """A source callable that raises is treated as having no value for the secret."""

    def _broken() -> Any:
        raise RuntimeError("config unreadable")

    assert SettingsProvider(_broken).get(_ref()) is None


def test_vault_provider_rejects_structured_values() -> None:
    """A Vault path returning a map is not a single credential value."""

    class _DummyBroker:
        vault_token = "s.token"

        def __init__(self, value: Any) -> None:
            self.value = value

        def read_secret(self, *args: Any, **kwargs: Any) -> Any:
            return self.value

    assert VaultProvider(broker=_DummyBroker({"nested": "structure"})).get(_ref()) is None
    assert VaultProvider(broker=_DummyBroker("  vault-value  ")).get(_ref()) == "vault-value"


def test_provider_failures_are_contained(keyring_store: FakeKeyring) -> None:
    """A provider that raises is treated as unable to supply, not as fatal."""

    class _FailingBroker:
        vault_token = "s.token"

        def read_secret(self, *args: Any, **kwargs: Any) -> Any:
            raise VaultUnreachableError("vault unreachable")

    assert VaultProvider(broker=_FailingBroker()).get(_ref()) is None

    keyring_store.locked = True
    assert KeyringProvider().get(_ref()) is None


def test_providers_satisfy_the_protocol() -> None:
    """Every built-in provider conforms to the SecretProvider protocol."""
    assert all(
        isinstance(provider, SecretProvider)
        for provider in (
            KeyringProvider(),
            EnvironmentProvider(),
            SettingsProvider(),
            VaultProvider(),
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Audit trail
# ─────────────────────────────────────────────────────────────────────────────


def test_audit_records_which_provider_answered() -> None:
    """Each lookup records the answering provider, so precedence is observable."""
    resolver = SecretResolver(
        providers=[_StubProvider("keyring", None), _StubProvider("environment", "value")]
    )
    resolver.resolve(_ref())
    entry = resolver.audit.entries()[-1]

    assert (entry.credential_id, entry.provider, entry.resolved) == (
        "test.secret",
        "environment",
        True,
    )


def test_audit_records_unresolved_lookups() -> None:
    """A failed lookup is recorded too, so a missing credential is diagnosable."""
    resolver = SecretResolver(providers=[_StubProvider("keyring", None)])
    resolver.resolve(_ref())
    entry = resolver.audit.entries()[-1]

    assert (entry.provider, entry.resolved) == (None, False)


def test_audit_never_stores_the_secret_value() -> None:
    """The audit trail must not retain credential values in any field."""
    resolver = SecretResolver(providers=[_StubProvider("keyring", "super-secret-value")])
    resolver.resolve(_ref())
    entry = resolver.audit.entries()[-1]

    assert "super-secret-value" not in repr(entry)
    assert not hasattr(entry, "value")


def test_audit_debug_log_carries_only_the_credential_identifier(
    caplog: Any,
) -> None:
    """The debug log line records which credential was requested, never its value."""
    import logging

    resolver = SecretResolver(providers=[_StubProvider("keyring", "super-secret-value")])
    with caplog.at_level(logging.DEBUG, logger="devops_cli.security.secrets"):
        resolver.resolve(_ref())

    assert "test.secret" in caplog.text
    assert "super-secret-value" not in caplog.text


def test_audit_log_is_bounded() -> None:
    """The trail evicts oldest entries so long sessions cannot grow without bound."""
    audit = SecretAuditLog(max_entries=3)
    for index in range(10):
        audit.record(f"secret-{index}", "keyring", resolved=True)

    entries = audit.entries()
    assert (len(entries), entries[0].credential_id, entries[-1].credential_id) == (
        3,
        "secret-7",
        "secret-9",
    )


def test_audit_log_clears() -> None:
    """The trail can be reset."""
    audit = SecretAuditLog()
    audit.record("s", "keyring", resolved=True)
    audit.clear()
    assert audit.entries() == []


def test_describe_reports_availability_without_returning_values() -> None:
    """Diagnostics show where a credential lives without exposing it."""
    resolver = SecretResolver(
        providers=[_StubProvider("keyring", None), _StubProvider("environment", "value")]
    )
    assert resolver.describe(_ref()) == {"keyring": False, "environment": True}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Secret registry
# ─────────────────────────────────────────────────────────────────────────────


def test_registry_describes_every_managed_credential() -> None:
    """The registry is the single declaration of where each credential may be found."""
    registry = build_secret_registry()
    grafana = registry["grafana.token"]

    assert (
        grafana.keyring_key == "grafana_token",
        "DEVOPS_CLI_GRAFANA_TOKEN" in grafana.env_vars,
        grafana.vault_path.startswith("secret/data/"),
    ) == (True, True, True)


def test_every_registry_entry_declares_a_keyring_key() -> None:
    """The canonical store must be reachable for every managed credential."""
    registry = build_secret_registry()
    assert all(ref.keyring_key for ref in registry.values())


def test_firecrawl_api_key_is_read_from_its_own_variable_and_from_the_config_file() -> None:
    firecrawl = build_secret_registry()["firecrawl.api_key"]
    assert (firecrawl.keyring_key, firecrawl.env_vars, firecrawl.settings_path) == (
        "firecrawl_api_key",
        ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"),
        "firecrawl.api_key",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Vault authentication
# ─────────────────────────────────────────────────────────────────────────────


def _auth_response(**overrides: Any) -> dict[str, Any]:
    """Build a Vault login response payload."""
    auth = {
        "client_token": "s.token",
        "accessor": "acc-1",
        "lease_duration": 3600,
        "renewable": True,
        "policies": ["default", "devops"],
    }
    auth.update(overrides)
    return {"auth": auth}


def test_approle_login_projects_typed_result(stub_web: StubWeb) -> None:
    """A successful AppRole login yields a typed result with its lease metadata."""
    stub_web.respond("POST", "http://example.com:8200/v1/auth/approle/login", 200, _auth_response())
    result = login_approle("http://example.com:8200", "role", "secret")

    assert (result.method, result.lease_duration, result.renewable, result.policies) == (
        "approle",
        3600,
        True,
        ["default", "devops"],
    )


def test_approle_login_requires_both_credentials() -> None:
    """A partial AppRole credential pair is rejected before any network call."""
    with pytest.raises(VaultAuthenticationError, match="role_id and a secret_id"):
        login_approle("http://example.com:8200", "", "secret")


def test_login_without_client_token_is_an_error(stub_web: StubWeb) -> None:
    """A login response carrying no token is a failure, not a silent success."""
    stub_web.respond("POST", "http://example.com:8200/v1/auth/approle/login", 200, {"auth": {}})
    with pytest.raises(VaultAuthenticationError, match="no client token"):
        login_approle("http://example.com:8200", "role", "secret")


def test_kubernetes_login_uses_projected_service_account_token(
    stub_web: StubWeb, tmp_path: Any
) -> None:
    """The in-cluster ServiceAccount token is read from its projected path."""
    token_file = tmp_path / "token"
    token_file.write_text("sa-jwt-token\n", encoding="utf-8")

    stub_web.respond(
        "POST", "http://example.com:8200/v1/auth/kubernetes/login", 200, _auth_response()
    )
    result = login_kubernetes("http://example.com:8200", "my-role", token_path=str(token_file))

    assert result.method == "kubernetes"
    assert json.loads(stub_web.sent[0].content) == {"role": "my-role", "jwt": "sa-jwt-token"}


def test_kubernetes_login_without_a_token_is_rejected(tmp_path: Any) -> None:
    """Outside a cluster, with no token supplied, login fails with an actionable message."""
    with pytest.raises(VaultAuthenticationError, match="ServiceAccount token"):
        login_kubernetes("http://example.com:8200", "my-role", token_path=str(tmp_path / "absent"))


def test_kubernetes_login_requires_a_role(tmp_path: Any) -> None:
    """A Vault role is mandatory for the Kubernetes auth method."""
    with pytest.raises(VaultAuthenticationError, match="role name"):
        login_kubernetes("http://example.com:8200", "", jwt="jwt")


def test_read_service_account_token_returns_none_outside_a_cluster(tmp_path: Any) -> None:
    """A missing projected token is reported as absent, not as an error."""
    assert read_service_account_token(str(tmp_path / "absent")) is None


def test_auth_result_never_serializes_the_raw_token() -> None:
    """The issued token must not travel in serialized output or trace spans."""
    result = VaultAuthResult(client_token="s.super-secret", method="approle")
    dumped = result.model_dump()

    assert dumped["client_token"] == "<masked-vault-token>"
    assert "s.super-secret" not in str(dumped)
    # The live attribute is still usable in-process.
    assert result.client_token == "s.super-secret"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Lease lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def _registry() -> LeaseRegistry:
    """Build a lease registry pointed at a documentation endpoint."""
    return LeaseRegistry(vault_addr="http://example.com:8200", token="s.token")


def test_lease_remaining_and_expiry() -> None:
    """A lease reports its remaining lifetime and expiry, floored at zero."""
    issued = time.time()
    lease = VaultLease(lease_id="l1", duration_seconds=100, renewable=True, issued_at=issued)

    assert lease.remaining_seconds(now=issued + 40) == pytest.approx(60.0)
    assert (lease.is_expired(now=issued + 40), lease.is_expired(now=issued + 200)) == (
        False,
        True,
    )
    assert lease.remaining_seconds(now=issued + 500) == 0.0


def test_registry_tracks_and_returns_leases() -> None:
    """Issued leases are tracked for lifecycle management."""
    registry = _registry()
    registry.track("lease-1", 3600, renewable=True, secret_path="database/creds/app")

    assert [lease.lease_id for lease in registry.leases()] == ["lease-1"]
    assert registry.get("lease-1") is not None
    assert registry.get("absent") is None


def test_registry_tracks_authentication_lease() -> None:
    """The lease backing a login token is tracked alongside dynamic secrets."""
    registry = _registry()
    auth = VaultAuthResult(
        client_token="s.token", accessor="acc-9", lease_duration=1800, renewable=True
    )
    lease = registry.track_auth(auth)

    assert (lease.lease_id, lease.duration_seconds, lease.renewable) == ("acc-9", 1800, True)


def test_needs_renewal_triggers_below_the_threshold() -> None:
    """Renewal is due once a lease burns past its configured TTL fraction."""
    registry = _registry()
    issued = time.time()
    lease = registry.track("l1", 100, renewable=True)
    lease = lease.model_copy(update={"issued_at": issued})

    assert registry.needs_renewal(lease, now=issued + 50) is False
    assert registry.needs_renewal(lease, now=issued + 80) is True


def test_non_renewable_leases_are_never_renewed() -> None:
    """A lease Vault marked non-renewable is left alone."""
    registry = _registry()
    lease = registry.track("l1", 100, renewable=False)
    assert registry.needs_renewal(lease, now=time.time() + 99) is False


def test_renew_extends_the_lease_and_counts_renewals(stub_web: StubWeb) -> None:
    """A renewed lease records its new lifetime and increments the renewal count."""
    registry = _registry()
    registry.track("lease-1", 100, renewable=True)
    stub_web.respond(
        "POST", "http://example.com:8200/v1/sys/leases/renew", 200, {"lease_duration": 3600}
    )

    renewed = registry.renew("lease-1")

    assert (renewed.duration_seconds, renewed.renewal_count) == (3600, 1)


def test_renewing_an_untracked_or_fixed_lease_is_an_error() -> None:
    """Renewal is refused for unknown leases and for those Vault will not renew."""
    registry = _registry()
    registry.track("fixed", 100, renewable=False)

    with pytest.raises(VaultLeaseError, match="not tracked"):
        registry.renew("absent")
    with pytest.raises(VaultLeaseError, match="not renewable"):
        registry.renew("fixed")


def test_renew_expiring_sweeps_every_lease_despite_a_failure(stub_web: StubWeb) -> None:
    """One failed renewal does not deny the remaining leases their chance."""
    registry = _registry()
    issued = time.time() - 90
    for lease_id in ("a", "b", "c"):
        registry.track(lease_id, 100, renewable=True)
        registry._leases[lease_id] = registry._leases[lease_id].model_copy(
            update={"issued_at": issued}
        )
    registry.track("fresh", 100, renewable=True)

    def handle_renew(req: httpx2.Request) -> httpx2.Response:
        data = json.loads(req.content)
        if data.get("lease_id") == "b":
            return httpx2.Response(400, json={"errors": ["renewal rejected"]})
        return httpx2.Response(200, json={"lease_duration": 3600})

    stub_web.serve(handle_renew)
    report = registry.renew_expiring()

    assert (sorted(report.renewed), report.failed, report.skipped) == (["a", "c"], ["b"], ["fresh"])
    assert report.all_renewed is False


def test_revoke_reports_the_refusal_and_stops_tracking(stub_web: StubWeb) -> None:
    """A refused revocation raises with Vault's status; the lease is dropped from tracking."""
    registry = _registry()
    registry.track("lease-1", 100, renewable=True)
    stub_web.respond(
        "POST", "http://example.com:8200/v1/sys/leases/revoke", 400, {"errors": ["bad request"]}
    )

    with pytest.raises(VaultLeaseError) as raised:
        registry.revoke("lease-1")

    assert (raised.value.status_code, registry.leases()) == (400, [])


def test_revoke_all_clears_the_registry_and_names_the_refusals(stub_web: StubWeb) -> None:
    """Every tracked lease is revoked in one sweep; the ones Vault refused are returned."""
    registry = _registry()
    for lease_id in ("a", "b"):
        registry.track(lease_id, 100, renewable=True)

    def handle_revoke(req: httpx2.Request) -> httpx2.Response:
        data = json.loads(req.content)
        if data.get("lease_id") == "b":
            return httpx2.Response(403, json={"errors": ["refused"]})
        return httpx2.Response(204)

    stub_web.serve(handle_revoke)
    refused = registry.revoke_all()

    assert (refused, registry.leases()) == (["b"], [])


def test_renew_token_returns_new_lifetime(stub_web: StubWeb) -> None:
    """Renewing the client token reports its refreshed lifetime."""
    registry = _registry()
    stub_web.respond(
        "POST",
        "http://example.com:8200/v1/auth/token/renew-self",
        200,
        {"auth": {"lease_duration": 7200}},
    )
    assert registry.renew_token() == 7200


# ─────────────────────────────────────────────────────────────────────────────
# 7. Same-origin and error wrapping at the HTTP boundary
# ─────────────────────────────────────────────────────────────────────────────


def test_post_routes_through_the_egress_validated_broker(stub_web: StubWeb) -> None:
    """Vault calls go through the shared broker, which enforces egress validation."""
    from devops_cli.security.vault_lease import _post

    stub_web.respond("POST", "http://example.com:8200/v1/sys/leases/renew", 200, {"ok": True})
    result = _post("http://example.com:8200/", "sys/leases/renew", {"a": 1}, {})

    assert result == {"ok": True}
    sent = stub_web.sent[0]
    assert (sent.method, str(sent.url)) == ("POST", "http://example.com:8200/v1/sys/leases/renew")
    policy = sent.extensions[CONST_HTTP_EGRESS_POLICY_EXTENSION]
    policy("http://example.com:8200/v1/sys/leases/renew")
    with pytest.raises(VaultOperationError, match=re.escape("https://example.com")):
        policy("https://example.com/v1/sys/leases/renew")


def test_post_reports_an_unreachable_vault(stub_web: StubWeb) -> None:
    """A transport failure becomes a typed error rather than a raw httpx2 exception."""
    from devops_cli.security.vault_lease import _post

    stub_web.fail("http://example.com:8200/v1/sys/leases/renew", httpx2.ConnectTimeout("timed out"))
    with pytest.raises(VaultUnreachableError, match="did not answer: ConnectTimeout"):
        _post("http://example.com:8200", "sys/leases/renew", {}, {})


def test_post_raises_on_error_status(stub_web: StubWeb) -> None:
    """A Vault error status becomes a typed lease error naming the path."""
    from devops_cli.security.vault_lease import _post

    stub_web.respond("POST", "http://example.com:8200/v1/sys/leases/renew", 403, {})
    with pytest.raises(VaultLeaseError, match="status 403") as raised:
        _post("http://example.com:8200", "sys/leases/renew", {}, {})
    assert raised.value.status_code == 403


def test_post_tolerates_an_empty_body(stub_web: StubWeb) -> None:
    """A successful call with no body yields an empty mapping, not an error."""
    from devops_cli.security.vault_lease import _post

    stub_web.respond("POST", "http://example.com:8200/v1/sys/leases/revoke", 204)
    assert _post("http://example.com:8200", "sys/leases/revoke", {}, {}) == {}


def test_post_ignores_a_non_mapping_body(stub_web: StubWeb) -> None:
    """A response body that is not a JSON object is treated as empty."""
    from devops_cli.security.vault_lease import _post

    stub_web.page(
        "http://example.com:8200/v1/sys/leases/renew",
        '["unexpected"]',
        headers={"content-type": "application/json"},
    )
    assert _post("http://example.com:8200", "sys/leases/renew", {}, {}) == {}


def test_registry_headers_carry_token_and_namespace() -> None:
    """Authenticated Vault calls send the token and namespace headers."""
    registry = LeaseRegistry(
        vault_addr="http://example.com:8200", token="s.token", namespace="team-a"
    )
    headers = registry._headers()

    assert (headers["X-Vault-Token"], headers["X-Vault-Namespace"]) == ("s.token", "team-a")


def test_registry_headers_always_carry_the_token() -> None:
    """A registry cannot exist without a token, so every call it makes sends one."""
    headers = LeaseRegistry(vault_addr="http://example.com:8200", token="s.token")._headers()
    assert (headers["X-Vault-Token"], "X-Vault-Namespace" in headers) == ("s.token", False)


def test_revoke_self_sends_the_token_to_its_own_vault(stub_web: StubWeb) -> None:
    """Logout's revoke-self call carries the stored token and namespace."""
    from devops_cli.security.vault_lease import revoke_self

    stub_web.respond("POST", "http://example.com:8200/v1/auth/token/revoke-self", 204)
    revoke_self("http://example.com:8200", "s.token", "team-a")

    assert len(stub_web.sent) == 1
    assert (
        str(stub_web.sent[0].url),
        stub_web.sent[0].headers.get("X-Vault-Token"),
        stub_web.sent[0].headers.get("X-Vault-Namespace"),
    ) == (
        "http://example.com:8200/v1/auth/token/revoke-self",
        "s.token",
        "team-a",
    )
