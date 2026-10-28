"""What `devops k8s audit` runs and tells the user: Popeye in the tool sandbox with the network
profile `kube-api`, and a pass only when Popeye ran and found nothing (#2132).

These cases fake the process edge with `process_fake`, so no sandbox, proxy or Popeye starts. The
fake finds each program that the audit looks for at `/usr/local/bin/<name>`, and bubblewrap at a
stand-in. Popeye answers with its recorded report of a lab cluster
(`tests/fixtures/scanner_runs/runs_with_findings.json`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_KUBE_API_HOST_SCRIPT
from devops_cli.lang import MESSAGES
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.paths import FIXTURES

_UID_MAP_REFUSED = "bwrap: setting up uid map: Permission denied"


def _recorded_report() -> dict[str, Any]:
    """The recorded report of Popeye, with six issues in two of its sections."""
    runs = json.loads((FIXTURES / "scanner_runs" / "runs_with_findings.json").read_text("utf-8"))
    report: dict[str, Any] = json.loads(runs["popeye"]["stdout"])
    return report


def _clean_report() -> dict[str, Any]:
    """The recorded report of Popeye with no issue in any section."""
    report = _recorded_report()
    for section in report["popeye"]["sections"]:
        section.pop("issues", None)
    return report


def _config_view(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `kubectl config view --minify --output=json` prints: the current context `example`,
    with the namespace `apps` and the credentials redacted."""
    view = {
        "current-context": "example",
        "contexts": [
            {
                "name": "example",
                "context": {"cluster": "example", "user": "example", "namespace": "apps"},
            }
        ],
        "users": [{"name": "example", "user": {"token": "REDACTED"}}],
    }
    return subprocess.CompletedProcess(list(call.argv), 0, json.dumps(view), "")


def _is_kube_api_run(call: ProcessCall) -> bool:
    """Whether `call` is the run of Popeye through the relay to the API server."""
    return CONST_KUBE_API_HOST_SCRIPT in call.argv


@pytest.fixture
def cluster(
    process_fake: ProcessFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ProcessFake:
    """A host that can start the sandbox, with a kubeconfig of the context `example`. Popeye
    answers with its recorded report."""
    bwrap = tmp_path / "bwrap-bin" / "bwrap"
    bwrap.parent.mkdir()
    bwrap.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    bwrap.chmod(0o755)
    which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, *a, **k: str(bwrap) if name == "bwrap" else which(name, *a, **k),
    )
    process_fake.answer(
        lambda call: call.argv[1:3] == ("config", "view"), ProcessAnswer(side_effect=_config_view)
    )
    process_fake.answer(
        _is_kube_api_run, ProcessAnswer(returncode=1, stdout=json.dumps(_recorded_report()))
    )
    return process_fake


def test_k8s_audit_runs_popeye_in_the_sandbox_with_the_kube_api_profile(
    cli: Any, cluster: ProcessFake
) -> None:
    """The audit starts `kubectl proxy` for the current context outside bubblewrap, and Popeye in
    bubblewrap with no network of its own, over every namespace (`-A`), from an empty directory
    that does not stay. It shows the findings of Popeye and exits 0."""
    result = cli("k8s", "audit")

    runs = [call for call in cluster.calls if _is_kube_api_run(call)]
    assert len(runs) == 1
    argv, cwd = runs[0].argv, runs[0].cwd
    bwrap = argv.index(shutil.which("bwrap"))
    assert (
        argv[7],
        "--unshare-all" in argv[bwrap:],
        "--share-net" in argv,
        argv[-6:],
        argv[argv.index("--chdir") + 1] == str(cwd),
        cwd is not None and cwd.exists(),
        "[POP-500] Zero scale detected" in result.output,
        result.exit_code,
    ) == (
        "example",
        True,
        False,
        (shutil.which("popeye"), "-o", "json", "-l", "warn", "-A"),
        True,
        False,
        True,
        0,
    )


def test_k8s_audit_passes_only_when_popeye_ran_and_found_nothing(
    cli: Any, cluster: ProcessFake
) -> None:
    """Popeye ran and its report has no issue, so the audit reports the pass and exits 0."""
    cluster.answer(_is_kube_api_run, ProcessAnswer(stdout=json.dumps(_clean_report())))

    result = cli("k8s", "audit")

    runs = [call for call in cluster.calls if _is_kube_api_run(call)]
    assert (len(runs), MESSAGES.k8s.popeye_passed in result.output, result.exit_code) == (
        1,
        True,
        0,
    )


def test_k8s_audit_fails_when_popeye_did_not_run(cli: Any, cluster: ProcessFake) -> None:
    """On a host whose kernel refuses bubblewrap a user namespace, Popeye does not run. The audit
    says so with the status and the cause, reports no pass, and exits 1."""
    cluster.answer(
        lambda call: call.argv[0] == shutil.which("bwrap"),
        ProcessAnswer(returncode=1, stderr=f"{_UID_MAP_REFUSED}\n"),
    )

    result = cli("k8s", "audit")

    not_run = MESSAGES.k8s.popeye_not_run.format(
        status="coverage_gap",
        reason=f"bubblewrap cannot make a sandbox on this host: {_UID_MAP_REFUSED}",
    )
    assert (
        " ".join(not_run.split()) in " ".join(result.output.split()),
        MESSAGES.k8s.popeye_passed in result.output,
        [call for call in cluster.calls if _is_kube_api_run(call)],
        result.exit_code,
    ) == (True, False, [], 1)
