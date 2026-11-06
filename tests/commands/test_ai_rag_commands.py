"""`devops ai rag`: arguments, output and exit codes, over the Qdrant, embedder and web fakes."""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.core.command_resolver import resolve_devops_argv
from devops_cli.lang import MESSAGES
from tests.support.embedding_replies import ollama_reply, serve
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.qdrant import seed_chunk, seed_knowledge_base

pytestmark = pytest.mark.usefixtures("keyring_store")

RAG = ("ai", "rag")


@pytest.fixture(autouse=True)
def _workspace_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in the test's directory: the index cache is a relative `.data/rag` of the working dir."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def kb_ready(qdrant: Any, embedder: Any) -> None:
    """Hold the installed knowledge base's digest in the store, so a query does not rebuild it."""
    seed_knowledge_base(qdrant, embedding_model=embedder.model)


def _app(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text("def run_app():\n    print('app running')\n", encoding="utf-8")
    return tmp_path


def test_index_dry_run_prints_the_plan_and_makes_no_request(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    result = cli("--dry-run", *RAG, "index", str(_app(tmp_path)))

    assert (result.exit_code, "Plan for AI RAG index" in result.output) == (0, True)
    assert (qdrant.calls, embedder.calls) == ([], [])


def test_query_dry_run_prints_the_plan_and_makes_no_request(
    cli: Callable[..., Any], qdrant: Any, embedder: Any
) -> None:
    result = cli("--dry-run", *RAG, "query", "how to deploy pods")

    assert (result.exit_code, "Plan for AI RAG query" in result.output) == (0, True)
    assert (qdrant.calls, embedder.calls) == ([], [])


def test_status_lists_each_collection_with_its_points(
    cli: Callable[..., Any], qdrant: Any, embedder: Any
) -> None:
    for number in range(3):
        seed_chunk(qdrant, embedder, f"def f{number}(): pass", file_path=f"src/f{number}.py")

    result = cli(*RAG, "status")

    assert result.exit_code == 0
    assert "RAG Vector Store Status" in result.output
    assert "devops_code" in result.output
    assert "fake-embed-model" in result.output
    assert "3" in result.output


def test_clear_deletes_both_collections(
    cli: Callable[..., Any], qdrant: Any, embedder: Any
) -> None:
    seed_chunk(qdrant, embedder, "def f(): pass")
    qdrant.ensure_collection("devops_docs", 4)

    result = cli(*RAG, "clear", "--force")

    assert result.exit_code == 0
    assert "Cleared collection" in result.output
    assert qdrant.collections == {}


def test_a_missing_qdrant_address_stops_each_command_with_the_setting_to_set(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, tmp_path: Path
) -> None:
    config = isolate_devops_cli_config
    config.write_text(
        config.read_text(encoding="utf-8").replace("qdrant:\n  url: http://localhost:6333\n", ""),
        encoding="utf-8",
    )

    results = [
        cli(*RAG, "index", str(tmp_path)),
        cli(*RAG, "index-kb"),
        cli(*RAG, "query", "run_app"),
        cli(*RAG, "status"),
        cli(*RAG, "clear", "--force"),
    ]

    assert [
        (result.exit_code, "devops config set qdrant.url <url>" in result.output)
        for result in results
    ] == [(1, True)] * 5


def test_index_stores_the_workspace_and_reports_it(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    result = cli(*RAG, "index", str(_app(tmp_path)), "--project", "test_proj", "--no-include-kb")

    assert result.exit_code == 0
    assert "Indexed 1 files" in result.output
    assert {p["payload"]["project_name"] for p in qdrant.collections["devops_code"]} == {
        "test_proj"
    }


def test_index_reports_the_files_it_pruned(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    workspace = _app(tmp_path)
    (workspace / "gone.py").write_text("def gone(): pass\n", encoding="utf-8")
    cli(*RAG, "index", str(workspace), "--no-include-kb")
    (workspace / "gone.py").unlink()

    result = cli(*RAG, "index", str(workspace), "--no-include-kb")

    assert (result.exit_code, "pruned 1 stale chunks" in result.output) == (0, True)


def test_index_kb_stores_the_knowledge_base(
    cli: Callable[..., Any], qdrant: Any, embedder: Any
) -> None:
    result = cli(*RAG, "index-kb")

    assert result.exit_code == 0
    assert "Knowledge Base indexing complete" in result.output
    assert len(qdrant.collections["devops_docs"]) > 0


@pytest.mark.usefixtures("kb_ready")
def test_query_prints_the_matches(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    cli(*RAG, "index", str(_app(tmp_path)), "--no-include-kb")

    result = cli(*RAG, "query", "run_app", "--top-k", "3")

    assert result.exit_code == 0
    assert "RAG Semantic Search" in result.output
    assert "app.py" in result.output


@pytest.mark.usefixtures("kb_ready")
def test_query_by_category_searches_one_collection(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    cli(*RAG, "index", str(_app(tmp_path)), "--no-include-kb")
    qdrant.calls.clear()

    result = cli(*RAG, "query", "run_app", "--category", "code")

    searched = {call[1][0] for call in qdrant.calls if call[0] == "search_points"}
    assert (result.exit_code, searched) == (0, {"devops_code"})


@pytest.mark.usefixtures("kb_ready")
def test_query_without_a_match_warns(cli: Callable[..., Any], qdrant: Any, embedder: Any) -> None:
    result = cli(*RAG, "query", "run_app", "--collection", "devops_code")

    assert (result.exit_code, "No matching code/documentation" in result.output) == (0, True)


def test_explain_prints_the_explanation(cli: Callable[..., Any]) -> None:
    assert cli(*RAG, "--explain").exit_code == 0


def test_index_of_a_missing_path_exits_1(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    assert cli(*RAG, "index", str(tmp_path / "nonexistent_dir")).exit_code == 1


def test_an_unreachable_qdrant_tip_names_a_deploy_command_the_cli_accepts(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """`index` and `index-kb` print the one Qdrant tip, and its quoted command resolves.

    The tip read `devops k8s deploy-stack llm`, which deploy-stack rejects: it takes the stack
    only as `--stack`.
    """
    qdrant.refusing = True
    results = [cli(*RAG, "index", str(tmp_path)), cli(*RAG, "index-kb")]

    tip = MESSAGES.rag.cannot_connect_qdrant.format(url=qdrant.base_url)
    quoted = shlex.split(shlex.split(tip)[-1])
    assert (
        [result.exit_code for result in results],
        ["devops k8s deploy-stack --stack llm" in result.output for result in results],
        quoted,
        resolve_devops_argv(quoted[1:]),
    ) == ([1, 1], [True, True], ["devops", "k8s", "deploy-stack", "--stack", "llm"], None)


MODEL_ERROR = "Embedding model m produced no embeddings: x answered HTTP 400"


@pytest.mark.usefixtures("kb_ready")
def test_index_and_query_fail_with_the_embedding_error(
    cli: Callable[..., Any], tmp_path: Path, embedder: Any
) -> None:
    """Index and query exit 1 with the error, and no traceback."""
    embedder.fail(MODEL_ERROR)

    results = [cli(*RAG, "index", str(_app(tmp_path))), cli(*RAG, "query", "run_app")]

    assert [(r.exit_code, MODEL_ERROR in r.output, type(r.exception)) for r in results] == [
        (1, True, SystemExit)
    ] * 2


def test_index_kb_fails_with_the_embedding_error(
    cli: Callable[..., Any], qdrant: Any, embedder: Any
) -> None:
    embedder.fail(MODEL_ERROR)

    result = cli(*RAG, "index-kb")

    assert (result.exit_code, MODEL_ERROR in result.output, type(result.exception)) == (
        1,
        True,
        SystemExit,
    )


def test_drift_of_an_unindexed_workspace_fails_on_demand_and_reports_json(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any, process_fake: ProcessFake
) -> None:
    process_fake.answer("git", ProcessAnswer(returncode=128, stderr="not a git repository"))

    result = cli(*RAG, "drift", str(_app(tmp_path)), "--fail-on-drift", "--json")

    data = json.loads(result.output)
    assert (result.exit_code, data["new_files"], data["drift_score"] > 0) == (1, ["app.py"], True)


def test_drift_of_an_indexed_workspace_is_clean(
    cli: Callable[..., Any], tmp_path: Path, qdrant: Any, embedder: Any, process_fake: ProcessFake
) -> None:
    process_fake.answer("git", ProcessAnswer(returncode=128, stderr="not a git repository"))
    workspace = _app(tmp_path)
    cli(*RAG, "index", str(workspace), "--no-include-kb")

    result = cli(*RAG, "drift", str(workspace), "--fail-on-drift")

    assert (result.exit_code, "RAG Index Drift" in result.output, "Clean" in result.output) == (
        0,
        True,
        True,
    )


def test_drift_with_auto_sync_indexes_what_changed(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    tmp_path: Path,
    qdrant: Any,
    web: WebFake,
    process_fake: ProcessFake,
) -> None:
    process_fake.answer("git", ProcessAnswer(returncode=128, stderr="not a git repository"))
    config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
    serve(web, ollama_reply)

    result = cli(*RAG, "drift", str(_app(tmp_path)), "--auto-sync")

    assert (result.exit_code, "Auto-synced 1 file(s)" in result.output) == (0, True)
    assert {p["payload"]["file_path"] for p in qdrant.collections["devops_code"]} == {"app.py"}


def test_drift_with_auto_sync_fails_with_the_embedding_error(
    cli: Callable[..., Any],
    tmp_path: Path,
    qdrant: Any,
    web: WebFake,
    config: Callable[..., Any],
    process_fake: ProcessFake,
) -> None:
    process_fake.answer("git", ProcessAnswer(returncode=128, stderr="not a git repository"))
    config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
    serve(web, lambda request: httpx2.Response(400, json={"error": "bad request"}))

    result = cli(*RAG, "drift", str(_app(tmp_path)), "--auto-sync")

    assert (result.exit_code, "answered HTTP 400" in result.output) == (1, True)
