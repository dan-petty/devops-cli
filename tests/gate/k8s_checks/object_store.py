"""The SeaweedFS object store of namespace `object-store` (#4750).

The SeaweedFS operator makes every workload of the store from the one `Seaweed` CR of
`k8s/object-store/seaweed.yaml`, so these checks read the CR, the NetworkPolicies and the
PodDisruptionBudgets of the render of `k8s/object-store`, the NetworkPolicies of the render of
`k8s/monitoring`, the two Argo CD Applications and the AppProject. Each rule is a function that
returns its problems, and one check applies the rule to the committed render. The rules of the
namespace, the chart floor, the release, the closed APIs, the placement, the admin port, the
egress, the scrape path, the Secrets and the merge field also have a check that applies the rule
to a fixture that breaks it and asserts that the problem names the object, so such a rule that
stops finding its problem fails the row too.
"""

from __future__ import annotations

import copy
import functools
import re
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Final

import yaml
from kubernetes.utils.quantity import parse_quantity

from devops_cli.k8s.argocd_gate import discover_path_applications
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from tests.gate.k8s_render import kustomize
from tests.support.k8s_tree import TREE
from tests.support.paths import REPO_ROOT

K8S_DIR: Final = REPO_ROOT / "k8s"
STORE_DIR: Final = K8S_DIR / "object-store"
APPS_DIR: Final = K8S_DIR / "argocd" / "apps"
OPERATOR_APP: Final = APPS_DIR / "seaweedfs-operator.yaml"
STORE_APP: Final = APPS_DIR / "object-store.yaml"
PROJECTS: Final = APPS_DIR / "projects.yaml"
OPERATOR_VALUES: Final = STORE_DIR / "operator-values.yaml"
MONITORING_DIR: Final = K8S_DIR / "monitoring"

NAMESPACE: Final = "object-store"
PROJECT: Final = "homelab"
CR_NAME: Final = "seaweedfs"
CHART_REPO: Final = "https://seaweedfs.github.io/seaweedfs-operator"
CHART: Final = "seaweedfs-operator"
VALUES_FILE: Final = "$values/k8s/object-store/operator-values.yaml"
# Chart 0.1.47 has appVersion 1.0.44, the first operator that builds against SeaweedFS 4.53.
CHART_FLOOR: Final = (0, 1, 47)
IMAGE_REPOSITORY: Final = "chrislusf/seaweedfs"
RELEASE_FLOOR: Final = (4, 53)
# Releases 4.48 to 4.51 break minio-go multipart uploads (seaweedfs/seaweedfs#12177); 4.52 fixes it.
EXCLUDED_RELEASES: Final = ((4, 48), (4, 51))
_IMAGE: Final = re.compile(r"^chrislusf/seaweedfs:(\d+)\.(\d+)@sha256:[0-9a-f]{64}$")

COMPONENTS: Final = ("master", "volume", "filer", "s3", "admin", "worker")
REPLICAS: Final = {"master": 3, "volume": 3, "filer": 2, "s3": 2, "admin": 1, "worker": 1}
WORKER_JOB_TYPES: Final = frozenset({"vacuum", "volume_balance", "admin_script", "s3_lifecycle"})
STORAGE_CLASS: Final = "fast-nvme"
CONTROL_PLANE_LABEL: Final = "node-role.kubernetes.io/control-plane"
HOSTNAME_KEY: Final = "kubernetes.io/hostname"

ADMIN_GRPC_PORT: Final = 33646
S3_PORT: Final = 8333
# The `kubernetes` Service resolves to the node's address on 6443, and kube-router filters after
# that translation, so the API rule of the operator needs no 443 (k8s/argo-workflows).
API_SERVER_PORTS: Final = frozenset({6443})
METADATA_ADDRESS: Final = "169.254.169.254/32"
CLIENT_LABEL: Final = {"backup-client": "true"}
MONITORING: Final = "monitoring"
# The pod of the `alloy-metrics` StatefulSet of the k8s-monitoring release, which scrapes the
# ServiceMonitors of every namespace.
ALLOY_LABELS: Final = {"app.kubernetes.io/name": "alloy-metrics"}
# The namespaces that a rule may name by `kubernetes.io/metadata.name`: CoreDNS and Alloy.
NAMED_NAMESPACES: Final = frozenset({"kube-system", MONITORING})

FORBIDDEN_FIELD: Final = "fs.mergeVolumes"
MAX_CPU: Final = "1"
MAX_MEMORY: Final = "3Gi"
INTERNAL_SERVICES: Final = frozenset(
    {"seaweedfs-master", "seaweedfs-volume", "seaweedfs-filer", "seaweedfs-admin"}
)
_SECRET_OBJECT_KEYS: Final = ("credentialsSecret", "configSecret", "secretKeyRef", "secretRef")
_SECRET_NAME_KEYS: Final = ("secretName",)

_SEAWEED_LABELS: Final = {
    "app.kubernetes.io/managed-by": "seaweedfs-operator",
    "app.kubernetes.io/name": "seaweedfs",
    "app.kubernetes.io/instance": CR_NAME,
}
OPERATOR_LABELS: Final = {
    "app.kubernetes.io/name": "seaweedfs-operator",
    "app.kubernetes.io/instance": "seaweedfs-operator",
}


def component_labels(component: str) -> dict[str, str]:
    """The labels that the operator gives the pods of one component."""
    return {**_SEAWEED_LABELS, "app.kubernetes.io/component": component}


# The peers of the perimeter model: a pod of each component and the operator in the namespace, the
# Alloy pod, a pod of a client namespace, and a pod of another namespace.
_PEERS: Final = {
    **{component: (NAMESPACE, component_labels(component), {}) for component in COMPONENTS},
    "operator": (NAMESPACE, OPERATOR_LABELS, {}),
    "alloy": (MONITORING, ALLOY_LABELS, {}),
    "client": ("example-client", {"app": "client"}, CLIENT_LABEL),
    "foreign": ("example-other", {"app": "other"}, {}),
}


