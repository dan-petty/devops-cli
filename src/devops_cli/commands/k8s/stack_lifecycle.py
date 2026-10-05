"""Kubernetes stack deployment, Helm lifecycle, conflict adoption, and Open-WebUI bootstrapping."""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
import devops_cli.commands.k8s.networking as net
from devops_cli.commands.k8s.cluster_runtime import run_subprocess as run_subprocess
from devops_cli.commands.k8s.cluster_secret_push import push_for_stacks, require_keyring_for_push
from devops_cli.config.constants import (
    CONST_HELM_DAEMONSET_RELEASES,
    CONST_HELM_OWNERSHIP_CONFLICT_RE,
    CONST_HELM_TEARDOWN_RETAINED_RELEASES,
)
from devops_cli.config.defaults import (
    DEFAULT_HELM_RECOVERY_MAX_RETRIES,
    DEFAULT_K8S_DIR,
    DEFAULT_K8S_STACK,
)
from devops_cli.dry_run import is_dry_run, render_dry_run_result, set_dry_run
from devops_cli.exceptions.k8s import ClusterSecretPushError
from devops_cli.k8s.cluster_secrets import BASE_STACK, DETACHED_STACKS, secrets_for_stacks
from devops_cli.k8s.secret_push import namespace_exists
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_warning,
    write_stdout,
)

_HELM_REPOS_BY_STACK: dict[str, dict[str, str]] = {
    "infra": {
        "argo": "https://argoproj.github.io/argo-helm",
        "prometheus-community": "https://prometheus-community.github.io/helm-charts",
        "grafana": "https://grafana.github.io/helm-charts",
        "open-telemetry": "https://open-telemetry.github.io/opentelemetry-helm-charts",
        "nvidia-dcgm": "https://nvidia.github.io/dcgm-exporter/helm-charts",
    },
    "llm": {
        "open-webui": "https://open-webui.github.io/helm-charts",
        "qdrant": "https://qdrant.github.io/qdrant-helm",
    },
    "logging": {
        "grafana": "https://grafana.github.io/helm-charts",
    },
}

_HELM_REPOS: dict[str, str] = {
    **_HELM_REPOS_BY_STACK["infra"],
    **_HELM_REPOS_BY_STACK["llm"],
    **_HELM_REPOS_BY_STACK["logging"],
}


_HELM_RELEASES_BY_STACK: dict[str, list[dict[str, str]]] = {
    "infra": [
        # First: k8s-monitoring's extraObjects and dcgm-exporter render ServiceMonitors, and no
        # other chart ships their CRD (k8s-monitoring 4.x dropped it).
        {
            "name": "prometheus-operator-crds",
            "chart": "prometheus-community/prometheus-operator-crds",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "prometheus-operator-crds-values.yaml"),
        },
        {
            "name": "argocd",
            "chart": "argo/argo-cd",
            "namespace": "argocd",
            "values": str(DEFAULT_K8S_DIR / "argocd" / "values.yaml"),
        },
        {
            "name": "k8s-monitoring",
            "chart": "grafana/k8s-monitoring",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml"),
        },
        {
            "name": "prometheus",
            "chart": "prometheus-community/prometheus",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "prometheus-values.yaml"),
        },
        {
            "name": "grafana",
            "chart": "grafana/grafana",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "grafana-values.yaml"),
        },
        {
            "name": "dcgm-exporter",
            "chart": "nvidia-dcgm/dcgm-exporter",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "dcgm-exporter-values.yaml"),
        },
        {
            "name": "otel-collector",
            "chart": "open-telemetry/opentelemetry-collector",
            "namespace": "otel",
            "values": str(DEFAULT_K8S_DIR / "otel" / "values.yaml"),
        },
        {
            "name": "pyroscope",
            "chart": "grafana/pyroscope",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "pyroscope-values.yaml"),
        },
    ],
    "llm": [
        {
            "name": "open-webui",
            "chart": "open-webui/open-webui",
            "namespace": "llm",
            "values": str(DEFAULT_K8S_DIR / "llm" / "values-open-webui.yaml"),
        },
        {
            "name": "qdrant",
            "chart": "qdrant/qdrant",
            "namespace": "llm",
            "values": str(DEFAULT_K8S_DIR / "llm" / "values-qdrant.yaml"),
        },
    ],
    "logging": [
        {
            "name": "loki",
            "chart": "grafana/loki",
            "namespace": "logging",
            "values": str(DEFAULT_K8S_DIR / "logging" / "loki-values.yaml"),
        },
    ],
}

