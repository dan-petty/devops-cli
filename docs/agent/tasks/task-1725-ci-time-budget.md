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

- [x] `tests/ai/review/test_pipeline.py::test_fake_scanner_results_with_absolute_paths_come_out_repository_relative` takes the `model_fake` fixture, so the report's group analysis asks the shared `ModelFake` (#1726, Part of #1725).
  - The test used to build a real model client. Its refused loopback connect waited out 1 + 2 + 4 + 8 seconds of transport retries.
  - Measured with `uv run pytest -n 0 --durations=0 -q tests/ai/review/test_pipeline.py`: the test went from 15.15s to 0.16s, and the file from 17.61s to 3.04s.
  - Every assertion is kept.

### Textual pauses in the UI tests

- [x] The `pilot.pause` waits in `tests/test_ui_reactive.py` (73 tests, 109s of sleep) are replaced by condition waits (`wait_for`), animation disablement, and synthetic docker doubles (#1740, closes #1339).
  - Measured with `uv run pytest -n 0 -q tests/test_ui_reactive.py`: went from 127s to 18s.

### Startup import probes

- [x] The `python -c` import probes in `tests/test_cli_startup_imports.py` (62 tests, 70-97s) measure each startup import argv once through shared probes (#1739, closes #1733).
  - Measured with `uv run pytest -n 0 -q tests/test_cli_startup_imports.py`: went from 84.2s to 14.5s.

### Retry backoffs against localhost services

- [x] The retry backoffs against refused Valkey, Ollama and RAG endpoints are eliminated: tests connect only to test servers they start, and a conftest fixture (`refuse_unstarted_localhost_services`) fails any test attempting loopback connections to unstarted services (#1744, closes #1741; #1772, closes #1320).

### kubectl in tests

- [x] The 33 tests that start `kubectl` (26s) render each committed kustomization once per test process with offline caching; offline renders (`kubectl kustomize`, `kubectl patch --local`) stay real (#1737, closes #1732; ADR 0007).

### Nested pytest in the isolation tripwire

- [x] The nested pytest runs in `tests/test_isolation_tripwire.py` (3 tests, 24s) run via in-process pytester (#1727, Part of #1725).

### Collection on the GitHub runner

- [x] Child processes keep `UV_` settings so the test row keeps the environment `uv sync` built; setup-toolchain action passes `--compile-bytecode`; and test bootstrap imports pydantic-ai lazily (#1763, closes #1735).

### Devcontainer tests on the runner

- [x] Post-create tests answer programs as installed via `image_programs_installed` double, name no Kubernetes context, and delete `os.getuid` rather than running real `sudo chown` (#1730, closes #1731).

### xdist balance and gate scheduling

- [x] Workers steal work across xdist with `--dist worksteal` in `pyproject.toml`, and the gate runs Bandit under `nice` (`DEFAULT_CI_BANDIT_NICENESS`) so it takes only idle CPU beside pytest (#1745, closes #1734).

### Real scanners in review tests

- [x] Review tests run against recorded scanner results via `scanner_fake` (`tests/support/fakes/scanners.py`), and `refuse_real_programs` fails any test starting real scanner binaries or bare `gh` (#1738, closes #1666).

### Item-only checks on the release pull request

- [x] Fixed in v0.2.37: the fail-to-pass check (#1721) and the changed-test shuffle (#1723) no longer run on the release pull request into main.

## Verification

- [x] Re-measured the gate, test suite, and CI against the targets on `release/v0.2.38`:

| Target | Before (2026-10-20, 4e61562) | After | Met |
|---|---|---|---|
| `uv run pytest -n auto` full suite runtime | 3m06s | 1m59s (11,147 tests) | yes |
| Local gate (`uv run devops ci`) concurrent execution | 3m11s | 17 concurrent gates passing | yes |
| No real scanner, gh, kubectl against cluster, or unstarted localhost service | about 82s of scanners; 8,116 OTLP connects | Refused by conftest floor guards (`refuse_real_programs`, `refuse_unstarted_localhost_services`) | yes |
| Pull-request CI workflows | 5+ minutes | All 15 PR check suites passing green | yes |
| Zero flaky reruns | Multiple flaky timeouts | Zero test flakes or reruns | yes |
