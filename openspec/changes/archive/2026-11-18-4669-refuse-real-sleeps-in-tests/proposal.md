# Proposal: #4669

## Why

No rule refused a real sleep in the test suite. An audit hook recorded 177 s of real sleep in 629 tests in 96 files in the probed test suite. direct `time.sleep` calls stayed across `src`, and tests waiting on rate limits or process loops slept for real. Each second of real sleep delays pull request checks and wastes continuous integration compute.

## What Changes

- Ban direct calls to `time.sleep` in `src` using the ruff TID251 banned-api table in `pyproject.toml` without per-file ignores.
- Route all direct waits in `src` through `devops_cli.core.clock.sleep`.
- The single allowed real wait in `src` stays in `src/devops_cli/core/clock.py` under `# noqa: TID251`.
- Record a reasoned waiver for `src noqa: TID251` with ceiling set to 1 in `DEFAULT_SUPPRESSION_CEILINGS`. Reason: `src/devops_cli/core/clock.py` is the single clock seam in `src` that supplies real time waiting when fake clocks are not attached.
- Add `real_sleep` marker to pytest markers in `pyproject.toml`.
- Add an audit hook in `tests/conftest.py` for the standard library `time.sleep` audit event (PEP 578). An autouse fixture fails any test whose real sleep exceeds the 0.25 s budget unless the test declares `@pytest.mark.real_sleep`.
- Update tests in `tests/commands/test_pr_update.py` to use `clock: ClockFake`.
- Mark real process-wait tests in `tests/commands/test_ci.py`, `tests/telemetry/test_sigterm_export.py`, and `tests/github/test_github_session.py` with `@pytest.mark.real_sleep`.
- Add invariant tests in `tests/invariants/test_refuse_real_sleeps.py`.
- No consumer sees a change, so the change has no spec delta (`skip_specs: true`).

## Capabilities

None. Internal test suite floor and static code quality rules.

## Impact

- Prevents real sleep regressions from entering `src` or the test suite.
- Reduces test execution time in continuous integration.
- The change fits one pull request.

## Feasibility

- The PEP 578 audit event `time.sleep` reliably intercepts calls to `time.sleep` in Python standard library.
- Tests requesting the `clock` fixture replace `time.sleep` with `ClockFake.sleep`, producing 0 audit events.
- All 22 call sites in `src` now wait through `devops_cli.core.clock.sleep`.