_HELM_RELEASES: list[dict[str, str]] = _HELM_RELEASES_BY_STACK["infra"]

_MANIFESTS_BY_STACK: dict[str, list[Path]] = {
    "infra": [
        DEFAULT_K8S_DIR / "otel" / "jaeger.yaml",
    ],
    "llm": [
        DEFAULT_K8S_DIR / "llm" / "networkpolicy.yaml",
        DEFAULT_K8S_DIR / "llm" / "valkey.yaml",
        DEFAULT_K8S_DIR / "llm" / "profiles" / "services.yaml",
        DEFAULT_K8S_DIR / "llm" / "profiles" / "ollama-profiles.yaml",
        DEFAULT_K8S_DIR / "llm" / "gateway" / "configmap.yaml",
        DEFAULT_K8S_DIR / "llm" / "gateway" / "deployment.yaml",
        DEFAULT_K8S_DIR / "llm" / "gateway" / "service.yaml",
    ],
    "logging": [
        DEFAULT_K8S_DIR / "logging" / "networkpolicy.yaml",
    ],
    "devops": [
        DEFAULT_K8S_DIR / "devops" / "networkpolicy.yaml",
        DEFAULT_K8S_DIR / "devops" / "serviceaccount.yaml",
        DEFAULT_K8S_DIR / "devops" / "configmap.yaml",
        DEFAULT_K8S_DIR / "devops" / "cronjob.yaml",
        DEFAULT_K8S_DIR / "devops" / "roadmap-service" / "pvc.yaml",
        DEFAULT_K8S_DIR / "devops" / "roadmap-service" / "service.yaml",
        DEFAULT_K8S_DIR / "devops" / "roadmap-service" / "deployment.yaml",
        DEFAULT_K8S_DIR / "devops" / "roadmap-service" / "ingress.yaml",
        DEFAULT_K8S_DIR / "devops" / "roadmap-service" / "networkpolicy.yaml",
    ],
}

VALID_STACKS: tuple[str, ...] = ("infra", "llm", "logging", "devops", "all")


def _recover_stuck_helm_release_if_pending(
    error_output: str, release_name: str, namespace: str, context: str | None = None
) -> bool:
    """If Helm failed due to another operation in progress, clean up stuck pending lock."""
    if "another operation" not in error_output:
        return False

    helm_ctx = ["--kube-context", context] if context else []
    status_cmd = ["helm", "status", release_name, "-n", namespace, "-o", "json"] + helm_ctx
    res = runtime._run_cmd(status_cmd, check=False, capture=True)
    if res.returncode != 0 or not res.stdout:
        return False

    try:
        data = json.loads(res.stdout)
        status = str(data.get("info", {}).get("status", ""))
        version = data.get("version")
        if status.startswith("pending-") and version:
            secret_name = f"sh.helm.release.v1.{release_name}.v{version}"
            msg = (
                f"Helm release '{release_name}' in namespace '{namespace}' is stuck in '{status}' "
                f"(revision {version}). Cleaning up release lock secret '{secret_name}'..."
            )
            print_warning(msg)
            k_ctx = ["--context", context] if context else []
            del_cmd = [
                "kubectl",
                "delete",
                "secret",
                secret_name,
                "-n",
                namespace,
                "--ignore-not-found",
            ] + k_ctx
            runtime._run_cmd(del_cmd, check=False)
            return True
    except json.JSONDecodeError, KeyError, TypeError:
        pass
    return False


