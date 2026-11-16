"""Unit tests for centralized language catalogs (errors, help, messages)."""

from __future__ import annotations

import os
import subprocess
import sys
from types import ModuleType

import pytest

import devops_cli.lang
import devops_cli.lang.en
from devops_cli.lang import ERRORS, HELP, MESSAGES, ErrorCatalog, HelpCatalog, LanguageCatalog
from tests.support.paths import REPO_ROOT

# A start reads `HELP` alone. The message and error catalogs load on first access, so a start
# builds the help catalog and nothing more (#3550).
_MAIN_START_PROBE = """\
import sys

import devops_cli.main

loaded = sorted(
    name
    for name in (
        "devops_cli.lang.en.errors",
        "devops_cli.lang.en.help",
        "devops_cli.lang.en.messages",
    )
    if name in sys.modules
)
print(f"loaded={loaded}")
"""
_CHILD_TIMEOUT_SECONDS = 180


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


def test_english_language_pack_dynamic_attributes() -> None:
    """The English language pack exports its catalogs on access (#3550)."""
    assert isinstance(devops_cli.lang.en.ERRORS, ErrorCatalog)
    assert isinstance(devops_cli.lang.en.HELP, HelpCatalog)
    assert isinstance(devops_cli.lang.en.MESSAGES, LanguageCatalog)
    assert devops_cli.lang.en.ErrorCatalog is ErrorCatalog
    assert devops_cli.lang.en.HelpCatalog is HelpCatalog
    assert devops_cli.lang.en.LanguageCatalog is LanguageCatalog


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


@pytest.mark.parametrize("module", [devops_cli.lang, devops_cli.lang.en], ids=["lang", "en"])
def test_an_unknown_name_of_a_catalog_module_raises_attribute_error(module: ModuleType) -> None:
    """A name the package does not hold stays absent, so a caller cannot read a catalog that is
    not there (#3550)."""
    with pytest.raises(AttributeError, match="has no attribute 'not_a_catalog'"):
        _ = module.not_a_catalog


@pytest.mark.live("python")
def test_a_start_that_imports_the_cli_main_loads_the_help_catalog_alone() -> None:
    """A start builds the help catalog alone: the message and error catalogs load on first use."""
    child = subprocess.run(
        [sys.executable, "-P", "-c", _MAIN_START_PROBE],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_SECONDS,
        check=False,
    )

    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "loaded=['devops_cli.lang.en.help']"
