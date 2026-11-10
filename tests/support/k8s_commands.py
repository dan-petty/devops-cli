"""Answers for the programs and API objects that the `devops k8s` commands reach.

The helpers script `process_fake` (kubectl, helm and minikube) and give the Kubernetes API fake
the Argo CD objects that a command reads. A command test asks for a helper and the fixtures it
needs, installs no patch, and reads what the fakes recorded. Names are generic.
"""

from __future__ import annotations

import json
import subprocess

from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_APPLICATIONS,
)
from tests.support.cluster_secret_fakes import FakeCluster as KubectlWorld
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake


def ingress_list(*routes: tuple[str, str, str]) -> str:
    """The output of `kubectl get ingress -A -o json` for `(namespace, service, host)` routes."""
    items = [
        {
            "metadata": {"namespace": namespace, "name": f"{service}-ingress"},
            "spec": {
                "rules": [
                    {
                        "host": host,
                        "http": {"paths": [{"backend": {"service": {"name": service}}}]},
                    }
                ]
            },
        }
        for namespace, service, host in routes
    ]
    return json.dumps({"items": items})


def answer_ingresses(process_fake: ProcessFake, *routes: tuple[str, str, str]) -> None:
    """Make `kubectl get ingress -A` list the Ingresses that route to the given services."""
    process_fake.answer("kubectl get ingress", ProcessAnswer(stdout=ingress_list(*routes)))


def answer_helm_version(process_fake: ProcessFake, version: str = "v3.17.0") -> None:
    """Make `helm version` report `version`."""
    process_fake.answer("helm version", ProcessAnswer(stdout=f"{version}\n"))


def minikube_starts_on_demand(process_fake: ProcessFake) -> None:
    """Make `minikube status` report a stopped host until a `minikube start` has run."""

    def status(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        started = any(earlier.argv[:2] == ("minikube", "start") for earlier in process_fake.calls)
        return subprocess.CompletedProcess(
            list(call.argv), 0, "Running\n" if started else "Stopped\n", ""
        )

    process_fake.answer("minikube status", ProcessAnswer(side_effect=status))


def minikube_running(process_fake: ProcessFake) -> None:
    """Make `minikube status` report a running host."""
    process_fake.answer("minikube status", ProcessAnswer(stdout="Running\n"))


def minikube_stopped(process_fake: ProcessFake) -> None:
    """Make `minikube status` report a stopped host."""
    process_fake.answer("minikube status", ProcessAnswer(returncode=1, stdout="Stopped\n"))


def calls_starting(process_fake: ProcessFake, *prefix: str) -> list[tuple[str, ...]]:
    """The argv of each program start that begins with `prefix`."""
    return [call.argv for call in process_fake.calls if call.argv[: len(prefix)] == prefix]


def install_kubectl_world(process_fake: ProcessFake) -> KubectlWorld:
    """Answer every kubectl and helm start from one cluster of namespaces, Secrets and workloads.

    The world answers `helm version` with v3.17.0, applies a server-side apply of Secrets to its
    own, and answers any other command with success and no output. A later `process_fake.answer`
    still wins over it.
    """
    world = KubectlWorld(namespaces={"llm", "cloudflared"})
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=world))
    return world


def stock_push_keyring(keyring: FakeKeyring) -> None:
    """Give the keyring a value for each row of the cluster Secret table that a push reads."""
    keyring.values.update(
        {
            "llm_gateway_master_key": "sk-deploy-gateway-0001",
            "qdrant_api_key": "deploy-qdrant-0001",
            "runs_index_password": "deploy-runs-0001",
            "valkey_password": "deploy-cache-0001",
            "cloudflare_tunnel_token": "deploy-tunnel-0001",
        }
    )


def name_contexts(cluster: FakeCluster, *names: str) -> None:
    """Add kubeconfig contexts to the fake cluster, which refuses a context it does not name."""
    cluster.context_names.extend(name for name in names if name not in cluster.context_names)


def argo_cd_manages_the_cluster(cluster: FakeCluster) -> None:
    """Give the fake cluster the Argo CD Application `cluster`, which marks it as Argo-managed."""
    key = (CONST_ARGO_API_GROUP, CONST_ARGO_API_VERSION, CONST_ARGO_PLURAL_APPLICATIONS)
    cluster.custom_objects.objects.setdefault(key, []).append(
        {"metadata": {"name": "cluster", "namespace": "argocd"}}
    )
