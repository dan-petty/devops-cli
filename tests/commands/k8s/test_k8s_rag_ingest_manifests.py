"""deploy-stack tests for the RAG ingest Argo workflows (#1653)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.k8s import app

runner = CliRunner()


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
