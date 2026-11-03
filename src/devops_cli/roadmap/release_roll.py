"""Which release the cluster runs (#2917).

Image Updater writes the digest of the Service image into Deployment `roadmap-service` and the
digest of the runner image into CronJob `devops-cli-runner`. A release runs when the digests that
the tags of the release name in the registry equal both of them. `latest` moves with each release,
so a newer release that runs also means that an older one ran.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx2

from devops_cli.config.constants import (
    CONST_ROADMAP_RELEASE_IMAGE_PREFIX,
    CONST_ROADMAP_SERVICE_CONTAINER,
    CONST_ROADMAP_SERVICE_DEPLOYMENT,
)
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.docker.registry import tag_digest
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.roadmap.release_feed import ReleaseInfo


@dataclass(frozen=True)
class RolledDigests:
    """The digests that the cluster runs now, None for an image that names none."""

    service: str | None
    runner: str | None


def cluster_digests(jobs: ClusterJobs) -> RolledDigests:
    """The Service digest of the Deployment and the runner digest of the CronJob. Raises
    ClusterJobError when either object cannot be read."""
    return RolledDigests(
        service=jobs.deployment_digest(
            CONST_ROADMAP_SERVICE_DEPLOYMENT, CONST_ROADMAP_SERVICE_CONTAINER
        ),
        runner=jobs.template_digest(RUNNER_TEMPLATE),
    )


def live_release(
    releases: Sequence[ReleaseInfo], cluster: RolledDigests, client: httpx2.Client
) -> ReleaseInfo | None:
    """The first of `releases`, newest first, whose two tags name the digests of `cluster`, or
    None. It reads no tag of a release older than the one it returns. Raises RegistryReadError
    when the registry gives no digest."""
    if cluster.service is None or cluster.runner is None:
        return None
    for release in releases:
        service = _digest("service", release.tag, client)
        runner = _digest("runner", release.tag, client)
        if (service, runner) == (cluster.service, cluster.runner):
            return release
    return None


def _digest(image: str, tag: str, client: httpx2.Client) -> str:
    reference = f"{CONST_ROADMAP_RELEASE_IMAGE_PREFIX}/{image}:{tag}"
    return tag_digest(reference, client, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)


__all__ = ["RolledDigests", "cluster_digests", "live_release"]
