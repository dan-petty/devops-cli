"""Kubernetes stack deployment, Helm lifecycle, conflict adoption, and Open-WebUI bootstrapping."""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Annotated

import typer

import devops_cli.commands.k8s as k8s
from devops_cli.config.defaults import (
    DEFAULT_K8S_DIR,
    DEFAULT_K8S_STACK,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result, set_dry_run
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
        "open-telemetry": "https://open-telemetry.github.io/opentelemetry-helm-charts",
    },
    "llm": {
        "open-webui": "https://open-webui.github.io/helm-charts",
        "qdrant": "https://qdrant.github.io/qdrant-helm",
    },
}

_HELM_REPOS: dict[str, str] = {
    **_HELM_REPOS_BY_STACK["infra"],
    **_HELM_REPOS_BY_STACK["llm"],
}


_HELM_RELEASES_BY_STACK: dict[str, list[dict[str, str]]] = {
    "infra": [
        {
            "name": "argocd",
            "chart": "argo/argo-cd",
            "namespace": "argocd",
            "values": str(DEFAULT_K8S_DIR / "argocd" / "values.yaml"),
        },
        {
            "name": "kube-prometheus",
            "chart": "prometheus-community/kube-prometheus-stack",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "prometheus-values.yaml"),
        },
        {
            "name": "otel-collector",
            "chart": "open-telemetry/opentelemetry-collector",
            "namespace": "otel",
            "values": str(DEFAULT_K8S_DIR / "otel" / "values.yaml"),
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
}

_HELM_RELEASES: list[dict[str, str]] = _HELM_RELEASES_BY_STACK["infra"]

_MANIFESTS_BY_STACK: dict[str, list[Path]] = {
    "infra": [
        DEFAULT_K8S_DIR / "otel" / "jaeger.yaml",
    ],
    "llm": [
        DEFAULT_K8S_DIR / "llm" / "valkey.yaml",
        DEFAULT_K8S_DIR / "llm" / "ollama-daemonset.yaml",
    ],
}

VALID_STACKS: tuple[str, ...] = ("infra", "llm", "all")


def _adopt_helm_resource_if_conflict(
    error_output: str, release_name: str, namespace: str, context: str | None = None
) -> bool:
    """If Helm failed due to pre-existing unmanaged resources, annotate and label them to adopt."""
    if (
        "invalid ownership metadata" not in error_output
        and "cannot be imported" not in error_output
    ):
        return False

    matches = re.findall(r'([A-Za-z0-9_-]+)\s+"([^"]+)"\s+in namespace\s+"([^"]+)"', error_output)
    if not matches:
        return False

    ctx_args = ["--context", context] if context else []
    adopted_any = False
    for kind_raw, name, ns in matches:
        kind = kind_raw.lower()
        adopt_msg = f"Adopting pre-existing {kind}/{name} for release '{release_name}'..."
        print_warning(adopt_msg)
        k8s._run_cmd(
            [
                "kubectl",
                "annotate",
                kind,
                name,
                "-n",
                ns,
                f"meta.helm.sh/release-name={release_name}",
                f"meta.helm.sh/release-namespace={ns}",
                "--overwrite",
            ]
            + ctx_args,
            check=False,
        )
        k8s._run_cmd(
            [
                "kubectl",
                "label",
                kind,
                name,
                "-n",
                ns,
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
) -> bool:
    """Ensure Open-WebUI signups are enabled and a local admin account is bootstrapped."""
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
        f"    hashed = bcrypt.hashpw({repr(admin_password)}.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')\n"
        "    cur.execute('INSERT INTO \"user\" (id, name, email, role, profile_image_url, last_active_at, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', "
        f"(uid, {repr(admin_name)}, {repr(admin_email)}, 'admin', '/user.png', now, now, now))\n"
        f"    cur.execute('INSERT INTO auth (id, email, password, active) VALUES (?, ?, ?, ?)', (uid, {repr(admin_email)}, hashed, 1))\n"
        "else:\n"
        "    cur.execute('UPDATE auth SET active = 1')\n"
        '    cur.execute(\'UPDATE "user" SET role = "admin" WHERE role = "pending"\')\n'
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
    res_pod = k8s._run_cmd(pod_cmd, check=False, capture=True)
    pod_name = (res_pod.stdout or "").strip()
    if not pod_name:
        return False

    exec_cmd = ["kubectl", "exec", "-i", "-n", "llm", pod_name]
    if context:
        exec_cmd.extend(["--context", context])
    exec_cmd.extend(["--", "python", "-"])
    res = k8s._run_cmd(exec_cmd, input=py_script, check=False, capture=True)
    return res.returncode == 0


def bootstrap_openwebui(
    email: Annotated[str, typer.Option("--email", "-e", help=HELP.k8s.email)] = "admin@localhost",
    name: Annotated[str, typer.Option("--name", "-n", help=HELP.k8s.admin_name)] = "Admin",
    password: Annotated[str, typer.Option("--password", "-p", help=HELP.k8s.password)] = "admin123",
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help=HELP.options.context),
    ] = None,
) -> None:
    """Bootstrap or activate a local administrator account for Open-WebUI."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s bootstrap-openwebui",
            target=email,
            action="bootstrap_openwebui_admin",
            details={"email": email, "name": name, "context": context},
        )
        return

    print_info(f"Bootstrapping Open-WebUI local admin account ({email})...")
    ok = k8s._bootstrap_openwebui_account(
        context=context, email=email, name=name, password=password
    )
    if ok:
        print_success(f"Open-WebUI admin account ready: [bold]{email}[/bold]")
    else:
        print_error(
            "Failed to bootstrap Open-WebUI account. Ensure the open-webui pod is running in namespace 'llm'."
        )
        raise typer.Exit(1)


def _ensure_qdrant_api_key_secret(
    context: str | None = None,
    namespace: str = "llm",
) -> str | None:
    """Ensure qdrant-api-key Secret exists in Kubernetes and is synchronized with OS Keyring."""
    from devops_cli.config.settings import _keyring_get, _keyring_set
    from devops_cli.k8s.credentials import fetch_qdrant_api_key

    k8s._validate_k8s_identifier(namespace, "namespace", namespace=True)
    if context:
        k8s._validate_k8s_identifier(context, "context")
    kubectl_ctx = ["--context", context] if context else []

    check_cmd = ["kubectl", "get", "secret", "qdrant-api-key", "-n", namespace] + kubectl_ctx
    res = run_subprocess(check_cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    if res.returncode == 0:
        return fetch_qdrant_api_key(namespace=namespace, context=context, save_to_keyring=True)

    key = _keyring_get("qdrant_api_key") or secrets.token_urlsafe(32)
    secret_manifest = json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": "qdrant-api-key",
                "namespace": namespace,
            },
            "type": "Opaque",
            "stringData": {
                "api-key": key,
            },
        }
    )
    apply_cmd = ["kubectl", "apply", "-f", "-"] + kubectl_ctx
    create_res = run_subprocess(
        apply_cmd,
        input=secret_manifest,
        quiet=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if create_res.returncode == 0:
        _keyring_set("qdrant_api_key", key)
        return key
    return None


def deploy_stack(
    k8s_dir: Annotated[Path, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = DEFAULT_K8S_DIR,
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
) -> None:
    """Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes."""
    if context:
        k8s._validate_k8s_identifier(context, "context")

    selected_stacks = k8s._resolve_stacks(stack)

    all_releases: list[dict[str, str]] = []
    all_manifests: list[str] = []
    for s_name in selected_stacks:
        all_releases.extend(_HELM_RELEASES_BY_STACK.get(s_name, []))
        all_manifests.extend([str(p) for p in _MANIFESTS_BY_STACK.get(s_name, [])])

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s deploy-stack",
            target=str(k8s_dir),
            action="deploy_k8s_stack",
            details={
                "kustomize_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
                "context": context,
                "helm_releases": [r["name"] for r in all_releases],
                "manifests": all_manifests,
            },
        )
        return

    # 1. Verify cluster reachability
    if not k8s._cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        if not context or context == "minikube":
            print_info(MESSAGES.k8s.start_minikube_tip, prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", context] if context else []
    helm_ctx = ["--kube-context", context] if context else []

    # 2. Apply kustomize base (namespaces)
    print_info("[bold]Applying namespaces...[/bold]", prefix=False)
    k8s._run_cmd(["kubectl", "apply", "-k", str(k8s_dir)] + kubectl_ctx)

    # 3. Add Helm repos for selected stacks
    repos_to_add: dict[str, str] = {}
    for s_name in selected_stacks:
        repos_to_add.update(_HELM_REPOS_BY_STACK.get(s_name, {}))

    if repos_to_add:
        print_info(MESSAGES.k8s.adding_helm_repos, prefix=False)
        for repo_name, repo_url in repos_to_add.items():
            k8s._run_cmd(["helm", "repo", "add", repo_name, repo_url], check=False)
        k8s._run_cmd(["helm", "repo", "update"])

    # 4. Install native manifests
    for manifest_path in all_manifests:
        print_info(f"[bold]Applying manifest {Path(manifest_path).name}...[/bold]", prefix=False)
        k8s._run_cmd(["kubectl", "apply", "-f", manifest_path] + kubectl_ctx, check=False)

    # 5. Install Helm releases
    for release in all_releases:
        if release["name"] == "qdrant":
            qdrant_key = _ensure_qdrant_api_key_secret(
                context=context, namespace=release["namespace"]
            )
            if not qdrant_key:
                print_error(
                    f"Failed to ensure Qdrant API key secret in namespace '{release['namespace']}'. Aborting deployment.",
                    prefix=False,
                )
                raise typer.Exit(1)
        print_info(f"[bold]Installing {release['name']}...[/bold]", prefix=False)
        helm_cmd = (
            [
                "helm",
                "upgrade",
                "--install",
                release["name"],
                release["chart"],
                "--namespace",
                release["namespace"],
                "--values",
                release["values"],
            ]
            + helm_ctx
            + [
                "--wait",
                "--timeout",
                "10m",
            ]
        )
        result = k8s._run_cmd(helm_cmd, check=False, capture=True)
        # If conflict occurs on pre-existing unmanaged resources, adopt and retry up to 5 times
        for _ in range(5):
            if result.returncode == 0:
                break
            err_msg = (result.stderr or "") + " " + (result.stdout or "")
            if not k8s._adopt_helm_resource_if_conflict(
                err_msg,
                release["name"],
                release["namespace"],
                context=context,
            ):
                break
            result = k8s._run_cmd(helm_cmd, check=False, capture=True)

        if result.returncode != 0:
            err_details = (result.stderr or result.stdout or "").strip()
            print_error(f"Failed to install {release['name']}: {err_details}", prefix=False)
        else:
            print_success(f"{release['name']} installed")

    # 6. Auto-configure monitoring URLs & port forwarding
    write_stdout("\n")
    print_success(f"Kubernetes stack ({stack}) deployed.")
    write_stdout("\n")
    k8s.port_forward(stack=stack, context=context)
    write_stdout("\n")
    if "infra" in selected_stacks:
        from devops_cli.k8s.credentials import sync_k8s_credentials

        synced = sync_k8s_credentials(context=context, stack="infra")
        if synced.get("argocd"):
            print_success("ArgoCD admin credentials securely synced to OS Keyring.")
        if synced.get("grafana"):
            print_success("Grafana admin credentials securely synced to OS Keyring.")
        print_info(
            "[dim]Jaeger Query UI: http://localhost:16686 (namespace: otel)[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Jaeger OTLP Traces: localhost:4317 (gRPC) / localhost:4318 (HTTP)[/dim]",
            prefix=False,
        )
    if "llm" in selected_stacks:
        from devops_cli.k8s.credentials import sync_k8s_credentials

        synced_llm = sync_k8s_credentials(context=context, stack="llm")
        if synced_llm.get("qdrant"):
            print_success("Qdrant API key securely synced to OS Keyring.")
        k8s._bootstrap_openwebui_account(context=context)
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


def sync_secrets(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Fetch stack admin credentials (ArgoCD, Grafana) from Kubernetes and store in OS Keyring."""
    if context:
        k8s._validate_k8s_identifier(context, "context")

    set_dry_run(dry_run)
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s sync-secrets",
            action="sync_stack_secrets",
            details={
                "stack": stack,
                "context": context or "active",
                "targets": "argocd.password, grafana.password, qdrant.api_key",
            },
        )
        return

    if not k8s._cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    from devops_cli.k8s.credentials import sync_k8s_credentials

    print_info(f"Synchronizing Kubernetes credentials for stack ({stack})...", prefix=False)
    results = sync_k8s_credentials(context=context, stack=stack)
    for svc, success in results.items():
        if success:
            print_success(f"{svc.capitalize()} credentials securely stored in OS Keyring.")
        else:
            print_info(f"{svc.capitalize()} secret not found in active cluster.", prefix=False)


