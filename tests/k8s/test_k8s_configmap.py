"""Tests for Kubernetes devops ConfigMap rendering and dynamic synchronization."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from ruamel.yaml import YAML

from devops_cli.config.settings import GitHubAppConfig, ServiceConfig, Settings
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.configmap import (
    build_devops_configmap_change,
    build_devops_configmap_history_manifest,
    build_devops_configmap_history_patch,
    changed_configmap_settings,
    configmap_data_sha256,
    emit_devops_configmap_changed_log,
    read_devops_configmap_template_commit,
    render_active_devops_configmap,
    render_devops_configmap_content,
)
from devops_cli.telemetry.logging_bridge import OTelLoggingHandler
from tests.support.credential_keys import credential_key_paths
from tests.support.fakes.process import ProcessAnswer, ProcessFake

SAMPLE_TEMPLATE = """apiVersion: v1
kind: ConfigMap
metadata:
  name: devops-cli-config
  namespace: devops
data:
  devops-cli.yaml: |
    ai:
      provider: gateway
      gateway_url: http://llm-gateway.llm.svc.cluster.local:4000/v1
      allow_private_network: true
      model: devops-background
      tasks:
        analysis:
          model: devops-background
          context_window: 65536
        chat:
          model: devops-background
        embedding:
          model: bge-m3:latest
    telemetry:
      enabled: true
      endpoint: http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318
    service:
      repos:
        - owner/repo
      github_app:
        app_id: 1
        installation_id: 1
        slug: devops-roadmap
"""

APP = GitHubAppConfig(app_id=1001, installation_id=42, slug="devops-roadmap")


def test_render_devops_configmap_substitutes_repos_and_the_github_app() -> None:
    """The rendered config names the repositories and the App, and keeps the template's rest."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["example-org/repo-one", "example-org/repo-two"],
        github_app=APP,
    )
    doc = yaml.safe_load(rendered)
    inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(inner)

    assert (
        settings.service.repos,
        settings.service.github_app,
        settings.ai.provider,
        settings.telemetry.enabled,
        doc["metadata"]["name"],
    ) == (
        ["example-org/repo-one", "example-org/repo-two"],
        APP,
        "gateway",
        True,
        "devops-cli-config",
    )


def test_a_bare_off_in_the_template_renders_a_config_whose_yaml_1_2_read_is_off() -> None:
    """The template holds `jev: off` with no quotes. The render reads the config as YAML 1.2, as
    the Service loads it, so the mode is the string `off` (#4481)."""
    template = SAMPLE_TEMPLATE + "    roadmap:\n      intake:\n        jev: off\n"

    rendered = render_devops_configmap_content(template, repos=["owner/repo"], github_app=APP)

    config = yaml.safe_load(rendered)["data"]["devops-cli.yaml"]
    assert YAML(typ="safe", pure=True).load(config)["roadmap"]["intake"]["jev"] == "off"


@pytest.mark.parametrize(
    ("repos", "github_app"),
    [([], APP), (["owner/repo"], GitHubAppConfig(app_id=1001, installation_id=42))],
)
def test_the_config_map_needs_a_repository_and_the_github_app(
    repos: list[str], github_app: GitHubAppConfig
) -> None:
    """No placeholder stands in for a value the service needs."""
    with pytest.raises(KubernetesContextError, match="at least one repository and the GitHub App"):
        render_devops_configmap_content(SAMPLE_TEMPLATE, repos=repos, github_app=github_app)


def test_render_devops_configmap_invalid_template_raises() -> None:
    """Verify KubernetesContextError is raised if service block is missing."""
    with pytest.raises(KubernetesContextError, match="standard service configuration block"):
        render_devops_configmap_content(
            "apiVersion: v1\nkind: ConfigMap\n", repos=["owner/repo"], github_app=APP
        )


def test_a_template_with_a_key_that_no_setting_declares_is_refused_naming_the_key() -> None:
    """The settings models ignore an unknown key, so the render refuses a template key that no
    model declares, such as a key that a change removed from the settings (#4093, #6082)."""
    template = SAMPLE_TEMPLATE.replace(
        "    telemetry:\n", "    telemetry:\n      not_a_setting: 1\n"
    ).replace("    ai:\n", "    not_a_section: {}\n    ai:\n")

    with pytest.raises(KubernetesContextError) as raised:
        render_devops_configmap_content(template, repos=["example/repo"], github_app=APP)

    assert (
        "not_a_section" in str(raised.value),
        "telemetry.not_a_setting" in str(raised.value),
    ) == (
        True,
        True,
    )


