"""The buckets, the lifecycle rules and the writer keys of the object store (#4756).

The SeaweedFS operator makes each bucket, quota, anonymous read, lifecycle rule, identity, policy
and key of the store from the CRs of `k8s/object-store/buckets.yaml` and `writers.yaml`, so no
reconcile code runs. These checks read the render of `k8s/object-store`, the values of the operator
chart and the AppProject. Each rule is a function that returns its problems. One check applies the
rule to the committed render, and one applies it to a fixture that breaks it and asserts that the
problem names the object, so a rule that stops finding its problem fails the row too.
"""

from __future__ import annotations

import copy
import functools
from collections.abc import Iterable, Mapping
from typing import Any, Final

import yaml
from kubernetes.utils.quantity import parse_quantity

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS, ClusterSecret
from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

STORE_DIR: Final = REPO_ROOT / "k8s" / "object-store"
OPERATOR_VALUES: Final = STORE_DIR / "operator-values.yaml"
PROJECTS: Final = REPO_ROOT / "k8s" / "argocd" / "apps" / "projects.yaml"

NAMESPACE: Final = "object-store"
CR_NAME: Final = "seaweedfs"
PROJECT: Final = "homelab"
GROUP: Final = "seaweed.seaweedfs.com"

# The platform buckets of the devops-cli workloads and their quotas. `local-path` does not
# enforce the size of a claim, so the quotas are the limits. The tenant buckets `backups-*` come
# from the tenant chart of dan-petty/infra.
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
ACCESS_KEY_FIELD: Final = "accessKey"
SECRET_KEY_FIELD: Final = "secretKey"
# The kinds the render may hold: the operator CRs, the perimeter and the budgets. No Job, CronJob,
# workload or script reconciles the store.
STORE_KINDS: Final = frozenset(
    {
        "Seaweed",
        "Bucket",
        "BucketLifecyclePolicy",
        "S3Identity",
        "S3Policy",
        "S3PolicyBinding",
        "S3Credentials",
        "ResourceReferenceGrant",
        "NetworkPolicy",
        "PodDisruptionBudget",
    }
)
_ARN_PREFIX: Final = "arn:aws:s3:::"


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


def _names_the_store(doc: Mapping[str, Any]) -> bool:
    ref = doc.get("spec", {}).get("seaweedRef") or {}
    return ref.get("name") == CR_NAME and (ref.get("namespace") or _namespace(doc)) == NAMESPACE


# The buckets.


def bucket_problems(buckets: Iterable[Mapping[str, Any]]) -> list[str]:
    """Each platform bucket is there with its quota, and each bucket of the store names the store,
    keeps an enforced quota and keeps its data when its CR goes."""
    problems: list[str] = []
    found = {_bucket_name(bucket): bucket for bucket in buckets}
    for name, size in PLATFORM_BUCKETS.items():
        quota = found.get(name, {}).get("spec", {}).get("quota", {}).get("size")
        if name not in found:
            problems.append(f"Bucket/{name}: no Bucket in the render")
        elif quota is None or parse_quantity(quota) != parse_quantity(size):
            problems.append(f"Bucket/{name}: quota is {quota!r}, not {size}")
    for bucket in found.values():
        spec = bucket.get("spec", {})
        quota = spec.get("quota", {})
        if _namespace(bucket) != NAMESPACE:
            problems.append(f"{_ref(bucket)}: namespace is {_namespace(bucket)!r}, not {NAMESPACE}")
        if "clusterRef" in spec or not _names_the_store(bucket):
            problems.append(f"{_ref(bucket)}: seaweedRef does not name {NAMESPACE}/{CR_NAME}")
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
        p for p in _kind("BucketLifecyclePolicy") if p["spec"]["bucketRef"]["name"] == _name(bucket)
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


# The writer policies.


def _resource_bucket(resource: str) -> str:
    return resource.removeprefix(_ARN_PREFIX).split("/", 1)[0]


def _statement_problems(policy: Mapping[str, Any], buckets: set[str]) -> list[str]:
    problems: list[str] = []
    spec = policy.get("spec", {})
    if "policyDocument" in spec:
        problems.append(f"{_ref(policy)}: a raw policyDocument, not statements")
    for statement in spec.get("statements", []):
        if statement.get("effect") != "Allow":
            problems.append(f"{_ref(policy)}: a statement with effect {statement.get('effect')}")
        if any("*" in action for action in statement.get("actions", [])):
            problems.append(f"{_ref(policy)}: a wildcard action")
        for resource in statement.get("resources", []):
            if "*" in _resource_bucket(resource) or _resource_bucket(resource) not in buckets:
                problems.append(f"{_ref(policy)}: resource {resource!r} is no bucket of the store")
    return problems


