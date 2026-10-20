# Task: The Gate and Pull-Request CI Run Within Their Time Budget, with Hermetic Tests (#1725)

**Issue**: [#1725](https://github.com/dan-petty/devops-cli/issues/1725)
**Scope**: scope/ci
**Feasibility**: Measured on `release/v0.2.37` at 4e61562 on 2026-10-20:
- a quiet-host `uv run devops ci`: 3m11s, of which the test row took 3m6s;
- a `--durations` run with a per-test probe of subprocesses, sleeps and sockets;
- the last 10 CI runs: about 287s each, with a Tests & Coverage median of 284s.

Each row below removes one measured cost at its source, in its own pull request, and records its time before and after at its own base.

## Description

The targets for v0.2.38:
- **Local gate:** `uv run devops ci` takes at most 2 minutes on a quiet host.
- **Pull-request CI:** at most 3 minutes.
- **Slow tests:** no test runs over 5 seconds without a recorded reason.
- **Hermetic tests:** no test touches the network, DNS, a real scanner, `kubectl` against a cluster, or a real localhost service.
- **Flakes:** no flaky reruns.

No check is dropped and no threshold is lowered. A check that does not apply to a path stops running there.

## Rows

### The 15-second wait in the review pipeline test

- [x] `tests/ai/review/test_pipeline.py::test_fake_scanner_results_with_absolute_paths_come_out_repository_relative` takes the `model_fake` fixture, so the report's group analysis asks the shared `ModelFake`.
  - The test used to build a real model client. Its refused loopback connect waited out 1 + 2 + 4 + 8 seconds of transport retries.
  - Measured with `uv run pytest -n 0 --durations=0 -q tests/ai/review/test_pipeline.py`: the test went from 15.15s to 0.16s, and the file from 17.61s to 3.04s.
  - Every assertion is kept.

### Textual pauses in the UI tests

- The `pilot.pause` waits in `tests/test_ui_reactive.py` (73 tests, 109s of sleep) are removed in their own pull request under #1725.

### Startup import probes

- The `python -c` import probes in `tests/test_cli_startup_imports.py` (62 tests, 70-97s) are removed in their own pull request under #1725.

### Retry backoffs against localhost services

- The retry backoffs against refused Valkey, Ollama and RAG endpoints (about 4.5-5s per test) are removed in their own pull request under #1725.

### kubectl in tests

- The 33 tests that start `kubectl` (26s) are handled in their own pull request under #1725. Offline renders (`kubectl kustomize`, `kubectl patch --local`) stay real, as decided on the issue.

### Nested pytest in the isolation tripwire

- The nested pytest runs in `tests/test_isolation_tripwire.py` (3 tests, 24s) are removed in their own pull request under #1725.

### Collection on the GitHub runner

- Startup and collection take 45s on the GitHub runner. That is cut in its own pull request under #1725.

### Devcontainer tests on the runner

- On the GitHub runner, four post-create tests run Claude Code's real installer (12-17s each). That stops in its own pull request under #1725.

### xdist balance and gate scheduling

- The slowest xdist worker finishes 47s after the median, and bandit competes with the test row (21s alone, 61s beside pytest). Both are fixed in their own pull request under #1725.

### Real scanners in review tests

- Real semgrep, gitleaks and bandit in the review tests (6 tests, about 82s) are replaced by recorded results under #1666.

### Item-only checks on the release pull request

- Fixed in v0.2.37: the fail-to-pass check (#1721) and the changed-test shuffle (#1723) no longer run on the release pull request into main.

## Verification

- The last pull request under #1725 re-measures the gate and CI against the targets.
