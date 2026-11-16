"""The self-hosted Renovate manifests under `k8s/devops/renovate/`: what the committed files must
hold (#4905, ADR 0027)."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.commands.k8s.stack_lifecycle import PRODUCT_MANIFESTS_BY_STACK
from devops_cli.config.env import env_var_for_option
from devops_cli.core.paths import is_forbidden_system_path
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    OPTIONAL_FEATURE_SECRETS,
    KeyringSource,
    SettingSource,
)
from tests.support.k8s_tree import K8S, manifests, pod_spec
from tests.support.paths import REPO_ROOT

RENOVATE_DIR = K8S / "devops" / "renovate"
SERVICE_IMAGE = "ghcr.io/dan-petty/devops-cli/service"
IMAGE_PATTERN = re.compile(
    r"^ghcr\.io/renovatebot/renovate:(?P<tag>\d+\.\d+\.\d+)@sha256:[0-9a-f]{64}$"
)
# GitHub ends an installation token one hour after it mints it.
TOKEN_LIFE_SECONDS = 3600
# The Renovate user of the image (`ubuntu`, 12021). A name cannot be checked against runAsNonRoot.
RENOVATE_USER = 12021
TOKEN_PATH = PurePosixPath("/token/github-token")
# The image paths that Renovate writes at run time, each on a volume, so that the root file
# system stays read-only (Trivy KSV-0014). `/var/lib/containerbase` is not one of them: root owns
# it with mode 0755, and it holds the tool markers that the image build wrote.
# The temp folder of the pod, not a path of this host.
POD_TMP = str(PurePosixPath("/") / "tmp")
WRITABLE_PATHS = {POD_TMP, "/opt/containerbase", "/home/ubuntu", "/cache", "/report"}
SETTINGS = (
    "renovate.github_app_id",
    "renovate.github_app_installation_id",
    "renovate.github_app_private_key",
)
ADR = REPO_ROOT / "docs" / "adr" / "0027-dependency-updates-come-from-self-hosted-renovate.md"


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for _, document in manifests()
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _pod() -> dict[str, Any]:
    spec = pod_spec(_object("CronJob", "renovate"))
    assert spec is not None
    return spec


def _containers() -> dict[str, dict[str, Any]]:
    """Each init container and container of the pod, by name."""
    pod = _pod()
    return {c["name"]: c for c in [*pod["initContainers"], *pod["containers"]]}


def _env(container: dict[str, Any]) -> dict[str, str]:
    return {item["name"]: item["value"] for item in container.get("env", []) if "value" in item}


def _config_files() -> dict[str, str]:
    return _object("ConfigMap", "renovate-config")["data"]


def _config() -> dict[str, Any]:
    config: dict[str, Any] = json.loads(_config_files()["config.json"])
    return config


def _mounts(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {mount["mountPath"]: mount for mount in container.get("volumeMounts", [])}


def _volumes() -> dict[str, dict[str, Any]]:
    return {volume["name"]: volume for volume in _pod()["volumes"]}


def test_renovate_runs_the_pinned_release_with_its_own_entrypoint() -> None:
    """The image names a release tag and the digest of its index. The command is the entrypoint of
    the image, which runs the containerbase start before Renovate."""
    renovate = _containers()["renovate"]

    assert (
        bool(IMAGE_PATTERN.match(renovate["image"])),
        renovate["imagePullPolicy"],
        renovate["command"],
        renovate["args"],
    ) == (True, "IfNotPresent", ["/usr/local/sbin/renovate-entrypoint.sh"], ["renovate"])


def test_the_cronjob_runs_every_two_hours_in_utc_and_one_run_at_a_time() -> None:
    """`Forbid` keeps one pod on the ReadWriteOnce cache claim. A run that changed GitHub never
    runs again on its own."""
    cronjob = _object("CronJob", "renovate")["spec"]
    job = cronjob["jobTemplate"]["spec"]

    assert (
        cronjob["schedule"],
        cronjob["timeZone"],
        cronjob["concurrencyPolicy"],
        cronjob["startingDeadlineSeconds"],
        cronjob.get("suspend", False),
        job["backoffLimit"],
        job["ttlSecondsAfterFinished"],
        job["activeDeadlineSeconds"],
        _pod()["restartPolicy"],
    ) == ("17 */2 * * *", "Etc/UTC", "Forbid", 600, False, 0, 86400, 3000, "Never")


def test_the_timeouts_nest_inside_the_life_of_the_token() -> None:
    """A child process of Renovate stops before the Job deadline, and the Job stops before GitHub
    ends the token that the init container wrote at the start of the pod."""
    child_seconds = _config()["executionTimeout"] * 60
    deadline = _object("CronJob", "renovate")["spec"]["jobTemplate"]["spec"][
        "activeDeadlineSeconds"
    ]

    assert (child_seconds, child_seconds < deadline < TOKEN_LIFE_SECONDS) == (900, True)


def test_only_the_token_init_container_reads_the_secret() -> None:
    """The App's private key reaches the token init container only. Renovate runs the commands of
    `postUpgradeTasks` that a repository names, so its container holds no Secret."""
    containers = _containers()

    assert (
        {name: c["envFrom"] for name, c in containers.items() if c.get("envFrom")},
        [name for name, c in containers.items() if "secretKeyRef" in json.dumps(c.get("env"))],
        [name for name, volume in _volumes().items() if "secret" in volume],
    ) == ({"token": [{"secretRef": {"name": "renovate", "optional": True}}]}, [], [])


def test_the_token_init_container_writes_the_file_that_the_config_reads() -> None:
    """The Service image writes the token to an emptyDir that both containers mount. The path is
    outside the system folders that the writer refuses, and Renovate mounts it read-only."""
    containers = _containers()
    token = containers["token"]
    renovate_mount = _mounts(containers["renovate"])[str(TOKEN_PATH.parent)]
    token_mount = _mounts(token)[str(TOKEN_PATH.parent)]

    assert (
        token["image"],
        token["imagePullPolicy"],
        token["args"],
        token_mount["name"],
        token_mount.get("readOnly", False),
        renovate_mount["name"],
        renovate_mount["readOnly"],
        set(_volumes()[token_mount["name"]]) - {"name"},
        is_forbidden_system_path(TOKEN_PATH),
        f"readFileSync('{TOKEN_PATH}', 'utf8')" in _config_files()["config.js"],
    ) == (
        SERVICE_IMAGE,
        "IfNotPresent",
        ["gh", "app-token", "--app", "renovate", "--write", str(TOKEN_PATH)],
        "token",
        False,
        "token",
        True,
        {"emptyDir"},
        False,
        True,
    )


def test_the_token_init_container_has_a_writable_home_and_data_folder() -> None:
    """The Service image runs here as the Renovate user, so the token file is the Renovate
    user's. That user cannot write the home of the image, so the home is an emptyDir."""
    token = _containers()["token"]
    writable = {path for path, mount in _mounts(token).items() if not mount.get("readOnly")}
    env = _env(token)

    assert (
        writable,
        env["DEVOPS_CLI_DATA_DIR"].startswith("/home/devops/"),
        token.get("securityContext", {}).get("runAsUser", _pod()["securityContext"]["runAsUser"]),
    ) == ({"/home/devops", POD_TMP, str(TOKEN_PATH.parent)}, True, RENOVATE_USER)