def _adopt_helm_resource_if_conflict(
    error_output: str, release_name: str, namespace: str, context: str | None = None
) -> bool:
    """If Helm failed due to pre-existing unmanaged resources, annotate and label them to adopt.

    Helm names a cluster-scoped resource, such as a CRD, `in namespace ""`, so it is addressed
    without `-n`. Helm checks the release-namespace annotation against the release's namespace,
    which a namespaced resource need not share.
    """
    if (
        "invalid ownership metadata" not in error_output
        and "cannot be imported" not in error_output
    ):
        return False

    matches = CONST_HELM_OWNERSHIP_CONFLICT_RE.findall(error_output)
    if not matches:
        return False

    ctx_args = ["--context", context] if context else []
    adopted_any = False
    for kind_raw, name, ns in matches:
        kind = kind_raw.lower()
        ns_args = ["-n", ns] if ns else []
        adopt_msg = f"Adopting pre-existing {kind}/{name} for release '{release_name}'..."
        print_warning(adopt_msg)
        runtime._run_cmd(
            [
                "kubectl",
                "annotate",
                kind,
                name,
                *ns_args,
                f"meta.helm.sh/release-name={release_name}",
                f"meta.helm.sh/release-namespace={namespace}",
                "--overwrite",
            ]
            + ctx_args,
            check=False,
        )
        runtime._run_cmd(
            [
                "kubectl",
                "label",
                kind,
                name,
                *ns_args,
                "app.kubernetes.io/managed-by=Helm",
                "--overwrite",
            ]
            + ctx_args,
            check=False,
        )
        adopted_any = True
    return adopted_any


def _get_openwebui_bootstrap_credentials() -> dict[str, str]:
    """Resolve OpenWebUI admin bootstrap credentials from environment or secure defaults."""
    env_password = os.environ.get("OPENWEBUI_ADMIN_PASSWORD")
    if not env_password:
        env_password = secrets.token_urlsafe(24)
    return {
        "email": os.environ.get("OPENWEBUI_ADMIN_EMAIL", "admin@localhost"),
        "name": os.environ.get("OPENWEBUI_ADMIN_NAME", "Admin"),
        "password": env_password,
    }


def _bootstrap_openwebui_account(
    context: str | None = None,
    email: str | None = None,
    name: str | None = None,
    password: str | None = None,
) -> tuple[bool, bool]:
    """Ensure Open-WebUI signups are enabled and a local admin account is bootstrapped.

    Returns:
        tuple[bool, bool]: (success, created) where created indicates whether a new admin
        account was inserted or an existing account was retained.
    """
    creds = _get_openwebui_bootstrap_credentials()
    admin_email = email or creds["email"]
    admin_name = name or creds["name"]
    admin_password = password or creds["password"]
    py_script = (
        "import sqlite3, uuid, time, json, bcrypt, os\n"
        "db_path = '/app/backend/data/webui.db'\n"
        "if not os.path.exists(db_path):\n"
        "    exit(0)\n"
        "conn = sqlite3.connect(db_path)\n"
        "cur = conn.cursor()\n"
        "now = int(time.time())\n"
        "cur.execute('UPDATE config SET value = ?, updated_at = ? WHERE key = ?', (json.dumps(True), now, 'ui.enable_signup'))\n"
        "cur.execute('UPDATE config SET value = ?, updated_at = ? WHERE key = ?', (json.dumps('user'), now, 'ui.default_user_role'))\n"
        "cur.execute('SELECT COUNT(*) FROM \"user\"')\n"
        "count = cur.fetchone()[0]\n"
        "if count == 0:\n"
        "    uid = str(uuid.uuid4())\n"
        f"    hashed = bcrypt.hashpw({admin_password!r}.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')\n"  # nosec B608  # Embedded admin bootstrap credentials in inline pod script
        "    cur.execute('INSERT INTO \"user\" (id, name, email, role, profile_image_url, last_active_at, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', "
        f"(uid, {admin_name!r}, {admin_email!r}, 'admin', '/user.png', now, now, now))\n"
        f"    cur.execute('INSERT INTO auth (id, email, password, active) VALUES (?, ?, ?, ?)', (uid, {admin_email!r}, hashed, 1))\n"
        "    print('CREATED')\n"
        "else:\n"
        "    cur.execute('UPDATE auth SET active = 1')\n"
        '    cur.execute(\'UPDATE "user" SET role = "admin" WHERE role = "pending"\')\n'
        "    print('EXISTING')\n"
        "conn.commit()\n"
    )
    pod_cmd = [
        "kubectl",
        "get",
        "pods",
        "-n",
        "llm",
        "-l",
        "app.kubernetes.io/name=open-webui",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ]
    if context:
        pod_cmd.extend(["--context", context])
    res_pod = runtime._run_cmd(pod_cmd, check=False, capture=True)
    pod_name = (res_pod.stdout or "").strip()
    if not pod_name:
        return (False, False)

    exec_cmd = ["kubectl", "exec", "-i", "-n", "llm", pod_name]
    if context:
        exec_cmd.extend(["--context", context])
    exec_cmd.extend(["--", "python", "-"])
    res = runtime._run_cmd(exec_cmd, input=py_script, check=False, capture=True)
    created = "CREATED" in (res.stdout or "")
    return (res.returncode == 0, created)


