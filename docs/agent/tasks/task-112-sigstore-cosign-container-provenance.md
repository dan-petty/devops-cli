# Task 112: Sigstore Cosign Container Provenance & Image Signing

**Issue**: [#112](https://github.com/dan-petty/devops-cli/issues/112)
**PR**: [#213](https://github.com/dan-petty/devops-cli/pull/213)
**Status**: In Review
**Milestone**: `v0.2.18`
**Priority**: `priority/p1-high`
**Scope**: `scope/security`, `scope/cli`

---

## 1. Description & Objectives

Integrate Sigstore Cosign CLI for keyless container image and manifest signing, cryptographic verification, attestation verification, and seamless OS Keyring / OIDC token integration for zero-plaintext key handling.

### Key Objectives:
1. **Container Image Signing (`devops docker sign`)**:
   - Support keyless signing via Fulcio/Rekor with OIDC identity tokens (`--keyless`).
   - Support keyed signing with private keys (`--key <path>` or `--key keyring:<name>`).
   - Seamless integration with OS Keyring: private keys and OIDC tokens resolved securely with zero plaintext leakage.
   - Support annotations (`-a key=val`) and upload toggle (`--upload/--no-upload`).
   - Full dry-run support (`--dry-run`) with structured action summary.
2. **Container Signature Verification (`devops docker verify`)**:
   - Verify signatures using public keys (`--key <path>` or `--key keyring:<name>`).
   - Verify keyless signatures using certificate identity (`--certificate-identity`) and OIDC issuer (`--certificate-oidc-issuer`).
   - Verify in-toto attestation predicates (`--attestation` / `cosign verify-attestation`) with optional predicate type filter (`--type`).
   - Support offline or test verification with `--insecure-ignore-tlog`.
   - Full dry-run support (`--dry-run`).
3. **Agentic FastMCP Tools**:
   - Implement `docker_sign` and `docker_verify` tools for supply-chain provenance automation.
4. **Architectural & Quality Gates**:
   - Strictly enforce cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$.
   - Maintain $\ge 90\%$ test coverage across new components.

---

## 2. Planned Changes

1. **`src/devops_cli/config/commands.py`**:
   - `BIN_COSIGN: str = "cosign"` (already present).
   - Centralized command builders: `build_cosign_sign_cmd(...)` and `build_cosign_verify_cmd(...)` (already present).
2. **`src/devops_cli/config/defaults.py` & `constants.py`**:
   - `DEFAULT_COSIGN_TIMEOUT_SECONDS: float = 60.0` (already present).
   - Error code constants `CONST_ERROR_CODE_COSIGN` and `CONST_ERROR_CODE_COSIGN_VERIFY` (already present).
3. **`src/devops_cli/models/docker.py`**:
   - Pydantic v2 models: `DockerSignRequest`, `DockerSignResult`, `DockerVerifyRequest`, `DockerVerifyResult`.
4. **`src/devops_cli/exceptions/docker.py`**:
   - Add `CosignError` and `CosignVerificationError` with bounded detail truncation.
5. **`src/devops_cli/docker/cosign.py`**:
   - Implement `CosignRunner` with binary preflight checks, OS Keyring zero-plaintext token injection, secured temporary key handling, and subprocess execution.
6. **`src/devops_cli/commands/docker.py`**:
   - Wire Typer commands `@app.command("sign")` and `@app.command("verify")`.
7. **`src/devops_cli/ai/mcp/server.py`**:
   - Implement `@mcp.tool()` `docker_sign` and `docker_verify`.
8. **`tests/test_docker_cosign.py` & `tests/test_fastmcp_contracts.py`**:
   - Author comprehensive unit tests covering all functional and edge-case paths with normalized mock hostnames (`example.com`).
9. **Documentation**:
   - Update `docs/commands/docker.md` and `docs/MCP_TOOLS.md`.

---

## 3. Verification & Acceptance Criteria

- [ ] Comprehensive unit tests in `tests/test_docker_cosign.py` pass cleanly.
- [ ] FastMCP contract tests in `tests/test_fastmcp_contracts.py` pass cleanly.
- [ ] Architectural invariant tests in `tests/test_architectural_invariants.py` pass cleanly.
- [ ] Code coverage $\ge 90\%$ maintained across all new modules.
- [ ] Actionable error when `cosign` binary is missing (`DependencyError`).
- [ ] Zero plaintext secrets exposed in arguments or logs.
- [ ] All quality gates pass in `devops ci`.
