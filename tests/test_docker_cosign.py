"""Unit and integration tests for Sigstore Cosign container provenance and signing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.config.commands import (
    BIN_COSIGN,
    build_cosign_sign_cmd,
    build_cosign_verify_cmd,
)
from devops_cli.docker.cosign import CosignRunner
from devops_cli.exceptions.docker import CosignError, CosignVerificationError
from devops_cli.exceptions.tools import DependencyError
from devops_cli.models.docker import (
    DockerSignRequest,
    DockerSignResult,
    DockerVerifyRequest,
    DockerVerifyResult,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing Typer CLI test runner."""
    return CliRunner()


# =============================================================================
# 1. Command Argument Builders
# =============================================================================


def test_build_cosign_sign_cmd_keyless() -> None:
    """Validate sign command builder in default keyless mode."""
    cmd = build_cosign_sign_cmd("example.com/app:1.0.0", keyless=True, upload=True)
    assert cmd == [BIN_COSIGN, "sign", "--yes", "example.com/app:1.0.0"]


def test_build_cosign_sign_cmd_keyed_and_annotations() -> None:
    """Validate sign command builder with explicit key and supply-chain annotations."""
    cmd = build_cosign_sign_cmd(
        "example.com/app:1.0.0",
        key="/path/to/cosign.key",
        keyless=False,
        upload=False,
        annotations=["git_commit=abcd1234", "build_env=ci"],
    )
    assert cmd == [
        BIN_COSIGN,
        "sign",
        "--key",
        "/path/to/cosign.key",
        "--upload=false",
        "-a",
        "git_commit=abcd1234",
        "-a",
        "build_env=ci",
        "example.com/app:1.0.0",
    ]


def test_build_cosign_verify_cmd_keyless() -> None:
    """Validate verify command builder with certificate identity and issuer."""
    cmd = build_cosign_verify_cmd(
        "example.com/app:1.0.0",
        cert_identity="https://example.com/workflows/build.yml@refs/heads/main",
        cert_issuer="https://example.com/oidc",
    )
    assert cmd == [
        BIN_COSIGN,
        "verify",
        "--output",
        "json",
        "--certificate-identity",
        "https://example.com/workflows/build.yml@refs/heads/main",
        "--certificate-oidc-issuer",
        "https://example.com/oidc",
        "example.com/app:1.0.0",
    ]


def test_build_cosign_verify_cmd_attestation_and_tlog() -> None:
    """Validate verify command builder for attestation predicates and offline/tlog flag."""
    cmd = build_cosign_verify_cmd(
        "example.com/app:1.0.0",
        key="/path/to/cosign.pub",
        attestation=True,
        predicate_type="slsaprovenance",
        insecure_ignore_tlog=True,
    )
    assert cmd == [
        BIN_COSIGN,
        "verify-attestation",
        "--output",
        "json",
        "--key",
        "/path/to/cosign.pub",
        "--type",
        "slsaprovenance",
        "--insecure-ignore-tlog=true",
        "example.com/app:1.0.0",
    ]


# =============================================================================
# 2. CosignRunner Core Logic
# =============================================================================


