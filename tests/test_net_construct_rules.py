"""Tests for the ast-grep network construct rules and banned socket APIs (#1107)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import (
    CONST_AST_GREP_SCAN_ARGS,
    CONST_BANNED_HAND_ROLLED_APIS,
)

pytestmark = pytest.mark.live("ast-grep", "ruff")


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


def test_ast_grep_scan_detects_net_address_list(tmp_path: Path) -> None:
    """ast-grep scan detects literal address/scheme lists in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text('bad_sans = ["localhost", "127.0.0.1"]\n', encoding="utf-8")

    res = subprocess.run(
        ["ast-grep", "scan", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "net-address-list" in res.stdout or "net-address-list" in res.stderr


def test_ast_grep_scan_detects_net_scheme_in(tmp_path: Path) -> None:
    """ast-grep scan detects scheme substring test '://' in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text('if "://" in url:\n    pass\n', encoding="utf-8")

    res = subprocess.run(
        ["ast-grep", "scan", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "net-scheme-in" in res.stdout or "net-scheme-in" in res.stderr


def test_ast_grep_scan_detects_net_scheme_affix(tmp_path: Path) -> None:
    """ast-grep scan detects scheme/address prefix or suffix tests in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text('secure = url.startswith("https://")\n', encoding="utf-8")

    res = subprocess.run(
        ["ast-grep", "scan", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "net-scheme-affix" in res.stdout or "net-scheme-affix" in res.stderr


def test_ast_grep_scan_detects_net_bracket_affix(tmp_path: Path) -> None:
    """ast-grep scan detects hand-rolled IPv6 bracket affix tests in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text('is_v6 = host.startswith("[") and ":" in host\n', encoding="utf-8")

    res = subprocess.run(
        ["ast-grep", "scan", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "net-bracket-affix" in res.stdout or "net-bracket-affix" in res.stderr


def test_ast_grep_scan_detects_net_url_build(tmp_path: Path) -> None:
    """ast-grep scan detects f-string URL authority formatting in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text('url = f"http://{host}:{port}"\n', encoding="utf-8")

    res = subprocess.run(
        ["ast-grep", "scan", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "net-url-build" in res.stdout or "net-url-build" in res.stderr


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
