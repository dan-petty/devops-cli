"""Tests for managed repository RAG ingestion (#1389)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.ingest import (
    cleanup_removed_repos,
    ingest_repository,
    read_repo_visibility,
    resolve_repo_paths,
    run_ingest_pass,
    update_points_visibility,
)
from devops_cli.ai.rag.qdrant import QdrantClientError
from devops_cli.config.settings import AIConfig, Settings
from devops_cli.exceptions import ConfigurationError, GitOperationError
from devops_cli.exceptions.ai import RagIngestError
from tests.support.fakes.qdrant import FakeQdrantClient

if TYPE_CHECKING:
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")


class FixedVectorEngine(EmbeddingsEngine):
    """An engine whose model answers every text with the same unit vector."""

    def __init__(self, *, fail_after: int | None = None) -> None:
        super().__init__(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)
        self.model = "test-model"
        self.fail_after = fail_after
        self.call_count = 0

    @property
    def dimension(self) -> int:
        return 4

    def _dispatch_embed(self, prefixed_miss: list[str]) -> list[list[float]]:
        self.call_count += len(prefixed_miss)
        if self.fail_after is not None and self.call_count > self.fail_after:
            raise RuntimeError("Embedder error halfway")
        return [[1.0, 0.0, 0.0, 0.0] for _ in prefixed_miss]


def _make_bare_remote(bare_dir: Path, files: dict[str, str], branch: str = "main") -> Path:
    bare_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", f"--initial-branch={branch}"],
        cwd=bare_dir,
        check=True,
        capture_output=True,
    )
    work_dir = bare_dir.parent / f"work_{bare_dir.name}"
    work_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", f"--initial-branch={branch}"],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=work_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=work_dir, check=True)
    for path_str, content in files.items():
        p = work_dir / path_str
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=work_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "commit 1"], cwd=work_dir, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{bare_dir}"],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    return bare_dir


class _ProcResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_fake_gh_runner(visibility_map: dict[str, str]) -> Any:
    def _runner(cmd: list[str], **kwargs: Any) -> Any:
        # Expect cmd e.g. ["gh", "api", "repos/owner/name"]
        api_path = cmd[2] if len(cmd) > 2 else ""
        repo = api_path.replace("repos/", "")
        vis = visibility_map.get(repo, "public")
        stdout = json.dumps({"visibility": vis, "name": repo.split("/")[-1]})
        return _ProcResult(returncode=0, stdout=stdout, stderr="")

    return _runner


def _run_collection() -> str:
    return f"devops_code_test_{uuid4().hex[:12]}"


def _indexed_repository_counts(
    qdrant: FakeQdrantClient, collection: str, repos: list[str]
) -> dict[str, int]:
    return {repo: qdrant.count_points(collection, {"project_name": repo}) for repo in repos}


def _assert_repositories_indexed(repos: list[str], counts: dict[str, int]) -> None:
    """Raise unless every repository of `repos` holds at least one indexed point."""
    missing = [repo for repo in repos if counts.get(repo, 0) < 1]
    if missing:
        raise AssertionError("RAG index has no point for: " + ", ".join(missing))


def _make_three_remotes(tmp_path: Path) -> dict[str, str]:
    """Build one bare git remote per fixture repository, as `owner/<name>`."""
    remote_urls: dict[str, str] = {}
    for name in ("alpha", "beta", "gamma"):
        bare = _make_bare_remote(tmp_path / f"{name}.git", {"module.py": "def f(): pass\n"})
        remote_urls[f"owner/{name}"] = f"file://{bare}"
    return remote_urls


def _run_coverage_pass(
    data_dir: Path,
    collection: str,
    repos: list[str],
    remote_urls: dict[str, str],
    qdrant: FakeQdrantClient,
) -> dict[str, int]:
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, qdrant),
        embedder=FixedVectorEngine(),
        code_collection=collection,
        cache_dir=data_dir,
    )
    settings = Settings(
        service={"repos": repos},
        qdrant={"url": "http://example.com:6333"},
        data={"rag_dir": data_dir},
    )
    run_ingest_pass(
        settings=settings,
        data_dir=data_dir,
        remote_urls=remote_urls,
        gh_runner=_make_fake_gh_runner({repo: "public" for repo in repos}),
        indexer=indexer,
    )
    return _indexed_repository_counts(qdrant, collection, repos)


def test_first_run_indexes_and_records_head(tmp_path: Path) -> None:
    bare = _make_bare_remote(tmp_path / "remote.git", {"file1.py": "def f(): pass\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"

    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )

    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    res = ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )
    assert res.success is True

    state_file = rag_dir / "repos" / "owner" / "repo" / "state.json"
    assert not state_file.exists()
    stored = indexer.read_project_state("owner/repo")
    assert stored["head"] == res.head
    assert stored["branch"] == "main"
    assert stored["visibility"] == "public"

    # Second run at same head makes no embedding calls
    embed_calls_before = embedder.call_count
    res2 = ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )
    assert res2.success is True
    assert res2.skipped is True
    assert embedder.call_count == embed_calls_before


def test_removed_repository_cleanup_leaves_workstation_projects(tmp_path: Path) -> None:
    rag_dir = tmp_path / "rag"
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )

    # Seed points in Qdrant for removed repo, kept repo, and a workstation project (no state.json)
    fake_qdrant.ensure_collection("devops_code", vector_size=4)
    fake_qdrant.ensure_collection("devops_docs", vector_size=4)
    pts = [
        {
            "id": "p1",
            "vector": [1.0, 0.0, 0.0, 0.0],
            "payload": {
                "project_name": "owner/removed-repo",
                "embedding_model": embedder.model,
            },
        },
        {
            "id": "p2",
            "vector": [1.0, 0.0, 0.0, 0.0],
            "payload": {
                "project_name": "owner/kept-repo",
                "embedding_model": embedder.model,
            },
        },
        {
            "id": "p3",
            "vector": [1.0, 0.0, 0.0, 0.0],
            "payload": {
                "project_name": "workstation-app",
                "embedding_model": embedder.model,
            },
        },
    ]
    fake_qdrant.upsert_points("devops_code", pts)

    settings = Settings(
        service={"repos": ["owner/kept-repo"]},
        qdrant={"url": "http://example.com:6333"},
        data={"rag_dir": rag_dir},
    )

    bare = _make_bare_remote(tmp_path / "kept.git", {"a.py": "x=1\n"})
    gh_runner = _make_fake_gh_runner({"owner/kept-repo": "public"})

    run_ingest_pass(
        settings=settings,
        data_dir=rag_dir,
        remote_urls={"owner/kept-repo": f"file://{bare}"},
        gh_runner=gh_runner,
        indexer=indexer,
    )

    # owner/removed-repo points were purged
    assert fake_qdrant.count_points("devops_code", {"project_name": "owner/removed-repo"}) == 0
    # workstation project remains
    assert fake_qdrant.count_points("devops_code", {"project_name": "workstation-app"}) == 1
    # kept-repo remains
    assert fake_qdrant.count_points("devops_code", {"project_name": "owner/kept-repo"}) >= 1
    # state file for removed repo is deleted
    assert not (rag_dir / "repos" / "owner" / "removed-repo" / "state.json").exists()


def test_empty_service_repos_fails_before_requests_and_cleanup(tmp_path: Path) -> None:
    rag_dir = tmp_path / "rag"
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )

    # State file exists
    state_dir = rag_dir / "repos" / "owner" / "old-repo"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    state_file.write_text(json.dumps({"head": "123", "branch": "main", "visibility": "public"}))

    settings = Settings(
        service={"repos": []},
        qdrant={"url": "http://example.com:6333"},
        data={"rag_dir": rag_dir},
    )

    with pytest.raises(ConfigurationError) as exc_info:
        run_ingest_pass(settings=settings, data_dir=rag_dir, indexer=indexer)

    assert "service.repos" in str(exc_info.value)
    # State file was NOT cleaned up
    assert state_file.exists()


def test_repo_option_outside_service_repos_fails_before_request(tmp_path: Path) -> None:
    settings = Settings(
        service={"repos": ["owner/configured-repo"]},
        qdrant={"url": "http://example.com:6333"},
        data={"rag_dir": tmp_path / "rag"},
    )
    with pytest.raises(ConfigurationError) as exc_info:
        run_ingest_pass(
            repo_filter=["owner/not-configured"],
            settings=settings,
            data_dir=tmp_path / "rag",
        )
    assert "owner/not-configured" in str(exc_info.value)


def test_unset_qdrant_url_fails_before_clone(tmp_path: Path) -> None:
    settings = Settings(
        service={"repos": ["owner/configured-repo"]},
        qdrant={"url": None},
        data={"rag_dir": tmp_path / "rag"},
    )
    with pytest.raises(ConfigurationError) as exc_info:
        run_ingest_pass(
            settings=settings,
            data_dir=tmp_path / "rag",
        )
    assert "qdrant.url" in str(exc_info.value)


def test_visibility_change_rewrites_payload_and_updates_search(tmp_path: Path) -> None:
    bare = _make_bare_remote(tmp_path / "remote.git", {"pub.py": "def foo(): pass\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )

    # First run: public
    gh_runner_pub = _make_fake_gh_runner({"owner/repo": "public"})
    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner_pub,
        indexer=indexer,
    )

    pts = fake_qdrant.collections["devops_code"]
    assert pts[0]["payload"]["visibility"] == "public"

    # Second run at same head: now private
    gh_runner_priv = _make_fake_gh_runner({"owner/repo": "private"})
    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner_priv,
        indexer=indexer,
    )

    # Points updated to private
    pts = fake_qdrant.collections["devops_code"]
    assert pts[0]["payload"]["visibility"] == "private"


def test_failed_repository_continues_and_reports_error(tmp_path: Path) -> None:
    bare_ok = _make_bare_remote(tmp_path / "ok.git", {"ok.py": "val=1\n"})
    rag_dir = tmp_path / "rag"
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )

    settings = Settings(
        service={"repos": ["owner/bad-repo", "owner/good-repo"]},
        qdrant={"url": "http://example.com:6333"},
        data={"rag_dir": rag_dir},
    )

    gh_runner = _make_fake_gh_runner({"owner/bad-repo": "public", "owner/good-repo": "public"})

    with pytest.raises(RagIngestError, match="owner/bad-repo"):
        run_ingest_pass(
            settings=settings,
            data_dir=rag_dir,
            remote_urls={
                "owner/bad-repo": "file:///nonexistent/path/repo.git",
                "owner/good-repo": f"file://{bare_ok}",
            },
            gh_runner=gh_runner,
            indexer=indexer,
        )

    # good repo was still indexed despite bad repo failing first!
    assert indexer.read_project_state("owner/good-repo")["head"]
    assert not (rag_dir / "repos" / "owner" / "good-repo" / "state.json").exists()


def test_push_edits_deletes_renames(tmp_path: Path) -> None:
    bare_dir = tmp_path / "repo.git"
    bare = _make_bare_remote(bare_dir, {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    # Run 1: initial index
    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )

    pts = fake_qdrant.collections["devops_code"]
    paths = {p["payload"]["file_path"] for p in pts}
    assert paths == {"a.py", "b.py"}

    # Push to bare remote: edit a.py, delete b.py, create c.py
    work_repo = tmp_path / f"work_{bare_dir.name}"
    (work_repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    (work_repo / "b.py").unlink()
    (work_repo / "c.py").write_text("z = 3\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=work_repo, check=True)
    subprocess.run(["git", "commit", "-m", "edit, delete, add"], cwd=work_repo, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=work_repo, check=True)

    # Run 2: incremental update
    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )

    pts2 = fake_qdrant.collections["devops_code"]
    paths2 = {p["payload"]["file_path"] for p in pts2}
    assert "b.py" not in paths2
    assert "a.py" in paths2
    assert "c.py" in paths2


def test_emptied_collection_causes_reindex(tmp_path: Path) -> None:
    bare = _make_bare_remote(tmp_path / "remote.git", {"main.py": "print(1)\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )
    assert len(fake_qdrant.collections["devops_code"]) >= 1

    # Empty points in collection
    fake_qdrant.collections["devops_code"].clear()

    # Re-running must detect missing points and re-index
    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )
    assert len(fake_qdrant.collections["devops_code"]) >= 1


def test_renamed_default_branch(tmp_path: Path) -> None:
    bare_dir = tmp_path / "remote.git"
    bare = _make_bare_remote(bare_dir, {"app.py": "pass\n"}, branch="main")
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )

    # In work repo, create branch 'trunk' and push
    work_repo = tmp_path / f"work_{bare_dir.name}"
    subprocess.run(["git", "checkout", "-b", "trunk"], cwd=work_repo, check=True)
    (work_repo / "app.py").write_text("pass # updated\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=work_repo, check=True)
    subprocess.run(["git", "commit", "-m", "trunk branch"], cwd=work_repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "trunk"], cwd=work_repo, check=True)

    # Point bare remote HEAD to refs/heads/trunk
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", "refs/heads/trunk"],
        cwd=bare,
        check=True,
    )

    res = ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )
    assert res.branch == "trunk"
    assert indexer.read_project_state("owner/repo")["branch"] == "trunk"
    assert not (rag_dir / "repos" / "owner" / "repo" / "state.json").exists()


def test_pass_leaves_roadmap_clone_untouched(tmp_path: Path) -> None:
    bare = _make_bare_remote(tmp_path / "remote.git", {"file.py": "1\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder,
        cache_dir=rag_dir,
    )
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    # Setup dummy roadmap clone
    roadmap_clone = rag_dir.parent / "roadmap" / "owner" / "repo" / "clone"
    roadmap_clone.mkdir(parents=True, exist_ok=True)
    marker = roadmap_clone / "sentinel.txt"
    marker.write_text("do-not-touch", encoding="utf-8")

    ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )

    assert marker.exists()
    assert marker.read_text(encoding="utf-8") == "do-not-touch"


def test_embedding_failure_halfway_records_no_head_and_resumes(tmp_path: Path) -> None:
    bare = _make_bare_remote(
        tmp_path / "remote.git",
        {"f1.py": "def a(): pass\n", "f2.py": "def b(): pass\n", "f3.py": "def c(): pass\n"},
    )
    rag_dir = tmp_path / "rag"
    fake_qdrant = FakeQdrantClient()
    embedder_fail = FixedVectorEngine(fail_after=1)
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder_fail,
        cache_dir=rag_dir,
    )
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    with pytest.raises(RuntimeError, match="Embedder error halfway"):
        ingest_repository(
            "owner/repo",
            data_dir=rag_dir,
            remote_url=f"file://{bare}",
            gh_runner=gh_runner,
            indexer=indexer,
        )

    assert indexer.read_project_state("owner/repo") == {}

    embedder_ok = FixedVectorEngine()
    indexer_ok = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=embedder_ok,
        cache_dir=rag_dir,
    )
    res = ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer_ok,
    )
    assert res.success is True
    assert indexer.read_project_state("owner/repo")["head"] == res.head
    assert not (rag_dir / "repos" / "owner" / "repo" / "state.json").exists()


def test_resolve_repo_paths_invalid(tmp_path: Path) -> None:
    with pytest.raises(GitOperationError, match="Invalid repository format"):
        resolve_repo_paths(tmp_path, "not-a-slug")

    with pytest.raises(GitOperationError, match="Invalid repository slug components"):
        resolve_repo_paths(tmp_path, "../repo")

    with pytest.raises(GitOperationError, match="Invalid repository slug components"):
        resolve_repo_paths(tmp_path, "owner/.hidden")


def test_read_repo_visibility_edge_cases() -> None:
    class _ProcResult:
        def __init__(self, returncode: int, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout

    # Error exit code
    assert read_repo_visibility("owner/repo", lambda cmd, **kwargs: _ProcResult(1)) == "private"

    # Invalid JSON
    assert (
        read_repo_visibility("owner/repo", lambda cmd, **kwargs: _ProcResult(0, "not json"))
        == "private"
    )

    # Private boolean false -> public
    assert (
        read_repo_visibility(
            "owner/repo", lambda cmd, **kwargs: _ProcResult(0, json.dumps({"private": False}))
        )
        == "public"
    )


def test_cleanup_removed_repos_qdrant_error(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repos" / "owner" / "old-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    class FailingDeleteQdrant(FakeQdrantClient):
        def delete_points_by_project(
            self,
            name: str,
            project_name: str,
            batch_size: int = 100,
            wait: bool = True,
        ) -> bool:
            raise QdrantClientError("delete failed")

    fake_qdrant = FailingDeleteQdrant()
    fake_qdrant.ensure_collection("devops_code", vector_size=4)
    fake_qdrant.upsert_points(
        "devops_code",
        [
            {
                "id": "old-1",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"project_name": "owner/old-repo"},
            }
        ],
    )
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=FixedVectorEngine(),
        cache_dir=tmp_path,
    )
    # Should log warning and not raise
    cleanup_removed_repos(tmp_path, {"owner/new-repo"}, indexer)
    assert not repo_dir.exists()


def test_update_points_visibility_qdrant_error(tmp_path: Path) -> None:
    called = []

    class FailingPayloadQdrant(FakeQdrantClient):
        def set_payload(
            self,
            name: str,
            payload: dict[str, Any],
            filter_payload: dict[str, Any] | None = None,
            *,
            wait: bool = True,
        ) -> bool:
            called.append(name)
            raise QdrantClientError("set_payload failed")

    indexer = WorkspaceIndexer(
        qdrant=cast(Any, FailingPayloadQdrant()),
        embedder=FixedVectorEngine(),
        cache_dir=tmp_path,
    )
    # Should log warning and not raise
    update_points_visibility(indexer, "owner/repo", "public")
    assert len(called) == 2


def test_ingest_empty_repository(tmp_path: Path) -> None:
    bare = tmp_path / "empty.git"
    bare.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=bare, check=True, capture_output=True)

    rag_dir = tmp_path / "rag"
    fake_qdrant = FakeQdrantClient()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant),
        embedder=FixedVectorEngine(),
        cache_dir=rag_dir,
    )
    gh_runner = _make_fake_gh_runner({"owner/empty": "public"})
    res = ingest_repository(
        "owner/empty",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer,
    )
    assert res.skipped is True
    assert res.head == ""


def test_run_ingest_pass_catches_repo_failure(tmp_path: Path) -> None:
    settings = Settings.model_validate(
        {
            "service": {"repos": ["owner/bad", "owner/good"]},
            "data": {"rag_dir": str(tmp_path)},
            "qdrant": {"url": "http://localhost:6333"},
        }
    )

    def failing_git_runner(cmd: list[str], **kwargs: Any) -> Any:
        if any("owner/bad" in arg for arg in cmd):
            raise GitOperationError("network down")
        return subprocess.CompletedProcess(cmd, 0, stdout="ref: refs/heads/main\tHEAD\n", stderr="")

    gh_runner = _make_fake_gh_runner({"owner/bad": "public", "owner/good": "public"})
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, FakeQdrantClient()),
        embedder=FixedVectorEngine(),
        cache_dir=tmp_path,
    )

    with pytest.raises(RagIngestError, match="RAG ingestion failed for repositories: owner/bad"):
        run_ingest_pass(
            settings=settings,
            data_dir=tmp_path,
            indexer=indexer,
            git_runner=failing_git_runner,
            gh_runner=gh_runner,
        )


def test_run_ingest_pass_updates_last_success_timestamp(
    tmp_path: Path, otlp: FakeCollector
) -> None:
    from devops_cli.telemetry.instruments import RAG_INGEST_LAST_SUCCESS_TIMESTAMP

    settings = Settings.model_validate(
        {
            "service": {"repos": ["owner/repo"]},
            "data": {"rag_dir": str(tmp_path)},
            "qdrant": {"url": "http://localhost:6333"},
        }
    )

    def empty_git_runner(cmd: list[str], **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(cmd, 0, stdout="ref: refs/heads/main\tHEAD\n", stderr="")

    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, FakeQdrantClient()),
        embedder=FixedVectorEngine(),
        cache_dir=tmp_path,
    )

    results = run_ingest_pass(
        settings=settings,
        data_dir=tmp_path,
        indexer=indexer,
        git_runner=empty_git_runner,
        gh_runner=gh_runner,
    )
    assert len(results) == 1
    found = [
        (val, labels)
        for labels, val in otlp.points(RAG_INGEST_LAST_SUCCESS_TIMESTAMP.name)
        if labels.get("repo") == "owner/repo"
    ]
    assert len(found) == 1
    val, labels = found[0]
    assert val > 0
    assert labels == {"repo": "owner/repo"}


def test_ingest_pass_indexes_each_managed_repository(tmp_path: Path) -> None:
    """One pass over three remotes leaves a point for each configured repository."""
    remote_urls = _make_three_remotes(tmp_path)
    repos = list(remote_urls)
    qdrant = FakeQdrantClient()
    collection = _run_collection()
    data_dir = tmp_path / "rag"

    try:
        counts = _run_coverage_pass(data_dir, collection, repos, remote_urls, qdrant)
        _assert_repositories_indexed(repos, counts)
        for repo in repos:
            assert counts[repo] >= 1
    finally:
        qdrant.delete_collection(collection)
        assert collection not in qdrant.list_collections()


def test_coverage_assertion_names_the_repository_with_no_point() -> None:
    repos = ["owner/alpha", "owner/beta", "owner/gamma"]

    with pytest.raises(AssertionError) as exc_info:
        _assert_repositories_indexed(repos, {"owner/alpha": 3, "owner/beta": 1})
    message = str(exc_info.value)
    assert "owner/gamma" in message
    assert "owner/alpha" not in message
    assert "owner/beta" not in message

    with pytest.raises(AssertionError) as zero_info:
        _assert_repositories_indexed(repos, {"owner/alpha": 3, "owner/beta": 0, "owner/gamma": 2})
    zero_message = str(zero_info.value)
    assert "owner/beta" in zero_message
    assert "owner/alpha" not in zero_message
    assert "owner/gamma" not in zero_message


def test_ingest_pass_leaves_no_run_collection(tmp_path: Path) -> None:
    """Two runs on one fake client give the same counts and leave no collection behind."""
    remote_urls = _make_three_remotes(tmp_path)
    repos = list(remote_urls)
    qdrant = FakeQdrantClient()
    run_counts: list[dict[str, int]] = []
    run_collections: list[str] = []

    for run_name in ("run1", "run2"):
        data_dir = tmp_path / run_name
        collection = _run_collection()
        run_collections.append(collection)
        try:
            run_counts.append(_run_coverage_pass(data_dir, collection, repos, remote_urls, qdrant))
        finally:
            qdrant.delete_collection(collection)

    assert run_counts[0] == run_counts[1]
    _assert_repositories_indexed(repos, run_counts[0])
    listed = qdrant.list_collections()
    for collection in run_collections:
        assert collection not in listed


def test_every_written_point_carries_the_repository_project_name(tmp_path: Path) -> None:
    """The pass names each point `owner/name`, never the directory that it runs in (#3771)."""
    bare = _make_bare_remote(
        tmp_path / "remote.git",
        {"src/main.py": "def f():\n    return 1\n", "README.md": "# Roadmap\n"},
    )
    worktree = tmp_path / "w-3566"
    worktree.mkdir()
    fake_qdrant = FakeQdrantClient()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant), embedder=FixedVectorEngine(), cache_dir=worktree
    )

    result = ingest_repository(
        "example/roadmap",
        data_dir=worktree,
        remote_url=f"file://{bare}",
        gh_runner=_make_fake_gh_runner({"example/roadmap": "private"}),
        indexer=indexer,
    )

    assert result.success is True
    points = [point for collection in fake_qdrant.collections.values() for point in collection]
    assert points
    assert {point["payload"]["project_name"] for point in points} == {"example/roadmap"}


