"""Mattermost Team Edition on CloudNativePG tests (#1391).

Each test reads committed files only. It starts no program and reaches no cluster or network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
MATTERMOST_DIR = K8S_DIR / "mattermost"
KEEP = "Prune=false,Delete=false"


def _yaml(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _documents(path: Path) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]


def test_mattermost_directory_manifests_exist() -> None:
    """Verify all required manifests and values files exist in k8s/mattermost/."""
    expected_files = (
        "cloudnative-pg-values.yaml",
        "mattermost-operator-values.yaml",
        "database.yaml",
        "files-pvc.yaml",
        "mattermost.yaml",
        "podmonitor.yaml",
        "networkpolicy.yaml",
        "kustomization.yaml",
    )
    for filename in expected_files:
        path = MATTERMOST_DIR / filename
        assert path.is_file(), f"Missing file: {path}"


def test_kustomization_resources() -> None:
    """Verify k8s/mattermost/kustomization.yaml lists exactly the required resources."""
    kust = _yaml(MATTERMOST_DIR / "kustomization.yaml")
    assert kust.get("resources") == [
        "networkpolicy.yaml",
        "database.yaml",
        "files-pvc.yaml",
        "mattermost.yaml",
        "podmonitor.yaml",
    ]


def test_cloudnative_pg_values() -> None:
    """Verify cloudnative-pg Helm values configure monitoring, security context, and resources."""
    values = _yaml(MATTERMOST_DIR / "cloudnative-pg-values.yaml")
    monitoring = values.get("monitoring", {})
    assert (
        monitoring.get("podMonitorEnabled"),
        monitoring.get("grafanaDashboard", {}).get("create"),
    ) == (True, True)

    resources = values.get("resources", {})
    assert (
        resources.get("requests", {}).get("cpu"),
        resources.get("requests", {}).get("memory"),
        resources.get("limits", {}).get("cpu"),
        resources.get("limits", {}).get("memory"),
    ) == ("50m", "128Mi", "500m", "512Mi")

    pod_sec = values.get("podSecurityContext", {})
    assert (
        pod_sec.get("runAsNonRoot"),
        pod_sec.get("seccompProfile", {}).get("type"),
    ) == (True, "RuntimeDefault")

    sec = values.get("containerSecurityContext") or values.get("securityContext", {})
    assert (
        sec.get("allowPrivilegeEscalation"),
        sec.get("readOnlyRootFilesystem"),
        sec.get("capabilities", {}).get("drop"),
    ) == (False, True, ["ALL"])


def test_mattermost_operator_values() -> None:
    """Verify mattermost-operator Helm values configure restricted security contexts."""
    values = _yaml(MATTERMOST_DIR / "mattermost-operator-values.yaml")
    pod_sec = values.get("podSecurityContext", {})
    assert (
        pod_sec.get("runAsNonRoot"),
        pod_sec.get("seccompProfile", {}).get("type"),
    ) == (True, "RuntimeDefault")

    sec = values.get("securityContext", {})
    assert (
        sec.get("allowPrivilegeEscalation"),
        sec.get("readOnlyRootFilesystem"),
        sec.get("capabilities", {}).get("drop"),
    ) == (False, True, ["ALL"])


def test_database_manifest() -> None:
    """Verify database.yaml configures CloudNativePG Cluster named mattermost-db."""
    doc = _yaml(MATTERMOST_DIR / "database.yaml")
    assert (
        doc.get("apiVersion"),
        doc.get("kind"),
        doc.get("metadata", {}).get("name"),
        doc.get("metadata", {}).get("namespace"),
        doc.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/sync-options"),
    ) == ("postgresql.cnpg.io/v1", "Cluster", "mattermost-db", "mattermost", KEEP)

    spec = doc.get("spec", {})
    assert (
        spec.get("instances"),
        spec.get("imageName"),
        spec.get("storage", {}).get("storageClass"),
        spec.get("storage", {}).get("size"),
        spec.get("enableSuperuserAccess"),
    ) == (1, "ghcr.io/cloudnative-pg/postgresql:17.2", "local-path", "10Gi", False)

    initdb = spec.get("bootstrap", {}).get("initdb", {})
    assert (
        initdb.get("database"),
        initdb.get("owner"),
        initdb.get("secret", {}).get("name"),
    ) == ("mattermost", "mattermost", "mattermost-db")

    resources = spec.get("resources", {})
    assert (
        resources.get("requests", {}).get("cpu"),
        resources.get("requests", {}).get("memory"),
        str(resources.get("limits", {}).get("cpu")),
        resources.get("limits", {}).get("memory"),
    ) in (("100m", "256Mi", "1", "1Gi"), ("100m", "256Mi", "1000m", "1Gi"))


def test_files_pvc_manifest() -> None:
    """Verify files-pvc.yaml defines PersistentVolumeClaim mattermost-files."""
    doc = _yaml(MATTERMOST_DIR / "files-pvc.yaml")
    assert (
        doc.get("apiVersion"),
        doc.get("kind"),
        doc.get("metadata", {}).get("name"),
        doc.get("metadata", {}).get("namespace"),
        doc.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/sync-options"),
    ) == ("v1", "PersistentVolumeClaim", "mattermost-files", "mattermost", KEEP)

    spec = doc.get("spec", {})
    assert (
        spec.get("accessModes"),
        spec.get("storageClassName"),
        spec.get("resources", {}).get("requests", {}).get("storage"),
    ) == (["ReadWriteOnce"], "local-path", "10Gi")


def test_mattermost_custom_resource() -> None:
    """Verify mattermost.yaml defines installation.mattermost.com/v1beta1 Mattermost."""
    doc = _yaml(MATTERMOST_DIR / "mattermost.yaml")
    assert (
        doc.get("apiVersion"),
        doc.get("kind"),
        doc.get("metadata", {}).get("name"),
        doc.get("metadata", {}).get("namespace"),
        doc.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/sync-options"),
    ) == ("installation.mattermost.com/v1beta1", "Mattermost", "mattermost", "mattermost", KEEP)

    spec = doc.get("spec", {})
    assert (
        spec.get("image"),
        spec.get("version"),
        spec.get("replicas"),
        spec.get("deploymentTemplate", {}).get("deploymentStrategyType"),
        spec.get("database", {}).get("external", {}).get("secret"),
        spec.get("fileStore", {}).get("externalVolume", {}).get("volumeClaimName"),
    ) == (
        "mattermost/mattermost-team-edition",
        "11.7.11",
        1,
        "Recreate",
        "mattermost-db",
        "mattermost-files",
    )

    ingress = spec.get("ingress", {})
    assert (
        ingress.get("enabled"),
        ingress.get("host"),
        ingress.get("ingressClass"),
        ingress.get("annotations", {}).get("traefik.ingress.kubernetes.io/router.entrypoints"),
    ) == (True, "mattermost.example.com", "traefik", "web")
    assert "tlsSecret" not in ingress

    pod_sec = spec.get("podTemplate", {}).get("securityContext", {})
    assert (
        pod_sec.get("runAsUser"),
        pod_sec.get("runAsGroup"),
        pod_sec.get("fsGroup"),
        pod_sec.get("runAsNonRoot"),
        pod_sec.get("seccompProfile", {}).get("type"),
    ) == (2000, 2000, 2000, True, "RuntimeDefault")

    resources = spec.get("scheduling", {}).get("resources", {})
    assert (
        resources.get("requests", {}).get("cpu"),
        resources.get("requests", {}).get("memory"),
        str(resources.get("limits", {}).get("cpu")),
        resources.get("limits", {}).get("memory"),
    ) in (("100m", "512Mi", "2", "2Gi"), ("100m", "512Mi", "2000m", "2Gi"))

    env_list = spec.get("mattermostEnv", [])
    env_map = {item["name"]: item.get("value") for item in env_list}
    assert env_map == {
        "MM_LOGSETTINGS_ENABLEDIAGNOSTICS": "false",
        "MM_SERVICESETTINGS_ENABLESECURITYFIXALERT": "false",
        "MM_PLUGINSETTINGS_ENABLEUPLOADS": "false",
        "MM_METRICSSETTINGS_ENABLE": "false",
        "MM_CLUSTERSETTINGS_ENABLE": "false",
        "MM_FILESETTINGS_MAXFILESIZE": "99000000",
        "MM_TEAMSETTINGS_ENABLEOPENSERVER": "false",
        "MM_LOGSETTINGS_ENABLEFILE": "false",
        "MM_SERVICESETTINGS_ENABLELOCALMODE": "true",
        "MM_SERVICESETTINGS_ALLOWEDUNTRUSTEDINTERNALCONNECTIONS": "roadmap-service.devops.svc.cluster.local",
        "MM_EMAILSETTINGS_SENDPUSHNOTIFICATIONS": "false",
        "MM_PLUGINSETTINGS_ENABLEREMOTEMARKETPLACE": "false",
    }


def test_podmonitor_manifest() -> None:
    """Verify podmonitor.yaml defines PodMonitor for CloudNativePG cluster."""
    doc = _yaml(MATTERMOST_DIR / "podmonitor.yaml")
    assert (
        doc.get("apiVersion"),
        doc.get("kind"),
        doc.get("metadata", {}).get("name"),
        doc.get("metadata", {}).get("namespace"),
    ) == ("monitoring.coreos.com/v1", "PodMonitor", "mattermost-db", "mattermost")

    spec = doc.get("spec", {})
    assert (
        spec.get("selector", {}).get("matchLabels", {}).get("cnpg.io/cluster"),
        spec.get("podMetricsEndpoints"),
    ) == ("mattermost-db", [{"port": "metrics"}])


def test_networkpolicy_manifests() -> None:
    """Verify networkpolicy.yaml defines default perimeter, db api, and roadmap service egress policies."""
    docs = _documents(MATTERMOST_DIR / "networkpolicy.yaml")
    assert len(docs) == 3

    perimeter, db_api, roadmap_egress = docs

    # 1. Perimeter policy
    assert (
        perimeter.get("apiVersion"),
        perimeter.get("kind"),
        perimeter.get("metadata", {}).get("name"),
        perimeter.get("metadata", {}).get("namespace"),
        perimeter.get("spec", {}).get("podSelector"),
        perimeter.get("spec", {}).get("policyTypes"),
    ) == (
        "networking.k8s.io/v1",
        "NetworkPolicy",
        "mattermost-default-perimeter",
        "mattermost",
        {},
        ["Ingress", "Egress"],
    )

    # Ingress peers: Traefik on 8065, intra-namespace, cnpg-system on 8000 and 5432, monitoring on 9187, alertmanager on 8065, argocd-notifications-controller on 8065
    ingress_rules = perimeter.get("spec", {}).get("ingress", [])
    assert len(ingress_rules) == 6

    # 2. DB API egress policy
    assert (
        db_api.get("apiVersion"),
        db_api.get("kind"),
        db_api.get("metadata", {}).get("name"),
        db_api.get("metadata", {}).get("namespace"),
        db_api.get("spec", {}).get("podSelector", {}).get("matchLabels", {}).get("cnpg.io/cluster"),
        db_api.get("spec", {}).get("policyTypes"),
    ) == (
        "networking.k8s.io/v1",
        "NetworkPolicy",
        "mattermost-db-api",
        "mattermost",
        "mattermost-db",
        ["Egress"],
    )

    # 3. Roadmap service egress policy (#1395)
    assert (
        roadmap_egress.get("apiVersion"),
        roadmap_egress.get("kind"),
        roadmap_egress.get("metadata", {}).get("name"),
        roadmap_egress.get("metadata", {}).get("namespace"),
        roadmap_egress.get("spec", {})
        .get("podSelector", {})
        .get("matchLabels", {})
        .get("app.kubernetes.io/name"),
        roadmap_egress.get("spec", {}).get("policyTypes"),
    ) == (
        "networking.k8s.io/v1",
        "NetworkPolicy",
        "mattermost-roadmap-service",
        "mattermost",
        "mattermost",
        ["Egress"],
    )