def test_render_devops_configmap_with_poll() -> None:
    """Verify render_devops_configmap_content formats poll_interval_seconds."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["example/repo"],
        github_app=APP,
        poll_interval_seconds=180,
    )
    doc = yaml.safe_load(rendered)
    inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(inner)

    assert settings.service.poll_interval_seconds == 180


def test_render_active_devops_configmap_produces_valid_yaml(tmp_path: Path) -> None:
    """Verify render_active_devops_configmap renders content in memory without creating files."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    settings = Settings(
        service=ServiceConfig(
            repos=["active/repo"],
            github_app=APP,
            poll_interval_seconds=150,
        )
    )

    rendered = render_active_devops_configmap(devops_dir, settings=settings)
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])

    assert (inner["service"], (devops_dir / "configmap.yaml").exists()) == (
        {
            "repos": ["active/repo"],
            "github_app": {"app_id": 1001, "installation_id": 42, "slug": "devops-roadmap"},
            "poll_interval_seconds": 150,
        },
        False,
    )


def _rendered_service(tmp_path: Path, service: ServiceConfig) -> dict[str, object]:
    """The `service` section of the ConfigMap that the active settings render."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    rendered = render_active_devops_configmap(devops_dir, settings=Settings(service=service))
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    section: dict[str, object] = inner["service"]
    return section


def test_a_deploy_renders_the_hourly_budget_that_the_active_settings_set(tmp_path: Path) -> None:
    """The owner raised the budget to 2000 by hand; a deploy must keep it (#2755)."""
    service = _rendered_service(
        tmp_path,
        ServiceConfig(repos=["active/repo"], github_app=APP, github_requests_per_hour=2000),
    )

    assert service["github_requests_per_hour"] == 2000


def test_a_deploy_renders_a_budget_that_equals_the_default_when_a_source_sets_it(
    tmp_path: Path,
) -> None:
    """A set value is rendered, so a later change of the default does not move the Service."""
    service = _rendered_service(
        tmp_path,
        ServiceConfig(repos=["active/repo"], github_app=APP, github_requests_per_hour=500),
    )

    assert service["github_requests_per_hour"] == 500


def test_a_deploy_renders_no_hourly_budget_when_the_active_settings_keep_the_default(
    tmp_path: Path,
) -> None:
    service = _rendered_service(tmp_path, ServiceConfig(repos=["active/repo"], github_app=APP))

    assert "github_requests_per_hour" not in service


def test_render_devops_configmap_with_an_hourly_budget() -> None:
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["example/repo"],
        github_app=APP,
        github_requests_per_hour=2000,
    )
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])

    assert Settings.model_validate(inner).service.github_requests_per_hour == 2000


def test_a_token_repository_of_the_active_config_is_not_rendered_into_the_service_section(
    tmp_path: Path,
) -> None:
    """The Service mints tokens for every repository in `service.repos`: only the Job that the
    Service makes names one repository, through its own environment (#2667)."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    scoped = APP.model_copy(update={"token_repository": "active/repo"})
    settings = Settings(service=ServiceConfig(repos=["active/repo"], github_app=scoped))

    rendered = render_active_devops_configmap(devops_dir, settings=settings)
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])

    assert inner["service"]["github_app"] == {
        "app_id": 1001,
        "installation_id": 42,
        "slug": "devops-roadmap",
    }


def test_render_active_devops_configmap_missing_template_raises(tmp_path: Path) -> None:
    """Verify render_active_devops_configmap raises FileNotFoundError when template is missing."""
    with pytest.raises(
        FileNotFoundError, match=r"Ensure k8s/devops/configmap\.example\.yaml exists"
    ):
        render_active_devops_configmap(tmp_path)


def _template_dir(tmp_path: Path) -> Path:
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    return devops_dir


def _settings(repos: list[str], github_app: GitHubAppConfig) -> Settings:
    return Settings(service=ServiceConfig(repos=repos, github_app=github_app))


def test_the_active_config_map_without_repositories_is_refused_naming_the_setting(
    tmp_path: Path,
) -> None:
    """A deploy never ships the template's placeholder repository."""
    with pytest.raises(KubernetesContextError, match=r"service\.repos"):
        render_active_devops_configmap(_template_dir(tmp_path), settings=_settings([], APP))


def test_the_active_config_map_without_the_github_app_is_refused_naming_each_setting(
    tmp_path: Path,
) -> None:
    """A deploy never ships the template's placeholder App."""
    with pytest.raises(KubernetesContextError) as raised:
        render_active_devops_configmap(
            _template_dir(tmp_path),
            settings=_settings(["owner/repo"], GitHubAppConfig(slug="devops-roadmap")),
        )
    assert raised.value.message == (
        "The roadmap service acts as a GitHub App, so set 'service.github_app.app_id', "
        "'service.github_app.installation_id' in config.yaml."
    )


