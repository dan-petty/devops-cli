"""RAG repository ingestion pass for managed repositories (#1389)."""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.rag.indexer import WorkspaceIndexer, resolve_rag_components
from devops_cli.ai.rag.qdrant import QdrantClientError
from devops_cli.config.constants import CONST_GH_CLI, CONST_GIT_CLI
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.paths import is_forbidden_system_path, safe_resolve_subpath
from devops_cli.core.repo import resolve_data_path
from devops_cli.exceptions import (
    ConfigurationError,
    DevOpsCLIError,
    GitOperationError,
)
from devops_cli.exceptions.ai import RagIngestError
from devops_cli.output.file_writer import write_json_file
from devops_cli.telemetry.instruments import (
    RAG_INGEST_LAST_SUCCESS_TIMESTAMP,
    RAG_INGEST_RUNS_TOTAL,
    emit,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    """The result of ingesting a single repository."""

    repo: str
    head: str
    branch: str
    visibility: str
    success: bool
    skipped: bool = False


def resolve_repo_paths(data_dir: Path, repo: str) -> tuple[Path, Path, Path]:
    """Validate repository slug and resolve data paths under repos/<owner>/<name>."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GitOperationError(f"Invalid repository format (expected 'owner/name'): {repo}")
    owner, name = parts
    if owner.startswith(("/", "\\", ".")) or name.startswith(("/", "\\", ".")):
        raise GitOperationError(f"Invalid repository slug components: '{repo}'")

    root = (data_dir / "repos").resolve()
    repo_dir = safe_resolve_subpath(root, Path(owner) / name, error_cls=GitOperationError)
    if is_forbidden_system_path(repo_dir):
        raise GitOperationError(
            f"Target repository path resolves to forbidden system path: {repo_dir}"
        )

    tree_dir = safe_resolve_subpath(repo_dir, "tree", error_cls=GitOperationError)
    state_file = repo_dir / "state.json"
    return repo_dir, tree_dir, state_file


_resolve_repo_paths = resolve_repo_paths


def read_repo_visibility(repo: str, gh_runner: Any) -> str:
    """Read repository visibility from GitHub API, counting public as public and others as private."""
    owner, name = repo.split("/")
    res = gh_runner([CONST_GH_CLI, "api", f"repos/{owner}/{name}"], check=False, quiet=True)
    if res.returncode != 0:
        return "private"
    try:
        stdout_text = res.stdout if isinstance(res.stdout, str) else ""
        data = json.loads(stdout_text or "{}")
        raw_vis = str(data.get("visibility", "")).lower()
        if raw_vis == "public":
            return "public"
        if "private" in data and not data["private"]:
            return "public"
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.debug("Failed to parse GitHub repo payload for %s: %s", repo, exc)
    return "private"


_read_repo_visibility = read_repo_visibility


def _parse_ls_remote(output: str) -> tuple[str, str]:
    """Parse default branch and HEAD commit hash from git ls-remote output."""
    branch = "main"
    head = ""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("ref:"):
            tokens = line.split()
            if len(tokens) >= 2 and tokens[1].startswith("refs/heads/"):
                branch = tokens[1].removeprefix("refs/heads/")
        elif "\tHEAD" in line or line.endswith(" HEAD"):
            head = line.split()[0].strip()
    return branch, head


def _sync_shallow_checkout(tree_dir: Path, url: str, branch: str, git_runner: Any) -> None:
    """Clone or fetch shallow single-branch checkout at tree_dir."""
    tree_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (tree_dir / ".git").exists():
        git_runner(
            [
                CONST_GIT_CLI,
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--no-tags",
                url,
                str(tree_dir),
            ],
            check=True,
            quiet=True,
        )
    else:
        git_runner(
            [CONST_GIT_CLI, "fetch", "--depth", "1", "origin", branch],
            cwd=tree_dir,
            check=True,
            quiet=True,
        )
        git_runner(
            [CONST_GIT_CLI, "checkout", "--detach", "FETCH_HEAD"],
            cwd=tree_dir,
            check=True,
            quiet=True,
        )


def cleanup_removed_repos(
    rag_dir: Path,
    configured_repos: set[str],
    indexer: WorkspaceIndexer,
) -> None:
    """Purge points and local state for repositories removed from service.repos."""
    repos_dir = rag_dir / "repos"
    if not repos_dir.is_dir():
        return

    for state_file in sorted(repos_dir.glob("*/*/state.json")):
        name = state_file.parent.name
        owner = state_file.parent.parent.name
        proj = f"{owner}/{name}"
        if proj not in configured_repos:
            logger.info("Cleaning up removed repository '%s'", proj)
            try:
                indexer.qdrant.delete_points_by_project(indexer.code_collection, proj, wait=True)
                indexer.qdrant.delete_points_by_project(indexer.docs_collection, proj, wait=True)
            except (QdrantClientError, DevOpsCLIError) as exc:
                logger.warning("Failed to delete points for removed repository '%s': %s", proj, exc)
            shutil.rmtree(state_file.parent, ignore_errors=True)


_cleanup_removed_repos = cleanup_removed_repos


def load_repo_state(state_file: Path) -> dict[str, Any]:
    """Read JSON state file if present."""
    if state_file.exists():
        try:
            content = state_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Failed reading state file %s: %s", state_file, exc)
    return {}


_load_repo_state = load_repo_state


def update_points_visibility(
    indexer: WorkspaceIndexer,
    repo: str,
    visibility: str,
) -> None:
    """Rewrite visibility payload field on project points in both collections."""
    for coll in (indexer.code_collection, indexer.docs_collection):
        try:
            indexer.qdrant.set_payload(
                coll,
                {"visibility": visibility},
                filter_payload={"project_name": repo},
                wait=True,
            )
        except (QdrantClientError, DevOpsCLIError) as exc:
            logger.warning("Failed rewriting visibility for %s in %s: %s", repo, coll, exc)


_update_points_visibility = update_points_visibility


def ingest_repository(
    repo: str,
    *,
    data_dir: Path,
    remote_url: str | None = None,
    git_runner: Any = None,
    gh_runner: Any = None,
    indexer: WorkspaceIndexer | None = None,
    settings: Settings | None = None,
) -> IngestResult:
    """Execute ingestion pass for one repository."""
    if git_runner is None:
        from devops_cli.core.process import run_subprocess

        git_runner = run_subprocess
    if gh_runner is None:
        from devops_cli.github.rate_limiter import run_gh

        gh_runner = run_gh
    if indexer is None:
        settings = settings or load_settings()
        components = resolve_rag_components(settings=settings)
        indexer = WorkspaceIndexer(
            qdrant=components.qdrant,
            embedder=components.embedder,
            code_collection=components.code_collection,
            docs_collection=components.docs_collection,
            cache_dir=data_dir,
        )

    repo_dir, tree_dir, state_file = resolve_repo_paths(data_dir, repo)
    state = load_repo_state(state_file)

    repo_indexer = WorkspaceIndexer(
        qdrant=indexer.qdrant,
        embedder=indexer.embedder,
        code_collection=indexer.code_collection,
        docs_collection=indexer.docs_collection,
        cache_dir=repo_dir,
    )

    visibility = read_repo_visibility(repo, gh_runner)
    if "visibility" in state and state["visibility"] != visibility:
        update_points_visibility(indexer, repo, visibility)

    url = remote_url or f"https://github.com/{repo}.git"
    ls_res = git_runner(
        [CONST_GIT_CLI, "ls-remote", "--symref", url, "HEAD"], check=True, quiet=True
    )
    raw_output = getattr(ls_res, "stdout", "") or ""
    branch, head = _parse_ls_remote(raw_output)

    if not head:
        write_json_file(
            state_file,
            {
                "head": "",
                "branch": branch,
                "visibility": visibility,
                "empty": True,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            atomic=True,
        )
        return IngestResult(
            repo=repo, head="", branch=branch, visibility=visibility, success=True, skipped=True
        )

    recorded_head = state.get("head")
    intact = repo_indexer.points_intact(repo)
    if recorded_head == head and intact:
        if state.get("visibility") != visibility:
            write_json_file(
                state_file,
                {**state, "visibility": visibility, "timestamp": datetime.now(UTC).isoformat()},
                atomic=True,
            )
        return IngestResult(
            repo=repo, head=head, branch=branch, visibility=visibility, success=True, skipped=True
        )

    _sync_shallow_checkout(tree_dir, url, branch, git_runner)

    repo_indexer.index_workspace(
        tree_dir,
        project=repo,
        force=(not intact),
        include_kb=False,
        visibility=visibility,
    )

    write_json_file(
        state_file,
        {
            "head": head,
            "branch": branch,
            "visibility": visibility,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        atomic=True,
    )
    return IngestResult(repo=repo, head=head, branch=branch, visibility=visibility, success=True)


def _validate_target_repos(
    repos: list[str] | None,
    repo_filter: list[str] | None,
    settings: Settings,
) -> tuple[list[str], list[str]]:
    """Validate settings and return configured repos and target repos."""
    if not settings.qdrant.url:
        raise ConfigurationError(
            "No Qdrant vector store URL configured. Run: devops config set qdrant.url <url>",
            key="qdrant.url",
        )

    configured_repos = list(repos if repos is not None else settings.service.repos)
    if not configured_repos:
        raise ConfigurationError(
            "No repositories configured in service.repos. Run: devops config set service.repos '[\"owner/repo\"]'",
            key="service.repos",
        )

    if repo_filter:
        for r in repo_filter:
            if r not in configured_repos:
                raise ConfigurationError(
                    f"Repository '{r}' is not configured in service.repos",
                    key="service.repos",
                )
        targets = [r for r in configured_repos if r in repo_filter]
    else:
        targets = configured_repos

    return configured_repos, targets


def _build_default_indexer(
    settings: Settings,
    rag_dir: Path,
    code_collection: str | None,
) -> WorkspaceIndexer:
    """Build default WorkspaceIndexer with resolved RAG components."""
    components = resolve_rag_components(settings=settings)
    return WorkspaceIndexer(
        qdrant=components.qdrant,
        embedder=components.embedder,
        code_collection=code_collection or components.code_collection,
        docs_collection=code_collection or components.docs_collection,
        cache_dir=rag_dir,
    )


def run_ingest_pass(
    repos: list[str] | None = None,
    *,
    repo_filter: list[str] | None = None,
    remote_urls: dict[str, str] | None = None,
    settings: Settings | None = None,
    data_dir: Path | None = None,
    git_runner: Any = None,
    gh_runner: Any = None,
    indexer: WorkspaceIndexer | None = None,
    code_collection: str | None = None,
) -> list[IngestResult]:
    """Execute complete ingestion pass over configured repositories."""
    settings = settings or load_settings()
    configured_repos, targets = _validate_target_repos(repos, repo_filter, settings)
    rag_dir = data_dir or resolve_data_path(settings.data.rag_dir)

    if indexer is None:
        indexer = _build_default_indexer(settings, rag_dir, code_collection)

    cleanup_removed_repos(rag_dir, set(configured_repos), indexer)

    results: list[IngestResult] = []
    failed_repos: list[str] = []

    for repo in targets:
        remote_url = remote_urls.get(repo) if remote_urls else None
        with trace_span("ai.rag.ingest", attributes={"rag.repo": repo, "repo": repo}):
            try:
                res = ingest_repository(
                    repo,
                    data_dir=rag_dir,
                    remote_url=remote_url,
                    git_runner=git_runner,
                    gh_runner=gh_runner,
                    indexer=indexer,
                    settings=settings,
                )
                results.append(res)
                now_ts = time.time()
                emit(RAG_INGEST_LAST_SUCCESS_TIMESTAMP, now_ts, {"repo": repo})
                GLOBAL_METRICS.increment_counter(
                    "devops_cli_rag_ingest_runs_total",
                    value=1.0,
                    labels={"repo": repo, "result": "success"},
                )
                emit(RAG_INGEST_RUNS_TOTAL, 1.0, {"repo": repo, "result": "success"})
            except Exception as exc:
                GLOBAL_METRICS.increment_counter(
                    "devops_cli_rag_ingest_runs_total",
                    value=1.0,
                    labels={"repo": repo, "result": "error"},
                )
                emit(RAG_INGEST_RUNS_TOTAL, 1.0, {"repo": repo, "result": "error"})
                if isinstance(exc, ConfigurationError):
                    logger.error("Repository '%s' failed: %s", repo, exc)
                else:
                    logger.error("Repository '%s' failed: %s", repo, exc, exc_info=True)
                failed_repos.append(repo)

    if failed_repos:
        raise RagIngestError(f"RAG ingestion failed for repositories: {', '.join(failed_repos)}")

    return results
