# Proposal: #4715

## Why

No automatic run selects the 55 tests with the `bwrap` mark: the root conftest deselects them unless `-m bwrap` is given, and no row of `devops ci` and no CI job gives it (change #2149). When a person runs them in the devcontainer, 2 tests fail and 2 tests give a teardown error: `_running` in `tests/ai/test_tool_executor_contract.py` reads `/proc/<pid>/cmdline` in the test process, and the host path guard of the floor refuses `/proc` (#2165). The marker text in `pyproject.toml` does not say that a default run deselects these tests. Closes #4715.

## What Changes

- `_running` reads the process table of the host with `ps -e -ww -o args=`. The two tests that call it carry `@pytest.mark.live("ps")`. The floor and its host path guard do not change.
- `devops ci` gets the row `bwrap`. It runs `uv run pytest -m bwrap -n 0 --timeout=60` over `tests/sandbox/test_host_sandbox.py` and `tests/ai/test_tool_executor_contract.py`. The bound of 60 s for each test is shorter than the 3-minute limit of the gate step of `Static Analysis`.
- A row can have a host check (`CheckSpec.host_refusal`). The `bwrap` row uses the host check of `SandboxToolExecutor`, which `host_refusal()` now makes public: bubblewrap and prlimit are installed, and bubblewrap can make a sandbox. On a host that fails it, the row starts no command, passes, and shows `skipped: <cause>` in its line and in the summary. The CI cache keeps the cause.
- `sandbox_host` in `tests/support/ci_root.py` puts a stand-in for bubblewrap and prlimit on PATH for every gate test that uses `ci_root` or `ci_head`, so no gate test reads the bubblewrap of the host.
- `RUNNER_TOOLS` names the row as a reason for pytest. `NOT_IN_RUNNER` gives the new reason for `bwrap` and names `ps`.
- The marker text, `docs/TESTING.md`, `docs/SDLC.md` and ADR 0007 say that the `bwrap` row runs the suite where the host can make the sandbox and skips with the cause elsewhere.
- The change adds a row and a message to `devops ci`, which a consumer sees, so it has a spec delta.

## Capabilities

- `ci-gate-rows`: the `bwrap` row runs the sandbox contract suites where the host can make a sandbox, and skips with the cause where it cannot.

## Impact

- The full `devops ci` in the devcontainer runs the contract suite of the real sandbox: 55 tests, 9.3 s for the row.
- `Static Analysis` runs `devops ci --check --no-cache --skip test,outdated,actionlint`, so it runs the row. On its `ubuntu-26.04` runner, bubblewrap makes the sandbox with no install, so the suite of the real sandbox gates each pull request. The row took 49 s there, beside the `security` row of 81 s, which sets the time of the step. No workflow changes and no package is installed on a runner.
- The change fits one pull request.

## Feasibility

- At `origin/main` 310981773, `uv run pytest -m bwrap tests/sandbox/test_host_sandbox.py tests/ai/test_tool_executor_contract.py -n 0` gives `2 failed, 53 passed, 2 errors`. Both failures are `host path reached without a fake: /proc/1/cmdline` from `_running`. Each teardown error is the same refusal, which the floor records and reports again after the test.
- With this change the same command gives `55 passed in 3.58s`, and `uv run devops ci --only bwrap --check --no-cache` passes in 9.27 s in the devcontainer.
- `Static Analysis` runs on `ubuntu-26.04`. The list of installed apt packages of that image (`actions/runner-images`, `images/ubuntu/Ubuntu2604-Readme.md`) does not name bubblewrap, but the first CI run of this change shows that the runner has it and can make the sandbox: the row passed in 49 s, and the gate step took 82 s, against 90 s on `main` at 310981773. A host with no bubblewrap gets the cause `bubblewrap (/usr/bin/bwrap) is not installed`.
- `SandboxToolExecutor._host_cause` (`src/devops_cli/security/tool_executor.py`) already finds a host where AppArmor refuses bubblewrap a user namespace, which a check of the binary alone does not find.
- The tests of `tests/commands/` and `tests/ci/` pass in the devcontainer and with a plugin that removes bubblewrap from the host (3,780 passed).

## Existing Tool Considered

- `ps` of procps reads the process table of the host, so the test process does not read `/proc` and the floor needs no exemption.
- pytest markers select the suite (`-m bwrap`) and allow `ps` (`live`). The host check is the existing check of the sandbox executor.
- The skip state of a row is new code in `src/devops_cli/commands/ci.py` and `src/devops_cli/ci/cache.py`, about 40 lines: no tool gives a row of `devops ci` a host check. Cost: about 60,000 tokens to build and about 5,000 tokens a year to keep, with 2 hours of elapsed time.
- The change deletes the loop over `/proc/*/cmdline` in `_running`.
