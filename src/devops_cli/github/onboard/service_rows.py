"""Rows 7, 8 and 12 to 15: the Apps, the labels, the webhook, the Service, the cluster and the RAG
index. The labels, the webhook, `service.repos` and the RAG reads come from `devops roadmap
onboard` (#1359, #3771, #3772), which this command replaces.
"""

from __future__ import annotations

import json
import secrets
import sys
from typing import TYPE_CHECKING, Any, Final

import yaml
from pydantic import ValidationError

from devops_cli.ai.rag.indexer import rag_collection_names, resolve_qdrant_client
from devops_cli.ai.rag.ingest import visibility_from_payload
from devops_cli.config.constants import (
    CONST_CANONICAL_OCI_SOURCE,
    CONST_DEVOPS_CLI_ENTRY_MODULE,
    CONST_RENOVATE_GITHUB_APP_SLUG,
    CONST_ROADMAP_WEBHOOK_EVENTS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.labels import LabelSpec, diff_labels
from devops_cli.github.onboard.baseline import LABELS_FILE
from devops_cli.github.onboard.model import (
    DOC_DEPLOY,
    DOC_INSTALL_APP,
    DOC_SERVICES_ENTRY,
    DOC_WEBHOOKS,
    PersonStep,
    Row,
    RowContext,
    RowState,
)
from devops_cli.roadmap.title_labels import declared_label_specs
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS

if TYPE_CHECKING:
    from pathlib import Path

    from devops_cli.ai.rag.qdrant import QdrantClient
    from devops_cli.config.settings import Settings
    from devops_cli.github.app_installation import GitHubApp
    from devops_cli.github.client import RepositoryHook
    from devops_cli.github.onboard.baseline import Baseline
    from devops_cli.github.onboard.routes import RouteWriter
    from devops_cli.github.session import GitHubSession

_WEBHOOK_SECRETS: Final[str] = "service.webhook_secrets"
_ALL_EVENTS: Final[str] = "*"
_SERVICE_SECRET: Final[str] = "devops/devops-cli"
_SERVICE_STACK: Final[str] = "devops"
_DEPLOY_TIMEOUT_SECONDS: Final[float] = 1800.0
_GIT_TIMEOUT_SECONDS: Final[float] = 120.0


def _write_state(writer: RouteWriter) -> RowState:
    return RowState.APPLIED if writer.confirm else RowState.PENDING


def configured_apps(settings: Settings) -> list[GitHubApp]:
    """The Apps whose ID, installation and key the configuration holds: the Service App and the
    Renovate App."""
    from devops_cli.config.settings import (
        get_renovate_github_app_private_key,
        get_service_github_app_private_key,
    )
    from devops_cli.github.app_installation import GitHubApp

    apps: list[GitHubApp] = []
    service = settings.service.github_app
    service_key = get_service_github_app_private_key(settings)
    if service.app_id and service.installation_id and service.slug and service_key:
        apps.append(
            GitHubApp(
                app_id=service.app_id,
                installation_id=service.installation_id,
                slug=service.slug,
                private_key=service_key,
            )
        )
    renovate = settings.renovate
    renovate_key = get_renovate_github_app_private_key(settings)
    if renovate.github_app_id and renovate.github_app_installation_id and renovate_key:
        apps.append(
            GitHubApp(
                app_id=renovate.github_app_id,
                installation_id=renovate.github_app_installation_id,
                slug=CONST_RENOVATE_GITHUB_APP_SLUG,
                private_key=renovate_key,
            )
        )
    return apps


def app_row(ctx: RowContext, settings: Settings) -> Row:
    """Row 7: each configured App is installed on the repository. The row only reads: every App
    of the account is installed on all of its repositories, so no step installs one."""
    from devops_cli.github.app_installation import repository_installed

    apps = configured_apps(settings)
    if not apps:
        return Row(
            7,
            "App check",
            RowState.NOT_READABLE,
            reason="no App ID, installation and key is set (service.github_app, renovate)",
        )
    absent = [app.slug for app in apps if not repository_installed(app, ctx.repo)]
    if not absent:
        return Row(7, "App check", RowState.PRESENT, reason=", ".join(app.slug for app in apps))
    steps = tuple(
        PersonStep(
            f"Add {ctx.repo} to the installation of the App {slug} in Settings > Applications. "
            "The App should hold all repositories of the account.",
            DOC_INSTALL_APP,
        )
        for slug in absent
    )
    return Row(
        7, "App check", RowState.PERSON, reason=f"not installed: {', '.join(absent)}", steps=steps
    )


def _label_specs(
    session: GitHubSession, ctx: RowContext, baseline: Baseline | None
) -> list[LabelSpec]:
    """The labels that the repository holds: those of the package and of `.github/labels.yml`,
    the file of the default branch, else the rendered file."""
    text = session.client.get_file_at(ctx.repo, LABELS_FILE, ctx.default_branch)
    if text is None and baseline is not None:
        text = baseline.files.get(LABELS_FILE)
    declared: list[LabelSpec] = []
    if text is not None:
        try:
            raw = yaml.safe_load(text)
            declared = declared_label_specs(text) if isinstance(raw, list) else []
        except yaml.YAMLError, ValidationError:
            declared = []
    names = {spec.name for spec in WORKFLOW_LABELS}
    return [*WORKFLOW_LABELS, *(spec for spec in declared if spec.name not in names)]


def labels_row(
    session: GitHubSession, writer: RouteWriter, ctx: RowContext, baseline: Baseline | None
) -> tuple[Row, tuple[str, ...]]:
    """Row 8: create each missing label; a label that differs stays. Gives the row and the names
    of the labels that differ."""
    desired = _label_specs(session, ctx, baseline)
    existing = list(session.paginate(f"/repos/{ctx.repo}/labels"))
    to_create, to_update, _ = diff_labels(desired, existing)
    differing = tuple(spec.name for spec in to_update)
    if not to_create:
        return Row(8, "Labels", RowState.PRESENT), differing
    for spec in to_create:
        writer.rest(
            "label",
            f"/repos/{ctx.repo}/labels",
            {"name": spec.name, "color": spec.color, "description": spec.description},
        )
    changes = tuple(f"create {spec.name}" for spec in to_create)
    return Row(8, "Labels", _write_state(writer), changes=changes), differing


def webhook_step(settings: Settings) -> PersonStep:
    """The step for a person that adds the repository webhook by hand. It names no secret."""
    events = ", ".join(sorted(CONST_ROADMAP_WEBHOOK_EVENTS))
    return PersonStep(
        f"Add the webhook {settings.service.webhook_url} with content type application/json and at "
        f"least the events {events}, set it active, and store its secret in "
        f"`devops config set {_WEBHOOK_SECRETS}`.",
        DOC_WEBHOOKS,
    )


def _sends_events(hook: RepositoryHook) -> bool:
    """Whether the hook sends each event that the Service takes; `*` sends every event (#6662)."""
    return _ALL_EVENTS in hook.events or set(CONST_ROADMAP_WEBHOOK_EVENTS) <= set(hook.events)


def _wrong_fields(hook: RepositoryHook) -> list[str]:
    """The fields of a hook of the Service URL that do not match."""
    wrong = [] if hook.active else ["active"]
    if hook.content_type != "json":
        wrong.append("content_type")
    if not _sends_events(hook):
        wrong.append("events")
    return wrong


def _stored_secrets(settings: Settings) -> dict[str, str]:
    """The keyring map of the webhook secrets, by repository."""
    from devops_cli.config.settings import get_service_webhook_secrets

    text = get_service_webhook_secrets(settings)
    if not text:
        return {}
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DevOpsCLIError(f"{_WEBHOOK_SECRETS} holds no JSON map: {exc.msg}") from None
    return (
        {str(key): str(value) for key, value in loaded.items()} if isinstance(loaded, dict) else {}
    )


def _hook_body(settings: Settings, secret: str) -> dict[str, Any]:
    """The body of the Service webhook, with its secret."""
    return {
        "name": "web",
        "active": True,
        "events": sorted(CONST_ROADMAP_WEBHOOK_EVENTS),
        "config": {
            "url": settings.service.webhook_url,
            "content_type": "json",
            "insecure_ssl": "0",
            "secret": secret,
        },
    }


def _store_secret(settings: Settings, repo: str, secret: str) -> None:
    """Put the secret of the hook of `repo` into the keyring map."""
    from devops_cli.config.settings import dotted_set

    stored = _stored_secrets(settings)
    stored[repo] = secret
    dotted_set(settings, _WEBHOOK_SECRETS, json.dumps(stored, sort_keys=True))


def webhook_row(
    session: GitHubSession, writer: RouteWriter, ctx: RowContext, settings: Settings
) -> Row:
    """Row 12: the repository webhook of the Service, until #4417. A missing hook gets `POST`, and
    a wrong hook or a hook whose secret the keyring map lacks gets `PATCH`, each with a new secret
    that goes into the keyring map and into no output."""
    name = "Webhook"
    try:
        hooks = session.client.get_repository_hooks(ctx.repo)
    except DevOpsCLIError as exc:
        return Row(
            12, name, RowState.NOT_READABLE, reason=exc.message, steps=(webhook_step(settings),)
        )
    url = settings.service.webhook_url
    hook = next((item for item in hooks if item.url == url), None)
    known = ctx.repo in _stored_secrets(settings)
    if hook is not None and not _wrong_fields(hook) and known:
        return Row(12, name, RowState.PRESENT)
    secret = secrets.token_hex(32)
    if hook is None:
        writer.rest("hook-create", f"/repos/{ctx.repo}/hooks", _hook_body(settings, secret))
        change = f"create the hook of {url}"
    else:
        writer.rest(
            "hook-update", f"/repos/{ctx.repo}/hooks/{hook.id}", _hook_body(settings, secret)
        )
        fields = _wrong_fields(hook) or ["secret"]
        change = f"update the hook of {url}: {', '.join(fields)}"
    writer.run("webhook-secret", lambda: _store_secret(settings, ctx.repo, secret))
    ctx.service_changed = True
    return Row(12, name, _write_state(writer), changes=(change, f"secret in {_WEBHOOK_SECRETS}"))


def _git(workdir: Path, *args: str) -> str | None:
    """The output of a git command in `workdir`, or None when it fails."""
    result = run_subprocess(["git", *args], cwd=workdir, timeout=_GIT_TIMEOUT_SECONDS, quiet=True)
    return result.stdout.strip() if result.returncode == 0 else None


def clean_main_reason(workdir: Path) -> str | None:
    """Why `workdir` is no clean checkout of `origin/main` of devops-cli, or None when it is one
    (D4). The fetch reads `origin/main` as it stands now."""
    from urllib.parse import urlsplit

    from devops_cli.core.repo import find_repo_root, get_repo_origin_name
    from devops_cli.github.repo_ref import RepoRef

    expected = RepoRef(urlsplit(CONST_CANONICAL_OCI_SOURCE).path.strip("/"))
    origin = get_repo_origin_name(find_repo_root(workdir))
    if origin is None or RepoRef(origin) != expected:
        return f"the working directory is no checkout of {expected.display}"
    if _git(workdir, "fetch", "--quiet", "origin", "main") is None:
        return "git fetch origin main failed"
    head, main = _git(workdir, "rev-parse", "HEAD"), _git(workdir, "rev-parse", "origin/main")
    if head is None or head != main:
        return "HEAD is not origin/main"
    status = _git(workdir, "status", "--porcelain")
    if status is None or status:
        count = len(status.splitlines()) if status else 0
        return f"the checkout has {count} changed files"
    return None


def _run_devops(workdir: Path, *args: str) -> None:
    """Run one devops command as a child of the person, or raise naming it."""
    argv = [sys.executable, "-P", "-m", CONST_DEVOPS_CLI_ENTRY_MODULE, *args]
    result = run_subprocess(
        argv, cwd=workdir, timeout=_DEPLOY_TIMEOUT_SECONDS, isolate_env=False, capture_output=False
    )
    if result.returncode != 0:
        raise DevOpsCLIError(f"devops {' '.join(args)} exited {result.returncode}.")


def _add_to_service_repos(settings: Settings, repo: str) -> None:
    """Add `repo` to `service.repos` in the config file."""
    from devops_cli.config.settings import save_settings

    settings.service.repos = [*settings.service.repos, repo]
    save_settings(settings, keys=("service.repos",))


_PUSH_ARGS: Final[tuple[str, ...]] = ("k8s", "push-secrets", "--only", _SERVICE_SECRET, "--rotate")
_DEPLOY_ARGS: Final[tuple[str, ...]] = ("k8s", "deploy-stack", "--stack", _SERVICE_STACK)
_DEPLOY_STEP: Final[str] = (
    "From a clean checkout of origin/main of devops-cli, run "
    f"`devops {' '.join(_PUSH_ARGS)}` and `devops {' '.join(_DEPLOY_ARGS)}`."
)


def service_row(writer: RouteWriter, ctx: RowContext, settings: Settings) -> Row:
    """Row 13 (D4): the repository in `service.repos`, then push-secrets and deploy-stack, only
    from a clean checkout of `origin/main` of devops-cli."""
    name = "Service"
    listed = ctx.repo in settings.service.repos
    if listed and not ctx.service_changed:
        return Row(13, name, RowState.PRESENT)
    changes = ([] if listed else [f"add {ctx.repo} to service.repos"]) + (
        [f"devops {' '.join(_PUSH_ARGS)}", f"devops {' '.join(_DEPLOY_ARGS)}"]
        if ctx.options.deploy
        else []
    )
    deploy_step = PersonStep(_DEPLOY_STEP, DOC_DEPLOY)
    if not writer.confirm:
        return Row(13, name, RowState.PENDING, changes=tuple(changes))
    reason = clean_main_reason(ctx.options.workdir)
    if reason is not None:
        step = PersonStep(
            f"Add {ctx.repo} to service.repos with `devops config set service.repos`, then: "
            f"{_DEPLOY_STEP}",
            DOC_DEPLOY,
        )
        return Row(13, name, RowState.REFUSED, reason=reason, steps=(step,))
    if not listed:
        writer.run("service-repos", lambda: _add_to_service_repos(settings, ctx.repo))
    if not ctx.options.deploy:
        return Row(13, name, RowState.APPLIED, changes=tuple(changes), steps=(deploy_step,))
    writer.run("push-secrets", lambda: _run_devops(ctx.options.workdir, *_PUSH_ARGS))
    writer.run("deploy-stack", lambda: _run_devops(ctx.options.workdir, *_DEPLOY_ARGS))
    return Row(13, name, RowState.APPLIED, changes=tuple(changes))


def cluster_row(ctx: RowContext) -> Row:
    """Row 14: with `--service`, the services entry of the repository in the environment
    repository, which only a person merges. Its values belong to the service repository."""
    if not ctx.options.service:
        return Row(14, "Cluster", RowState.SKIPPED, reason="no --service")
    step = PersonStep(
        f"Add the services entry k8s/services/{ctx.options.repo.name}.yaml of {ctx.repo} to the "
        "environment repository, and merge its pull request.",
        DOC_SERVICES_ENTRY,
    )
    return Row(14, "Cluster", RowState.PERSON, steps=(step,))


def _first_point(qdrant: QdrantClient, collection: str, repo: str) -> dict[str, Any] | None:
    """One point of `repo` in `collection`, or None when the collection holds none."""
    points = qdrant.scroll_points(
        collection, filter_payload={"project_name": repo}, limit=1, with_payload=True
    )
    return points[0] if points else None


def _count_points(qdrant: QdrantClient, settings: Settings, repo: str) -> tuple[int, int]:
    """The points of `repo` in the code collection and in the docs collection."""
    code_collection, docs_collection = rag_collection_names(settings)
    return (
        qdrant.count_points(code_collection, filter_payload={"project_name": repo}),
        qdrant.count_points(docs_collection, filter_payload={"project_name": repo}),
    )


def _index_lines(
    repo: str, settings: Settings, payload: dict[str, Any] | None
) -> tuple[list[str], bool]:
    """The `indexed`, `rag visibility` and `rag schedule` lines, and whether the index is current:
    both collections hold points with the visibility that GitHub returns (#3771). A count raises
    `DevOpsCLIError` when the store cannot be read."""
    qdrant = resolve_qdrant_client(settings=settings)
    code, docs = _count_points(qdrant, settings, repo)
    counts = f"code {code}, docs {docs}"
    indexed = "present" if code and docs else ("partial" if code or docs else "missing")
    lines = [f"indexed: {indexed}" + (f" ({counts})" if code or docs else "")]
    current = indexed == "present"
    if code or docs:
        code_collection, docs_collection = rag_collection_names(settings)
        point = _first_point(qdrant, code_collection if code else docs_collection, repo)
        value = ((point or {}).get("payload") or {}).get("visibility")
        recorded = str(value).lower() if value else None
        published = visibility_from_payload(payload) if payload else None
        if published is None:
            lines.append("rag visibility: not readable (the repository read failed)")
        elif recorded == published:
            lines.append(f"rag visibility: {published}")
        else:
            lines.append(
                f"rag visibility: mismatch (points {recorded or 'not recorded'}, github {published})"
            )
            current = False
    else:
        lines.append("rag visibility: not indexed")
    return lines, current


def rag_row(writer: RouteWriter, ctx: RowContext, settings: Settings) -> Row:
    """Row 15: the RAG index of the repository. With `--confirm` and a repository in
    `service.repos`, an index that is not current gets the ingestion pass of #1389 for that
    repository alone. The row informs only."""
    from devops_cli.ai.rag.ingest import run_ingest_pass

    name = "RAG"
    listed = ctx.repo in settings.service.repos
    schedule = "rag schedule: present" if listed else "rag schedule: missing (not in service.repos)"
    try:
        lines, current = _index_lines(ctx.repo, settings, ctx.repo_payload)
    except DevOpsCLIError as exc:
        return Row(
            15,
            name,
            RowState.NOT_READABLE,
            changes=(f"indexed: not readable ({exc.message})", schedule),
            informs_only=True,
        )
    lines.append(schedule)
    if current or not listed:
        return Row(
            15,
            name,
            RowState.PRESENT if current else RowState.SKIPPED,
            changes=tuple(lines),
            informs_only=True,
        )

    def ingest() -> tuple[int, int]:
        run_ingest_pass(repo_filter=[ctx.repo], settings=settings)
        return _count_points(resolve_qdrant_client(settings=settings), settings, ctx.repo)

    try:
        counts = writer.run("rag-pass", ingest)
    except DevOpsCLIError as exc:
        return Row(
            15, name, RowState.FAILED, changes=tuple(lines), reason=exc.message, informs_only=True
        )
    if counts is not None:
        lines.append(f"RAG points: code {counts[0]}, docs {counts[1]}")
    return Row(15, name, _write_state(writer), changes=tuple(lines), informs_only=True)


__all__ = [
    "app_row",
    "clean_main_reason",
    "cluster_row",
    "configured_apps",
    "labels_row",
    "rag_row",
    "service_row",
    "webhook_row",
    "webhook_step",
]