def _load(text: str) -> list[dict[str, Any]]:
    return [doc for doc in yaml.load_all(text, Loader=yaml.CSafeLoader) if isinstance(doc, dict)]


@functools.cache
def _store() -> tuple[dict[str, Any], ...]:
    """The objects of the render of `k8s/object-store`."""
    return tuple(_load(kustomize(STORE_DIR).stdout))


def _store_kind(kind: str) -> list[dict[str, Any]]:
    return [copy.deepcopy(doc) for doc in _store() if doc.get("kind") == kind]


def _seaweed() -> dict[str, Any]:
    (seaweed,) = _store_kind("Seaweed")
    return seaweed


def _file(path: Any) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _projects() -> list[dict[str, Any]]:
    return _load(PROJECTS.read_text(encoding="utf-8"))


@functools.cache
def _path_application_documents() -> tuple[tuple[str, dict[str, Any]], ...]:
    """Each object of the render of each Argo CD path Application, with the Application name."""
    return tuple(
        (name, doc)
        for name, path in sorted(discover_path_applications(TREE, APPS_DIR).items())
        for doc in _load(kustomize(path).stdout)
    )


def _ref(doc: Mapping[str, Any]) -> str:
    return f"{doc.get('kind')}/{doc.get('metadata', {}).get('name')}"


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def _sync_options(doc: Mapping[str, Any]) -> list[str]:
    annotation = (
        doc.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/sync-options", "")
    )
    listed = doc.get("spec", {}).get("syncPolicy", {}).get("syncOptions", [])
    return [*filter(None, str(annotation).split(",")), *listed]


def _sync_wave(doc: Mapping[str, Any]) -> int:
    annotations = doc.get("metadata", {}).get("annotations", {})
    return int(annotations.get("argocd.argoproj.io/sync-wave", "0"))


# The namespace.


def namespace_problems(namespace: Mapping[str, Any]) -> list[str]:
    """The namespace enforces Pod Security `restricted`, and Argo CD neither prunes nor deletes it."""
    labels = namespace.get("metadata", {}).get("labels", {})
    options = _sync_options(namespace)
    problems = []
    if labels.get("pod-security.kubernetes.io/enforce") != "restricted":
        problems.append(f"{_ref(namespace)}: Pod Security enforce is not restricted")
    if not {"Prune=false", "Delete=false"} <= set(options):
        problems.append(
            f"{_ref(namespace)}: sync options are {options}, not Prune=false,Delete=false"
        )
    return problems


def _namespace() -> dict[str, Any]:
    (namespace,) = [
        doc
        for doc in _load(kustomize(K8S_DIR).stdout)
        if doc.get("kind") == "Namespace" and doc["metadata"]["name"] == NAMESPACE
    ]
    return copy.deepcopy(namespace)


def check_the_object_store_namespace_is_restricted_and_kept() -> None:
    assert namespace_problems(_namespace()) == []


def check_the_namespace_rule_names_a_namespace_with_no_restricted_label() -> None:
    namespace = _namespace()
    del namespace["metadata"]["labels"]["pod-security.kubernetes.io/enforce"]

    assert any(f"Namespace/{NAMESPACE}" in p for p in namespace_problems(namespace))


# The Argo CD Applications and the project.


def operator_application_problems(app: Mapping[str, Any]) -> list[str]:
    """The operator Application installs a chart of the floor or newer before the store."""
    spec = app.get("spec", {})
    charts = [s for s in spec.get("sources", []) if s.get("chart")]
    problems = []
    if [(s.get("repoURL"), s.get("chart")) for s in charts] != [(CHART_REPO, CHART)]:
        problems.append(f"{_ref(app)}: the chart source is not {CHART} of {CHART_REPO}")
    for source in charts:
        if _version(str(source.get("targetRevision", ""))) < CHART_FLOOR:
            floor = ".".join(map(str, CHART_FLOOR))
            problems.append(
                f"{_ref(app)}: chart {source.get('targetRevision')} is under the floor {floor}"
            )
        if VALUES_FILE not in source.get("helm", {}).get("valueFiles", []):
            problems.append(f"{_ref(app)}: the chart does not read {VALUES_FILE}")
    if spec.get("project") != PROJECT:
        problems.append(f"{_ref(app)}: project is {spec.get('project')}, not {PROJECT}")
    if spec.get("destination", {}).get("namespace") != NAMESPACE:
        problems.append(f"{_ref(app)}: the destination is not namespace {NAMESPACE}")
    if _sync_wave(app) != -1:
        problems.append(f"{_ref(app)}: sync-wave is {_sync_wave(app)}, not -1")
    if "ServerSideApply=true" not in _sync_options(app):
        problems.append(f"{_ref(app)}: the CRDs need ServerSideApply=true")
    return problems


def operator_values_problems(values: Mapping[str, Any]) -> list[str]:
    """The values keep the operator of the chart's appVersion, in the store namespace, with the
    webhook certificate of cert-manager and no dashboard ConfigMap of the chart."""
    expected = {
        "image tag": "",
        "watchNamespaces": [NAMESPACE],
        "grafanaDashboard.enabled": False,
        "webhook.certManager.enabled": True,
        "crds.create": True,
    }
    found = {
        "image tag": values.get("image", {}).get("tag", ""),
        "watchNamespaces": values.get("watchNamespaces"),
        "grafanaDashboard.enabled": values.get("grafanaDashboard", {}).get("enabled"),
        "webhook.certManager.enabled": values.get("webhook", {})
        .get("certManager", {})
        .get("enabled"),
        "crds.create": values.get("crds", {}).get("create", True),
    }
    return [
        f"{OPERATOR_VALUES.name}: {key} is {found[key]!r}, not {value!r}"
        for key, value in expected.items()
        if found[key] != value
    ]


