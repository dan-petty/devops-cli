"""Unit tests for Dive container layer efficiency analyzer."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.tools.builtin_tools import docker_analyze_layers
from devops_cli.commands.docker import app as docker_app
from devops_cli.security.dive import DiveScanner, run_dive_analysis
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

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


DiveStub = Callable[[ProcessCall], subprocess.CompletedProcess[str]]


def _writes_export(export: dict[str, Any]) -> DiveStub:
    """A dive that writes `export` to the file `--json` names, as wagoodman/dive does."""

    def dive(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        argv = list(call.argv)
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(export), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="Analyzing image...\n", stderr="")

    return dive


def _answer_dive(process_fake: ProcessFake, answer: ProcessAnswer) -> None:
    """Answer each run of dive, which `run_dive_analysis` starts from its path on PATH."""
    process_fake.answer(lambda call: Path(call.argv[0]).name == "dive", answer)


def _dive_runs(process_fake: ProcessFake) -> list[list[str]]:
    """The argv of each dive run the fake received."""
    return [list(call.argv) for call in process_fake.calls if Path(call.argv[0]).name == "dive"]


def test_dive_missing_reports_unavailable_without_inventing_layers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without dive on PATH there is no analysis: no layers, no score, and the tool says so."""
    empty_bin = tmp_path / "bin-without-dive"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Dive writes `--json <path>` to that file, never stdout; the export's real keys are parsed."""
    monkeypatch.chdir(tmp_path)  # a relative export path would land in the working directory
    _answer_dive(process_fake, ProcessAnswer(side_effect=_writes_export(_DIVE_EXPORT)))

    result = run_dive_analysis("my-app:v1")

    (seen,) = _dive_runs(process_fake)
    export_path = Path(seen[-1])
    assert seen[:3] == ["/usr/local/bin/dive", "my-app:v1", "--json"]
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


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        pytest.param(
            ProcessAnswer(side_effect=subprocess.TimeoutExpired(["dive"], 5)),
            "timed out",
            id="times-out",
        ),
        pytest.param(
            ProcessAnswer(returncode=1, stderr="image not found"), "image not found", id="exits-1"
        ),
        pytest.param(ProcessAnswer(), "dive wrote no JSON export", id="writes-no-export"),
    ],
)
def test_dive_failures_report_failed_with_the_reason(
    process_fake: ProcessFake, answer: ProcessAnswer, reason: str
) -> None:
    """A dive that raises, exits non-zero, or writes no export is a failed run, not a clean image."""
    _answer_dive(process_fake, answer)

    result = run_dive_analysis("img:1")

    assert (result.status, result.layers, result.efficiency_score, reason in result.reason) == (
        "failed",
        [],
        0.0,
        True,
    )


# A private key dive quotes in its error, long enough that a cut at the shared cap would drop its
# END marker, which the masking pattern needs (#915).
_KEY_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7" + "A" * 1000
# Joined at runtime so this file holds no key marker for the detect-private-key commit hook.
_PEM_LABEL = "PRIVATE" + " KEY"
_KEY_ERROR = (
    "cannot load registry credentials from "
    f"-----BEGIN {_PEM_LABEL}-----\n{_KEY_BODY}\n-----END {_PEM_LABEL}-----"
)


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (
            ProcessAnswer(returncode=1, stderr=f"error: {_KEY_ERROR}\n"),
            "dive exited with code 1: error: cannot load registry credentials from "
            "<masked-private-key>\n\n",
        ),
        (
            ProcessAnswer(side_effect=OSError(_KEY_ERROR)),
            "dive failed: cannot load registry credentials from <masked-private-key>\n\n",
        ),
    ],
    ids=["dive exits non-zero", "dive cannot be run"],
)
def test_a_dive_failure_masks_a_secret_before_it_is_cut(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    answer: ProcessAnswer,
    reason: str,
) -> None:
    """Verify a key in dive's error is masked whole wherever its reason goes.

    That is the analysis, the `devops scan` adapter, the `docker_analyze_layers` tool and
    `devops docker analyze-layers`, whose output is read with whitespace removed so that a wrapped
    line cannot hide the key.
    """
    monkeypatch.chdir(tmp_path)
    _answer_dive(process_fake, answer)

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """The `devops scan` adapter reads the same export file, so a wasteful image is a finding."""
    monkeypatch.chdir(tmp_path)
    wasteful = {**_DIVE_EXPORT, "image": {**_DIVE_EXPORT["image"], "efficiencyScore": 0.5}}
    _answer_dive(process_fake, ProcessAnswer(side_effect=_writes_export(wasteful)))

    outcome = DiveScanner().scan(tmp_path, image="my-app:v1")

    (seen,) = _dive_runs(process_fake)
    assert (outcome.status, [f.location for f in outcome.findings], "-" in seen) == (
        "ran",
        ["my-app:v1:efficiency"],
        False,
    )


def test_dive_passes_docker_host_when_endpoint_not_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """Dive sets DOCKER_HOST in subprocess env when resolved endpoint is not from DOCKER_HOST."""
    monkeypatch.chdir(tmp_path)
    socket = "unix:///run/user/1000/podman/podman.sock"
    monkeypatch.setenv("CONTAINER_HOST", socket)
    _answer_dive(process_fake, ProcessAnswer(side_effect=_writes_export(_DIVE_EXPORT)))

    analysis = run_dive_analysis("my-app:v1")

    (dive_call,) = [call for call in process_fake.calls if Path(call.argv[0]).name == "dive"]
    assert (analysis.status, (dive_call.env or {}).get("DOCKER_HOST")) == ("ran", socket)
