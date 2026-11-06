"""Unit tests for run_json_subprocess (TDD Specification)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.core.process import run_json_subprocess
from devops_cli.exceptions.base import DevOpsCLIError
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake


def test_run_json_subprocess_parses_json_stdout(process_fake: ProcessFake) -> None:
    """Parses JSON stdout into dict/list cleanly on success."""
    argv = ["kubectl", "get", "pods", "-o", "json"]
    process_fake.answer(
        argv,
        ProcessAnswer(stdout='{"kind": "PodList", "items": [{"name": "pod-1"}]}'),
    )

    res = run_json_subprocess(argv)

    assert res == {"kind": "PodList", "items": [{"name": "pod-1"}]}
    assert [call.argv for call in process_fake.calls] == [tuple(argv)]


def test_run_json_subprocess_sends_its_input_and_directory(
    process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The body and the working directory that the caller gives reach the child."""
    process_fake.answer(["jq", "."], ProcessAnswer(stdout="[1, 2]"))

    run_json_subprocess(["jq", "."], input="[1,2]", cwd=tmp_path)

    call: ProcessCall = process_fake.calls[0]
    assert (call.stdin, call.cwd) == ("[1,2]", tmp_path)


def test_run_json_subprocess_raises_on_nonzero_returncode(process_fake: ProcessFake) -> None:
    """Raises DevOpsCLIError when subprocess exits non-zero and check is True (default)."""
    process_fake.answer(
        ["kubectl", "get", "pods"],
        ProcessAnswer(returncode=1, stderr="Error from server: namespace not found"),
    )

    with pytest.raises(DevOpsCLIError) as exc_info:
        run_json_subprocess(["kubectl", "get", "pods"])

    assert "namespace not found" in str(exc_info.value) or "Subprocess failed" in str(
        exc_info.value
    )


def test_run_json_subprocess_handles_malformed_json_with_default(
    process_fake: ProcessFake,
) -> None:
    """Returns default value when stdout is not valid JSON and default is specified."""
    process_fake.answer(["helm", "list"], ProcessAnswer(stdout="not json text"))

    assert run_json_subprocess(["helm", "list"], default=[]) == []


def test_run_json_subprocess_raises_on_malformed_json_without_default(
    process_fake: ProcessFake,
) -> None:
    """Raises DevOpsCLIError when stdout is not valid JSON and no default is specified."""
    process_fake.answer(["helm", "list"], ProcessAnswer(stdout="not json text"))

    with pytest.raises(DevOpsCLIError) as raised:
        run_json_subprocess(["helm", "list"])

    assert raised.value.error_code == "SUBPROCESS_FAILED"


def test_run_json_subprocess_nonzero_returncode_allowed_when_check_false(
    process_fake: ProcessFake,
) -> None:
    """When check=False, parses valid JSON stdout even if returncode != 0 (e.g. invalid resources
    of kubeconform)."""
    argv = ["kubeconform", "-output", "json", "."]
    process_fake.answer(
        argv,
        ProcessAnswer(
            returncode=1,
            stdout='{"resources": [{"kind": "Service", "status": "statusInvalid"}]}',
        ),
    )

    res = run_json_subprocess(argv, check=False)

    assert res == {"resources": [{"kind": "Service", "status": "statusInvalid"}]}


def test_run_json_subprocess_nonzero_returncode_fallback_when_check_false(
    process_fake: ProcessFake,
) -> None:
    """When check=False and output is empty/invalid, returns default fallback."""
    argv = ["kubeconform", "-output", "json", "."]
    process_fake.answer(argv, ProcessAnswer(returncode=2, stderr="Fatal error"))

    assert run_json_subprocess(argv, default={}, check=False) == {}
