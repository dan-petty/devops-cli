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
