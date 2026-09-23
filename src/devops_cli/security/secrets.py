"""Unified secret resolution across OS keyring, Vault, environment, and configuration.

Every credential lookup in the codebase resolves through :class:`SecretResolver`, which
walks an ordered provider chain in a single pass and records an audit entry naming the
logical secret and the provider that satisfied it — never the value.

Before this layer, each credential carried its own hand-written fallback ladder, so two
secrets could disagree about whether the environment outranked the keyring, and no lookup
was observable.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from devops_cli.config.constants import (
    CONST_SECRET_AUDIT_MAX_ENTRIES,
    CONST_SECRET_PROVIDER_ENVIRONMENT,
    CONST_SECRET_PROVIDER_KEYRING,
    CONST_SECRET_PROVIDER_SETTINGS,
    CONST_SECRET_PROVIDER_TOOL,
    CONST_SECRET_PROVIDER_VAULT,
    CONST_VAULT_SECRET_MOUNT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Secret Reference & Audit Records
# =============================================================================


@dataclass(frozen=True)
class SecretRef:
    """Describes where one logical secret may be found, in resolution order."""

    name: str
    keyring_key: str | None = None
    env_vars: tuple[str, ...] = ()
    settings_path: str | None = None
    vault_path: str | None = None
    vault_key: str | None = None


@dataclass(frozen=True)
class SecretAccess:
    """One recorded credential lookup.

    `credential_id` is the credential's *identifier* (for example ``github.token``), not
    its value. The value is never carried by this record, logged, or rendered.
    """

    credential_id: str
    provider: str | None
    resolved: bool
    timestamp: str


class SecretAuditLog:
    """Bounded in-memory audit trail of credential accesses.

    Records which logical secret was requested and which provider answered, so a
    misconfigured precedence or an unexpected environment fallback is observable. The
    value is never stored, logged, or rendered.
    """

    def __init__(self, max_entries: int = CONST_SECRET_AUDIT_MAX_ENTRIES) -> None:
        self._entries: list[SecretAccess] = []
        self._max_entries = max_entries

    def record(self, credential_id: str, provider: str | None, resolved: bool) -> SecretAccess:
        """Append an access record, evicting the oldest entry beyond the cap.

        `credential_id` identifies which credential was requested (``github.token``); the
        credential's value is never passed to, stored by, or logged from this method.
        """
        entry = SecretAccess(
            credential_id=credential_id,
            provider=provider,
            resolved=resolved,
            timestamp=datetime.now(UTC).isoformat(),
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            del self._entries[: len(self._entries) - self._max_entries]

        logger.debug(
            "Credential %r resolved=%s via provider=%s",
            credential_id,
            resolved,
            provider or "none",
        )
        return entry

    def entries(self) -> list[SecretAccess]:
        """Return a copy of the recorded accesses, oldest first."""
        return list(self._entries)

    def clear(self) -> None:
        """Discard all recorded accesses."""
        self._entries.clear()


# =============================================================================
# Providers
# =============================================================================


@runtime_checkable
class SecretProvider(Protocol):
    """A source that can answer a secret lookup."""

    @property
    def name(self) -> str:
        """Stable provider identifier recorded in the audit trail."""
        ...

    def get(self, ref: SecretRef) -> str | None:
        """Return the secret value, or ``None`` when this provider cannot supply it."""
        ...


class KeyringProvider:
    """Resolves secrets from the OS keyring, the canonical store for this project."""

    @property
    def name(self) -> str:
        """Provider identifier."""
        return CONST_SECRET_PROVIDER_KEYRING

    def get(self, ref: SecretRef) -> str | None:
        """Look the secret up by its keyring key, when it defines one."""
        if not ref.keyring_key:
            return None
        from devops_cli.config.settings import get_keyring_secret

        try:
            return get_keyring_secret(ref.keyring_key)
        except Exception as exc:
            logger.debug("Keyring lookup failed for %s: %s", ref.name, exc)
            return None


class EnvironmentProvider:
    """Resolves secrets from environment variables, for non-interactive CI runners."""

    @property
    def name(self) -> str:
        """Provider identifier."""
        return CONST_SECRET_PROVIDER_ENVIRONMENT

    def get(self, ref: SecretRef) -> str | None:
        """Return the first environment variable that is set and non-empty."""
        for var in ref.env_vars:
            value = os.environ.get(var, "").strip()
            if value:
                return value
        return None


class SettingsProvider:
    """Resolves secrets declared directly in configuration.

    Retained only for values a user may legitimately place in `config.yaml`; it is
    deliberately last in the chain so a keyring or Vault entry always wins.

    Settings are resolved through a callable rather than captured at construction, so the
    process-wide resolver can be cached without pinning a stale configuration snapshot.
    """

    def __init__(self, settings_source: Callable[[], Any] | None = None) -> None:
        self._settings_source = settings_source

    @property
    def name(self) -> str:
        """Provider identifier."""
        return CONST_SECRET_PROVIDER_SETTINGS

    def _settings(self) -> Any:
        """Resolve the current settings object."""
        if self._settings_source is not None:
            return self._settings_source()
        from devops_cli.config.settings import load_settings

        return load_settings()

    def get(self, ref: SecretRef) -> str | None:
        """Walk the dotted settings path, returning the value when present."""
        if not ref.settings_path:
            return None

        try:
            current: Any = self._settings()
        except Exception as exc:
            logger.debug("Settings unavailable while resolving %s: %s", ref.name, exc)
            return None

        for attribute in ref.settings_path.split("."):
            current = getattr(current, attribute, None)
            if current is None:
                return None
        text = str(current).strip()
        return text or None


class VaultProvider:
    """Resolves secrets from HashiCorp Vault's KV-v2 engine."""

    def __init__(self, broker: Any | None = None) -> None:
        self._broker = broker

    @property
    def name(self) -> str:
        """Provider identifier."""
        return CONST_SECRET_PROVIDER_VAULT

    def _resolve_broker(self) -> Any | None:
        """Construct the Vault broker lazily, tolerating an unconfigured environment."""
        if self._broker is not None:
            return self._broker
        try:
            from devops_cli.security.vault_broker import VaultSecretBroker

            self._broker = VaultSecretBroker()
        except Exception as exc:
            logger.debug("Vault broker unavailable: %s", exc)
            return None
        return self._broker

    def get(self, ref: SecretRef) -> str | None:
        """Fetch the secret from Vault when the reference declares a path."""
        if not ref.vault_path:
            return None
        broker = self._resolve_broker()
        if broker is None:
            return None

        try:
            value = broker.get_secret(ref.vault_path, key=ref.vault_key)
        except Exception as exc:
            logger.debug("Vault lookup failed for %s: %s", ref.name, exc)
            return None

        if value is None or isinstance(value, dict | list):
            return None
        text = str(value).strip()
        return text or None