def test_second_pass_in_new_data_folder_skips_clone_and_embedding(tmp_path: Path) -> None:
    """A new pod with an empty data folder skips clone and embed when Qdrant holds the head."""
    bare = _make_bare_remote(tmp_path / "remote.git", {"app.py": "def run():\n    return 1\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    rag_dir_1 = tmp_path / "pod1"
    indexer_1 = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant), embedder=embedder, cache_dir=rag_dir_1
    )
    first = ingest_repository(
        "owner/repo",
        data_dir=rag_dir_1,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=indexer_1,
    )
    assert first.skipped is False

    rag_dir_2 = tmp_path / "pod2"
    rag_dir_2.mkdir()
    git_calls: list[list[str]] = []
    embed_calls_before = embedder.call_count

    def _recording_git(cmd: list[str], **kwargs: Any) -> Any:
        git_calls.append(cmd)
        return subprocess.run(
            cmd, check=True, capture_output=True, text=True, cwd=kwargs.get("cwd")
        )

    indexer_2 = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant), embedder=embedder, cache_dir=rag_dir_2
    )
    second = ingest_repository(
        "owner/repo",
        data_dir=rag_dir_2,
        remote_url=f"file://{bare}",
        git_runner=_recording_git,
        gh_runner=gh_runner,
        indexer=indexer_2,
    )

    assert second.skipped is True
    assert second.head == first.head
    assert embedder.call_count == embed_calls_before
    assert not any("clone" in cmd for cmd in git_calls)
    assert not (rag_dir_2 / "repos" / "owner" / "repo" / "state.json").exists()


