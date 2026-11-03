"""Which release the cluster runs: the digests of the Service and the runner image in the cluster
are matched with the digests that the tags of each release name in the registry (#2917).

The Kubernetes API is faked at its edge (`FakeCluster`) and the registry at the HTTP edge
(`RegistryFake`).
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

import pytest
import yaml

from devops_cli.exceptions.docker import RegistryReadError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.roadmap.release_feed import ReleaseInfo
from devops_cli.roadmap.release_roll import RolledDigests, cluster_digests, live_release
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.oci_registry import RegistryFake
from tests.support.paths import REPO_ROOT
from tests.web_fakes import StubWeb

PREFIX = "ghcr.io/dan-petty/devops-cli"
SERVICE = {tag: "sha256:" + str(index) * 64 for index, tag in enumerate(("v1.0.0", "v1.1.0"), 1)}
RUNNER = {tag: "sha256:" + str(index) * 64 for index, tag in enumerate(("v1.0.0", "v1.1.0"), 3)}
NEWER = ReleaseInfo("v1.1.0", "u", datetime(2026, 11, 2, 10, tzinfo=UTC), False, False, "")
OLDER = ReleaseInfo("v1.0.0", "u", datetime(2026, 11, 2, 9, tzinfo=UTC), False, False, "")


def _registry() -> RegistryFake:
    digests: dict[str, str] = {}
    for tag in SERVICE:
        digests[f"{PREFIX}/service:{tag}"] = SERVICE[tag]
        digests[f"{PREFIX}/runner:{tag}"] = RUNNER[tag]
    return RegistryFake(digests)


def _roll(cluster: FakeCluster, service: str, runner: str) -> RolledDigests:
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    pod = template["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    pod["containers"][0]["image"] = f"{PREFIX}/runner@{runner}"
    deployment: dict[str, Any] = {
        "metadata": {"name": "roadmap-service", "namespace": "devops"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [{"name": "service", "image": f"{PREFIX}/service@{service}"}]
                }
            }
        },
    }
    cluster.custom_objects.objects[("batch", "v1", "cronjobs")] = [copy.deepcopy(template)]
    cluster.custom_objects.objects[("apps", "v1", "deployments")] = [deployment]
    return cluster_digests(ClusterJobs())


def test_the_cluster_digests_are_the_service_digest_of_the_deployment_and_the_runner_digest_of_the_cronjob(
    cluster: FakeCluster,
) -> None:
    assert _roll(cluster, SERVICE["v1.1.0"], RUNNER["v1.0.0"]) == RolledDigests(
        service=SERVICE["v1.1.0"], runner=RUNNER["v1.0.0"]
    )


@pytest.mark.parametrize(
    ("service", "runner", "expected"),
    [
        ("v1.1.0", "v1.1.0", "v1.1.0"),
        ("v1.0.0", "v1.0.0", "v1.0.0"),
        ("v1.1.0", "v1.0.0", None),
        ("v1.0.0", "v1.1.0", None),
    ],
    ids=["newer", "older", "only-the-service-rolled", "only-the-runner-rolled"],
)
def test_the_live_release_is_the_newest_whose_two_digests_run(
    cluster: FakeCluster,
    stub_web: StubWeb,
    service: str,
    runner: str,
    expected: str | None,
) -> None:
    rolled = _roll(cluster, SERVICE[service], RUNNER[runner])
    stub_web.serve(_registry())

    with new_http_client(level=EgressLevel.PUBLIC) as client:
        found = live_release((NEWER, OLDER), rolled, client)

    assert (found.tag if found else None) == expected


def test_the_registry_is_not_read_for_a_release_older_than_the_live_one(
    cluster: FakeCluster, stub_web: StubWeb
) -> None:
    rolled = _roll(cluster, SERVICE["v1.1.0"], RUNNER["v1.1.0"])
    stub_web.serve(_registry())

    with new_http_client(level=EgressLevel.PUBLIC) as client:
        live_release((NEWER, OLDER), rolled, client)

    read = [str(request.url) for request in stub_web.sent if "manifests" in str(request.url)]
    assert read
    assert not any("v1.0.0" in url for url in read)


def test_a_registry_that_gives_no_digest_propagates(
    cluster: FakeCluster, stub_web: StubWeb
) -> None:
    rolled = _roll(cluster, SERVICE["v1.1.0"], RUNNER["v1.1.0"])
    stub_web.serve(RegistryFake({}))

    with (
        new_http_client(level=EgressLevel.PUBLIC) as client,
        pytest.raises(RegistryReadError, match="no manifest"),
    ):
        live_release((NEWER, OLDER), rolled, client)
