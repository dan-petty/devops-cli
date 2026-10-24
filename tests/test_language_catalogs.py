"""Unit tests for centralized language catalogs (errors, help, messages)."""

from __future__ import annotations

from devops_cli.lang import ERRORS, HELP, MESSAGES, ErrorCatalog, HelpCatalog, LanguageCatalog


def test_language_catalogs_integrity() -> None:
    """Verify that language catalogs are properly initialized."""
    assert isinstance(MESSAGES, LanguageCatalog)
    assert isinstance(ERRORS, ErrorCatalog)
    assert isinstance(HELP, HelpCatalog)

    assert "DevSecOps" in MESSAGES.persona_titles.devsecops
    assert "Target path" in ERRORS.git.outside_boundary
    assert "Repository root" in HELP.options.repo
    assert "Ed25519" in HELP.ssh.app
    assert "Workspace file" in ERRORS.workspace.file_too_large
    assert "Python version" in ERRORS.uv.no_version_provided
    assert "Working tree clean." in MESSAGES.tools.working_tree_clean
    assert "Access Denied" in ERRORS.tools.access_denied_outside_workspace


def test_domain_message_catalogs() -> None:
    """Verify domain-specific message catalog attributes exist and are non-empty."""
    messages = [
        MESSAGES.argo.url_not_configured,
        MESSAGES.ci.ci_summary_title,
        MESSAGES.devcontainer.already_exists,
        MESSAGES.docker.pushed_success,
        MESSAGES.grafana.exported_success,
        MESSAGES.mcp.starting_stdio,
        MESSAGES.serve.starting_service,
        MESSAGES.scan.gitleaks_passed,
        MESSAGES.rag.reset_cache_success,
        MESSAGES.tls.cert_generated,
        MESSAGES.ssh.key_generated,
        MESSAGES.workspace.workspace_synced,
        MESSAGES.pr.gh_cli_required,
        MESSAGES.prometheus.query_instant_header,
        MESSAGES.tf.plan_success,
        MESSAGES.pipeline.executing,
        MESSAGES.ai.cache_title,
        MESSAGES.install.status_title,
    ]
    for msg in messages:
        assert isinstance(msg, str)
        assert len(msg) > 0


def test_domain_error_catalogs() -> None:
    """Verify domain-specific error catalog attributes exist and are non-empty."""
    errors = [
        ERRORS.argo.url_not_configured,
        ERRORS.ci.python_version_fail,
        ERRORS.devcontainer.manifest_not_found,
        ERRORS.docker.cannot_connect,
        ERRORS.grafana.invalid_uid,
        ERRORS.mcp.invalid_transport,
        ERRORS.tls.ca_not_found,
        ERRORS.prometheus.expr_too_long,
        ERRORS.rag.path_not_found,
        ERRORS.tf.binary_not_found,
        ERRORS.pr.invalid_number,
    ]
    for err in errors:
        assert isinstance(err, str)
        assert len(err) > 0


def test_domain_help_catalogs() -> None:
    """Verify domain-specific help catalog attributes exist and are non-empty."""
    helps = [
        HELP.argo.app,
        HELP.ci.app,
        HELP.devcontainer.app,
        HELP.docker.app,
        HELP.grafana.app,
        HELP.mcp.app,
        HELP.serve.app,
        HELP.docs.app,
        HELP.pr.app,
        HELP.review.app,
        HELP.scan.app,
        HELP.telemetry.app,
        HELP.tls.app,
        HELP.config.app,
        HELP.install.app,
        HELP.benchmark.app,
        HELP.analyze.app,
        HELP.prometheus.app,
        HELP.rag.app,
        HELP.pipeline.app,
    ]
    for h in helps:
        assert isinstance(h, str)
        assert len(h) > 0