def _mask_email_display(email: str) -> str:
    """Mask user email in CLI outputs to prevent leaking PII, while keeping local dev clear."""
    if email.endswith("@localhost") or email.endswith(".local") or email.endswith(".internal"):
        return email
    parts = email.split("@", 1)
    if len(parts) == 2:
        prefix = parts[0][:2] if len(parts[0]) > 2 else parts[0][:1]
        return f"{prefix}***@{parts[1]}"
    return "***"


def bootstrap_openwebui(
    email: Annotated[
        str,
        typer.Option(
            "--email",
            "-e",
            help="Email address for the local administrator account.",
        ),
    ] = "admin@localhost",
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            "-p",
            help="Password for administrator. If omitted, securely generated and stored in OS Keyring.",
        ),
    ] = None,
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Full display name for the administrator.",
        ),
    ] = "Local Administrator",
    context: Annotated[
        str | None,
        typer.Option(
            "--context",
            "-c",
            help="Kubernetes context to target (defaults to config default or active).",
        ),
    ] = None,
    show_password: Annotated[
        bool,
        typer.Option(
            "--show-password",
            help="Display generated admin password in plain text instead of masking.",
        ),
    ] = False,
) -> None:
    """Bootstrap or activate a local administrator account for Open-WebUI."""
    creds = _get_openwebui_bootstrap_credentials()
    effective_password = password or creds["password"]
    raw_env_password = os.environ.get("OPENWEBUI_ADMIN_PASSWORD", "").strip()
    was_generated = password is None and not raw_env_password

    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    display_email = _mask_email_display(email)
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s bootstrap-openwebui",
            target=display_email,
            action="bootstrap_openwebui_admin",
            details={"email": display_email, "name": name, "context": effective_context},
        )
        return

    print_info(f"Bootstrapping Open-WebUI local admin account ({display_email})...")
    ok, created = _bootstrap_openwebui_account(
        context=effective_context, email=email, name=name, password=effective_password
    )
    if ok:
        print_success(f"Open-WebUI admin account ready: [bold]{display_email}[/bold]")
        if created:
            from devops_cli.config.settings import _keyring_set

            _keyring_set("openwebui_admin_password", effective_password)
            if was_generated:
                if show_password:
                    print_success(
                        f"Generated secure Open-WebUI admin password: [bold]{effective_password}[/bold]"
                    )
                else:
                    masked = effective_password[:3] + "..." + effective_password[-3:]
                    print_success(
                        f"Generated secure Open-WebUI admin password: [bold]{masked}[/bold] (use --show-password to reveal)"
                    )
        else:
            print_info(
                "Open-WebUI user database already initialized; existing admin credentials retained."
            )
    else:
        print_error(
            "Failed to bootstrap Open-WebUI account. Ensure the open-webui pod is running in namespace 'llm'."
        )
        raise typer.Exit(1)