def store_application_problems(
    app: Mapping[str, Any], projects: Iterable[Mapping[str, Any]]
) -> list[str]:
    """The store Application deploys `k8s/object-store` after the operator, and the project admits
    the chart repository and the namespace."""
    spec = app.get("spec", {})
    problems = []
    if spec.get("source", {}).get("path") != "k8s/object-store":
        problems.append(f"{_ref(app)}: the source path is not k8s/object-store")
    if spec.get("project") != PROJECT:
        problems.append(f"{_ref(app)}: project is {spec.get('project')}, not {PROJECT}")
    if spec.get("destination", {}).get("namespace") != NAMESPACE:
        problems.append(f"{_ref(app)}: the destination is not namespace {NAMESPACE}")
    if _sync_wave(app) <= -1:
        problems.append(f"{_ref(app)}: sync-wave {_sync_wave(app)} does not follow the operator")
    if "SkipDryRunOnMissingResource=true" not in _sync_options(app):
        problems.append(f"{_ref(app)}: the first sync needs SkipDryRunOnMissingResource=true")
    (project,) = [p for p in projects if p.get("metadata", {}).get("name") == PROJECT]
    if CHART_REPO not in project["spec"].get("sourceRepos", []):
        problems.append(f"AppProject/{PROJECT}: sourceRepos does not list {CHART_REPO}")
    if NAMESPACE not in {d.get("namespace") for d in project["spec"].get("destinations", [])}:
        problems.append(f"AppProject/{PROJECT}: no destination names namespace {NAMESPACE}")
    return problems


def check_the_operator_application_installs_a_supported_chart_before_the_store() -> None:
    assert (
        operator_application_problems(_file(OPERATOR_APP)),
        operator_values_problems(_file(OPERATOR_VALUES)),
    ) == ([], [])


def check_the_chart_rule_names_the_floor_of_a_chart_under_it() -> None:
    app = _file(OPERATOR_APP)
    (source,) = [s for s in app["spec"]["sources"] if s.get("chart")]
    source["targetRevision"] = "0.1.46"

    assert any("0.1.47" in p for p in operator_application_problems(app))


def check_the_store_application_deploys_the_store_after_the_operator() -> None:
    assert store_application_problems(_file(STORE_APP), _projects()) == []


# The release of the store.


