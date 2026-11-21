"""The live part of the run console (#3076): the masked tail of the log of the runner Job pod.

`live_lines` reads the log of the pod of the runner Job through the Kubernetes client and masks
each line with `mask_secrets`, as the runner masks each line of its own log. It reads no GitHub
data and parses no line: the rows of the console come from the events of the recorded trace.
"""

from __future__ import annotations

from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.security.sanitizer import mask_secrets

__all__ = ["live_lines"]


def live_lines(jobs: ClusterJobs, name: str, lines: int) -> list[str]:
    """The last `lines` lines of the log of the pod of Job `name`, each masked as a secret. On the
    phases (#3700), the log is of the container that runs."""
    return [mask_secrets(line) for line in jobs.log_tail(name, lines).splitlines()]