def _policy_buckets(policy: Mapping[str, Any]) -> set[str]:
    return {
        _resource_bucket(resource)
        for statement in policy.get("spec", {}).get("statements", [])
        for resource in statement.get("resources", [])
    }


def policy_problems(documents: Iterable[Mapping[str, Any]]) -> list[str]:
    """Each policy allows actions only on buckets of the store, each binding attaches a policy of
    the render to identities of the render, and no bucket is in the policies of two identities."""
    docs = list(documents)
    buckets = {_bucket_name(bucket) for bucket in _kind("Bucket", docs)}
    identities = {_name(identity) for identity in _kind("S3Identity", docs)}
    policies = {_name(policy): policy for policy in _kind("S3Policy", docs)}
    problems = [p for policy in policies.values() for p in _statement_problems(policy, buckets)]
    owners: dict[str, set[str]] = {}
    for binding in _kind("S3PolicyBinding", docs):
        spec = binding.get("spec", {})
        policy = policies.get(spec.get("policyRef", {}).get("name", ""))
        if policy is None:
            problems.append(f"{_ref(binding)}: policyRef names no S3Policy of the render")
            continue
        for subject in spec.get("subjects", []):
            if (
                subject.get("kind", "S3Identity") != "S3Identity"
                or subject.get("name") not in identities
            ):
                problems.append(
                    f"{_ref(binding)}: subject {subject.get('name')!r} is no S3Identity"
                )
                continue
            for bucket in _policy_buckets(policy):
                owners.setdefault(bucket, set()).add(str(subject["name"]))
    problems.extend(
        f"bucket {bucket} is in the policies of {', '.join(sorted(names))}"
        for bucket, names in sorted(owners.items())
        if len(names) > 1
    )
    return problems


def _with_policy(policy_name: str, change: Any) -> list[dict[str, Any]]:
    documents = [copy.deepcopy(dict(doc)) for doc in _render()]
    for doc in documents:
        if doc.get("kind") == "S3Policy" and _name(doc) == policy_name:
            change(doc["spec"]["statements"])
    return documents


def check_each_writer_key_works_only_on_its_own_buckets() -> None:
    assert policy_problems(_render()) == []


def check_the_policy_rule_names_a_policy_on_every_bucket() -> None:
    documents = _with_policy("argo", lambda statements: statements[0]["resources"].append("*"))

    assert any(p.startswith("S3Policy/argo:") for p in policy_problems(documents))


def check_the_policy_rule_names_a_bucket_of_two_identities() -> None:
    documents = _with_policy("argo", lambda statements: statements[0]["resources"].append("cache"))

    assert any(
        p.startswith("bucket cache is in the policies of") for p in policy_problems(documents)
    )


# The writer keys and their grants.


def _secret_target(credentials: Mapping[str, Any]) -> tuple[str, str, tuple[str, str]]:
    """The namespace, the name and the two fields of the Secret of a credential, with the defaults
    of `S3Credentials`."""
    ref = credentials.get("spec", {}).get("secretRef", {})
    fields = (
        ref.get("accessKeyField", ACCESS_KEY_FIELD),
        ref.get("secretKeyField", SECRET_KEY_FIELD),
    )
    return (
        ref.get("namespace") or _namespace(credentials),
        ref.get("name") or _name(credentials),
        fields,
    )


def _grant_admits(grant: Mapping[str, Any], secret: str) -> bool:
    spec = grant.get("spec", {})
    return any(
        f == {"group": GROUP, "kind": "S3Credentials", "namespace": NAMESPACE}
        for f in spec.get("from", [])
    ) and any(
        t.get("group") == "" and t.get("kind") == "Secret" and t.get("name") == secret
        for t in spec.get("to", [])
    )


def _grant_problems(grant: Mapping[str, Any], secrets: set[tuple[str, str]]) -> list[str]:
    """A grant admits only the credentials of the store, by namespace name, to only the Secrets
    that a credential names."""
    ref = f"ResourceReferenceGrant {_namespace(grant)}/{_name(grant)}"
    spec = grant.get("spec", {})
    problems = [
        f"{ref}: admits {source}, not S3Credentials of namespace {NAMESPACE}"
        for source in spec.get("from", [])
        if source != {"group": GROUP, "kind": "S3Credentials", "namespace": NAMESPACE}
    ]
    problems.extend(
        f"{ref}: target {target} is no Secret that a credential names"
        for target in spec.get("to", [])
        if target.get("group") != ""
        or target.get("kind") != "Secret"
        or (_namespace(grant), target.get("name")) not in secrets
    )
    return problems


