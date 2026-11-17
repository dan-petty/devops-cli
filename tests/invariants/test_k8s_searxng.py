"""The SearXNG manifests under `k8s/devops/searxng/`: what the committed files must hold (#3924)."""

from __future__ import annotations

import ipaddress
import re
from pathlib import PurePosixPath
from typing import Any

import yaml

from devops_cli.commands.k8s.stack_lifecycle import PRODUCT_MANIFESTS_BY_STACK
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from devops_cli.k8s.searxng_check import OFF_ENGINES
from tests.support.k8s_tree import K8S, manifests, pod_spec
from tests.support.paths import REPO_ROOT

SEARXNG_DIR = K8S / "devops" / "searxng"
DEAD_ENGINES = REPO_ROOT / "tests" / "fixtures" / "searxng" / "engines_that_never_answer.txt"
CLUSTER_DOC = REPO_ROOT / "docs" / "CLUSTER.md"
# The sentence of docs/CLUSTER.md that lists the kept engines, each name in backticks.
DOCUMENTED_ENGINES = re.compile(
    r"\*\*The engines\.\*\* `keep_only` in `searxng-settings` keeps \w+ engines? that need no key: (?P<names>[^.]+)\."
)
# One line of the dead-engines file: the name, then `# <date>: <reason>`.
DEAD_ENGINE_LINE = re.compile(r"^(?P<name>[^#]+?) # \d{4}-\d{2}-\d{2}: \S.*$")
# The pod root, not a path of this host, and the IPv4 wildcard address that the pod binds.
_POD_ROOT = PurePosixPath("/")
BIND_ALL_IPV4 = str(ipaddress.IPv4Address(0))
ROUTE_KINDS = ("Ingress", "IngressRoute", "IngressRouteTCP", "HTTPRoute", "Middleware")


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for _, document in manifests()
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _pod() -> dict[str, Any]:
    spec = pod_spec(_object("Deployment", "searxng"))
    assert spec is not None
    return spec


def _container() -> dict[str, Any]:
    (container,) = _pod()["containers"]
    assert isinstance(container, dict)
    return container


def _settings() -> dict[str, Any]:
    text = _object("ConfigMap", "searxng-settings")["data"]["settings.yml"]
    settings = yaml.safe_load(text)
    assert isinstance(settings, dict)
    return settings


def test_the_pod_meets_pod_security_restricted() -> None:
    """Namespace devops enforces `restricted`, so the pod sets each control that level needs. The
    user is the numeric ID of `searxng` in the image (977), because a named user cannot be checked
    against `runAsNonRoot`. The pod mounts no host path, and its only writable volumes are two
    empty directories."""
    pod = _pod()
    container = _container()
    volume_kinds = {next(iter(set(volume) - {"name"})) for volume in pod["volumes"]}
    writable = {
        mount["mountPath"] for mount in container["volumeMounts"] if not mount.get("readOnly")
    }

    assert (
        pod["securityContext"],
        container["securityContext"],
        volume_kinds,
        writable,
        pod.get("hostNetwork", False) or pod.get("hostPID", False) or pod.get("hostIPC", False),
    ) == (
        {
            "runAsNonRoot": True,
            "runAsUser": 977,
            "runAsGroup": 977,
            "fsGroup": 977,
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        {"configMap", "emptyDir"},
        {str(_POD_ROOT / "tmp"), "/var/cache/searxng"},
        False,
    )


def test_the_environment_holds_the_server_secret_from_the_secret_and_an_ipv4_bind() -> None:
    """The settings file holds no secret: SearXNG reads `SEARXNG_SECRET` before it. The bind is an
    IPv4 address, so a Service reaches the pod whatever the node's IPv6 setting. Granian replaces a
    worker that passes 512 MiB (#4939)."""
    container = _container()

    assert ({item["name"]: item for item in container["env"]}, container.get("envFrom")) == (
        {
            "SEARXNG_SECRET": {
                "name": "SEARXNG_SECRET",
                "valueFrom": {"secretKeyRef": {"name": "searxng", "key": "SEARXNG_SECRET"}},
            },
            "GRANIAN_HOST": {"name": "GRANIAN_HOST", "value": BIND_ALL_IPV4},
            "GRANIAN_WORKERS_MAX_RSS": {"name": "GRANIAN_WORKERS_MAX_RSS", "value": "512"},
        },
        None,
    )


def test_the_secret_row_feeds_the_variable_and_restarts_the_deployment() -> None:
    """The value lives in the keyring alone (no Settings option reads it), and a first push
    generates 64 hex characters."""
    (row,) = [secret for secret in CLUSTER_SECRETS if secret.ref == "devops/searxng"]
    (entry,) = row.entries
    generator = entry.generator
    assert generator is not None

    assert (
        entry.key,
        entry.source.label,
        (generator.encoding, generator.nbytes),
        [str(workload) for workload in row.restarts],
        row.stack,
    ) == (
        "SEARXNG_SECRET",
        "keyring searxng_secret_key",
        ("hex", 32),
        ["deployment/searxng"],
        "devops",
    )


def test_no_route_reaches_the_service_from_outside_the_cluster() -> None:
    """The service has no limiter and no login: no Ingress, Traefik route or tunnel entry names it."""
    routed = [
        (relative, document["kind"])
        for relative, document in manifests()
        if document["kind"] in ROUTE_KINDS and "searxng" in yaml.safe_dump(document)
    ]
    tunnel = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in (K8S / "cloudflared").rglob("*.y*ml")
        if "searxng" in path.read_text(encoding="utf-8")
    ]

    assert (routed, tunnel) == ([], [])


