"""Comprehensive unit tests for all domain and subsystem Pydantic resource models."""

from __future__ import annotations

from devops_cli import models
from devops_cli.models.ai import (
    ExportFeedbackRequest,
    ExportFeedbackResult,
    FindingSummaryEntry,
    RAGChunkResult,
    RAGIndexRequest,
    RAGIndexResult,
    RAGSearchRequest,
    RAGSearchResult,
    ReviewBranchRequest,
    ReviewFindingsRequest,
    ReviewFindingsResult,
    ReviewPathRequest,
    ReviewPRRequest,
    ReviewStatsRequest,
    ReviewStatsResult,
    TelemetryStatusRequest,
    TelemetryStatusResult,
    TelemetryTestSpanRequest,
    TelemetryTestSpanResult,
    VerifyFindingRequest,
    VerifyFindingResult,
)
from devops_cli.models.ci import (
    CICheckResult,
    CIRunRequest,
    CIRunResult,
)
from devops_cli.models.config import (
    ConfigOptionSpec,
    ConfigOutputRequest,
    ConfigOutputResult,
    ConfigShowRequest,
    ConfigShowResult,
)
from devops_cli.models.docker import (
    ContainerStatEntry,
    DockerLayerAnalysisRequest,
    DockerLayerAnalysisResult,
    DockerPruneRequest,
    DockerPruneResult,
    DockerStatsRequest,
    DockerStatsResult,
)
from devops_cli.models.git import (
    BranchesListRequest,
    BranchListing,
    RepoEntry,
    ReposListRequest,
    ReposListResult,
    ReposStatusRequest,
    ReposStatusResult,
    ReposSyncRequest,
    ReposSyncResult,
    RepoStatusEntry,
)
from devops_cli.models.k8s import (
    K8sBootstrapRequest,
    K8sBootstrapResult,
    K8sClusterStatusRequest,
    K8sClusterStatusResult,
    K8sDeployStackRequest,
    K8sDeployStackResult,
    K8sJaegerInfoRequest,
    K8sJaegerInfoResult,
    K8sPodsRequest,
    K8sPodsResult,
    K8sPolicyValidateRequest,
    K8sPolicyValidateResult,
    K8sTeardownStackRequest,
    K8sTeardownStackResult,
    PodInfo,
    PolicyRuleViolation,
)
from devops_cli.models.release import (
    ReleasePrepareRequest,
    ReleasePrepareResult,
    ReleaseStatusRequest,
    ReleaseStatusResult,
)
from devops_cli.models.security import (
    NetworkIntelRequest,
    NetworkIntelResult,
    PackageIntelRequest,
    PackageIntelResult,
    SecurityScanRequest,
    SecurityScanResult,
    SSHKeyAuditRequest,
    SSHKeyAuditResult,
    StaticFindingEntry,
    UvAuditRequest,
    UvAuditResult,
)
from devops_cli.models.tf import (
    TFApplyRequest,
    TFApplyResult,
    TFLintIssue,
    TFLintRequest,
    TFLintResult,
    TFOutputRequest,
    TFOutputResult,
    TFPlanRequest,
    TFPlanResult,
)
from devops_cli.models.workspace import (
    WorkspaceCleanRequest,
    WorkspaceCleanResult,
    WorkspaceEntry,
    WorkspaceListRequest,
    WorkspaceListResult,
)


def test_docker_resource_models_roundtrip() -> None:
    """Verify Docker request and result resource models serialize and deserialize cleanly."""
    prune_req = DockerPruneRequest(all_resources=True, volumes=True, dry_run=False)
    assert prune_req.all_resources is True
    assert "all_resources" in prune_req.model_json_schema()["properties"]

    prune_res = DockerPruneResult(
        containers_deleted=3,
        images_deleted=5,
        volumes_deleted=2,
        space_reclaimed_bytes=104857600,
        space_reclaimed_human="100MB",
        success=True,
        details=["Deleted container c1", "Deleted image img1"],
    )
    dumped = prune_res.model_dump_json()
    loaded = DockerPruneResult.model_validate_json(dumped)
    assert loaded.containers_deleted == 3
    assert len(loaded.details) == 2

    c_stat = ContainerStatEntry(
        container_id="c12345",
        name="web-app",
        cpu_percentage=12.5,
        memory_usage_bytes=52428800,
        memory_limit_bytes=104857600,
        memory_percentage=50.0,
        net_io_in_bytes=1000,
        net_io_out_bytes=2000,
        block_io_read_bytes=500,
        block_io_write_bytes=1500,
        pids_count=8,
    )
    stats_req = DockerStatsRequest(all_containers=True, no_stream=True)
    assert stats_req.all_containers is True
    stats_res = DockerStatsResult(containers=[c_stat], total_containers=1)
    assert stats_res.total_containers == 1
    assert stats_res.containers[0].name == "web-app"

    layer_req = DockerLayerAnalysisRequest(image_tag="app:latest")
    assert layer_req.image_tag == "app:latest"
    layer_res = DockerLayerAnalysisResult(
        image_tag="app:latest",
        efficiency_score=0.95,
        wasted_space_bytes=5000,
        wasted_space_human="5KB",
        layer_count=6,
        passed=True,
    )
    assert layer_res.efficiency_score == 0.95


