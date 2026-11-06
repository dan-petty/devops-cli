"""Tests for `devops docker sign` and `devops docker verify`.

The commands run through `cli`. Cosign is a program: a test scripts its answer on `process_fake`.
A host without Cosign is a `PATH` with no program in it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.process import ProcessAnswer, ProcessFake

IMAGE = "example.com/app:1.0.0"


def test_sign_dry_run_renders_the_plan(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """Validate 'devops docker sign --dry-run' renders dry-run output cleanly."""
    result = cli("docker", "sign", IMAGE, "--annotation", "team=infra", "--dry-run")

    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "action" in result.output.lower()
    assert process_fake.calls == []


def test_verify_dry_run_renders_the_plan(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """Validate 'devops docker verify --dry-run' renders dry-run output cleanly."""
    result = cli(
        "docker",
        "verify",
        IMAGE,
        "--certificate-identity",
        "https://example.com/workflows/build.yml",
        "--certificate-oidc-issuer",
        "https://example.com/oidc",
        "--dry-run",
    )

    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "action" in result.output.lower()
    assert process_fake.calls == []


def test_sign_and_verify_report_success(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """Validate 'devops docker sign' and 'verify' execute cosign and report the outcome."""
    process_fake.answer(
        "cosign sign",
        ProcessAnswer(stdout="Pushing signature to: example.com/app:sha256-abc.sig\n"),
    )
    process_fake.answer("cosign verify", ProcessAnswer(stdout='[{"optional": {"Issuer": "x"}}]'))

    sign_res = cli("docker", "sign", IMAGE)
    verify_res = cli("docker", "verify", IMAGE, "--key", "/path/to/key.pub")

    assert sign_res.exit_code == 0
    assert "signed successfully" in sign_res.output.lower()
    assert verify_res.exit_code == 0
    assert "verified" in verify_res.output.lower()
    assert [call.argv[:2] for call in process_fake.calls] == [
        ("cosign", "sign"),
        ("cosign", "verify"),
    ]


@pytest.mark.parametrize("subcommand", ["sign", "verify"])
def test_a_missing_cosign_program_ends_the_command_with_an_error(
    subcommand: str, cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate CLI handles missing cosign executable gracefully."""
    empty = tmp_path / "no-programs"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    result = cli("docker", subcommand, IMAGE)

    assert result.exit_code != 0
    assert "cosign" in result.output.lower()


def test_verify_reports_a_failed_check(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """Validate CLI verify handles CosignVerificationError cleanly."""
    process_fake.answer("cosign", ProcessAnswer(returncode=1, stderr="verification failed"))

    result = cli("docker", "verify", IMAGE)

    assert result.exit_code != 0
    assert "verification failed" in result.output.lower()