def teardown_stack(
    k8s_dir: Annotated[Path, typer.Option("--k8s-dir", help=HELP.k8s.k8s_dir)] = DEFAULT_K8S_DIR,
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
) -> None:
    """Uninstall the k8s infrastructure / LLM stack and delete namespaces."""
    if context:
        k8s._validate_k8s_identifier(context, "context")

    selected_stacks = k8s._resolve_stacks(stack)

    all_uninstalls: list[dict[str, str]] = []
    all_manifest_deletes: list[str] = []
    for s_name in reversed(selected_stacks):
        all_uninstalls.extend(reversed(_HELM_RELEASES_BY_STACK.get(s_name, [])))
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
                "context": context,
                "helm_uninstalls": [r["name"] for r in all_uninstalls],
                "manifest_deletes": all_manifest_deletes,
            },
        )
        return

    if not k8s._cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", context] if context else []
    helm_ctx = ["--kube-context", context] if context else []

    # 1. Delete manifests
    for manifest_path in all_manifest_deletes:
        print_info(f"[bold]Deleting manifest {Path(manifest_path).name}...[/bold]", prefix=False)
        k8s._run_cmd(
            ["kubectl", "delete", "-f", manifest_path, "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )

    # 2. Uninstall Helm releases in reverse order
    for release in all_uninstalls:
        print_info(f"[bold]Uninstalling {release['name']}...[/bold]", prefix=False)
        k8s._run_cmd(
            ["helm", "uninstall", release["name"], "--namespace", release["namespace"]] + helm_ctx,
            check=False,
        )

    # 3. Clean up namespaces
    if stack == "all":
        print_info(MESSAGES.k8s.removing_stack_namespaces, prefix=False)
        k8s._run_cmd(
            ["kubectl", "delete", "-k", str(k8s_dir), "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )
    elif stack == "infra":
        print_info(MESSAGES.k8s.removing_infra_namespaces, prefix=False)
        for ns in ["argocd", "monitoring", "otel"]:
            k8s._run_cmd(
                ["kubectl", "delete", "namespace", ns, "--ignore-not-found"] + kubectl_ctx,
                check=False,
            )
    elif stack == "llm":
        print_info(MESSAGES.k8s.removing_llm_namespace, prefix=False)
        k8s._run_cmd(
            ["kubectl", "delete", "namespace", "llm", "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )

    print_success(f"Kubernetes stack ({stack}) torn down.")
