"""Tests for the Sigstore Cosign command builders and `CosignRunner` (container image signing).

Cosign is a program: a test scripts its answer on `process_fake`, and reads the command and the
environment that were started from the fake's `calls`. Secrets come from `keyring_store`. A host
without Cosign is a `PATH` with no program in it.
"""

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest

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
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

IMAGE = "example.com/app:1.0.0"
KEY_TEXT = (
    "-----BEGIN ENCRYPTED COSIGN PRIVATE KEY-----\ntest\n-----END ENCRYPTED COSIGN PRIVATE KEY-----"
)


@pytest.fixture
def no_programs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A host on which no program is installed: `PATH` names an empty directory."""
    empty = tmp_path / "no-programs"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


# =============================================================================
# 1. Command Argument Builders
# =============================================================================


def test_build_cosign_sign_cmd_keyless() -> None:
    """Validate sign command builder in default keyless mode."""
    cmd = build_cosign_sign_cmd(IMAGE, keyless=True, upload=True)
    assert cmd == [BIN_COSIGN, "sign", "--yes", IMAGE]


def test_build_cosign_sign_cmd_keyed_and_annotations() -> None:
    """Validate sign command builder with explicit key and supply-chain annotations."""
    cmd = build_cosign_sign_cmd(
        IMAGE,
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
        IMAGE,
    ]


def test_build_cosign_verify_cmd_keyless() -> None:
    """Validate verify command builder with certificate identity and issuer."""
    cmd = build_cosign_verify_cmd(
        IMAGE,
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
        IMAGE,
    ]


def test_build_cosign_verify_cmd_attestation_and_tlog() -> None:
    """Validate verify command builder for attestation predicates and offline/tlog flag."""
    cmd = build_cosign_verify_cmd(
        IMAGE,
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
        IMAGE,
    ]


# =============================================================================
# 2. Binary lookup
# =============================================================================


def test_check_available_finds_cosign_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_available is true when a `cosign` program is on PATH, and false when none is."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    program = bin_dir / "cosign"
    program.write_text("#!/bin/sh\n", encoding="utf-8")
    program.chmod(program.stat().st_mode | stat.S_IXUSR)
    runner = CosignRunner()

    monkeypatch.setenv("PATH", str(bin_dir))
    found = runner.check_available()
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert (found, runner.check_available()) == (True, False)


@pytest.mark.usefixtures("no_programs")
def test_require_binary_raises_when_cosign_is_missing() -> None:
    """Validate require_binary raises DependencyError when cosign is missing."""
    with pytest.raises(DependencyError) as exc_info:
        CosignRunner().require_binary()

    assert "cosign" in str(exc_info.value).lower()


@pytest.mark.usefixtures("no_programs")
def test_sign_and_verify_stop_before_any_work_when_cosign_is_missing() -> None:
    """Both operations raise DependencyError at once, and read no key."""
    runner = CosignRunner()

    with pytest.raises(DependencyError, match="cosign"):
        runner.sign_image(DockerSignRequest(image=IMAGE, key="keyring:never_read"))
    with pytest.raises(DependencyError, match="cosign"):
        runner.verify_image(DockerVerifyRequest(image=IMAGE))


# =============================================================================
# 3. Signing
# =============================================================================


def test_sign_dry_run(process_fake: ProcessFake) -> None:
    """Validate sign_image in dry-run mode returns structured result without a process."""
    req = DockerSignRequest(image=IMAGE, keyless=True, annotations=["env=prod"], dry_run=True)

    result = CosignRunner().sign_image(req)

    assert isinstance(result, DockerSignResult)
    assert (result.image, result.keyless, result.annotations, result.success) == (
        IMAGE,
        True,
        ["env=prod"],
        True,
    )
    assert process_fake.calls == []


def test_sign_dry_run_with_key_reports_keyed() -> None:
    """Validate dry-run accurately reports keyless=False when a signing key is supplied."""
    res = CosignRunner().sign_image(DockerSignRequest(image=IMAGE, key="cosign.key", dry_run=True))

    assert (res.keyless, res.success) == (False, True)


def test_sign_keyless_runs_cosign_and_reads_the_signature_reference(
    process_fake: ProcessFake,
) -> None:
    """Validate keyless sign_image starts cosign and reads where the signature was pushed."""
    process_fake.answer(
        "cosign", ProcessAnswer(stdout="Pushing signature to: example.com/app:sha256-abc.sig\n")
    )

    res = CosignRunner().sign_image(DockerSignRequest(image=IMAGE, keyless=True))

    (call,) = process_fake.calls
    assert (res.success, res.image, res.signature_ref, call.argv) == (
        True,
        IMAGE,
        "example.com/app:sha256-abc.sig",
        tuple(build_cosign_sign_cmd(IMAGE, keyless=True, upload=True)),
    )


def test_sign_with_a_keyring_key_writes_an_ephemeral_key_file_and_removes_it(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """The key in the OS keyring reaches cosign as a file that holds it, and is deleted after."""
    keyring_store.values["test_key"] = KEY_TEXT
    seen: dict[str, object] = {}

    def cosign(call: ProcessCall) -> ProcessAnswer:
        key_path = Path(call.argv[call.argv.index("--key") + 1])
        seen["path"] = key_path
        seen["content"] = key_path.read_text(encoding="utf-8")
        seen["mode"] = stat.S_IMODE(key_path.stat().st_mode)
        return ProcessAnswer(stdout="Pushing signature to: example.com/app:sha256-key.sig\n")

    process_fake.answer("cosign", cosign)

    res = CosignRunner().sign_image(
        DockerSignRequest(image=IMAGE, key="keyring:test_key", keyless=False)
    )

    assert (res.success, res.keyless, seen["content"], seen["mode"]) == (
        True,
        False,
        KEY_TEXT,
        0o600,
    )
    assert isinstance(seen["path"], Path)
    assert not seen["path"].exists()


def test_sign_with_a_key_that_the_keyring_lacks_raises_cosign_error(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Validate sign_image raises CosignError when keyring key is missing."""
    req = DockerSignRequest(image=IMAGE, key="keyring:missing_key", keyless=False)

    with pytest.raises(CosignError, match="not found in OS Keyring"):
        CosignRunner().sign_image(req)

    assert process_fake.calls == []


