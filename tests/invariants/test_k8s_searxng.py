"""The SearXNG manifests under `k8s/devops/searxng/`: what the committed files must hold (#3924)."""

from __future__ import annotations

import ipaddress
import re
from pathlib import PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.commands.k8s.stack_lifecycle import MANIFESTS_BY_STACK
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from devops_cli.k8s.image_pins import names_latest
from devops_cli.k8s.searxng_check import OFF_ENGINES
from tests.support.k8s_tree import K8S, manifests, pod_spec
from tests.support.paths import REPO_ROOT

SEARXNG_DIR = K8S / "devops" / "searxng"
ENGINE_NAMES = REPO_ROOT / "tests" / "fixtures" / "searxng" / "default_engine_names.txt"
DEAD_ENGINES = REPO_ROOT / "tests" / "fixtures" / "searxng" / "engines_that_never_answer.txt"
K8S_README = K8S / "README.md"
# The sentence of the README that lists the kept engines, each name in backticks.
README_ENGINES = re.compile(
    r"\*\*The engines\.\*\* `keep_only` in `searxng-settings` keeps \w+ engines? that need no key: (?P<names>[^.]+)\."
)
# One line of the dead-engines file: the name, then `# <date>: <reason>`.
DEAD_ENGINE_LINE = re.compile(r"^(?P<name>[^#]+?) # \d{4}-\d{2}-\d{2}: \S.*$")
IMAGE_PATTERN = re.compile(
    r"^docker\.io/searxng/searxng:(?P<tag>\d{4}\.\d+\.\d+-[0-9a-f]{7,9})@sha256:[0-9a-f]{64}$"
)
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


def _default_engine_names() -> set[str]:
    lines = ENGINE_NAMES.read_text(encoding="utf-8").splitlines()
    return {line for line in lines if line and not line.startswith("#")}


def test_the_image_names_a_release_tag_and_its_digest() -> None:
    """A digest alone hides the release from a reader, and a tag alone can move. The pin names
    both, and Renovate bumps both together."""
    image = _container()["image"]

    assert (bool(IMAGE_PATTERN.match(image)), names_latest(image)) == (True, False)


def test_the_engine_names_file_is_the_one_of_the_pinned_image() -> None:
    """The names file holds the engines of the default settings.yml of the image that the
    Deployment pins. A bump of the image that does not refresh the file fails here."""
    match = IMAGE_PATTERN.match(_container()["image"])
    assert match is not None
    header = ENGINE_NAMES.read_text(encoding="utf-8").splitlines()[0]

    assert f"searxng:{match['tag']}." in header


def test_the_deployment_runs_one_pod_with_no_service_account_token() -> None:
    spec = _object("Deployment", "searxng")["spec"]

    assert (spec["replicas"], _pod()["automountServiceAccountToken"]) == (1, False)


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


def test_the_probes_read_healthz() -> None:
    container = _container()

    assert [
        container[probe]["httpGet"]["path"]
        for probe in ("startupProbe", "readinessProbe", "livenessProbe")
    ] == ["/healthz"] * 3


def test_the_container_has_requests_and_limits() -> None:
    """The memory limit holds a worker at `GRANIAN_WORKERS_MAX_RSS` and the new worker that
    Granian starts in its place, so the slow growth of one worker ends in a replacement, not in
    an OOM kill (#4939)."""
    resources = _container()["resources"]

    assert resources == {
        "requests": {"cpu": "50m", "memory": "256Mi", "ephemeral-storage": "64Mi"},
        "limits": {"cpu": "1", "memory": "1Gi", "ephemeral-storage": "256Mi"},
    }


def test_the_service_is_a_cluster_ip_on_8080_for_the_pod() -> None:
    spec = _object("Service", "searxng")["spec"]

    assert (
        spec["type"],
        spec["selector"],
        [(p["port"], p["targetPort"]) for p in spec["ports"]],
    ) == (
        "ClusterIP",
        {"app.kubernetes.io/name": "searxng"},
        [(8080, 8080)],
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


def test_the_dead_engines_file_gives_a_date_and_a_reason_for_real_engines() -> None:
    """The file begins with `pypi`, and each line has a date and a reason. A name that is not an
    engine of the default settings would make the test above pass for any list."""
    lines = [line for line in DEAD_ENGINES.read_text(encoding="utf-8").splitlines() if line]
    names = _dead_engine_names()

    assert (
        names[:1],
        [line for line in lines if not DEAD_ENGINE_LINE.match(line)],
        sorted(set(names) - _default_engine_names()),
    ) == (["pypi"], [], [])


def test_the_readme_lists_the_engines_that_the_settings_keep() -> None:
    """The README names the kept engines in one sentence. An edit of `keep_only` that leaves the
    sentence behind fails here."""
    kept = _settings()["use_default_settings"]["engines"]["keep_only"]
    match = README_ENGINES.search(K8S_README.read_text(encoding="utf-8"))
    assert match is not None

    assert sorted(re.findall(r"`([^`]+)`", match["names"])) == sorted(kept)


def test_the_configmap_says_why_the_two_log_lines_of_the_start_are_harmless() -> None:
    """The pod logs an ERROR for a missing proxy header and a WARNING for a missing `limiter.toml`.
    Neither matters with the limiter off, and a comment in the file names the source of each, so a
    reader does not chase them or mount a `limiter.toml` to hide them."""
    text = (SEARXNG_DIR / "configmap.yaml").read_text(encoding="utf-8")
    needles = (
        "X-Forwarded-For",
        "searx/botdetection/trusted_proxies.py",
        "limiter.toml",
        "searx/botdetection/config.py",
        "harmless",
    )

    assert [needle for needle in needles if needle not in text] == []


def test_the_settings_keep_none_of_the_suspended_or_keyed_engines() -> None:
    """The scraping engines of these sites were suspended in October 2026, and the keyed Brave
    engine is not used. A setting that names one, in any form, fails here."""
    settings = _settings()
    kept = settings["use_default_settings"]["engines"]["keep_only"]
    named = {name.split(".")[0].split(" ")[0] for name in kept}
    declared = [engine["name"] for engine in settings.get("engines", [])]

    assert (sorted(named & set(OFF_ENGINES)), declared) == ([], [])


def test_every_kept_engine_exists_in_the_default_settings_of_the_pinned_image() -> None:
    kept = _settings()["use_default_settings"]["engines"]["keep_only"]

    assert sorted(set(kept) - _default_engine_names()) == []


def test_the_names_file_holds_the_forbidden_engines_so_the_check_above_means_something() -> None:
    """The forbidden names are real engines of the default settings: the test of the kept
    engines would pass for any list if the names file were empty."""
    names = _default_engine_names()

    assert sorted(name for name in OFF_ENGINES if name not in names) == []


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
        path.name for path in MANIFESTS_BY_STACK["devops"] if path.parent.name == "searxng"
    )

    assert (sorted(inner["resources"]), "searxng" in outer["resources"], stack) == (
        files,
        True,
        files,
    )


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("ConfigMap", "searxng-settings"),
        ("Deployment", "searxng"),
        ("Service", "searxng"),
        ("NetworkPolicy", "searxng-perimeter"),
        ("NetworkPolicy", "searxng-clients"),
    ],
)
def test_each_object_is_in_namespace_devops_and_part_of_the_stack(kind: str, name: str) -> None:
    metadata = _object(kind, name)["metadata"]

    assert (metadata["namespace"], metadata["labels"]["app.kubernetes.io/part-of"]) == (
        "devops",
        "devops-cli-stack",
    )