def test_the_pod_meets_pod_security_restricted() -> None:
    """Namespace devops enforces `restricted`. The pod runs as the Renovate user of the image,
    mounts no host path and no token, and each container has a read-only root."""
    pod = _pod()
    controls = {name: container["securityContext"] for name, container in _containers().items()}
    volume_kinds = {next(iter(set(volume) - {"name"})) for volume in pod["volumes"]}

    assert (
        pod["securityContext"],
        pod["automountServiceAccountToken"],
        set(controls),
        all(
            control
            == {
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]},
            }
            for control in controls.values()
        ),
        volume_kinds,
        pod.get("hostNetwork", False) or pod.get("hostPID", False) or pod.get("hostIPC", False),
    ) == (
        {
            "runAsNonRoot": True,
            "runAsUser": RENOVATE_USER,
            "runAsGroup": RENOVATE_USER,
            "fsGroup": RENOVATE_USER,
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        False,
        {"seed", "token", "renovate"},
        True,
        {"configMap", "emptyDir", "persistentVolumeClaim"},
        False,
    )


def test_the_seed_init_container_copies_the_image_folders_that_renovate_writes() -> None:
    """`/opt/containerbase` and `/home/ubuntu` hold what the image build wrote, and Renovate
    installs tools there at run time. A plain emptyDir would hide the build files, so the seed
    copies both folders into the volume that Renovate then mounts on the same paths."""
    containers = _containers()
    seed = containers["seed"]
    renovate_mounts = _mounts(containers["renovate"])
    (seed_mount,) = seed["volumeMounts"]
    seeded = {
        path: mount["subPath"]
        for path, mount in renovate_mounts.items()
        if mount["name"] == seed_mount["name"]
    }

    assert (
        seed["image"] == containers["renovate"]["image"],
        seed["command"],
        seeded,
        {path for path, mount in renovate_mounts.items() if not mount.get("readOnly")},
    ) == (
        True,
        [
            "cp",
            "-a",
            "--no-preserve=ownership",
            "--parents",
            "/opt/containerbase",
            "/home/ubuntu",
            seed_mount["mountPath"],
        ],
        {"/opt/containerbase": "opt/containerbase", "/home/ubuntu": "home/ubuntu"},
        WRITABLE_PATHS,
    )


def test_each_container_has_requests_and_limits_and_each_empty_dir_a_size() -> None:
    containers = _containers().values()
    sizes = {
        name: volume["emptyDir"].get("sizeLimit")
        for name, volume in _volumes().items()
        if "emptyDir" in volume
    }

    assert (
        [
            c["name"]
            for c in containers
            if not {"cpu", "memory"} <= set(c["resources"].get("requests", {}))
            or not {"cpu", "memory"} <= set(c["resources"].get("limits", {}))
        ],
        [name for name, size in sizes.items() if not size],
    ) == ([], [])


def test_the_config_runs_every_repository_of_the_installation_and_onboards_none_yet() -> None:
    """The App installation is the scope, so no repository list is copied here. Only devops-cli
    holds a config today. The others get no onboarding pull request until #4913 turns
    `onboarding` on, and then the onboarding config extends the shared preset."""
    config = _config()

    assert (
        config["platform"],
        config["autodiscover"],
        config["onboarding"],
        config["requireConfig"],
        config["onboardingConfig"]["extends"],
        "token" in config,
        "gitAuthor" in config,
    ) == (
        "github",
        True,
        False,
        "required",
        ["github>dan-petty/devops-cli//.github/renovate/base"],
        False,
        False,
    )


def test_the_caches_are_on_the_claim_and_the_report_on_a_volume() -> None:
    config = _config()
    renovate_mounts = _mounts(_containers()["renovate"])
    cache = renovate_mounts[config["cacheDir"]]
    report = renovate_mounts[str(PurePosixPath(config["reportPath"]).parent)]

    assert (
        config["binarySource"],
        PurePosixPath(config["containerbaseDir"]).is_relative_to(config["cacheDir"]),
        config["repositoryCache"],
        config["reportType"],
        config["persistRepoData"],
        _volumes()[cache["name"]]["persistentVolumeClaim"]["claimName"],
        set(_volumes()[report["name"]]) - {"name"},
    ) == ("install", True, "enabled", "file", False, "renovate-cache", {"emptyDir"})


def test_the_cache_claim_survives_a_prune_and_a_delete() -> None:
    pvc = _object("PersistentVolumeClaim", "renovate-cache")

    assert (
        pvc["metadata"]["annotations"]["argocd.argoproj.io/sync-options"],
        pvc["spec"]["accessModes"],
        pvc["spec"]["storageClassName"],
        pvc["spec"]["resources"]["requests"]["storage"],
    ) == ("Prune=false,Delete=false", ["ReadWriteOnce"], "local-path", "5Gi")


def _post_upgrade_commands() -> list[str]:
    """Each command of `postUpgradeTasks` in the Renovate config of this repository."""
    files = [
        REPO_ROOT / ".github" / "renovate.json",
        *(REPO_ROOT / ".github" / "renovate").glob("*.json"),
    ]
    commands: list[str] = []
    stack: list[Any] = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            commands.extend((node.get("postUpgradeTasks") or {}).get("commands", []))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return commands


def test_each_allowed_command_is_anchored_and_matches_a_command_of_the_repository() -> None:
    """Renovate runs a command of `postUpgradeTasks` only when an `allowedCommands` regex matches
    it, and never in a shell. Each regex holds a whole command line, and each command of the
    repository config has a regex (#4896; #4902 adds its own)."""
    config = _config()
    patterns = config["allowedCommands"]
    commands = _post_upgrade_commands()

    assert (
        config["allowShellExecutorForPostUpgradeCommands"],
        [p for p in patterns if not (p.startswith("^") and p.endswith("$"))],
        [c for c in commands if not any(re.fullmatch(p, c) for p in patterns)],
        [p for p in patterns if not any(re.fullmatch(p, c) for c in commands)],
        len(commands) >= 4,
    ) == (False, [], [], [], True)


def test_the_environment_starts_with_a_lookup_dry_run_and_no_metadata_service() -> None:
    """#4909 removes the dry run after it measures the first run."""
    env = _env(_containers()["renovate"])
    config_mount = _mounts(_containers()["renovate"])[
        str(PurePosixPath(env["RENOVATE_CONFIG_FILE"]).parent)
    ]

    assert (
        env["RENOVATE_DRY_RUN"],
        env["RENOVATE_USE_CLOUD_METADATA_SERVICES"],
        env["RENOVATE_X_SQLITE_PACKAGE_CACHE"],
        env["OSV_OFFLINE_DATABASE_FORMAT"],
        env["OSV_OFFLINE_MAX_AGE"],
        PurePosixPath(env["RENOVATE_CONFIG_FILE"]).name,
        _volumes()[config_mount["name"]]["configMap"]["name"],
        config_mount["readOnly"],
    ) == ("lookup", "false", "true", "split", "6h", "config.js", "renovate-config", True)


def test_the_config_uses_no_hosted_mend_service() -> None:
    """The hosted Mend Renovate app stays off these repositories (#4893 owner step 6), and this
    instance sends nothing to a Mend service."""
    text = "\n".join(_config_files().values()).lower()

    assert ("mend.io" in text, "mergeconfidence" in text) == (False, False)


def test_the_secret_row_holds_the_two_ids_and_the_key_under_their_variables() -> None:
    """The keys are the variables of the settings, so the init container takes the Secret with
    `envFrom`. A run reads the token at its start, so no workload restarts. Renovate is an optional
    feature: a push with no Renovate settings skips the three keys and does not fail the stack."""
    (row,) = (secret for secret in CLUSTER_SECRETS if secret.ref == "devops/renovate")
    entries = {entry.key: entry for entry in row.entries}
    app_id, installation_id, private_key = SETTINGS

    assert (
        row.stack,
        row.restarts,
        list(entries),
        entries[env_var_for_option(app_id) or ""].source,
        entries[env_var_for_option(installation_id) or ""].source,
        entries[env_var_for_option(private_key) or ""].source,
        [entry.key for entry in row.entries if entry.required],
        row.ref in OPTIONAL_FEATURE_SECRETS,
    ) == (
        "devops",
        (),
        [env_var_for_option(setting) for setting in SETTINGS],
        SettingSource(app_id),
        SettingSource(installation_id),
        KeyringSource.for_credential(private_key),
        [],
        True,
    )


def test_argo_cd_ignores_the_pushed_secret_as_an_orphan() -> None:
    documents = yaml.safe_load_all(
        (K8S / "argocd" / "apps" / "projects.yaml").read_text(encoding="utf-8")
    )
    (homelab,) = (d for d in documents if d and d["metadata"]["name"] == "homelab")

    assert {"group": "", "kind": "Secret", "name": "renovate"} in homelab["spec"][
        "orphanedResources"
    ]["ignore"]


def test_every_file_is_in_both_kustomizations_and_the_deploy_stack() -> None:
    """Argo CD syncs the files that the kustomizations list, and `devops k8s deploy-stack` applies
    the files of `PRODUCT_MANIFESTS_BY_STACK`."""
    files = sorted(
        path.name for path in RENOVATE_DIR.glob("*.yaml") if path.name != "kustomization.yaml"
    )
    inner = yaml.safe_load((RENOVATE_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    outer = yaml.safe_load((K8S / "devops" / "kustomization.yaml").read_text(encoding="utf-8"))
    stack = sorted(
        path.name for path in PRODUCT_MANIFESTS_BY_STACK["devops"] if path.parent.name == "renovate"
    )

    assert (sorted(inner["resources"]), "renovate" in outer["resources"], stack) == (
        files,
        True,
        files,
    )


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("ConfigMap", "renovate-config"),
        ("CronJob", "renovate"),
        ("PersistentVolumeClaim", "renovate-cache"),
        ("NetworkPolicy", "renovate-perimeter"),
    ],
)
def test_each_object_is_in_namespace_devops_and_part_of_the_stack(kind: str, name: str) -> None:
    metadata = _object(kind, name)["metadata"]

    assert (
        metadata["namespace"],
        metadata["labels"]["app.kubernetes.io/name"],
        metadata["labels"]["app.kubernetes.io/part-of"],
    ) == ("devops", "renovate", "devops-cli-stack")


def test_the_perimeter_admits_no_ingress_and_only_dns_otel_and_public_https() -> None:
    """Renovate runs repository commands, so its pod reaches no gateway, no Valkey, no Qdrant and
    no API server: only CoreDNS, the OTLP/HTTP port of the collector and public TCP 443, with the
    ranges that `devops-default-perimeter` removes."""
    default = _object("NetworkPolicy", "devops-default-perimeter")["spec"]
    spec = _object("NetworkPolicy", "renovate-perimeter")["spec"]
    (public,) = (rule for rule in default["egress"] if "ipBlock" in rule["to"][0])

    assert (
        spec["podSelector"],
        spec["policyTypes"],
        spec.get("ingress"),
        spec["egress"],
        "renovate" in default["podSelector"]["matchExpressions"][0]["values"],
    ) == (
        {"matchLabels": {"app.kubernetes.io/name": "renovate"}},
        ["Ingress", "Egress"],
        None,
        [
            default["egress"][0],
            {
                "to": [
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "otel"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 4318}],
            },
            public,
        ],
        True,
    )


def _license_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if "Renovate" in line and "AGPL-3.0-only" in line
    ]


def test_the_records_of_the_license_exception_agree() -> None:
    """The record, the open-tools rule and the Renovate section name one exception: the
    unmodified official image, and a patch to it is a new decision."""
    places = {
        "adr": ADR,
        "contributing": REPO_ROOT / "CONTRIBUTING.md",
        "cluster": REPO_ROOT / "docs" / "CLUSTER.md",
    }
    found = {name: _license_lines(path) for name, path in places.items()}

    assert {
        name: (
            bool(lines),
            any("unmodified" in line for line in lines),
            any("new decision" in line for line in lines),
            name == "adr" or any(ADR.name in line for line in lines),
        )
        for name, lines in found.items()
    } == {name: (True, True, True, True) for name in places}
