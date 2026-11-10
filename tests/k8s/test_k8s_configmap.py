"""Tests for Kubernetes devops ConfigMap rendering and dynamic synchronization."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devops_cli.config.settings import AITasksConfig, GitHubAppConfig, ServiceConfig, Settings
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.configmap import (
    render_active_devops_configmap,
    render_devops_configmap_content,
)
from tests.support.paths import REPO_ROOT

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


def test_render_devops_configmap_with_timeouts_and_poll() -> None:
    """Verify render_devops_configmap_content formats drain_timeout_seconds and poll_interval_seconds."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["example/repo"],
        github_app=APP,
        drain_timeout_seconds=90,
        poll_interval_seconds=180,
    )
    doc = yaml.safe_load(rendered)
    inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(inner)

    assert (
        settings.service.drain_timeout_seconds,
        settings.service.poll_interval_seconds,
    ) == (90, 180)


def test_render_active_devops_configmap_produces_valid_yaml(tmp_path: Path) -> None:
    """Verify render_active_devops_configmap renders content in memory without creating files."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    settings = Settings(
        service=ServiceConfig(
            repos=["active/repo"],
            github_app=APP,
            drain_timeout_seconds=75,
            poll_interval_seconds=150,
        )
    )

    rendered = render_active_devops_configmap(k8s_dir=tmp_path, settings=settings)
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])

    assert (inner["service"], (devops_dir / "configmap.yaml").exists()) == (
        {
            "repos": ["active/repo"],
            "github_app": {"app_id": 1001, "installation_id": 42, "slug": "devops-roadmap"},
            "drain_timeout_seconds": 75,
            "poll_interval_seconds": 150,
        },
        False,
    )


def _rendered_service(tmp_path: Path, service: ServiceConfig) -> dict[str, object]:
    """The `service` section of the ConfigMap that the active settings render."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    rendered = render_active_devops_configmap(k8s_dir=tmp_path, settings=Settings(service=service))
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

    rendered = render_active_devops_configmap(k8s_dir=tmp_path, settings=settings)
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])

    assert inner["service"]["github_app"] == {
        "app_id": 1001,
        "installation_id": 42,
        "slug": "devops-roadmap",
    }


def test_the_repository_template_renders_one_model_retry_for_the_cluster() -> None:
    """Each model call of the Service and the cluster Jobs is sent at most two times (#2494)."""
    rendered = render_active_devops_configmap(
        k8s_dir=REPO_ROOT / "k8s", settings=_settings(["owner/repo"], APP)
    )
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])

    assert Settings.model_validate(inner).ai.max_retries == 1


def test_every_chat_model_slot_of_the_rendered_template_names_one_hosted_group() -> None:
    """The Service uses one chat model (#3874). The task `analysis` returned to it on 2026-11-10
    (#4369) after the Sonnet trial of 2026-11-09 (#4204). Every task of `ai.tasks` and the default
    `ai.model` resolve to the one model. The embedding slot is the embedding model, because a chat
    model cannot embed."""
    rendered = render_active_devops_configmap(
        k8s_dir=REPO_ROOT / "k8s", settings=_settings(["owner/repo"], APP)
    )
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    ai = Settings.model_validate(inner).ai
    chat_slots = {
        name: ai.for_task(name).model for name in AITasksConfig.model_fields if name != "embedding"
    }

    assert (
        ai.model,
        {name: model for name, model in chat_slots.items() if model != "deepseek-v4.1-flash-1017"},
        ai.for_task("embedding").model,
        (ai.for_task("analysis").context_window, ai.for_task("stage").context_window),
    ) == ("deepseek-v4.1-flash-1017", {}, "qwen3-embedding:0.6b", (256000, 256000))


def test_the_rendered_template_names_the_reference_models_of_the_spend_reports() -> None:
    """The owner values local tokens at the hosted prices of two models from 2026-11-09 (#4241).

    Without the two names, a deploy removes them from the cluster, and the Service reports value
    local tokens at the defaults `gpt-4o` and `text-embedding-3-small` again.
    """
    rendered = render_active_devops_configmap(
        k8s_dir=REPO_ROOT / "k8s", settings=_settings(["owner/repo"], APP)
    )
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    ai = Settings.model_validate(inner).ai

    assert (ai.reference_model, ai.reference_embedding_model) == (
        "qwen3.8:27b",
        "qwen/qwen3-embedding-8b",
    )


def test_the_template_prices_both_reference_models() -> None:
    """The repository owns the two prices of the owner decision of 2026-11-09 (#4242)."""
    rendered = render_active_devops_configmap(
        k8s_dir=REPO_ROOT / "k8s", settings=_settings(["owner/repo"], APP)
    )
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    prices = Settings.model_validate(inner).ai.price_overrides

    assert {
        name: (price.prompt_usd_per_million, price.completion_usd_per_million)
        for name, price in prices.items()
    } == {"qwen3.8:27b": (0.035, 1.5), "qwen/qwen3-embedding-8b": (0.01, 0.0)}


def test_the_comment_above_the_reference_models_gives_the_decision_and_the_prices() -> None:
    """A reader of the template learns who decided, when, and which prices the names stand for."""
    template = (REPO_ROOT / "k8s" / "devops" / "configmap.example.yaml").read_text(encoding="utf-8")
    lines = template.splitlines()
    key = next(i for i, line in enumerate(lines) if line.strip().startswith("reference_model:"))
    comment_lines: list[str] = []
    for line in reversed(lines[:key]):
        if not line.strip().startswith("#"):
            break
        comment_lines.append(line)
    comment = "\n".join(comment_lines)

    assert all(
        word in comment for word in ("2026-11-09", "0.035", "1.50", "0.01", "pricing_overrides")
    )


def test_render_active_devops_configmap_missing_template_raises(tmp_path: Path) -> None:
    """Verify render_active_devops_configmap raises FileNotFoundError when template is missing."""
    with pytest.raises(
        FileNotFoundError, match=r"Ensure k8s/devops/configmap\.example\.yaml exists"
    ):
        render_active_devops_configmap(k8s_dir=tmp_path)


def _template_dir(tmp_path: Path) -> Path:
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    return tmp_path


def _settings(repos: list[str], github_app: GitHubAppConfig) -> Settings:
    return Settings(service=ServiceConfig(repos=repos, github_app=github_app))


def test_the_active_config_map_without_repositories_is_refused_naming_the_setting(
    tmp_path: Path,
) -> None:
    """A deploy never ships the template's placeholder repository."""
    with pytest.raises(KubernetesContextError, match=r"service\.repos"):
        render_active_devops_configmap(k8s_dir=_template_dir(tmp_path), settings=_settings([], APP))


def test_the_active_config_map_without_the_github_app_is_refused_naming_each_setting(
    tmp_path: Path,
) -> None:
    """A deploy never ships the template's placeholder App."""
    with pytest.raises(KubernetesContextError) as raised:
        render_active_devops_configmap(
            k8s_dir=_template_dir(tmp_path),
            settings=_settings(["owner/repo"], GitHubAppConfig(slug="devops-roadmap")),
        )
    assert raised.value.message == (
        "The roadmap service acts as a GitHub App, so set 'service.github_app.app_id', "
        "'service.github_app.installation_id' in config.yaml."
    )
