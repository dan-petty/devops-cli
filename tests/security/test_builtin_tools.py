"""Comprehensive unit tests for built-in workspace inspection and execution tools."""

from __future__ import annotations

import ipaddress
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai.tools.builtin_tools import (
    argo_apps,
    check_threat_intel,
    git_diff,
    git_status,
    k8s_pods,
    k8s_tempo_status,
    k8s_validate_manifests,
    list_files,
    rag_search,
    read_file,
    scan_bandit,
    scan_gitleaks,
    scan_iac,
    scan_kubelinter,
    scan_osv,
    scan_pluto,
    scan_popeye,
    scan_semgrep,
    scan_trivy,
    scan_uv_audit,
    search_code,
    tf_lint,
)
from devops_cli.config.defaults import DEFAULT_TOOL_DIFF_MAX_CHARS, DEFAULT_TRIVY_SEVERITIES
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.review.rules_pack import RULE_PACK_DIR
from devops_cli.security.tool_executor import KubeApiNetwork
from devops_cli.security.vulnerability_lookup import OSVClient, ShodanInternetDBClient
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.qdrant import FakeQdrantClient, seed_knowledge_base
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.registry_cache import CACHED_RULESET_FILE_NAME

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_path_outside_the_workspace_is_denied_and_so_is_a_link_out_of_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`read_file` and `list_files` read inside the workspace only. A symbolic link in the
    workspace that points outside it is outside, so the tools deny it."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    inside_file = workspace / "inside.txt"
    inside_file.write_text("in", encoding="utf-8")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("out", encoding="utf-8")
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("out", encoding="utf-8")
    (workspace / "link_in.txt").symlink_to(inside_file)
    (workspace / "link_out.txt").symlink_to(outside_file)
    (workspace / "link_out_dir").symlink_to(outside_dir)

    assert (
        read_file(str(inside_file)),
        read_file(str(workspace / "link_in.txt")),
        read_file(str(outside_file)),
        read_file(str(workspace / "link_out.txt")),
        list_files(str(outside_dir)),
        list_files(str(workspace / "link_out_dir")),
    ) == (
        "in",
        "in",
        ERRORS.tools.access_denied_outside_workspace.format(path=str(outside_file)),
        ERRORS.tools.access_denied_outside_workspace.format(path=str(workspace / "link_out.txt")),
        [],
        [],
    )


def test_a_tool_that_starts_a_process_replies_with_its_trimmed_output(
    process_fake: ProcessFake,
) -> None:
    """`git_status` runs `git status -s` and replies with what git printed, without the
    whitespace around it."""
    process_fake.answer("git status", ProcessAnswer(stdout=" M src/main.py\n"))

    reply = git_status()

    assert ([call.argv for call in process_fake.calls], reply) == (
        [("git", "status", "-s")],
        "M src/main.py",
    )


def test_a_tool_that_starts_a_process_names_a_clean_result_when_it_prints_nothing(
    process_fake: ProcessFake,
) -> None:
    """A command with no output gives the tool's own sentence, not an empty reply."""
    process_fake.answer("git", ProcessAnswer(stdout=""))

    assert (git_status(), git_diff()) == (
        MESSAGES.tools.working_tree_clean,
        MESSAGES.tools.no_unstaged_changes,
    )


def test_a_tool_that_starts_a_process_cuts_a_long_reply_and_says_where(
    process_fake: ProcessFake,
) -> None:
    """`git_diff` keeps the first `DEFAULT_TOOL_DIFF_MAX_CHARS` characters and ends the reply
    with a line that says where it cut."""
    process_fake.answer("git diff", ProcessAnswer(stdout="A" * (DEFAULT_TOOL_DIFF_MAX_CHARS + 50)))

    assert git_diff() == (
        "A" * DEFAULT_TOOL_DIFF_MAX_CHARS
        + f"\n... [truncated at {DEFAULT_TOOL_DIFF_MAX_CHARS} chars]"
    )


def test_a_tool_that_cannot_start_its_program_replies_with_the_failure(
    process_fake: ProcessFake,
) -> None:
    """A program that is not installed gives a reply that names it and the cause."""
    process_fake.answer("git status", ProcessAnswer(side_effect=OSError("Executable not found")))

    assert git_status() == ERRORS.tools.tool_execution_failed.format(
        tool="git", exc="Executable not found"
    )


