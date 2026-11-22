"""The buckets and the lifecycle rules of the object store (#4756).

The SeaweedFS operator makes each bucket, quota, anonymous read and lifecycle rule of the store
from the CRs of `k8s/object-store/buckets.yaml`, so no reconcile code runs. Each bucket lives in
the namespace of the workload that writes it, and names the `Seaweed` CR of `object-store` through
a grant there. These checks read the render of `k8s/object-store`, the values of the operator chart
and the AppProject. Each rule is a function that returns its problems. One check applies the rule
to the committed render, and one applies it to a fixture that breaks it and asserts that the
problem names the object, so a rule that stops finding its problem fails the row too.
"""

from __future__ import annotations

import copy
import functools
from collections.abc import Iterable, Mapping
from typing import Any, Final

import yaml
from kubernetes.utils.quantity import parse_quantity

from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

STORE_DIR: Final = REPO_ROOT / "k8s" / "object-store"
OPERATOR_VALUES: Final = STORE_DIR / "operator-values.yaml"
PROJECTS: Final = REPO_ROOT / "k8s" / "argocd" / "apps" / "projects.yaml"

NAMESPACE: Final = "object-store"
CR_NAME: Final = "seaweedfs"
PROJECT: Final = "homelab"
GROUP: Final = "seaweed.seaweedfs.com"
GRANT_NAME: Final = "object-store-buckets"

# The platform buckets of the devops-cli workloads: the namespace of the workload that writes each
# one, and its quota. `local-path` does not enforce the size of a claim, so the quotas are the
# limits. The tenant buckets `backups-*` come from the tenant chart of dan-petty/infra.
PLATFORM_BUCKETS: Final = {
    "reports": ("devops", "20Gi"),
    "reports-private": ("devops", "20Gi"),
    "cache": ("devops", "10Gi"),
    "argo-artifacts": ("argo-workflows", "10Gi"),
}
ANONYMOUS_READ: Final = frozenset({"reports", "reports-private"})
ANONYMOUS_USER: Final = "anonymous"
BACKUP_PREFIX: Final = "backups-"
# (bucket, prefix) -> days to the expiration of an object.
EXPIRATIONS: Final = {
    ("reports-private", "studies/"): 90,
    ("cache", ""): 7,
    ("argo-artifacts", ""): 7,
}
ABORT_MULTIPART_DAYS: Final = 1
# The kinds of the operator that it reconciles in their own namespace.
WATCHED_KINDS: Final = frozenset({"Bucket", "BucketLifecyclePolicy"})
# The kinds the render may hold: the operator CRs, the perimeter and the budgets. No Job, CronJob,
# workload or script reconciles the store.
STORE_KINDS: Final = frozenset(
    {
        "Seaweed",
        "Bucket",
        "BucketLifecyclePolicy",
        "ResourceReferenceGrant",
        "NetworkPolicy",
        "PodDisruptionBudget",
    }
)


def _load(text: str) -> list[dict[str, Any]]:
    return [doc for doc in yaml.load_all(text, Loader=yaml.CSafeLoader) if isinstance(doc, dict)]


@functools.cache
def _render() -> tuple[dict[str, Any], ...]:
    """The objects of the render of `k8s/object-store`."""
    return tuple(_load(kustomize(STORE_DIR).stdout))


