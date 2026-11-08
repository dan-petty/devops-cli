# Proposal

## Why

A full local `uv run devops ci` took 6m 53s for its pytest step on a shared agent host, against the 5-minute budget of AGENTS.md rule 5 (#3593). The plan states what that budget measures, because the parallel option that the issue asks for already runs the suite.

## What Changes

- State in `docs/TESTING.md` that the 300-second budget measures the mean of the `Tests & Coverage` check, and that a local full gate runs the whole suite on a host that other agents share.
- State that the gate prints the pytest step's time against the budget and the slowest tests, and fails no test on the time.
- Add no pytest option and no code, because the full suite already runs on `addopts`' `-n logical --dist worksteal`.
- The change has no spec delta: it changes one document and no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/TESTING.md`

## Feasibility

- The probes confirm the file of the slowest test that the issue names: "The path `tests/commands/test_ai_local_dry_run.py` is a file of the staging commit."
- The probes confirm the file of the host-state SSH test: "The path `tests/crypto/test_ssh.py` is a file of the staging commit."
- read_issue(3585) showed "#3585 issue, closed (completed)" and "No merged pull request closed it", and the body of #3593 says that the four host-state tests are tracked in #3585, so this item holds only the time budget.
- search_code("worksteal") showed that the full suite already runs on every logical CPU: `pyproject.toml:205:addopts = "-n logical --dist worksteal` and `docs/TESTING.md:159:the full suite, and the fallback to it, run on`.
- The 6m 53s run of the issue is a run of `devops ci`, whose test row uses those addopts, so the `-n auto` of the proposed design renames the worker count and cuts no time.
- The staged constants `src/devops_cli/config/defaults.py:469:DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12` and `src/devops_cli/config/defaults.py:470:DEFAULT_CI_TEST_NARROWED_WORKERS: Final[int] = 4` govern a narrowed run only, so the full suite keeps `-n logical`.
- The budget that AGENTS.md rule 5 sets is the mean of a check: `AGENTS.md:13:A build or check that averages more than 5 minutes is a P0 bug.` and `docs/TESTING.md:171:check must average under 300 s (AGENTS.md, rule 5).`
- The gate already compares its test step with the staged constant `src/devops_cli/config/constants.py:703:CONST_CI_TEST_BUDGET_SECONDS: Final[float] = 300.0` and prints the slowest tests: `src/devops_cli/commands/ci.py:def _warn_when_over_budget`.
- The issue's own numbers put the check at 290 s of the 300 s budget, so the check is under the limit that rule 5 names, and the excess is the local run on a host that other agents load.
- The cause of that excess is the shared host: `src/devops_cli/commands/ci.py:596:The gates of several agents share one host`, and the gate slot bounds how many gates run, not the CPU that each one gets.
- The project already concluded that no cut of constant work holds the bound on every host: `docs/TESTING.md:172:The same suite took 355 s on a fast runner and 528 s on a slow one`.
- The acceptance criterion of the proposed design, a step under 300 seconds, needs a test that bounds elapsed time from above, which the project forbids: `docs/TESTING.md:143:No test bounds elapsed wall-clock time from above.`
- So the item cannot be built as written: no command makes a wall-clock step deterministic on a shared host, and the parallel option that it asks for is already in force. This plan adds no code that compensates for it, and it records the budget's subject in the test guide.
- The first checks of the implementation against the real system are `uv run devops ci job-time`, which reads the mean of the check on `main`, and `uv run devops ci --dry-run --only test`, which prints the pytest command that the test row builds.
- `uv run devops ci job-time` needs a client of GitHub and a network, because it reads the job times of the check from the Actions API.
- `uv run devops ci --dry-run --only test` needs a checkout of the repository, because it reads the rows and the settings of the tree.
- `_resolve_pytest_cmd` needs a checkout of the repository, because it splits a shard by reading the test files of the project root.
- `uv run devops ci docs` needs a checkout of the repository, because the `docs` row runs `devops docs check` over the CLI and the documents of the tree.

## Existing Tool Considered

The change builds no code and needs no new tool: pytest-xdist 3.8.0 is already a test dependency and already runs the suite on every logical CPU, and pytest's `--durations` already gives the per-test seconds that the gate prints.

## Dependencies

None.
