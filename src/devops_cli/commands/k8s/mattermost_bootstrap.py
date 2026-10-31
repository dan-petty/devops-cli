"""Bootstrap Mattermost teams, channels, webhooks, and slash commands in Kubernetes."""

from __future__ import annotations

import json
from typing import Annotated, Any, cast

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP
from devops_cli.output.console import print_error, print_info, print_success


def _extract_json_payload(output: str) -> dict[str, Any] | list[Any] | None:
    """Extract JSON payload from mmctl output which may include non-JSON logs."""
    output = output.strip()
    if not output:
        return None
    idx_brace = output.find("{")
    idx_bracket = output.find("[")
    start_idx = -1
    if idx_brace != -1 and idx_bracket != -1:
        start_idx = min(idx_brace, idx_bracket)
    elif idx_brace != -1:
        start_idx = idx_brace
    elif idx_bracket != -1:
        start_idx = idx_bracket

    if start_idx != -1:
        output = output[start_idx:]
    try:
        return cast(dict[str, Any] | list[Any], json.loads(output))
    except json.JSONDecodeError:
        return None


def _find_admin_user_id(user_list_output: str, preferred_user: str | None = None) -> str:
    """Find the user ID from mmctl user list output."""
    lines = user_list_output.strip().splitlines()
    candidates: list[tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if ":" not in line:
            continue
        parts = line.split(":", 1)
        uid = parts[0].strip()
        rest = parts[1].strip()
        uname = rest.split()[0] if rest else ""
        candidates.append((uid, uname))

    if preferred_user:
        for uid, uname in candidates:
            if preferred_user in (uid, uname):
                return uid

    # Default to first non-bot user
    bot_names = {"calls", "github", "system-bot"}
    for uid, uname in candidates:
        if uname not in bot_names:
            return uid

    return candidates[0][0] if candidates else "admin"


def _resolve_mattermost_pod(effective_context: str | None) -> str:
    print_info(
        f"Checking Mattermost deployment in namespace 'mattermost' (context: {effective_context or 'default'})..."
    )
    for selector in ("app.kubernetes.io/name=mattermost", "app=mattermost"):
        pod_cmd = [
            "kubectl",
            "get",
            "pods",
            "-n",
            "mattermost",
            "-l",
            selector,
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ]
        if effective_context:
            pod_cmd.extend(["--context", effective_context])
        res_pod = runtime._run_cmd(pod_cmd, check=False, capture=True)
        pod_name = (res_pod.stdout or "").strip()
        if pod_name:
            return pod_name

    print_error("No Mattermost pod found in namespace 'mattermost'.", prefix=False)
    raise typer.Exit(1)


def _exec_mmctl(pod_name: str, effective_context: str | None, args: list[str]) -> tuple[int, str]:
    cmd = ["kubectl", "exec", "-n", "mattermost", pod_name]
    if effective_context:
        cmd.extend(["--context", effective_context])
    cmd.extend(["--", "mmctl", "--local", *args])
    res = runtime._run_cmd(cmd, check=False, capture=True)
    return res.returncode, res.stdout or ""


def _ensure_team(pod_name: str, effective_context: str | None, team: str) -> str:
    _, team_list_out = _exec_mmctl(pod_name, effective_context, ["team", "list", "--json"])
    teams = _extract_json_payload(team_list_out) or []
    if isinstance(teams, list):
        for t in teams:
            if isinstance(t, dict) and t.get("name") == team:
                return str(t.get("id") or team)

    print_info(f"Creating Mattermost team '{team}'...")
    _, team_create_out = _exec_mmctl(
        pod_name,
        effective_context,
        [
            "team",
            "create",
            "--name",
            team,
            "--display-name",
            team.capitalize(),
            "--json",
        ],
    )
    t_data = _extract_json_payload(team_create_out)
    return str(t_data.get("id")) if isinstance(t_data, dict) and t_data.get("id") else team


def _ensure_channel(
    pod_name: str,
    effective_context: str | None,
    team: str,
    name: str,
    display_name: str,
    header: str,
    existing_id: str | None,
) -> str | None:
    if existing_id:
        return existing_id
    print_info(f"Creating channel '{name}'...")
    _, ch_out = _exec_mmctl(
        pod_name,
        effective_context,
        [
            "channel",
            "create",
            "--team",
            team,
            "--name",
            name,
            "--display-name",
            display_name,
            "--header",
            header,
            "--json",
        ],
    )
    c_data = _extract_json_payload(ch_out)
    return str(c_data.get("id")) if isinstance(c_data, dict) and c_data.get("id") else None


def _ensure_channels(
    pod_name: str, effective_context: str | None, team: str
) -> tuple[str | None, str | None]:
    _, chan_list_out = _exec_mmctl(pod_name, effective_context, ["channel", "list", team, "--json"])
    channels = _extract_json_payload(chan_list_out) or []
    alerts_id: str | None = None
    deploys_id: str | None = None
    if isinstance(channels, list):
        for ch in channels:
            if isinstance(ch, dict):
                if ch.get("name") == "alerts":
                    alerts_id = ch.get("id")
                elif ch.get("name") == "deploys":
                    deploys_id = ch.get("id")

    alerts_id = _ensure_channel(
        pod_name,
        effective_context,
        team,
        "alerts",
        "Alerts",
        "Cluster alerts from Alertmanager",
        alerts_id,
    )
    deploys_id = _ensure_channel(
        pod_name,
        effective_context,
        team,
        "deploys",
        "Deploys",
        "Deployment notifications from Argo CD",
        deploys_id,
    )
    return alerts_id, deploys_id


def _ensure_incoming_webhook(
    pod_name: str,
    effective_context: str | None,
    channel_id: str,
    creator_id: str,
    display_name: str,
    description: str,
    existing_token: str | None,
) -> str | None:
    if existing_token:
        return existing_token
    print_info(f"Creating incoming webhook for {display_name}...")
    _, hook_res = _exec_mmctl(
        pod_name,
        effective_context,
        [
            "webhook",
            "create-incoming",
            "--channel",
            channel_id,
            "--user",
            creator_id,
            "--display-name",
            display_name,
            "--description",
            description,
            "--lock-to-channel",
            "--json",
        ],
    )
    h_data = _extract_json_payload(hook_res)
    return str(h_data.get("id")) if isinstance(h_data, dict) and h_data.get("id") else None


def _ensure_webhooks(
    pod_name: str,
    effective_context: str | None,
    team: str,
    creator_id: str,
    alerts_id: str | None,
    deploys_id: str | None,
) -> tuple[str | None, str | None]:
    _, hooks_out = _exec_mmctl(pod_name, effective_context, ["webhook", "list", team, "--json"])
    webhooks = _extract_json_payload(hooks_out) or []
    alerts_token: str | None = None
    deploys_token: str | None = None

    if isinstance(webhooks, list):
        for hook in webhooks:
            if isinstance(hook, dict):
                cid = hook.get("channel_id")
                if cid == alerts_id and hook.get("channel_locked", True):
                    alerts_token = hook.get("id")
                elif cid == deploys_id and hook.get("channel_locked", True):
                    deploys_token = hook.get("id")

    if alerts_id:
        alerts_token = _ensure_incoming_webhook(
            pod_name,
            effective_context,
            alerts_id,
            creator_id,
            "Alertmanager",
            "Cluster alerts from Alertmanager",
            alerts_token,
        )
    if deploys_id:
        deploys_token = _ensure_incoming_webhook(
            pod_name,
            effective_context,
            deploys_id,
            creator_id,
            "Argo CD",
            "Deployment notifications from Argo CD",
            deploys_token,
        )
    return alerts_token, deploys_token


def _ensure_slash_command(
    pod_name: str,
    effective_context: str | None,
    team: str,
    creator_id: str,
) -> str | None:
    _, cmds_out = _exec_mmctl(pod_name, effective_context, ["command", "list", team, "--json"])
    commands = _extract_json_payload(cmds_out) or []
    if isinstance(commands, list):
        for cmd in commands:
            if isinstance(cmd, dict) and cmd.get("trigger") == "roadmap":
                return cmd.get("token")

    print_info("Creating slash command '/roadmap'...")
    _, cmd_res = _exec_mmctl(
        pod_name,
        effective_context,
        [
            "command",
            "create",
            team,
            "--title",
            "Roadmap Service",
            "--description",
            "Roadmap status inspection",
            "--trigger-word",
            "roadmap",
            "--url",
            "http://roadmap-service.devops.svc.cluster.local:8000/webhooks/mattermost",
            "--creator",
            creator_id,
            "--post",
            "--json",
        ],
    )
    cmd_data = _extract_json_payload(cmd_res)
    return (
        str(cmd_data.get("token")) if isinstance(cmd_data, dict) and cmd_data.get("token") else None
    )


def _save_tokens_to_keyring(
    alerts_token: str | None,
    deploys_token: str | None,
    command_token: str | None,
) -> None:
    from devops_cli.config.os_keyring import store_keyring_secret
    from devops_cli.config.settings import _KEYRING_KEYS

    if alerts_token:
        store_keyring_secret(_KEYRING_KEYS["mattermost.alerts_hook"], alerts_token)
        print_success("Saved 'mattermost.alerts_hook' to OS keyring.")
    if deploys_token:
        store_keyring_secret(_KEYRING_KEYS["mattermost.deploys_hook"], deploys_token)
        print_success("Saved 'mattermost.deploys_hook' to OS keyring.")
    if command_token:
        store_keyring_secret(_KEYRING_KEYS["mattermost.command_token"], command_token)
        print_success("Saved 'mattermost.command_token' to OS keyring.")


def _push_cluster_secrets(effective_context: str | None) -> None:
    print_info("Pushing updated cluster secrets...")
    from devops_cli.commands.k8s.cluster_secret_push import push_secrets as k8s_push_secrets

    k8s_push_secrets(
        only=[
            "monitoring/alertmanager-mattermost",
            "argocd/argocd-notifications-secret",
            "devops/devops-cli",
        ],
        context=effective_context,
    )


@dry_run_class("request-plan")
def bootstrap_mattermost(
    team: Annotated[
        str,
        typer.Option(
            "--team",
            help="Mattermost team name.",
        ),
    ] = "homelab",
    admin_user: Annotated[
        str | None,
        typer.Option(
            "--admin-user",
            help="Administrator username or ID to own integrations.",
        ),
    ] = None,
    push_secrets: Annotated[
        bool,
        typer.Option(
            "--push-secrets/--no-push-secrets",
            help="Push updated cluster secrets after saving tokens to keyring.",
        ),
    ] = True,
    context: Annotated[
        str | None,
        typer.Option(
            "--context",
            "-c",
            help="Kubernetes context to target (defaults to config default or active).",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Bootstrap Mattermost teams, channels, webhooks, and slash commands in Kubernetes."""
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.k8s.manifest_plans import plan_k8s_bootstrap_mattermost

        requests = plan_k8s_bootstrap_mattermost(
            team=team,
            context=effective_context,
            push_secrets=push_secrets,
        )
        render_request_plan("devops k8s bootstrap-mattermost", requests)
        return

    pod_name = _resolve_mattermost_pod(effective_context)

    # 1. Resolve administrator user
    _, user_list_out = _exec_mmctl(pod_name, effective_context, ["user", "list"])
    creator_id = _find_admin_user_id(user_list_out, admin_user)

    # 2. Ensure team exists
    _ensure_team(pod_name, effective_context, team)

    # 3. Ensure channels alerts and deploys exist
    alerts_id, deploys_id = _ensure_channels(pod_name, effective_context, team)

    # 4. Ensure incoming webhooks exist
    alerts_token, deploys_token = _ensure_webhooks(
        pod_name, effective_context, team, creator_id, alerts_id, deploys_id
    )

    # 5. Ensure slash command /roadmap exists
    command_token = _ensure_slash_command(pod_name, effective_context, team, creator_id)

    # 6. Store tokens in OS keyring
    _save_tokens_to_keyring(alerts_token, deploys_token, command_token)

    # 7. Push cluster secrets if enabled
    if push_secrets:
        _push_cluster_secrets(effective_context)

    print_success(
        "Mattermost bootstrap complete: team, channels, webhooks, and slash commands configured."
    )