def test_list_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify list_files traverses non-hidden files up to 2 directory levels."""
    monkeypatch.chdir(tmp_path)

    # Create directory structure
    (tmp_path / "file1.txt").touch()
    (tmp_path / ".hidden").touch()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.pyc").touch()

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "file2.txt").touch()
    (sub / ".subhidden").touch()

    sub_deep = sub / "deep"
    sub_deep.mkdir()
    (sub_deep / "file3.txt").touch()

    files = list_files(str(tmp_path))
    assert "file1.txt" in files
    assert "sub/file2.txt" in files
    assert ".hidden" not in files
    assert "sub/.subhidden" not in files
    assert "__pycache__/cached.pyc" not in files

    # Outside workspace path returns empty list
    outside = tmp_path.parent / "outside_dir"
    assert list_files(str(outside)) == []


def test_read_file_paging_and_safety(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify read_file with offset, max_bytes paging, EOF check, and workspace safety."""
    monkeypatch.chdir(tmp_path)

    target_file = tmp_path / "sample.txt"
    target_file.write_text("0123456789ABCDEF", encoding="utf-8")

    # Read full file
    assert read_file(str(target_file)) == "0123456789ABCDEF"

    # Paging with max_bytes
    page1 = read_file(str(target_file), offset=0, max_bytes=8)
    assert "01234567" in page1
    assert "Page ended at byte 8 of 16" in page1

    page2 = read_file(str(target_file), offset=8, max_bytes=8)
    assert page2 == "89ABCDEF"

    # Offset at or beyond EOF
    eof = read_file(str(target_file), offset=20)
    assert "beyond end of file" in eof

    # Non-existent file
    assert "File not found" in read_file(str(tmp_path / "nonexistent.txt"))

    # Outside workspace
    outside = tmp_path.parent / "secret.txt"
    assert "Access Denied" in read_file(str(outside))