def _components(seaweed: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    spec = seaweed.get("spec", {})
    return {component: dict(spec.get(component) or {}) for component in COMPONENTS}


def release_problems(seaweed: Mapping[str, Any]) -> list[str]:
    """`spec.image` pins a release of the floor or newer by digest, never one of 4.48 to 4.51, and
    no component sets a version of its own."""
    image = str(seaweed.get("spec", {}).get("image", ""))
    match = _IMAGE.match(image)
    problems = []
    if match is None:
        problems.append(
            f"{_ref(seaweed)}: image {image!r} is not {IMAGE_REPOSITORY}:<tag>@<digest>"
        )
    else:
        release = (int(match[1]), int(match[2]))
        low, high = EXCLUDED_RELEASES
        if low <= release <= high:
            problems.append(
                f"{_ref(seaweed)}: release {match[1]}.{match[2]} is in the range 4.48 to 4.51, "
                "which breaks minio-go multipart uploads (seaweedfs/seaweedfs#12177)"
            )
        if release < RELEASE_FLOOR:
            problems.append(f"{_ref(seaweed)}: release {match[1]}.{match[2]} is under 4.53")
    problems += [
        f"{_ref(seaweed)}: component {component} sets version {spec['version']!r}"
        for component, spec in _components(seaweed).items()
        if spec.get("version")
    ]
    return problems


def check_the_store_runs_a_supported_release() -> None:
    assert release_problems(_seaweed()) == []


def check_the_release_rule_names_an_excluded_release() -> None:
    seaweed = _seaweed()
    seaweed["spec"]["image"] = f"{IMAGE_REPOSITORY}:4.48@sha256:{'0' * 64}"

    assert any("4.48" in p and "4.48 to 4.51" in p for p in release_problems(seaweed))


# The layout of the store.


def _anti_affinity_on_host(spec: Mapping[str, Any], component: str) -> bool:
    terms = (
        spec.get("affinity", {})
        .get("podAntiAffinity", {})
        .get("requiredDuringSchedulingIgnoredDuringExecution", [])
    )
    return any(
        term.get("topologyKey") == HOSTNAME_KEY
        and term.get("labelSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/component")
        == component
        for term in terms
    )


def layout_problems(seaweed: Mapping[str, Any]) -> list[str]:
    """The counts, the replication, the volume limits, the stores, the ports, the admin Secret, the
    worker job types and the JWT signing of the store."""
    spec = seaweed.get("spec", {})
    parts = _components(seaweed)
    master, volume, filer, s3, admin, worker = (parts[c] for c in COMPONENTS)
    growth = tomllib.loads(master.get("config", "")).get("master", {}).get("volume_growth", {})
    store = tomllib.loads(filer.get("config", ""))
    job_types = frozenset(str(worker.get("jobType", "")).split(","))
    signing = spec.get("securityConfig", {}).get("jwtSigning", {})
    found = {
        "replicas": {c: parts[c].get("replicas", 1) for c in COMPONENTS},
        "master.defaultReplication": master.get("defaultReplication"),
        "master.volumeSizeLimitMB": master.get("volumeSizeLimitMB"),
        "master volume_growth.copy_2": growth.get("copy_2"),
        "master -telemetry=false": "-telemetry=false" in master.get("extraArgs", []),
        "master.persistence.enabled": master.get("persistence", {}).get("enabled"),
        "volume.storageClassName": volume.get("storageClassName"),
        "volume.maxVolumeCounts": volume.get("maxVolumeCounts"),
        "volume.minFreeSpacePercent": volume.get("minFreeSpacePercent"),
        "volume hostname anti-affinity": _anti_affinity_on_host(volume, "volume"),
        "filer leveldb2": store.get("leveldb2", {}).get("enabled"),
        "filer.persistence.enabled": filer.get("persistence", {}).get("enabled"),
        "s3.port": s3.get("port"),
        "admin.credentialsSecret": admin.get("credentialsSecret", {}).get("name"),
        "worker.jobType": sorted(job_types),
        "jwtSigning": (signing.get("volumeWrite"), signing.get("filerWrite")),
    }
    expected = {
        "replicas": REPLICAS,
        "master.defaultReplication": "001",
        "master.volumeSizeLimitMB": 1000,
        "master volume_growth.copy_2": 2,
        "master -telemetry=false": True,
        "master.persistence.enabled": True,
        "volume.storageClassName": STORAGE_CLASS,
        "volume.maxVolumeCounts": 300,
        "volume.minFreeSpacePercent": 10,
        "volume hostname anti-affinity": True,
        "filer leveldb2": True,
        "filer.persistence.enabled": True,
        "s3.port": S3_PORT,
        "admin.credentialsSecret": "seaweedfs-admin",
        "worker.jobType": sorted(WORKER_JOB_TYPES),
        "jwtSigning": (True, True),
    }
    return [
        f"{_ref(seaweed)}: {key} is {found[key]!r}, not {value!r}"
        for key, value in expected.items()
        if found[key] != value
    ]


def check_the_store_holds_its_layout() -> None:
    assert layout_problems(_seaweed()) == []


# The optional APIs.


def feature_problems(seaweed: Mapping[str, Any]) -> list[str]:
    """The IAM API, STS, the Iceberg catalog, the Lance namespace, the filer S3, SFTP, WebDAV and
    S3 Vectors stay off, and the S3 gateway reads an identities file."""
    spec = seaweed.get("spec", {})
    parts = _components(seaweed)
    filer, s3 = parts["filer"], parts["s3"]
    s3_args = s3.get("extraArgs", [])
    problems = [
        f"{_ref(seaweed)}: {name} is on"
        for name, on in {
            "the IAM API of the S3 gateway (iam)": s3.get("iam", True) is not False,
            "the Iceberg catalog of the S3 gateway (-port.iceberg=0 absent)": (
                "-port.iceberg=0" not in s3_args
            ),
            "the Lance namespace of the S3 gateway (-port.lance=0 absent)": (
                "-port.lance=0" not in s3_args
            ),
            "the S3 of the filer": bool(filer.get("s3", {}).get("enabled")),
            "the Iceberg catalog of the filer": bool(filer.get("iceberg", {}).get("enabled")),
            "the Lance namespace of the filer": bool(filer.get("lance", {}).get("enabled")),
            "SFTP": "sftp" in spec,
            "S3 Vectors": "vector" in spec,
        }.items()
        if on
    ]
    if not s3.get("configSecret", {}).get("name"):
        problems.append(f"{_ref(seaweed)}: the S3 gateway reads no identities file (configSecret)")
    problems += [
        f"{_ref(seaweed)}: component {component} passes {arg}"
        for component, part in parts.items()
        for arg in part.get("extraArgs", [])
        if arg.startswith(("-iam.config", "-webdav", "-s3.iam.config"))
    ]
    return problems


def check_the_optional_apis_of_the_store_stay_off() -> None:
    assert feature_problems(_seaweed()) == []


def check_the_feature_rule_names_the_iceberg_catalog_of_a_filer() -> None:
    seaweed = _seaweed()
    seaweed["spec"]["filer"]["iceberg"] = {"enabled": True}

    assert any("Iceberg catalog of the filer" in p for p in feature_problems(seaweed))


# The placement.


def _claimed(component: str, part: Mapping[str, Any]) -> str | None:
    """The storage class of the claims of a component, or None when it has no claim."""
    if component == "volume":
        return str(part.get("storageClassName"))
    persistence = part.get("persistence", {})
    return str(persistence.get("storageClassName")) if persistence.get("enabled") else None


def _excludes_control_plane(affinity: Mapping[str, Any]) -> bool:
    terms = (
        affinity.get("nodeAffinity", {})
        .get("requiredDuringSchedulingIgnoredDuringExecution", {})
        .get("nodeSelectorTerms", [])
    )
    return bool(terms) and all(
        {"key": CONTROL_PLANE_LABEL, "operator": "DoesNotExist"} in term.get("matchExpressions", [])
        for term in terms
    )


def placement_problems(seaweed: Mapping[str, Any]) -> list[str]:
    """Each component with a claim keeps its pods off the control-plane node, on `fast-nvme`."""
    spec = seaweed.get("spec", {})
    problems = []
    for component, part in _components(seaweed).items():
        storage_class = _claimed(component, part)
        if storage_class is None:
            continue
        if storage_class != STORAGE_CLASS:
            problems.append(
                f"{_ref(seaweed)}: component {component} claims {storage_class}, not {STORAGE_CLASS}"
            )
        if not _excludes_control_plane(part.get("affinity") or spec.get("affinity") or {}):
            problems.append(
                f"{_ref(seaweed)}: component {component} has a claim and no required "
                f"{CONTROL_PLANE_LABEL} DoesNotExist affinity"
            )
    return problems


def check_the_store_pods_with_claims_stay_off_the_control_plane_node() -> None:
    assert placement_problems(_seaweed()) == []


def check_the_placement_rule_names_a_volume_server_with_no_exclusion() -> None:
    seaweed = _seaweed()
    del seaweed["spec"]["volume"]["affinity"]["nodeAffinity"]

    assert any(
        f"Seaweed/{CR_NAME}" in p and "component volume" in p for p in placement_problems(seaweed)
    )


# The perimeter.


def _selects(selector: Mapping[str, Any] | None, labels: Mapping[str, str]) -> bool:
    """Whether a label selector selects these labels. None selects nothing."""
    if selector is None:
        return False
    if any(labels.get(key) != value for key, value in selector.get("matchLabels", {}).items()):
        return False
    for expression in selector.get("matchExpressions", []):
        key, operator, values = expression["key"], expression["operator"], expression.get("values")
        if operator == "In" and labels.get(key) not in values:
            return False
        if operator == "NotIn" and labels.get(key) in values:
            return False
        if operator == "Exists" and key not in labels:
            return False
        if operator == "DoesNotExist" and key in labels:
            return False
    return True


def _namespace_labels(namespace: str, extra: Mapping[str, str]) -> dict[str, str]:
    return {"kubernetes.io/metadata.name": namespace, **extra}


def _peer_admitted(peer: Mapping[str, Any], name: str) -> bool:
    namespace, labels, namespace_extra = _PEERS[name]
    if "ipBlock" in peer:
        return True
    namespaces = peer.get("namespaceSelector")
    pods = peer.get("podSelector")
    in_namespace = (
        namespace == NAMESPACE
        if namespaces is None
        else _selects(namespaces, _namespace_labels(namespace, namespace_extra))
    )
    return in_namespace and (pods is None or _selects(pods, labels))


def _port_matches(rule: Mapping[str, Any], port: int) -> bool:
    """Whether a rule admits TCP `port`. An entry with no port admits every port of its protocol.
    The rule cannot resolve a named port, so a named port admits `port`: the rules fail closed."""
    ports = rule.get("ports")
    if not ports:
        return True
    return any(
        not isinstance(entry.get("port"), int)
        or entry["port"] <= port <= entry.get("endPort", entry["port"])
        for entry in ports
    )


def admitted_peers(
    policies: Iterable[Mapping[str, Any]], target: Mapping[str, str], port: int
) -> dict[str, set[str]]:
    """Each peer of the model that the policies admit to a pod with the labels `target` on TCP
    `port`, with the names of the policies that admit it. With no policy that selects the pod for
    ingress, every peer is admitted."""
    selecting = [
        policy
        for policy in policies
        if "Ingress" in policy.get("spec", {}).get("policyTypes", ["Ingress"])
        and _selects(policy.get("spec", {}).get("podSelector", {}), target)
    ]
    if not selecting:
        return {name: {"(no policy)"} for name in _PEERS}
    admitted: dict[str, set[str]] = {}
    for policy in selecting:
        for rule in policy["spec"].get("ingress", []):
            if not _port_matches(rule, port):
                continue
            peers = rule.get("from") or [{"namespaceSelector": {}}]
            for name in _PEERS:
                if any(_peer_admitted(peer, name) for peer in peers):
                    admitted.setdefault(name, set()).add(policy["metadata"]["name"])
    return admitted


def admin_port_problems(policies: Iterable[Mapping[str, Any]]) -> list[str]:
    """Only the worker pods reach the admin gRPC port, which has no authentication
    (GHSA-3qr2-qw48-cj6q). The rule reads the ingress and the egress rules: the network policy
    controller of the cluster does not apply the ingress rules of the admin pod when an egress
    rule of the source pod allows the traffic (#6707), so no egress rule of a pod that is not the
    worker may cover the port."""
    policies = list(policies)
    admin = component_labels("admin")
    admitted = admitted_peers(policies, admin, ADMIN_GRPC_PORT)
    problems = [
        f"NetworkPolicy {', '.join(sorted(names))}: admits {peer} to the admin pod on "
        f"{ADMIN_GRPC_PORT}"
        for peer, names in sorted(admitted.items())
        if peer != "worker"
    ]
    if "worker" not in admitted:
        problems.append(f"no policy admits the worker on {ADMIN_GRPC_PORT}")
    problems += [
        f"NetworkPolicy {', '.join(sorted(names))}: lets {peer} send to the admin pod on "
        f"{ADMIN_GRPC_PORT}"
        for peer, names in sorted(egress_senders(policies, admin, ADMIN_GRPC_PORT).items())
        if peer != "worker"
    ]
    worker = (NAMESPACE, component_labels("worker"))
    if egress_blockers(policies, worker, (NAMESPACE, admin), ADMIN_GRPC_PORT):
        problems.append(f"no policy lets the worker send to the admin pod on {ADMIN_GRPC_PORT}")
    return problems


def _is_dns(peer: Mapping[str, Any]) -> bool:
    return peer == {
        "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
        "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
    }


def _rule_ports(rule: Mapping[str, Any]) -> set[Any]:
    return {entry.get("port") for entry in rule.get("ports", [])}


def _egress_rule_problems(name: str, rule: Mapping[str, Any], operator_only: bool) -> list[str]:
    """The problems of one egress rule of policy `name`."""
    peers = rule.get("to")
    if not peers:
        return [f"NetworkPolicy {name}: egress to everywhere"]
    problems = []
    for peer in peers:
        if "ipBlock" in peer:
            block = peer["ipBlock"]
            api_rule = (
                operator_only
                and _rule_ports(rule) == API_SERVER_PORTS
                and METADATA_ADDRESS in block.get("except", [])
            )
            if not api_rule:
                problems.append(f"NetworkPolicy {name}: egress to {block.get('cidr')}")
        elif "namespaceSelector" in peer and not _is_dns(peer):
            problems.append(f"NetworkPolicy {name}: egress to another namespace")
    return problems


def egress_problems(policies: Iterable[Mapping[str, Any]]) -> list[str]:
    """The pods reach only CoreDNS and the pods of the namespace; the operator pod also reaches
    the Kubernetes API on 6443, with the metadata address excluded."""
    problems = []
    policies = list(policies)
    perimeter = [
        p
        for p in policies
        if p.get("spec", {}).get("podSelector") == {}
        and {"Ingress", "Egress"} <= set(p["spec"].get("policyTypes", []))
    ]
    if not perimeter:
        problems.append(f"no NetworkPolicy of {NAMESPACE} selects every pod for ingress and egress")
    for policy in policies:
        spec = policy.get("spec", {})
        selector = spec.get("podSelector", {})
        operator_only = _selects(selector, OPERATOR_LABELS) and not any(
            _selects(selector, component_labels(c)) for c in COMPONENTS
        )
        for rule in spec.get("egress", []):
            problems += _egress_rule_problems(policy["metadata"]["name"], rule, operator_only)
    return problems


def client_problems(policies: Iterable[Mapping[str, Any]]) -> list[str]:
    """A namespace with the label `backup-client: "true"` reaches the S3 port, a namespace with no
    label does not, and no rule names a client namespace by its name."""
    policies = list(policies)
    admitted = admitted_peers(policies, component_labels("s3"), S3_PORT)
    problems = []
    if "client" not in admitted:
        problems.append(
            f"no policy admits a namespace with {CLIENT_LABEL} to the S3 port {S3_PORT}"
        )
    if "foreign" in admitted:
        problems.append(f"NetworkPolicy {sorted(admitted['foreign'])}: admits any namespace to S3")
    named = {
        selector["matchLabels"]["kubernetes.io/metadata.name"]
        for policy in policies
        for rules in (policy["spec"].get("ingress", []), policy["spec"].get("egress", []))
        for rule in rules
        for peer in rule.get("from", rule.get("to", [])) or []
        if (selector := peer.get("namespaceSelector"))
        and "kubernetes.io/metadata.name" in selector.get("matchLabels", {})
    }
    problems += [f"a rule names namespace {name} by its name" for name in named - NAMED_NAMESPACES]
    return problems


def check_only_the_worker_reaches_the_admin_grpc_port() -> None:
    assert admin_port_problems(_store_kind("NetworkPolicy")) == []


def _filer_admitted_on(ports: list[dict[str, Any]]) -> list[str]:
    """The problems of the admin port rule for the committed policies and a fixture policy that
    admits the filer pods to every pod of the namespace on `ports`."""
    fixture = {
        "kind": "NetworkPolicy",
        "metadata": {"name": "fixture-perimeter", "namespace": NAMESPACE},
        "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress"],
            "ingress": [
                {
                    "from": [{"podSelector": {"matchLabels": component_labels("filer")}}],
                    "ports": ports,
                }
            ],
        },
    }
    return [
        p
        for p in admin_port_problems([*_store_kind("NetworkPolicy"), fixture])
        if "fixture-perimeter" in p and str(ADMIN_GRPC_PORT) in p
    ]


