"""Comprehensive unit tests for built-in workspace inspection and execution tools."""

from __future__ import annotations

import ipaddress
import json
import os
import time
from collections.abc import Callable
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
    k8s_validate_manifests,
    list_files,
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
)
from devops_cli.config.defaults import DEFAULT_TOOL_DIFF_MAX_CHARS, DEFAULT_TRIVY_SEVERITIES
from devops_cli.review.rules_pack import RULE_PACK_DIR
from devops_cli.security.tool_executor import KubeApiNetwork
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.registry_cache import CACHED_RULESET_FILE_NAME

pytestmark = pytest.mark.usefixtures("keyring_store")


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
    """Verify the external DevOps tool wrappers that run no scanner adapter execute expected
    commands."""
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
    """Verify tf_lint, docker_analyze_layers, and rag_search.

    The knowledge base check before the search finds Qdrant down, refused through
    `refusing_port`, and its retry waits return at once.
    """
    from devops_cli.ai.review_schema import Finding
    from devops_cli.ai.tools.builtin_tools import (
        docker_analyze_layers,
        rag_search,
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

    from devops_cli.config.settings import reset_settings_cache

    monkeypatch.setenv("DEVOPS_CLI_QDRANT_URL", f"http://127.0.0.1:{refusing_port}")
    reset_settings_cache()
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    with (
        patch("devops_cli.ai.tools.builtin_tools._is_safe_workspace_path", return_value=True),
        patch("devops_cli.security.tflint.run_tflint_scan", return_value=[mock_finding]),
        patch("devops_cli.security.dive.run_dive_analysis", return_value=mock_dive),
        patch("devops_cli.ai.rag.qdrant.QdrantClient.is_alive", return_value=True),
        patch(
            "devops_cli.ai.rag.retriever.SemanticRetriever.retrieve_context",
            return_value=MagicMock(results=[]),
        ),
    ):
        res_tflint = tf_lint(str(tmp_path))
        assert "Sample issue" in res_tflint

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
