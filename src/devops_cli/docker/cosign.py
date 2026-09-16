"""Sigstore Cosign runner for container image signing, verification, and attestation."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any

from devops_cli.config.commands import BIN_COSIGN, build_cosign_sign_cmd, build_cosign_verify_cmd
from devops_cli.config.defaults import DEFAULT_COSIGN_TIMEOUT_SECONDS
from devops_cli.config.settings import get_keyring_secret
from devops_cli.exceptions.docker import CosignError, CosignVerificationError
from devops_cli.exceptions.tools import DependencyError
from devops_cli.models.docker import (
    DockerSignRequest,
    DockerSignResult,
    DockerVerifyRequest,
    DockerVerifyResult,
)

_SIGNATURE_REF_PATTERN = re.compile(r"Pushing signature to:\s*(\S+)")


@contextlib.contextmanager
def _resolve_signing_key(key_ref: str | None) -> Generator[str | None]:
    """Resolve key path, extracting from OS Keyring into an ephemeral file if needed."""
    if not key_ref:
        yield None
        return

    if not key_ref.startswith("keyring:"):
        yield key_ref
        return

    secret_name = key_ref.removeprefix("keyring:")
    key_content = get_keyring_secret(secret_name)
    if not key_content:
        raise CosignError(f"Private key secret '{secret_name}' not found in OS Keyring")

    fd, temp_path = tempfile.mkstemp(prefix="cosign-key-", suffix=".key")
    try:
        with os.fdopen(fd, "w") as tf:
            tf.write(key_content)
        yield temp_path
    finally:
        with contextlib.suppress(OSError):
            Path(temp_path).unlink(missing_ok=True)


def _resolve_oidc_env(oidc_token: str | None, base_env: Mapping[str, str]) -> dict[str, str]:
    """Resolve OIDC identity token, populating COSIGN_IDENTITY_TOKEN in environment."""
    env = dict(base_env)
    if not oidc_token:
        return env

    if oidc_token.startswith("keyring:"):
        token_name = oidc_token.removeprefix("keyring:")
        token_val = get_keyring_secret(token_name)
        if token_val:
            env["COSIGN_IDENTITY_TOKEN"] = token_val
    else:
        env["COSIGN_IDENTITY_TOKEN"] = oidc_token
    return env


def _parse_verification_output(stdout: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse JSON output from cosign verify into signatures and claims."""
    if not stdout.strip():
        return [], []
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            signatures = data
            claims = [item.get("optional", {}) for item in data if isinstance(item, dict)]
            return signatures, claims
        if isinstance(data, dict):
            return [data], [data.get("optional", {})]
    except json.JSONDecodeError, TypeError:
        pass
    return [], []


class CosignRunner:
    """Manages container image signing and verification using Sigstore Cosign."""

    def __init__(self, timeout: float = DEFAULT_COSIGN_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def check_available(self) -> bool:
        """Check whether the cosign CLI binary is available on PATH."""
        return shutil.which(BIN_COSIGN) is not None

    def require_binary(self) -> None:
        """Raise DependencyError if cosign binary is missing."""
        if not self.check_available():
            raise DependencyError(
                tool_name=BIN_COSIGN,
                install_hint="Install Sigstore Cosign CLI (e.g. 'go install github.com/sigstore/cosign/v2/cmd/cosign@latest')",
            )

    def sign_image(self, req: DockerSignRequest) -> DockerSignResult:
        """Sign container image using Cosign keyless or keyed signing."""
        if req.dry_run:
            return DockerSignResult(
                image=req.image,
                digest="sha256:dry-run",
                signature_ref=f"{req.image}.sig",
                keyless=req.keyless,
                annotations=req.annotations,
                success=True,
                duration_seconds=0.0,
                details="[dry-run] simulated cosign sign",
            )

        self.require_binary()
        t0 = time.perf_counter()

        with _resolve_signing_key(req.key) as key_path:
            cmd = build_cosign_sign_cmd(
                req.image,
                key=key_path,
                keyless=req.keyless,
                upload=req.upload,
                annotations=req.annotations,
            )
            env = _resolve_oidc_env(req.oidc_token, os.environ)
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=self.timeout,
            )

        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Cosign signing failed"
            raise CosignError(
                err_msg,
                image=req.image,
                exit_code=proc.returncode,
                details={"stdout": proc.stdout[:256], "stderr": proc.stderr[:256]},
            )

        match = _SIGNATURE_REF_PATTERN.search(proc.stdout)
        sig_ref = match.group(1) if match else None

        return DockerSignResult(
            image=req.image,
            signature_ref=sig_ref,
            keyless=req.keyless,
            annotations=req.annotations,
            success=True,
            duration_seconds=elapsed,
            details=proc.stdout or proc.stderr,
        )

    def verify_image(self, req: DockerVerifyRequest) -> DockerVerifyResult:
        """Verify container image signature or attestation using Cosign."""
        if req.dry_run:
            return DockerVerifyResult(
                image=req.image,
                verified=True,
                signatures=[],
                claims=[],
                duration_seconds=0.0,
                details="[dry-run] simulated cosign verify",
            )

        self.require_binary()
        t0 = time.perf_counter()

        with _resolve_signing_key(req.key) as key_path:
            cmd = build_cosign_verify_cmd(
                req.image,
                key=key_path,
                cert_identity=req.cert_identity,
                cert_issuer=req.cert_issuer,
                attestation=req.attestation,
                predicate_type=req.predicate_type,
                insecure_ignore_tlog=req.insecure_ignore_tlog,
            )
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )

        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Cosign verification failed"
            raise CosignVerificationError(
                err_msg,
                image=req.image,
                exit_code=proc.returncode,
                details={"stdout": proc.stdout[:256], "stderr": proc.stderr[:256]},
            )

        signatures, claims = _parse_verification_output(proc.stdout)
        return DockerVerifyResult(
            image=req.image,
            verified=True,
            signatures=signatures,
            claims=claims,
            duration_seconds=elapsed,
            details=proc.stderr or proc.stdout,
        )


__all__ = [
    "CosignRunner",
]
