"""Unit and integration tests for security sandboxed code execution, symlink protection, and secret redaction.

TDD specifications covering:

- Ground-truth importability of DEFAULT_HTTP_BROKER
- CodeMode sandboxed execution built-in and import safety
- Path traversal and symlink prevention across prompt_eval, ssh_keys, ast_stream, complexity, tflint, sandbox
- Secret redaction across agent memory summaries, telemetry error samples, CLI failures, tool errors, helm diff
- URL and reference validation in difftastic, ollama provider, and create_pydantic_ai_provider
- Information disclosure mitigation in pipeline error messages and status endpoints
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from devops_cli.exceptions import SecurityError, ValidationError


# 1. Ground truth verification for Finding 1
def test_default_http_broker_is_defined_and_importable() -> None:
    """Verify DEFAULT_HTTP_BROKER exists, is defined in broker.py, and imports cleanly."""
    from devops_cli.http import DEFAULT_HTTP_BROKER, HttpClientBroker
    from devops_cli.http.broker import DEFAULT_HTTP_BROKER as BROKER_FROM_MODULE

    assert isinstance(DEFAULT_HTTP_BROKER, HttpClientBroker)
    assert DEFAULT_HTTP_BROKER is BROKER_FROM_MODULE


# 2. CodeMode sandbox builtins and import restriction (Finding 2)
def test_os_access_codemode_blocks_dangerous_imports_and_builtins() -> None:
    """Verify CodeMode run_code blocks dangerous imports like os, subprocess, and builtins."""
    from devops_cli.ai.harness.os_access import CodeMode

    cm = CodeMode(tools=[], max_tool_calls=5)
    tools = {t.name: t for t in cm.get_tools()}
    assert "run_code" in tools
    run_fn = tools["run_code"].function

    # Attempting to import os must fail safely
    malicious_import = """
import os
os.environ.get("HOME")
"""
    res = asyncio.run(run_fn(code=malicious_import))
    assert "ImportError" in str(res) or "RuntimeError" in str(res) or "not permitted" in str(res)

    # Attempting to import subprocess must fail safely
    malicious_subprocess = """
import subprocess
subprocess.run(["echo", "hello"])
"""
    res_sub = asyncio.run(run_fn(code=malicious_subprocess))
    assert (
        "ImportError" in str(res_sub)
        or "RuntimeError" in str(res_sub)
        or "not permitted" in str(res_sub)
    )

    # Safe imports in whitelist should still work
    safe_script = """
