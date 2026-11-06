"""Waiting for an Argo Workflow to finish."""

from __future__ import annotations

from devops_cli.argo.crd import ArgoCRDService
from devops_cli.config.constants import CONST_ARGO_WORKFLOW_TERMINAL_PHASES
from devops_cli.config.defaults import (
    DEFAULT_WORKFLOW_POLL_INTERVAL_SECONDS,
    DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS,
)
from devops_cli.core import clock
from devops_cli.exceptions.argo import ArgoWorkflowTimeoutError
from devops_cli.lang import MESSAGES
from devops_cli.models.argo import ArgoWorkflowState


def await_workflow(
    service: ArgoCRDService,
    name: str,
    namespace: str,
    *,
    timeout: float = DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS,
    poll_interval: float = DEFAULT_WORKFLOW_POLL_INTERVAL_SECONDS,
) -> ArgoWorkflowState:
    """Poll a Workflow until it reaches a terminal phase and return its last state.

    The function reads the Workflow at once, then once every `poll_interval` seconds. It raises
    `ArgoWorkflowTimeoutError` when the Workflow is not terminal after `timeout` seconds.
    """
    deadline = clock.monotonic() + timeout
    state = service.get_workflow(name, namespace)
    while state.phase not in CONST_ARGO_WORKFLOW_TERMINAL_PHASES:
        if clock.monotonic() >= deadline:
            raise ArgoWorkflowTimeoutError(
                MESSAGES.argo.workflow_wait_timeout.format(name=name, seconds=timeout),
                resource=name,
                namespace=namespace,
            )
        clock.sleep(poll_interval)
        state = service.get_workflow(name, namespace)
    return state


__all__ = ["await_workflow"]