def check_the_admin_port_rule_names_a_policy_that_admits_a_filer() -> None:
    assert _filer_admitted_on([{"protocol": "TCP", "port": ADMIN_GRPC_PORT}])


def check_the_admin_port_rule_names_a_policy_that_admits_every_tcp_port() -> None:
    # A ports entry with no port admits every port of its protocol.
    assert _filer_admitted_on([{"protocol": "TCP"}])


def check_the_admin_port_rule_names_a_policy_that_admits_a_named_port() -> None:
    # The rule cannot resolve a named port, so it counts the port as the admin port.
    assert _filer_admitted_on([{"protocol": "TCP", "port": "grpc"}])


def _admin_port_problems_of(policies: list[dict[str, Any]], name: str) -> list[str]:
    """The problems of the admin port rule for `policies` that name the policy or the text
    `name` and the admin gRPC port."""
    return [p for p in admin_port_problems(policies) if name in p and str(ADMIN_GRPC_PORT) in p]


def check_the_admin_port_rule_names_a_perimeter_whose_namespace_egress_has_no_ports() -> None:
    # The controller of the cluster does not apply the ingress rules of the admin pod when an
    # egress rule of the source pod allows the traffic, so a rule with no ports opens 33646.
    policies = _store_kind("NetworkPolicy")
    (perimeter,) = [p for p in policies if p["metadata"]["name"] == "object-store-perimeter"]
    (namespace_rule,) = [
        rule for rule in perimeter["spec"]["egress"] if rule.get("to") == [{"podSelector": {}}]
    ]
    namespace_rule.pop("ports", None)

    assert _admin_port_problems_of(policies, "object-store-perimeter")