_SANDBOX_TEMPLATE = (
    SAMPLE_TEMPLATE.replace(
        "    ai:\n",
        "    github_token: example-value\n"
        "    ai:\n"
        "      api_key: example-value\n"
        "      db_password: example-value\n",
    )
    # The sandbox ConfigMap holds the one data key that the planner run Job mounts.
    + "  other.yaml: |\n    value: 1\n"
)

_COUNT_TEMPLATE = SAMPLE_TEMPLATE.replace(
    "    telemetry:\n",
    "    roadmap:\n"
    "      stage:\n"
    "        step_tokens: 64000\n"
    "      review:\n"
    "        token_budget: 16000000\n"
    "      implement:\n"
    "        step_token_budget: 32000000\n"
    "        item_token_budget: 80000000\n"
    "    telemetry:\n",
)


def _sandbox_manifest(
    tmp_path: Path,
    template: str,
    render: Callable[[Path, Settings | None], str],
) -> dict[str, Any]:
    """The sandbox ConfigMap that `render` gives for the active settings and `template`."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(template, encoding="utf-8")
    settings = Settings(service=ServiceConfig(repos=["active/repo"], github_app=APP))
    manifest: dict[str, Any] = yaml.safe_load(render(devops_dir, settings))
    return manifest


def test_the_sandbox_config_map_drops_every_credential_key_and_keeps_its_name(
    tmp_path: Path,
) -> None:
    """The rendered sandbox ConfigMap holds no credential-named key at any depth, keeps every
    other key with its value, and keeps the name and the one data key that the planner run Job
    mounts (#4147)."""
    from devops_cli.config.constants import CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP
    from devops_cli.k8s.configmap import render_active_devops_sandbox_configmap

    hand_built = {
        "github_token": "example-value",
        "repository": "example/repo",
        "ai": {"api_key": "example-value", "provider": "gateway"},
    }

    manifest = _sandbox_manifest(
        tmp_path, _SANDBOX_TEMPLATE, render_active_devops_sandbox_configmap
    )
    inner = yaml.safe_load(manifest["data"]["devops-cli.yaml"])

    assert (
        credential_key_paths(hand_built),
        credential_key_paths(inner),
        manifest["metadata"]["name"],
        list(manifest["data"]),
        inner["ai"]["provider"],
        inner["service"]["repos"],
    ) == (
        ["github_token", "ai.api_key"],
        [],
        CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP,
        ["devops-cli.yaml"],
        "gateway",
        ["active/repo"],
    )


def test_the_sandbox_config_map_keeps_a_number_under_a_credential_like_name(
    tmp_path: Path,
) -> None:
    """The same walk over a credential-free template names no key, and a number under a
    credential-like name stays: the four token budgets reach the planner with their values
    (#4147)."""
    from devops_cli.k8s.configmap import render_active_devops_sandbox_configmap

    manifest = _sandbox_manifest(tmp_path, _COUNT_TEMPLATE, render_active_devops_sandbox_configmap)
    inner = yaml.safe_load(manifest["data"]["devops-cli.yaml"])
    roadmap = inner["roadmap"]

    assert (
        credential_key_paths(inner),
        roadmap["stage"]["step_tokens"],
        roadmap["review"]["token_budget"],
        roadmap["implement"]["step_token_budget"],
        roadmap["implement"]["item_token_budget"],
    ) == ([], 64000, 16000000, 32000000, 80000000)


def test_the_configmap_leaves_out_the_read_only_setting() -> None:
    """Only the drift Job asks for a read-only token, through its own variable, so the ConfigMap
    that the Service reads never carries the setting (#6783)."""
    app = GitHubAppConfig.model_validate({**APP.model_dump(), "read_only": True})

    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=app
    )

    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    assert sorted(inner["service"]["github_app"]) == ["app_id", "installation_id", "slug"]


def _data_from_rendered(rendered: str) -> dict[str, str]:
    """The `data` mapping of a rendered ConfigMap YAML document."""
    return dict(yaml.safe_load(rendered)["data"])


