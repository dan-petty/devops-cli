"""Tests for the retirement of Helm release records of charts that Argo CD renders (#1644).

kubectl is faked at the process edge (`process_fake`). `Cluster` answers the four reads of a plan
from a small cluster: the Applications, the release records, the resource kinds and the objects.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.argo.helm_records import HelmRelease, RetirementPlan, plan_helm_record_retirement
from devops_cli.main import app as main_app
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()

CONTEXT = "homelab"
COMMAND = ["argo", "cd", "apps", "retire-helm-records", "--context", CONTEXT]


def _application(
    name: str, namespace: str, *, chart: str | None = None, release_name: str | None = None
) -> dict[str, Any]:
    if chart:
        source: dict[str, Any] = {
            "repoURL": "https://charts.example.com",
            "chart": chart,
            "targetRevision": "1.0.0",
        }
        if release_name:
            source["helm"] = {"releaseName": release_name}
    else:
        source = {"repoURL": "https://github.com/example/repo", "path": f"k8s/{name}"}
    values = {"repoURL": "https://github.com/example/repo", "ref": "values"}
    return {
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {
            "project": "homelab",
            "destination": {"server": "https://kubernetes.default.svc", "namespace": namespace},
            "sources": [source, values],
        },
    }


def _record(namespace: str, release: str, version: int, owners: str = "") -> str:
    return f"{namespace}\tsh.helm.release.v1.{release}.v{version}\t{release}\t{owners}"


def _object(
    kind: str,
    namespace: str,
    name: str,
    release: str,
    release_namespace: str,
    *,
    tracking: str = "",
    owners: str = "",
    managers: str = "helm",
) -> str:
    return "\t".join(
        (kind, namespace, name, release, release_namespace, tracking, owners, managers)
    )


@dataclass
class Cluster:
    """What kubectl answers; each field is one read of the plan."""

    applications: list[dict[str, Any]] = field(
        default_factory=lambda: [
            _application("grafana", "monitoring", chart="grafana"),
            _application(
                "prometheus-operator-crds", "monitoring", chart="prometheus-operator-crds"
            ),
            _application("stack", "logging", chart="loki", release_name="loki"),
            _application("monitoring", "monitoring"),
        ]
    )
    records: list[str] = field(
        default_factory=lambda: [
            _record("monitoring", "grafana", 49),
            _record("monitoring", "grafana", 50),
            _record("monitoring", "prometheus-operator-crds", 28),
            _record("logging", "loki", 83),
            _record("monitoring", "k8s-monitoring-alloy-logs", 3, owners="Alloy"),
            _record("default", "legacy", 1),
        ]
    )
    kinds: list[str] = field(
        default_factory=lambda: [
            "configmaps",
            "secrets",
            "events",
            "deployments.apps",
            "events.events.k8s.io",
            "customresourcedefinitions.apiextensions.k8s.io",
        ]
    )
    objects: list[str] = field(
        default_factory=lambda: [
            _object(
                "Deployment",
                "monitoring",
                "grafana",
                "grafana",
                "monitoring",
                tracking="grafana:apps/Deployment:monitoring/grafana",
                managers="helm argocd-controller",
            ),
            _object(
                "CustomResourceDefinition",
                "",
                "dashboards.grafana.example.com",
                "grafana",
                "monitoring",
                managers="helm argocd-controller",
            ),
            _object(
                "ControllerRevision",
                "monitoring",
                "grafana-6d5f",
                "grafana",
                "monitoring",
                owners="StatefulSet",
                managers="kube-controller-manager",
            ),
            _object(
                "CustomResourceDefinition",
                "",
                "servicemonitors.monitoring.coreos.com",
                "prometheus-operator-crds",
                "monitoring",
                managers="helm k3s",
            ),
            _object(
                "StatefulSet",
                "logging",
                "loki",
                "loki",
                "logging",
                tracking="stack:apps/StatefulSet:logging/loki",
                managers="argocd-controller",
            ),
            _object(
                "ClusterRole",
                "",
                "k8s-monitoring-alloy-logs",
                "k8s-monitoring-alloy-logs",
                "monitoring",
                managers="helm-operator",
            ),
            _object("Deployment", "default", "legacy", "legacy", "default"),
        ]
    )
    failing_read: str = ""

    def install(self, fake: ProcessFake, context: str | None = None) -> None:
        kubectl = ("kubectl", *(("--context", context) if context else ()))
        fake.answer(
            (*kubectl, "get", "applications.argoproj.io", "-n", "argocd"),
            ProcessAnswer(stdout=json.dumps({"items": self.applications})),
        )
        fake.answer(
            (*kubectl, "get", "secrets", "--all-namespaces", "-l", "owner=helm"),
            ProcessAnswer(stdout="".join(f"{row}\n" for row in self.records)),
        )
        fake.answer(
            (*kubectl, "api-resources"),
            ProcessAnswer(stdout="".join(f"{kind}\n" for kind in self.kinds)),
        )
        fake.answer(
            lambda call: "--show-managed-fields" in call.argv,
            ProcessAnswer(stdout="".join(f"{row}\n" for row in self.objects)),
        )
        if self.failing_read:
            fake.answer(
                (*kubectl, "get", self.failing_read),
                ProcessAnswer(returncode=1, stderr="Error from server (Forbidden): forbidden"),
            )


def _deletes(fake: ProcessFake) -> list[tuple[str, ...]]:
    return [call.argv for call in fake.calls if "delete" in call.argv]


def _object_read(fake: ProcessFake) -> ProcessCall:
    return next(call for call in fake.calls if "--show-managed-fields" in call.argv)


EXPECTED_PLAN = RetirementPlan(
    releases=(
        HelmRelease(
            name="loki",
            namespace="logging",
            application="stack",
            records=("sh.helm.release.v1.loki.v83",),
        ),
        HelmRelease(
            name="grafana",
            namespace="monitoring",
            application="grafana",
            records=("sh.helm.release.v1.grafana.v49", "sh.helm.release.v1.grafana.v50"),
        ),
        HelmRelease(
            name="prometheus-operator-crds",
            namespace="monitoring",
            application="prometheus-operator-crds",
            records=("sh.helm.release.v1.prometheus-operator-crds.v28",),
            unapplied=("CustomResourceDefinition/servicemonitors.monitoring.coreos.com",),
        ),
    ),
    kept=("default/legacy", "monitoring/k8s-monitoring-alloy-logs"),
)


def test_the_plan_retires_releases_that_argo_cd_applied_and_keeps_the_rest(
    process_fake: ProcessFake,
) -> None:
    """Verify a release qualifies by tracking id or the argocd-controller manager, and the rest stay."""
    Cluster().install(process_fake)

    plan = plan_helm_record_retirement()

    assert (
        plan,
        [release.name for release in plan.qualifying],
        [part for part in _object_read(process_fake).argv[2].split(",") if "event" in part],
    ) == (EXPECTED_PLAN, ["loki", "grafana"], [])


def test_the_plan_writes_nothing_and_reads_no_secret_data(process_fake: ProcessFake) -> None:
    """Verify the plan sends no delete, and reads Secrets only through a metadata jsonpath."""
    Cluster().install(process_fake, CONTEXT)

    result = runner.invoke(main_app, COMMAND)

    secret_reads = [
        call.argv
        for call in process_fake.calls
        if call.argv[3] == "get" and "secrets" in call.argv[4].split(",")
    ]
    outputs = [argv[argv.index("-o") + 1] for argv in secret_reads]
    assert (
        result.exit_code,
        _deletes(process_fake),
        len(secret_reads),
        all(output.startswith("jsonpath=") and ".data" not in output for output in outputs),
        "servicemonitors.monitoring.coreos.com" in result.output,
        "--confirm" in result.output,
    ) == (0, [], 2, True, True, True)


def test_confirm_deletes_the_planned_records_by_name(process_fake: ProcessFake) -> None:
    """Verify --confirm deletes each qualifying release's records by name, and nothing else."""
    Cluster().install(process_fake, CONTEXT)

    result = runner.invoke(main_app, [*COMMAND, "--confirm"])

    kubectl = ("kubectl", "--context", CONTEXT, "delete", "secret")
    assert (result.exit_code, _deletes(process_fake)) == (
        0,
        [
            (*kubectl, "-n", "logging", "--ignore-not-found", "sh.helm.release.v1.loki.v83"),
            (
                *kubectl,
                "-n",
                "monitoring",
                "--ignore-not-found",
                "sh.helm.release.v1.grafana.v49",
                "sh.helm.release.v1.grafana.v50",
            ),
        ],
    )