def test_k8s_resource_models_roundtrip() -> None:
    """Verify Kubernetes request and result resource models."""
    pod_req = K8sPodsRequest(namespace="default")
    assert pod_req.namespace == "default"
    pod_info = PodInfo(
        name="api-server-1",
        namespace="default",
        status="Running",
        ready_containers="1/1",
        restart_count=0,
        node_name="node-1",
        ip_address="10.244.0.5",
        age_seconds=3600,
    )
    pod_res = K8sPodsResult(pods=[pod_info], total_pods=1, running_pods=1, failed_pods=0)
    assert pod_res.total_pods == 1
    assert pod_res.pods[0].status == "Running"

    cluster_req = K8sClusterStatusRequest(timeout_seconds=5.0)
    assert cluster_req.timeout_seconds == 5.0
    cluster_res = K8sClusterStatusResult(
        connected=True,
        cluster_name="minikube",
        api_server_url="https://127.0.0.1:8443",
        server_version="v1.31.0",
        node_count=1,
        ready_nodes=1,
        namespaces_count=4,
        healthy=True,
        components={"etcd": "Healthy", "scheduler": "Healthy"},
    )
    assert cluster_res.healthy is True

    boot_req = K8sBootstrapRequest(cpus=4, memory_mb=8192)
    assert boot_req.cpus == 4
    boot_res = K8sBootstrapResult(
        success=True,
        cluster_name="minikube",
        driver="docker",
        ip_address="192.168.49.2",
        kubeconfig_path="~/.kube/config",
        duration_seconds=15.2,
    )
    assert boot_res.success is True

    deploy_req = K8sDeployStackRequest(stack_name="llm", namespace="ai")
    assert deploy_req.stack_name == "llm"
    deploy_res = K8sDeployStackResult(
        stack_name="llm",
        namespace="ai",
        resources_created=["Deployment/ollama", "Service/ollama"],
        endpoints={"ollama": "http://127.0.0.1:11434"},
        success=True,
    )
    assert len(deploy_res.resources_created) == 2

    teardown_req = K8sTeardownStackRequest(stack_name="llm")
    assert teardown_req.stack_name == "llm"
    teardown_res = K8sTeardownStackResult(
        stack_name="llm",
        namespace="default",
        resources_deleted=["Deployment/ollama"],
        success=True,
    )
    assert teardown_res.success is True

    violation = PolicyRuleViolation(
        policy_name="disallow-privileged",
        rule_name="require-non-root",
        resource_kind="Pod",
        resource_name="nginx",
        severity="HIGH",
        message="Containers must not run as root",
    )
    val_req = K8sPolicyValidateRequest(manifest_path="k8s/nginx.yaml")
    assert val_req.manifest_path == "k8s/nginx.yaml"
    val_res = K8sPolicyValidateResult(
        manifest_path="k8s/nginx.yaml",
        passed=False,
        total_rules_evaluated=10,
        violations_count=1,
        violations=[violation],
    )
    assert val_res.passed is False

    jaeger_req = K8sJaegerInfoRequest()
    assert jaeger_req.namespace == "telemetry"
    jaeger_res = K8sJaegerInfoResult(
        ui_url="http://127.0.0.1:16686",
        collector_otlp_grpc="127.0.0.1:4317",
        collector_otlp_http="127.0.0.1:4318",
        status="Running",
        available=True,
    )
    assert jaeger_res.available is True