def _kind(kind: str, documents: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    source = _render() if documents is None else documents
    return [copy.deepcopy(dict(doc)) for doc in source if doc.get("kind") == kind]


def _values() -> dict[str, Any]:
    data = yaml.safe_load(OPERATOR_VALUES.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _projects() -> list[dict[str, Any]]:
    return _load(PROJECTS.read_text(encoding="utf-8"))


def _name(doc: Mapping[str, Any]) -> str:
    return str(doc.get("metadata", {}).get("name", ""))


def _namespace(doc: Mapping[str, Any]) -> str:
    return str(doc.get("metadata", {}).get("namespace", ""))


def _ref(doc: Mapping[str, Any]) -> str:
    return f"{doc.get('kind')}/{_name(doc)}"


def _bucket_name(bucket: Mapping[str, Any]) -> str:
    """The bucket on the store: `spec.name`, else the name of the CR."""
    return str(bucket.get("spec", {}).get("name") or _name(bucket))


def _names_the_store(bucket: Mapping[str, Any]) -> bool:
    spec = bucket.get("spec", {})
    ref = spec.get("clusterRef") or {}
    return (
        "seaweedRef" not in spec
        and ref.get("name") == CR_NAME
        and (ref.get("namespace") or _namespace(bucket)) == NAMESPACE
    )


# The buckets.


def bucket_problems(buckets: Iterable[Mapping[str, Any]]) -> list[str]:
    """Each platform bucket is there in the namespace of its writer with its quota, and each bucket
    of the store names the store in `clusterRef`, keeps an enforced quota and keeps its data when
    its CR goes."""
    problems: list[str] = []
    found = {_bucket_name(bucket): bucket for bucket in buckets}
    for name, (namespace, size) in PLATFORM_BUCKETS.items():
        bucket = found.get(name)
        if bucket is None:
            problems.append(f"Bucket/{name}: no Bucket in the render")
            continue
        quota = bucket.get("spec", {}).get("quota", {}).get("size")
        if quota is None or parse_quantity(quota) != parse_quantity(size):
            problems.append(f"Bucket/{name}: quota is {quota!r}, not {size}")
        if _namespace(bucket) != namespace:
            problems.append(f"Bucket/{name}: namespace is {_namespace(bucket)!r}, not {namespace}")
    for bucket in found.values():
        spec = bucket.get("spec", {})
        quota = spec.get("quota", {})
        if not _names_the_store(bucket):
            problems.append(f"{_ref(bucket)}: clusterRef does not name {NAMESPACE}/{CR_NAME}")
        if "size" not in quota or quota.get("enforce") is False:
            problems.append(f"{_ref(bucket)}: no enforced quota")
        if spec.get("reclaimPolicy") != "Retain":
            problems.append(f"{_ref(bucket)}: reclaimPolicy is not Retain")
    return problems


def check_the_store_declares_the_platform_buckets_with_their_quotas() -> None:
    assert bucket_problems(_kind("Bucket")) == []


def check_the_bucket_rule_names_a_bucket_that_deletes_its_data() -> None:
    buckets = _kind("Bucket")
    for bucket in buckets:
        if _bucket_name(bucket) == "cache":
            bucket["spec"]["reclaimPolicy"] = "Delete"

    assert any(p.startswith("Bucket/cache:") for p in bucket_problems(buckets))


def check_the_bucket_rule_names_a_bucket_in_the_store_namespace() -> None:
    buckets = _kind("Bucket")
    for bucket in buckets:
        if _bucket_name(bucket) == "cache":
            bucket["metadata"]["namespace"] = NAMESPACE

    assert any(p.startswith("Bucket/cache: namespace") for p in bucket_problems(buckets))


# The grant of the buckets.


def _admits(grant: Mapping[str, Any], namespace: str) -> bool:
    """The grant admits a `Bucket` of the namespace to the `Seaweed` CR of the store."""
    spec = grant.get("spec", {})
    return any(
        source.get("group") == GROUP
        and source.get("kind") == "Bucket"
        and source.get("namespace") == namespace
        for source in spec.get("from", [])
    ) and any(
        target.get("group") == GROUP
        and target.get("kind") == "Seaweed"
        and target.get("name") == CR_NAME
        for target in spec.get("to", [])
    )


def _grant_problems(grant: Mapping[str, Any], namespaces: set[str]) -> list[str]:
    """One grant: in the store namespace, from buckets of the bucket namespaces by name, to the
    `Seaweed` CR of the store by name."""
    ref = f"{_ref(grant)} of {_namespace(grant)}"
    spec = grant.get("spec", {})
    problems = [f"{ref}: not in namespace {NAMESPACE}"] if _namespace(grant) != NAMESPACE else []
    problems.extend(
        f"{ref}: admits {source.get('kind')} from {source.get('namespace') or 'a selector'}"
        for source in spec.get("from", [])
        if source.get("group") != GROUP
        or source.get("kind") != "Bucket"
        or "namespaceSelector" in source
        or source.get("namespace") not in namespaces
    )
    problems.extend(
        f"{ref}: admits {target.get('kind')} {target.get('name') or 'of every name'}"
        for target in spec.get("to", [])
        if target.get("group") != GROUP
        or target.get("kind") != "Seaweed"
        or target.get("name") != CR_NAME
    )
    return problems


def grant_problems(documents: Iterable[Mapping[str, Any]]) -> list[str]:
    """A grant in the store namespace admits each bucket of another namespace to the store, and
    each grant admits only such buckets, to the store only."""
    docs = list(documents)
    grants = _kind("ResourceReferenceGrant", docs)
    outside = [bucket for bucket in _kind("Bucket", docs) if _namespace(bucket) != NAMESPACE]
    namespaces = {_namespace(bucket) for bucket in outside}
    problems = [
        f"{_ref(bucket)}: no grant in {NAMESPACE} admits the Buckets of {_namespace(bucket)}"
        for bucket in outside
        if not any(
            _namespace(grant) == NAMESPACE and _admits(grant, _namespace(bucket))
            for grant in grants
        )
    ]
    for grant in grants:
        problems.extend(_grant_problems(grant, namespaces))
    return problems


def check_a_grant_admits_the_buckets_to_the_store() -> None:
    assert grant_problems(_render()) == []


def check_the_grant_rule_names_a_bucket_namespace_with_no_grant() -> None:
    documents = [copy.deepcopy(doc) for doc in _render()]
    for doc in documents:
        if doc.get("kind") == "Bucket" and _bucket_name(doc) == "argo-artifacts":
            doc["metadata"]["namespace"] = "llm"

    assert any(p.startswith("Bucket/argo-artifacts: no grant") for p in grant_problems(documents))


def check_the_grant_rule_names_a_grant_to_every_seaweed_cr() -> None:
    documents = [copy.deepcopy(doc) for doc in _render()]
    for doc in documents:
        if doc.get("kind") == "ResourceReferenceGrant":
            for target in doc["spec"]["to"]:
                target.pop("name", None)

    assert any(
        p.startswith(f"ResourceReferenceGrant/{GRANT_NAME} of {NAMESPACE}: admits Seaweed")
        for p in grant_problems(documents)
    )


# The anonymous read.


def anonymous_problems(buckets: Iterable[Mapping[str, Any]]) -> list[str]:
    """Only the report buckets have anonymous read, and no bucket grants the anonymous user an
    action of its own."""
    problems: list[str] = []
    for bucket in buckets:
        spec = bucket.get("spec", {})
        name = _bucket_name(bucket)
        if bool(spec.get("anonymousRead")) != (name in ANONYMOUS_READ):
            problems.append(f"{_ref(bucket)}: anonymousRead is {bool(spec.get('anonymousRead'))}")
        if any(entry.get("user") == ANONYMOUS_USER for entry in spec.get("access", [])):
            problems.append(f"{_ref(bucket)}: access names the user {ANONYMOUS_USER}")
    return problems


def check_only_the_report_buckets_have_anonymous_read() -> None:
    assert anonymous_problems(_kind("Bucket")) == []


def check_the_anonymous_rule_names_a_backup_bucket_with_anonymous_read() -> None:
    (bucket, *_) = [b for b in _kind("Bucket") if _bucket_name(b) == "cache"]
    bucket["metadata"]["name"] = bucket["spec"]["name"] = "backups-example"
    bucket["spec"]["anonymousRead"] = True

    assert any("Bucket/backups-example" in p for p in anonymous_problems([bucket]))


# The lifecycle rules.


def _enabled(rule: Mapping[str, Any]) -> bool:
    return bool(rule.get("status", "Enabled") == "Enabled")


def _expires(rule: Mapping[str, Any]) -> bool:
    return "expiration" in rule or "noncurrentVersionExpiration" in rule


def _rule_problems(name: str, rules: list[Mapping[str, Any]]) -> list[str]:
    """The rules of one bucket: the abort rule, the expirations of the design, and no expiration
    of a backup."""
    problems: list[str] = []
    if not any(
        _enabled(rule)
        and not rule.get("prefix")
        and rule.get("abortIncompleteMultipartUpload", {}).get("daysAfterInitiation")
        == ABORT_MULTIPART_DAYS
        for rule in rules
    ):
        problems.append(f"Bucket/{name}: no rule aborts an incomplete upload after 1 day")
    if name.startswith(BACKUP_PREFIX) and any(_expires(rule) for rule in rules):
        problems.append(f"Bucket/{name}: a backup bucket has an expiration rule")
    for (bucket, prefix), days in EXPIRATIONS.items():
        if bucket == name and not any(
            _enabled(rule)
            and rule.get("prefix", "") == prefix
            and rule.get("expiration", {}).get("days") == days
            for rule in rules
        ):
            problems.append(f"Bucket/{name}: prefix {prefix!r} does not expire after {days} days")
    return problems


def lifecycle_problems(
    buckets: Iterable[Mapping[str, Any]], policies: Iterable[Mapping[str, Any]]
) -> list[str]:
    """Each bucket has one lifecycle policy in its namespace with the rules of the design."""
    problems: list[str] = []
    bucket_list = list(buckets)
    by_bucket: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for policy in policies:
        target = (_namespace(policy), policy.get("spec", {}).get("bucketRef", {}).get("name", ""))
        by_bucket.setdefault(target, []).append(policy)
    known = {(_namespace(bucket), _name(bucket)) for bucket in bucket_list}
    problems.extend(
        f"{_ref(policy)}: bucketRef names no Bucket of its namespace"
        for target, listed in by_bucket.items()
        if target not in known
        for policy in listed
    )
    for bucket in bucket_list:
        listed = by_bucket.get((_namespace(bucket), _name(bucket)), [])
        if len(listed) != 1:
            problems.append(f"{_ref(bucket)}: {len(listed)} lifecycle policies, not 1")
            continue
        problems.extend(_rule_problems(_bucket_name(bucket), listed[0]["spec"].get("rules", [])))
    return problems


def check_each_bucket_has_its_lifecycle_rules_in_git() -> None:
    assert lifecycle_problems(_kind("Bucket"), _kind("BucketLifecyclePolicy")) == []


def check_the_lifecycle_rule_names_a_backup_bucket_with_an_expiration_rule() -> None:
    (bucket,) = [b for b in _kind("Bucket") if _bucket_name(b) == "cache"]
    (policy,) = [
        p
        for p in _kind("BucketLifecyclePolicy")
        if p["spec"]["bucketRef"]["name"] == _name(bucket) and _namespace(p) == _namespace(bucket)
    ]
    bucket["metadata"]["name"] = bucket["spec"]["name"] = "backups-example"
    policy["spec"]["bucketRef"]["name"] = "backups-example"

    assert any(
        "Bucket/backups-example: a backup bucket" in p
        for p in lifecycle_problems([bucket], [policy])
    )


def check_the_lifecycle_rule_names_a_bucket_with_no_policy() -> None:
    policies = [
        p for p in _kind("BucketLifecyclePolicy") if p["spec"]["bucketRef"]["name"] != "reports"
    ]

    assert any(
        p.startswith("Bucket/reports: 0 lifecycle")
        for p in lifecycle_problems(_kind("Bucket"), policies)
    )


# The watch scope of the operator.


def watch_problems(values: Mapping[str, Any], documents: Iterable[Mapping[str, Any]]) -> list[str]:
    """The operator watches the store and the namespace of each bucket and lifecycle policy, each
    once: it sees a CR only through the cache of these namespaces, and an empty list gives it a
    ClusterRole over every namespace."""
    found = list(values.get("watchNamespaces") or [])
    expected = {NAMESPACE} | {
        _namespace(doc) for doc in documents if doc.get("kind") in WATCHED_KINDS
    }
    problems = [
        f"watchNamespaces lacks namespace {namespace}"
        for namespace in sorted(expected - set(found))
    ]
    problems.extend(
        f"watchNamespaces names namespace {namespace}, which no CR of the store needs"
        for namespace in sorted(set(found) - expected)
    )
    if len(found) != len(set(found)):
        problems.append(f"watchNamespaces repeats a namespace: {found}")
    return problems


def check_the_operator_watches_the_store_and_each_bucket_namespace() -> None:
    assert watch_problems(_values(), _render()) == []


def check_the_watch_rule_names_a_bucket_namespace_the_operator_does_not_watch() -> None:
    values = {**_values(), "watchNamespaces": [NAMESPACE]}

    assert "watchNamespaces lacks namespace devops" in watch_problems(values, _render())


# The kinds of the render.


def kind_problems(
    documents: Iterable[Mapping[str, Any]], projects: Iterable[Mapping[str, Any]]
) -> list[str]:
    """The render holds only the operator CRs, the perimeter and the budgets, each in a namespace
    that the project admits."""
    (project,) = [p for p in projects if _name(p) == PROJECT]
    destinations = {d.get("namespace") for d in project.get("spec", {}).get("destinations", [])}
    problems: list[str] = []
    for doc in documents:
        if doc.get("kind") not in STORE_KINDS:
            problems.append(f"{_ref(doc)}: kind {doc.get('kind')} reconciles outside the operator")
        if _namespace(doc) not in destinations:
            problems.append(
                f"{_ref(doc)}: AppProject/{PROJECT} has no destination {_namespace(doc)!r}"
            )
    return problems


def check_the_store_render_holds_no_reconcile_workload() -> None:
    assert kind_problems(_render(), _projects()) == []


def check_the_kind_rule_names_a_reconcile_job() -> None:
    job = {"kind": "Job", "metadata": {"name": "bucket-reconcile", "namespace": NAMESPACE}}

    assert any(
        p.startswith("Job/bucket-reconcile:") for p in kind_problems([*_render(), job], _projects())
    )
