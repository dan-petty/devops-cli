"""Tests for managed repository RAG ingestion (#1389)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.ingest import ingest_repository, run_ingest_pass
from devops_cli.config.settings import AIConfig, Settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.ai import RagIngestError
from tests.support.fakes.qdrant import FakeQdrantClient

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


def _make_fake_gh_runner(visibility_map: dict[str, str]) -> Any:
    def _runner(cmd: list[str], **kwargs: Any) -> Any:
        res = MagicMock()
        # Expect cmd e.g. ["gh", "api", "repos/owner/name"]
        api_path = cmd[2] if len(cmd) > 2 else ""
        repo = api_path.replace("repos/", "")
        vis = visibility_map.get(repo, "public")
        res.returncode = 0
        res.stdout = json.dumps({"visibility": vis, "name": repo.split("/")[-1]})
        res.stderr = ""
        return res

    return _runner


def test_first_run_indexes_and_records_head(tmp_path: Path) -> None:
    bare = _make_bare_remote(tmp_path / "remote.git", {"file1.py": "def f(): pass\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"

    indexer = WorkspaceIndexer(
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert state["head"]
    assert state["visibility"] == "public"

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
    assert embedder.call_count == embed_calls_before


def test_removed_repository_cleanup_leaves_workstation_projects(tmp_path: Path) -> None:
    rag_dir = tmp_path / "rag"
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    indexer = WorkspaceIndexer(
        qdrant=fake_qdrant,  # type: ignore[arg-type]
        embedder=embedder,
        cache_dir=rag_dir,
    )

    # Pre-populate state for owner/removed-repo and owner/kept-repo
    for repo in ("owner/removed-repo", "owner/kept-repo"):
        state_dir = rag_dir / "repos" / repo
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "state.json").write_text(
            json.dumps({"head": "123", "branch": "main", "visibility": "public"})
        )

    # Seed points in Qdrant for both and a workstation project
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
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
    good_state = rag_dir / "repos" / "owner" / "good-repo" / "state.json"
    assert good_state.exists()


def test_push_edits_deletes_renames(tmp_path: Path) -> None:
    bare_dir = tmp_path / "repo.git"
    bare = _make_bare_remote(bare_dir, {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
    state = json.loads((rag_dir / "repos" / "owner" / "repo" / "state.json").read_text())
    assert state["branch"] == "trunk"


def test_pass_leaves_roadmap_clone_untouched(tmp_path: Path) -> None:
    bare = _make_bare_remote(tmp_path / "remote.git", {"file.py": "1\n"})
    fake_qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()
    rag_dir = tmp_path / "rag"
    indexer = WorkspaceIndexer(
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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

    state_file = rag_dir / "repos" / "owner" / "repo" / "state.json"
    assert not state_file.exists()

    embedder_ok = FixedVectorEngine()
    indexer_ok = WorkspaceIndexer(
        qdrant=fake_qdrant,  # type: ignore[arg-type]
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
    assert state_file.exists()