def test_changed_configmap_settings_names_only_ai_model_without_value() -> None:
    """When only `ai.model` differs between two rendered ConfigMaps, only that dotted path appears
    with no setting value."""
    live = _data_from_rendered(
        render_devops_configmap_content(SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP)
    )
    updated_template = SAMPLE_TEMPLATE.replace("model: devops-background", "model: canary-model", 1)
    rendered = _data_from_rendered(
        render_devops_configmap_content(updated_template, repos=["owner/repo"], github_app=APP)
    )

    changed = changed_configmap_settings(live, rendered)

    assert changed == ("ai.model",)


def test_build_devops_configmap_change_sets_all_five_annotations_and_keeps_private_sentinel_out() -> (
    None
):
    """Changed ConfigMap data writes all five `roadmap.devops-cli/` annotations, and neither the
    annotations, history line, nor log record exposes a sentinel value (#5221)."""
    live_data = _data_from_rendered(
        render_devops_configmap_content(SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP)
    )
    sentinel_repo = "private-org/sentinel-secret-repo"
    updated_template = SAMPLE_TEMPLATE.replace(
        "model: devops-background", "model: next-sentinel-model", 1
    )
    rendered = render_devops_configmap_content(
        updated_template, repos=[sentinel_repo], github_app=APP
    )
    fixed_now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)

    annotated_yaml, record = build_devops_configmap_change(
        rendered,
        live_data,
        config_template_commit="deadbeef1234",
        reason="#5221",
        now=fixed_now,
    )

    assert record is not None
    doc = yaml.safe_load(annotated_yaml)
    annotations = doc["metadata"]["annotations"]
    assert annotations == {
        "roadmap.devops-cli/config-template-commit": "deadbeef1234",
        "roadmap.devops-cli/data-sha256": configmap_data_sha256(doc["data"]),
        "roadmap.devops-cli/changed-settings": "ai.model,service.repos",
        "roadmap.devops-cli/changed-at": "2026-11-25T12:00:00Z",
        "roadmap.devops-cli/change-reason": "#5221",
    }

    patch_json = build_devops_configmap_history_patch(record, {}, now=fixed_now)
    sent: list[dict[str, Any]] = []
    handler = OTelLoggingHandler(exporter=sent.append)
    logger = logging.getLogger("devops_cli.k8s.configmap")
    logger.addHandler(handler)
    try:
        emit_devops_configmap_changed_log(record)
    finally:
        logger.removeHandler(handler)

    rendered_records = json.dumps(
        {
            "annotations": annotations,
            "history": patch_json,
            "log": sent,
        }
    )
    assert sentinel_repo not in rendered_records
    assert "next-sentinel-model" not in rendered_records


def test_build_devops_configmap_change_omits_template_commit_and_reason_when_empty() -> None:
    """Outside a git checkout or without `--reason`, those optional annotations are omitted."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP
    )
    fixed_now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)

    annotated_yaml, record = build_devops_configmap_change(
        rendered, None, config_template_commit="", reason=None, now=fixed_now
    )

    assert record is not None
    annotations = yaml.safe_load(annotated_yaml)["metadata"]["annotations"]
    assert sorted(annotations) == [
        "roadmap.devops-cli/changed-at",
        "roadmap.devops-cli/changed-settings",
        "roadmap.devops-cli/data-sha256",
    ]


def test_build_devops_configmap_change_returns_none_when_data_sha256_matches() -> None:
    """Identical rendered and live `data` writes no annotation and produces no change record."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP
    )
    live_data = _data_from_rendered(rendered)

    unchanged_yaml, record = build_devops_configmap_change(
        rendered, live_data, config_template_commit="deadbeef1234", reason="#5221"
    )

    assert record is None
    assert "annotations" not in yaml.safe_load(unchanged_yaml)["metadata"]


