# Proposal

## Why

Issue #2543, part 2 of #1332: after part 1 (#2542), the security and crypto tests of #1332 still patched process-layer, clock, settings and `github.ssh` names that merged fakes cover. Three pieces of logic also lived in `commands/` (Q19 of #1332): the `--fail-on` gate of `devops scan report`, the Vault lease revoke and its error mapping, and the git signing configuration of `devops ssh`.

## What Changes

- The gate of `devops scan report` is `gate_report` in `src/devops_cli/security/pipeline.py`. It returns a `GateVerdict`: the scanners that failed, the named scanners that did not run, and whether a gating finding is at or above the threshold. The command prints the same errors and exits with the same status. `_evaluate_fail_on`, `_check_failed_scanners` and `_check_explicit_scanners_not_run` are deleted.
- `revoke_lease(broker, lease_id)` in `src/devops_cli/security/vault_lease.py` builds the session's lease registry with the broker's token, revokes the lease and maps a refusal: a rejected token raises the broker's status error, any other refusal a `VaultLeaseError` with the masked lease id and the status. `devops vault leases --revoke` calls it and prints the success line. `_revoke_lease` is deleted.
- `configure_git_signing(key_path, repo_dir=None)` in `src/devops_cli/crypto/ssh_keys.py` writes the SSH signing settings to the global git config and to the local config of a repository. It prints nothing; the `devops ssh` commands print the message.
- The tests of #1332's files move onto the merged fakes:
  - `process_fake` (#775) for `run_subprocess`, `subprocess.run` and `shutil.which`: the dive, zizmor, dependency remediator, difftastic and Helm tests.
  - Real git in temporary repositories, with the global git config under `tmp_path` (Q23): the remediation branch and git signing tests.
  - The `clock` fixture (#1320) for the TLS expiry and the dates of the `devops ssh` tests.
  - The GitHub API fake (#983) for SSH key registration.
  - The `config` fixture, or the config file itself, for settings: no test patches `load_settings` or `CONFIG_PATH`.
  - A `PATH` that holds only the programs a test needs, for `check_binary` and `shutil.which`.
  - `DEVOPS_CLI_DRY_RUN` and `set_dry_run` for dry runs, not a patch of `is_dry_run`.
- New tests: `tests/security/test_scan_gate.py` and `tests/security/test_vault_lease_revoke.py`, and a real-git test of `configure_git_signing` in `tests/test_ssh.py`.
- No command, option, message or exit status changes, so the change has no spec delta.
- This change fits one pull request.

## Impact

- `src/devops_cli/security/pipeline.py`, `src/devops_cli/security/vault_lease.py`, `src/devops_cli/crypto/ssh_keys.py`, `src/devops_cli/commands/{scan,vault,ssh}.py`.
- `tests/test_ssh.py`, `tests/test_ssh_host_keys.py`, `tests/test_security_dive.py`, `tests/test_security_zizmor.py`, `tests/test_security_sandbox_and_protection.py`, `tests/test_dependency_remediator.py`, `tests/test_crypto_tls.py`, `tests/test_sbom.py`, `tests/test_review_static_analyzers.py`, `tests/test_review_untrusted_tree.py`, `tests/security/test_scanner_base_and_registry.py`, and the two new test files.

## Feasibility

- On origin/main dbfbb653 (after #2566 merged), an AST scan of the security and crypto test files found 28 patches of a process-layer, clock, settings or `github.ssh` name outside `test_ssh.py`, and 26 in `test_ssh.py`. After the change the scan finds one, in `tests/security/test_kube_api_network_profile.py`, which #2467 added and which is not one of #1332's files.
- `process_fake` (`tests/support/fakes/process.py`) replaces the runner behind `run_subprocess` and fakes `shutil.which`; `refuse_real_programs` in the test floor refuses any other started program. The `clock` fixture runs `time-machine` with ticking off. The `github_api` fixture answers the GitHub session's requests. All three are on main.
- The settings of `devops ssh` read the config file that `DEVOPS_CLI_CONFIG` names, so `config(ssh={...})` gives the same values that the patched `load_settings` gave. The global config file `CONFIG_PATH` is bound under the isolated HOME of the test worker, so a test can write it and remove it.
- The text of a GitHub refusal reaches the output of `devops ssh rotate`, masked: a probe run printed `GitHub refused POST /user/keys (HTTP 422): API timeout for token <masked-github-token>`.
- The changed tests and their neighbours (1,527 tests) pass, and `uv run devops ci typecheck` passes.

## Existing Tool Considered

The change builds no fake. It uses the merged fakes: `ProcessFake` (#775), `ClockFake` over `time-machine` (#1320), `GitHubApiFake` (#983), `StubWeb` over httpx2's `MockTransport`, and git itself. The moved functions are plain functions beside their owners. The change deletes `_evaluate_fail_on`, `_check_failed_scanners`, `_check_explicit_scanners_not_run` and `_revoke_lease` from `commands/`, and the git commands of `_configure_git_signing`.