def test_security_resource_models_roundtrip() -> None:
    """Verify Security request and result resource models."""
    scan_req = SecurityScanRequest(target_path="src", scanner="all", severity_threshold="MEDIUM")
    assert scan_req.target_path == "src"
    finding = StaticFindingEntry(
        scanner="bandit",
        rule_id="B101",
        title="Assert used",
        location="src/main.py:10",
        severity="LOW",
    )
    scan_res = SecurityScanResult(
        target_path="src",
        scanners_executed=["bandit", "semgrep"],
        total_findings=1,
        findings=[finding],
        passed=True,
    )
    assert scan_res.total_findings == 1

    pkg_req = PackageIntelRequest(package_name="requests", version="2.25.0")
    assert pkg_req.package_name == "requests"
    pkg_res = PackageIntelResult(
        package_name="requests",
        version="2.25.0",
        ecosystem="PyPI",
        is_vulnerable=False,
        security_status="Clean",
    )
    assert pkg_res.is_vulnerable is False

    net_req = NetworkIntelRequest(target="example.com")
    assert net_req.target == "example.com"
    net_res = NetworkIntelResult(
        target="example.com",
        target_type="domain",
        is_malicious=False,
        risk_level="LOW",
        open_ports=[80, 443],
        reputation_summary="Clean Domain",
    )
    assert net_res.is_malicious is False

    uv_req = UvAuditRequest(project_dir=".")
    assert uv_req.project_dir == "."
    uv_res = UvAuditResult(passed=True, vulnerabilities_count=0, packages_audited=35)
    assert uv_res.passed is True

    ssh_req = SSHKeyAuditRequest()
    assert ssh_req.ssh_dir == "~/.ssh"
    ssh_res = SSHKeyAuditResult(
        keys_scanned=2,
        weak_keys_count=0,
        permission_issues_count=0,
        passed=True,
        recommendations=["All keys meet ed25519/RSA-4096 standards."],
    )
    assert ssh_res.passed is True


def test_tf_resource_models_roundtrip() -> None:
    """Verify OpenTofu / Terraform request and result resource models."""
    plan_req = TFPlanRequest(directory="tf", detailed_exitcode=True)
    assert plan_req.detailed_exitcode is True
    plan_res = TFPlanResult(
        directory="tf",
        has_changes=True,
        resources_to_add=2,
        resources_to_change=1,
        resources_to_destroy=0,
        plan_output="Plan: 2 to add, 1 to change, 0 to destroy.",
        success=True,
    )
    assert plan_res.resources_to_add == 2

    apply_req = TFApplyRequest(directory="tf", auto_approve=True)
    assert apply_req.auto_approve is True
    apply_res = TFApplyResult(
        directory="tf",
        resources_added=2,
        resources_changed=1,
        resources_destroyed=0,
        outputs={"cluster_endpoint": "https://k8s.example.com"},
        success=True,
    )
    assert apply_res.resources_added == 2

    out_req = TFOutputRequest(directory="tf")
    assert out_req.directory == "tf"
    out_res = TFOutputResult(
        directory="tf",
        outputs={"vpc_id": "vpc-12345"},
        success=True,
    )
    assert out_res.outputs["vpc_id"] == "vpc-12345"

    lint_req = TFLintRequest(directory="tf")
    assert lint_req.directory == "tf"
    lint_issue = TFLintIssue(
        rule_name="terraform_unused_declarations",
        message="variable 'unused' is declared but not used",
        location="variables.tf:12",
        severity="WARNING",
    )
    lint_res = TFLintResult(
        directory="tf",
        passed=False,
        issues_count=1,
        issues=[lint_issue],
    )
    assert lint_res.issues_count == 1


def test_config_and_workspace_resource_models_roundtrip() -> None:
    """Verify Config and Workspace request and result resource models."""
    cfg_req = ConfigShowRequest(include_defaults=True, redact_secrets=True)
    assert cfg_req.include_defaults is True
    cfg_res = ConfigShowResult(
        config_path="/workspaces/devops-cli/config.yaml",
        settings={"ai": {"provider": "ollama"}},
    )
    assert cfg_res.settings["ai"]["provider"] == "ollama"

    opt_spec = ConfigOptionSpec(
        key="ai.provider",
        env_var="DEVOPS_CLI_AI_PROVIDER",
        type_name="str",
        default_value="ollama",
        description="LLM provider name",
    )
    out_req = ConfigOutputRequest(format="json")
    assert out_req.format == "json"
    out_res = ConfigOutputResult(total_options=1, options=[opt_spec])
    assert out_res.total_options == 1

    ws_req = WorkspaceListRequest(base_dir=".", max_depth=2)
    assert ws_req.max_depth == 2
    ws_entry = WorkspaceEntry(
        name="devops-cli",
        path="/workspaces/devops-cli",
        is_git_repo=True,
        current_branch="release/v0.2.5",
        is_dirty=False,
        size_bytes=1048576,
    )
    ws_res = WorkspaceListResult(total_workspaces=1, workspaces=[ws_entry])
    assert ws_res.workspaces[0].name == "devops-cli"

    clean_req = WorkspaceCleanRequest(older_than_days=7, dry_run=False)
    assert clean_req.older_than_days == 7
    clean_res = WorkspaceCleanResult(
        files_removed=12,
        bytes_reclaimed=5242880,
        bytes_reclaimed_human="5MB",
        purged_directories=[".data/reviews/old-session"],
    )
    assert clean_res.files_removed == 12


