"""Test suite for resolving which Kubernetes context a command connects to."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.k8s.context import configured_context, resolve_context


def _settings(context: Any) -> Any:
    """Build a settings object exposing k8s.context."""
    settings = MagicMock()
    settings.k8s.context = context
    return settings


def _with_settings(context: Any) -> Any:
    """Patch load_settings to return a settings object with the given context."""
    return patch("devops_cli.config.settings.load_settings", return_value=_settings(context))


# =============================================================================
# Resolution
# =============================================================================


def test_the_configured_context_is_used_when_no_override_is_given() -> None:
    """The recorded context was write-only: stored and displayed, never consulted.

    A workstation configured for one cluster therefore talked to whichever cluster
    kubectl's current-context named, and the only symptom was a connection error citing an
    address the operator never configured.
    """
    with _with_settings("homelab-k3s"):
        assert resolve_context() == "homelab-k3s"


def test_an_explicit_context_overrides_the_configured_one() -> None:
    """A --context flag is a deliberate override for a single command."""
    with _with_settings("homelab-k3s"):
        assert resolve_context("staging") == "staging"


def test_no_configured_context_defers_to_the_ambient_kubeconfig() -> None:
    """Returning None lets load_kube_config use kubectl's current-context, as before."""
    with _with_settings(""):
        assert resolve_context() is None


@pytest.mark.parametrize("value", [None, "", "   ", 42, object()])
def test_an_unusable_configured_value_defers_to_the_ambient_kubeconfig(value: Any) -> None:
    """A blank or non-string setting must not be passed to the Kubernetes client."""
    with _with_settings(value):
        assert configured_context() is None


def test_surrounding_whitespace_is_stripped_from_the_configured_context() -> None:
    """A trailing space in a hand-edited config.yaml names no context at all."""
    with _with_settings("  homelab-k3s  "):
        assert resolve_context() == "homelab-k3s"


def test_surrounding_whitespace_is_stripped_from_an_explicit_context() -> None:
    """The same applies to a value arriving from a shell argument."""
    with _with_settings(None):
        assert resolve_context("  staging  ") == "staging"


def test_a_blank_explicit_context_falls_back_rather_than_naming_nothing() -> None:
    """An empty --context is not a request to connect to a context named ''."""
    with _with_settings("homelab-k3s"):
        assert resolve_context("   ") == "homelab-k3s"


def test_unreadable_settings_do_not_make_the_cluster_unreachable() -> None:
    """A configuration problem must degrade to the ambient kubeconfig, not fail the call."""
    with patch("devops_cli.config.settings.load_settings", side_effect=RuntimeError("bad config")):
        assert resolve_context() is None


def test_settings_are_re_read_on_every_resolution() -> None:
    """A long-running process must follow a context change rather than the startup value.

    Capturing the setting once would leave the dashboard and the MCP server talking to the
    cluster configured when they started.
    """
    with patch("devops_cli.config.settings.load_settings") as load:
        load.side_effect = [_settings("first"), _settings("second")]
        assert (resolve_context(), resolve_context()) == ("first", "second")


# =============================================================================
# Service Integration
# =============================================================================


@pytest.fixture
def service() -> Any:
    """Provide a KubernetesService with no cached client."""
    from devops_cli.k8s.service import KubernetesService

    instance = KubernetesService()
    instance._config_loaded = False
    instance._active_context = None
    instance._core_v1 = None
    return instance


def _patched_k8s() -> Any:
    """Patch the kubernetes config and client modules used by load_config."""
    config_module = MagicMock()
    config_module.load_incluster_config.side_effect = RuntimeError("not in cluster")
    return config_module


def test_the_service_connects_using_the_configured_context(service: Any) -> None:
    """The defect: load_config(None) passed None straight through to load_kube_config."""
    config_module = _patched_k8s()
    with (
        patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(client=MagicMock(), config=config_module)},
        ),
        patch("devops_cli.k8s.service.resolve_context", return_value="homelab-k3s"),
    ):
        from kubernetes import config as patched_config  # noqa: F401

        service.load_config()

    config_module.load_kube_config.assert_called_once_with(context="homelab-k3s")


def test_the_service_records_the_resolved_context_not_the_argument(service: Any) -> None:
    """The cache key must be the context actually connected to.

    Treating `None` and the configured name as different keys would rebuild the client on
    alternating calls, and worse, could serve a client built for a context the caller did
    not ask for.
    """
    config_module = _patched_k8s()
    with (
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=config_module)}
        ),
        patch("devops_cli.k8s.service.resolve_context", return_value="homelab-k3s"),
    ):
        service.load_config()

    assert service._active_context == "homelab-k3s"


def test_a_second_call_naming_the_same_cluster_reuses_the_client(service: Any) -> None:
    """An explicit context equal to the configured one is not a different cluster."""
    config_module = _patched_k8s()
    with (
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=config_module)}
        ),
        patch("devops_cli.k8s.service.resolve_context", return_value="homelab-k3s"),
    ):
        service.load_config()
        service.load_config("homelab-k3s")

    assert config_module.load_kube_config.call_count == 1


def test_switching_context_rebuilds_the_client(service: Any) -> None:
    """A genuinely different context must not be served from the cache."""
    config_module = _patched_k8s()
    with (
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=config_module)}
        ),
        patch("devops_cli.k8s.service.resolve_context", side_effect=["homelab-k3s", "staging"]),
    ):
        service.load_config()
        service.load_config("staging")

    assert config_module.load_kube_config.call_count == 2


def test_in_cluster_configuration_still_takes_precedence(service: Any) -> None:
    """Running inside a pod must use the pod's service account, not a kubeconfig."""
    config_module = MagicMock()
    with (
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=config_module)}
        ),
        patch("devops_cli.k8s.service.resolve_context", return_value="homelab-k3s"),
    ):
        service.load_config()

    assert (
        config_module.load_incluster_config.call_count,
        config_module.load_kube_config.call_count,
    ) == (1, 0)


# =============================================================================
# Dashboard Integration
# =============================================================================


def test_the_dashboard_reads_the_configured_cluster() -> None:
    """The dashboard must report on the same cluster as every other command.

    Loading the kubeconfig without a context silently follows kubectl's current-context, so
    the panel would describe a different cluster than `devops k8s pods` in the same shell.
    """
    from devops_cli.ui import data_providers

    config_module = MagicMock()
    with (
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=config_module)}
        ),
        patch("devops_cli.k8s.context.resolve_context", return_value="homelab-k3s"),
    ):
        data_providers._get_k8s_client()

    config_module.load_kube_config.assert_called_once_with(context="homelab-k3s")


def test_the_dashboard_falls_back_to_in_cluster_configuration() -> None:
    """Running the dashboard inside the cluster must still work."""
    from devops_cli.ui import data_providers

    config_module = MagicMock()
    config_module.load_kube_config.side_effect = RuntimeError("no kubeconfig")
    with (
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=config_module)}
        ),
        patch("devops_cli.k8s.context.resolve_context", return_value=None),
    ):
        data_providers._get_k8s_client()

    config_module.load_incluster_config.assert_called_once()
