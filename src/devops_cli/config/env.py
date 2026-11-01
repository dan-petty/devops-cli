"""The environment variables that set devops-cli, as views of the settings that declare them.

A settings field declares that a variable sets it with a `Variable` marker, and its description
with `Field(description=...)`. A credential is declared once in `CREDENTIALS`. Every list of
settings, variables and keyring entries that a command, the docs or the secret resolver reads is
derived here from those two declarations (#2444).
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_PROJECT_CONFIG_ENV
from devops_cli.config.defaults import DEFAULT_OTEL_ENDPOINT

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

ENV_AGENT_GRANT = "DEVOPS_CLI_AGENT_GRANT"
# OpenTelemetry's own name for the collector. devops-cli reads it only when its configuration
# names no `telemetry.endpoint`.
ENV_OTEL_EXPORTER_OTLP_ENDPOINT = "OTEL_EXPORTER_OTLP_ENDPOINT"

_VARIABLE_PREFIX = "DEVOPS_CLI"


@dataclass(frozen=True)
class Variable:
    """Marks a settings field that an environment variable sets.

    The variable is `DEVOPS_CLI_` and the field's dotted key in upper case, with `_` for `.`. On a
    field that holds a section, `fields` names the section's fields that a variable sets, for a
    section model that several fields share, and `segment` takes the place of the field's name in
    the variables of the fields under it.
    """

    fields: tuple[str, ...] = ()
    segment: str | None = None


@dataclass(frozen=True)
class Credential:
    """A secret setting: the OS keyring holds it, and a variable or Vault can give it.

    `aliases` are other variables that hold it, such as the name its own tool reads. `in_file`
    lets the config file hold it, in the settings field of the same key. `keyring` names the
    keyring entry when it is not the key with `_` for `.`.
    """

    key: str
    description: str
    aliases: tuple[str, ...] = ()
    in_file: bool = False
    keyring: str | None = None

    @property
    def keyring_name(self) -> str:
        return self.keyring or self.key.replace(".", "_")

    @property
    def env_vars(self) -> tuple[str, ...]:
        """The variables that hold the credential, in the order the resolver reads them."""
        return (_variable_name(self.key.split(".")), *self.aliases)


CREDENTIALS: tuple[Credential, ...] = (
    Credential("grafana.token", "Grafana API token (stored in OS keyring)"),
    Credential("grafana.password", "Grafana admin password (stored in OS keyring)"),
    Credential("argocd.token", "ArgoCD API token (stored in OS keyring)"),
    Credential("argocd.password", "ArgoCD admin password (stored in OS keyring)"),
    Credential(
        "argocd.github_app_private_key",
        "PEM private key of the GitHub App that Argo CD's GitHub notifier acts as (stored in OS "
        "keyring)",
    ),
    Credential("ai.api_key", "AI API key (stored in OS keyring)"),
    Credential("qdrant.api_key", "Qdrant API key (stored in OS keyring)", in_file=True),
    Credential(
        "valkey.password", "Valkey authentication password (stored in OS keyring)", in_file=True
    ),
    Credential("runs.index_password", "Run index Valkey password (stored in OS keyring)"),
    Credential(
        "gitea.admin_password",
        "Password of Gitea's admin user, which `devops k8s push-secrets` writes to Secret "
        "gitea/gitea-admin (stored in OS keyring)",
    ),
    Credential(
        "telemetry.logfire_token",
        "Logfire write token (stored in OS keyring)",
        aliases=("LOGFIRE_TOKEN",),
        in_file=True,
        keyring="logfire_token",
    ),
    Credential(
        "cloudflare.api_token",
        "Cloudflare API Token (stored in OS keyring)",
        aliases=("CLOUDFLARE_API_TOKEN",),
    ),
    Credential(
        "cloudflare.tunnel_token",
        "Cloudflare Tunnel token that `devops k8s push-secrets` writes to the cluster (stored in "
        "OS keyring)",
    ),
    Credential(
        "service.webhook_secrets",
        "JSON map of repo to webhook HMAC secret for incoming GitHub webhooks",
    ),
    Credential(
        "service.github_app.private_key",
        "PEM private key of the GitHub App (stored in OS keyring). A process whose environment "
        "holds it acts as the App",
    ),
    Credential(
        "firecrawl.api_key",
        "API key for the Firecrawl web search API",
        aliases=("FIRECRAWL_API_KEY",),
        in_file=True,
    ),
    Credential(
        "gemini.api_key",
        "Google Gemini API key that `devops k8s push-secrets` writes to the LLM gateway Secret "
        "(stored in OS keyring)",
    ),
    Credential(
        "anthropic.api_key",
        "Anthropic API key that `devops k8s push-secrets` writes to the LLM gateway Secret "
        "(stored in OS keyring)",
    ),
    Credential(
        "mattermost.alerts_hook",
        "Mattermost incoming webhook token for the alerts channel (stored in OS keyring)",
    ),
    Credential(
        "mattermost.deploys_hook",
        "Mattermost incoming webhook token for the deploys channel (stored in OS keyring)",
    ),
    Credential(
        "mattermost.command_token",
        "Mattermost slash command token for the /roadmap command (stored in OS keyring)",
    ),
)

_CREDENTIALS_BY_KEY: dict[str, Credential] = {c.key: c for c in CREDENTIALS}


def credential(key: str) -> Credential:
    """The credential declared for `key`; a key that names no credential raises `KeyError`."""
    return _CREDENTIALS_BY_KEY[key]


def secret_keys() -> frozenset[str]:
    """The dotted keys of every credential."""
    return frozenset(_CREDENTIALS_BY_KEY)


def keyring_names() -> dict[str, str]:
    """The OS keyring entry of each credential, by dotted key."""
    return {c.key: c.keyring_name for c in CREDENTIALS}


def _variable_name(parts: list[str] | tuple[str, ...]) -> str:
    return "_".join((_VARIABLE_PREFIX, *(part.upper() for part in parts)))


def _marker(info: FieldInfo) -> Variable | None:
    return next((m for m in info.metadata if isinstance(m, Variable)), None)


def _section(info: FieldInfo) -> type[BaseModel] | None:
    annotation = info.annotation
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _declared(
    model: type[BaseModel],
    key: tuple[str, ...],
    names: tuple[str, ...],
    only: tuple[str, ...] | None,
) -> Iterator[tuple[str, str, FieldInfo]]:
    for name, info in model.model_fields.items():
        marker = _marker(info)
        field_key = (*key, name)
        field_names = (*names, marker.segment if marker and marker.segment else name)
        section = _section(info)
        if section is not None:
            yield from _declared(
                section, field_key, field_names, marker.fields if marker and marker.fields else None
            )
        elif (name in only) if only is not None else marker is not None:
            yield ".".join(field_key), _variable_name(field_names), info


@functools.cache
def _settings_declarations() -> tuple[tuple[str, str, str], ...]:
    # Imported here: the settings module reads the markers and the credentials from this one.
    from devops_cli.config.settings import Settings

    return tuple(
        (key, variable, info.description or "")
        for key, variable, info in _declared(Settings, (), (), None)
    )


def reset_declarations_cache() -> None:
    """Forget the declarations read from the settings model, so the next read walks it again."""
    _settings_declarations.cache_clear()


def setting_variables() -> dict[str, str]:
    """The variable of each setting that one sets, by dotted key, credentials apart."""
    return {key: variable for key, variable, _ in _settings_declarations()}


def option_env_vars() -> dict[str, str]:
    """The variable of each setting and of each credential, by dotted key."""
    return {**setting_variables(), **{c.key: c.env_vars[0] for c in CREDENTIALS}}


def env_var_for_option(option_key: str) -> str | None:
    """The variable of a setting or a credential, or None for a key that no variable sets."""
    return option_env_vars().get(option_key)


class EnvVarSpec(BaseModel):
    """One environment variable that devops-cli reads, as `devops config env` and the docs list it."""

    model_config = ConfigDict(frozen=True)

    env_var: str
    option_key: str | None = None
    is_secret: bool = False
    description: str = ""

    def __init__(
        self,
        env_var: str,
        option_key: str | None = None,
        is_secret: bool = False,
        description: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            env_var=env_var,
            option_key=option_key,
            is_secret=is_secret,
            description=description,
            **kwargs,
        )


def _credential_spec(entry: Credential) -> EnvVarSpec:
    also = "".join(f" Also read from `{alias}`." for alias in entry.aliases)
    return EnvVarSpec(entry.env_vars[0], entry.key, True, f"{entry.description}{also}")


def get_all_env_var_specs() -> list[EnvVarSpec]:
    """Every variable that devops-cli reads for its configuration, settings and credentials by key."""
    settings = [
        EnvVarSpec(variable, key, False, description)
        for key, variable, description in _settings_declarations()
    ]
    credentials = [_credential_spec(entry) for entry in CREDENTIALS]
    return [
        EnvVarSpec(
            CONST_PROJECT_CONFIG_ENV,
            None,
            False,
            "Absolute path to project configuration file; outside devops-cli's own "
            "repository, the only one a `devops review` command reads",
        ),
        EnvVarSpec(
            ENV_OTEL_EXPORTER_OTLP_ENDPOINT,
            None,
            False,
            "OpenTelemetry's standard collector variable, read only when `telemetry.endpoint` "
            f"is unset (default: {DEFAULT_OTEL_ENDPOINT})",
        ),
        *sorted([*settings, *credentials], key=lambda spec: spec.option_key or ""),
    ]
