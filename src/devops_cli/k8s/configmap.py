"""Kubernetes ConfigMap generation and dynamic synchronization for cluster devops-cli jobs."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_K8S_ANNOTATION_CHANGE_REASON,
    CONST_K8S_ANNOTATION_CHANGED_AT,
    CONST_K8S_ANNOTATION_CHANGED_SETTINGS,
    CONST_K8S_ANNOTATION_CONFIG_TEMPLATE_COMMIT,
    CONST_K8S_ANNOTATION_DATA_SHA256,
    CONST_K8S_CONFIGMAP_CHANGED_EVENT,
    CONST_K8S_CONFIGMAP_CHANGED_LOGGER,
    CONST_K8S_CONFIGMAP_HISTORY_RETENTION_SECONDS,
    CONST_K8S_DEVOPS_CONFIGMAP_HISTORY,
    CONST_K8S_DEVOPS_NAMESPACE,
    CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP,
)
from devops_cli.config.setting_keys import unknown_setting_keys
from devops_cli.config.settings import GitHubAppConfig, Settings, load_settings
from devops_cli.config.yaml_errors import parse_config_yaml
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.security.sanitizer import drop_credential_keys

_CONFIG_KEY = "devops-cli.yaml"


class _BlockDumper(yaml.SafeDumper):
    """YAML that writes a multi-line string as a literal block, as the template holds its config."""


def _represent_text(dumper: yaml.SafeDumper, text: str) -> yaml.ScalarNode:
    style = "|" if "\n" in text else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


_BlockDumper.add_representer(str, _represent_text)


def _service_block(
    repos: Sequence[str],
    github_app: GitHubAppConfig,
    poll_interval_seconds: int | None,
    github_requests_per_hour: int | None,
) -> dict[str, Any]:
    """The ConfigMap's `service` section: the repositories, the GitHub App the Service acts as,
    and the timings and the hourly request budget when set."""
    clean_repos = [r.strip() for r in repos if r and r.strip()]
    if not clean_repos or _missing_app_settings(github_app):
        raise KubernetesContextError(
            "The devops ConfigMap needs at least one repository and the GitHub App's ID, "
            "installation ID and slug."
        )
    service: dict[str, Any] = {
        "repos": clean_repos,
        # The Service names no single repository for its tokens: the Job it makes does (#2667).
        # Only the drift Job asks for a read-only token, through its own variable (#6783).
        "github_app": github_app.model_dump(mode="json", exclude={"token_repository", "read_only"}),
    }
    optional = {
        "poll_interval_seconds": poll_interval_seconds,
        "github_requests_per_hour": github_requests_per_hour,
    }
    service.update({key: value for key, value in optional.items() if value is not None})
    return service


def render_devops_configmap_content(
    template_content: str,
    repos: Sequence[str],
    github_app: GitHubAppConfig,
    poll_interval_seconds: int | None = None,
    github_requests_per_hour: int | None = None,
    *,
    drop_secret_keys: bool = False,
) -> str:
    """The ConfigMap template with its service section set to `repos` and `github_app`.

    The template's config is read as YAML and written again, so the applied ConfigMap does not
    keep the template's comments. Kubernetes reads the manifest, so the manifest is read with
    PyYAML. The config in it is a config file of devops-cli, which the Service reads as YAML 1.2,
    so the render reads it as YAML 1.2 too (#4481). PyYAML writes it again and quotes each word
    that YAML 1.1 reads as a bool or a number, such as `'off'`. The render validates the YAML 1.2
    read of the text that it writes, which is the config that the Service loads. The settings
    models ignore a key that they do not declare, so the render refuses such a key by its dotted
    path, such as a key that a change removed from the settings and left in the template.

    With `drop_secret_keys`, every key that names a credential leaves the config before the write,
    so the validation and the refusal see the config without it (#4147).
    """
    manifest = yaml.safe_load(template_content)
    data = manifest.get("data") if isinstance(manifest, dict) else None
    if not isinstance(data, dict):
        data = {}
    config = parse_config_yaml(data.get(_CONFIG_KEY) or "")
    if not isinstance(config, dict) or not isinstance(config.get("service"), dict):
        raise KubernetesContextError(
            "Could not locate standard service configuration block in devops ConfigMap template."
        )
    config["service"] = _service_block(
        repos, github_app, poll_interval_seconds, github_requests_per_hour
    )
    if drop_secret_keys:
        config = drop_credential_keys(config)
    data[_CONFIG_KEY] = yaml.dump(config, Dumper=_BlockDumper, sort_keys=False)
    written = parse_config_yaml(data[_CONFIG_KEY])
    Settings.model_validate(written)
    unknown = unknown_setting_keys(written)
    if unknown:
        raise KubernetesContextError(
            "The devops ConfigMap template holds keys that no setting declares: "
            + ", ".join(unknown)
            + ". Remove them from the template."
        )
    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False)


def _configured_repos(settings: Settings) -> list[str]:
    """The repositories the service works for, or an error naming the setting."""
    repos = [str(r).strip() for r in settings.service.repos if str(r).strip()]
    if not repos:
        raise KubernetesContextError(
            "No repositories configured for the roadmap service. "
            "Set 'service.repos' in config.yaml."
        )
    return repos


def _missing_app_settings(github_app: GitHubAppConfig) -> list[str]:
    """The App settings that are not set."""
    wanted = (
        ("service.github_app.app_id", github_app.app_id),
        ("service.github_app.installation_id", github_app.installation_id),
        ("service.github_app.slug", github_app.slug),
    )
    return [option for option, value in wanted if not value]


def _configured_app(settings: Settings) -> GitHubAppConfig:
    """The GitHub App the service acts as, or an error naming each setting that is not set."""
    github_app = settings.service.github_app
    missing = _missing_app_settings(github_app)
    if missing:
        raise KubernetesContextError(
            "The roadmap service acts as a GitHub App, so set "
            + ", ".join(f"'{option}'" for option in missing)
            + " in config.yaml."
        )
    return github_app


def render_active_devops_configmap(
    product_dir: Path,
    settings: Settings | None = None,
    *,
    drop_secret_keys: bool = False,
) -> str:
    """ConfigMap devops-cli-config rendered in memory from the active config and the template
    `configmap.example.yaml` of the product base `product_dir` (`k8s/devops`).

    The repository holds only its template, so the homelab's repositories and App never enter
    git; a deploy applies this rendering and refuses when a setting it needs is unset. With
    `drop_secret_keys`, every key that names a credential leaves the rendered config (#4147).
    """
    template_path = product_dir / "configmap.example.yaml"

    if not template_path.is_file():
        raise FileNotFoundError(
            f"DevOps ConfigMap template not found at {template_path}. "
            "Ensure k8s/devops/configmap.example.yaml exists."
        )

    active_settings = settings if settings is not None else load_settings()
    effective_repos = _configured_repos(active_settings)
    github_app = _configured_app(active_settings)

    poll_interval = active_settings.service.poll_interval_seconds
    # The Service keeps its own default unless a source sets the budget: the ConfigMap copies no
    # default into the cluster (#2755).
    budget = (
        active_settings.service.github_requests_per_hour
        if "github_requests_per_hour" in active_settings.service.model_fields_set
        else None
    )

    template_text = template_path.read_text(encoding="utf-8")
    return render_devops_configmap_content(
        template_text,
        repos=effective_repos,
        github_app=github_app,
        poll_interval_seconds=poll_interval,
        github_requests_per_hour=budget,
        drop_secret_keys=drop_secret_keys,
    )


def render_active_devops_sandbox_configmap(
    product_dir: Path,
    settings: Settings | None = None,
) -> str:
    """ConfigMap devops-cli-config-sandbox rendered from the active config and the template.

    The planner run Job mounts this copy of the config with no credential (ADR 0018 control 2), so
    the render drops each key that names a credential at any depth, and keeps a number or a
    boolean under such a name, such as `token_budget`. The name and the one data key
    `devops-cli.yaml` stay those that the Job mounts (#4147).
    """
    rendered = render_active_devops_configmap(product_dir, settings, drop_secret_keys=True)
    manifest: dict[str, Any] = yaml.safe_load(rendered)
    manifest["metadata"]["name"] = CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP
    data: dict[str, Any] = manifest["data"]
    manifest["data"] = {_CONFIG_KEY: data[_CONFIG_KEY]}
    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False)


_MISSING = object()
_TEMPLATE_FILENAME = "configmap.example.yaml"


@dataclass(frozen=True)
class DevopsConfigMapChangeRecord:
    """Metadata describing a change applied to ConfigMap `devops-cli-config` (#5221)."""

    changed_settings: tuple[str, ...]
    data_sha256: str
    config_template_commit: str
    changed_at: str
    epoch_seconds: int
    change_reason: str | None = None


def configmap_data_sha256(data: Mapping[str, Any]) -> str:
    """Canonical SHA-256 hex digest of a ConfigMap `data` mapping."""
    canonical = json.dumps(dict(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _flatten_settings(value: Any, prefix: str, out: dict[str, Any]) -> None:
    """Flatten nested mappings into dotted paths without altering leaf values."""
    if isinstance(value, Mapping):
        if not value and prefix:
            out[prefix] = {}
            return
        for key, item in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            _flatten_settings(item, dotted, out)
        return
    if prefix:
        out[prefix] = value


def _parsed_config_data(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Flatten `devops-cli.yaml` settings and any extra data keys for value-free key comparison."""
    if not data:
        return {}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key != _CONFIG_KEY:
            out[key] = value
            continue
        if isinstance(value, str) and value.strip():
            parsed = parse_config_yaml(value)
            if isinstance(parsed, Mapping):
                _flatten_settings(parsed, "", out)
    return out


def changed_configmap_settings(
    live_data: Mapping[str, Any] | None, rendered_data: Mapping[str, Any]
) -> tuple[str, ...]:
    """Sorted dotted setting names whose values differ between `live_data` and `rendered_data`."""
    live_flat = _parsed_config_data(live_data)
    rendered_flat = _parsed_config_data(rendered_data)
    return tuple(
        sorted(
            key
            for key in set(live_flat) | set(rendered_flat)
            if live_flat.get(key, _MISSING) != rendered_flat.get(key, _MISSING)
        )
    )


def read_devops_configmap_template_commit(product_dir: Path) -> str:
    """Last commit hash touching `configmap.example.yaml` in `product_dir`, or `""` outside git."""
    if not product_dir.is_dir():
        return ""
    res = run_subprocess(
        ["git", "log", "-1", "--format=%H", "--", _TEMPLATE_FILENAME],
        cwd=product_dir,
        local_read=True,
        quiet=True,
        check=False,
    )
    return res.stdout.strip() if res.returncode == 0 else ""


def build_devops_configmap_change(
    rendered_manifest: str,
    live_data: Mapping[str, Any] | None,
    *,
    config_template_commit: str = "",
    reason: str | None = None,
    now: datetime | None = None,
) -> tuple[str, DevopsConfigMapChangeRecord | None]:
    """Annotate `rendered_manifest` when its `data` digest differs from `live_data`."""
    manifest: dict[str, Any] = yaml.safe_load(rendered_manifest)
    rendered_data: Mapping[str, Any] = manifest.get("data") or {}
    data_sha256 = configmap_data_sha256(rendered_data)
    if live_data is not None and configmap_data_sha256(live_data) == data_sha256:
        return rendered_manifest, None

    now_utc = (now or datetime.now(UTC)).astimezone(UTC)
    epoch_seconds = int(now_utc.timestamp())
    changed_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = changed_configmap_settings(live_data, rendered_data)
    commit = config_template_commit.strip()
    clean_reason = reason.strip() if reason and reason.strip() else None

    record = DevopsConfigMapChangeRecord(
        changed_settings=changed,
        data_sha256=data_sha256,
        config_template_commit=commit,
        changed_at=changed_at,
        epoch_seconds=epoch_seconds,
        change_reason=clean_reason,
    )

    metadata: dict[str, Any] = manifest.setdefault("metadata", {})
    annotations: dict[str, str] = dict(metadata.get("annotations") or {})
    if commit:
        annotations[CONST_K8S_ANNOTATION_CONFIG_TEMPLATE_COMMIT] = commit
    annotations[CONST_K8S_ANNOTATION_DATA_SHA256] = data_sha256
    annotations[CONST_K8S_ANNOTATION_CHANGED_SETTINGS] = ",".join(changed)
    annotations[CONST_K8S_ANNOTATION_CHANGED_AT] = changed_at
    if clean_reason:
        annotations[CONST_K8S_ANNOTATION_CHANGE_REASON] = clean_reason
    metadata["annotations"] = annotations

    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False), record


def build_devops_configmap_history_manifest() -> str:
    """Empty `devops-cli-config-changes` ConfigMap YAML applied when absent on the cluster."""
    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": CONST_K8S_DEVOPS_CONFIGMAP_HISTORY,
            "namespace": CONST_K8S_DEVOPS_NAMESPACE,
        },
        "data": {},
    }
    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False)


def _history_entry_epoch(key: str, raw_value: Any) -> int | None:
    """Extract Unix epoch seconds from a history ConfigMap key `<epoch>-<hash>` or its JSON time."""
    head, sep, _ = key.partition("-")
    if sep and head.isdigit():
        return int(head)
    if not isinstance(raw_value, str):
        return None
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return None
    ts = parsed.get("time") if isinstance(parsed, Mapping) else None
    if not isinstance(ts, str):
        return None
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def build_devops_configmap_history_patch(
    record: DevopsConfigMapChangeRecord,
    existing_data: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> str:
    """JSON merge patch adding `record` to `devops-cli-config-changes` and pruning >30d entries."""
    now_epoch = int(now.astimezone(UTC).timestamp()) if now is not None else record.epoch_seconds
    cutoff = now_epoch - CONST_K8S_CONFIGMAP_HISTORY_RETENTION_SECONDS
    entry_key = f"{record.epoch_seconds}-{record.data_sha256[:8]}"

    patch_data: dict[str, Any] = {}
    for key, raw_value in (existing_data or {}).items():
        if key == entry_key:
            continue
        entry_epoch = _history_entry_epoch(key, raw_value)
        if entry_epoch is not None and entry_epoch < cutoff:
            patch_data[key] = None

    entry_payload: dict[str, Any] = {
        "time": record.changed_at,
        "changed_settings": list(record.changed_settings),
        "data_sha256": record.data_sha256,
    }
    if record.config_template_commit:
        entry_payload["config_template_commit"] = record.config_template_commit
    if record.change_reason:
        entry_payload["change_reason"] = record.change_reason
    patch_data[entry_key] = json.dumps(entry_payload, separators=(",", ":"))

    return json.dumps({"data": patch_data}, separators=(",", ":"))


def emit_devops_configmap_changed_log(record: DevopsConfigMapChangeRecord) -> None:
    """Emit one `configmap_changed` WARNING record on `devops_cli.k8s.configmap` for OTel/Loki."""
    extra: dict[str, str] = {
        "changed_settings": ",".join(record.changed_settings),
        "data_sha256": record.data_sha256,
        "time": record.changed_at,
    }
    if record.config_template_commit:
        extra["config_template_commit"] = record.config_template_commit
    if record.change_reason:
        extra["change_reason"] = record.change_reason
    logging.getLogger(CONST_K8S_CONFIGMAP_CHANGED_LOGGER).warning(
        CONST_K8S_CONFIGMAP_CHANGED_EVENT, extra=extra
    )
