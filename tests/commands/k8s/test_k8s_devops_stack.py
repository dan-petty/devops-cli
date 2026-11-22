"""Tests for the Kubernetes devops stack lifecycle and inclusion in stack all."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.networking import VALID_STACKS, _resolve_stacks
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.process import ProcessFake

runner = CliRunner()


# The GitHub App the Service acts as, in config.yaml (ADR 0015).
_GITHUB_APP = "  github_app:\n    app_id: 1001\n    installation_id: 42\n    slug: devops-roadmap\n"


def test_devops_stack_registration_and_resolution() -> None:
    """Verify devops stack is registered and resolved in stack all and stack devops."""
    assert (
        "devops" in VALID_STACKS,
        _resolve_stacks("devops"),
        _resolve_stacks("all"),
    ) == (
        True,
        ["devops"],
        ["infra", "llm", "logging", "devops", "gitea", "chat"],
    )


def test_the_devops_stack_applies_the_rate_limit_before_the_ingress_that_names_it() -> None:
    """Traefik refuses an Ingress that names a Middleware that does not exist yet (#2476)."""
    from devops_cli.commands.k8s.stack_lifecycle import PRODUCT_MANIFESTS_BY_STACK

    paths = PRODUCT_MANIFESTS_BY_STACK["devops"]

    assert paths.index(Path("roadmap-service", "middleware.yaml")) < paths.index(
        Path("roadmap-service", "ingress.yaml")
    )


def test_the_devops_stack_applies_the_searxng_service_monitor() -> None:
    """The monitor needs the ServiceMonitor CRD of the Prometheus operator release, so deploy-stack
    applies it after the Helm releases and not before them (#4201)."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        PRODUCT_MANIFESTS_BY_STACK,
        PRODUCT_POST_HELM_BY_STACK,
    )

    monitor = Path("searxng", "servicemonitor.yaml")

    assert (
        monitor in PRODUCT_POST_HELM_BY_STACK["devops"],
        monitor in PRODUCT_MANIFESTS_BY_STACK["devops"],
    ) == (True, False)


def test_deploy_stack_devops_dry_run(
    isolate_devops_cli_config: Path, process_fake: ProcessFake
) -> None:
    """Verify deploy-stack --stack devops includes devops manifests in dry-run output."""
    from devops_cli.config.settings import reset_settings_cache

    with isolate_devops_cli_config.open("a", encoding="utf-8") as config:
        config.write("service:\n  repos:\n    - owner/repo\n" + _GITHUB_APP)
    reset_settings_cache()
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "devops"])
        assert (
            result.exit_code,
            "devops/configmap.yaml" in result.output,
            "roadmap-service" in result.output,
            "cronjob.yaml" in result.output,
            "searxng/configmap.yaml" in result.output,
        ) == (0, False, True, True, True)
    finally:
        set_dry_run(False)


def test_deploy_stack_domain_option_in_dry_run(
    isolate_devops_cli_config: Path, process_fake: ProcessFake
) -> None:
    """Verify deploy-stack propagates domain option in dry-run output."""
    from devops_cli.config.settings import reset_settings_cache

    with isolate_devops_cli_config.open("a", encoding="utf-8") as config:
        config.write("service:\n  repos:\n    - owner/repo\n" + _GITHUB_APP)
    reset_settings_cache()
    set_dry_run(True)
    try:
        result = runner.invoke(
            app, ["deploy-stack", "--stack", "devops", "--domain", "example.com"]
        )
        assert (
            result.exit_code,
            "example.com" in result.output,
        ) == (0, True)
    finally:
        set_dry_run(False)


def test_apply_single_manifest_renders_domain_template(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Verify _apply_single_manifest renders domain placeholders via stdin."""
    from devops_cli.commands.k8s.stack_lifecycle import _apply_single_manifest

    manifest = tmp_path / "test-ingress.yaml"
    manifest.write_text("host: hooks.${DOMAIN}\npath: /test\n", encoding="utf-8")

    _apply_single_manifest(str(manifest), ["--context", "test-ctx"], domain="example.com")

    assert [(call.argv, call.stdin, call.check) for call in process_fake.calls] == [
        (
            ("kubectl", "apply", "-f", "-", "--context", "test-ctx"),
            "host: hooks.example.com\npath: /test\n",
            False,
        )
    ]
