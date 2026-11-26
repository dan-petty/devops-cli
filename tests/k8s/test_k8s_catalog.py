"""Tests for `devops k8s catalog` service catalog generation from rendered Applications (#5535)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.dry_run.state import set_dry_run
from devops_cli.k8s.image_pins import application_renders
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_ORIGIN = "https://github.com/example/repo"


def _kustomize(call: ProcessCall) -> ProcessAnswer:
    """`kubectl kustomize <directory>` joins its listed resources or chart output."""
    directory = Path(call.argv[2])
    kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text(encoding="utf-8"))
    resources = [
        (directory / name).read_text(encoding="utf-8") for name in kustomization["resources"]
    ]
    return ProcessAnswer(stdout="---\n".join(resources))


@pytest.fixture(autouse=True)
def _render_answers(process_fake: ProcessFake) -> Iterator[None]:
    """Answer `kubectl kustomize` and git origin lookups locally with no cluster or network."""
    process_fake.answer(("kubectl", "kustomize"), _kustomize)
    process_fake.answer(
        lambda call: "remote.origin.url" in call.argv, ProcessAnswer(stdout=f"{_ORIGIN}.git\n")
    )
    yield


def _write_app(apps_dir: Path, name: str, namespace: str, *, path: str | None = None) -> None:
    """Write a kustomize path Application or Helm chart Application under `argocd/apps/`."""
    if path is not None:
        doc = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": name, "namespace": "argocd"},
            "spec": {
                "project": "default",
                "source": {"repoURL": _ORIGIN, "path": path},
                "destination": {"namespace": namespace},
            },
        }
    else:
        doc = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": name, "namespace": "argocd"},
            "spec": {
                "project": "default",
                "sources": [
                    {
                        "repoURL": "https://charts.example.com",
                        "chart": name,
                        "targetRevision": "1.2.3",
                    }
                ],
                "destination": {"namespace": namespace},
            },
        }
    (apps_dir / f"{name}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _write_kustomization(folder: Path, files: dict[str, str]) -> None:
    """Write YAML resources and their `kustomization.yaml` into `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    names = sorted(files)
    for name, body in files.items():
        (folder / name).write_text(body, encoding="utf-8")
    (folder / "kustomization.yaml").write_text(
        yaml.safe_dump({"resources": names}, sort_keys=False), encoding="utf-8"
    )


def _chart_deployment_stream(name: str, namespace: str) -> str:
    """Simulated `helm template` output for a chart Application."""
    return (
        f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {name}\n"
        f"  namespace: {namespace}\n  labels:\n    app: {name}\nspec:\n  replicas: 1\n"
        "  selector:\n    matchLabels:\n      app: "
        f"{name}\n  template:\n    metadata:\n      labels:\n        app: {name}\n"
        "    spec:\n      containers:\n        - name: server\n"
        "          image: ghcr.io/example/chart-app:1.2.3@sha256:" + "a" * 64 + "\n"
    )


def _seed_base_fixture(
    root: Path,
    process_fake: ProcessFake,
    *,
    extra_workloads: str = "",
    catalog_toml: str | None = None,
    slo_service: str = "roadmap-service",
    dashboard_workload: str = "roadmap-service",
    chart_stream: str | None = None,
) -> Path:
    """Create a synthetic environment tree with kustomize + chart apps, SLO, and dashboard."""
    k8s_dir = root / "k8s"
    apps = k8s_dir / "argocd" / "apps"
    apps.mkdir(parents=True)

    _write_app(apps, "devops", "devops", path="k8s/devops")
    _write_app(apps, "ingress", "devops", path="k8s/ingress")
    _write_app(apps, "metrics-store", "monitoring", path=None)

    process_fake.answer(
        ("helm", "template", "metrics-store"),
        ProcessAnswer(
            stdout=chart_stream or _chart_deployment_stream("metrics-store", "monitoring")
        ),
    )

    devops_manifests = (
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: roadmap-service\n"
        "  namespace: devops\n  labels:\n    app.kubernetes.io/name: roadmap-service\n"
        "spec:\n  replicas: 1\n  strategy:\n    type: RollingUpdate\n"
        "  template:\n    metadata:\n      labels:\n        app.kubernetes.io/name: roadmap-service\n"
        "    spec:\n      priorityClassName: devops-high\n      runtimeClassName: gvisor\n"
        "      terminationGracePeriodSeconds: 30\n      containers:\n        - name: service\n"
        "          image: ghcr.io/example/service:1.0.0\n"
        "          resources:\n            requests:\n              cpu: 100m\n              memory: 256Mi\n"
        "            limits:\n              memory: 512Mi\n"
        "          livenessProbe:\n            httpGet:\n              path: /healthz\n              port: 8000\n"
        "          readinessProbe:\n            httpGet:\n              path: /readyz\n              port: 8000\n"
        "---\napiVersion: v1\nkind: Service\nmetadata:\n  name: roadmap-service\n  namespace: devops\n"
        "spec:\n  selector:\n    app.kubernetes.io/name: roadmap-service\n"
        "  ports:\n    - port: 8000\n"
        "---\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: worker\n  namespace: devops\n"
        "spec:\n  replicas: 1\n  template:\n    metadata:\n      labels:\n        app: worker\n"
        "    spec:\n      containers:\n        - name: worker\n          image: ghcr.io/example/worker:1.0.0\n"
        "---\napiVersion: v1\nkind: PersistentVolumeClaim\nmetadata:\n  name: roadmap-data\n"
        "  namespace: devops\nspec:\n  storageClassName: local-path\n  accessModes: [ReadWriteOnce]\n"
        "  resources:\n    requests:\n      storage: 5Gi\n"
        "---\napiVersion: scheduling.k8s.io/v1\nkind: PriorityClass\nmetadata:\n  name: devops-high\nvalue: 1000\n"
        "---\napiVersion: node.k8s.io/v1\nkind: RuntimeClass\nmetadata:\n  name: gvisor\nhandler: runsc\n"
        "---\napiVersion: storage.k8s.io/v1\nkind: StorageClass\nmetadata:\n  name: local-path\n"
        "provisioner: rancher.io/local-path\nreclaimPolicy: Retain\nvolumeBindingMode: WaitForFirstConsumer\n"
    )
    if extra_workloads:
        devops_manifests += "---\n" + extra_workloads
    _write_kustomization(k8s_dir / "devops", {"resources.yaml": devops_manifests})

    ingress_manifest = (
        "apiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n"
        "  name: roadmap-ui\n  namespace: devops\n  annotations:\n"
        "    gethomepage.dev/description: Roadmap Service UI\n"
        "spec:\n  rules:\n    - host: hooks.example.com\n      http:\n        paths:\n"
        "          - path: /\n            pathType: Prefix\n            backend:\n"
        "              service:\n                name: roadmap-service\n                port:\n                  number: 8000\n"
    )
    _write_kustomization(k8s_dir / "ingress", {"ingress.yaml": ingress_manifest})

    slos_dir = k8s_dir / "devops" / "monitoring" / "slos"
    slos_dir.mkdir(parents=True)
    (slos_dir / "rounds.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "prometheus/v1",
                "service": slo_service,
                "slos": [
                    {
                        "name": "rounds",
                        "objective": 99,
                        "description": "Good rounds ratio",
                        "sli": {
                            "events": {
                                "error_query": 'sum(error_total{window="{{.window}}"})',
                                "total_query": 'sum(total_count{window="{{.window}}"})',
                            }
                        },
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    dashboards_dir = k8s_dir / "monitoring" / "dashboards"
    dashboards_dir.mkdir(parents=True)
    (dashboards_dir / "services.toml").write_text(
        f'[[service]]\nuid = "devops-roadmap-service"\ntitle = "Roadmap Service"\n'
        f'description = "Golden signals"\nnamespace = "devops"\nworkload = "{dashboard_workload}"\n',
        encoding="utf-8",
    )

    default_catalog = (
        '[[service]]\nname = "roadmap-service"\napplications = ["devops"]\n'
        'workloads = ["roadmap-service"]\ntier = 1\ndata_class = "owned"\n\n'
        '[[service]]\nname = "worker"\napplications = ["devops"]\n'
        'workloads = ["worker"]\ndescription = "Background worker description"\n'
        'tier = 2\ndata_class = "none"\n\n'
        '[[service]]\nname = "metrics-store"\napplications = ["metrics-store"]\n'
        'tier = 3\ndata_class = "telemetry"\n'
    )
    (k8s_dir / "catalog.toml").write_text(
        catalog_toml if catalog_toml is not None else default_catalog,
        encoding="utf-8",
    )
    return k8s_dir


def test_application_renders_is_public_and_catalog_writes_markdown(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """`devops k8s catalog` uses public `application_renders` and writes `<k8s-dir>/CATALOG.md`."""
    assert callable(application_renders)
    k8s_dir = _seed_base_fixture(tmp_path, process_fake)

    result = cli("k8s", "catalog", "--k8s-dir", str(k8s_dir))

    assert result.exit_code == 0
    catalog_text = (k8s_dir / "CATALOG.md").read_text(encoding="utf-8")
    lines = [line for line in catalog_text.splitlines() if line.strip()]
    assert lines[0] == "# Service Catalog"
    assert lines[1] == "Generated by `uv run devops k8s catalog`. Do not edit this file."
    for heading in (
        "## Services",
        "## SLOs",
        "## Workloads by Application",
        "## Stores",
        "## Cluster classes",
    ):
        assert heading in catalog_text
    assert "Roadmap Service UI" in catalog_text
    assert "Background worker description" in catalog_text
    assert "devops-roadmap-service" in catalog_text
    assert "99%" in catalog_text
    assert "28d" in catalog_text
    assert "Good rounds ratio" in catalog_text
    assert "local-path" in catalog_text
    assert "devops-high" in catalog_text
    assert "gvisor" in catalog_text

    # Tier 3 `metrics-store` has neither UI annotation, catalog description, SLO, nor dashboard.
    metrics_row = next(line for line in lines if "| metrics-store |" in line)
    assert "| none |" in metrics_row


def test_k8s_catalog_supports_globs_operator_workloads_and_multi_ui_descriptions(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """Glob `workloads`, CloudNativePG `Cluster`, `Mattermost`, multiple sorted UI annotations, and
    tier 1 missing SLO/dashboard all succeed."""
    extra = (
        "apiVersion: apps/v1\nkind: DaemonSet\nmetadata:\n  name: ollama-48gib\n"
        "  namespace: llm\nspec:\n  template:\n    spec:\n      containers:\n        - name: ollama\n"
        "          image: ollama/ollama:0.5.0\n"
        "---\napiVersion: apps/v1\nkind: DaemonSet\nmetadata:\n  name: ollama-64gib\n"
        "  namespace: llm\nspec:\n  template:\n    spec:\n      containers:\n        - name: ollama\n"
        "          image: ollama/ollama:0.5.0\n"
        "---\napiVersion: postgresql.cnpg.io/v1\nkind: Cluster\nmetadata:\n  name: llm-gateway-db\n"
        "  namespace: llm\nspec:\n  instances: 2\n  storage:\n    storageClass: local-path\n    size: 10Gi\n"
        "---\napiVersion: installation.mattermost.com/v1beta1\nkind: Mattermost\nmetadata:\n"
        "  name: mattermost\n  namespace: mattermost\nspec:\n  replicas: 1\n"
        "  ingress:\n    annotations:\n      gethomepage.dev/description: Mattermost Team Chat\n"
        "---\napiVersion: traefik.io/v1alpha1\nkind: IngressRoute\nmetadata:\n  name: a-roadmap-api\n"
        "  namespace: devops\n  annotations:\n    gethomepage.dev/description: API Docs UI\n"
        "spec:\n  routes:\n    - match: Host(`api.example.com`)\n      kind: Rule\n"
        "      services:\n        - name: roadmap-service\n          port: 8000\n"
    )
    catalog_toml = (
        '[[service]]\nname = "roadmap-service"\napplications = ["devops"]\n'
        'workloads = ["roadmap-service"]\ntier = 1\ndata_class = "owned"\n\n'
        '[[service]]\nname = "worker"\napplications = ["devops"]\n'
        'workloads = ["worker"]\ntier = 1\ndata_class = "none"\n\n'
        '[[service]]\nname = "model-tiers"\napplications = ["devops"]\n'
        'workloads = ["ollama-*"]\ndescription = "Ollama tiers"\ntier = 2\ndata_class = "derived"\n\n'
        '[[service]]\nname = "gateway-db"\napplications = ["devops"]\n'
        'workloads = ["llm-gateway-db"]\ndescription = "Gateway DB"\ntier = 2\ndata_class = "owned"\n\n'
        '[[service]]\nname = "mattermost"\napplications = ["devops"]\n'
        'workloads = ["mattermost"]\ntier = 3\ndata_class = "owned"\n\n'
        '[[service]]\nname = "metrics-store"\napplications = ["metrics-store"]\n'
        'tier = 3\ndata_class = "telemetry"\n'
    )
    k8s_dir = _seed_base_fixture(
        tmp_path, process_fake, extra_workloads=extra, catalog_toml=catalog_toml
    )

    result = cli("k8s", "catalog", "--k8s-dir", str(k8s_dir))

    assert result.exit_code == 0
    text = (k8s_dir / "CATALOG.md").read_text(encoding="utf-8")
    roadmap_row = next(line for line in text.splitlines() if "| roadmap-service |" in line)
    assert "API Docs UI<br>Roadmap Service UI" in roadmap_row
    worker_row = next(line for line in text.splitlines() if "| worker |" in line)
    assert "| none |" in worker_row
    assert "Mattermost Team Chat" in text
    assert "ollama-48gib" in text
    assert "ollama-64gib" in text
    assert "llm-gateway-db" in text


def test_k8s_catalog_validation_failures_exit_1_with_object_names(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """Duplicate descriptions, unclaimed workloads, missing workloads, unknown SLOs, and unknown
    dashboards each exit 1 naming the offending object."""
    dup_catalog = (
        '[[service]]\nname = "roadmap-service"\napplications = ["devops"]\n'
        'workloads = ["roadmap-service"]\ndescription = "Duplicate"\ntier = 1\ndata_class = "owned"\n\n'
        '[[service]]\nname = "worker"\napplications = ["devops"]\n'
        'workloads = ["worker"]\ntier = 2\ndata_class = "none"\n\n'
        '[[service]]\nname = "metrics-store"\napplications = ["metrics-store"]\n'
        'tier = 3\ndata_class = "telemetry"\n'
    )
    dup_dir = _seed_base_fixture(tmp_path / "dup", process_fake, catalog_toml=dup_catalog)
    dup_res = cli("k8s", "catalog", "--k8s-dir", str(dup_dir))
    assert (dup_res.exit_code, "roadmap-service" in dup_res.output) == (1, True)

    unclaimed_extra = (
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: open-webui\n"
        "  namespace: llm\nspec:\n  replicas: 1\n  template:\n    spec:\n"
        "      containers:\n        - name: webui\n          image: ghcr.io/open-webui/open-webui:0.5\n"
    )
    unclaimed_dir = _seed_base_fixture(
        tmp_path / "unclaimed", process_fake, extra_workloads=unclaimed_extra
    )
    unclaimed_res = cli("k8s", "catalog", "--k8s-dir", str(unclaimed_dir))
    assert (unclaimed_res.exit_code, "open-webui" in unclaimed_res.output) == (1, True)

    missing_catalog = (
        '[[service]]\nname = "roadmap-service"\napplications = ["devops"]\n'
        'workloads = ["roadmap-service", "gone"]\ntier = 1\ndata_class = "owned"\n\n'
        '[[service]]\nname = "worker"\napplications = ["devops"]\n'
        'workloads = ["worker"]\ntier = 2\ndata_class = "none"\n\n'
        '[[service]]\nname = "metrics-store"\napplications = ["metrics-store"]\n'
        'tier = 3\ndata_class = "telemetry"\n'
    )
    missing_dir = _seed_base_fixture(
        tmp_path / "missing", process_fake, catalog_toml=missing_catalog
    )
    missing_res = cli("k8s", "catalog", "--k8s-dir", str(missing_dir))
    assert (missing_res.exit_code, "gone" in missing_res.output) == (1, True)

    unknown_slo_dir = _seed_base_fixture(tmp_path / "bad_slo", process_fake, slo_service="unknown")
    unknown_slo_res = cli("k8s", "catalog", "--k8s-dir", str(unknown_slo_dir))
    assert (unknown_slo_res.exit_code, "unknown" in unknown_slo_res.output) == (1, True)

    unknown_dash_dir = _seed_base_fixture(
        tmp_path / "bad_dash", process_fake, dashboard_workload="ghost"
    )
    unknown_dash_res = cli("k8s", "catalog", "--k8s-dir", str(unknown_dash_dir))
    assert (unknown_dash_res.exit_code, "ghost" in unknown_dash_res.output) == (1, True)


def test_k8s_catalog_check_json_and_dry_run_modes(
    tmp_path: Path, web: WebFake, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """`--check` catches stale files and passes when current, `--format json` emits structured
    sections, and `--dry-run` makes zero requests or subprocess calls while listing charts."""
    k8s_dir = _seed_base_fixture(tmp_path, process_fake)

    (k8s_dir / "CATALOG.md").write_text("# stale\n", encoding="utf-8")
    stale_check = cli("k8s", "catalog", "--check", "--k8s-dir", str(k8s_dir))
    assert stale_check.exit_code == 1

    generate_res = cli("k8s", "catalog", "--k8s-dir", str(k8s_dir))
    assert generate_res.exit_code == 0

    fresh_check = cli("k8s", "catalog", "--check", "--k8s-dir", str(k8s_dir))
    assert fresh_check.exit_code == 0

    json_res = cli("k8s", "catalog", "--format", "json", "--k8s-dir", str(k8s_dir))
    assert json_res.exit_code == 0
    payload = json.loads(json_res.output)
    assert set(payload) >= {"services", "slos", "workloads", "stores", "cluster_classes"}
    assert [svc["name"] for svc in payload["services"]] == [
        "roadmap-service",
        "worker",
        "metrics-store",
    ]

    process_fake.calls.clear()
    try:
        dry_res = cli("k8s", "catalog", "--dry-run", "--k8s-dir", str(k8s_dir))
    finally:
        set_dry_run(False)

    assert (
        dry_res.exit_code,
        web.sent,
        process_fake.calls,
        "metrics-store" in dry_res.output,
        {"https://charts.example.com"} <= set(dry_res.output.split()),
    ) == (0, [], [], True, True)


def test_k8s_catalog_says_when_the_tree_holds_no_slo_folder(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """The SLO specs of the product are not in the environment tree, so a catalog of a tree with
    no SLO folder names the folder that it did not find, and keeps its JSON output whole
    (#7290)."""
    k8s_dir = _seed_base_fixture(tmp_path, process_fake)
    with_folder = cli("k8s", "catalog", "--k8s-dir", str(k8s_dir))
    shutil.rmtree(k8s_dir / "devops" / "monitoring")

    without = cli("k8s", "catalog", "--format", "json", "--k8s-dir", str(k8s_dir))

    assert (
        "devops/monitoring/slos" in with_folder.stderr,
        without.exit_code,
        "devops/monitoring/slos" in "".join(without.stderr.split()),
        json.loads(without.stdout)["slos"],
    ) == (False, 0, True, [])


def test_k8s_catalog_covers_statefulset_cronjob_backup_and_error_branches(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """CronJob, StatefulSet volumeClaimTemplates, ScheduledBackup, defaultBackend Ingress, empty
    SLOs/stores/classes, and CLI/TOML error branches behave consistently."""
    extra = (
        "apiVersion: batch/v1\nkind: CronJob\nmetadata:\n  name: cleanup\n  namespace: devops\n"
        "spec:\n  schedule: '0 * * * *'\n  concurrencyPolicy: Forbid\n  jobTemplate:\n    spec:\n"
        "      template:\n        metadata:\n          labels:\n            app: cleanup\n"
        "        spec:\n          containers:\n            - name: job\n              image: busybox:1.37\n"
        "---\napiVersion: apps/v1\nkind: StatefulSet\nmetadata:\n  name: cache\n  namespace: devops\n"
        "spec:\n  replicas: 1\n  updateStrategy:\n    type: RollingUpdate\n  template:\n"
        "    metadata:\n      labels:\n        app: cache\n    spec:\n      containers:\n"
        "        - name: redis\n          image: redis:7.4\n  volumeClaimTemplates:\n"
        "    - metadata:\n        name: data\n      spec:\n        storageClassName: local-path\n"
        "        accessModes: [ReadWriteOnce]\n        resources:\n          requests:\n"
        "            storage: 2Gi\n"
        "---\napiVersion: postgresql.cnpg.io/v1\nkind: Cluster\nmetadata:\n  name: pg-main\n"
        "  namespace: devops\nspec:\n  instances: 1\n  imageName: ghcr.io/cloudnative-pg/postgresql:17\n"
        "  resources:\n    requests:\n      cpu: 250m\n      memory: 512Mi\n    limits:\n"
        "      memory: 1Gi\n  storage:\n    storageClass: local-path\n    size: 10Gi\n"
        "---\napiVersion: postgresql.cnpg.io/v1\nkind: ScheduledBackup\nmetadata:\n"
        "  name: pg-nightly\n  namespace: devops\nspec:\n  schedule: '0 0 * * *'\n"
        "  cluster:\n    name: pg-main\n"
        "---\napiVersion: scheduling.k8s.io/v1\nkind: PriorityClass\nmetadata:\n  name: cluster-default\n"
        "value: 500\nglobalDefault: true\n"
        "---\napiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: default-ing\n"
        "  namespace: devops\n  annotations:\n    gethomepage.dev/description: Default UI\n"
        "spec:\n  defaultBackend:\n    service:\n      name: roadmap-service\n      port:\n        number: 8000\n"
        "  rules:\n    - host: orphan.example.com\n      http:\n        paths:\n          - path: /\n"
        "            pathType: Prefix\n            backend:\n              service:\n                name: missing-svc\n"
        "                port:\n                  number: 80\n"
    )
    chart_with_pvc = (
        _chart_deployment_stream("metrics-store", "monitoring")
        + "---\napiVersion: v1\nkind: PersistentVolumeClaim\nmetadata:\n  name: tsdb-data\n"
        "  namespace: monitoring\nspec:\n  storageClassName: local-path\n  accessModes: [ReadWriteOnce]\n"
        "  resources:\n    requests:\n      storage: 20Gi\n"
    )
    catalog_toml = (
        '[[service]]\nname = "roadmap-service"\napplications = ["devops"]\n'
        'workloads = ["roadmap-service"]\ntier = 1\ndata_class = "owned"\n\n'
        '[[service]]\nname = "worker"\napplications = ["devops"]\n'
        'workloads = ["worker", "cleanup", "cache", "pg-main"]\ndescription = "Workers and DB"\n'
        'tier = 2\ndata_class = "owned"\n\n'
        '[[service]]\nname = "metrics-store"\napplications = ["metrics-store"]\n'
        'tier = 3\ndata_class = "telemetry"\n'
    )
    k8s_dir = _seed_base_fixture(
        tmp_path / "full",
        process_fake,
        extra_workloads=extra,
        catalog_toml=catalog_toml,
        chart_stream=chart_with_pvc,
    )
    ok_res = cli("k8s", "catalog", "--k8s-dir", str(k8s_dir))
    assert ok_res.exit_code == 0
    full_md = (k8s_dir / "CATALOG.md").read_text(encoding="utf-8")
    assert "cache/data" in full_md
    assert "pg-nightly" in full_md
    assert "globalDefault=true" in full_md
    assert "Default UI" in full_md
    assert "tsdb-data" in full_md

    # Invalid CLI format exits 1 cleanly.
    bad_fmt = cli("k8s", "catalog", "--format", "xml", "--k8s-dir", str(k8s_dir))
    assert (bad_fmt.exit_code, "xml" in bad_fmt.output) == (1, True)

    # Catalog error branches: missing catalog.toml, malformed TOML, wrong table type, invalid tier, missing app.
    no_toml_dir = tmp_path / "no_toml" / "k8s"
    no_toml_dir.mkdir(parents=True)
    assert cli("k8s", "catalog", "--k8s-dir", str(no_toml_dir)).exit_code == 1

    (no_toml_dir / "catalog.toml").write_text("[invalid toml", encoding="utf-8")
    assert cli("k8s", "catalog", "--k8s-dir", str(no_toml_dir)).exit_code == 1

    (no_toml_dir / "catalog.toml").write_text("title = 'no-array'\n", encoding="utf-8")
    assert cli("k8s", "catalog", "--k8s-dir", str(no_toml_dir)).exit_code == 1

    (no_toml_dir / "catalog.toml").write_text(
        '[[service]]\nname = "x"\napplications = ["a"]\ntier = 9\ndata_class = "owned"\n',
        encoding="utf-8",
    )
    assert cli("k8s", "catalog", "--k8s-dir", str(no_toml_dir)).exit_code == 1

    bad_app_dir = _seed_base_fixture(
        tmp_path / "bad_app",
        process_fake,
        catalog_toml='[[service]]\nname = "ghost"\napplications = ["missing-app"]\ntier = 1\ndata_class = "owned"\n',
    )
    assert cli("k8s", "catalog", "--k8s-dir", str(bad_app_dir)).exit_code == 1

    # Empty optional sections: no SLOs, no dashboards, no stores, no cluster classes.
    minimal_root = tmp_path / "minimal" / "k8s"
    apps_dir = minimal_root / "argocd" / "apps"
    apps_dir.mkdir(parents=True)
    _write_app(apps_dir, "tiny", "tiny", path="k8s/tiny")
    _write_kustomization(
        minimal_root / "tiny",
        {
            "deploy.yaml": (
                "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: tiny\n  namespace: tiny\n"
                "spec:\n  template:\n    spec:\n      containers: []\n"
            )
        },
    )
    (minimal_root / "catalog.toml").write_text(
        '[[service]]\nname = "tiny"\napplications = ["tiny"]\ntier = 3\ndata_class = "none"\n',
        encoding="utf-8",
    )
    min_res = cli("k8s", "catalog", "--k8s-dir", str(minimal_root))
    assert min_res.exit_code == 0
    min_md = (minimal_root / "CATALOG.md").read_text(encoding="utf-8")
    assert "No Sloth SLO specs defined." in min_md
    assert "No stores defined." in min_md
    assert "No cluster classes defined." in min_md