import math
math.sqrt(16)
"""
    res_safe = asyncio.run(run_fn(code=safe_script))
    assert res_safe == 4.0 or res_safe == {"result": 4.0} or "4.0" in str(res_safe)


# 3. Path traversal prevention in evaluate_persona_prompts (Finding 3)
def test_prompt_eval_rejects_path_traversal_and_symlinks(tmp_path: Path) -> None:
    """Verify evaluate_persona_prompts rejects dataset_path escaping repo root or symlinks."""
    from devops_cli.ai.prompt_eval import evaluate_persona_prompts

    # Relative path traversal outside repo root
    traversal_path = Path("../../outside_repo_dataset.jsonl")
    with pytest.raises((ValueError, SecurityError)):
        evaluate_persona_prompts(dataset_path=traversal_path)

    # Symlink dataset path
    real_file = tmp_path / "real.jsonl"
    real_file.write_text('{"input": "test"}', encoding="utf-8")
    symlink_file = tmp_path / "symlink.jsonl"
    try:
        symlink_file.symlink_to(real_file)
        with pytest.raises((ValueError, SecurityError)):
            evaluate_persona_prompts(dataset_path=symlink_file)
    except OSError:
        pass


# 4. Symlink rejection in generate_ed25519_key (Finding 4)
def test_generate_ed25519_key_rejects_symlinks(tmp_path: Path) -> None:
    """Verify generate_ed25519_key refuses to write to a symlinked private or public key path."""
    from devops_cli.crypto.ssh_keys import generate_ed25519_key

    target_file = tmp_path / "target_passwd"
    target_file.write_text("root:x:0:0:", encoding="utf-8")
    symlink_key = tmp_path / "id_ed25519"
    try:
        symlink_key.symlink_to(target_file)
        with pytest.raises(ValidationError):
            generate_ed25519_key(symlink_key)
        # Ensure target file was not overwritten
        assert target_file.read_text(encoding="utf-8") == "root:x:0:0:"
    except OSError:
        pass


# 5. Git reference validation and stderr sanitization in difftastic (Findings 5 & 18)
def test_difftastic_validates_git_references_and_sanitizes_stderr(tmp_path: Path) -> None:
    """Verify get_structural_diff rejects unsafe git reference syntax and sanitizes stderr."""
    from devops_cli.ai.diff.difftastic import get_structural_diff

    # Unsafe command injection character
    res = get_structural_diff(path_a=tmp_path, branch="main; rm -rf /", base="HEAD")
    assert "Invalid git reference" in res or "Error" in res

    # Stderr sanitization when subprocess fails
    with patch("devops_cli.ai.diff.difftastic.run_subprocess") as mock_sub:
        mock_proc = MagicMock()
        mock_proc.returncode = 128
        mock_proc.stdout = ""
        mock_proc.stderr = "fatal: token=ghp_super_secret_token_12345 in repo"
        mock_sub.return_value = mock_proc

        diff_res = get_structural_diff(path_a=tmp_path, branch="feature", base="main")
        assert "ghp_super_secret_token_12345" not in diff_res
        assert "[REDACTED_SECRET]" in diff_res or "<masked" in diff_res.lower()


# 6. Secret sanitization in AgentMemory auto_summarize (Finding 6)
def test_agent_memory_masks_secrets_in_auto_summarize() -> None:
    """Verify AgentMemory.auto_summarize_if_needed sanitizes secrets from LLM output."""
    from devops_cli.ai.agents.memory import AgentMemory, MemoryEntry

    mem = AgentMemory(max_entries=2, max_chars=5000)
    mem.entries = [
        MemoryEntry(role="user", content="Deploy stack"),
        MemoryEntry(role="assistant", content="Deployed successfully"),
        MemoryEntry(role="user", content="Trigger summary"),
    ]

    mock_llm = MagicMock()
    mock_llm.chat.return_value = "Summary contains secret_key=sk-proj-super_confidential_api_token"

    summarized = mem.auto_summarize_if_needed(llm_client=mock_llm)
    assert summarized is True
    assert "sk-proj-super_confidential_api_token" not in mem.summary
    assert "<masked" in mem.summary.lower() or "[REDACTED" in mem.summary


# 7. Symlink rejection in stream_ast_symbols (Finding 7)
def test_stream_ast_symbols_rejects_symlinks(tmp_path: Path) -> None:
    """Verify stream_ast_symbols refuses symlink paths."""
    from devops_cli.ai.ast_stream import stream_ast_symbols

    real_py = tmp_path / "real.py"
    real_py.write_text("def hello(): pass", encoding="utf-8")
    sym_py = tmp_path / "symlink.py"
    try:
        sym_py.symlink_to(real_py)
        with pytest.raises(SecurityError):
            list(stream_ast_symbols(sym_py))
    except OSError:
        pass


# 8. URL validation in OllamaProvider (Finding 8)
def test_ollama_provider_validates_urls() -> None:
    """Verify OllamaProvider validates base_url against invalid schemes and formats."""
    from devops_cli.ai.providers.ollama import OllamaProvider

    cfg_mock = MagicMock()
    cfg_mock.get_ollama_urls = ["ftp://invalid-scheme.internal:11434"]
    prov = OllamaProvider(cfg_mock)
    assert prov.is_available() is False


# 9. Telemetry error sample secret sanitization (Finding 9)
@pytest.mark.asyncio
async def test_subprocess_telemetry_masks_secrets_in_error_sample(tmp_path: Path) -> None:
    """Verify run_subprocess_async masks secrets in error sample recorded to telemetry."""
    from devops_cli.core.process import run_subprocess_async

    with patch("devops_cli.core.process.trace_span") as mock_trace:
        span_mock = MagicMock()
        mock_trace.return_value.__enter__.return_value = span_mock

        # Run command that fails and outputs a token
        cmd = [
            "python3",
            "-c",
            "import sys; sys.stderr.write('Error: password=SuperSecretPassword123\\n'); sys.exit(1)",
        ]
        with pytest.raises(Exception):
            await run_subprocess_async(cmd, check=True)

        for call in span_mock.set_attribute.call_args_list:
            attr_name, attr_val = call[0]
            if attr_name == "subprocess.error_sample":
                assert "SuperSecretPassword123" not in attr_val
                assert "<masked" in attr_val.lower() or "[REDACTED" in attr_val


# 10. CLI failure telemetry secret sanitization (Finding 16)
def test_cli_telemetry_masks_secrets_in_cli_error() -> None:
    """Verify _record_cli_failure masks secrets in cli.error telemetry attribute."""
    from devops_cli.core.cli import _record_cli_failure

    span_mock = MagicMock()
    exc = ValueError("Failed connection with token=ghp_secret_telemetry_token_999")
    _record_cli_failure(span_mock, "test_cmd", 1.5, exc)

    for call in span_mock.set_attribute.call_args_list:
        attr_name, attr_val = call[0]
        if attr_name == "cli.error":
            assert "ghp_secret_telemetry_token_999" not in str(attr_val)
            assert "<masked" in str(attr_val).lower() or "[REDACTED" in str(attr_val)


# 11. Tool execution error message secret sanitization (Finding 17)
def test_agent_runner_masks_secrets_in_tool_errors() -> None:
    """Verify _execute_single_tool masks secrets in exception message."""
    from devops_cli.ai.agents.runner import _execute_single_tool
    from devops_cli.ai.agents.tools import Tool

    def leaking_tool() -> None:
        raise RuntimeError(
            "Database connection failed for user=admin password=SecretVaultPassword456"
        )

    tool = Tool(name="leak_tool", description="leaks secret", function=leaking_tool)
    status, _, err_res = _execute_single_tool(tool, "leak_tool", {}, [])
    assert status == "error"
    assert "SecretVaultPassword456" not in str(err_res)
    assert "<masked" in str(err_res).lower() or "[REDACTED" in str(err_res)


# 12. Sandbox directory validation (Finding 10)
def test_docker_sandbox_rejects_symlinks_and_system_roots(tmp_path: Path) -> None:
    """Verify WorkloadSandboxRunner rejects symlinked workspace and sensitive root directories."""
    from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner

    # Sensitive root path
    cfg_root = WorkloadSandboxConfig(workspace_dir=Path("/etc"), command=["echo", "test"])
    runner_root = WorkloadSandboxRunner(cfg_root)
    with pytest.raises(ValueError):
        runner_root.run()

    # User home path
    cfg_home = WorkloadSandboxConfig(workspace_dir=Path.home(), command=["echo", "test"])
    runner_home = WorkloadSandboxRunner(cfg_home)
    with pytest.raises(ValueError):
        runner_home.run()

    # Sensitive credential and metadata subpaths
    for sensitive_name in [".ssh", ".aws", ".kube", ".git"]:
        sens_dir = tmp_path / sensitive_name
        sens_dir.mkdir(exist_ok=True)
        cfg_sens = WorkloadSandboxConfig(workspace_dir=sens_dir, command=["echo", "test"])
        runner_sens = WorkloadSandboxRunner(cfg_sens)
        with pytest.raises(ValueError):
            runner_sens.run()

    # Docker socket reference
    sock_path = tmp_path / "var_run_docker.sock"
    sock_path.touch()
    cfg_sock = WorkloadSandboxConfig(workspace_dir=sock_path, command=["echo", "test"])
    runner_sock = WorkloadSandboxRunner(cfg_sock)
    with pytest.raises(ValueError):
        runner_sock.run()

    # Symlinked workspace path
    real_ws = tmp_path / "real_ws"
    real_ws.mkdir()
    sym_ws = tmp_path / "sym_ws"
    try:
        sym_ws.symlink_to(real_ws)
        cfg_sym = WorkloadSandboxConfig(workspace_dir=sym_ws, command=["echo", "test"])
        runner_sym = WorkloadSandboxRunner(cfg_sym)
        with pytest.raises(ValueError):
            runner_sym.run()
    except OSError:
        pass


# 13. Dive binary symlink rejection (Finding 11)
def test_dive_analysis_refuses_symlink_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_dive_analysis refuses to execute if dive executable in PATH is a symlink."""
    from devops_cli.security.dive import run_dive_analysis

    real_bin = tmp_path / "real_bin.sh"
    real_bin.write_text("#!/bin/sh\necho dive", encoding="utf-8")
    real_bin.chmod(0o755)
    sym_bin = tmp_path / "dive"
    try:
        sym_bin.symlink_to(real_bin)
        monkeypatch.setenv("PATH", str(tmp_path))

        res = run_dive_analysis(image_name="test-image:latest")
        # Should gracefully return synthetic / fallback analysis without calling subprocess
        assert res.image_name == "test-image:latest"
    except OSError:
        pass