class CallableProvider:
    """Adapts a bespoke lookup, such as delegating to an authenticated external CLI."""

    def __init__(self, name: str, lookup: Callable[[SecretRef], str | None]) -> None:
        self._name = name
        self._lookup = lookup

    @property
    def name(self) -> str:
        """Provider identifier."""
        return self._name

    def get(self, ref: SecretRef) -> str | None:
        """Invoke the wrapped lookup, treating any failure as "cannot supply"."""
        try:
            return self._lookup(ref)
        except Exception as exc:
            logger.debug("Provider %s failed for %s: %s", self._name, ref.name, exc)
            return None


# =============================================================================
# Resolver
# =============================================================================


@dataclass
class SecretResolver:
    """Resolves secrets through an ordered provider chain in a single pass."""

    providers: list[SecretProvider] = field(default_factory=list)
    audit: SecretAuditLog = field(default_factory=SecretAuditLog)

    def resolve(
        self, ref: SecretRef, settings_source: Callable[[], Any] | None = None
    ) -> str | None:
        """Return the first value any provider supplies, recording which one answered.

        `settings_source` binds the configuration this particular lookup should consult,
        so a cached resolver never serves a stale settings snapshot.
        """
        for provider in self._chain(settings_source):
            value = provider.get(ref)
            if value:
                self.audit.record(ref.name, provider.name, resolved=True)
                return value

        self.audit.record(ref.name, None, resolved=False)
        return None

    def _chain(self, settings_source: Callable[[], Any] | None) -> list[SecretProvider]:
        """Return the provider chain, rebinding the settings provider when asked."""
        if settings_source is None:
            return self.providers
        return [
            SettingsProvider(settings_source)
            if isinstance(provider, SettingsProvider)
            else provider
            for provider in self.providers
        ]

    def describe(
        self, ref: SecretRef, settings_source: Callable[[], Any] | None = None
    ) -> dict[str, bool]:
        """Report which providers can currently supply a secret, without returning it.

        Used by diagnostics so an operator can see where a credential is coming from
        without the value ever reaching the terminal.
        """
        return {provider.name: bool(provider.get(ref)) for provider in self._chain(settings_source)}