def test_cosign_runner_check_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate check_available returns boolean based on binary availability."""
    runner = CosignRunner()
    monkeypatch.setattr(
        "shutil.which", lambda name: "/usr/local/bin/cosign" if name == "cosign" else None
    )
    assert runner.check_available() is True

    monkeypatch.setattr("shutil.which", lambda name: None)
    assert runner.check_available() is False


def test_cosign_runner_require_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate require_binary raises DependencyError when cosign is missing."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(DependencyError) as exc_info:
        runner.require_binary()
    assert "cosign" in str(exc_info.value).lower()


def test_cosign_runner_sign_dry_run() -> None:
    """Validate sign_image in dry-run mode returns structured result without executing subprocess."""
    runner = CosignRunner()
    req = DockerSignRequest(
        image="example.com/app:1.0.0",
        keyless=True,
        annotations=["env=prod"],
        dry_run=True,
    )
    result = runner.sign_image(req)
    assert isinstance(result, DockerSignResult)
    assert result.image == "example.com/app:1.0.0"
    assert result.keyless is True
    assert result.annotations == ["env=prod"]
    assert result.success is True


def test_cosign_runner_sign_keyless_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate keyless sign_image executes cosign with simulated subprocess output."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 0
    mock_proc.stdout = "Pushing signature to: example.com/app:sha256-abc.sig\n"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        req = DockerSignRequest(image="example.com/app:1.0.0", keyless=True)
        res = runner.sign_image(req)
        assert res.success is True
        assert res.image == "example.com/app:1.0.0"
        assert res.signature_ref == "example.com/app:sha256-abc.sig"
        mock_run.assert_called_once()


def test_cosign_runner_sign_keyring_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Validate sign_image with private key stored in OS Keyring creates ephemeral key file."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")
    monkeypatch.setattr(
        "devops_cli.docker.cosign.get_keyring_secret",
        lambda key: (
            "-----BEGIN ENCRYPTED COSIGN PRIVATE KEY-----\ntest\n-----END ENCRYPTED COSIGN PRIVATE KEY-----"
            if key == "test_key"
            else None
        ),
    )

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 0
    mock_proc.stdout = "Pushing signature to: example.com/app:sha256-key.sig\n"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        req = DockerSignRequest(
            image="example.com/app:1.0.0", key="keyring:test_key", keyless=False
        )
        res = runner.sign_image(req)
        assert res.success is True
        mock_run.assert_called_once()
        called_cmd = mock_run.call_args[0][0]
        key_idx = called_cmd.index("--key")
        temp_key_path = Path(called_cmd[key_idx + 1])
        assert not temp_key_path.exists()


def test_cosign_runner_sign_keyring_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate sign_image raises CosignError when keyring key is missing."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")
    monkeypatch.setattr("devops_cli.docker.cosign.get_keyring_secret", lambda key: None)

    req = DockerSignRequest(image="example.com/app:1.0.0", key="keyring:missing_key", keyless=False)
    with pytest.raises(CosignError) as exc_info:
        runner.sign_image(req)
    assert "not found in OS Keyring" in str(exc_info.value)


def test_cosign_runner_sign_keyring_oidc_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate sign_image with OIDC token from OS Keyring passes COSIGN_IDENTITY_TOKEN via env."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")
    monkeypatch.setattr(
        "devops_cli.docker.cosign.get_keyring_secret",
        lambda key: "mock-oidc-jwt-token-from-keyring" if key == "cosign_oidc" else None,
    )

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 0
    mock_proc.stdout = "Signing image with OIDC token...\n"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        req = DockerSignRequest(image="example.com/app:1.0.0", oidc_token="keyring:cosign_oidc")
        res = runner.sign_image(req)
        assert res.success is True
        mock_run.assert_called_once()
        env_passed = mock_run.call_args[1].get("env", {})
        assert env_passed.get("COSIGN_IDENTITY_TOKEN") == "mock-oidc-jwt-token-from-keyring"


def test_cosign_runner_sign_raw_oidc_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate sign_image with raw OIDC token string passes COSIGN_IDENTITY_TOKEN via env."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 0
    mock_proc.stdout = "Signing image with raw OIDC token...\n"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        req = DockerSignRequest(image="example.com/app:1.0.0", oidc_token="raw-jwt-token-12345")
        res = runner.sign_image(req)
        assert res.success is True
        mock_run.assert_called_once()
        env_passed = mock_run.call_args[1].get("env", {})
        assert env_passed.get("COSIGN_IDENTITY_TOKEN") == "raw-jwt-token-12345"


def test_cosign_runner_sign_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate sign_image raises CosignError when cosign subprocess fails."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    mock_proc.stderr = "Error: signing repository access denied"

    with patch("subprocess.run", return_value=mock_proc):
        req = DockerSignRequest(image="example.com/app:1.0.0", keyless=True)
        with pytest.raises(CosignError) as exc_info:
            runner.sign_image(req)
        assert "signing repository access denied" in exc_info.value.message


def test_cosign_runner_verify_dry_run() -> None:
    """Validate verify_image in dry-run mode returns structured result without executing subprocess."""
    runner = CosignRunner()
    req = DockerVerifyRequest(
        image="example.com/app:1.0.0",
        cert_identity="https://example.com/workflows/build.yml@refs/heads/main",
        cert_issuer="https://example.com/oidc",
        dry_run=True,
    )
    res = runner.verify_image(req)
    assert isinstance(res, DockerVerifyResult)
    assert res.image == "example.com/app:1.0.0"
    assert res.verified is True


def test_cosign_runner_verify_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate verify_image parses cosign JSON output into claims and signatures."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")

    mock_cosign_json = [
        {
            "critical": {
                "identity": {"docker-reference": "example.com/app"},
                "image": {"docker-manifest-digest": "sha256:1234abcd5678"},
                "type": "cosign container image signature",
            },
            "optional": {
                "Issuer": "https://example.com/oidc",
                "Subject": "https://example.com/workflows/build.yml@refs/heads/main",
                "git_commit": "1234abcd",
            },
        }
    ]

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps(mock_cosign_json)
    mock_proc.stderr = (
        "Verification for example.com/app:1.0.0 --\nThe following checks were performed:\n"
    )

    with patch("subprocess.run", return_value=mock_proc):
        req = DockerVerifyRequest(
            image="example.com/app:1.0.0",
            cert_identity="https://example.com/workflows/build.yml@refs/heads/main",
            cert_issuer="https://example.com/oidc",
        )
        res = runner.verify_image(req)
        assert res.verified is True
        assert res.image == "example.com/app:1.0.0"
        assert len(res.signatures) == 1
        assert res.claims[0]["Issuer"] == "https://example.com/oidc"


def test_cosign_runner_verify_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate verify_image parses single dict JSON payload properly."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")

    mock_cosign_dict = {
        "critical": {"identity": {"docker-reference": "example.com/app"}},
        "optional": {"Issuer": "https://example.com/oidc"},
    }

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps(mock_cosign_dict)
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc):
        req = DockerVerifyRequest(image="example.com/app:1.0.0")
        res = runner.verify_image(req)
        assert res.verified is True
        assert len(res.signatures) == 1
        assert res.claims[0]["Issuer"] == "https://example.com/oidc"


def test_cosign_runner_verify_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate verify_image raises CosignVerificationError when signature check fails."""
    runner = CosignRunner()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cosign")

    mock_proc = MagicMock(spec=subprocess.CompletedProcess)
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    mock_proc.stderr = "Error: no matching signatures found"

    with patch("subprocess.run", return_value=mock_proc):
        req = DockerVerifyRequest(image="example.com/app:1.0.0", key="/path/to/cosign.pub")
        with pytest.raises(CosignVerificationError) as exc_info:
            runner.verify_image(req)
        assert "no matching signatures found" in exc_info.value.message


