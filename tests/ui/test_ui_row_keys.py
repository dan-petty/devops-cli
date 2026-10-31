"""Tests for Row Keys behaviour in reactive dashboard."""

from __future__ import annotations

import json
import time

import pytest

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAINS,
    CONST_DOCKER_RESOURCES,
)
from devops_cli.ui.data_providers import (
    K8sSummary,
)
from devops_cli.ui.projections import (
    docker_resource_keys,
    docker_resource_rows,
    render_keys,
    render_rows,
    row_keys,
)
from devops_cli.ui.state import DomainSnapshot
from tests.support.ui import (
    SAMPLES,
    _docker,
    _pod,
)


@pytest.mark.parametrize("domain", CONST_DASHBOARD_DOMAINS)
def test_every_domain_keys_each_row_it_projects(domain: str) -> None:
    """A row without a key could not be found again after the table is redrawn."""
    snapshot = DomainSnapshot(domain=domain, data=SAMPLES[domain](), updated_at=time.time())
    assert len(render_keys(snapshot)) == len(render_rows(snapshot))


@pytest.mark.parametrize("resource", list(CONST_DOCKER_RESOURCES))
def test_every_docker_resource_keys_each_row_it_projects(resource: str) -> None:
    """Each Docker view is redrawn from the shared snapshot, so each needs its own keys."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    assert len(docker_resource_keys(resource, snapshot)) == len(
        docker_resource_rows(resource, snapshot)
    )


def test_an_unloaded_snapshot_has_no_row_keys() -> None:
    """Keys come from the data, so a domain that has not loaded has none."""
    assert (
        render_keys(DomainSnapshot(domain="k8s")),
        docker_resource_keys("images", DomainSnapshot(domain="docker")),
    ) == ([], [])


def test_row_keys_number_each_repeat_of_an_identity() -> None:
    """Two records with one identity are two rows, so their keys must still differ."""
    assert row_keys([("a", "b"), ("a", "b"), ("c",)]) == [
        '["a", "b", 0]',
        '["a", "b", 1]',
        '["c", 0]',
    ]


def test_pods_are_keyed_by_namespace_and_name() -> None:
    """A pod name is unique only within its namespace."""
    summary = K8sSummary(connected=True, pods=[_pod("api-0"), _pod("api-0", "b")])
    keys = render_keys(DomainSnapshot(domain="k8s", data=summary, updated_at=time.time()))
    assert [json.loads(key) for key in keys] == [["default", "api-0", 0], ["b", "api-0", 0]]