def key_problems(
    documents: Iterable[Mapping[str, Any]], table: Iterable[ClusterSecret]
) -> list[str]:
    """Each credential names an identity of the render and a Secret with a row that holds its
    fields, through a grant of the Secret namespace that admits only the store."""
    docs = list(documents)
    rows = {secret.ref: secret for secret in table}
    identities = {_name(identity) for identity in _kind("S3Identity", docs)}
    grants = _kind("ResourceReferenceGrant", docs)
    problems: list[str] = []
    secrets: set[tuple[str, str]] = set()
    for credentials in _kind("S3Credentials", docs):
        namespace, name, fields = _secret_target(credentials)
        secrets.add((namespace, name))
        row = rows.get(f"{namespace}/{name}")
        if credentials.get("spec", {}).get("identityRef", {}).get("name") not in identities:
            problems.append(f"{_ref(credentials)}: identityRef names no S3Identity of the render")
        if not _names_the_store(credentials):
            problems.append(f"{_ref(credentials)}: seaweedRef does not name {NAMESPACE}/{CR_NAME}")
        if row is None:
            problems.append(
                f"{_ref(credentials)}: Secret {namespace}/{name} has no row in CLUSTER_SECRETS"
            )
        elif not set(fields) <= {entry.key for entry in row.entries}:
            problems.append(f"{_ref(credentials)}: the row of {namespace}/{name} lacks {fields}")
        if namespace != _namespace(credentials) and not any(
            _namespace(grant) == namespace and _grant_admits(grant, name) for grant in grants
        ):
            problems.append(
                f"{_ref(credentials)}: no grant of {namespace} admits it to Secret {name}"
            )
    problems.extend(p for grant in grants for p in _grant_problems(grant, secrets))
    return problems


def check_each_writer_key_comes_from_a_pushed_secret_through_a_narrow_grant() -> None:
    assert key_problems(_render(), CLUSTER_SECRETS) == []


def check_the_key_rule_names_a_credential_with_no_row() -> None:
    (credentials, *_) = _kind("S3Credentials")
    credentials["spec"]["secretRef"] = {"namespace": "devops", "name": "object-store-missing"}

    assert any(
        "devops/object-store-missing" in p
        for p in key_problems([*_kind("S3Identity"), credentials], CLUSTER_SECRETS)
    )


def check_the_key_rule_names_a_grant_to_every_secret() -> None:
    documents = [copy.deepcopy(dict(doc)) for doc in _render()]
    for doc in documents:
        if doc.get("kind") == "ResourceReferenceGrant" and _namespace(doc) == "devops":
            for target in doc["spec"]["to"]:
                target.pop("name", None)

    assert any(
        "ResourceReferenceGrant devops/object-store-credentials" in p
        for p in key_problems(documents, CLUSTER_SECRETS)
    )


# The watch scope of the operator.


def watch_problems(
    values: Mapping[str, Any], credentials: Iterable[Mapping[str, Any]]
) -> list[str]:
    """The operator watches the store and the namespace of each Secret of a credential, each once:
    it reads that Secret and its grants through the cache of these namespaces only, and an empty
    list gives it a ClusterRole over every namespace."""
    found = list(values.get("watchNamespaces") or [])
    expected = {NAMESPACE} | {_secret_target(c)[0] for c in credentials}
    problems = [
        f"watchNamespaces lacks namespace {namespace}"
        for namespace in sorted(expected - set(found))
    ]
    problems.extend(
        f"watchNamespaces names namespace {namespace}, which no credential needs"
        for namespace in sorted(set(found) - expected)
    )
    if len(found) != len(set(found)):
        problems.append(f"watchNamespaces repeats a namespace: {found}")
    return problems


def check_the_operator_watches_the_store_and_each_writer_namespace() -> None:
    assert watch_problems(_values(), _kind("S3Credentials")) == []


def check_the_watch_rule_names_a_writer_namespace_the_operator_does_not_watch() -> None:
    values = {**_values(), "watchNamespaces": [NAMESPACE]}

    assert "watchNamespaces lacks namespace devops" in watch_problems(
        values, _kind("S3Credentials")
    )


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
