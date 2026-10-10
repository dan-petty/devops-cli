# Task: Bandit covers src and tests at medium severity through one config the gate and the code-scanning upload share, and the test findings are fixed (#1542)

**Issue**: [#1542](https://github.com/dan-petty/devops-cli/issues/1542)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: unset on the issue; the owner asked for it in v0.2.33 (2026-10-10) to fix release pull request #1537's `bandit` check
**Scope**: type/bug, scope/security, scope/ci
**Feasibility**: Checked at release/v0.2.33 (5c5df79) with bandit 1.9.4. The gate ran `uv run bandit -r src -ll` (`src/devops_cli/commands/ci.py:455`), so `tests/` was never scanned. The code-scanning upload #419 added (`.github/workflows/ci.yml:54-60`) ran `devops scan report`, whose Bandit command scanned the whole checkout with `--ignore-nosec`. A full scan found 69 Medium or High findings in `tests/` (52 B108, 12 B104, 4 B103, 1 B102) and none in `src/` with `# nosec` honoured. Bandit 1.9.4 reads targets and `recursive` from a `.bandit` INI file, but it crashes on a `level` line there and its `[tool.bandit]` table has no targets or severity, so the threshold stays a command-line option (`--severity-level`) taken from the existing `DEFAULT_BANDIT_SEVERITY` constant.

## Description

- **One scope.** A `.bandit` file at the repository root names `src` and `tests`. `devops ci security` runs `bandit --ini .bandit -r --severity-level medium`.
- **The upload agrees with the gate.** `devops scan report` on a tree whose `.bandit` names its targets runs Bandit on them from that tree, with `-r`, the same threshold, and `# nosec` honoured, so it reports exactly what the gate fails on. A tree whose `.bandit` names no targets is still scanned whole with `--ignore-nosec`.
- **Reviews unchanged.** An isolated (review) scan never reads the reviewed tree's `.bandit`, still names its own targets, still passes `--ignore-nosec`, and still gets the empty INI file it is handed (#972).
- **Test findings fixed.** 56 of the 69 are fixed in code: `tmp_path` or `tmp_path_factory` paths, source constants instead of literals, `::1` for pass-through hosts, and private keys created at 0o644 rather than world-writable. Thirteen findings sit on 12 lines whose literal is itself under test (a pod's bind-all address or `emptyDir` mount, a refused `/tmp` data directory, a deliberately world-writable certificate), each marked `# nosec BXXX  # <reason>`.

## Acceptance Criteria

- [x] The gate's command and the SARIF scan's command name the same `.bandit`, threshold and `-r`, and neither ignores `# nosec` (`tests/test_security_bandit.py`).
- [x] A review scan reads no config of the reviewed tree and still reports `# nosec` lines (`tests/test_security_bandit.py`).
- [x] A tree whose `.bandit` names no targets, or names targets without `recursive`, still reports its findings (`tests/test_security_bandit.py`, checked with real bandit 1.9.4 on scratch trees).
- [x] `uv run bandit --ini .bandit -r --severity-level medium` reports 0 findings over `src/` and `tests/`, and `uv run devops ci security` passes; a probe file with a `/tmp` path under `tests/` makes it fail.
- [x] Bandit's wall time in the gate is about 37 s locally under load, up from about 21 s; the static job stays within the 5-minute budget.
- [x] `changelog.d/1542.md` holds the entry under `### Changed`, and `changelog.d/419.md` is in house style under `### Added`.
- `uv run devops ci` is the pull request's gate.
- Pending a person: on release pull request #1537, the `bandit` code-scanning check passes after this merges.

Related: #419, #1537, #1538 (the Low findings in `src/`).
