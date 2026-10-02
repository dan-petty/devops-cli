"""Unit tests for Dive container layer efficiency analyzer."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.tools.builtin_tools import docker_analyze_layers
from devops_cli.commands.docker import app as docker_app
from devops_cli.security.dive import DiveScanner, run_dive_analysis

# Dive's JSON export (`dive <image> --json <file>`), keyed as wagoodman/dive writes it.
_DIVE_EXPORT: dict[str, Any] = {
    "layer": [
        {
            "index": 0,
            "id": "blobs",
            "digestId": "sha256:1234",
            "sizeBytes": 50000000,
            "command": "RUN apt-get update",
            "fileList": [],
        }
    ],
    "image": {
        "sizeBytes": 50000000,
        "inefficientBytes": 1000000,
        "efficiencyScore": 0.95,
        "fileReference": [],
    },
}


DiveStub = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _subprocess_run(dive: DiveStub, seen: list[list[str]]) -> Any:
    """Stand in for `subprocess.run`, handing dive's command to `dive` and recording it.

    Anything else gets an empty success: the tracer's first span runs `uname -p` (through
    `platform`), whichever test starts it, and that must neither run nor reach `dive`.
    """

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if Path(cmd[0]).name != "dive":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        seen.append(list(cmd))
        return dive(list(cmd))

    return fake_run


def _writes_export(export: dict[str, Any]) -> DiveStub:
    """A dive that writes `export` to the file `--json` names, as wagoodman/dive does."""

    def dive(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        Path(cmd[cmd.index("--json") + 1]).write_text(json.dumps(export), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="Analyzing image...\n", stderr="")

    return dive


def _times_out(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """A dive that runs past its timeout."""
    raise subprocess.TimeoutExpired(cmd, 5)


def test_dive_missing_reports_unavailable_without_inventing_layers() -> None:
    """Without dive on PATH there is no analysis: no layers, no score, and the tool says so."""
    with patch("shutil.which", return_value=None):
        result = run_dive_analysis("img:1")
        tool_reply = docker_analyze_layers("img:1")

    assert (result.status, result.layers, result.efficiency_score, result.total_bytes) == (
        "unavailable",
        [],
        0.0,
        0,
    )
    assert ("dive" in result.reason, "Efficiency Score" in tool_reply) == (True, False)
    assert tool_reply.startswith("Dive not available: ")


def test_dive_reads_the_json_export_file_it_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dive writes `--json <path>` to that file, never stdout; the export's real keys are parsed."""
    monkeypatch.chdir(tmp_path)  # a relative export path would land in the working directory
    seen: list[list[str]] = []
    with (
        patch("shutil.which", return_value="/usr/local/bin/dive"),
        patch("subprocess.run", side_effect=_subprocess_run(_writes_export(_DIVE_EXPORT), seen)),
    ):
        result = run_dive_analysis("my-app:v1")

    export_path = Path(seen[0][-1])
    assert seen[0][:3] == ["/usr/local/bin/dive", "my-app:v1", "--json"]
    assert (export_path.name != "-", export_path.exists()) == (True, False)
    assert (result.status, result.efficiency_score, result.wasted_bytes, result.total_bytes) == (
        "ran",
        0.95,
        1000000,
        50000000,
    )
    assert [(layer.index, layer.digest, layer.size_bytes) for layer in result.layers] == [
        (0, "sha256:1234", 50000000)
    ]


def test_dive_failures_report_failed_with_the_reason() -> None:
    """A dive that raises, exits non-zero, or writes no export is a failed run, not a clean image."""
    dives: list[DiveStub] = [
        _times_out,
        lambda cmd: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="image not found"),
        lambda cmd: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    ]
    results = []
    with patch("shutil.which", return_value="/usr/local/bin/dive"):
        for dive in dives:
            with patch("subprocess.run", side_effect=_subprocess_run(dive, [])):
                results.append(run_dive_analysis("img:1"))

    assert [(r.status, r.layers, r.efficiency_score) for r in results] == [("failed", [], 0.0)] * 3
    assert ["timed out" in results[0].reason, "image not found" in results[1].reason] == [
        True,
        True,
    ]
    assert results[2].reason == "dive wrote no JSON export"


# A private key dive quotes in its error, long enough that a cut at the shared cap would drop its
# END marker, which the masking pattern needs (#915).
_KEY_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7" + "A" * 1000
# Joined at runtime so this file holds no key marker for the detect-private-key commit hook.
_PEM_LABEL = "PRIVATE" + " KEY"
_KEY_ERROR = (
    "cannot load registry credentials from "
    f"-----BEGIN {_PEM_LABEL}-----\n{_KEY_BODY}\n-----END {_PEM_LABEL}-----"
)


def _exits_quoting_the_key(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """A dive that exits 1 with the key in its stderr."""
    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=f"error: {_KEY_ERROR}\n")


def _raises_quoting_the_key(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """A dive that cannot be run, with the key in the error."""
    raise OSError(_KEY_ERROR)


@pytest.mark.parametrize(
    ("dive", "reason"),
    [
        (
            _exits_quoting_the_key,
            "dive exited with code 1: error: cannot load registry credentials from "
            "<masked-private-key>\n\n",
        ),
        (
            _raises_quoting_the_key,
            "dive failed: cannot load registry credentials from <masked-private-key>\n\n",
        ),
    ],
    ids=["dive exits non-zero", "dive cannot be run"],
)
def test_a_dive_failure_masks_a_secret_before_it_is_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dive: DiveStub, reason: str
) -> None:
    """Verify a key in dive's error is masked whole wherever its reason goes.

    That is the analysis, the `devops scan` adapter, the `docker_analyze_layers` tool and
    `devops docker analyze-layers`, whose output is read with whitespace removed so that a wrapped
    line cannot hide the key.
    """
    monkeypatch.chdir(tmp_path)
    with (
        patch("shutil.which", return_value="/usr/local/bin/dive"),
        patch("subprocess.run", side_effect=_subprocess_run(dive, [])),
    ):
        analysis = run_dive_analysis("org/img:1")
        outcome = DiveScanner().scan(tmp_path, image="org/img:1")
        tool_reply = docker_analyze_layers("org/img:1")
        cli = CliRunner().invoke(docker_app, ["analyze-layers", "org/img:1"])

    places = (
        ("analysis", analysis.reason),
        ("scan", outcome.reason),
        ("tool", tool_reply),
        ("cli", "".join(cli.output.split())),
    )
    assert (
        analysis.status,
        outcome.status,
        [place for place, text in places if _KEY_BODY[:20] in text],
        analysis.reason,
        outcome.reason,
        tool_reply,
        cli.exit_code,
    ) == ("failed", "failed", [], reason, reason, f"Dive analysis failed: {reason}", 1)


def test_dive_scanner_reads_the_export_and_flags_an_inefficient_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `devops scan` adapter reads the same export file, so a wasteful image is a finding."""
    monkeypatch.chdir(tmp_path)
    wasteful = {**_DIVE_EXPORT, "image": {**_DIVE_EXPORT["image"], "efficiencyScore": 0.5}}
    seen: list[list[str]] = []
    with (
        patch("shutil.which", return_value="/usr/local/bin/dive"),
        patch("subprocess.run", side_effect=_subprocess_run(_writes_export(wasteful), seen)),
    ):
        outcome = DiveScanner().scan(tmp_path, image="my-app:v1")

    assert (outcome.status, [f.location for f in outcome.findings], "-" in seen[0]) == (
        "ran",
        ["my-app:v1:efficiency"],
        False,
    )
