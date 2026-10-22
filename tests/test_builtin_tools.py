"""Comprehensive unit tests for built-in workspace inspection and execution tools."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from devops_cli.ai.tools.builtin_tools import (
    _is_safe_workspace_path,
    _run_tool_cmd,
    argo_apps,
    check_threat_intel,
    git_diff,
    git_status,
    k8s_pods,
    k8s_tempo_status,
    list_files,
    read_file,
    scan_bandit,
    scan_kubelinter,
    scan_osv,
    scan_pluto,
    scan_popeye,
    scan_semgrep,
    scan_trivy,
    scan_uv_audit,
    search_code,
)
from devops_cli.review.rules_pack import RULE_PACK_DIR
from tests.support.fakes.scanners import ScannerFake

pytestmark = pytest.mark.usefixtures("mock_keyring")


def test_is_safe_workspace_path(tmp_path: Path) -> None:
    """Verify _is_safe_workspace_path allows workspace paths and denies external/symlinked paths."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    inside_file = workspace / "test.txt"
    inside_file.touch()
    outside_file = tmp_path / "outside.txt"
    outside_file.touch()

    # Symlink
    symlink_file = workspace / "link.txt"
    try:
        symlink_file.symlink_to(inside_file)
        assert _is_safe_workspace_path(symlink_file, workspace_root=workspace) is False
    except OSError:
        pass

    assert _is_safe_workspace_path(inside_file, workspace_root=workspace) is True
    assert _is_safe_workspace_path(outside_file, workspace_root=workspace) is False


def test_run_tool_cmd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _run_tool_cmd execution, truncating, and fallback messages."""
    # 1. Successful execution
    mock_ok = MagicMock(stdout="Sample Output")
    monkeypatch.setattr("devops_cli.ai.tools.builtin_tools.run_subprocess", lambda *a, **k: mock_ok)
    assert _run_tool_cmd(["echo", "hi"]) == "Sample Output"

    # 2. Fallback message on empty stdout
    mock_empty = MagicMock(stdout="")
    monkeypatch.setattr(
        "devops_cli.ai.tools.builtin_tools.run_subprocess", lambda *a, **k: mock_empty
    )
    assert _run_tool_cmd(["echo"], fallback_msg="No output") == "No output"

    # 3. Truncated output
    mock_long = MagicMock(stdout="A" * 50)
    monkeypatch.setattr(
        "devops_cli.ai.tools.builtin_tools.run_subprocess", lambda *a, **k: mock_long
    )
    res = _run_tool_cmd(["long"], max_chars=20)
    assert "truncated at 20 chars" in res
    assert res.startswith("A" * 20)

    # 4. Command exception
    def mock_raise(*a, **k):
        raise OSError("Executable not found")

    monkeypatch.setattr("devops_cli.ai.tools.builtin_tools.run_subprocess", mock_raise)
    assert "failed" in _run_tool_cmd(["invalid_cmd"]).lower()


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


def test_git_status_and_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify git_status and git_diff tool wrappers."""
    mock_run = MagicMock(stdout=" M src/main.py")
    monkeypatch.setattr(
        "devops_cli.ai.tools.builtin_tools.run_subprocess", lambda *a, **k: mock_run
    )

    assert "src/main.py" in git_status()
    assert "src/main.py" in git_diff()


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


