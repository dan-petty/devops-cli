"""The database of the LLM gateway: a CloudNativePG Cluster that the operator fills with a Secret (#1635)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _POST_HELM_BY_STACK,
)
from tests.gate.k8s_render import applied_documents, kustomize
from tests.support.paths import REPO_ROOT

LLM_DIR = REPO_ROOT / "k8s" / "llm"
DATABASE_FILE = LLM_DIR / "gateway-db.yaml"
GATEWAY_DIR = LLM_DIR / "gateway"

CLUSTER_NAME = "llm-gateway-db"
# CloudNativePG names the Secret of the application user `<cluster>-app`, and puts a ready
# connection string in its `uri` key.
OPERATOR_SECRET = f"{CLUSTER_NAME}-app"
DATABASE_PORT = 5432


def _documents(path: Path) -> list[dict[str, Any]]:
    return [
        doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(doc, dict)
    ]


def _of_kind(documents: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [doc for doc in documents if doc["kind"] == kind]


def _gateway_deployment() -> dict[str, Any]:
    documents = [doc for doc in yaml.safe_load_all(kustomize(LLM_DIR).stdout) if doc]
    return next(
        doc
        for doc in documents
        if doc["kind"] == "Deployment" and doc["metadata"]["name"] == "llm-gateway"
    )


def _gateway_container() -> dict[str, Any]:
    container: dict[str, Any] = _gateway_deployment()["spec"]["template"]["spec"]["containers"][0]
    return container


def _policy(name: str) -> dict[str, Any]:
    documents = [doc for doc in yaml.safe_load_all(kustomize(LLM_DIR).stdout) if doc]
    return next(
        doc
        for doc in documents
        if doc["kind"] == "NetworkPolicy" and doc["metadata"]["name"] == name
    )


def check_the_database_is_a_cloudnative_pg_cluster_that_keeps_its_data_and_has_no_secret_in_git() -> (
    None
):
    """The Cluster has one instance on `local-path`, which Argo CD never prunes or deletes. It
    names no `bootstrap.initdb.secret`, so the operator generates the application user and the
    Secret `llm-gateway-db-app` when it creates the database, and no person pushes a password.
    Superuser access over the network stays off."""
    documents = _documents(DATABASE_FILE)
    (cluster,) = _of_kind(documents, "Cluster")
    spec = cluster["spec"]
    initdb = spec["bootstrap"]["initdb"]

    assert (
        cluster["apiVersion"],
        cluster["metadata"]["name"],
        cluster["metadata"]["namespace"],
        cluster["metadata"]["annotations"]["argocd.argoproj.io/sync-options"],
        spec["instances"],
        spec["storage"]["storageClass"],
        spec["enableSuperuserAccess"],
        "secret" in initdb,
        [doc["kind"] for doc in documents if doc["kind"] in ("Secret", "PersistentVolumeClaim")],
    ) == (
        "postgresql.cnpg.io/v1",
        CLUSTER_NAME,
        "llm",
        "Prune=false,Delete=false",
        1,
        "local-path",
        False,
        False,
        [],
    )


def check_the_gateway_reads_database_url_from_the_secret_of_the_operator() -> None:
    """DATABASE_URL is the `uri` key of Secret `llm-gateway-db-app`, with no literal value, so
    git holds no password and no connection string."""
    env = {item["name"]: item for item in _gateway_container()["env"]}

    assert env["DATABASE_URL"] == {
        "name": "DATABASE_URL",
        "valueFrom": {"secretKeyRef": {"name": OPERATOR_SECRET, "key": "uri"}},
    }


def check_the_gateway_writes_its_migrations_to_an_empty_dir_and_keeps_a_read_only_root() -> None:
    """LiteLLM copies its migrations to LITELLM_MIGRATION_DIR before `prisma migrate deploy`, so
    that directory is an emptyDir, and the root file system stays read-only."""
    pod = _gateway_deployment()["spec"]["template"]["spec"]
    container = pod["containers"][0]
    directory = next(item for item in container["env"] if item["name"] == "LITELLM_MIGRATION_DIR")
    mount = next(m for m in container["volumeMounts"] if m["mountPath"] == directory["value"])
    volume = next(v for v in pod["volumes"] if v["name"] == mount["name"])

    assert (
        volume,
        mount.get("readOnly", False),
        container["securityContext"]["readOnlyRootFilesystem"],
    ) == ({"name": mount["name"], "emptyDir": {}}, False, True)


def check_the_gateway_has_time_to_run_its_migrations_before_the_liveness_probe_starts() -> None:
    """The proxy opens its port after `prisma migrate deploy`. A startup probe holds the liveness
    and readiness probes back for up to ten minutes, so Kubernetes does not kill a pod that is
    still migrating."""
    probe = _gateway_container()["startupProbe"]

    assert (
        probe["httpGet"],
        probe["periodSeconds"] * probe["failureThreshold"] >= 600,
    ) == ({"path": "/health/liveliness", "port": 4000}, True)


def check_a_failed_migration_ends_the_start_up_of_the_gateway() -> None:
    """Without ENFORCE_PRISMA_MIGRATION_CHECK, LiteLLM logs a failed `prisma migrate deploy` and
    starts on an empty schema, and nothing runs the migration again. With it, the pod exits and
    the restart loop waits for the database."""
    env = {item["name"]: item.get("value") for item in _gateway_container()["env"]}

    assert env["ENFORCE_PRISMA_MIGRATION_CHECK"] == "true"


def check_the_readiness_of_the_gateway_does_not_depend_on_the_database() -> None:
    """/health/readiness answers 503 while the database is down, and Kubernetes would then take
    every gateway pod out of the Service, also for clients of the master key. The readiness probe
    uses the liveliness path, so a database outage refuses only the keys that need the database."""
    probe = _gateway_container()["readinessProbe"]

    assert probe["httpGet"] == {"path": "/health/liveliness", "port": 4000}


def check_the_gateway_refuses_a_key_it_cannot_check_when_the_database_is_down() -> None:
    """The gateway is reachable from outside the cluster, so `allow_requests_on_db_unavailable`
    stays off. Models stay in git, so `store_model_in_db` stays off too."""
    settings = yaml.safe_load((GATEWAY_DIR / "config.yaml").read_text(encoding="utf-8"))[
        "general_settings"
    ]

    assert (
        settings.get("allow_requests_on_db_unavailable", False),
        settings["store_model_in_db"],
    ) == (False, False)


def check_only_the_gateway_reaches_the_database_and_the_database_calls_only_dns_and_the_api() -> (
    None
):
    """The database admits the gateway's pods and the operator on 5432, and nothing else on that
    port. Its egress is DNS and the Kubernetes API (the instance manager reads Secrets and updates
    status through it), the form of the Mattermost database."""
    policy = next(
        doc
        for doc in _of_kind(_documents(DATABASE_FILE), "NetworkPolicy")
        if doc["metadata"]["name"] == "llm-gateway-db-perimeter"
    )
    spec = policy["spec"]
    ingress = {
        yaml.safe_dump(rule["from"], sort_keys=True): [p["port"] for p in rule["ports"]]
        for rule in spec["ingress"]
    }
    egress_ports = [[p["port"] for p in rule["ports"]] for rule in spec["egress"]]

    assert (
        spec["podSelector"],
        spec["policyTypes"],
        ingress,
        egress_ports,
    ) == (
        {"matchLabels": {"cnpg.io/cluster": CLUSTER_NAME}},
        ["Ingress", "Egress"],
        {
            yaml.safe_dump(
                [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "llm-gateway"}}}],
                sort_keys=True,
            ): [DATABASE_PORT],
            yaml.safe_dump(
                [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "cnpg-system"}
                        }
                    }
                ],
                sort_keys=True,
            ): [8000, DATABASE_PORT],
        },
        [[53, 53], [443, 6443]],
    )


def check_the_gateway_policy_admits_egress_to_the_database_pods_by_label() -> None:
    """The gateway's egress gains one rule: the database pods on 5432, named by a pod selector and
    never by an ipBlock."""
    rules = [
        rule
        for rule in _policy("llm-gateway-perimeter")["spec"]["egress"]
        if rule["ports"] == [{"protocol": "TCP", "port": DATABASE_PORT}]
    ]

    assert [rule["to"] for rule in rules] == [
        [{"podSelector": {"matchLabels": {"cnpg.io/cluster": CLUSTER_NAME}}}]
    ]


def check_the_default_perimeter_leaves_the_database_to_its_own_policy() -> None:
    """llm-default-perimeter admits every pod of the namespace to every other, so the database
    pods are outside it and llm-gateway-db-perimeter alone governs them."""
    selector = _policy("llm-default-perimeter")["spec"]["podSelector"]["matchExpressions"]

    assert {
        "key": "cnpg.io/cluster",
        "operator": "NotIn",
        "values": [CLUSTER_NAME],
    } in selector


def check_argo_cd_and_deploy_stack_both_apply_the_database_and_the_operator_comes_first() -> None:
    """Argo CD's `llm` Application lists the file. deploy-stack applies it after the Helm releases
    (the Cluster needs the operator's CRD), and the operator is a release of stack `infra`, which
    every stack that holds a CloudNativePG Cluster needs, so no stack installs it twice."""
    kustomization = yaml.safe_load((LLM_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    post_helm = [str(path) for path in _POST_HELM_BY_STACK["llm"]]
    releases = {
        stack: [release["name"] for release in releases]
        for stack, releases in _HELM_RELEASES_BY_STACK.items()
    }

    assert (
        "gateway-db.yaml" in kustomization["resources"],
        "llm/gateway-db.yaml" in post_helm,
        "cloudnative-pg" in releases["infra"],
        "cloudnative-pg" in releases["chat"],
        [doc["kind"] for doc in applied_documents(DATABASE_FILE)],
    ) == (True, True, True, False, ["NetworkPolicy", "Cluster"])