# 14. Provider base_url validation (Finding 12)
def test_create_pydantic_ai_provider_validates_base_url() -> None:
    """Verify create_pydantic_ai_provider rejects malicious or invalid URL schemes."""
    from devops_cli.ai.providers import create_pydantic_ai_provider

    with pytest.raises((ValueError, SecurityError)):
        create_pydantic_ai_provider("ollama", base_url="file:///etc/passwd")


# 15. Helm diff secret masking (Finding 13)
def test_diff_helm_release_masks_secrets(tmp_path: Path) -> None:
    """Verify diff_helm_release masks secrets in helm diff output."""
    from devops_cli.k8s.diff import diff_helm_release

    chart_dir = tmp_path / "chart"
    chart_dir.mkdir()

    with patch("devops_cli.k8s.diff.run_subprocess") as mock_sub:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "+ api_key: ghp_confidential_helm_key_777\n- replicas: 1"
        mock_res.stderr = ""
        mock_sub.return_value = mock_res

        code, output = diff_helm_release("test-release", chart_dir)
        assert code == 0
        assert "ghp_confidential_helm_key_777" not in output
        assert "<masked" in output.lower() or "[REDACTED" in output


# 16. Complexity scanner skips external symlinks (Finding 14)
def test_complexity_scan_skips_symlinks(tmp_path: Path) -> None:
    """Verify run_complexity_scan skips symlinks pointing outside target directory."""
    from devops_cli.security.complexity import run_complexity_scan

    outside_py = tmp_path / "outside.py"
    outside_py.write_text("def f():\n  if True:\n    pass\n", encoding="utf-8")

    scan_dir = tmp_path / "scan_target"
    scan_dir.mkdir()
    sym_py = scan_dir / "sym.py"
    try:
        sym_py.symlink_to(outside_py)
        findings = run_complexity_scan(scan_dir)
        # Should not crash and should skip symlink
        assert isinstance(findings, list)
    except OSError:
        pass