def test_devops_subcommand_wrappers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all external DevOps tool wrappers execute expected commands."""
    called_cmds: list[list[str]] = []

    def mock_tool_cmd(cmd: list[str], *args, **kwargs) -> str:
        called_cmds.append(cmd)
        return "OK"

    monkeypatch.setattr("devops_cli.ai.tools.builtin_tools._run_tool_cmd", mock_tool_cmd)

    k8s_pods("kube-system")
    assert called_cmds[-1][:3] == ["kubectl", "get", "pods"]

    k8s_tempo_status("default")
    assert called_cmds[-1][:3] == ["kubectl", "get", "deployments,statefulsets,services"]

    argo_apps()
    assert called_cmds[-1][:3] == ["argocd", "app", "list"]

    scan_trivy("src")
    assert called_cmds[-1][:2] == ["trivy", "fs"]

    scan_uv_audit(".")
    assert called_cmds[-1][:2] == ["uv", "audit"]

    scan_kubelinter("k8s")
    assert called_cmds[-1][:2] == ["kube-linter", "lint"]

    scan_pluto("k8s")
    pluto_dir_cmd = called_cmds[-1][:2]

    scan_pluto("k8s/deployment.yaml")
    pluto_file_cmd = called_cmds[-1][:2]

    assert (pluto_dir_cmd, pluto_file_cmd) == (
        ["pluto", "detect-files"],
        ["pluto", "detect"],
    )

    scan_bandit("src")
    assert called_cmds[-1][:2] == ["bandit", "-r"]

    scan_popeye("monitoring")
    assert called_cmds[-1][:2] == ["popeye", "-n"]


def test_scan_osv_and_threat_intel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify scan_osv and check_threat_intel functions."""
    from devops_cli.models.vulnerability import (
        NetworkReputationRecord,
        PackageLookupResult,
        VulnerabilityRecord,
    )

    mock_rec = VulnerabilityRecord(
        id="CVE-2026-0001",
        cve_id="CVE-2026-0001",
        title="Test Vuln",
        severity="HIGH",
        package_name="pydantic",
        ecosystem="PyPI",
    )
    with patch(
        "devops_cli.security.vulnerability_lookup.OSVClient.query_package",
        return_value=PackageLookupResult(status="ok", vulnerabilities=[mock_rec]),
    ):
        res_osv = scan_osv("pydantic", version="2.0.0")
        assert "CVE-2026-0001" in res_osv

    mock_rep = NetworkReputationRecord(
        target="1.1.1.1",
        reference_type="ip",
        is_suspicious=False,
        threat_level="CLEAN",
        ports=[53, 443],
        reputation_summary="Safe / Clean IP",
    )
    with patch(
        "devops_cli.security.vulnerability_lookup.ShodanInternetDBClient.check_ip",
        return_value=mock_rep,
    ):
        res_intel = check_threat_intel("1.1.1.1")
        assert "Safe / Clean IP" in res_intel

    res_ex_domain = check_threat_intel("example.com")
    assert "is a documented example" in res_ex_domain

    res_ex_ip = check_threat_intel("192.0.2.1")
    assert "is a documented example" in res_ex_ip


# 0.0.0.0, the unspecified IPv4 address, as a value under test rather than a bind address.
_UNSPECIFIED_IPV4 = str(ipaddress.IPv4Address(0))


@pytest.mark.parametrize(
    "target",
    [
        "3fff::1",
        "555-0100",
        _UNSPECIFIED_IPV4,
        "::",
        f"http://{_UNSPECIFIED_IPV4}:8000",
        "3221225985",
    ],
)
def test_check_threat_intel_names_the_rfcs_of_every_target_it_excludes(target: str) -> None:
    """The reply names everything `is_example_or_invalid_network_target` excludes: example
    domains, documentation and benchmarking addresses, fictional phone numbers and the
    unspecified addresses, and not RFC 6890, whose reserved space is local. A documentation
    address in a numeric spelling a resolver dials (`3221225985` is 192.0.2.1) is excluded too.
    No service is asked (#1174)."""
    with patch(
        "devops_cli.security.vulnerability_lookup.httpx2.Client.get",
        side_effect=AssertionError("no threat-intel request may leave"),
    ) as http_get:
        reply = check_threat_intel(target)
    assert (http_get.call_count, reply) == (
        0,
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
    target: str, address: str
) -> None:
    """Multicast, shared address space, 6to4 relay anycast in either spelling and site-local
    space are local, so neither Shodan nor Cloudflare Radar is asked, and the reply says so
    without calling the address a domain. That holds after a trailing punctuation mark, in a
    URL and in a numeric spelling a resolver dials (`2130706433` is 127.0.0.1). Multicast used to
    be in no class and went to Radar, as each punctuated address did; 6to4 relay anycast in its
    IPv4-mapped spelling and site-local space went to Shodan (#1174)."""
    with patch(
        "devops_cli.security.vulnerability_lookup.httpx2.Client.get",
        side_effect=AssertionError("no threat-intel request may leave"),
    ) as http_get:
        reply = check_threat_intel(target)
    assert (http_get.call_count, reply) == (
        0,
        f"Target {target} is a local address ({address}): private, loopback, link-local, shared, "
        "site-local, multicast or reserved space, which is not globally reachable. No threat "
        "intelligence service was asked.",
    )


