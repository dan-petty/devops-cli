# Proposal

## Why

Issue #2143 records the rule: a test of `src/` starts no program. The analyze, AI tooling, and security scanner tests still start a real `git` binary. An audit of the test suite recorded 31 tests across 13 files that start `git`:
- `tests/commands/test_analyze.py` (7 tests)
- `tests/security/test_security_semgrep.py` (4 tests)
- `tests/security/test_scanner_tool_executor.py` (3 tests)
- `tests/commands/test_security_bandit.py` (2 tests)
- `tests/security/test_secops.py` (2 tests)
- `tests/security/test_osv_scanner.py` (2 tests)
- `tests/ai/analyze/test_ai_analyze_outlines.py` (2 tests)
- `tests/ai/test_repomap.py` (1 test)
- `tests/ai/test_ai_diagram.py` (1 test)
- `tests/ai/ast/test_treesitter_engine.py` (1 test)
- `tests/security/test_scanner_contract.py` (1 test)
- `tests/core/test_scan_complexity.py` (1 test)
- `tests/ai/client/test_url_credential_masking.py` (1 test)

Issue #2146 delivered the `git_fake` fixture. These tests must use `git_fake` and start no git process.

## What Changes

- Tests in the 13 files above reach `git` through `git_fake`.
- Test helpers and fixtures that start a real `git` to build repositories under `tmp_path` are replaced by file creation and scripted `git_fake` responses.
- Any start of a real `git` binary fails under `git_fake`.
- No test patches a `devops_cli` name.
- The pull request records the summed execution duration before and after the change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/commands/test_analyze.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/security/test_security_semgrep.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/security/test_scanner_tool_executor.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/commands/test_security_bandit.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/security/test_secops.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/security/test_osv_scanner.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/analyze/test_ai_analyze_outlines.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/test_repomap.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/test_ai_diagram.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/ast/test_treesitter_engine.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/security/test_scanner_contract.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/core/test_scan_complexity.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/client/test_url_credential_masking.py`: Use `git_fake` and file fixtures instead of real git.

## Feasibility

Checked on 2026-10-31 against `tests/support/fakes/git.py` and the target test files:
- An audit of the 13 files with `sys.addaudithook` confirmed 31 tests starting `git` and a baseline duration of 21.18s across 305 tests.
- `git_fake` installs a `GitFake` instance into the process runner seam.
- `git_fake` intercepts `run_subprocess` calls for `git` and answers them through recorded scenarios or scripted `ProcessAnswer` records.
- When `git_fake` is active, `subprocess.Popen.__init__` checks the started program and fails if a real `git` binary starts.
- Code under test routes `git` calls through `devops_cli.core.process.run_subprocess` or reads files under `.git`.

## Existing Tool Considered

`git_fake` in `tests/support/fakes/git.py` provides the hermetic git fake seam. No new tool is needed.