def test_release_and_ci_resource_models_roundtrip() -> None:
    """Verify Release and CI request and result resource models."""
    rel_req = ReleaseStatusRequest(check_remote=True)
    assert rel_req.check_remote is True
    rel_res = ReleaseStatusResult(
        current_version="0.2.5",
        latest_git_tag="v0.2.4",
        is_clean=True,
        branch_name="release/v0.2.5",
        unreleased_commits_count=5,
        docs_synchronized=True,
        ready_for_release=True,
    )
    assert rel_res.ready_for_release is True

    prep_req = ReleasePrepareRequest(bump_type="patch")
    assert prep_req.bump_type == "patch"
    prep_res = ReleasePrepareResult(
        previous_version="0.2.4",
        new_version="0.2.5",
        updated_files=["pyproject.toml", "README.md"],
        release_branch="release/v0.2.5",
    )
    assert prep_res.new_version == "0.2.5"

    ci_chk = CICheckResult(
        name="test",
        passed=True,
        duration_seconds=12.4,
        details="All 1035 tests passed",
    )
    ci_req = CIRunRequest(checks=["test"], fail_fast=True)
    assert ci_req.fail_fast is True
    ci_res = CIRunResult(
        passed=True,
        total_checks=1,
        passed_checks=1,
        failed_checks=0,
        total_duration_seconds=12.4,
        checks=[ci_chk],
    )
    assert ci_res.passed is True


def test_git_resource_models_roundtrip() -> None:
    """Verify Git branch and repo request and result resource models."""
    branch_req = BranchesListRequest(repo_path=".")
    assert branch_req.repo_path == "."
    branch_list = BranchListing(branches=["main", "release/v0.2.5"], current="release/v0.2.5")
    assert branch_list.current == "release/v0.2.5"

    repo_req = ReposListRequest(filter_pattern="*")
    assert repo_req.filter_pattern == "*"
    repo_entry = RepoEntry(
        name="devops-cli",
        path="/workspaces/devops-cli",
        remote_url="https://github.com/dan-petty/devops-cli.git",
        current_branch="release/v0.2.5",
    )
    repos_res = ReposListResult(total_repos=1, repos=[repo_entry])
    assert repos_res.total_repos == 1

    status_req = ReposStatusRequest(dirty_only=True)
    assert status_req.dirty_only is True
    status_entry = RepoStatusEntry(
        name="devops-cli",
        path="/workspaces/devops-cli",
        branch="release/v0.2.5",
        is_clean=True,
        uncommitted_files_count=0,
        commits_ahead=0,
        commits_behind=0,
    )
    status_res = ReposStatusResult(total_repos=1, dirty_repos_count=0, repos=[status_entry])
    assert status_res.dirty_repos_count == 0

    sync_req = ReposSyncRequest(branch="main", prune=True)
    assert sync_req.prune is True
    sync_res = ReposSyncResult(repos_synced=1, failed_repos=[], success=True)
    assert sync_res.success is True


def test_review_request_models_roundtrip() -> None:
    """Verify review path, branch, and PR request models."""
    review_p_req = ReviewPathRequest(target="src/devops_cli", pattern="*.py", persona="devsecops")
    assert review_p_req.target == "src/devops_cli"

    review_b_req = ReviewBranchRequest(branch="feat/test", base="main", persona="architect")
    assert review_b_req.base == "main"

    review_pr_req = ReviewPRRequest(number=42, post=True, persona="devsecops")
    assert review_pr_req.number == 42