def check_the_admin_port_rule_names_a_policy_that_lets_a_filer_send_to_the_admin_port() -> None:
    fixture = {
        "kind": "NetworkPolicy",
        "metadata": {"name": "fixture-filer-egress", "namespace": NAMESPACE},
        "spec": {
            "podSelector": {"matchLabels": component_labels("filer")},
            "policyTypes": ["Egress"],
            "egress": [
                {
                    "to": [{"podSelector": {"matchLabels": component_labels("admin")}}],
                    "ports": [{"protocol": "TCP", "port": ADMIN_GRPC_PORT}],
                }
            ],
        },
    }

    assert _admin_port_problems_of([*_store_kind("NetworkPolicy"), fixture], "fixture-filer-egress")


def check_the_admin_port_rule_names_a_worker_with_no_egress_to_the_admin_port() -> None:
    policies = [
        p for p in _store_kind("NetworkPolicy") if p["metadata"]["name"] != "object-store-worker"
    ]

    assert _admin_port_problems_of(policies, "lets the worker send")


def check_the_store_has_no_internet_egress() -> None:
    assert egress_problems(_store_kind("NetworkPolicy")) == []


def check_the_egress_rule_names_a_perimeter_with_internet_egress() -> None:
    policies = _store_kind("NetworkPolicy")
    (perimeter,) = [p for p in policies if p["metadata"]["name"] == "object-store-perimeter"]
    perimeter["spec"]["egress"].append({"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]})

    assert any("object-store-perimeter" in p for p in egress_problems(policies))


def check_clients_reach_the_s3_port_by_a_namespace_label() -> None:
    assert client_problems(_store_kind("NetworkPolicy")) == []


def _monitoring_policies() -> list[dict[str, Any]]:
    """The NetworkPolicies of the render of `k8s/monitoring`."""
    return [
        doc for doc in _load(kustomize(MONITORING_DIR).stdout) if doc.get("kind") == "NetworkPolicy"
    ]


def _egress_peer_reaches(
    peer: Mapping[str, Any], source_namespace: str, namespace: str, labels: Mapping[str, str]
) -> bool:
    if "ipBlock" in peer:
        return True
    namespaces = peer.get("namespaceSelector")
    pods = peer.get("podSelector")
    in_namespace = (
        namespace == source_namespace
        if namespaces is None
        else _selects(namespaces, _namespace_labels(namespace, {}))
    )
    return in_namespace and (pods is None or _selects(pods, labels))


def _egress_selecting(
    policies: Iterable[Mapping[str, Any]], namespace: str, labels: Mapping[str, str]
) -> list[Mapping[str, Any]]:
    """The policies of `namespace` that select the pod with the labels `labels` for egress."""
    return [
        policy
        for policy in policies
        if policy.get("metadata", {}).get("namespace") == namespace
        and "Egress"
        in policy.get("spec", {}).get(
            "policyTypes", ["Egress"] if "egress" in policy.get("spec", {}) else []
        )
        and _selects(policy["spec"].get("podSelector", {}), labels)
    ]


def _sends(
    policy: Mapping[str, Any],
    source_namespace: str,
    target: tuple[str, Mapping[str, str]],
    port: int,
) -> bool:
    """Whether an egress rule of `policy` lets a pod of `source_namespace` send to the pod
    `target` (namespace, labels) on TCP `port`. A rule with no `to` sends everywhere."""
    return any(
        _port_matches(rule, port)
        and any(
            _egress_peer_reaches(peer, source_namespace, *target)
            for peer in rule.get("to") or [{"namespaceSelector": {}}]
        )
        for rule in policy["spec"].get("egress", [])
    )


def egress_blockers(
    policies: Iterable[Mapping[str, Any]],
    source: tuple[str, Mapping[str, str]],
    target: tuple[str, Mapping[str, str]],
    port: int,
) -> list[str]:
    """The names of the policies that select the pod `source` (namespace, labels) for egress when
    no egress rule of them lets it send to the pod `target` on TCP `port`; empty when the pod may
    send. With no policy that selects the pod for egress, the pod sends everywhere."""
    source_namespace, source_labels = source
    selecting = _egress_selecting(policies, source_namespace, source_labels)
    sends = any(_sends(policy, source_namespace, target, port) for policy in selecting)
    return [] if not selecting or sends else sorted(p["metadata"]["name"] for p in selecting)


def egress_senders(
    policies: Iterable[Mapping[str, Any]], target: Mapping[str, str], port: int
) -> dict[str, set[str]]:
    """Each peer of the model in namespace `object-store` that an egress rule lets send to a pod of
    the namespace with the labels `target` on TCP `port`, with the names of the policies of those
    rules. A pod that no policy selects for egress is not a sender: the ingress rules of the target
    hold for it."""
    policies = list(policies)
    senders: dict[str, set[str]] = {}
    for name, (namespace, labels, _) in _PEERS.items():
        if namespace != NAMESPACE:
            continue
        for policy in _egress_selecting(policies, NAMESPACE, labels):
            if _sends(policy, NAMESPACE, (NAMESPACE, target), port):
                senders.setdefault(name, set()).add(policy["metadata"]["name"])
    return senders


def scrape_problems(
    monitoring_policies: Iterable[Mapping[str, Any]],
    store_policies: Iterable[Mapping[str, Any]],
    seaweed: Mapping[str, Any],
) -> list[str]:
    """Alloy reaches the metrics port of each component: the perimeter of `monitoring` lets the
    Alloy pod send to it, and the perimeter of the store admits the Alloy pod."""
    monitoring_policies, store_policies = list(monitoring_policies), list(store_policies)
    problems = []
    for component, part in _components(seaweed).items():
        port = part.get("metricsPort")
        if not isinstance(port, int):
            continue
        labels = component_labels(component)
        blockers = egress_blockers(
            monitoring_policies, (MONITORING, ALLOY_LABELS), (NAMESPACE, labels), port
        )
        if blockers:
            problems.append(
                f"NetworkPolicy {', '.join(blockers)}: Alloy cannot send to component "
                f"{component} on {port}"
            )
        if "alloy" not in admitted_peers(store_policies, labels, port):
            problems.append(f"no policy admits Alloy to component {component} on {port}")
    return problems


def check_alloy_reaches_the_metrics_port_of_each_component() -> None:
    assert scrape_problems(_monitoring_policies(), _store_kind("NetworkPolicy"), _seaweed()) == []


def check_the_scrape_rule_names_a_monitoring_perimeter_with_no_egress_to_the_store() -> None:
    policies = _monitoring_policies()
    for policy in policies:
        policy["spec"]["egress"] = [
            rule
            for rule in policy["spec"].get("egress", [])
            if not any(
                peer.get("namespaceSelector", {}).get("matchLabels", {})
                == {"kubernetes.io/metadata.name": NAMESPACE}
                for peer in rule.get("to", [])
            )
        ]

    assert any(
        "monitoring-default-perimeter" in p
        for p in scrape_problems(policies, _store_kind("NetworkPolicy"), _seaweed())
    )


# The workloads.


def _budgeted(budgets: Iterable[Mapping[str, Any]], labels: Mapping[str, str]) -> list[str]:
    return [
        budget["metadata"]["name"]
        for budget in budgets
        if _selects(budget.get("spec", {}).get("selector"), labels)
        and budget["spec"].get("maxUnavailable", 0) not in (0, "0%")
    ]


def workload_problems(
    seaweed: Mapping[str, Any], budgets: Iterable[Mapping[str, Any]]
) -> list[str]:
    """Each component runs restricted, exports metrics that a ServiceMonitor of the operator
    scrapes, and has a PodDisruptionBudget of its own; the operator has one too."""
    budgets = list(budgets)
    problems = []
    for component, part in _components(seaweed).items():
        pod = part.get("podSecurityContext", {})
        container = part.get("containerSecurityContext", {})
        found = (
            pod.get("runAsNonRoot"),
            int(pod.get("runAsUser", 0)) > 0,
            pod.get("seccompProfile", {}).get("type"),
            container.get("allowPrivilegeEscalation"),
            container.get("capabilities", {}).get("drop"),
            isinstance(part.get("metricsPort"), int),
        )
        if found != (True, True, "RuntimeDefault", False, ["ALL"], True):
            problems.append(
                f"{_ref(seaweed)}: component {component} has security and metrics {found}"
            )
        if len(_budgeted(budgets, component_labels(component))) != 1:
            problems.append(f"component {component} has no PodDisruptionBudget of its own")
    if len(_budgeted(budgets, OPERATOR_LABELS)) != 1:
        problems.append("the operator has no PodDisruptionBudget of its own")
    if seaweed.get("spec", {}).get("serviceMonitor", {}).get("enabled") is not True:
        problems.append(f"{_ref(seaweed)}: serviceMonitor.enabled is not true")
    return problems


def check_each_store_workload_is_restricted_budgeted_and_scraped() -> None:
    assert workload_problems(_seaweed(), _store_kind("PodDisruptionBudget")) == []


# The Secrets.


def _secret_names(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _SECRET_OBJECT_KEYS and isinstance(value, dict) and value.get("name"):
                yield str(value["name"])
            elif key in _SECRET_NAME_KEYS and isinstance(value, str):
                yield value
            else:
                yield from _secret_names(value)
    elif isinstance(node, list):
        for item in node:
            yield from _secret_names(item)


def secret_reference_problems(
    documents: Iterable[Mapping[str, Any]], refs: Iterable[str]
) -> list[str]:
    """Each Secret that an object references has a row in `CLUSTER_SECRETS`."""
    known = set(refs)
    return [
        f"{_ref(doc)}: Secret {namespace}/{name} has no row in CLUSTER_SECRETS"
        for doc in documents
        for namespace in [doc.get("metadata", {}).get("namespace", NAMESPACE)]
        for name in _secret_names(doc.get("spec", {}))
        if f"{namespace}/{name}" not in known
    ]


def check_every_secret_that_the_store_reads_has_a_cluster_secret_row() -> None:
    refs = [secret.ref for secret in CLUSTER_SECRETS]

    assert secret_reference_problems(_store(), refs) == []


def check_the_secret_rule_names_a_reference_with_no_row() -> None:
    seaweed = _seaweed()
    seaweed["spec"]["admin"]["credentialsSecret"]["name"] = "seaweedfs-missing"
    refs = [secret.ref for secret in CLUSTER_SECRETS]

    assert any(
        f"{NAMESPACE}/seaweedfs-missing" in p for p in secret_reference_problems([seaweed], refs)
    )


# The forbidden field.


def _texts(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _texts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _texts(item)
    elif isinstance(node, str):
        yield node


def forbidden_field_problems(documents: Iterable[Mapping[str, Any]]) -> list[str]:
    """No object holds `fs.mergeVolumes`, which can lose a completed object
    (seaweedfs/seaweedfs#12521)."""
    return [
        f"{_ref(doc)}: holds {FORBIDDEN_FIELD}"
        for doc in documents
        if any(FORBIDDEN_FIELD in text for text in _texts(doc))
    ]


def check_no_manifest_holds_the_merge_volumes_command() -> None:
    documents = [doc for _, doc in _path_application_documents()]

    assert forbidden_field_problems([*documents, _file(OPERATOR_VALUES)]) == []


def check_the_field_rule_names_an_admin_script_with_the_command() -> None:
    fixture = {
        "apiVersion": "seaweed.seaweedfs.com/v1",
        "kind": "AdminScript",
        "metadata": {"name": "fixture-merge", "namespace": NAMESPACE},
        "spec": {"script": f"lock\n{FORBIDDEN_FIELD} -apply\nunlock"},
    }

    assert forbidden_field_problems([fixture]) == [
        f"AdminScript/fixture-merge: holds {FORBIDDEN_FIELD}"
    ]


# The Ingress hosts.


def _backends(doc: Mapping[str, Any]) -> set[str]:
    spec = doc.get("spec", {})
    if doc.get("kind") == "Ingress":
        paths = [p for r in spec.get("rules", []) for p in r.get("http", {}).get("paths", [])]
        backends = [p.get("backend", {}) for p in paths] + [spec.get("defaultBackend", {})]
        return {b.get("service", {}).get("name", "") for b in backends} - {""}
    if doc.get("kind") == "IngressRoute":
        return {s.get("name", "") for r in spec.get("routes", []) for s in r.get("services", [])}
    return set()


def ingress_problems(
    seaweed: Mapping[str, Any], documents: Iterable[Mapping[str, Any]]
) -> list[str]:
    """No Ingress serves the master, volume, filer or admin port, and the CR turns on none."""
    problems = [
        f"{_ref(seaweed)}: component {component} turns on an Ingress"
        for component, part in _components(seaweed).items()
        if any(part.get(key, {}).get("enabled") for key in ("ingress", "s3Ingress", "grpcIngress"))
    ]
    if seaweed.get("spec", {}).get("hostSuffix"):
        problems.append(f"{_ref(seaweed)}: hostSuffix publishes every component")
    problems += [
        f"{_ref(doc)}: routes to {service}"
        for doc in documents
        for service in sorted(_backends(doc) & INTERNAL_SERVICES)
    ]
    return problems


def check_no_ingress_host_serves_an_internal_port_of_the_store() -> None:
    documents = [doc for _, doc in _path_application_documents()]

    assert ingress_problems(_seaweed(), documents) == []


# The requests.


def request_sums(seaweed: Mapping[str, Any], operator_values: Mapping[str, Any]) -> tuple[Any, Any]:
    """The CPU and the memory that the components, times their replicas, and the operator ask."""
    parts = [
        (part.get("requests", {}), part.get("replicas", 1))
        for part in _components(seaweed).values()
    ]
    parts.append((operator_values.get("resources", {}).get("requests", {}), 1))
    cpu = sum(parse_quantity(r.get("cpu", "0")) * n for r, n in parts)
    memory = sum(parse_quantity(r.get("memory", "0")) * n for r, n in parts)
    return cpu, memory


def check_the_store_requests_at_most_one_cpu_and_three_gibibytes() -> None:
    cpu, memory = request_sums(_seaweed(), _file(OPERATOR_VALUES))

    assert (cpu <= parse_quantity(MAX_CPU), memory <= parse_quantity(MAX_MEMORY)) == (True, True), (
        f"the store requests {cpu} CPU and {memory} bytes, over {MAX_CPU} CPU or {MAX_MEMORY}"
    )