def build_default_resolver(
    settings_source: Callable[[], Any] | None = None,
    extra_providers: Sequence[SecretProvider] | None = None,
) -> SecretResolver:
    """Construct the standard provider chain.

    Order is deliberate and uniform for every secret: the OS keyring is canonical, Vault
    serves centrally managed credentials, the environment supports non-interactive CI,
    and plain configuration is the last resort.
    """
    providers: list[SecretProvider] = [KeyringProvider(), VaultProvider(), EnvironmentProvider()]
    providers.extend(extra_providers or [])
    providers.append(SettingsProvider(settings_source))
    return SecretResolver(providers=providers)


_DEFAULT_RESOLVER: SecretResolver | None = None


def get_resolver(settings_source: Callable[[], Any] | None = None) -> SecretResolver:
    """Return the process-wide resolver, constructing it on first use."""
    global _DEFAULT_RESOLVER
    if _DEFAULT_RESOLVER is None:
        _DEFAULT_RESOLVER = build_default_resolver(settings_source)
    return _DEFAULT_RESOLVER


def reset_resolver() -> None:
    """Reset the process-wide resolver for clean test fixture isolation."""
    global _DEFAULT_RESOLVER
    _DEFAULT_RESOLVER = None


def resolve_secret(ref: SecretRef, settings_source: Callable[[], Any] | None = None) -> str | None:
    """Resolve one secret through the process-wide provider chain."""
    return get_resolver(settings_source).resolve(ref)


def audit_entries() -> list[SecretAccess]:
    """Return the recorded credential accesses from the process-wide resolver."""
    return get_resolver().audit.entries()


def iter_provider_names(providers: Iterable[SecretProvider]) -> list[str]:
    """List provider identifiers in resolution order."""
    return [provider.name for provider in providers]


__all__ = [
    "CONST_SECRET_PROVIDER_TOOL",
    "CallableProvider",
    "EnvironmentProvider",
    "KeyringProvider",
    "SecretAccess",
    "SecretAuditLog",
    "SecretProvider",
    "SecretRef",
    "SecretResolver",
    "SettingsProvider",
    "VaultProvider",
    "audit_entries",
    "build_default_resolver",
    "build_secret_registry",
    "get_resolver",
    "iter_provider_names",
    "reset_resolver",
    "resolve_secret",
]


# =============================================================================
# Secret Registry
# =============================================================================


def _vault_path_for(name: str) -> str:
    """Build the conventional Vault KV-v2 path for a managed credential."""
    return f"{CONST_VAULT_SECRET_MOUNT}/{name}"


def build_secret_registry(keyring_keys: dict[str, str]) -> dict[str, SecretRef]:
    """Describe every managed credential and where it may be found.

    Declaring the sources in one table is what replaced the per-credential fallback
    ladders: precedence is now a property of the resolver, identical for every secret,
    rather than something each getter re-decided for itself.
    """
    from devops_cli.config import options as opt

    definitions: tuple[tuple[str, str, tuple[str, ...], str | None], ...] = (
        (opt.GITHUB_TOKEN, "github_token", ("DEVOPS_CLI_GITHUB_TOKEN", "GITHUB_TOKEN"), None),
        (opt.GRAFANA_TOKEN, "grafana_token", ("DEVOPS_CLI_GRAFANA_TOKEN",), None),
        (opt.GRAFANA_PASSWORD, "grafana_password", ("DEVOPS_CLI_GRAFANA_PASSWORD",), None),
        (opt.ARGOCD_TOKEN, "argocd_token", ("DEVOPS_CLI_ARGOCD_TOKEN",), None),
        (opt.ARGOCD_PASSWORD, "argocd_password", ("DEVOPS_CLI_ARGOCD_PASSWORD",), None),
        (opt.AI_API_KEY, "ai_api_key", ("DEVOPS_CLI_AI_API_KEY",), None),
        (opt.QDRANT_API_KEY, "qdrant_api_key", ("DEVOPS_CLI_QDRANT_API_KEY",), "qdrant.api_key"),
        (
            opt.VALKEY_PASSWORD,
            "valkey_password",
            ("DEVOPS_CLI_VALKEY_PASSWORD",),
            "valkey.password",
        ),
        (
            opt.TELEMETRY_LOGFIRE_TOKEN,
            "logfire_token",
            ("DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN", "LOGFIRE_TOKEN"),
            "telemetry.logfire_token",
        ),
    )

    return {
        option: SecretRef(
            name=option,
            keyring_key=keyring_keys.get(option),
            env_vars=env_vars,
            settings_path=settings_path,
            vault_path=_vault_path_for(vault_name),
            vault_key=vault_name,
        )
        for option, vault_name, env_vars, settings_path in definitions
    }