def _is_helm_v4_or_newer() -> bool:
    """Detect whether the active Helm CLI is version 4 or newer."""
    proc = runtime._run_cmd(
        ["helm", "version", "--template", "{{.Version}}"], check=False, capture=True
    )
    if proc.returncode != 0 or not proc.stdout:
        return False
    ver_clean = proc.stdout.strip().lstrip("v")
    try:
        major = int(ver_clean.split(".")[0])
        return major >= 4
    except ValueError, IndexError:
        return False


def _build_helm_upgrade_cmd(
    release: dict[str, str],
    helm_ctx: list[str],
    wait: bool,
    timeout: str,
) -> list[str]:
    """Construct helm upgrade --install command matching installed Helm capabilities."""
    helm_cmd = ["helm", "upgrade", "--install"]
    if _is_helm_v4_or_newer():
        helm_cmd.append("--force-conflicts")
    helm_cmd.extend(
        [
            release["name"],
            release["chart"],
            "--namespace",
            release["namespace"],
            "--values",
            release["values"],
        ]
    )
    helm_cmd.extend(helm_ctx)
    if wait:
        helm_cmd.extend(["--wait", "--timeout", timeout])
    return helm_cmd


def _deploy_helm_repos(selected_stacks: Sequence[str]) -> None:
    """Add and update Helm repositories required for the selected stacks."""
    repos_to_add: dict[str, str] = {}
    for s_name in selected_stacks:
        repos_to_add.update(_HELM_REPOS_BY_STACK.get(s_name, {}))
    if not repos_to_add:
        return
    print_info(MESSAGES.k8s.adding_helm_repos, prefix=False)
    for repo_name, repo_url in repos_to_add.items():
        runtime._run_cmd(["helm", "repo", "add", repo_name, repo_url], check=False)
    runtime._run_cmd(["helm", "repo", "update"])


def _apply_manifest_files(manifests: Sequence[str], kubectl_ctx: list[str]) -> None:
    """Apply Kubernetes native manifest files."""
    for manifest_path in manifests:
        print_info(f"[bold]Applying manifest {Path(manifest_path).name}...[/bold]", prefix=False)
        runtime._run_cmd(["kubectl", "apply", "-f", manifest_path] + kubectl_ctx, check=False)


def _run_helm_with_adoption_retries(
    helm_cmd: list[str],
    release: dict[str, str],
    effective_context: str | None,
) -> Any:
    """Run Helm upgrade, retrying after recovering a stuck pending lock or adopting a resource.

    Helm names one conflicting resource per failed attempt, so each retry adopts the next one. A
    retry that fails exactly like the attempt before it made no progress and ends the retries.
    """
    result = runtime._run_cmd(helm_cmd, check=False, capture=True)
    previous_error: str | None = None
    for _ in range(DEFAULT_HELM_RECOVERY_MAX_RETRIES):
        err_msg = (result.stderr or "") + " " + (result.stdout or "")
        if result.returncode == 0 or err_msg == previous_error:
            break
        previous_error = err_msg
        pending_recovered = _recover_stuck_helm_release_if_pending(
            err_msg,
            release["name"],
            release["namespace"],
            context=effective_context,
        )
        conflicts_adopted = _adopt_helm_resource_if_conflict(
            err_msg,
            release["name"],
            release["namespace"],
            context=effective_context,
        )
        if not (pending_recovered or conflicts_adopted):
            break
        result = runtime._run_cmd(helm_cmd, check=False, capture=True)
    return result


def _install_single_release(
    release: dict[str, str],
    effective_context: str | None,
    helm_ctx: list[str],
    wait: bool,
    timeout: str,
    unready_nodes: Sequence[str] = (),
) -> None:
    """Install or upgrade a single Helm release with conflict adoption retries."""
    effective_wait = wait
    if wait and unready_nodes and release["name"] in CONST_HELM_DAEMONSET_RELEASES:
        print_warning(
            f"Cluster has unready nodes ({', '.join(unready_nodes)}). Skipping Helm '--wait' for DaemonSet release '{release['name']}'."
        )
        effective_wait = False
    print_info(f"[bold]Installing {release['name']}...[/bold]", prefix=False)
    helm_cmd = _build_helm_upgrade_cmd(release, helm_ctx, effective_wait, timeout)
    result = _run_helm_with_adoption_retries(helm_cmd, release, effective_context)
    if result.returncode != 0:
        err_details = (result.stderr or result.stdout or "").strip()
        print_error(f"Failed to install {release['name']}: {err_details}", prefix=False)
    else:
        print_success(f"{release['name']} installed")


