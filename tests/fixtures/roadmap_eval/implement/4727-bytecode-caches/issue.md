### Problem or Motivation

`setup-toolchain` runs `uv sync ... --compile-bytecode` (`.github/actions/setup-toolchain/action.yml:55`). 'Bytecode compiled 19212 files' took 7.6-14.7 s per job, with a mean of 11.4 s (10 logs, measured). The test jobs restore a tooling cache (`.mypy_cache` and `.ruff_cache`) that they do not use. In Service Image Tests, the cache never hits and is never saved.

Saving: About 9 s per Tests & Coverage job and 11 s per Service Image Tests job, which is about 1.8 runner-min per push (estimated).

Found by the CI and test audit of 2026-11-11. The account runs at most 20 hosted jobs at one time (measured), so each job that does no work makes the queue of each pull request longer.

### Proposed Solution & Architectural Design

- Add an input to `setup-toolchain` that turns off `--compile-bytecode`.
- Pass this input, and empty tooling-cache paths, in test-shard, service-image-test, changed-tests and job-time.

Risk: The workers compile the same modules one time at the start (CPU only).

### Target Subsystem

SDLC, Git & PR Governance (`.github/actions/setup-toolchain/action.yml`, `.github/workflows/ci.yml`).

### Existing Tool Considered

uv compiles bytecode only on request (`--compile-bytecode`). No new tool. Cost: about 10,000 tokens and 1 hour.

### Acceptance Criteria

- The logs of these jobs have no 'Bytecode compiled' line.
- The mean shard job time falls by 5 s or more.

### Dependencies

Depends on #4642.

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-14: not-applicable.
Class: perf, no search.
Tool: none found.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.adr_hash": null, "alternatives.body_hash": "1ef65d950e8f997eb6607d1324e1b941f4641e234d780e8aa30b62822979d0cf", "alternatives.checked_at": "2026-11-14T05:23:21.329599+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": null, "alternatives.tool_id": null, "alternatives.verdict": "not-applicable"} -->
