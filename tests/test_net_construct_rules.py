"""Tests for the ast-grep network construct rules and banned socket APIs (#1107)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import (
    CONST_AST_GREP_SCAN_ARGS,
    CONST_BANNED_HAND_ROLLED_APIS,
)


def test_ast_grep_network_construct_rule_tests_pass() -> None:
    """Every rule in .ast-grep/rules/ has unit tests that pass with ast-grep test."""
    res = subprocess.run(
        ["ast-grep", "test", "--skip-snapshot-tests"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"ast-grep test failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"


def test_ast_grep_scan_detects_hand_rolled_port_table(tmp_path: Path) -> None:
    """ast-grep scan detects the net-port-table construct in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text("port = 443 if tls else 80\n", encoding="utf-8")

    res = subprocess.run(
        ["ast-grep", "scan", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "net-port-table" in res.stdout or "net-port-table" in res.stderr


def test_ruff_tid251_detects_banned_socket_apis(tmp_path: Path) -> None:
    """Ruff TID251 flags banned socket.inet_* APIs in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text(
        "import socket\nfrom socket import inet_pton\nsocket.inet_aton('127.0.0.1')\n",
        encoding="utf-8",
    )

    res = subprocess.run(
        ["ruff", "check", "--select", "TID251", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    output = res.stdout + res.stderr
    assert "TID251" in output
    assert "Parse and format addresses with ipaddress.ip_address." in output
    assert "socket.inet_aton" in output
    assert "socket.inet_pton" in output


def test_ci_constructs_row_matches_constants() -> None:
    """The constructs row in devops ci runs the scan with CONST_AST_GREP_SCAN_ARGS."""
    spec = get_check_spec("constructs")
    assert spec.cmd == ["uv", "run", "ast-grep", *CONST_AST_GREP_SCAN_ARGS]
    assert len(CONST_BANNED_HAND_ROLLED_APIS) == 4
