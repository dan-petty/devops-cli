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
    assert MESSAGES.argo.url_not_configured
    assert MESSAGES.ci.ci_summary_title
    assert MESSAGES.devcontainer.already_exists
    assert MESSAGES.docker.pushed_success
    assert MESSAGES.grafana.exported_success
    assert MESSAGES.mcp.starting_stdio
    assert MESSAGES.serve.starting_service
    assert MESSAGES.scan.gitleaks_passed
    assert MESSAGES.rag.reset_cache_success
    assert MESSAGES.tls.cert_generated
    assert MESSAGES.ssh.key_generated
    assert MESSAGES.workspace.workspace_synced
    assert MESSAGES.release.bumped_version
    assert MESSAGES.pr.gh_cli_required
    assert MESSAGES.prometheus.query_instant_header
    assert MESSAGES.tf.plan_success


def test_domain_error_catalogs() -> None:
    """Verify domain-specific error catalog attributes exist and are non-empty."""
    assert ERRORS.argo.url_not_configured
    assert ERRORS.ci.python_version_fail
    assert ERRORS.devcontainer.manifest_not_found
    assert ERRORS.docker.cannot_connect
    assert ERRORS.grafana.invalid_uid
    assert ERRORS.mcp.invalid_transport
    assert ERRORS.release.invalid_version_format
    assert ERRORS.tls.ca_not_found
    assert ERRORS.prometheus.expr_too_long
    assert ERRORS.rag.path_not_found
    assert ERRORS.tf.binary_not_found
    assert ERRORS.pr.invalid_number


def test_domain_help_catalogs() -> None:
    """Verify domain-specific help catalog attributes exist and are non-empty."""
    assert HELP.argo.app
    assert HELP.ci.app
    assert HELP.devcontainer.app
    assert HELP.docker.app
    assert HELP.grafana.app
    assert HELP.mcp.app
    assert HELP.serve.app
    assert HELP.docs.app
    assert HELP.pr.app
    assert HELP.release.app
    assert HELP.review.app
    assert HELP.scan.app
    assert HELP.telemetry.app
    assert HELP.tls.app
    assert HELP.config.app
    assert HELP.install.app
    assert HELP.benchmark.app
    assert HELP.analyze.app
    assert HELP.prometheus.app
    assert HELP.rag.app