@pytest.mark.parametrize("target", ["8.8.8.8.", "8.8.8.8,", "::ffff:8.8.8.8"])
def test_check_threat_intel_asks_shodan_about_the_address_the_target_names(target: str) -> None:
    """A public address is sent to Shodan InternetDB as the address it is, without the
    punctuation prose leaves after it and in its IPv4 spelling; a trailing dot used to send it
    to Cloudflare Radar's domain lookup (#1174)."""
    from devops_cli.models.vulnerability import NetworkReputationRecord

    record = NetworkReputationRecord(target="8.8.8.8", ip="8.8.8.8", reputation_summary="Clean")
    with patch(
        "devops_cli.security.vulnerability_lookup.ShodanInternetDBClient.check_ip",
        return_value=record,
    ) as check_ip:
        reply = check_threat_intel(target)
    assert (check_ip.call_args_list, reply.splitlines()[0]) == (
        [call("8.8.8.8")],
        "Shodan Intelligence for IP 8.8.8.8:",
    )


def test_scan_osv_names_only_the_database_it_queries() -> None:
    """`scan_osv` and the `security_intel_package` tool query OSV.dev alone, so neither their
    descriptions nor a clean reply mention NVD, which nothing queries (#956)."""
    from devops_cli.ai.mcp.server import security_intel_package
    from devops_cli.models.vulnerability import PackageLookupResult

    with patch(
        "devops_cli.security.vulnerability_lookup.OSVClient.query_package",
        return_value=PackageLookupResult(status="ok", vulnerabilities=[]),
    ):
        clean = scan_osv("requests", "2.0.0")

    assert (
        clean,
        "NVD" in (scan_osv.__doc__ or ""),
        "NVD" in (security_intel_package.__doc__ or ""),
    ) == ("No known vulnerabilities found in OSV for requests (PyPI).", False, False)


def test_scan_osv_reports_a_failed_lookup_instead_of_a_clean_package() -> None:
    """A lookup that cannot reach OSV.dev says so with the reason. It used to answer "No known
    vulnerabilities", which reads as a clean package (#956)."""
    import httpx2

    with patch(
        "devops_cli.security.vulnerability_lookup.httpx2.Client.post",
        side_effect=httpx2.ConnectError("connection refused"),
    ):
        reply = scan_osv("requests", "2.0.0")

    assert (reply, "No known vulnerabilities" in reply) == (
        "OSV lookup failed: connection refused",
        False,
    )


