"""The Semgrep and uv audit tools run their scanner adapters with the ruleset or directory that the caller names."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from devops_cli.ai.mcp.server import (
    mcp,
)
from tests.support.fakes.scanners import ScannerFake
from tests.support.registry_cache import CACHED_RULESET_FILE_NAME


@pytest.mark.usefixtures("cached_default_ruleset")
def test_the_mcp_semgrep_tool_scans_with_the_default_ruleset_unless_the_caller_names_one(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The MCP `scan_sast` tool runs the Semgrep adapter with `DEFAULT_SEMGREP_CONFIG`, read from
    its cached ruleset, and with the ruleset that the caller names in its place (#1435). A local
    path that the caller names resolves under the work tree (#3480)."""
    monkeypatch.chdir(tmp_path)

    for arguments in ({"target": str(tmp_path)}, {"target": str(tmp_path), "config": "./rules"}):
        asyncio.run(mcp.call_tool("scan_sast", arguments, run_middleware=False))

    assert [run.argv[run.argv.index("--config") + 1] for run in scanner_fake.runs] == [
        f"./{CACHED_RULESET_FILE_NAME}",
        str(tmp_path / "rules"),
    ]


def test_the_mcp_uv_audit_tool_takes_a_directory_and_runs_the_uv_audit_adapter_there(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The MCP `scan_uv_audit` tool takes only the directory of the project, and runs the uv audit
    adapter there, as the agent tool does (#2106)."""
    monkeypatch.chdir(tmp_path)
    recorded = scanner_fake.script_run_with_findings("uv", tree=tmp_path.resolve())

    tool = asyncio.run(mcp.get_tool("scan_uv_audit"))
    result = asyncio.run(
        mcp.call_tool("scan_uv_audit", {"directory": str(tmp_path)}, run_middleware=False)
    )

    assert (tool.parameters["properties"], scanner_fake.runs, result.content[0].text) == (
        {"directory": {"default": ".", "type": "string"}},
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
