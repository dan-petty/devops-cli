# Task: GitHub clones trust GitHub's published host keys through OpenSSH (#1114)

**Issue**: [#1114](https://github.com/dan-petty/devops-cli/issues/1114)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: scope/security

## Description
Prior to this change, `clone_repo` attempted in-process SSH host key verification by invoking `ssh-keyscan` and parsing `~/.ssh/known_hosts` with a custom in-process parser (`crypto/known_hosts.py` and `crypto/host_keys.py`). This led to two critical security fail-opens:
1. Malformed or junk lines in `~/.ssh/known_hosts` (such as unparseable tokens or invalid entries) caused the in-process parser to reject or skip lines, silently failing open and skipping host-key pinning.
2. If `ssh-keyscan` failed (e.g. during intermittent network timeouts or firewall restrictions), the scan error was caught and ignored, silently skipping host-key pinning before cloning.
3. Hand-rolled parsing duplicated OpenSSH's native configuration and marker handling, failing to properly model `@revoked`, `@cert-authority`, hashing, negated patterns, or alternate ports.

This deliverable replaces the custom parser and runtime key scanning with GitHub's published, pinned host keys written directly to `~/.ssh/known_hosts`, letting OpenSSH perform native verification:
1. Replaced custom crypto parsing with `CONST_GITHUB_KNOWN_HOSTS_LINES` in `src/devops_cli/config/constants.py` containing GitHub's 3 published known_hosts lines (ed25519, ecdsa-sha2-nistp256, and ssh-rsa).
2. Removed hand-rolled `src/devops_cli/crypto/host_keys.py` and `src/devops_cli/crypto/known_hosts.py`.
3. In `src/devops_cli/git/operations.py`, implemented `_ensure_known_host` decorated with `@functools.cache` to append missing pinned lines to `~/.ssh/known_hosts` with mode `0600` and directory mode `0700`.
4. If `~/.ssh` or `known_hosts` is unwritable, `_ensure_known_host` logs a warning once and allows the operation to proceed without crashing.
5. Invoked `_ensure_known_host()` unconditionally in `_prepare_clone_url` for all repository clone operations.
6. Wrapped `gitlib.GitCommandError` in `GitOperationError` during `clone_repo`, masking secrets from stdout and stderr.
7. Wrapped `clone_repo` in `src/devops_cli/commands/repos.py` with `with exit_on_error(GitOperationError):` to report clean error diagnostics.
8. Updated `docs/KNOWN_ISSUES.md` documenting native OpenSSH host key verification and pinned host keys.
9. Rewrote `tests/test_ssh_host_keys.py` to test pinned line structure via `cryptography`, match GitHub's published fingerprints, verify file permissions and newline handling, and test error masking.

## Acceptance Criteria Checklist
- [x] Pinned host key lines in `CONST_GITHUB_KNOWN_HOSTS_LINES` parse into valid public keys via `cryptography.hazmat.primitives.serialization.load_ssh_public_key`.
- [x] Fingerprints of pinned lines match GitHub's published SHA256 fingerprints for ed25519, ecdsa-sha2-nistp256, and ssh-rsa.
- [x] `_ensure_known_host` creates `~/.ssh` (mode 0700) and `known_hosts` (mode 0600) and appends missing lines preserving existing contents.
- [x] Existing un-terminated files get a newline before appended lines.
- [x] Junk, malformed, or comment lines in `~/.ssh/known_hosts` do not prevent pinned lines from being appended.
- [x] Unwritable `~/.ssh` directory logs a warning once and does not raise.
- [x] `clone_repo` calls `_ensure_known_host` for both SSH and HTTPS clone URLs.
- [x] Failed clone commands raise `GitOperationError` with masked stderr.
- [x] `devops repos clone` CLI command handles `GitOperationError` cleanly via `exit_on_error`.
- [x] Hand-rolled `crypto/host_keys.py` and `crypto/known_hosts.py` modules are deleted.
- [x] All tests run offline with no external network or live ssh binary required.
- Pending a person: with an empty `~/.ssh` and OpenSSH's default `StrictHostKeyChecking ask`, `devops repos clone git@github.com:<org>/<repo>.git` clones with no host-key prompt. It does the same with an `@cert-authority github.com …` line already in `~/.ssh/known_hosts`.