def test_the_dry_run_starts_no_process(process_fake: ProcessFake) -> None:
    """Verify --dry-run makes no request and lists the reads and the confirmed delete."""
    Cluster().install(process_fake, CONTEXT)

    result = runner.invoke(main_app, [*COMMAND, "--dry-run"])

    assert (
        result.exit_code,
        process_fake.calls,
        [
            text in result.output
            for text in (
                "kubectl --context homelab get applications.argoproj.io -n argocd",
                "-l owner=helm",
                "api-resources",
                "--show-managed-fields",
                "delete secret",
                "--confirm",
            )
        ],
    ) == (0, [], [True] * 6)


def test_a_failed_read_stops_before_any_delete(process_fake: ProcessFake) -> None:
    """Verify a refused kubectl read ends the command with an error and deletes nothing."""
    Cluster(failing_read="secrets").install(process_fake, CONTEXT)

    result = runner.invoke(main_app, [*COMMAND, "--confirm"])

    assert (result.exit_code, _deletes(process_fake), "Forbidden" in result.output) == (
        1,
        [],
        True,
    )


def test_no_candidate_release_needs_no_object_listing(process_fake: ProcessFake) -> None:
    """Verify only operator-owned and unrendered records give an empty plan with two reads."""
    Cluster(
        records=[
            _record("monitoring", "k8s-monitoring-alloy-logs", 3, owners="Alloy"),
            _record("default", "legacy", 1),
        ]
    ).install(process_fake)

    plan = plan_helm_record_retirement()

    assert (plan, len(process_fake.calls)) == (
        RetirementPlan(
            releases=(), kept=("default/legacy", "monitoring/k8s-monitoring-alloy-logs")
        ),
        2,
    )