def _post_deploy_networking(
    stack: str,
    effective_context: str | None,
    port_forward: bool,
    configure_urls: bool,
) -> None:
    """Handle optional port-forwarding and service URL configuration."""
    if port_forward:
        net.port_forward(
            stack=stack,
            context=effective_context,
            update_config=configure_urls,
        )
    elif configure_urls:
        net.configure_urls(stack=stack, context=effective_context)


def _post_deploy_credentials(
    selected_stacks: Sequence[str],
    effective_context: str | None,
) -> None:
    """Sync credentials to OS Keyring and display service endpoints."""
    if "infra" in selected_stacks:
        from devops_cli.k8s.credentials import sync_k8s_credentials

        synced = sync_k8s_credentials(context=effective_context, stack="infra")
        if synced.get("argocd"):
            print_success("ArgoCD admin credentials securely synced to OS Keyring.")
        if synced.get("argocd_token"):
            print_success("ArgoCD API token securely synced to OS Keyring.")
        if synced.get("grafana"):
            print_success("Grafana admin credentials securely synced to OS Keyring.")
        if synced.get("grafana_token"):
            print_success("Grafana API token securely synced to OS Keyring.")
        print_info(
            "[dim]Jaeger Query UI: http://localhost:16686 (namespace: otel)[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Jaeger OTLP Traces: localhost:4317 (gRPC) / localhost:4318 (HTTP)[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Pyroscope UI: http://localhost:4040 (namespace: monitoring)[/dim]",
            prefix=False,
        )
    if "llm" in selected_stacks:
        _bootstrap_openwebui_account(context=effective_context)
        print_info("[dim]Ollama: http://localhost:11434 (namespace: llm)[/dim]", prefix=False)
        print_info(
            "[dim]Open-WebUI: http://localhost:3000 (Admin: admin@localhost | Sign-ups: enabled)[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Qdrant Vector DB: http://localhost:6333 (HTTP) / :6334 (gRPC)[/dim]",
            prefix=False,
        )
        print_info("[dim]Valkey Cache: localhost:6379 (namespace: llm)[/dim]", prefix=False)
    if "devops" in selected_stacks:
        k_ctx = ["--context", effective_context] if effective_context else []
        runtime._run_cmd(
            ["kubectl", "rollout", "restart", "deploy/roadmap-service", "-n", "devops"] + k_ctx,
            check=False,
        )
        print_info(
            "[dim]Roadmap Service: http://localhost:8000 (namespace: devops)[/dim]",
            prefix=False,
        )


def _push_stacks_for(selected_stacks: Sequence[str], context: str | None) -> list[str]:
    """The base rows, the deployed stacks' and each detached stack whose namespace exists.

    Detached stacks are pushed only where their namespace exists and they were not explicitly selected.
    """
    try:
        detached = [
            name
            for name in DETACHED_STACKS
            if name not in selected_stacks and namespace_exists(name, context)
        ]
    except ClusterSecretPushError as exc:
        print_error(MESSAGES.k8s.push_failed.format(reason=str(exc)), prefix=False, safe=True)
        raise typer.Exit(1) from exc
    return [BASE_STACK, *selected_stacks, *detached]


def _dry_run_secrets(selected_stacks: Sequence[str], push_secrets: bool) -> list[str]:
    """The Secrets and key names a deploy would push, from the table alone, running nothing.

    A detached stack's rows are pushed only where its namespace exists, which a dry run does
    not ask the cluster, so they are listed with that condition. No value is listed.
    """
    if not push_secrets:
        return []
    detached = set(DETACHED_STACKS) - set(selected_stacks)
    return [
        f"{secret.ref}: {', '.join(entry.key for entry in secret.entries)}"
        + (f" (if namespace {secret.namespace} exists)" if secret.stack in detached else "")
        for secret in secrets_for_stacks([BASE_STACK, *selected_stacks, *detached])
    ]