# =============================================================================
# 3. CLI Command Integrations
# =============================================================================


def test_cli_docker_sign_dry_run(cli_runner: CliRunner) -> None:
    """Validate 'devops docker sign --dry-run' renders dry-run output cleanly."""
    result = cli_runner.invoke(
        docker_app,
        ["sign", "example.com/app:1.0.0", "--annotation", "team=infra", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "action" in result.output.lower()


def test_cli_docker_verify_dry_run(cli_runner: CliRunner) -> None:
    """Validate 'devops docker verify --dry-run' renders dry-run output cleanly."""
    result = cli_runner.invoke(
        docker_app,
        [
            "verify",
            "example.com/app:1.0.0",
            "--certificate-identity",
            "https://example.com/workflows/build.yml",
            "--certificate-oidc-issuer",
            "https://example.com/oidc",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "action" in result.output.lower()


def test_cli_docker_sign_and_verify_live_mock(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate 'devops docker sign' and 'verify' CLI commands execute successfully with mocked runner."""
    monkeypatch.setattr(
        "devops_cli.docker.cosign.CosignRunner.sign_image",
        lambda self, req: DockerSignResult(
            image=req.image,
            digest="sha256:abcdef",
            signature_ref="example.com/app:sha256-abcdef.sig",
            keyless=req.keyless,
            annotations=req.annotations or [],
            success=True,
            duration_seconds=0.45,
        ),
    )
    sign_res = cli_runner.invoke(docker_app, ["sign", "example.com/app:1.0.0"])
    assert sign_res.exit_code == 0
    assert "signed successfully" in sign_res.output.lower()

    monkeypatch.setattr(
        "devops_cli.docker.cosign.CosignRunner.verify_image",
        lambda self, req: DockerVerifyResult(
            image=req.image,
            verified=True,
            signatures=[{"subject": "test"}],
            claims=[{"Issuer": "https://example.com"}],
            duration_seconds=0.32,
        ),
    )
    verify_res = cli_runner.invoke(
        docker_app,
        ["verify", "example.com/app:1.0.0", "--key", "/path/to/key.pub"],
    )
    assert verify_res.exit_code == 0
    assert "verified" in verify_res.output.lower()


def test_cli_docker_sign_missing_binary(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate CLI handles missing cosign executable gracefully."""
    monkeypatch.setattr(
        "devops_cli.docker.cosign.CosignRunner.sign_image",
        MagicMock(side_effect=DependencyError(tool_name="cosign", install_hint="Install Cosign")),
    )
    res = cli_runner.invoke(docker_app, ["sign", "example.com/app:1.0.0"])
    assert res.exit_code != 0
    assert "cosign" in res.output.lower()


def test_cosign_parse_verification_output_empty_and_invalid() -> None:
    """Validate _parse_verification_output handles empty and invalid JSON payloads gracefully."""
    from devops_cli.docker.cosign import _parse_verification_output

    assert _parse_verification_output("") == ([], [])
    assert _parse_verification_output("   \n\t ") == ([], [])
    assert _parse_verification_output("not valid json content") == ([], [])


def test_cli_docker_verify_missing_binary(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate CLI verify handles missing cosign executable gracefully."""
    monkeypatch.setattr(
        "devops_cli.docker.cosign.CosignRunner.verify_image",
        MagicMock(side_effect=DependencyError(tool_name="cosign", install_hint="Install Cosign")),
    )
    res = cli_runner.invoke(docker_app, ["verify", "example.com/app:1.0.0"])
    assert res.exit_code != 0
    assert "cosign" in res.output.lower()


def test_cli_docker_verify_verification_error(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate CLI verify handles CosignVerificationError cleanly."""
    monkeypatch.setattr(
        "devops_cli.docker.cosign.CosignRunner.verify_image",
        MagicMock(
            side_effect=CosignVerificationError(
                "verification failed", image="example.com/app:1.0.0"
            )
        ),
    )
    res = cli_runner.invoke(docker_app, ["verify", "example.com/app:1.0.0"])
    assert res.exit_code != 0
    assert "verification failed" in res.output.lower()


def test_cosign_exception_details() -> None:
    """Validate CosignError and CosignVerificationError construct details properly."""
    err = CosignError("signing failed", image="example.com/app:1.0.0", details={"reason": "denied"})
    assert err.details is not None
    assert err.details["image"] == "example.com/app:1.0.0"
    assert err.details["reason"] == "denied"

    verr = CosignVerificationError(
        "verification failed", image="example.com/app:1.0.0", details={"key": "cosign.pub"}
    )
    assert verr.details is not None
    assert verr.details["image"] == "example.com/app:1.0.0"
    assert verr.details["key"] == "cosign.pub"