def test_review_findings_and_stats_models_roundtrip() -> None:
    """Verify review findings, verification, stats, and feedback export models."""
    finding_req = ReviewFindingsRequest(session_id="20260827-test")
    assert finding_req.session_id == "20260827-test"
    finding_item = FindingSummaryEntry(
        finding_id="F001",
        title="Insecure Token Ingest",
        severity="HIGH",
        location="src/auth.py:45",
        status="VERIFIED",
        persona="devsecops",
    )
    findings_res = ReviewFindingsResult(
        session_id="20260827-test", total_findings=1, findings=[finding_item]
    )
    assert findings_res.total_findings == 1

    verify_req = VerifyFindingRequest(
        finding_id="F001", action="verify", reason="Confirmed genuine vulnerability"
    )
    assert verify_req.action == "verify"
    verify_res = VerifyFindingResult(finding_id="F001", updated_status="VERIFIED", success=True)
    assert verify_res.success is True

    stats_req = ReviewStatsRequest(limit_sessions=5)
    assert stats_req.limit_sessions == 5
    stats_res = ReviewStatsResult(
        total_sessions_analyzed=5,
        total_findings=20,
        verified_findings=18,
        invalidated_findings=2,
        accuracy_rate=0.9,
        persona_distribution={"devsecops": 12, "architect": 8},
    )
    assert stats_res.accuracy_rate == 0.9

    fb_req = ExportFeedbackRequest(output_path=".data/feedback.jsonl")
    assert fb_req.output_path == ".data/feedback.jsonl"
    fb_res = ExportFeedbackResult(
        output_path=".data/feedback.jsonl", total_records_exported=10, success=True
    )
    assert fb_res.total_records_exported == 10


def test_rag_resource_models_roundtrip() -> None:
    """Verify RAG search and index request and result models."""
    rag_req = RAGSearchRequest(query="def main")
    assert rag_req.query == "def main"
    rag_chunk = RAGChunkResult(
        file_path="src/main.py", chunk_index=0, content="def main(): pass", score=0.92
    )
    rag_res = RAGSearchResult(query="def main", chunks=[rag_chunk], total_chunks=1)
    assert rag_res.total_chunks == 1

    rag_idx_req = RAGIndexRequest(target_dir="src", force_refresh=True)
    assert rag_idx_req.force_refresh is True
    rag_idx_res = RAGIndexResult(
        target_dir="src", indexed_files=50, total_chunks_created=200, success=True
    )
    assert rag_idx_res.total_chunks_created == 200


def test_telemetry_resource_models_roundtrip() -> None:
    """Verify telemetry status and test span models."""
    tel_req = TelemetryStatusRequest(include_metrics=True)
    assert tel_req.include_metrics is True
    tel_res = TelemetryStatusResult(
        tracing_enabled=True,
        otlp_endpoint="http://127.0.0.1:4318",
        service_name="devops-cli",
        metrics_count=15,
        active_spans_count=0,
    )
    assert tel_res.tracing_enabled is True

    span_req = TelemetryTestSpanRequest(name="test.span", attributes={"test": True})
    assert span_req.name == "test.span"
    span_res = TelemetryTestSpanResult(
        trace_id="0123456789abcdef0123456789abcdef",
        span_id="0123456789abcdef",
        sent=True,
    )
    assert span_res.sent is True


def test_domain_model_registry_completeness() -> None:
    """Verify models.__all__ exports all domain request and result models."""
    exported = set(models.__all__)
    expected_models = {
        "DockerPruneRequest",
        "DockerPruneResult",
        "DockerStatsRequest",
        "DockerStatsResult",
        "K8sPodsRequest",
        "K8sPodsResult",
        "K8sClusterStatusRequest",
        "K8sClusterStatusResult",
        "SecurityScanRequest",
        "SecurityScanResult",
        "TFPlanRequest",
        "TFPlanResult",
        "ConfigShowRequest",
        "ConfigShowResult",
        "WorkspaceListRequest",
        "WorkspaceListResult",
        "ReleaseStatusRequest",
        "ReleaseStatusResult",
        "CIRunRequest",
        "CIRunResult",
        "ReviewPathRequest",
        "ReviewBranchRequest",
        "ReviewPRRequest",
        "VerifyFindingRequest",
        "VerifyFindingResult",
        "RAGSearchRequest",
        "RAGSearchResult",
        "TelemetryStatusRequest",
        "TelemetryStatusResult",
    }
    for m in expected_models:
        assert m in exported, f"Missing {m} in models.__all__"
        assert hasattr(models, m), f"Missing attribute {m} on models package"