def deploy_stack(
    k8s_dir: Annotated[Path, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = DEFAULT_K8S_DIR,
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    wait: Annotated[
        bool,
        typer.Option(
            "--wait/--no-wait",
            help="Wait for Helm releases and workloads to become ready before returning.",
        ),
    ] = True,
    timeout: Annotated[
        str,
        typer.Option("--timeout", "-t", help="Timeout for Helm operations when waiting."),
    ] = "10m",
    port_forward: Annotated[
        bool,
        typer.Option(
            "--port-forward/--no-port-forward",
            help=HELP.k8s.port_forward_flag,
        ),
    ] = False,
    configure_urls: Annotated[
        bool,
        typer.Option(
            "--configure-urls/--no-configure-urls",
            help=HELP.k8s.configure_urls_flag,
        ),
    ] = False,
    push_secrets: Annotated[
        bool,
        typer.Option("--push-secrets/--no-push-secrets", help=HELP.k8s.push_secrets_flag),
    ] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.k8s.deploy_dry_run)] = False,
) -> None:
    """Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes.

    Right after the namespaces, it pushes the Secrets of the base rows, its stacks and every
    detached stack whose namespace exists (`devops k8s push-secrets`), before anything that
    reads them. A locked or missing keyring stops it before it applies anything.
    """
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    selected_stacks = net._resolve_stacks(stack)

    all_releases: list[dict[str, str]] = []
    all_manifests: list[str] = []
    for s_name in selected_stacks:
        all_releases.extend(_HELM_RELEASES_BY_STACK.get(s_name, []))
        all_manifests.extend([str(p) for p in _MANIFESTS_BY_STACK.get(s_name, [])])

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops k8s deploy-stack",
            target=str(k8s_dir),
            action="deploy_k8s_stack",
            details={
                "kustomize_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
                "context": effective_context,
                "wait": wait,
                "timeout": timeout,
                "port_forward": port_forward,
                "configure_urls": configure_urls,
                "secrets": _dry_run_secrets(selected_stacks, push_secrets),
                "helm_releases": [r["name"] for r in all_releases],
                "manifests": all_manifests,
            },
        )
        return

    # 1. A push needs the unlocked keyring: check it before anything reads or writes the cluster
    if push_secrets:
        require_keyring_for_push()

    # 2. Verify cluster reachability
    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        if not effective_context or effective_context.strip().lower() == "minikube":
            print_info(MESSAGES.k8s.start_minikube_tip, prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", effective_context] if effective_context else []
    helm_ctx = ["--kube-context", effective_context] if effective_context else []

    # 3. Apply kustomize base (namespaces)
    print_info("[bold]Applying namespaces...[/bold]", prefix=False)
    runtime._run_cmd(["kubectl", "apply", "-k", str(k8s_dir)] + kubectl_ctx)

    # 4. Push the stacks' Secrets before anything reads them
    if push_secrets:
        print_info(MESSAGES.k8s.pushing_secrets, prefix=False)
        push_for_stacks(_push_stacks_for(selected_stacks, effective_context), effective_context)

    # 5. Add Helm repos for selected stacks
    _deploy_helm_repos(selected_stacks)

    # 6. Install native manifests
    _apply_manifest_files(all_manifests, kubectl_ctx)

    # 7. Check for unready cluster nodes to avoid DaemonSet wait timeouts
    unready_nodes = runtime._get_unready_nodes(context=effective_context)
    if unready_nodes and wait:
        print_warning(
            f"Detected unready cluster nodes: {', '.join(unready_nodes)}. Skipping Helm '--wait' for DaemonSet releases to prevent deadline timeouts."
        )

    # 8. Install Helm releases
    for release in all_releases:
        _install_single_release(
            release, effective_context, helm_ctx, wait, timeout, unready_nodes=unready_nodes
        )

    # 9. Post-deployment networking & credentials
    write_stdout("\n")
    print_success(f"Kubernetes stack ({stack}) deployed.")
    write_stdout("\n")
    _post_deploy_networking(stack, effective_context, port_forward, configure_urls)
    _post_deploy_credentials(selected_stacks, effective_context)


def sync_secrets(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring.

    The direction is cluster → workstation keyring, the reverse of `push-secrets`.
    """
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    set_dry_run(dry_run)
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s sync-secrets",
            action="sync_stack_secrets",
            details={
                "stack": stack,
                "context": effective_context or "active",
                "targets": "argocd.password, grafana.password",
            },
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    from devops_cli.k8s.credentials import sync_k8s_credentials

    print_info(f"Synchronizing Kubernetes credentials for stack ({stack})...", prefix=False)
    results = sync_k8s_credentials(context=effective_context, stack=stack)
    for svc, success in results.items():
        if success:
            label = svc.replace("_", " ").title()
            print_success(f"{label} credentials securely stored in OS Keyring.")
        elif not svc.endswith("_token"):
            print_info(f"{svc.capitalize()} secret not found in active cluster.", prefix=False)


def _teardown_namespaces(stack: str, k8s_dir: Path, kubectl_ctx: list[str]) -> None:
    """Delete Kubernetes namespaces corresponding to torn-down stacks."""
    normalized_stack = stack.lower()
    if normalized_stack == "all":
        print_info(MESSAGES.k8s.removing_stack_namespaces, prefix=False)
        runtime._run_cmd(
            ["kubectl", "delete", "-k", str(k8s_dir), "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )
        return

    ns_map: dict[str, tuple[str, ...]] = {
        "infra": ("argocd", "monitoring", "otel"),
        "llm": ("llm",),
        "logging": ("logging",),
    }
    targets = ns_map.get(normalized_stack, ())
    if targets:
        print_info(f"Removing {normalized_stack} namespace(s)...", prefix=False)
        for ns in targets:
            runtime._run_cmd(
                ["kubectl", "delete", "namespace", ns, "--ignore-not-found"] + kubectl_ctx,
                check=False,
            )


def teardown_stack(
    k8s_dir: Annotated[Path, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = DEFAULT_K8S_DIR,
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
) -> None:
    """Uninstall the k8s infrastructure / LLM stack and delete namespaces."""
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    selected_stacks = net._resolve_stacks(stack)

    all_uninstalls: list[dict[str, str]] = []
    all_manifest_deletes: list[str] = []
    for s_name in reversed(selected_stacks):
        all_uninstalls.extend(
            release
            for release in reversed(_HELM_RELEASES_BY_STACK.get(s_name, []))
            if release["name"] not in CONST_HELM_TEARDOWN_RETAINED_RELEASES
        )
        all_manifest_deletes.extend([str(p) for p in reversed(_MANIFESTS_BY_STACK.get(s_name, []))])

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s teardown-stack",
            target=str(k8s_dir),
            action="teardown_k8s_stack",
            details={
                "kustomize_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
                "context": effective_context,
                "helm_uninstalls": [r["name"] for r in all_uninstalls],
                "manifest_deletes": all_manifest_deletes,
            },
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", effective_context] if effective_context else []
    helm_ctx = ["--kube-context", effective_context] if effective_context else []

    # 1. Delete manifests
    for manifest_path in all_manifest_deletes:
        print_info(f"[bold]Deleting manifest {Path(manifest_path).name}...[/bold]", prefix=False)
        runtime._run_cmd(
            ["kubectl", "delete", "-f", manifest_path, "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )

    # 2. Uninstall Helm releases in reverse order
    for release in all_uninstalls:
        print_info(f"[bold]Uninstalling {release['name']}...[/bold]", prefix=False)
        runtime._run_cmd(
            ["helm", "uninstall", release["name"], "--namespace", release["namespace"]] + helm_ctx,
            check=False,
        )

    # 3. Clean up namespaces
    _teardown_namespaces(stack, k8s_dir, kubectl_ctx)

    print_success(f"Kubernetes stack ({stack}) torn down.")
