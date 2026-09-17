# Task 231: Real-time CI Streaming, Re-entrant Rate Limiter Locking, and Dynamic Repos Clone Destination

**Issue**: [#231](https://github.com/dan-petty/devops-cli/issues/231)
**PR**: [#232](https://github.com/dan-petty/devops-cli/pull/232)
**Status**: In Review
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`, `scope/github`

---

## 1. Description & Objectives

This task addresses three architectural improvements and reliability fixes across developer workflows:

1. **Real-time CI Streaming (`devops ci`)**:
   - Deliver immediate visual progress badges (`✓ pass` / `✗ fail`) with step durations streamed directly to stdout as each concurrent check finishes.
   - Maintain a background status indicator for long-running test and coverage suites to prevent terminal silence.
   - Standardize subprocess output decoding via `_format_process_output` to decode raw bytes safely without mangling.

2. **Re-entrant Cross-Process Rate Limiter Locking (`devops_cli.github.rate_limiter`)**:
   - Eliminate self-deadlocks where nested methods (`calculate_delay`, `acquire`, `update_quota`) re-enter the file lock `_disk_quota_lock`.
   - Implement thread-local depth tracking in `_DISK_LOCK_STATE` to allow recursive acquisition within the same process while maintaining exclusive cross-process isolation via `fcntl.flock`.
   - Enforce mandatory uniform pacing without zero-delay threshold bypasses.
   - Synchronize quota state and request counters across processes.

3. **Dynamic Repository Clone Destination (`devops repos clone`)**:
   - Dynamically parse organization/owner from Git clone URLs (`repos/<org>/<name>`) rather than hardcoding `repos/_standalone/<name>`.
   - Support HTTPS, SSH SCP-style, SSH URI-style, and shorthand repository references.
   - Fall back safely to `_standalone` only when no organization can be determined.
   - Defend against directory traversal escapes.
   - Relocate previously misclassified standalone repositories into their respective organization directory.

---

## 2. Key Deliverables

- `src/devops_cli/commands/ci.py`: Real-time streaming badge reporting with stdout flushing and process output decoding.
- `src/devops_cli/github/rate_limiter.py`: Re-entrant advisory locking with thread-local depth tracking, mandatory pacing, and cross-process persistence.
- `src/devops_cli/github/projects.py`: GraphQL quota safety threshold guards and mutation budgeting per sync run.
- `src/devops_cli/commands/repos.py`: Dynamic `_parse_clone_destination` helper extracting org and repository names from clone URLs.
- `tests/test_repos.py`: Unit tests for org-based and standalone repository cloning.
- `tests/test_github_rate_limiter.py`: Comprehensive test suite for rate limiting, locking, and cross-process synchronization.
- `tests/test_process.py`: Subprocess test isolation avoiding live git hook invocation.