def test_the_settings_turn_off_the_limiter_and_serve_json_to_the_cluster_only() -> None:
    """The limiter needs Valkey and refuses a plain machine client, and the NetworkPolicy replaces
    it. The roadmap Service reads `format=json`, which the default settings leave off. No setting
    holds a secret key or an e-mail address."""
    settings = _settings()
    text = _object("ConfigMap", "searxng-settings")["data"]["settings.yml"]

    assert (
        settings["server"],
        settings["search"],
        settings["outgoing"]["request_timeout"],
        "secret_key" in text,
        "@" in text,
    ) == (
        {"limiter": False, "public_instance": False, "image_proxy": False},
        {"formats": ["html", "json"], "autocomplete": "", "default_lang": "en"},
        5.0,
        False,
        False,
    )


def test_the_settings_keep_only_engines_that_need_no_key() -> None:
    kept = _settings()["use_default_settings"]["engines"]["keep_only"]

    assert kept == [
        "duckduckgo",
        "wikipedia",
        "github",
        "stackoverflow",
        "askubuntu",
        "superuser",
        "arxiv",
        "mdn",
        "docker hub",
    ]


def _dead_engine_names() -> list[str]:
    lines = DEAD_ENGINES.read_text(encoding="utf-8").splitlines()
    return [line.partition(" # ")[0] for line in lines if line]


def test_the_settings_keep_no_engine_that_never_answers() -> None:
    """An engine that gets a challenge page from its site returns no hit and no error, so it only
    costs a request. The file lists each such engine, so a bump or an edit cannot bring one back."""
    kept = _settings()["use_default_settings"]["engines"]["keep_only"]

    assert sorted(set(kept) & set(_dead_engine_names())) == []


def test_the_dead_engines_file_gives_a_date_and_a_reason() -> None:
    """The file begins with `pypi`, and each line has a date and a reason."""
    lines = [line for line in DEAD_ENGINES.read_text(encoding="utf-8").splitlines() if line]

    assert (
        _dead_engine_names()[:1],
        [line for line in lines if not DEAD_ENGINE_LINE.match(line)],
    ) == (["pypi"], [])


def test_the_cluster_document_lists_the_engines_that_the_settings_keep() -> None:
    """docs/CLUSTER.md names the kept engines in one sentence. An edit of `keep_only` that leaves
    the sentence behind fails here."""
    kept = _settings()["use_default_settings"]["engines"]["keep_only"]
    match = DOCUMENTED_ENGINES.search(CLUSTER_DOC.read_text(encoding="utf-8"))
    assert match is not None

    assert sorted(re.findall(r"`([^`]+)`", match["names"])) == sorted(kept)


def test_the_settings_keep_none_of_the_suspended_or_keyed_engines() -> None:
    """The scraping engines of these sites were suspended in October 2026, and the keyed Brave
    engine is not used. A setting that names one, in any form, fails here."""
    settings = _settings()
    kept = settings["use_default_settings"]["engines"]["keep_only"]
    named = {name.split(".")[0].split(" ")[0] for name in kept}
    declared = [engine["name"] for engine in settings.get("engines", [])]

    assert (sorted(named & set(OFF_ENGINES)), declared) == ([], [])


def test_every_file_of_the_service_is_in_both_kustomizations_and_the_deploy_stack() -> None:
    """Argo CD syncs the files that the kustomizations list, and `devops k8s deploy-stack` applies
    the files of `MANIFESTS_BY_STACK`. A file in one list and not in the other is applied by one
    path and not by the other."""
    files = sorted(
        path.name for path in SEARXNG_DIR.glob("*.yaml") if path.name != "kustomization.yaml"
    )
    inner = yaml.safe_load((SEARXNG_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    outer = yaml.safe_load((K8S / "devops" / "kustomization.yaml").read_text(encoding="utf-8"))
    stack = sorted(
        path.name for path in PRODUCT_MANIFESTS_BY_STACK["devops"] if path.parent.name == "searxng"
    )

    assert (sorted(inner["resources"]), "searxng" in outer["resources"], stack) == (
        files,
        True,
        files,
    )
