"""Environment trees, and answers for the programs and API objects that `devops k8s` reaches.

devops-cli ships no environment tree, so a command test builds one: the fixtures `env_tree` and
`environment_repo` give a whole one, from the stubs of `tests/fixtures/k8s_environment` and the
Argo CD Applications that the product's stack tables name. The helpers script `process_fake`
(kubectl, helm and minikube) and give the Kubernetes API fake the Argo CD objects that a command
reads. A command test asks for a helper and the fixtures it needs, installs no patch, and reads
what the fakes recorded. Names are generic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Final

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_APPLICATIONS,
    CONST_CANONICAL_OCI_SOURCE,
)
from tests.support.cluster_secret_fakes import FakeCluster as KubectlWorld
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.paths import FIXTURES, REPO_ROOT

_ENVIRONMENT_STUBS: Final[Path] = FIXTURES / "k8s_environment"
_CLUSTER_SECRETS_TABLE: Final[Path] = FIXTURES / "cluster-secrets.toml"
_PRODUCT_BASE: Final[Path] = Path("k8s", "devops")


def write_environment_tree(root: Path) -> Path:
    """Write at `root` a whole environment tree, and return `root`: the stubs of
    `tests/fixtures/k8s_environment`, the cluster Secret table, and the Argo CD Applications of
    every stack. The Applications are generated, so no file holds a release list or a chart
    version."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        APPLICATIONS_BY_STACK,
        HELM_RELEASES_BY_STACK,
    )

    shutil.copytree(_ENVIRONMENT_STUBS, root, dirs_exist_ok=True)
    from devops_cli.commands.k8s.stack_lifecycle import MANIFESTS_BY_STACK, POST_HELM_BY_STACK

    for stack in HELM_RELEASES_BY_STACK:
        write_chart_applications(root, stack)
    others = {*APPLICATIONS_BY_STACK, *MANIFESTS_BY_STACK, *POST_HELM_BY_STACK}
    for stack in others - set(HELM_RELEASES_BY_STACK):
        write_path_applications(root, stack)
    return root


def write_stack_paths(tree: Path, stack: str) -> None:
    """Write into the environment tree `tree` each file and folder that the stack tables of
    deploy-stack name for `stack`, and the root kustomization, as empty stubs where the tree has
    none. The tables give the names, so no file holds a second list of them."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        KUSTOMIZATIONS_BY_STACK,
        MANIFESTS_BY_STACK,
        POST_HELM_BY_STACK,
    )

    named = [
        Path("kustomization.yaml"),
        *MANIFESTS_BY_STACK.get(stack, ()),
        *KUSTOMIZATIONS_BY_STACK.get(stack, ()),
        *POST_HELM_BY_STACK.get(stack, ()),
    ]
    for path in named:
        target = tree / path
        if target.exists():
            continue
        if target.suffix:
            file = target
        else:
            file = target / "kustomization.yaml"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("resources: []\n" if file.name == "kustomization.yaml" else "", "utf-8")


def write_cluster_secrets(tree: Path) -> None:
    """Write into the environment tree `tree` the cluster Secret table of the test data."""
    tree.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_CLUSTER_SECRETS_TABLE, tree / _CLUSTER_SECRETS_TABLE.name)


@pytest.fixture
def env_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A whole environment tree outside any repository, for the option `--k8s-dir`."""
    return write_environment_tree(tmp_path_factory.mktemp("environment") / "tree")


@pytest.fixture
def environment_repo(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """The current folder is a repository whose project profile names its environment tree `k8s`.
    The tree also holds a copy of the product base `k8s/devops`, which devops-cli ships. A command
    with no `--k8s-dir` reads this tree, and so does `--k8s-dir k8s`."""
    repo = tmp_path_factory.mktemp("environment") / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".devops").mkdir()
    (repo / ".devops" / "project.toml").write_text('[kubernetes]\ndir = "k8s"\n', "utf-8")
    write_environment_tree(repo / "k8s")
    shutil.copytree(REPO_ROOT / _PRODUCT_BASE, repo / _PRODUCT_BASE)
    monkeypatch.chdir(repo)
    return repo


def write_chart_applications(tree: Path, stack: str, version: str = "1.0.0") -> None:
    """Write into the environment tree `tree` one Argo CD Application for each Helm release of
    `stack`, which pins its chart at `version`, as deploy-stack reads the version (#6060)."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    folder = tree / "argocd" / "apps"
    folder.mkdir(parents=True, exist_ok=True)
    for release in HELM_RELEASES_BY_STACK[stack]:
        application = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": release["name"]},
            "spec": {
                "sources": [
                    {
                        "repoURL": "https://charts.example.com",
                        "chart": release["chart"].rsplit("/", 1)[-1],
                        "targetRevision": version,
                    }
                ]
            },
        }
        (folder / f"{release['name']}.yaml").write_text(yaml.safe_dump(application), "utf-8")
    write_path_applications(tree, stack)


def write_path_applications(tree: Path, stack: str) -> None:
    """Give each Argo CD Application of `tree` that `APPLICATIONS_BY_STACK` names for `stack` a
    path source: an empty kustomization of the tree, which deploy-stack builds (#6681). The tree
    has no `origin`, so the source of devops-cli stands for it. An Application of a chart keeps
    its chart source. The tree also gets its cluster Secret table and the files of the stack."""
    from devops_cli.commands.k8s.stack_lifecycle import APPLICATIONS_BY_STACK

    write_cluster_secrets(tree)
    write_stack_paths(tree, stack)
    folder = tree / "argocd" / "apps"
    folder.mkdir(parents=True, exist_ok=True)
    for name in APPLICATIONS_BY_STACK.get(stack, ()):
        source = tree / "sources" / name
        source.mkdir(parents=True, exist_ok=True)
        (source / "kustomization.yaml").write_text("resources: []\n", "utf-8")
        file = folder / f"{name}.yaml"
        application = (
            yaml.safe_load(file.read_text("utf-8"))
            if file.is_file()
            else {"apiVersion": "argoproj.io/v1alpha1", "kind": "Application"}
        )
        application.setdefault("metadata", {"name": name})
        sources = application.setdefault("spec", {}).setdefault("sources", [])
        sources.append(
            {
                "repoURL": CONST_CANONICAL_OCI_SOURCE,
                "targetRevision": "main",
                "path": f"{tree.name}/sources/{name}",
            }
        )
        file.write_text(yaml.safe_dump(application), "utf-8")


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