# ── The repository: the AppProject and the knowledge base ────────────────────

_HELM_COMMAND = re.compile(r"\bhelm\s+(?:rollback|uninstall|upgrade(?:\s+--install)?)\s+([\w.-]+)")


def _adopted_releases() -> set[str]:
    """The release of each chart source of the Applications in k8s/argocd/apps/."""
    releases: set[str] = set()
    for path in sorted((REPO_ROOT / "k8s" / "argocd" / "apps").glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(doc, dict) or doc.get("kind") != "Application":
                continue
            spec = doc.get("spec") or {}
            sources = spec.get("sources") or [spec.get("source") or {}]
            for source in sources:
                if source.get("chart"):
                    helm = source.get("helm") or {}
                    releases.add(helm.get("releaseName") or doc["metadata"]["name"])
    return releases


def test_no_knowledge_base_page_runs_helm_against_an_adopted_release() -> None:
    """Verify no knowledge base page rolls back, uninstalls or upgrades a release Argo CD renders."""
    adopted = _adopted_releases()
    knowledge_base = REPO_ROOT / "src" / "devops_cli" / "ai" / "knowledge_base"
    found = sorted(
        f"{path.relative_to(REPO_ROOT)}: {match.group(1)}"
        for path in knowledge_base.rglob("*.md")
        for match in _HELM_COMMAND.finditer(path.read_text(encoding="utf-8"))
        if match.group(1) in adopted
    )

    assert ("prometheus" in adopted, found) == (True, [])
