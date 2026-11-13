"""Offline manifest and configuration tests for RAG ingest Argo workflows (#1653)."""

from __future__ import annotations

import math
from pathlib import Path

import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.config.defaults import DEFAULT_SERVICE_POLL_INTERVAL_SECONDS
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
DEVOPS_DIR = K8S_DIR / "devops"
LLM_DIR = K8S_DIR / "llm"

runner = CliRunner()


def cron_schedule_for_poll_interval(interval_seconds: int) -> str:
    """The shortest whole-minute cron period that is not shorter than interval_seconds."""
    minutes = max(1, math.ceil(interval_seconds / 60))
    return f"*/{minutes} * * * *"


def test_network_policy_selects_only_ingest_pods_for_qdrant_6333() -> None:
    """NetworkPolicy selects only ingest pods for TCP 6333 egress and ingress."""
    egress_policy_file = DEVOPS_DIR / "networkpolicy-rag-ingest.yaml"
    assert egress_policy_file.is_file(), f"Missing {egress_policy_file}"
    egress_policy = yaml.safe_load(egress_policy_file.read_text(encoding="utf-8"))

    llm_policy_file = LLM_DIR / "networkpolicy.yaml"
    llm_policy = yaml.safe_load(llm_policy_file.read_text(encoding="utf-8"))

    # Egress: from devops to llm qdrant
    assert egress_policy["spec"]["podSelector"] == {
        "matchLabels": {"app.kubernetes.io/name": "rag-ingest"}
    }
    egress_rules = egress_policy["spec"]["egress"]
    has_qdrant_egress = any(
        any(p.get("port") == 6333 and p.get("protocol") == "TCP" for p in rule.get("ports", []))
        for rule in egress_rules
    )
    assert has_qdrant_egress, "rag-ingest-egress must permit egress to TCP port 6333"

    # Ingress: llm perimeter permits TCP 6333 from devops ingest pods only
    ingress_rules = llm_policy["spec"].get("ingress", [])
    qdrant_ingress_peers = [
        peer
        for rule in ingress_rules
        if any(p.get("port") == 6333 and p.get("protocol") == "TCP" for p in rule.get("ports", []))
        for peer in rule.get("from", [])
    ]
    assert len(qdrant_ingress_peers) == 1
    peer = qdrant_ingress_peers[0]
    assert peer.get("namespaceSelector") == {
        "matchLabels": {"kubernetes.io/metadata.name": "devops"}
    }
    assert peer.get("podSelector") == {"matchLabels": {"app.kubernetes.io/name": "rag-ingest"}}


def test_workflow_template_mutex_and_cronworkflow_concurrency_policy() -> None:
    """The WorkflowTemplate holds mutex rag-ingest and CronWorkflow sets concurrencyPolicy: Forbid."""
    template_file = DEVOPS_DIR / "workflowtemplate-rag-ingest.yaml"
    assert template_file.is_file(), f"Missing {template_file}"
    template = yaml.safe_load(template_file.read_text(encoding="utf-8"))

    cron_file = DEVOPS_DIR / "cronworkflow-rag-ingest.yaml"
    assert cron_file.is_file(), f"Missing {cron_file}"
    cron = yaml.safe_load(cron_file.read_text(encoding="utf-8"))

    assert template["spec"]["synchronization"]["mutex"]["name"] == "rag-ingest"
    assert cron["spec"]["concurrencyPolicy"] == "Forbid"


def test_cronworkflow_schedule_follows_poll_interval() -> None:
    """The CronWorkflow uses shortest whole-minute period not shorter than service.poll_interval_seconds."""
    cron_file = DEVOPS_DIR / "cronworkflow-rag-ingest.yaml"
    assert cron_file.is_file(), f"Missing {cron_file}"
    cron = yaml.safe_load(cron_file.read_text(encoding="utf-8"))

    default_schedule = cron_schedule_for_poll_interval(DEFAULT_SERVICE_POLL_INTERVAL_SECONDS)
    assert default_schedule == "*/3 * * * *"
    assert cron["spec"]["schedule"] == "*/3 * * * *"


def test_ingest_template_sets_embedding_concurrency_to_one() -> None:
    """The ingest template sets ai.gateway_concurrency.embedding to 1."""
    template_file = DEVOPS_DIR / "workflowtemplate-rag-ingest.yaml"
    assert template_file.is_file(), f"Missing {template_file}"
    template = yaml.safe_load(template_file.read_text(encoding="utf-8"))

    (step_template,) = template["spec"]["templates"]
    env_vars = {e["name"]: e.get("value") for e in step_template["container"]["env"]}
    assert env_vars.get("DEVOPS_CLI_AI_GATEWAY_CONCURRENCY_EMBEDDING") == "1"


def test_rag_ingest_behind_alert_rule() -> None:
    """The product rules ship a RagIngestBehind alert that fires after two schedule periods
    without success (#1653, #5292)."""
    values_file = DEVOPS_DIR / "monitoring" / "prometheus-rules-values.yaml"
    values = yaml.safe_load(values_file.read_text(encoding="utf-8"))
    groups = values["serverFiles"]["devops_cli_alerting_rules.yml"]["groups"]

    alert = next(
        (
            rule
            for group in groups
            for rule in group.get("rules", [])
            if rule.get("alert") == "RagIngestBehind"
        ),
        None,
    )
    assert alert is not None, "RagIngestBehind alert must be defined"
    assert "devops_cli_rag_ingest_last_success_timestamp_seconds" in alert["expr"]
    assert "> 360" in alert["expr"]
    assert alert["labels"]["severity"] == "warning"


def test_deploy_stack_all_renders_ingest_workflow_template_and_cronworkflow(
    isolate_devops_cli_config: Path,
) -> None:
    """devops k8s deploy-stack --stack all renders the WorkflowTemplate and CronWorkflow."""
    from devops_cli.config.settings import reset_settings_cache

    with isolate_devops_cli_config.open("a", encoding="utf-8") as config:
        config.write(
            "service:\n"
            "  repos:\n"
            "    - owner/repo\n"
            "  github_app:\n"
            "    app_id: 1001\n"
            "    installation_id: 42\n"
            "    slug: devops-roadmap\n"
        )
    reset_settings_cache()
    res = runner.invoke(app, ["deploy-stack", "--stack", "all", "--dry-run"])
    assert res.exit_code == 0, f"Output: {res.output}\nException: {res.exception}"
    assert "k8s/devops/workflowtemplate-rag-ingest.yaml" in res.output
    assert "k8s/devops/cronworkflow-rag-ingest.yaml" in res.output