def test_builtin_security_and_iac_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refusing_port: int
) -> None:
    """Verify scan_gitleaks, scan_semgrep, scan_iac, tf_lint, k8s_validate_manifests, docker_analyze_layers, and rag_search.

    The knowledge base check before the search finds Qdrant down, refused through
    `refusing_port`, and its retry waits return at once.
    """
    from devops_cli.ai.review_schema import Finding
    from devops_cli.ai.tools.builtin_tools import (
        docker_analyze_layers,
        k8s_validate_manifests,
        rag_search,
        scan_gitleaks,
        scan_iac,
        scan_semgrep,
        tf_lint,
    )

    mock_finding = Finding(
        category="security",
        severity="HIGH",
        location="main.tf:1",
        title="Sample issue",
        fix="Fix issue",
    )

    from devops_cli.security.dive import DiveAnalysisResult

    mock_dive = DiveAnalysisResult(
        image_name="alpine:latest",
        status="ran",
        efficiency_score=0.95,
        wasted_bytes=1024 * 1024,
        total_bytes=10 * 1024 * 1024,
    )

    import subprocess

    mock_scan_proc = subprocess.CompletedProcess(
        args=["scan"],
        returncode=0,
        stdout="Found 1 finding in target",
        stderr="",
    )

    from devops_cli.config.settings import reset_settings_cache

    monkeypatch.setenv("DEVOPS_CLI_QDRANT_URL", f"http://127.0.0.1:{refusing_port}")
    reset_settings_cache()
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    with (
        patch("devops_cli.ai.tools.builtin_tools._is_safe_workspace_path", return_value=True),
        patch("devops_cli.ai.tools.builtin_tools.run_subprocess", return_value=mock_scan_proc),
        patch("devops_cli.security.checkov.run_checkov_scan", return_value=[mock_finding]),
        patch("devops_cli.security.tflint.run_tflint_scan", return_value=[mock_finding]),
        patch(
            "devops_cli.security.kubeconform.run_kubeconform_validation",
            return_value=[mock_finding],
        ),
        patch("devops_cli.security.dive.run_dive_analysis", return_value=mock_dive),
        patch("devops_cli.ai.rag.qdrant.QdrantClient.is_alive", return_value=True),
        patch(
            "devops_cli.ai.rag.retriever.SemanticRetriever.retrieve_context",
            return_value=MagicMock(results=[]),
        ),
    ):
        res_gitleaks = scan_gitleaks(str(tmp_path))
        assert "Found 1 finding in target" in res_gitleaks

        res_semgrep = scan_semgrep(str(tmp_path))
        assert "Found 1 finding in target" in res_semgrep

        res_iac = scan_iac(str(tmp_path))
        assert "Sample issue" in res_iac

        res_tflint = tf_lint(str(tmp_path))
        assert "Sample issue" in res_tflint

        res_k8s = k8s_validate_manifests(str(tmp_path))
        assert "Sample issue" in res_k8s

        res_docker = docker_analyze_layers("alpine:latest")
        assert "Efficiency Score: 95.0%" in res_docker

        res_rag = rag_search("test query")
        assert "No semantic matches found" in res_rag


def test_rag_search_names_an_embedding_failure(
    monkeypatch: pytest.MonkeyPatch, refusing_port: int, unserved_side_channel_port: int
) -> None:
    """A query the embedding model cannot embed returns the failure, as an unreachable store does.

    The knowledge base check before the search finds Qdrant down, refused through
    `refusing_port`, and its retry waits return at once; telemetry goes to the floor's collector.
    """
    from devops_cli.ai.rag.embeddings import EmbeddingsError
    from devops_cli.ai.tools.builtin_tools import rag_search
    from devops_cli.config.settings import Settings

    failure = EmbeddingsError(
        "Embedding model bge-m3:latest produced no embeddings: "
        "https://example.com/v1/embeddings answered HTTP 400: model not loaded"
    )
    settings = Settings()
    settings.qdrant.url = f"http://127.0.0.1:{refusing_port}"
    settings.telemetry.endpoint = f"http://127.0.0.1:{unserved_side_channel_port}"
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    with (
        patch("devops_cli.config.settings.load_settings", return_value=settings),
        patch("devops_cli.config.settings.get_ai_api_key", return_value=None),
        patch("devops_cli.config.settings.get_qdrant_api_key", return_value=None),
        patch("devops_cli.ai.rag.embeddings.EmbeddingsEngine._init_valkey", return_value=None),
        patch("devops_cli.ai.rag.qdrant.QdrantClient.is_alive", return_value=True),
        patch(
            "devops_cli.ai.rag.retriever.SemanticRetriever.retrieve_context", side_effect=failure
        ),
    ):
        reply = rag_search("where is the retry policy")

    assert reply == (
        "RAG search unavailable: Embedding model bge-m3:latest produced no embeddings: "
        "https://example.com/v1/embeddings answered HTTP 400: model not loaded. "
        "Fallback: use search_code."
    )


def test_the_agent_semgrep_tool_sends_no_metrics_and_runs_the_rule_pack(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool's scan sends no metrics, checks no version, runs the rule pack and excludes no
    directory (#1144)."""
    monkeypatch.chdir(tmp_path)

    scan_semgrep(str(tmp_path), config="./local-rules")

    assert [run.argv for run in scanner_fake.runs] == [
        [
            "semgrep",
            "scan",
            "--json",
            "--metrics",
            "off",
            "--disable-version-check",
            "--config",
            "./local-rules",
            "--config",
            str(RULE_PACK_DIR),
            "--disable-nosem",
            "--quiet",
            str(tmp_path.resolve()),
        ]
    ]
