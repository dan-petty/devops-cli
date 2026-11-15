"""The live part of the run console (#3076): the masked tail of the log of the runner Job pod.

The Kubernetes API is faked at its edge (`FakeCluster`), so `ClusterJobs` runs for real over it.
"""

from __future__ import annotations

from devops_cli.k8s.cluster_job_api import ClusterJobs
from tests.support.fakes.kubernetes import FakeCluster, pod

SECRET = "ghp_ABC1234567890123456789012345678901234567"


def _pod_log(cluster: FakeCluster, log: str) -> None:
    """The one pod of Job `runner-7`, whose log is `log`."""
    cluster.core.answers["list_namespaced_pod"] = [pod("runner-7-abc", namespace="devops")]
    cluster.core.answers["read_namespaced_pod_log"] = log


def test_a_secret_in_the_pod_log_is_masked(cluster: FakeCluster) -> None:
    from devops_cli.roadmap.follow_live import live_lines

    _pod_log(cluster, f"step group 1\ncurl -H 'Authorization: Bearer {SECRET}'\n")

    lines = live_lines(ClusterJobs(), "runner-7", 40)

    assert SECRET not in "\n".join(lines)
    assert "<masked" in lines[1]


def test_the_tail_reads_the_lines_of_the_named_job(cluster: FakeCluster) -> None:
    from devops_cli.roadmap.follow_live import live_lines

    _pod_log(cluster, "line 1\nline 2\n")

    lines = live_lines(ClusterJobs(), "runner-7", 40)

    read = next(c for c in cluster.core.calls if c[0] == "read_namespaced_pod_log")[1]
    assert lines == ["line 1", "line 2"]
    assert (read["name"], read["tail_lines"]) == ("runner-7-abc", 40)


def test_a_job_with_no_log_has_no_live_line(cluster: FakeCluster) -> None:
    from devops_cli.roadmap.follow_live import live_lines

    assert live_lines(ClusterJobs(), "runner-7", 40) == []
