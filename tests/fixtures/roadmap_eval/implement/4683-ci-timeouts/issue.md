### Problem or Motivation

The `devops ci` check timeout of 1800 s (`src/devops_cli/config/defaults.py:353`) cannot fire in CI, because the 30-min job limit includes about 30 s of setup. Service Image Tests start `pytest.main` with no check timeout (`.github/workflows/ci.yml:653`).

pytest-timeout does not end a hung teardown: a probe ran until the outer kill, rc 124 (measured). `docs/TESTING.md:153` says otherwise.

The coverage-index build took 1,627 s of its 1,800 s timeout (measured once), so one 600 s hang makes the index stale.

The owner rule of 2026-11-11 says that each inner timeout is shorter than the one around it (test < step < job).

Saving: None on a green run. A hang gives a clear failure line.

Found by the CI and test audit of 2026-11-11. The account runs at most 20 hosted jobs at one time (measured), so each job that does no work makes the queue of each pull request longer.

### Proposed Solution & Architectural Design

- Add an optional `timeout_seconds` to `CheckSpec` (`src/devops_cli/commands/ci.py:144-163`).
- Use 900 s for the test row of a `--shard` run, inside the 20-min job limit of #4677.
- Wrap the Service Image Tests `docker run` in `timeout --kill-after=30 900` (coreutils).
- Give the index build its own constant of 3600 s, with a comment that gives the measured time.
- In `docs/TESTING.md:153`, say that the row timeout and the job timeout bound a hung teardown.

Risk: Low.

### Target Subsystem

SDLC, Git & PR Governance (`src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `.github/workflows/ci.yml`, `docs/TESTING.md`).

### Existing Tool Considered

coreutils `timeout` and the existing pytest-timeout. No new tool. Cost: about 30,000 tokens and 2 hours.

### Acceptance Criteria

- In a shard run, a probe test with a hung teardown ends at 900 s with a 'timed out' line from `devops ci`, before the job limit.
- Service Image Tests end a hung run at 900 s.
- The index build uses 3600 s.
- `docs/TESTING.md` gives the bound.

### Dependencies

Depends on #4677.

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-14: partly.
Tool: coreutils/coreutils (https://github.com/coreutils/coreutils), GPL-3.0, last activity 2026-11-13, maintained.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.adr_hash": "a1cd29eb2588913c344a50dcec7edc599fc9cc39aed976ed694194eb1398099a", "alternatives.body_hash": "67f88b8e77a8303d81b1044c609007d43f1c9b8f1c2ec5279f13b950990dcae2", "alternatives.checked_at": "2026-11-14T02:21:20.996548+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": "https://github.com/coreutils/coreutils", "alternatives.tool_id": "github.com/coreutils/coreutils", "alternatives.verdict": "partly"} -->