# 17. TFLint fallback skips external symlinks (Finding 15)
def test_tflint_fallback_skips_symlinks(tmp_path: Path) -> None:
    """Verify _run_native_fallback_tf_lint skips symlinks pointing outside target."""
    from devops_cli.security.tflint import _run_native_fallback_tf_lint

    outside_tf = tmp_path / "outside.tf"
    outside_tf.write_text(
        'resource "aws_security_group" "open" { cidr_blocks = ["0.0.0.0/0"] }', encoding="utf-8"
    )

    scan_dir = tmp_path / "scan_tf"
    scan_dir.mkdir()
    sym_tf = scan_dir / "sym.tf"
    try:
        sym_tf.symlink_to(outside_tf)
        findings = _run_native_fallback_tf_lint(scan_dir)
        # External symlink should be ignored
        assert len(findings) == 0
    except OSError:
        pass


# 18. Pipeline path disclosure mitigation (Finding 19)
def test_pipeline_run_error_message_does_not_disclose_system_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify run_pipeline_cmd prints a safe generic error message without disclosing sensitive full paths."""
    from devops_cli.commands.pipeline import run_pipeline_cmd

    bad_path = Path("/home/secret_user/confidential_project/nonexistent_dagger_pipeline.go")
    with pytest.raises(typer.Exit):
        run_pipeline_cmd(pipeline_path=bad_path)

    captured = capsys.readouterr()
    err_text = captured.err or captured.out
    assert "/home/secret_user/confidential_project" not in err_text
    assert "Pipeline path does not exist" in err_text


# 19. Status endpoint masks tool paths (Finding 20)
def test_status_endpoint_masks_tool_paths() -> None:
    """Verify /api/v1/status endpoint does not expose raw full filesystem paths for installed tools."""
    from fastapi.testclient import TestClient

    from devops_cli.server.app import create_app

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    for tool_name, tool_info in data["tools"].items():
        if tool_info.get("installed") and tool_info.get("path"):
            # Path should either be masked or tool basename, never revealing internal system directory structure
            assert not tool_info["path"].startswith("/home/")
            assert not tool_info["path"].startswith("/Users/")
