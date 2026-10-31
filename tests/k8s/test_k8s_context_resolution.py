"""Test suite for resolving which Kubernetes context a command connects to."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.k8s.context import (
    apply_configured_k8s_context,
    configured_context,
    resolve_context,
)
from devops_cli.k8s.service import KubernetesService
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake

# =============================================================================
# Resolution
# =============================================================================


def test_the_configured_context_is_used_when_no_override_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorded context is consulted when no explicit override is given."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert resolve_context() == "homelab-k3s"


def test_an_explicit_context_overrides_the_configured_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A --context flag is a deliberate override for a single command."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert resolve_context("staging") == "staging"


def test_no_configured_context_defers_to_the_ambient_kubeconfig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Returning None lets load_kube_config use kubectl's current-context, as before."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: ''\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert resolve_context() is None


@pytest.mark.parametrize("value", ["''", "'   '"])
def test_an_unusable_configured_value_defers_to_the_ambient_kubeconfig(
    value: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A blank setting must not be passed to the Kubernetes client."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"k8s:\n  context: {value}\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert configured_context() is None


def test_surrounding_whitespace_is_stripped_from_the_configured_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trailing space in a hand-edited config.yaml names no context at all."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: '  homelab-k3s  '\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert resolve_context() == "homelab-k3s"


def test_surrounding_whitespace_is_stripped_from_an_explicit_context() -> None:
    """The same applies to a value arriving from a shell argument."""
    assert resolve_context("  staging  ") == "staging"


def test_a_blank_explicit_context_falls_back_rather_than_naming_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty --context is not a request to connect to a context named ''."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert resolve_context("   ") == "homelab-k3s"


def test_unreadable_settings_do_not_make_the_cluster_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configuration problem must degrade to the ambient kubeconfig, not fail the call."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("invalid: [yaml: broken\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    assert resolve_context() is None


def test_a_context_change_is_followed_rather_than_pinned_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A long-running process must follow a context change, not the value it started with."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: first\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))
    first = resolve_context()

    now = time.time() + 10.0
    cfg.write_text("k8s:\n  context: second\n")
    os.utime(cfg, (now, now))
    second = resolve_context()
    assert (first, second) == ("first", "second")


# =============================================================================
# Service Integration
# =============================================================================


@pytest.fixture
def homelab(config: Callable[..., Path]) -> FakeCluster:
    """A fake cluster that names `homelab-k3s` and `staging`, with `homelab-k3s` configured."""
    config(k8s={"context": "homelab-k3s"})
    return FakeCluster(contexts=("homelab-k3s", "staging"), current="staging")


def test_the_service_connects_using_the_configured_context(homelab: FakeCluster) -> None:
    """The service connects to the configured context."""
    KubernetesService(homelab).load_config()
    assert homelab.connects == ["homelab-k3s"]


def test_a_second_call_naming_the_same_cluster_reuses_the_client(homelab: FakeCluster) -> None:
    """An explicit context equal to the configured one is not a different cluster."""
    service = KubernetesService(homelab)
    service.load_config()
    service.load_config("homelab-k3s")
    assert homelab.connects == ["homelab-k3s"]


def test_switching_context_rebuilds_the_client(homelab: FakeCluster) -> None:
    """A genuinely different context must not be served from the cache."""
    service = KubernetesService(homelab)
    service.load_config()
    service.load_config("staging")
    assert homelab.connects == ["homelab-k3s", "staging"]


# =============================================================================
# DevContainer Post-Start Alignment
# =============================================================================


def test_post_start_points_kubectl_at_the_configured_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    process_fake.answer(
        lambda call: "get-contexts" in call.argv,
        ProcessAnswer(returncode=0, stdout="minikube\nhomelab-k3s\n"),
    )
    process_fake.answer(
        lambda call: "use-context" in call.argv,
        ProcessAnswer(returncode=0, stdout=""),
    )

    actions = apply_configured_k8s_context()
    use_calls = [c for c in process_fake.calls if "use-context" in c.argv]
    assert len(use_calls) == 1
    assert "homelab-k3s" in use_calls[0].argv
    assert "homelab-k3s" in actions[0]


def test_post_start_leaves_kubectl_alone_when_the_context_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    process_fake.answer(
        lambda call: "get-contexts" in call.argv,
        ProcessAnswer(returncode=0, stdout="minikube\n"),
    )

    actions = apply_configured_k8s_context()
    use_calls = [c for c in process_fake.calls if "use-context" in c.argv]
    assert len(use_calls) == 0
    assert "not in the kubeconfig" in actions[0]


def test_post_start_does_nothing_without_a_configured_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: ''\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    actions = apply_configured_k8s_context()
    assert actions == []
    assert len(process_fake.calls) == 0


def test_post_start_reports_a_failed_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    process_fake.answer(
        lambda call: "get-contexts" in call.argv,
        ProcessAnswer(returncode=0, stdout="homelab-k3s\n"),
    )
    process_fake.answer(
        lambda call: "use-context" in call.argv,
        ProcessAnswer(returncode=1, stderr="denied"),
    )

    actions = apply_configured_k8s_context()
    assert "Failed setting" in actions[0]


def test_post_start_tolerates_an_unreadable_kubeconfig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    process_fake.answer(
        lambda call: "get-contexts" in call.argv,
        ProcessAnswer(returncode=1, stderr="error"),
    )

    actions = apply_configured_k8s_context()
    assert actions == []


def test_post_start_dry_run_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    actions = apply_configured_k8s_context(dry_run=True)
    assert len(process_fake.calls) == 0
    assert "Would set" in actions[0]


def test_context_alignment_runs_after_the_minikube_supervisor() -> None:
    import inspect

    from devops_cli.commands import devcontainer

    source = inspect.getsource(devcontainer._run_post_start_lifecycle)
    align = source.index("apply_configured_k8s_context")
    supervisor = source.index("_spawn_background_k8s_bootstrap")
    assert align > supervisor
