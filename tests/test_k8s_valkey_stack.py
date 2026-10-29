"""Tests verifying Valkey is configured as the key-value store across all Kubernetes stacks."""

import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from kubernetes.utils.quantity import parse_quantity

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
LLM_DIR = K8S_DIR / "llm"
CACHE_SERVICE_HOST = "valkey.llm.svc.cluster.local"
# valkey.conf: "1mb => 1024*1024 bytes".
VALKEY_MB_BYTES = 1024 * 1024


def _document(path: Path, kind: str, name: str) -> dict[str, Any]:
    """Return the document of this kind and name from a multi-document manifest."""
    return next(
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(document, dict)
        and document.get("kind") == kind
        and document["metadata"]["name"] == name
    )


def _container(deployment: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the named container of a Deployment's pod template."""
    containers = deployment["spec"]["template"]["spec"]["containers"]
    return next(container for container in containers if container["name"] == name)


def _secret_env(container: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Return each environment variable a container reads from a Secret, as (Secret, key)."""
    return {
        variable["name"]: (
            variable["valueFrom"]["secretKeyRef"]["name"],
            variable["valueFrom"]["secretKeyRef"]["key"],
        )
        for variable in container.get("env", [])
        if "secretKeyRef" in variable.get("valueFrom", {})
    }


def _password_setup(deployment: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Return the valkey container's script before `exec`, the exec'd command, and the
    emptyDir that holds the config file the script writes."""
    container = _container(deployment, "valkey")
    _shell, _flag, script = container["command"]
    prelude, _, server = script.partition("exec ")
    mount = next(m for m in container["volumeMounts"] if m["mountPath"] == "/run/valkey")
    volume = next(
        v for v in deployment["spec"]["template"]["spec"]["volumes"] if v["name"] == mount["name"]
    )
    return prelude, server, volume["emptyDir"]


def _server_flags(deployment: dict[str, Any]) -> dict[str, str]:
    """Return each `--name value` flag that the valkey container gives valkey-server after its
    config file."""
    _, server, _ = _password_setup(deployment)
    _binary, _config_file, *flags = shlex.split(server)
    return dict(zip(flags[::2], flags[1::2], strict=True))


def _cache_secret() -> tuple[str, str]:
    """Return the name and only key of the Secret that holds the cache Valkey's password."""
    secret = next(s for s in CLUSTER_SECRETS if s.ref == "llm/valkey-auth")
    (entry,) = secret.entries
    return secret.name, entry.key


def _strings(node: Any) -> Iterator[str]:
    """Yield every string value in a parsed YAML document, at any depth."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)


def _extract_images_from_yaml(data: Any) -> list[str]:
    """Recursively extract all image field values from parsed YAML structures."""
    if isinstance(data, list):
        return [image for item in data for image in _extract_images_from_yaml(item)]
    if not isinstance(data, dict):
        return []
    extracted: list[str] = []
    for k, v in data.items():
        if k != "image":
            extracted.extend(_extract_images_from_yaml(v))
        elif isinstance(v, str):
            extracted.append(v)
        elif isinstance(v, dict) and "repository" in v:
            repo = v.get("repository", "")
            tag = v.get("tag", "")
            extracted.append(f"{repo}:{tag}" if tag else str(repo))
    return extracted


def test_argocd_values_specifies_valkey_image() -> None:
    """Verify ArgoCD Helm values.yaml configures Valkey instead of proprietary Redis."""
    values_path = K8S_DIR / "argocd" / "values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "redis" in data, "ArgoCD values.yaml must contain redis configuration block"
    redis_cfg = data["redis"]
    assert redis_cfg.get("enabled") is True, "Redis component must be enabled"
    assert "image" in redis_cfg, "Redis component must explicitly override container image"
    assert redis_cfg["image"]["repository"] == "valkey/valkey"
    assert redis_cfg["image"]["tag"] == "9.1.2-alpine"


def test_llm_valkey_manifest_specification() -> None:
    """Verify LLM stack valkey.yaml defines Valkey deployment and service."""
    valkey_path = K8S_DIR / "llm" / "valkey.yaml"
    assert valkey_path.is_file(), f"Missing {valkey_path}"

    docs = list(yaml.safe_load_all(valkey_path.read_text(encoding="utf-8")))
    assert len(docs) >= 2, f"Expected at least 2 YAML documents in {valkey_path}"

    deployment = next(
        (d for d in docs if isinstance(d, dict) and d.get("kind") == "Deployment"), None
    )
    assert deployment is not None, f"Expected Deployment document in {valkey_path}"

    containers = (
        deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    )
    assert containers, f"Expected container definitions in Deployment in {valkey_path}"
    container = containers[0]
    assert container.get("name") == "valkey"
    assert container.get("image") == "valkey/valkey:9.1.2-alpine"
    assert "exec valkey-server " in container["command"][-1]

    service = next((d for d in docs if isinstance(d, dict) and d.get("kind") == "Service"), None)
    assert service is not None, f"Expected Service document in {valkey_path}"
    assert service.get("metadata", {}).get("name") == "valkey"
    ports = service.get("spec", {}).get("ports", [])
    assert ports
    assert ports[0].get("port") == 6379


def test_open_webui_values_connects_to_valkey() -> None:
    """Verify Open-WebUI Helm values connects websocket manager to Valkey service."""
    webui_values_path = K8S_DIR / "llm" / "values-open-webui.yaml"
    assert webui_values_path.is_file(), f"Missing {webui_values_path}"

    with open(webui_values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "websocket" in data, "values-open-webui.yaml must configure websocket"
    ws = data["websocket"]
    assert ws.get("enabled") is True
    assert "valkey.llm.svc.cluster.local:6379" in ws.get("url", "")
    assert ws.get("redis", {}).get("enabled") is False, "Embedded Redis subchart must be disabled"


def test_no_proprietary_redis_images_in_stack() -> None:
    """Ensure no un-overridden legacy or proprietary Redis images exist in parsed k8s manifests."""
    for yml_file in K8S_DIR.rglob("*.yaml"):
        docs = list(yaml.safe_load_all(yml_file.read_text(encoding="utf-8")))
        for doc in docs:
            images = _extract_images_from_yaml(doc)
            for img in images:
                image_name = img.split("/")[-1].split(":")[0].split("@")[0].lower()
                assert image_name != "redis", (
                    f"Found proprietary redis image {img!r} in {yml_file.relative_to(REPO_ROOT)}"
                )


def test_the_cache_valkey_takes_its_password_from_its_secret_as_the_run_index_does() -> None:
    """The llm cache Valkey requires a password from Secret valkey-auth, written as the run index
    writes its own (#1654).

    It ran with no password, so every pod in llm and monitoring, and Traefik, could read and
    write Open WebUI's state. The script writes the password into a config file on a memory
    volume, never onto valkey-server's command line, where the process list would show it.
    """
    cache = _document(LLM_DIR / "valkey.yaml", "Deployment", "valkey")
    runs = _document(LLM_DIR / "valkey-runs.yaml", "Deployment", "valkey-runs")
    cache_prelude, cache_server, cache_volume = _password_setup(cache)
    runs_prelude, _, runs_volume = _password_setup(runs)
    secret, key = _cache_secret()

    assert _secret_env(_container(cache, "valkey")) == {"VALKEY_PASSWORD": (secret, key)}
    assert (cache_prelude, cache_volume) == (runs_prelude, runs_volume)
    assert cache_server.split() == [
        "valkey-server",
        "/run/valkey/auth.conf",
        "--save",
        '""',
        "--appendonly",
        "no",
        "--dir",
        "/data",
        "--maxmemory",
        "1536mb",
        "--maxmemory-policy",
        "noeviction",
    ]


@pytest.mark.parametrize(
    ("manifest", "name", "bound"),
    [("valkey.yaml", "valkey", "1536mb"), ("valkey-runs.yaml", "valkey-runs", "512mb")],
)
def test_each_llm_valkey_refuses_writes_at_a_memory_bound_below_its_container_limit(
    manifest: str, name: str, bound: str
) -> None:
    """Each Valkey of the llm namespace keeps at most three quarters of its container's memory
    limit as data, and at that bound refuses writes and evicts no key (#711).

    The cache Valkey ran with no bound under a 2048Mi limit, so its growth could end only in an
    OOM kill. maxmemory counts the bytes Valkey allocates, not its resident memory, so the rest
    of the limit holds the allocator's fragmentation and Valkey's own overhead. Open WebUI keeps
    its session pools and token revocations in the cache Valkey, and eviction would drop them.
    """
    deployment = _document(LLM_DIR / manifest, "Deployment", name)
    flags = _server_flags(deployment)
    limit = parse_quantity(_container(deployment, "valkey")["resources"]["limits"]["memory"])

    assert (flags.get("--maxmemory"), flags.get("--maxmemory-policy")) == (bound, "noeviction")
    assert int(bound.removesuffix("mb")) * VALKEY_MB_BYTES <= limit * 3 / 4


def test_the_cache_valkey_exporter_scrapes_with_the_password() -> None:
    """The redis-exporter sidecar sends the password, so `redis_up` stays 1 once Valkey requires it."""
    cache = _document(LLM_DIR / "valkey.yaml", "Deployment", "valkey")

    assert _secret_env(_container(cache, "redis-exporter")) == {"REDIS_PASSWORD": _cache_secret()}


def test_open_webui_sends_the_password_from_the_secret_in_both_redis_urls() -> None:
    """Open WebUI reads the cache Valkey's password from Secret valkey-auth (#1654).

    The chart renders REDIS_URL and WEBSOCKET_REDIS_URL from `websocket.url` before
    `extraEnvVars`, and Kubernetes expands `$(VAR)` only from a variable defined earlier. The
    variables of `envFrom` come before every `env` entry, so the Secret comes in through
    `extraEnvFrom`, and its key is the variable the URL names.
    """
    values = yaml.safe_load((LLM_DIR / "values-open-webui.yaml").read_text(encoding="utf-8"))
    secret, key = _cache_secret()

    assert values["extraEnvFrom"] == [{"secretRef": {"name": secret}}]
    assert values["websocket"]["url"] == f"redis://:$({key})@{CACHE_SERVICE_HOST}:6379/0"


def test_only_open_webui_and_the_metrics_scrapers_reach_the_cache_valkey() -> None:
    """valkey-perimeter admits Open WebUI on 6379 and the monitoring namespace on the exporter's
    port, and lets Valkey dial nothing (#1654).

    llm-default-perimeter admitted every pod in llm, the monitoring namespace and Traefik on
    every port. Policies add up, so llm-default-perimeter leaves valkey out.
    """
    policy = _document(LLM_DIR / "valkey.yaml", "NetworkPolicy", "valkey-perimeter")

    assert policy["spec"] == {
        "podSelector": {"matchLabels": {"app.kubernetes.io/name": "valkey"}},
        "policyTypes": ["Ingress", "Egress"],
        "ingress": [
            {
                "from": [
                    {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "open-webui"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 6379}],
            },
            {
                "from": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "monitoring"}
                        }
                    }
                ],
                "ports": [{"protocol": "TCP", "port": 9121}],
            },
        ],
        "egress": [],
    }


def test_open_webui_is_the_only_workload_that_names_the_cache_valkey() -> None:
    """Only Open WebUI is set up to reach the cache Valkey, so its perimeter admits no other pod (#1654).

    Portkey 1.15.0 reads its cache only from REDIS_CONNECTION_STRING, so its CACHE_STORE and
    REDIS_URL had no effect. LiteLLM reads no LITELLM_REDIS_* variable, and the gateway config
    turns on no cache. Neither connected to Valkey.
    """
    files = sorted(
        {
            path.relative_to(K8S_DIR).as_posix()
            for path in K8S_DIR.rglob("*.yaml")
            for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
            if any(CACHE_SERVICE_HOST in value for value in _strings(document))
        }
    )

    assert files == ["llm/values-open-webui.yaml"]


# devops-cli's cache in the cluster: the Valkey that the Service and the cluster jobs use for their
# embeddings and their threat-intelligence reads (#1655).
DEVOPS_CACHE = "valkey-devops"
DEVOPS_CACHE_MANIFEST = LLM_DIR / "valkey-devops.yaml"
DEVOPS_CACHE_URL = "valkey://valkey-devops.llm.svc.cluster.local:6379/0"
DEVOPS_CONFIGMAP_TEMPLATE = K8S_DIR / "devops" / "configmap.example.yaml"


def _devops_cache_secret() -> tuple[str, str]:
    """Return the name and only key of the Secret that holds the devops cache Valkey's password."""
    secret = next(s for s in CLUSTER_SECRETS if s.ref == "llm/valkey-devops-auth")
    (entry,) = secret.entries
    return secret.name, entry.key


def _keys(node: Any) -> Iterator[str]:
    """Yield every mapping key in a parsed YAML document, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


def test_the_devops_cache_valkey_takes_its_password_from_its_secret_as_the_run_index_does() -> None:
    """devops-cli's cache Valkey requires a password from Secret valkey-devops-auth, written as
    the run index writes its own, and its exporter sends it (#1655).

    The cache Valkey of Open WebUI keeps its state with noeviction, so it can't hold a cache that
    must evict; this Valkey holds only devops-cli's caches.
    """
    cache = _document(DEVOPS_CACHE_MANIFEST, "Deployment", DEVOPS_CACHE)
    runs = _document(LLM_DIR / "valkey-runs.yaml", "Deployment", "valkey-runs")
    cache_prelude, _, cache_volume = _password_setup(cache)
    runs_prelude, _, runs_volume = _password_setup(runs)
    secret, key = _devops_cache_secret()

    assert (
        _secret_env(_container(cache, "valkey")),
        _secret_env(_container(cache, "redis-exporter")),
        (cache_prelude, cache_volume),
    ) == (
        {"VALKEY_PASSWORD": (secret, key)},
        {"REDIS_PASSWORD": (secret, key)},
        (runs_prelude, runs_volume),
    )


def test_the_devops_cache_valkey_evicts_the_least_recently_used_key_at_a_bound_below_its_limit() -> (
    None
):
    """It keeps at most three quarters of its container's memory limit as data, and at that bound
    evicts the least recently used key (#1655).

    It holds caches only, so an evicted key costs one more model request, not a lost state. It
    writes no RDB and no AOF, and a restart starts it empty.
    """
    deployment = _document(DEVOPS_CACHE_MANIFEST, "Deployment", DEVOPS_CACHE)
    flags = _server_flags(deployment)
    limit = parse_quantity(_container(deployment, "valkey")["resources"]["limits"]["memory"])

    assert (flags.get("--maxmemory-policy"), flags.get("--save"), flags.get("--appendonly")) == (
        "allkeys-lru",
        "",
        "no",
    )
    assert int(flags["--maxmemory"].removesuffix("mb")) * VALKEY_MB_BYTES <= limit * 3 / 4


def test_only_the_devops_namespace_and_the_metrics_scrapers_reach_the_devops_cache_valkey() -> None:
    """valkey-devops-perimeter admits namespace devops on 6379 and the monitoring namespace on the
    exporter's port, and lets Valkey dial nothing (#1655).

    A namespace-selector peer with `ports:` is the shape kube-router enforces.
    """
    policy = _document(DEVOPS_CACHE_MANIFEST, "NetworkPolicy", "valkey-devops-perimeter")
    service = _document(DEVOPS_CACHE_MANIFEST, "Service", DEVOPS_CACHE)

    assert policy["spec"] == {
        "podSelector": {"matchLabels": {"app.kubernetes.io/name": DEVOPS_CACHE}},
        "policyTypes": ["Ingress", "Egress"],
        "ingress": [
            {
                "from": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "devops"}
                        }
                    }
                ],
                "ports": [{"protocol": "TCP", "port": 6379}],
            },
            {
                "from": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "monitoring"}
                        }
                    }
                ],
                "ports": [{"protocol": "TCP", "port": 9121}],
            },
        ],
        "egress": [],
    }
    assert (service["spec"]["type"], service["spec"]["ports"]) == (
        "ClusterIP",
        [{"name": "valkey", "port": 6379, "targetPort": 6379}],
    )


def test_the_cluster_jobs_name_the_devops_cache_valkey_and_get_its_password_from_their_secret() -> (
    None
):
    """The devops ConfigMap names the devops cache Valkey and holds no password. Secret devops-cli
    carries the password under the variable that `valkey.password` reads, from the keyring entry
    of Secret valkey-devops-auth, and adopts the live value when the keyring lacks it (#1655)."""
    from devops_cli.config.env import credential
    from devops_cli.k8s.cluster_secrets import KeyringSource, SecretKeyRef

    template = yaml.safe_load(DEVOPS_CONFIGMAP_TEMPLATE.read_text(encoding="utf-8"))
    config = yaml.safe_load(template["data"]["devops-cli.yaml"])
    devops = next(s for s in CLUSTER_SECRETS if s.ref == "devops/devops-cli")
    (variable, *_) = credential("valkey.password").env_vars
    entry = next(e for e in devops.entries if e.key == variable)
    llm = next(s for s in CLUSTER_SECRETS if s.ref == "llm/valkey-devops-auth")
    (llm_entry,) = llm.entries
    secret, key = _devops_cache_secret()

    assert (
        config["valkey"],
        [k for k in _keys(config) if "password" in k.lower()],
        isinstance(entry.source, KeyringSource),
        entry.source == llm_entry.source,
        entry.adopt_from,
    ) == (
        {"url": DEVOPS_CACHE_URL},
        [],
        True,
        True,
        SecretKeyRef("llm", secret, key),
    )
