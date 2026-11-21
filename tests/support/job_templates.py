"""A CronJob template in the shape that `build_job` and `ClusterJobs` read (#6082).

The tests of the Jobs of the roadmap Service build their CronJob here, not from a committed
manifest under `k8s/`, so a change of a value of the manifest needs no test change. The template
holds what the code reads: the name of the CronJob, the Job spec with its deadline, and the pod
template with the container that `JobTemplate.container` names.
"""

from __future__ import annotations

from typing import Any

from devops_cli.k8s.cluster_job import JOB_NAMESPACE, JobTemplate

TEMPLATE_IMAGE = "registry.example.com/devops-cli/runner"
TEMPLATE_DEADLINE = 3600
TEMPLATE_RESOURCES: dict[str, dict[str, str]] = {
    "requests": {"cpu": "500m", "memory": "1Gi", "ephemeral-storage": "1Gi"},
    "limits": {"cpu": "1", "memory": "2Gi", "ephemeral-storage": "2Gi"},
}
TEMPLATE_ENV = [{"name": "DEVOPS_CLI_CONFIG", "value": "/etc/devops-cli/devops-cli.yaml"}]


def cronjob_template(template: JobTemplate, *, image: str = TEMPLATE_IMAGE) -> dict[str, Any]:
    """The CronJob of `template`: a suspended template whose pod runs the container of the
    template with `image`, a deadline, resources and one environment value."""
    labels = {"app.kubernetes.io/name": template.cronjob}
    return {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {"name": template.cronjob, "namespace": JOB_NAMESPACE, "labels": labels},
        "spec": {
            "suspend": True,
            "jobTemplate": {
                "spec": {
                    "backoffLimit": 0,
                    "activeDeadlineSeconds": TEMPLATE_DEADLINE,
                    "template": {
                        "metadata": {"labels": dict(labels)},
                        "spec": {
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": template.container,
                                    "image": image,
                                    "env": [dict(entry) for entry in TEMPLATE_ENV],
                                    "resources": {
                                        part: dict(values)
                                        for part, values in TEMPLATE_RESOURCES.items()
                                    },
                                }
                            ],
                        },
                    },
                }
            },
        },
    }


PHASE_RESOURCES: dict[str, dict[str, str]] = {
    "requests": {"cpu": "100m", "memory": "256Mi"},
    "limits": {"cpu": "500m", "memory": "512Mi"},
}


def phase_cronjob_template(template: JobTemplate, *, image: str = TEMPLATE_IMAGE) -> dict[str, Any]:
    """The CronJob of `template` on the phases (#3700): the init containers `prepare` and `agent`
    and the container `publish`, each with `image`. `agent` has the resources of the template,
    and `prepare` and `publish` a small fixed row."""
    cronjob = cronjob_template(template, image=image)
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    (container,) = pod_spec["containers"]

    def phase(name: str, resources: dict[str, dict[str, str]]) -> dict[str, Any]:
        return {
            **container,
            "name": name,
            "env": [dict(entry) for entry in TEMPLATE_ENV],
            "resources": {part: dict(values) for part, values in resources.items()},
        }

    pod_spec["initContainers"] = [
        phase("prepare", PHASE_RESOURCES),
        phase("agent", TEMPLATE_RESOURCES),
    ]
    pod_spec["containers"] = [phase("publish", PHASE_RESOURCES)]
    return cronjob
