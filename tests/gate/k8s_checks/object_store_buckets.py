"""The buckets and the lifecycle rules of the object store (#4756).

The SeaweedFS operator makes each bucket, quota, anonymous read and lifecycle rule of the store
from the CRs of `k8s/object-store/buckets.yaml`, so no reconcile code runs. Each bucket and its
lifecycle policy live in namespace `object-store` beside the `Seaweed` CR, and the operator watches
only that namespace: the chart gives each watched namespace the manager Role of the operator, which
can read and write every Secret there. These checks read the render of `k8s/object-store` and the
values of the operator chart. Each rule is a function that returns its problems. One check applies
the rule to the committed render, and one applies it to a fixture that breaks it and asserts that
the problem names the object, so a rule that stops finding its problem fails the row too.
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

NAMESPACE: Final = "object-store"
CR_NAME: Final = "seaweedfs"

# The platform buckets of the devops-cli workloads and their quotas, all in the store namespace.
# `local-path` does not enforce the size of a claim, so the quotas are the limits. The tenant
# buckets `backups-*` come from the tenant chart of dan-petty/infra.
PLATFORM_BUCKETS: Final = {
    "reports": "20Gi",
    "reports-private": "20Gi",
    "cache": "10Gi",
    "argo-artifacts": "10Gi",
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
# The kinds of the operator that it reconciles only in a watched namespace.
WATCHED_KINDS: Final = frozenset({"Bucket", "BucketLifecyclePolicy"})
# The kinds the render may hold: the operator CRs, the perimeter and the budgets. No Job, CronJob,
# workload or script reconciles the store, and no ResourceReferenceGrant admits a CR of another
# namespace to the store.
STORE_KINDS: Final = frozenset(
    {"Seaweed", "Bucket", "BucketLifecyclePolicy", "NetworkPolicy", "PodDisruptionBudget"}
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
    """`clusterRef` names the `Seaweed` CR of the namespace of the bucket, the store namespace, so
    the operator needs no grant."""
    spec = bucket.get("spec", {})
    ref = spec.get("clusterRef") or {}
    return (
        "seaweedRef" not in spec
        and ref.get("name") == CR_NAME
        and ref.get("namespace", _namespace(bucket)) == _namespace(bucket) == NAMESPACE
    )


# The buckets.


def bucket_problems(buckets: Iterable[Mapping[str, Any]]) -> list[str]:
    """Each platform bucket is there in the store namespace with its quota, and each bucket of the
    store names the store in `clusterRef`, keeps an enforced quota and keeps its data when its CR
    goes."""
    problems: list[str] = []
    found = {_bucket_name(bucket): bucket for bucket in buckets}
    for name, size in PLATFORM_BUCKETS.items():
        bucket = found.get(name)
        if bucket is None:
            problems.append(f"Bucket/{name}: no Bucket in the render")
            continue
        quota = bucket.get("spec", {}).get("quota", {}).get("size")
        if quota is None or parse_quantity(quota) != parse_quantity(size):
            problems.append(f"Bucket/{name}: quota is {quota!r}, not {size}")
        if _namespace(bucket) != NAMESPACE:
            problems.append(f"Bucket/{name}: namespace is {_namespace(bucket)!r}, not {NAMESPACE}")
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


def check_the_bucket_rule_names_a_bucket_in_the_namespace_of_its_writer() -> None:
    buckets = _kind("Bucket")
    for bucket in buckets:
        if _bucket_name(bucket) == "cache":
            bucket["metadata"]["namespace"] = "devops"
            bucket["spec"]["clusterRef"]["namespace"] = NAMESPACE

    problems = bucket_problems(buckets)

    assert "Bucket/cache: namespace is 'devops', not object-store" in problems
    assert f"Bucket/cache: clusterRef does not name {NAMESPACE}/{CR_NAME}" in problems


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
    """The operator watches only the store namespace, and each CR that it reconciles is there. The
    chart gives each watched namespace the manager Role of the operator, which can read and write
    every Secret there, and an empty list gives it a ClusterRole over every namespace."""
    found = list(values.get("watchNamespaces") or [])
    problems = [] if found == [NAMESPACE] else [f"watchNamespaces is {found}, not [{NAMESPACE}]"]
    problems.extend(
        f"{_ref(doc)}: the operator does not watch namespace {_namespace(doc)!r}"
        for doc in documents
        if doc.get("kind") in WATCHED_KINDS and _namespace(doc) not in found
    )
    return problems


def check_the_operator_watches_only_the_store_namespace() -> None:
    assert watch_problems(_values(), _render()) == []


def check_the_watch_rule_names_a_watched_writer_namespace() -> None:
    values = {**_values(), "watchNamespaces": [NAMESPACE, "devops", "argo-workflows"]}

    assert watch_problems(values, _render()) == [
        "watchNamespaces is ['object-store', 'devops', 'argo-workflows'], not [object-store]"
    ]


def check_the_watch_rule_names_a_watch_of_every_namespace() -> None:
    values = {**_values(), "watchNamespaces": []}

    assert "watchNamespaces is [], not [object-store]" in watch_problems(values, _render())


# The kinds of the render.


def kind_problems(documents: Iterable[Mapping[str, Any]]) -> list[str]:
    """The render holds only the operator CRs, the perimeter and the budgets, each in the store
    namespace."""
    problems: list[str] = []
    for doc in documents:
        if doc.get("kind") not in STORE_KINDS:
            problems.append(f"{_ref(doc)}: kind {doc.get('kind')} is not a kind of the store")
        if _namespace(doc) != NAMESPACE:
            problems.append(f"{_ref(doc)}: namespace is {_namespace(doc)!r}, not {NAMESPACE}")
    return problems


def check_the_store_render_holds_no_reconcile_workload() -> None:
    assert kind_problems(_render()) == []


def check_the_kind_rule_names_a_reconcile_job() -> None:
    job = {"kind": "Job", "metadata": {"name": "bucket-reconcile", "namespace": NAMESPACE}}

    assert kind_problems([*_render(), job]) == [
        "Job/bucket-reconcile: kind Job is not a kind of the store"
    ]


def check_the_kind_rule_names_a_reference_grant() -> None:
    grant = {
        "apiVersion": "seaweed.seaweedfs.com/v1",
        "kind": "ResourceReferenceGrant",
        "metadata": {"name": "object-store-buckets", "namespace": NAMESPACE},
    }

    assert kind_problems([*_render(), grant]) == [
        "ResourceReferenceGrant/object-store-buckets: kind ResourceReferenceGrant is not a kind"
        " of the store"
    ]


def check_the_kind_rule_names_a_policy_in_the_namespace_of_its_writer() -> None:
    documents = [copy.deepcopy(doc) for doc in _render()]
    for doc in documents:
        if doc.get("kind") == "BucketLifecyclePolicy" and _name(doc) == "argo-artifacts":
            doc["metadata"]["namespace"] = "argo-workflows"

    assert kind_problems(documents) == [
        "BucketLifecyclePolicy/argo-artifacts: namespace is 'argo-workflows', not object-store"
    ]