def test_sign_hands_an_oidc_token_from_the_keyring_to_cosign_in_its_environment(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Validate sign_image with OIDC token from OS Keyring passes COSIGN_IDENTITY_TOKEN via env."""
    keyring_store.values["cosign_oidc"] = "mock-oidc-jwt-token-from-keyring"
    process_fake.answer("cosign", ProcessAnswer(stdout="Signing image with OIDC token...\n"))

    res = CosignRunner().sign_image(
        DockerSignRequest(image=IMAGE, oidc_token="keyring:cosign_oidc")
    )

    (call,) = process_fake.calls
    assert (res.success, call.env) == (
        True,
        {"COSIGN_IDENTITY_TOKEN": "mock-oidc-jwt-token-from-keyring"},
    )


def test_sign_hands_a_raw_oidc_token_to_cosign_in_its_environment(
    process_fake: ProcessFake,
) -> None:
    """Validate sign_image with raw OIDC token string passes COSIGN_IDENTITY_TOKEN via env."""
    res = CosignRunner().sign_image(
        DockerSignRequest(image=IMAGE, oidc_token="raw-jwt-token-12345")
    )

    (call,) = process_fake.calls
    assert (res.success, call.env) == (True, {"COSIGN_IDENTITY_TOKEN": "raw-jwt-token-12345"})


def test_sign_fails_closed_when_the_keyring_lacks_the_oidc_token(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Validate sign_image fails closed with CosignError when keyring OIDC token is missing."""
    req = DockerSignRequest(image=IMAGE, oidc_token="keyring:missing_token")

    with pytest.raises(CosignError, match="not found in OS keyring"):
        CosignRunner().sign_image(req)

    assert process_fake.calls == []


def test_sign_failure_carries_the_stderr_and_exit_code(process_fake: ProcessFake) -> None:
    """Validate sign_image raises CosignError when cosign subprocess fails."""
    process_fake.answer(
        "cosign", ProcessAnswer(returncode=1, stderr="Error: signing repository access denied")
    )

    with pytest.raises(CosignError) as exc_info:
        CosignRunner().sign_image(DockerSignRequest(image=IMAGE, keyless=True))

    assert "signing repository access denied" in exc_info.value.message


def test_sign_timeout_is_wrapped_as_cosign_error(process_fake: ProcessFake) -> None:
    """Validate sign_image wraps subprocess.TimeoutExpired as CosignError."""
    process_fake.answer(
        "cosign", ProcessAnswer(side_effect=subprocess.TimeoutExpired(cmd=["cosign"], timeout=2.0))
    )

    with pytest.raises(CosignError, match=r"timed out after 2\.0s"):
        CosignRunner(timeout=2.0).sign_image(DockerSignRequest(image=IMAGE))


# =============================================================================
# 4. Verification
# =============================================================================


def test_verify_dry_run(process_fake: ProcessFake) -> None:
    """Validate verify_image in dry-run mode returns structured result without a process."""
    req = DockerVerifyRequest(
        image=IMAGE,
        cert_identity="https://example.com/workflows/build.yml@refs/heads/main",
        cert_issuer="https://example.com/oidc",
        dry_run=True,
    )

    res = CosignRunner().verify_image(req)

    assert isinstance(res, DockerVerifyResult)
    assert (res.image, res.verified, process_fake.calls) == (IMAGE, True, [])


def test_verify_parses_a_list_of_signatures_into_claims(process_fake: ProcessFake) -> None:
    """Validate verify_image parses cosign JSON output into claims and signatures."""
    signatures = [
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
    process_fake.answer(
        "cosign",
        ProcessAnswer(
            stdout=json.dumps(signatures),
            stderr="Verification for example.com/app:1.0.0 --\nThe following checks were performed:\n",
        ),
    )
    req = DockerVerifyRequest(
        image=IMAGE,
        cert_identity="https://example.com/workflows/build.yml@refs/heads/main",
        cert_issuer="https://example.com/oidc",
    )

    res = CosignRunner().verify_image(req)

    (call,) = process_fake.calls
    assert (res.verified, res.image, res.signatures, res.claims, call.argv) == (
        True,
        IMAGE,
        signatures,
        [signatures[0]["optional"]],
        tuple(
            build_cosign_verify_cmd(
                IMAGE,
                cert_identity=req.cert_identity,
                cert_issuer=req.cert_issuer,
            )
        ),
    )


def test_verify_parses_a_single_object_payload(process_fake: ProcessFake) -> None:
    """Validate verify_image parses single dict JSON payload properly."""
    payload = {
        "critical": {"identity": {"docker-reference": "example.com/app"}},
        "optional": {"Issuer": "https://example.com/oidc"},
    }
    process_fake.answer("cosign", ProcessAnswer(stdout=json.dumps(payload)))

    res = CosignRunner().verify_image(DockerVerifyRequest(image=IMAGE))

    assert (res.verified, res.signatures, res.claims) == (True, [payload], [payload["optional"]])


@pytest.mark.parametrize("stdout", ["", "   \n\t ", "not valid json content", "42"])
def test_verify_with_no_readable_signature_output_succeeds_with_none(
    stdout: str, process_fake: ProcessFake
) -> None:
    """Empty, malformed or non-object output verifies with no signatures and no claims."""
    process_fake.answer("cosign", ProcessAnswer(stdout=stdout))

    res = CosignRunner().verify_image(DockerVerifyRequest(image=IMAGE))

    assert (res.verified, res.signatures, res.claims) == (True, [], [])


def test_verify_failure_carries_the_stderr(process_fake: ProcessFake) -> None:
    """Validate verify_image raises CosignVerificationError when signature check fails."""
    process_fake.answer(
        "cosign", ProcessAnswer(returncode=1, stderr="Error: no matching signatures found")
    )
    req = DockerVerifyRequest(image=IMAGE, key="/path/to/cosign.pub")

    with pytest.raises(CosignVerificationError) as exc_info:
        CosignRunner().verify_image(req)

    assert "no matching signatures found" in exc_info.value.message


def test_verify_timeout_is_wrapped_as_verification_error(process_fake: ProcessFake) -> None:
    """Validate verify_image wraps subprocess.TimeoutExpired as CosignVerificationError."""
    process_fake.answer(
        "cosign", ProcessAnswer(side_effect=subprocess.TimeoutExpired(cmd=["cosign"], timeout=3.0))
    )

    with pytest.raises(CosignVerificationError, match=r"timed out after 3\.0s"):
        CosignRunner(timeout=3.0).verify_image(DockerVerifyRequest(image=IMAGE))


def test_sign_and_verify_let_cosign_inherit_xdg_runtime_dir(process_fake: ProcessFake) -> None:
    """Both operations let the child inherit XDG_RUNTIME_DIR, which the keyring client needs."""
    runner = CosignRunner()

    runner.sign_image(DockerSignRequest(image=IMAGE, keyless=True))
    runner.verify_image(DockerVerifyRequest(image=IMAGE))

    assert [call.extra_allowed_env for call in process_fake.calls] == [
        frozenset({"XDG_RUNTIME_DIR"}),
        frozenset({"XDG_RUNTIME_DIR"}),
    ]


# =============================================================================
# 5. Errors and re-exports
# =============================================================================


def test_cosign_exception_details() -> None:
    """Validate CosignError and CosignVerificationError construct details properly."""
    err = CosignError("signing failed", image=IMAGE, details={"reason": "denied"})
    assert err.details is not None
    assert err.details["image"] == IMAGE
    assert err.details["reason"] == "denied"

    verr = CosignVerificationError(
        "verification failed", image=IMAGE, details={"key": "cosign.pub"}
    )
    assert verr.details is not None
    assert verr.details["image"] == IMAGE
    assert verr.details["key"] == "cosign.pub"


def test_cosign_exceptions_and_models_reexported() -> None:
    """Validate Cosign exceptions and models are exposed through package roots."""
    import devops_cli.exceptions as exceptions_mod
    import devops_cli.exceptions.docker as docker_exceptions
    import devops_cli.models as models_mod
    import devops_cli.models.docker as docker_models

    assert exceptions_mod.CosignError is docker_exceptions.CosignError
    assert exceptions_mod.CosignVerificationError is docker_exceptions.CosignVerificationError
    assert models_mod.DockerSignRequest is docker_models.DockerSignRequest
    assert models_mod.DockerSignResult is docker_models.DockerSignResult
    assert models_mod.DockerVerifyRequest is docker_models.DockerVerifyRequest
    assert models_mod.DockerVerifyResult is docker_models.DockerVerifyResult
