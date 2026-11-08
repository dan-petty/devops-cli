"""Kubernetes command group (cluster contexts, node status, manifest apply, pod logs, stack lifecycle, TLS, auditing, and diagnostics)."""

from __future__ import annotations

from devops_cli.commands.k8s.bootstrap import bootstrap
from devops_cli.commands.k8s.cluster_context import (
    apply,
    contexts,
    logs,
    render,
    status,
    switch_context,
)
from devops_cli.commands.k8s.cluster_jobs import run_job
from devops_cli.commands.k8s.cluster_secret_push import push_secrets
from devops_cli.commands.k8s.crawl4ai_check import k8s_crawl4ai_check
from devops_cli.commands.k8s.diagnostics import (
    chaos_cmd,
    diff_helm_cmd,
    doctor_cmd,
    pods_cmd,
    security_stream_cmd,
    stream_logs_cmd,
)
from devops_cli.commands.k8s.gpu_matrix import gpu_matrix_cmd
from devops_cli.commands.k8s.image_pins import k8s_image_pins
from devops_cli.commands.k8s.mattermost_bootstrap import bootstrap_mattermost
from devops_cli.commands.k8s.networking import (
    configure_urls,
    port_forward,
    port_forward_status,
    port_forward_stop,
    service_url,
)
from devops_cli.commands.k8s.ollama import app as ollama_app
from devops_cli.commands.k8s.searxng_check import k8s_searxng_check
from devops_cli.commands.k8s.security_audit import (
    k8s_audit,
    k8s_check_deprecated,
    k8s_lint,
    k8s_validate,
    rbac_audit,
    validate_policy_cmd,
)
from devops_cli.commands.k8s.stack_lifecycle import (
    bootstrap_openwebui,
    deploy_stack,
    sync_secrets,
    teardown_stack,
)
from devops_cli.commands.k8s.tls_management import (
    create_tls_secret,
    enable_tls_stack,
)
from devops_cli.commands.k8s.tunnel import app as tunnel_app
from devops_cli.commands.k8s.volume import app as volume_app
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

app = new_typer(help=HELP.k8s.app, no_args_is_help=True)

# Register subcommands
app.command()(contexts)
app.command("switch-context")(switch_context)
app.command()(status)
app.command()(apply)
app.command()(render)
app.command()(logs)
app.command("bootstrap", help=HELP.k8s.bootstrap)(bootstrap)
app.command("bootstrap-openwebui")(bootstrap_openwebui)
app.command("bootstrap-mattermost")(bootstrap_mattermost)
app.command("deploy-stack", help=HELP.k8s.deploy_stack)(deploy_stack)
app.command("sync-secrets")(sync_secrets)
app.command("push-secrets", help=HELP.k8s.push_secrets)(push_secrets)
app.command("run-job", help=HELP.k8s.run_job)(run_job)
app.command("configure-urls")(configure_urls)
app.command("service-url")(service_url)
app.command("port-forward")(port_forward)
app.command("port-forward-status")(port_forward_status)
app.command("port-forward-stop")(port_forward_stop)
app.command("teardown-stack")(teardown_stack)
app.command("rbac-audit")(rbac_audit)
app.command("lint")(k8s_lint)
app.command("audit")(k8s_audit)
app.command("check-deprecated")(k8s_check_deprecated)
app.command("image-pins")(k8s_image_pins)
app.command("crawl4ai-check")(k8s_crawl4ai_check)
app.command("searxng-check")(k8s_searxng_check)
app.command("create-tls-secret")(create_tls_secret)
app.command("enable-tls")(enable_tls_stack)
app.command("validate")(k8s_validate)
app.command(name="validate-policy")(validate_policy_cmd)
app.command(name="stream-logs")(stream_logs_cmd)
app.command(name="diff-helm")(diff_helm_cmd)
app.command(name="chaos")(chaos_cmd)
app.command(name="pods")(pods_cmd)
app.command(name="security-stream")(security_stream_cmd)
app.command(name="gpu-matrix")(gpu_matrix_cmd)
app.command(name="doctor")(doctor_cmd)
app.add_typer(ollama_app, name="ollama", help=HELP.k8s.ollama_app)
app.add_typer(tunnel_app, name="tunnel", help=HELP.k8s.tunnel_app)
app.add_typer(volume_app, name="volume", help=HELP.k8s.volume_app)


__all__ = ["app"]