def test_build_devops_configmap_history_patch_adds_key_and_prunes_older_than_30_days() -> None:
    """Merge patch adds `<epoch>-<sha8>` with UTC `Z` JSON and deletes entries older than 30d."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP
    )
    fixed_now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)
    now_epoch = int(fixed_now.timestamp())
    _, record = build_devops_configmap_change(
        rendered, None, config_template_commit="abc123", reason="#5221", now=fixed_now
    )
    assert record is not None

    stale_key = f"{now_epoch - 31 * 86400}-11111111"
    recent_key = f"{now_epoch - 5 * 86400}-22222222"
    existing = {stale_key: '{"time":"2026-10-20T00:00:00Z"}', recent_key: '{"time":"recent"}'}

    patch = json.loads(build_devops_configmap_history_patch(record, existing, now=fixed_now))
    expected_key = f"{now_epoch}-{record.data_sha256[:8]}"
    assert re.fullmatch(r"[-._a-zA-Z0-9]+", expected_key) is not None
    assert patch["data"][stale_key] is None
    assert recent_key not in patch["data"]

    entry = json.loads(patch["data"][expected_key])
    assert entry == {
        "time": "2026-11-25T12:00:00Z",
        "changed_settings": list(record.changed_settings),
        "data_sha256": record.data_sha256,
        "config_template_commit": "abc123",
        "change_reason": "#5221",
    }

    empty_doc = yaml.safe_load(build_devops_configmap_history_manifest())
    assert (empty_doc["kind"], empty_doc["metadata"], empty_doc["data"]) == (
        "ConfigMap",
        {"name": "devops-cli-config-changes", "namespace": "devops"},
        {},
    )


def test_emit_devops_configmap_changed_log_reaches_otel_handler_at_warning() -> None:
    """`emit_devops_configmap_changed_log` emits `configmap_changed` at WARNING with attributes."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP
    )
    live_data = _data_from_rendered(rendered)
    updated = render_devops_configmap_content(
        SAMPLE_TEMPLATE.replace("model: devops-background", "model: other", 1),
        repos=["owner/repo"],
        github_app=APP,
    )
    fixed_now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)
    _, record = build_devops_configmap_change(
        updated, live_data, config_template_commit="deadbeef", now=fixed_now
    )
    assert record is not None

    sent: list[dict[str, Any]] = []
    handler = OTelLoggingHandler(exporter=sent.append)
    logger = logging.getLogger("devops_cli.k8s.configmap")
    logger.addHandler(handler)
    try:
        emit_devops_configmap_changed_log(record)
    finally:
        logger.removeHandler(handler)

    assert len(sent) == 1
    log_rec = sent[0]
    attrs = {a["key"]: a["value"] for a in log_rec["attributes"]}
    assert (
        log_rec["severityText"],
        log_rec["body"],
        attrs["log.logger"],
        attrs["changed_settings"],
        attrs["config_template_commit"],
        attrs["time"],
        attrs["data_sha256"],
    ) == (
        "WARN",
        {"stringValue": "configmap_changed"},
        {"stringValue": "devops_cli.k8s.configmap"},
        {"stringValue": "ai.model"},
        {"stringValue": "deadbeef"},
        {"stringValue": "2026-11-25T12:00:00Z"},
        {"stringValue": record.data_sha256},
    )


def test_read_devops_configmap_template_commit_reads_git_checkout_and_handles_non_git_dir(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Template commit lookup queries git with `local_read=True` and returns empty outside git."""
    template = tmp_path / "configmap.example.yaml"
    template.write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    process_fake.answer(
        lambda call: call.local_read and call.argv[:3] == ("git", "log", "-1"),
        ProcessAnswer(stdout="cafebabe123456\n"),
    )
    assert read_devops_configmap_template_commit(tmp_path) == "cafebabe123456"

    process_fake.answer(
        lambda call: call.local_read and call.argv[:3] == ("git", "log", "-1"),
        ProcessAnswer(returncode=128, stderr="fatal: not a git repository"),
    )
    assert read_devops_configmap_template_commit(tmp_path) == ""
    assert read_devops_configmap_template_commit(tmp_path / "missing-dir") == ""


def test_changed_configmap_settings_and_history_patch_cover_extra_keys_and_json_time_fallback() -> (
    None
):
    """Extra non-YAML data keys, empty nested maps, same-key replacement, and JSON time fallback
    for non-epoch history keys behave deterministically."""
    changed = changed_configmap_settings(
        {"devops-cli.yaml": "ai: {}\n", "extra.txt": "old"},
        {"devops-cli.yaml": "ai: {}\n", "extra.txt": "new"},
    )
    assert changed == ("extra.txt",)

    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE, repos=["owner/repo"], github_app=APP
    )
    fixed_now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)
    _, record = build_devops_configmap_change(rendered, None, now=fixed_now)
    assert record is not None
    same_key = f"{record.epoch_seconds}-{record.data_sha256[:8]}"
    existing = {
        same_key: '{"time":"2026-11-25T12:00:00Z"}',
        "legacy-old": '{"time":"2026-10-01T00:00:00Z"}',
        "legacy-bad-json": "{not-json",
        "legacy-bad-time": '{"time":"not-a-timestamp"}',
        "legacy-nonstr": 123,
    }

    patch = json.loads(build_devops_configmap_history_patch(record, existing, now=fixed_now))

    assert patch["data"]["legacy-old"] is None
    assert "legacy-bad-json" not in patch["data"]
    assert "legacy-bad-time" not in patch["data"]
    assert "legacy-nonstr" not in patch["data"]
    assert same_key in patch["data"]