def test_search_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify search_code scans text files and returns matching file paths."""
    monkeypatch.chdir(tmp_path)

    code_file = tmp_path / "app.py"
    code_file.write_text("def authenticate():\n    return True\n", encoding="utf-8")

    bin_file = tmp_path / "image.png"
    bin_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    matches = search_code("authenticate", str(tmp_path))
    assert matches == ["app.py"]

    # No match
    assert search_code("nonexistent_symbol", str(tmp_path)) == []


def test_the_cluster_tools_run_kubectl_and_argocd_with_their_arguments(
    process_fake: ProcessFake,
) -> None:
    """The Kubernetes and Argo CD tools, which run no scanner adapter, start the program with
    the namespace they are given."""
    k8s_pods("kube-system")
    k8s_tempo_status("default")
    argo_apps()

    assert [call.argv for call in process_fake.calls] == [
        ("kubectl", "get", "pods", "-n", "kube-system"),
        ("kubectl", "get", "deployments,statefulsets,services", "-n", "default"),
        ("argocd", "app", "list"),
    ]


def test_scan_osv_lists_the_advisories_that_osv_answers(web: WebFake) -> None:
    """`scan_osv` asks OSV.dev about the package and version, and lists each advisory with its
    severity and its fixed version."""
    web.respond(
        "POST",
        OSVClient.BASE_URL,
        200,
        {
            "vulns": [
                {
                    "id": "GHSA-abcd-1234",
                    "summary": "Sample vulnerability in pydantic",
                    "database_specific": {"severity": "HIGH"},
                }
            ]
        },
    )

    reply = scan_osv("pydantic", version="2.0.0")

    assert ([(request.method, request.url) for request in web.recorded], reply) == (
        [("POST", OSVClient.BASE_URL)],
        "Found 1 vulnerability record(s) for pydantic:\n"
        "- [GHSA-abcd-1234] Severity: HIGH | Fixed: None\n"
        "  Summary: Sample vulnerability in pydantic",
    )
    assert web.recorded[0].json == {
        "package": {"name": "pydantic", "ecosystem": "PyPI"},
        "version": "2.0.0",
    }


def test_check_threat_intel_replies_with_what_shodan_knows_about_a_public_address(
    web: WebFake,
) -> None:
    """The reply for a public address lists the open ports, the CVEs and the summary that
    Shodan InternetDB gives."""
    web.respond(
        "GET",
        f"{ShodanInternetDBClient.BASE_URL}/1.1.1.1",
        200,
        {
            "ip": "1.1.1.1",
            "ports": [53, 443],
            "vulns": [],
            "hostnames": ["one.one.one.one"],
            "tags": [],
        },
    )

    reply = check_threat_intel("1.1.1.1")

    assert (web.requested, reply) == (
        [f"{ShodanInternetDBClient.BASE_URL}/1.1.1.1"],
        "Shodan Intelligence for IP 1.1.1.1:\n"
        "- Hostnames: one.one.one.one\n"
        "- Open Ports: 53, 443\n"
        "- Known CVEs: None detected\n"
        "- Reputation Summary: Open ports detected: [53, 443]",
    )


def test_check_threat_intel_replies_with_what_radar_knows_about_a_domain(
    monkeypatch: pytest.MonkeyPatch, web: WebFake
) -> None:
    """The reply for a domain lists the categories that Cloudflare Radar gives, and the request
    carries the configured token."""
    monkeypatch.setenv("DEVOPS_CLI_CLOUDFLARE_API_TOKEN", "cf-test-token")
    url = "https://api.cloudflare.com/client/v4/radar/ranking/domain/service-domain.org"
    web.respond(
        "GET",
        url,
        200,
        {"success": True, "result": {"categories": [{"name": "Technology"}]}},
    )

    reply = check_threat_intel("service-domain.org")

    assert (
        [(request.method, request.url) for request in web.recorded],
        web.recorded[0].headers.get("authorization"),
        reply.splitlines()[:2],
    ) == (
        [("GET", url)],
        "Bearer cf-test-token",
        [
            "Cloudflare Radar Intelligence for Domain service-domain.org:",
            "- Threat Categories: Technology",
        ],
    )


# 0.0.0.0, the unspecified IPv4 address, as a value under test rather than a bind address.
_UNSPECIFIED_IPV4 = str(ipaddress.IPv4Address(0))


@pytest.mark.parametrize(
    "target",
    [
        "example.com",
        "192.0.2.1",
        "3fff::1",
        "555-0100",
        _UNSPECIFIED_IPV4,
        "::",
        f"http://{_UNSPECIFIED_IPV4}:8000",
        "3221225985",
    ],
)
def test_check_threat_intel_names_the_rfcs_of_every_target_it_excludes(
    target: str, web: WebFake
) -> None:
    """The reply names everything `is_example_or_invalid_network_target` excludes: example
    domains, documentation and benchmarking addresses, fictional phone numbers and the
    unspecified addresses, and not RFC 6890, whose reserved space is local. A documentation
    address in a numeric spelling a resolver dials (`3221225985` is 192.0.2.1) is excluded too.
    No service is asked (#1174)."""
    reply = check_threat_intel(target)
    assert (web.sent, reply) == (
        [],
        f"Target {target} is a documented example or an unspecified address: an example domain "
        "(RFC 2606 / RFC 6761), a documentation address (RFC 5737 / RFC 3849 / RFC 9637), a "
        "benchmarking address (RFC 2544 / RFC 5180), a fictional phone number (ATIS-0300115 / "
        "Ofcom drama numbers) or an unspecified address (RFC 1122 / RFC 4291). Excluded from "
        "external threat intelligence scanning.",
    )


@pytest.mark.parametrize(
    ("target", "address"),
    [
        ("224.0.0.1", "224.0.0.1"),
        ("100.64.0.1", "100.64.0.1"),
        ("192.88.99.1", "192.88.99.1"),
        ("::ffff:192.88.99.1", "192.88.99.1"),
        ("fec0::1", "fec0::1"),
        ("100.64.0.1.", "100.64.0.1"),
        ("224.0.0.1,", "224.0.0.1"),
        ("10.0.0.1.", "10.0.0.1"),
        ("2130706433", "127.0.0.1"),
        ("http://100.64.0.1./v1", "100.64.0.1"),
    ],
)
def test_check_threat_intel_asks_no_service_about_a_local_address(
    target: str, address: str, web: WebFake
) -> None:
    """Multicast, shared address space, 6to4 relay anycast in either spelling and site-local
    space are local, so neither Shodan nor Cloudflare Radar is asked, and the reply says so
    without calling the address a domain. That holds after a trailing punctuation mark, in a
    URL and in a numeric spelling a resolver dials (`2130706433` is 127.0.0.1). Multicast used to
    be in no class and went to Radar, as each punctuated address did; 6to4 relay anycast in its
    IPv4-mapped spelling and site-local space went to Shodan (#1174)."""
    reply = check_threat_intel(target)
    assert (web.sent, reply) == (
        [],
        f"Target {target} is a local address ({address}): private, loopback, link-local, shared, "
        "site-local, multicast or reserved space, which is not globally reachable. No threat "
        "intelligence service was asked.",
    )


@pytest.mark.parametrize("target", ["8.8.8.8.", "8.8.8.8,", "::ffff:8.8.8.8"])
def test_check_threat_intel_asks_shodan_about_the_address_the_target_names(
    target: str, web: WebFake
) -> None:
    """A public address is sent to Shodan InternetDB as the address it is, without the
    punctuation prose leaves after it and in its IPv4 spelling; a trailing dot used to send it
    to Cloudflare Radar's domain lookup (#1174)."""
    web.respond(
        "GET",
        f"{ShodanInternetDBClient.BASE_URL}/8.8.8.8",
        200,
        {"ip": "8.8.8.8", "ports": [], "vulns": [], "hostnames": [], "tags": []},
    )

    reply = check_threat_intel(target)

    assert (web.requested, reply.splitlines()[0]) == (
        [f"{ShodanInternetDBClient.BASE_URL}/8.8.8.8"],
        "Shodan Intelligence for IP 8.8.8.8:",
    )


def test_scan_osv_names_only_the_database_it_queries(web: WebFake) -> None:
    """`scan_osv` and the `security_intel_package` tool query OSV.dev alone, so neither their
    descriptions nor a clean reply mention NVD, which nothing queries (#956)."""
    from devops_cli.ai.mcp.server import security_intel_package

    web.respond("POST", OSVClient.BASE_URL, 200, {})

    clean = scan_osv("requests", "2.0.0")

    assert (
        clean,
        "NVD" in (scan_osv.__doc__ or ""),
        "NVD" in (security_intel_package.__doc__ or ""),
    ) == ("No known vulnerabilities found in OSV for requests (PyPI).", False, False)


def test_scan_osv_reports_a_failed_lookup_instead_of_a_clean_package(web: WebFake) -> None:
    """A lookup that cannot reach OSV.dev says so with the reason. It used to answer "No known
    vulnerabilities", which reads as a clean package (#956)."""
    import httpx2

    web.fail(OSVClient.BASE_URL, httpx2.ConnectError("connection refused"))

    reply = scan_osv("requests", "2.0.0")

    assert (reply, "No known vulnerabilities" in reply) == (
        "OSV lookup failed: connection refused",
        False,
    )


def _index_chunk(qdrant: FakeQdrantClient, embedder: FakeEmbedder, query: str) -> None:
    """Hold one code chunk in the store whose vector is the embedding of `query`, so a search
    for `query` finds it, and hold the knowledge base, so the search rebuilds nothing."""
    seed_knowledge_base(qdrant)
    qdrant.upsert_points(
        "devops_code",
        [
            {
                "id": "chunk-1",
                "vector": embedder.embed_query(query),
                "payload": {
                    "file_path": "src/retry.py",
                    "start_line": 3,
                    "end_line": 9,
                    "content": "def retry_policy():\n    return 3\n",
                    "language": "python",
                    "embedding_model": embedder.model,
                },
            }
        ],
    )


def test_rag_search_replies_with_the_chunks_the_store_holds(
    qdrant: FakeQdrantClient, embedder: FakeEmbedder, capsys: pytest.CaptureFixture[str]
) -> None:
    """The search embeds the query, finds the chunk whose vector is nearest, and names its file
    and lines. The knowledge base is current, so the search prints no rebuild line."""
    _index_chunk(qdrant, embedder, "where is the retry policy")
    embedded_before = len(embedder.recorded_texts)

    reply = rag_search("where is the retry policy")

    assert (
        "src/retry.py" in reply,
        "def retry_policy()" in reply,
        "Rebuilding knowledge base" in capsys.readouterr().out,
        embedder.recorded_texts[embedded_before:],
    ) == (True, True, False, [("where is the retry policy", True)])


def test_rag_search_rebuilds_a_knowledge_base_that_the_store_lacks(
    qdrant: FakeQdrantClient, embedder: FakeEmbedder, capsys: pytest.CaptureFixture[str]
) -> None:
    """A store that holds no knowledge base is rebuilt before the search, and the search says so."""
    rag_search("where is the retry policy")

    assert "Rebuilding knowledge base" in capsys.readouterr().out


def test_rag_search_passes_the_language_and_the_limit_to_the_store(
    qdrant: FakeQdrantClient, embedder: FakeEmbedder
) -> None:
    """Two chunks match the query equally. The `language` filter keeps the chunk in that language,
    and `top_k` caps the count of chunks."""
    query = "where is the retry policy"
    seed_knowledge_base(qdrant)
    for chunk_id, file_path, language in (
        ("py", "src/retry.py", "python"),
        ("go", "src/retry.go", "go"),
        ("go2", "src/backoff.go", "go"),
    ):
        qdrant.upsert_points(
            "devops_code",
            [
                {
                    "id": chunk_id,
                    "vector": embedder.embed_query(query),
                    "payload": {
                        "file_path": file_path,
                        "start_line": 1,
                        "end_line": 2,
                        "content": f"retry in {language}\n",
                        "language": language,
                        "embedding_model": embedder.model,
                    },
                }
            ],
        )

    by_language = rag_search(query, language="go")
    by_limit = rag_search(query, top_k=1)

    assert (
        "src/retry.py" in by_language,
        "src/retry.go" in by_language,
        by_limit.count("<chunk"),
    ) == (False, True, 1)


def test_rag_search_reports_an_empty_result(
    qdrant: FakeQdrantClient, embedder: FakeEmbedder
) -> None:
    """A store with no chunk near the query gives the reply that names the query."""
    seed_knowledge_base(qdrant)

    assert rag_search("test query") == "No semantic matches found in vector store for: test query"


def test_rag_search_reports_a_store_that_is_down(
    qdrant: FakeQdrantClient, embedder: FakeEmbedder
) -> None:
    """A store that refuses the connection gives the reply that names its address and the
    fallback tool. The search does not wait."""
    qdrant.refusing = True

    assert rag_search("test query") == (
        "RAG vector database unavailable at http://example.com:6333. Fallback: use search_code."
    )


def test_rag_search_names_an_embedding_failure(
    qdrant: FakeQdrantClient, embedder: FakeEmbedder
) -> None:
    """A query the embedding model cannot embed returns the failure, as an unreachable store
    does."""
    seed_knowledge_base(qdrant)
    embedder.fail(
        "Embedding model bge-m3:latest produced no embeddings: "
        "https://example.com/v1/embeddings answered HTTP 400: model not loaded"
    )

    reply = rag_search("where is the retry policy")

    assert reply == (
        "RAG search unavailable: Embedding model bge-m3:latest produced no embeddings: "
        "https://example.com/v1/embeddings answered HTTP 400: model not loaded. "
        "Fallback: use search_code."
    )


def test_rag_search_names_the_setting_a_missing_store_address_needs(
    embedder: FakeEmbedder, config: Callable[..., Path]
) -> None:
    """With no Qdrant address configured and no store installed, the reply names the setting
    and the fallback tool, and asks no service."""
    config(qdrant={"url": None})

    reply = rag_search("test query")

    assert reply == (
        "RAG vector database unconfigured (qdrant.url is not set). Fallback: use search_code."
    )


def _semgrep_directory_scan(target: Path, *configs: str) -> list[str]:
    """The Semgrep command that the agent tool runs over a directory with `configs`: the
    adapter's, with the rule pack, and with the directories of dependencies and data left out."""
    return [
        "semgrep",
        "scan",
        "--json",
        "--metrics",
        "off",
        "--disable-version-check",
        "--jobs",
        "4",
        *(arg for config in (*configs, str(RULE_PACK_DIR)) for arg in ("--config", config)),
        "--disable-nosem",
        *("--exclude", ".venv", "--exclude", "venv", "--exclude", "node_modules"),
        *("--exclude", ".data", "--exclude", "repos", "--exclude", ".git"),
        "--quiet",
        str(target.resolve()),
    ]


def test_the_agent_popeye_tool_runs_the_popeye_adapter_over_the_namespace(
    scanner_fake: ScannerFake,
) -> None:
    """`scan_popeye` runs Popeye through its adapter, at warn level over the namespace, with the
    network profile `kube-api`, from a new empty directory that does not stay (#2132), and replies
    with the outcome of the scan (#1434)."""
    scanner_fake.snapshot_workdirs = True
    recorded = scanner_fake.script_run_with_findings("popeye")

    reply = scan_popeye("argocd")

    deployment = "argocd/argocd-applicationset-controller"
    pod = "argocd/argocd-application-controller-0"
    fix_deployment = f"(Review and adjust Kubernetes specification for {deployment})"
    fix_pod = f"(Review and adjust Kubernetes specification for {pod})"
    (run,) = scanner_fake.runs
    assert (
        run.argv,
        run.workdir_files,
        Path(run.cwd).exists(),
        [request.network for request in scanner_fake.requests],
        reply,
    ) == (
        recorded.argv,
        {},
        False,
        [KubeApiNetwork()],
        "\n".join(
            [
                "Popeye scan status: ok",
                "Findings (6):",
                f"- [MEDIUM] k8s:deployments/{deployment}: [POP-500] Zero scale detected "
                f"{fix_deployment}",
                f"- [MEDIUM] k8s:deployments/{deployment}/applicationset-controller: "
                f"[POP-106] No resources requests/limits defined {fix_deployment}",
                f"- [HIGH] k8s:deployments/{deployment}: [POP-508] No pods match controller "
                "selector: app.kubernetes.io/name=argocd-applicationset-controller,"
                f"app.kubernetes.io/instance=argocd {fix_deployment}",
                f"- [MEDIUM] k8s:pods/{pod}/application-controller: [POP-103] No liveness probe "
                f"{fix_pod}",
                f"- [MEDIUM] k8s:pods/{pod}: [POP-301] Connects to API Server? ServiceAccount "
                f"token is mounted {fix_pod}",
                f"- [MEDIUM] k8s:pods/{pod}: [POP-110] Memory Current/Request (791Mi/256Mi) "
                f"reached user 80% threshold (308%) {fix_pod}",
            ]
        ),
    )


def test_the_agent_uv_audit_tool_runs_the_uv_audit_adapter_over_the_directory(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`scan_uv_audit` runs uv audit through its adapter, over the lockfile of the project in the
    directory as it is, and replies with the outcome of the scan (#2106)."""
    monkeypatch.chdir(tmp_path)
    recorded = scanner_fake.script_run_with_findings("uv", tree=tmp_path.resolve())

    reply = scan_uv_audit(str(tmp_path))

    assert (scanner_fake.runs, reply) == (
        [recorded],
        "\n".join(
            [
                "uv audit scan status: ok",
                "Findings (4):",
                "- [MEDIUM] uv.lock:idna: [GHSA-65pc-fj4g-8rjx] Internationalized Domain Names in "
                "Applications (IDNA): Specially crafted inputs to idna.encode() can bypass "
                "CVE-2024-3651 fix (Upgrade idna from 3.6 to 3.15)",
                "- [MEDIUM] uv.lock:idna: [GHSA-jjg7-2v4v-x38h] Internationalized Domain Names in "
                "Applications (IDNA) vulnerable to denial of service from specially crafted "
                "inputs to idna.encode (Upgrade idna from 3.6 to 3.7)",
                "- [MEDIUM] uv.lock:idna: [PYSEC-2024-60] idna 3.6 has a known vulnerability "
                "(Upgrade idna from 3.6 to 3.7)",
                "- [MEDIUM] uv.lock:idna: [PYSEC-2026-215] idna 3.6 has a known vulnerability "
                "(Upgrade idna from 3.6 to 3.15)",
            ]
        ),
    )


def test_the_agent_uv_audit_tool_of_a_project_outside_the_workspace_gives_no_result(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workspace is a subdirectory of a uv project. The tool refuses the project outside the
    workspace and gives no result, naming the project, so it never reads the lockfile of another
    project as the audit of the workspace (#2440)."""
    project = (tmp_path / "proj").resolve()
    workspace = project / "sub"
    workspace.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.chdir(workspace)
    scanner_fake.script_probe(str(project))

    reply = scan_uv_audit(".")

    assert (reply, scanner_fake.runs) == (
        "uv audit scan status: not_applicable\n"
        "Reason: uv audit would audit the project at "
        f"{project}, which lies outside the workspace. "
        "The scan audits only the project of the workspace.\n"
        "The scan gave no result. Do not report the target as clean.",
        [],
    )


def test_the_agent_uv_audit_tool_over_a_directory_that_does_not_exist_gives_no_result(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workspace holds a uv project, and the agent names a directory of it that does not exist.
    uv does not start, so the reply does not give the audit of the workspace project as the audit
    of that directory (#2106)."""
    workspace = tmp_path.resolve()
    (workspace / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    monkeypatch.chdir(workspace)
    scanner_fake.script_run_with_findings("uv", tree=workspace)

    reply = scan_uv_audit("services/api-typo")

    assert (reply, scanner_fake.runs) == (
        "uv audit scan status: not_applicable\n"
        f"Reason: {workspace / 'services' / 'api-typo'} is not a directory. uv audit audits the "
        "project of a directory.\n"
        "The scan gave no result. Do not report the target as clean.",
        [],
    )


def test_the_agent_manifest_tool_reports_each_resource_that_kubeconform_finds_invalid(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`k8s_validate_manifests` runs the kubeconform adapter over its target and replies with the
    outcome, one line for each resource that kubeconform reports (#2214)."""
    manifests = tmp_path / "k8s"
    manifests.mkdir()
    (manifests / "app.yaml").write_text("apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    recorded = scanner_fake.script_run_with_findings("kubeconform", tree=tmp_path)

    reply = k8s_validate_manifests(str(manifests))

    fix_invalid = "Correct the resource to match its schema"
    assert (scanner_fake.runs, reply) == (
        [recorded],
        "\n".join(
            [
                "Kubeconform scan status: ok",
                "Findings (3):",
                "- [HIGH] app.yaml:Widget/blue: [Kubeconform statusError] Widget 'blue' could not "
                "be validated (Correct the resource so that kubeconform can read it, or give "
                "kubeconform a schema for its kind.)",
                "- [HIGH] app.yaml:ConfigMap/settings: [Kubeconform statusInvalid] ConfigMap "
                f"'settings' does not match its schema ({fix_invalid}: additional properties "
                "'replicas' not allowed.)",
                "- [HIGH] app.yaml:Service/web: [Kubeconform statusInvalid] Service 'web' does "
                f"not match its schema ({fix_invalid}: /spec/ports/0/port: got string, want "
                "integer.)",
            ]
        ),
    )


def test_the_agent_terraform_lint_tool_replies_with_the_outcome_of_the_tflint_adapter(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`tf_lint` runs the tflint adapter over its target and replies with the outcome, one line
    for each issue that tflint reports (#2427)."""
    (tmp_path / "main.tf").write_text('variable "unused" {}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    position = {"line": 1, "column": 1}
    issue = {
        "rule": {"name": "terraform_unused_declarations", "severity": "warning", "link": ""},
        "message": 'variable "unused" is declared but not used',
        "range": {"filename": "main.tf", "start": position, "end": position},
        "callers": [],
    }
    report = json.dumps({"issues": [issue], "errors": []})
    scanner_fake.script("tflint", ToolAnswer(exit_code=2, stdout=report))

    reply = tf_lint(str(tmp_path))

    assert reply.splitlines()[:3] == [
        "TFLint scan status: ok",
        "Findings (1):",
        "- [MEDIUM] main.tf:1: [terraform_unused_declarations] "
        'variable "unused" is declared but not used '
        "(Update Terraform block to satisfy provider rule constraints.)",
    ]


def test_the_agent_iac_tool_runs_the_misconfiguration_scan_of_trivy(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`scan_iac` runs Trivy's misconfiguration scan over its target, in place of Checkov, and
    replies as `scan_trivy` does (#2214)."""
    scanner_fake.script("trivy", _trivy_run([]))
    monkeypatch.chdir(tmp_path)

    reply = scan_iac(str(tmp_path))

    assert ([run.argv for run in scanner_fake.runs], reply) == (
        [
            [
                "trivy",
                "config",
                str(tmp_path),
                "--severity",
                DEFAULT_TRIVY_SEVERITIES,
                "--format",
                "json",
                "--quiet",
            ]
        ],
        "Trivy scan status: ok\nNo findings.",
    )


def test_the_agent_semgrep_tool_sends_no_metrics_and_runs_the_rule_pack(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool's scan sends no metrics, checks no version, runs the rule pack, leaves out the
    directories of dependencies and data, and starts in its target (#1144, #1435)."""
    monkeypatch.chdir(tmp_path)

    scan_semgrep(str(tmp_path), config="./local-rules")

    assert [(run.argv, run.cwd) for run in scanner_fake.runs] == [
        (_semgrep_directory_scan(tmp_path, "./local-rules"), str(tmp_path.resolve()))
    ]


def test_the_agent_semgrep_tool_runs_from_the_cache_directory_with_the_cached_ruleset_named_there(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Semgrep returns plain rule ids for a config in its working directory, so the tool runs it
    from the cache directory and names the target by its absolute path."""
    monkeypatch.chdir(tmp_path)

    reply = scan_semgrep(str(tmp_path))

    assert (reply, [(run.argv, run.cwd) for run in scanner_fake.runs]) == (
        "Semgrep scan status: ok\nNo findings.",
        [
            (
                _semgrep_directory_scan(tmp_path, f"./{CACHED_RULESET_FILE_NAME}"),
                str(cached_default_ruleset.parent),
            )
        ],
    )


def test_the_agent_semgrep_tool_warns_when_the_cached_ruleset_is_older_than_a_day(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    clock: ClockFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    aged = time.time() - 25 * 3600
    os.utime(cached_default_ruleset, (aged, aged))

    scan_semgrep(str(tmp_path))

    assert (len(scanner_fake.runs), capsys.readouterr().err) == (
        1,
        "! The cached registry rules p/default are 25 hours old, and the scan uses them. "
        "Run `devops review rules fetch --ruleset p/default` to refresh them.\n",
    )


def test_the_agent_semgrep_tool_warns_of_nothing_when_the_cached_ruleset_is_current(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    scan_semgrep(str(tmp_path))

    assert capsys.readouterr().err == ""


def test_the_agent_semgrep_tool_without_the_cached_ruleset_runs_the_rule_pack_and_names_the_fetch_command(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no cached `p/default` the scan runs the rule pack alone, and the reply calls it a
    coverage gap and names the fetch command, as the adapter does for every scan (#1144)."""
    monkeypatch.chdir(tmp_path)

    reply = scan_semgrep(str(tmp_path))

    assert (reply, [run.argv for run in scanner_fake.runs]) == (
        "Semgrep scan status: coverage_gap\n"
        "Reason: The registry rules p/default are not cached, or the cached file is not a "
        "Semgrep ruleset. Run `devops review rules fetch --ruleset p/default`.\n"
        "No findings.",
        [_semgrep_directory_scan(tmp_path)],
    )


# A Kubernetes manifest. kubeconform starts only for a target that holds one (#2214).
_MANIFEST = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: settings\n"

# Each agent scan tool that runs a scanner adapter over a workspace path (#1435): the tool, the
# name its reply gives the scanner, and the program the adapter starts.
_ADAPTER_SCAN_TOOLS = [
    pytest.param(scan_trivy, "Trivy", "trivy", id="trivy"),
    pytest.param(scan_kubelinter, "Kube-linter", "kube-linter", id="kube-linter"),
    pytest.param(scan_pluto, "Pluto", "pluto", id="pluto"),
    pytest.param(scan_bandit, "Bandit", "bandit", id="bandit"),
    pytest.param(scan_gitleaks, "Gitleaks", "gitleaks", id="gitleaks"),
    pytest.param(scan_semgrep, "Semgrep", "semgrep", id="semgrep"),
    pytest.param(scan_uv_audit, "uv audit", "uv", id="uv-audit"),
    pytest.param(scan_iac, "Trivy", "trivy", id="trivy-config"),
    pytest.param(k8s_validate_manifests, "Kubeconform", "kubeconform", id="kubeconform"),
    pytest.param(tf_lint, "TFLint", "tflint", id="tflint"),
]


@pytest.mark.parametrize(("scan_tool", "scanner", "program"), _ADAPTER_SCAN_TOOLS)
def test_an_agent_scan_tool_whose_scanner_is_not_installed_says_so_and_not_clean(
    scan_tool: Callable[[str], str],
    scanner: str,
    program: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scanner that no directory of PATH holds gives no result, and the reply says so first
    (#1435). The target holds a manifest, which kubeconform needs before it starts."""
    no_scanners = tmp_path / "no-scanners"
    no_scanners.mkdir()
    monkeypatch.setenv("PATH", str(no_scanners))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "deploy.yaml").write_text(_MANIFEST, encoding="utf-8")

    reply = scan_tool(str(tmp_path))

    assert reply == (
        f"{scanner} scan status: not installed\n"
        f"Reason: Binary '{program}' not found on PATH\n"
        "The scan gave no result. Do not report the target as clean."
    )


@pytest.mark.parametrize(("scan_tool", "scanner", "program"), _ADAPTER_SCAN_TOOLS)
def test_an_agent_scan_tool_whose_scanner_fails_with_no_output_says_failed_and_not_clean(
    scan_tool: Callable[[str], str],
    scanner: str,
    program: str,
    scanner_fake: ScannerFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scanner that exits non-zero and writes nothing on stdout gives no result, and the reply
    says that the scan failed, with what the scanner wrote on stderr (#1435). The target holds a
    manifest, which kubeconform needs before it starts."""
    scanner_fake.script(program, ToolAnswer(exit_code=2, stderr="fatal: the target cannot be read"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "deploy.yaml").write_text(_MANIFEST, encoding="utf-8")

    reply = scan_tool(str(tmp_path))

    assert (reply, len(scanner_fake.runs)) == (
        f"{scanner} scan status: failed\n"
        "Reason: Scanner exited with code 2: fatal: the target cannot be read\n"
        "The scan gave no result. Do not report the target as clean.",
        1,
    )


@pytest.mark.parametrize(
    ("scan_tool", "scanner"), [(scan_bandit, "Bandit"), (scan_gitleaks, "Gitleaks")]
)
def test_an_agent_scan_tool_whose_scanner_finds_nothing_says_ok_and_no_findings(
    scan_tool: Callable[[str], str],
    scanner: str,
    scanner_fake: ScannerFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recorded runs of the real scanners find nothing, and the reply says the scan is ok."""
    monkeypatch.chdir(tmp_path)

    reply = scan_tool(str(tmp_path))

    assert reply == f"{scanner} scan status: ok\nNo findings."


def _trivy_run(results: list[dict[str, object]]) -> ToolAnswer:
    """A Trivy run that exits 0 and reports `results` as JSON on stdout."""
    return ToolAnswer(stdout=json.dumps({"Results": results}))


def test_an_agent_scan_tool_leads_with_the_status_and_lists_each_finding_masked(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reply gives the status first, then each finding of the adapter, with every secret in
    the text masked (#1435)."""
    token = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz"
    scanner_fake.script(
        "trivy",
        _trivy_run(
            [
                {
                    "Target": "uv.lock",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-0001",
                            "PkgName": "requests",
                            "InstalledVersion": "2.0.0",
                            "FixedVersion": "2.32.0",
                            "Severity": "HIGH",
                            "Title": "requests sends the session cookie to any host",
                        }
                    ],
                },
                {
                    "Target": "app.env",
                    "Secrets": [
                        {"RuleID": "github-pat", "Title": f"token {token}", "Severity": "CRITICAL"}
                    ],
                },
            ]
        ),
    )
    monkeypatch.chdir(tmp_path)

    reply = scan_trivy(str(tmp_path))

    assert reply == (
        "Trivy scan status: ok\n"
        "Findings (2):\n"
        "- [HIGH] uv.lock:requests: [CVE-2026-0001] requests sends the session cookie to any "
        "host (Upgrade requests from 2.0.0 to 2.32.0)\n"
        "- [CRITICAL] app.env:github-pat: [SECRET] token <masked-github-token> (Remove "
        "hardcoded secret and store in OS Keyring or environment variables)"
    )


def test_an_agent_scan_tool_cuts_a_long_reply_at_the_tool_output_limit(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reply longer than the limit of a tool's output is cut there, and says where (#1435)."""
    packages = [f"pkg{number}" for number in range(200)]
    scanner_fake.script(
        "trivy",
        _trivy_run(
            [
                {
                    "Target": "uv.lock",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-0001",
                            "PkgName": package,
                            "InstalledVersion": "1.0",
                            "FixedVersion": "2.0",
                            "Severity": "LOW",
                            "Title": "t",
                        }
                        for package in packages
                    ],
                }
            ]
        ),
    )
    monkeypatch.chdir(tmp_path)
    whole = "\n".join(
        [
            "Trivy scan status: ok",
            "Findings (200):",
            *(
                f"- [LOW] uv.lock:{package}: [CVE-2026-0001] t (Upgrade {package} from 1.0 to 2.0)"
                for package in packages
            ),
        ]
    )

    reply = scan_trivy(str(tmp_path))

    assert reply == (
        f"{whole[:DEFAULT_TOOL_DIFF_MAX_CHARS]}\n"
        f"... [truncated at {DEFAULT_TOOL_DIFF_MAX_CHARS} chars]"
    )
