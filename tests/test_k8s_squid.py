"""Unit and integration tests for Kubernetes Squid Caching Proxy & Observability."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
SQUID_DIR = K8S_DIR / "squid"
DOCKER_DIR = SQUID_DIR / "docker"


def test_squid_manifest_files_exist() -> None:
    """Verify all expected Squid Kubernetes manifests and docker assets exist."""
    expected_files = [
        SQUID_DIR / "configmap.yaml",
        SQUID_DIR / "pvc.yaml",
        SQUID_DIR / "ca-configmap.yaml",
        SQUID_DIR / "deployment.yaml",
        SQUID_DIR / "service.yaml",
        SQUID_DIR / "networkpolicy.yaml",
        SQUID_DIR / "kustomization.yaml",
        DOCKER_DIR / "Dockerfile",
        DOCKER_DIR / "entrypoint.sh",
        REPO_ROOT / "docs" / "squid-failover-and-observability.md",
    ]
    for file_path in expected_files:
        assert file_path.is_file(), f"Expected file does not exist: {file_path}"


def test_squid_kustomization_and_namespace_registration() -> None:
    """Verify root k8s/kustomization.yaml and namespaces.yaml register squid."""
    root_kust = yaml.safe_load((K8S_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    assert "squid" in root_kust.get("resources", [])

    squid_kust = yaml.safe_load((SQUID_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    assert squid_kust.get("namespace") == "squid"
    assert "configmap.yaml" in squid_kust.get("resources", [])
    assert "deployment.yaml" in squid_kust.get("resources", [])
    assert "service.yaml" in squid_kust.get("resources", [])

    namespaces_doc = list(
        yaml.safe_load_all((K8S_DIR / "namespaces.yaml").read_text(encoding="utf-8"))
    )
    squid_ns = [ns for ns in namespaces_doc if ns and ns.get("metadata", {}).get("name") == "squid"]
    assert len(squid_ns) == 1
    assert squid_ns[0]["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "baseline"


def test_squid_conf_caching_and_observability_directives() -> None:
    """Verify squid.conf tuning for 100GB model layers, SSL-Bump, LFUDA, and JSON logging."""
    cm_doc = yaml.safe_load((SQUID_DIR / "configmap.yaml").read_text(encoding="utf-8"))
    assert cm_doc.get("kind") == "ConfigMap"
    conf_text = cm_doc.get("data", {}).get("squid.conf", "")

    # Massive 100GB Layer Support
    assert "maximum_object_size 100 GB" in conf_text
    assert "range_offset_limit -1" in conf_text
    assert "quick_abort_min -1" in conf_text
    assert "read_ahead_gap 64 MB" in conf_text
    assert "cache_dir ufs /var/spool/squid/cache 200000 16 256" in conf_text

    # Memory & LFUDA Eviction Tuning (Protection against storage exhaustion)
    assert "cache_mem 2048 MB" in conf_text
    assert "maximum_object_size_in_memory 32 MB" in conf_text
    assert "cache_replacement_policy heap LFUDA" in conf_text
    assert "cache_swap_low 85" in conf_text
    assert "cache_swap_high 92" in conf_text

    # SSL-Bump & Content-Addressable Blobs
    assert "ssl-bump" in conf_text
    assert "sslcrtd_program /usr/lib/squid/security_file_certgen" in conf_text
    assert "ssl_bump peek step1" in conf_text
    assert "ssl_bump bump all" in conf_text
    assert "/v2/.*/blobs/sha256:" in conf_text
    assert ".*/blobs/sha256/.*" in conf_text
    assert r".*\.r2\.cloudflarestorage\.com/.*/blobs/sha256/.*" in conf_text
    assert r".*\.r2\.cloudflarestorage\.com/.* 1440 20% 10080" in conf_text
    assert "ollama-cache\\.local/blobs/sha256/" in conf_text

    # Store-ID & URL Rewriting for In-Cluster Workloads & Presigned S3/R2 Layers
    assert "store_id_program /usr/lib/squid/storeid_file_rewrite" in conf_text
    assert "url_rewrite_program /usr/bin/perl /etc/squid/url_rewrite.pl" in conf_text
    assert "ssl_bump splice to_localnet" in conf_text
    assert "storeid_rewrite.conf" in cm_doc.get("data", {})
    assert "url_rewrite.pl" in cm_doc.get("data", {})

    # Observability & Structured JSON Logging
    assert "strip_query_terms on" in conf_text
    assert "logformat json_k8s" in conf_text
    assert "access_log /var/log/squid/access.log json_k8s" in conf_text
    assert "acl manager proto cache_object" in conf_text
    assert "http_access allow manager localhost" in conf_text
    assert "snmp_port 3401" in conf_text
    assert "snmp_access allow snmppublic localnet" in conf_text


def test_squid_deployment_and_sidecar_exporter() -> None:
    """Verify deployment includes squid-exporter sidecar, probes, and Prometheus annotations."""
    dep_doc = yaml.safe_load((SQUID_DIR / "deployment.yaml").read_text(encoding="utf-8"))
    assert dep_doc.get("kind") == "Deployment"
    spec = dep_doc["spec"]
    assert spec["replicas"] == 1
    assert spec["strategy"]["type"] == "Recreate"

    pod_metadata = spec["template"]["metadata"]
    annotations = pod_metadata.get("annotations", {})
    assert annotations.get("prometheus.io/scrape") == "true"
    assert annotations.get("prometheus.io/port") == "9301"

    pod_spec = spec["template"]["spec"]
    containers = pod_spec.get("containers", [])
    container_names = [c["name"] for c in containers]
    assert "squid" in container_names
    assert "squid-exporter" in container_names

    # Squid container verification with tcpSocket probes
    squid_c = next(c for c in containers if c["name"] == "squid")
    assert squid_c.get("livenessProbe") is not None
    assert squid_c.get("readinessProbe") is not None
    assert squid_c["livenessProbe"].get("tcpSocket", {}).get("port") == 3128
    assert squid_c["readinessProbe"].get("tcpSocket", {}).get("port") == 3128
    assert squid_c["readinessProbe"]["failureThreshold"] == 2
    assert squid_c["readinessProbe"]["periodSeconds"] == 5

    # Config volume mounts for squid.conf, storeid, and url rewriter
    mount_paths = {
        vm["mountPath"]: vm["subPath"] for vm in squid_c.get("volumeMounts", []) if "subPath" in vm
    }
    assert mount_paths.get("/etc/squid/squid.conf") == "squid.conf"
    assert mount_paths.get("/etc/squid/storeid_rewrite.conf") == "storeid_rewrite.conf"
    assert mount_paths.get("/etc/squid/url_rewrite.pl") == "url_rewrite.pl"

    # Exporter sidecar verification
    exporter_c = next(c for c in containers if c["name"] == "squid-exporter")
    exporter_ports = [p["containerPort"] for p in exporter_c.get("ports", [])]
    assert 9301 in exporter_ports
    assert "-listen" in exporter_c.get("command", [])

    # Storage node affinity verification (prefers high-capacity storage node)
    affinity = pod_spec.get("affinity", {})
    node_aff = affinity.get("nodeAffinity", {})
    preferred = node_aff.get("preferredDuringSchedulingIgnoredDuringExecution", [])
    has_storage_affinity = any(
        "storage-node" in expr.get("values", [])
        for p in preferred
        for expr in p.get("preference", {}).get("matchExpressions", [])
    )
    assert has_storage_affinity is True

    # Squid CA volume must be non-optional (fail-fast security requirement)
    squid_ca_vol = next(v for v in pod_spec.get("volumes", []) if v["name"] == "squid-ca")
    assert squid_ca_vol.get("secret", {}).get("optional") is False


def test_squid_pvc_and_service_spec() -> None:
    """Verify 250Gi PVC and Service ports for proxy and metrics."""
    pvc_doc = yaml.safe_load((SQUID_DIR / "pvc.yaml").read_text(encoding="utf-8"))
    assert pvc_doc.get("kind") == "PersistentVolumeClaim"
    assert pvc_doc["spec"]["resources"]["requests"]["storage"] == "250Gi"
    assert "ReadWriteOnce" in pvc_doc["spec"]["accessModes"]

    svc_doc = yaml.safe_load((SQUID_DIR / "service.yaml").read_text(encoding="utf-8"))
    assert svc_doc.get("kind") == "Service"
    ports = {p["name"]: p["port"] for p in svc_doc["spec"]["ports"]}
    assert ports.get("http-proxy") == 3128
    assert ports.get("metrics") == 9301


def test_ollama_daemonset_proxy_integration() -> None:
    """Verify ollama-daemonset.yaml configures HTTP_PROXY, HTTPS_PROXY, and squid-ca mount."""
    docs = list(
        yaml.safe_load_all((K8S_DIR / "llm" / "ollama-daemonset.yaml").read_text(encoding="utf-8"))
    )
    daemonset_doc = next(d for d in docs if d and d.get("kind") == "DaemonSet")
    containers = daemonset_doc["spec"]["template"]["spec"]["containers"]
    ollama_c = next(c for c in containers if c["name"] == "ollama")

    env_map = {e["name"]: e["value"] for e in ollama_c.get("env", []) if "value" in e}
    assert env_map.get("HTTP_PROXY") == "http://squid.squid.svc.cluster.local:3128"
    assert env_map.get("HTTPS_PROXY") == "http://squid.squid.svc.cluster.local:3128"
    assert env_map.get("SSL_CERT_DIR") == "/etc/ssl/certs:/etc/ssl/squid-ca"
    assert "localhost" in env_map.get("NO_PROXY", "")

    volume_mounts = {vm["name"]: vm["mountPath"] for vm in ollama_c.get("volumeMounts", [])}
    assert volume_mounts.get("squid-ca-cert") == "/etc/ssl/squid-ca"

    volumes = {v["name"]: v for v in daemonset_doc["spec"]["template"]["spec"]["volumes"]}
    assert "squid-ca-cert" in volumes
    assert volumes["squid-ca-cert"].get("configMap", {}).get("optional") is False

    # Node-local NVMe hostPath storage contract
    assert "ollama-data" in volumes
    ollama_data_vol = volumes["ollama-data"]
    assert ollama_data_vol.get("hostPath", {}).get("path") == "/var/lib/ollama"
    assert ollama_data_vol.get("hostPath", {}).get("type") == "DirectoryOrCreate"


def test_squid_networkpolicy_security_and_ca_distribution() -> None:
    """Verify NetworkPolicy SSRF protections and cross-namespace CA distribution."""
    np_doc = yaml.safe_load((SQUID_DIR / "networkpolicy.yaml").read_text(encoding="utf-8"))
    assert np_doc.get("kind") == "NetworkPolicy"

    egress_rules = np_doc["spec"].get("egress", [])
    external_rule = next(
        r for r in egress_rules if any("ipBlock" in to_item for to_item in r.get("to", []))
    )
    ip_block = next(to_item["ipBlock"] for to_item in external_rule["to"] if "ipBlock" in to_item)
    assert ip_block["cidr"] == "0.0.0.0/0"
    assert "169.254.169.254/32" in ip_block["except"]

    # Verify CA configmaps in both squid and llm namespaces
    squid_ca_doc = yaml.safe_load((SQUID_DIR / "ca-configmap.yaml").read_text(encoding="utf-8"))
    assert squid_ca_doc["metadata"]["name"] == "squid-ca-cert"
    assert squid_ca_doc["metadata"]["namespace"] == "squid"
    assert "squid-ca.pem" in squid_ca_doc["data"]

    llm_ca_doc = yaml.safe_load((K8S_DIR / "llm" / "ca-configmap.yaml").read_text(encoding="utf-8"))
    assert llm_ca_doc["metadata"]["name"] == "squid-ca-cert"
    assert llm_ca_doc["metadata"]["namespace"] == "llm"
    assert llm_ca_doc["data"]["squid-ca.pem"] == squid_ca_doc["data"]["squid-ca.pem"]

    # Verify entrypoint.sh avoids recursive chown on restart and checks for pre-provisioned CA
    entrypoint_text = (DOCKER_DIR / "entrypoint.sh").read_text(encoding="utf-8")
    assert ".initialized" in entrypoint_text
    assert "/etc/squid/ssl-ca" in entrypoint_text
    assert "FATAL: Pre-provisioned Root CA missing" in entrypoint_text
