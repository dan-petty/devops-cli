# Tasks

## 1. The scan gate, the lease revoke and git signing leave commands

- [x] Add failing tests of `gate_report`, `revoke_lease` and `configure_git_signing`
  - Verification: `uv run pytest tests/security/test_scan_gate.py tests/security/test_vault_lease_revoke.py tests/test_ssh.py`
- [x] Move the gate into `security/pipeline.py`, the lease revoke into `security/vault_lease.py` and git signing into `crypto/ssh_keys.py`, and delete the helpers in `commands/`
  - Verification: `uv run pytest tests/test_scan_outcomes_and_gating.py tests/test_vault_cmd.py tests/test_ssh.py`

## 2. The tests of #1332's files run on the merged fakes

- [x] Move the process-layer patches onto `process_fake`, real git and `PATH`: dive, zizmor, dependency remediator, difftastic, Helm, SBOM, static analyzers, known hosts
  - Verification: `uv run pytest tests/test_security_dive.py tests/test_security_zizmor.py tests/test_dependency_remediator.py tests/test_security_sandbox_and_protection.py tests/test_sbom.py tests/test_review_static_analyzers.py tests/test_ssh_host_keys.py`
- [x] Move the clock, settings and `github.ssh` patches onto the `clock`, `config` and `github_api` fixtures, and the dry-run patches onto `DEVOPS_CLI_DRY_RUN` and `set_dry_run`
  - Verification: `uv run pytest tests/test_ssh.py tests/test_crypto_tls.py tests/test_review_untrusted_tree.py tests/security/test_scanner_base_and_registry.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2543-security-process-fakes`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- #2544 moves the HTTP, Valkey, secret and span tests of #1332 onto the fakes of #1314 and #1317.
- The `shutil.which` patch in `tests/security/test_kube_api_network_profile.py` (#2467) is outside #1332's files.
