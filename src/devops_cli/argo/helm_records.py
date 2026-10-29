"""Retire the Helm release records of charts that Argo CD renders (#1644).

Helm's default storage keeps each revision of a release as a Secret in the release's namespace,
labelled `owner=helm` and `name=<release>`. Argo CD renders a chart with `helm template` and keeps
no release, so a chart that moved from `helm upgrade --install` to an Application keeps its last
records, and `helm rollback` or `helm uninstall` would still act on objects that Argo CD owns.
Deleting the records makes Helm forget the release. Every object stays.

`plan_helm_record_retirement` only reads. A release is planned when an Application renders it: a
source of the Application has a `chart`, and the release name is that source's
`helm.releaseName`, or else the Application's name, in the Application's destination namespace.
It qualifies when each top-level object (no owner reference) that carries the release's Helm
annotations was applied by Argo CD: the object carries the Application's tracking id, or names the
field manager `argocd-controller`. Argo CD writes no tracking id on a CustomResourceDefinition. A
record with an owner reference belongs to an operator, such as the Alloy operator, and is kept.
The reads use a `jsonpath` of metadata fields, so no Secret data reaches this process.

`retire_helm_records` deletes the records of the qualifying releases by name, and only those.
`dry_run_helm_record_retirement` makes no request: it lists the requests a run makes.
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from devops_cli.config.commands import build_kubectl_cmd
from devops_cli.config.constants import CONST_ARGOCD_TRACKING_ID_ANNOTATION
from devops_cli.config.defaults import DEFAULT_ARGOCD_NAMESPACE, DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.argo import ArgoError
from devops_cli.lang import MESSAGES

_APPLICATIONS = "applications.argoproj.io"
_RECORD_SELECTOR = "owner=helm"
_ARGOCD_FIELD_MANAGER = "argocd-controller"
_RELEASE_NAME_ANNOTATION = "meta.helm.sh/release-name"
_RELEASE_NAMESPACE_ANNOTATION = "meta.helm.sh/release-namespace"
# Events are never part of a release, and they are the most numerous objects of a cluster.
_UNLISTED_KINDS = frozenset({"events", "events.events.k8s.io"})
_DETAIL_CHARS = 300


def _key(name: str) -> str:
    """An annotation name as a jsonpath key: its dots escaped."""
    return name.replace(".", "\\.")


def _jsonpath(fields: Sequence[str]) -> str:
    """A kubectl output that prints the fields of each item, tab-separated, one item a line."""
    columns = '{"\\t"}'.join(f"{{{name}}}" for name in fields)
    return f'jsonpath={{range .items[*]}}{columns}{{"\\n"}}{{end}}'


_RECORD_FIELDS = (
    ".metadata.namespace",
    ".metadata.name",
    ".metadata.labels.name",
    ".metadata.ownerReferences[*].kind",
)
_OBJECT_FIELDS = (
    ".kind",
    ".metadata.namespace",
    ".metadata.name",
    f".metadata.annotations.{_key(_RELEASE_NAME_ANNOTATION)}",
    f".metadata.annotations.{_key(_RELEASE_NAMESPACE_ANNOTATION)}",
    f".metadata.annotations.{_key(CONST_ARGOCD_TRACKING_ID_ANNOTATION)}",
    ".metadata.ownerReferences[*].kind",
    ".metadata.managedFields[*].manager",
)


@dataclass(frozen=True)
class HelmRelease:
    """A release that an Application renders: its records, and the objects Argo CD did not apply."""

    name: str
    namespace: str
    application: str
    records: tuple[str, ...]
    unapplied: tuple[str, ...] = ()

    @property
    def qualifies(self) -> bool:
        """Whether Argo CD applied each object of the release, so its records can go."""
        return not self.unapplied


@dataclass(frozen=True)
class RetirementPlan:
    """The releases that Applications render, and the `<namespace>/<release>` of the rest."""

    releases: tuple[HelmRelease, ...]
    kept: tuple[str, ...]

    @property
    def qualifying(self) -> tuple[HelmRelease, ...]:
        return tuple(release for release in self.releases if release.qualifies)


# ── kubectl ──────────────────────────────────────────────────────────────────


def _applications_args() -> list[str]:
    return ["get", _APPLICATIONS, "-n", DEFAULT_ARGOCD_NAMESPACE, "-o", "json"]


def _records_args() -> list[str]:
    return [
        "get",
        "secrets",
        "--all-namespaces",
        "-l",
        _RECORD_SELECTOR,
        "-o",
        _jsonpath(_RECORD_FIELDS),
    ]


def _kinds_args() -> list[str]:
    return ["api-resources", "--verbs=list,create", "-o", "name"]


def _objects_args(kinds: Sequence[str]) -> list[str]:
    return [
        "get",
        ",".join(kinds),
        "--all-namespaces",
        "--show-managed-fields",
        "-o",
        _jsonpath(_OBJECT_FIELDS),
    ]


def _delete_args(namespace: str, records: Sequence[str]) -> list[str]:
    return ["delete", "secret", "-n", namespace, "--ignore-not-found", *records]


def _kubectl(args: Sequence[str], context: str | None) -> str:
    """Run one kubectl request and return its stdout, raising `ArgoError` when it fails."""
    request = " ".join(["kubectl", *args[:2]])
    try:
        result = run_subprocess(
            build_kubectl_cmd(args, context),
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ArgoError(
            MESSAGES.argo.helm_records_request_timeout.format(request=request, seconds=exc.timeout)
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[:_DETAIL_CHARS]
        raise ArgoError(
            MESSAGES.argo.helm_records_request_failed.format(request=request, detail=detail)
        )
    return result.stdout or ""


def _rows(output: str, width: int) -> list[tuple[str, ...]]:
    """The tab-separated lines of a jsonpath read, each padded to `width` fields."""
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        rows.append(tuple(fields + [""] * (width - len(fields)))[:width])
    return rows


# ── The plan ─────────────────────────────────────────────────────────────────


def _rendered_releases(applications: dict[str, Any]) -> dict[tuple[str, str], str]:
    """`(release, namespace)` to the name of the Application that renders that chart release."""
    rendered: dict[tuple[str, str], str] = {}
    for item in applications.get("items") or []:
        name = str((item.get("metadata") or {}).get("name") or "")
        spec = item.get("spec") or {}
        namespace = str((spec.get("destination") or {}).get("namespace") or "")
        sources = spec.get("sources") or ([spec["source"]] if spec.get("source") else [])
        for source in sources:
            if name and namespace and source.get("chart"):
                release = (source.get("helm") or {}).get("releaseName") or name
                rendered[(str(release), namespace)] = name
    return rendered


def _object_ref(kind: str, namespace: str, name: str) -> str:
    return f"{kind}/{namespace}/{name}" if namespace else f"{kind}/{name}"


def _unapplied_objects(
    candidates: dict[tuple[str, str], str], context: str | None
) -> dict[tuple[str, str], list[str]]:
    """For each candidate release, the top-level objects of it that Argo CD did not apply."""
    kinds = [
        kind for kind in _kubectl(_kinds_args(), context).split() if kind not in _UNLISTED_KINDS
    ]
    unapplied: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in _rows(_kubectl(_objects_args(kinds), context), len(_OBJECT_FIELDS)):
        kind, namespace, name, release, release_namespace, tracking, owners, managers = row
        application = candidates.get((release, release_namespace))
        if application is None or owners:
            continue
        if tracking.startswith(f"{application}:") or _ARGOCD_FIELD_MANAGER in managers.split():
            continue
        unapplied[(release, release_namespace)].append(_object_ref(kind, namespace, name))
    return unapplied


def plan_helm_record_retirement(context: str | None = None) -> RetirementPlan:
    """The releases whose records can go, and those that stay. It only reads."""
    rendered = _rendered_releases(json.loads(_kubectl(_applications_args(), context) or "{}"))
    records: dict[tuple[str, str], list[str]] = defaultdict(list)
    kept: set[str] = set()
    for namespace, secret, release, owners in _rows(_kubectl(_records_args(), context), 4):
        if owners or (release, namespace) not in rendered:
            kept.add(f"{namespace}/{release}")
            continue
        records[(release, namespace)].append(secret)
    candidates = {key: rendered[key] for key in records}
    unapplied = _unapplied_objects(candidates, context) if candidates else {}
    releases = tuple(
        HelmRelease(
            name=release,
            namespace=namespace,
            application=candidates[(release, namespace)],
            records=tuple(sorted(secrets)),
            unapplied=tuple(sorted(unapplied.get((release, namespace), ()))),
        )
        for (release, namespace), secrets in sorted(records.items(), key=lambda item: item[0][::-1])
    )
    return RetirementPlan(releases=releases, kept=tuple(sorted(kept)))


def retire_helm_records(
    plan: RetirementPlan,
    context: str | None = None,
    progress: Callable[[HelmRelease], None] | None = None,
) -> tuple[HelmRelease, ...]:
    """Delete the records of each qualifying release, by name, and return those releases."""
    retired = []
    for release in plan.qualifying:
        _kubectl(_delete_args(release.namespace, release.records), context)
        retired.append(release)
        if progress is not None:
            progress(release)
    return tuple(retired)


def dry_run_helm_record_retirement(context: str | None = None) -> tuple[PlannedRequest, ...]:
    """The requests a run makes, in order, making none."""

    def planned(
        args: Sequence[str], target: str, *, condition: str = "", repeat: str = ""
    ) -> PlannedRequest:
        return PlannedRequest(
            method=f"kubectl {args[0]}",
            target=target,
            argv=tuple(build_kubectl_cmd(args, context)),
            condition=condition,
            repeat=repeat,
        )

    candidate = "an Application renders a release that has a record"
    return (
        planned(
            _applications_args(),
            f"the Argo CD Applications in namespace {DEFAULT_ARGOCD_NAMESPACE}",
        ),
        planned(_records_args(), "the metadata of the Helm release records"),
        planned(_kinds_args(), "the kinds that Helm can create", condition=candidate),
        planned(
            _objects_args(["<kinds>"]),
            "the metadata of every object of those kinds",
            condition=candidate,
        ),
        planned(
            _delete_args("<namespace>", ["<records>"]),
            "the records of a release that qualifies",
            condition="--confirm",
            repeat="for each release that qualifies",
        ),
    )


__all__ = [
    "HelmRelease",
    "RetirementPlan",
    "dry_run_helm_record_retirement",
    "plan_helm_record_retirement",
    "retire_helm_records",
]