def test_reindexes_with_force_when_points_not_intact_at_same_head(tmp_path: Path) -> None:
    """When Qdrant points are lost at the same head, the pass clones and force-indexes."""
    import shutil

    bare = _make_bare_remote(tmp_path / "remote.git", {"app.py": "def run():\n    return 1\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    gh_runner = _make_fake_gh_runner({"owner/repo": "public"})

    rag_dir = tmp_path / "pod"
    first = ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        gh_runner=gh_runner,
        indexer=WorkspaceIndexer(
            qdrant=cast(Any, fake_qdrant), embedder=embedder, cache_dir=rag_dir
        ),
    )

    fake_qdrant.collections["devops_code"].clear()
    shutil.rmtree(rag_dir / "repos" / "owner" / "repo" / "tree")
    fake_qdrant.calls.clear()
    git_calls: list[list[str]] = []

    def _recording_git(cmd: list[str], **kwargs: Any) -> Any:
        git_calls.append(cmd)
        return subprocess.run(
            cmd, check=True, capture_output=True, text=True, cwd=kwargs.get("cwd")
        )

    second = ingest_repository(
        "owner/repo",
        data_dir=rag_dir,
        remote_url=f"file://{bare}",
        git_runner=_recording_git,
        gh_runner=gh_runner,
        indexer=WorkspaceIndexer(
            qdrant=cast(Any, fake_qdrant), embedder=embedder, cache_dir=rag_dir
        ),
    )

    assert second.skipped is False
    assert second.head == first.head
    assert any("clone" in cmd for cmd in git_calls)
    assert any(name == "delete_points_by_project" for name, _args, _kwargs in fake_qdrant.calls)
    assert fake_qdrant.count_points("devops_code", {"project_name": "owner/repo"}) >= 1


def test_failed_index_workspace_writes_no_head_payload(tmp_path: Path) -> None:
    """A failure in `index_workspace` writes no `head` field via `set_payload`."""
    bare = _make_bare_remote(
        tmp_path / "remote.git",
        {"f1.py": "def a(): pass\n", "f2.py": "def b(): pass\n"},
    )
    fake_qdrant = FakeQdrantClient()

    with pytest.raises(RuntimeError, match="Embedder error halfway"):
        ingest_repository(
            "owner/repo",
            data_dir=tmp_path / "pod",
            remote_url=f"file://{bare}",
            gh_runner=_make_fake_gh_runner({"owner/repo": "public"}),
            indexer=WorkspaceIndexer(
                qdrant=cast(Any, fake_qdrant),
                embedder=FixedVectorEngine(fail_after=1),
                cache_dir=tmp_path / "pod",
            ),
        )

    assert not any(
        name == "set_payload" and isinstance(args[1], dict) and "head" in args[1]
        for name, args, _kwargs in fake_qdrant.calls
    )


def test_cleanup_in_new_data_folder_respects_repo_filter_and_keeps_others(tmp_path: Path) -> None:
    """Cleanup in an empty data folder removes unlisted `owner/name` repos and respects `--repo`."""
    bare_a = _make_bare_remote(tmp_path / "a.git", {"a.py": "x = 1\n"})
    fake_qdrant = FakeQdrantClient()
    fake_qdrant.ensure_collection("devops_code", vector_size=4)
    fake_qdrant.ensure_collection("devops_docs", vector_size=4)
    fake_qdrant.upsert_points(
        "devops_code",
        [
            {
                "id": "1",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"project_name": "owner/a", "embedding_model": "test-model"},
            },
            {
                "id": "2",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"project_name": "owner/b", "embedding_model": "test-model"},
            },
            {
                "id": "3",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"project_name": "owner/gone", "embedding_model": "test-model"},
            },
            {
                "id": "4",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"project_name": "workstation-proj", "embedding_model": "test-model"},
            },
        ],
    )
    fake_qdrant.upsert_points(
        "devops_docs",
        [
            {
                "id": "5",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"project_name": "owner/gone", "embedding_model": "test-model"},
            }
        ],
    )

    rag_dir = tmp_path / "empty_pod"
    rag_dir.mkdir()
    settings = Settings(
        service={"repos": ["owner/a", "owner/b"]},
        qdrant={"url": "http://example.com:6333"},
        data={"rag_dir": rag_dir},
    )
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, fake_qdrant), embedder=FixedVectorEngine(), cache_dir=rag_dir
    )

    run_ingest_pass(
        repo_filter=["owner/a"],
        settings=settings,
        data_dir=rag_dir,
        remote_urls={"owner/a": f"file://{bare_a}"},
        gh_runner=_make_fake_gh_runner({"owner/a": "public"}),
        indexer=indexer,
    )

    assert fake_qdrant.count_points("devops_code", {"project_name": "owner/gone"}) == 0
    assert fake_qdrant.count_points("devops_docs", {"project_name": "owner/gone"}) == 0
    assert fake_qdrant.count_points("devops_code", {"project_name": "owner/b"}) == 1
    assert fake_qdrant.count_points("devops_code", {"project_name": "workstation-proj"}) == 1
