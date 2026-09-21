"""Unit tests for unified secret resolution, the access audit trail, and Vault leases."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.vault import VaultAuthenticationError, VaultLeaseError
from devops_cli.models.vault import VaultAuthResult, VaultLease
from devops_cli.security.secrets import (
    CallableProvider,
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
    reset_resolver,
)
from devops_cli.security.vault_lease import (
    LeaseRegistry,
    login_approle,
    login_kubernetes,
    read_service_account_token,
    transit_decrypt,
    transit_encrypt,
)


@pytest.fixture(autouse=True)
def _reset_resolver_singleton() -> Any:
    """Guarantee no resolver state leaks between tests."""
    reset_resolver()
    yield
    reset_resolver()


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


def test_keyring_outranks_environment_and_settings() -> None:
    """The OS keyring is canonical and wins over every other source."""
    settings = SimpleNamespace(section=SimpleNamespace(value="from-settings"))
    resolver = build_default_resolver(settings_source=lambda: settings)

    with (
        patch("devops_cli.config.settings.get_keyring_secret", return_value="from-keyring"),
        patch.dict("os.environ", {"TEST_SECRET": "from-env"}),
        patch.object(VaultProvider, "get", return_value=None),
    ):
        assert resolver.resolve(_ref()) == "from-keyring"


def test_environment_outranks_settings() -> None:
    """Environment variables override committed configuration for every secret."""
    settings = SimpleNamespace(section=SimpleNamespace(value="from-settings"))
    resolver = build_default_resolver(settings_source=lambda: settings)

    with (
        patch("devops_cli.config.settings.get_keyring_secret", return_value=None),
        patch.dict("os.environ", {"TEST_SECRET": "from-env"}),
        patch.object(VaultProvider, "get", return_value=None),
    ):
        assert resolver.resolve(_ref()) == "from-env"


def test_settings_answer_only_as_last_resort() -> None:
    """Configuration supplies the value when nothing above it can."""
    settings = SimpleNamespace(section=SimpleNamespace(value="from-settings"))
    resolver = build_default_resolver(settings_source=lambda: settings)

    with (
        patch("devops_cli.config.settings.get_keyring_secret", return_value=None),
        patch.dict("os.environ", {"TEST_SECRET": ""}),
        patch.object(VaultProvider, "get", return_value=None),
    ):
        assert resolver.resolve(_ref()) == "from-settings"


def test_cached_resolver_never_serves_a_stale_settings_snapshot() -> None:
    """A per-call settings source rebinds configuration on every lookup.

    The process-wide resolver is cached, so capturing settings at construction would pin
    whichever configuration happened to be loaded first.
    """
    resolver = get_resolver()
    first = SimpleNamespace(section=SimpleNamespace(value="first-config"))
    second = SimpleNamespace(section=SimpleNamespace(value="second-config"))

    with (
        patch("devops_cli.config.settings.get_keyring_secret", return_value=None),
        patch.dict("os.environ", {"TEST_SECRET": ""}),
        patch.object(VaultProvider, "get", return_value=None),
    ):
        resolved = (
            resolver.resolve(_ref(), settings_source=lambda: first),
            resolver.resolve(_ref(), settings_source=lambda: second),
        )

    assert resolved == ("first-config", "second-config")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Individual providers
# ─────────────────────────────────────────────────────────────────────────────


def test_providers_skip_references_they_cannot_serve() -> None:
    """A provider with no configured source for a secret declines rather than guessing."""
    bare = SecretRef(name="bare")
    assert KeyringProvider().get(bare) is None
    assert EnvironmentProvider().get(bare) is None
    assert SettingsProvider(lambda: SimpleNamespace()).get(bare) is None
    assert VaultProvider(broker=MagicMock()).get(bare) is None


def test_environment_provider_prefers_earlier_variables() -> None:
    """Environment variables are consulted in declaration order."""
    ref = _ref(env_vars=("PRIMARY_VAR", "FALLBACK_VAR"))
    with patch.dict("os.environ", {"PRIMARY_VAR": "primary", "FALLBACK_VAR": "fallback"}):
        assert EnvironmentProvider().get(ref) == "primary"
    with patch.dict("os.environ", {"PRIMARY_VAR": "  ", "FALLBACK_VAR": "fallback"}):
        assert EnvironmentProvider().get(ref) == "fallback"


def test_settings_provider_walks_dotted_paths() -> None:
    """Nested configuration attributes are reachable through a dotted path."""
    settings = SimpleNamespace(section=SimpleNamespace(value="nested"))
    assert SettingsProvider(lambda: settings).get(_ref()) == "nested"
    assert SettingsProvider(lambda: SimpleNamespace()).get(_ref()) is None


def test_settings_provider_tolerates_unloadable_settings() -> None:
    """A configuration load failure degrades to None rather than breaking resolution."""

    def _broken() -> Any:
        raise RuntimeError("config unreadable")

    assert SettingsProvider(_broken).get(_ref()) is None


def test_vault_provider_rejects_structured_values() -> None:
    """A Vault path returning a map is not a single credential value."""
    broker = MagicMock()
    broker.get_secret.return_value = {"nested": "structure"}
    assert VaultProvider(broker=broker).get(_ref()) is None

    broker.get_secret.return_value = "  vault-value  "
    assert VaultProvider(broker=broker).get(_ref()) == "vault-value"


def test_provider_failures_are_contained() -> None:
    """A provider that raises is treated as unable to supply, not as fatal."""
    broker = MagicMock()
    broker.get_secret.side_effect = RuntimeError("vault unreachable")
    assert VaultProvider(broker=broker).get(_ref()) is None

    with patch("devops_cli.config.settings.get_keyring_secret", side_effect=RuntimeError("locked")):
        assert KeyringProvider().get(_ref()) is None


def test_callable_provider_wraps_bespoke_lookups() -> None:
    """A bespoke lookup integrates into the chain and contains its own failures."""
    assert CallableProvider("tool", lambda ref: "tool-value").get(_ref()) == "tool-value"

    def _explode(ref: SecretRef) -> str | None:
        raise RuntimeError("cli not installed")

    assert CallableProvider("tool", _explode).get(_ref()) is None


def test_providers_satisfy_the_protocol() -> None:
    """Every built-in provider conforms to the SecretProvider protocol."""
    assert all(
        isinstance(provider, SecretProvider)
        for provider in (
            KeyringProvider(),
            EnvironmentProvider(),
            SettingsProvider(),
            VaultProvider(),
            CallableProvider("tool", lambda ref: None),
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
    """The debug log line records which credential was requested, never its value.

    CodeQL flagged the previous parameter name as clear-text logging of a secret. The
    parameter holds an identifier such as `github.token`; this pins that the emitted log
    record cannot contain the credential value.
    """
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
    from devops_cli.config import options as opt

    registry = build_secret_registry(opt.KEYRING_KEYS)
    github = registry[opt.GITHUB_TOKEN]

    assert github.keyring_key == opt.KEYRING_KEYS[opt.GITHUB_TOKEN]
    assert "DEVOPS_CLI_GITHUB_TOKEN" in github.env_vars
    assert github.vault_path.startswith("secret/data/")


def test_every_registry_entry_declares_a_keyring_key() -> None:
    """The canonical store must be reachable for every managed credential."""
    from devops_cli.config import options as opt

    registry = build_secret_registry(opt.KEYRING_KEYS)
    assert all(ref.keyring_key for ref in registry.values())


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


def test_approle_login_projects_typed_result() -> None:
    """A successful AppRole login yields a typed result with its lease metadata."""
    with patch("devops_cli.security.vault_lease._post", return_value=_auth_response()):
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


def test_login_without_client_token_is_an_error() -> None:
    """A login response carrying no token is a failure, not a silent success."""
    with patch("devops_cli.security.vault_lease._post", return_value={"auth": {}}):
        with pytest.raises(VaultAuthenticationError, match="no client token"):
            login_approle("http://example.com:8200", "role", "secret")


def test_kubernetes_login_uses_projected_service_account_token(tmp_path: Any) -> None:
    """The in-cluster ServiceAccount token is read from its projected path."""
    token_file = tmp_path / "token"
    token_file.write_text("sa-jwt-token\n", encoding="utf-8")

    with patch("devops_cli.security.vault_lease._post", return_value=_auth_response()) as mock_post:
        result = login_kubernetes("http://example.com:8200", "my-role", token_path=str(token_file))

    assert result.method == "kubernetes"
    assert mock_post.call_args[0][2] == {"role": "my-role", "jwt": "sa-jwt-token"}


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


def test_renew_extends_the_lease_and_counts_renewals() -> None:
    """A renewed lease records its new lifetime and increments the renewal count."""
    registry = _registry()
    registry.track("lease-1", 100, renewable=True)

    with patch("devops_cli.security.vault_lease._post", return_value={"lease_duration": 3600}):
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


def test_renew_expiring_sweeps_every_lease_despite_a_failure() -> None:
    """One failed renewal does not deny the remaining leases their chance."""
    registry = _registry()
    issued = time.time() - 90
    for lease_id in ("a", "b", "c"):
        registry.track(lease_id, 100, renewable=True)
        registry._leases[lease_id] = registry._leases[lease_id].model_copy(
            update={"issued_at": issued}
        )
    registry.track("fresh", 100, renewable=True)

    def _renew(addr: str, path: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        if payload.get("lease_id") == "b":
            raise VaultLeaseError("renewal rejected")
        return {"lease_duration": 3600}

    with patch("devops_cli.security.vault_lease._post", side_effect=_renew):
        report = registry.renew_expiring()

    assert (sorted(report.renewed), report.failed, report.skipped) == (["a", "c"], ["b"], ["fresh"])
    assert report.all_renewed is False


def test_revoke_stops_tracking_even_when_vault_refuses() -> None:
    """A lease is dropped from tracking whether or not Vault accepted the revocation."""
    registry = _registry()
    registry.track("lease-1", 100, renewable=True)

    with patch("devops_cli.security.vault_lease._post", side_effect=VaultLeaseError("nope")):
        revoked = registry.revoke("lease-1")

    assert (revoked, registry.leases()) == (False, [])


def test_revoke_all_clears_the_registry() -> None:
    """Every tracked lease can be revoked in one sweep."""
    registry = _registry()
    for lease_id in ("a", "b"):
        registry.track(lease_id, 100, renewable=True)

    with patch("devops_cli.security.vault_lease._post", return_value={}):
        count = registry.revoke_all()

    assert (count, registry.leases()) == (2, [])


def test_renew_token_returns_new_lifetime() -> None:
    """Renewing the client token reports its refreshed lifetime."""
    registry = _registry()
    with patch(
        "devops_cli.security.vault_lease._post",
        return_value={"auth": {"lease_duration": 7200}},
    ):
        assert registry.renew_token() == 7200


# ─────────────────────────────────────────────────────────────────────────────
# 7. Transit envelope encryption
# ─────────────────────────────────────────────────────────────────────────────


def test_transit_encrypt_sends_base64_and_returns_ciphertext() -> None:
    """Plaintext is base64 encoded for Transit, which returns opaque ciphertext."""
    with patch(
        "devops_cli.security.vault_lease._post",
        return_value={"data": {"ciphertext": "vault:v1:abcd"}},
    ) as mock_post:
        ciphertext = transit_encrypt("http://example.com:8200", "devops", "secret-value")

    assert ciphertext == "vault:v1:abcd"
    assert mock_post.call_args[0][2]["plaintext"] == "c2VjcmV0LXZhbHVl"


def test_transit_decrypt_returns_plaintext() -> None:
    """Ciphertext round-trips back to the original plaintext."""
    with patch(
        "devops_cli.security.vault_lease._post",
        return_value={"data": {"plaintext": "c2VjcmV0LXZhbHVl"}},
    ):
        assert transit_decrypt("http://example.com:8200", "devops", "vault:v1:abcd") == (
            "secret-value"
        )


def test_transit_failures_are_typed() -> None:
    """A Transit response missing its payload is an error, not a silent empty value."""
    with patch("devops_cli.security.vault_lease._post", return_value={"data": {}}):
        with pytest.raises(VaultLeaseError, match="no ciphertext"):
            transit_encrypt("http://example.com:8200", "devops", "value")
        with pytest.raises(VaultLeaseError, match="no plaintext"):
            transit_decrypt("http://example.com:8200", "devops", "vault:v1:abcd")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Vault HTTP boundary
# ─────────────────────────────────────────────────────────────────────────────


def _broker_response(status: int = 200, payload: Any = None, content: bytes = b"{}") -> Any:
    """Build a stub HTTP response from the shared broker."""
    response = MagicMock()
    response.status_code = status
    response.content = content
    response.json.return_value = payload if payload is not None else {}
    return response


def test_post_routes_through_the_egress_validated_broker() -> None:
    """Vault calls go through the shared broker, which enforces egress validation."""
    from devops_cli.security.vault_lease import _post

    mock_broker = MagicMock()
    mock_broker.request.return_value = _broker_response(payload={"ok": True})

    with patch("devops_cli.http.broker.get_broker", return_value=mock_broker):
        result = _post("http://example.com:8200/", "sys/leases/renew", {"a": 1}, {})

    assert result == {"ok": True}
    method, url = mock_broker.request.call_args[0]
    assert (method, url) == ("POST", "http://example.com:8200/v1/sys/leases/renew")
    assert mock_broker.request.call_args.kwargs["allow_private_network"] is True


def test_post_raises_on_error_status() -> None:
    """A Vault error status becomes a typed lease error naming the path."""
    from devops_cli.security.vault_lease import _post

    mock_broker = MagicMock()
    mock_broker.request.return_value = _broker_response(status=403)

    with patch("devops_cli.http.broker.get_broker", return_value=mock_broker):
        with pytest.raises(VaultLeaseError, match="status 403"):
            _post("http://example.com:8200", "sys/leases/renew", {}, {})


def test_post_tolerates_an_empty_body() -> None:
    """A successful call with no body yields an empty mapping, not an error."""
    from devops_cli.security.vault_lease import _post

    mock_broker = MagicMock()
    mock_broker.request.return_value = _broker_response(content=b"")

    with patch("devops_cli.http.broker.get_broker", return_value=mock_broker):
        assert _post("http://example.com:8200", "sys/leases/revoke", {}, {}) == {}


def test_post_ignores_a_non_mapping_body() -> None:
    """A response body that is not a JSON object is treated as empty."""
    from devops_cli.security.vault_lease import _post

    mock_broker = MagicMock()
    mock_broker.request.return_value = _broker_response(payload=["unexpected"])

    with patch("devops_cli.http.broker.get_broker", return_value=mock_broker):
        assert _post("http://example.com:8200", "sys/leases/renew", {}, {}) == {}


def test_registry_headers_carry_token_and_namespace() -> None:
    """Authenticated Vault calls send the token and namespace headers."""
    registry = LeaseRegistry(
        vault_addr="http://example.com:8200", token="s.token", namespace="team-a"
    )
    headers = registry._headers()

    assert (headers["X-Vault-Token"], headers["X-Vault-Namespace"]) == ("s.token", "team-a")


def test_registry_headers_omit_absent_credentials() -> None:
    """An unauthenticated registry sends no token or namespace header."""
    headers = LeaseRegistry(vault_addr="http://example.com:8200")._headers()
    assert "X-Vault-Token" not in headers
    assert "X-Vault-Namespace" not in headers
