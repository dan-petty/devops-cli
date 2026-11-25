### What happened

The host sandbox's own I/O loop never runs in CI, and product code detects test doubles to keep it out of tests.

- `sandbox/host.py` starts bwrap with `subprocess.Popen` itself. Its bounded loop reads stdout and stderr, stops at the output cap and at the deadline, kills the process group and reaps the child. The coverage run of CI at f4d7066b did not cover any of it: `sandbox/host.py` is at 69%.
- `_is_mock_subprocess` and `_communicate_mock` check whether the `Popen` object is a mock and then skip the loop. `tests/test_host_sandbox.py:193` patches `subprocess.Popen` with a mock, so its test runs this branch and not the real loop. docs/TESTING.md says that product code holds no check for a mock.
- The cases that run the real loop carry the `bwrap` mark: 10 in `tests/test_host_sandbox.py` and 6 in `tests/test_tool_executor_contract.py`. They run in the devcontainer, where bwrap is installed, and skip on the stock runner. So the devcontainer and CI do not run the same suite.
- The direct-executor cases of `tests/test_tool_executor_contract.py` start a real git as the tool. The audit saw 88 of its tests start git.

### What should happen

The owner's rule of 2026-10-24, recorded by #2143, applies: a test starts no program, and every test runs the same on every host.

- The host sandbox starts bwrap through one seam, the process runner or a spawn seam in `sandbox/host.py`. A test fills the seam with a double from `tests/support/fakes/process.py` that starts no child. Its stdout and stderr are pipes the test writes, and it records the signals and the reap.
- The I/O loop runs in CI against that double: the output cap, the deadline (on the clock fixture), the group kill and the reap.
- `_is_mock_subprocess` and `_communicate_mock` are deleted.
- The tool executor's cases run over the process fake and the recorded scanner runs. They start no git and no tool.
- The real-bwrap cases become an opt-in contract suite that a person runs in the devcontainer. A default `pytest` run, `devops ci` and CI do not select them.

Do not install bubblewrap in CI, and do not add a test that starts a real child process.

### Evidence

At b170358e:
- `src/devops_cli/sandbox/host.py:96-124`: `_is_mock_subprocess` and `_communicate_mock`.
- `:127-274`: the bounded loop; `:255-256` sends a double to the mock branch.
- `:297-303`: `subprocess.Popen(..., start_new_session=True)`.
- `tests/test_host_sandbox.py:74-125`, `:252-293`, `:373`, `:390`: the `bwrap` cases. `:193`: the patched `Popen`.
- `tests/test_tool_executor_contract.py:613`, `:633`, `:640`, `:993`, `:1014`, `:1067`: the `bwrap` cases. `:172`, `:688-735`, `:1052`: real git.
- `src/devops_cli/security/tool_executor.py:534-683`: `SandboxToolExecutor` starts bwrap through `run_subprocess`.
- CI run 40123645251 (stock ubuntu-24.04): 45 skipped. The devcontainer: 1 skipped.

### Acceptance criteria

- [ ] Tests first: with the double, a child that writes more than the cap is killed with its group, and the result names the cap. A child that passes the deadline is killed and `timed_out` is true. A child that does not exit after the kill is reaped. These tests fail on today's code, because the mock branch skips the loop.
- [ ] `rg -n "_is_mock_subprocess|_communicate_mock|_mock_return_value" src` prints nothing.
- [ ] The double lives in `tests/support/fakes/process.py` and is shared. No test builds its own `Popen` double, and no test patches `subprocess.Popen` for the sandbox.
- [ ] The tool executor contract cases that start git or a tool run over the process fake or `scanner_fake` instead.
- [ ] The `bwrap` cases run only when a person asks for them, for example with `-m bwrap`. CI and the devcontainer report the same test count for a default run.
- [ ] The coverage of `sandbox/host.py` in CI goes up from 69%. The pull request gives the new figure.
- [ ] `uv run devops ci` passes, and the `Tests & Coverage` job stays under 5 minutes.

Related: #1335 lists the deletion of the mock branch and live bwrap tests among its criteria. This item delivers the deletion as one pull request. Under #2143 the live tests become the opt-in suite. #1328 owns the mock check in `ai/review/pipeline.py`, and #1332 the one in `security/base.py`.


Source: https://github.com/dan-petty/devops-cli/issues/2143

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The host sandbox's I/O loop never runs in CI. Product code detects a mock Popen object and skips the loop. This violates the rule that product code holds no test accommodations. The real bwrap tests run in the devcontainer but skip on stock CI runners, so the two environments run different suites. The direct-executor contract cases start real git, which the owner's rule forbids.

### Acceptance criteria
- Criterion 1: A test with the process fake shows that a child writing more than the output cap is killed with its group, and the result names the cap.
  Verification: Run the new test. It fails on today's code because the mock branch skips the loop. It passes after the seam is added and the mock branch is deleted.
- Criterion 2: A test with the process fake shows that a child passing the deadline is killed and timed_out is true.
  Verification: Run the new test against the clock fixture. It passes after the seam is added and the mock branch is deleted.
- Criterion 3: A test with the process fake shows that a child not exiting after the kill is reaped.
  Verification: Run the new test. It passes after the seam is added and the mock branch is deleted.
- Criterion 4: Product code holds no mock-detection code.
  Verification: Run `rg -n "_is_mock_subprocess|_communicate_mock|_mock_return_value" src`. It prints nothing.
- Criterion 5: The process fake lives in tests/support/fakes/process.py and is shared by all sandbox tests. No test builds its own Popen double. No test patches subprocess.Popen for the sandbox.
  Verification: Run `rg -n "Popen" tests/`. No test file builds a Popen double or patches subprocess.Popen for the sandbox.
- Criterion 6: The tool executor contract cases that start git or a tool run over the process fake or scanner_fake instead.
  Verification: Run the contract suite. The hermetic floor fails any test that starts git or a tool. No such failure occurs.
- Criterion 7: The bwrap cases run only when a person selects them with -m bwrap. A default pytest run, devops ci, and CI do not select them.
  Verification: Run `uv run pytest` without -m bwrap. The bwrap cases are not selected. Run `uv run pytest -m bwrap` in the devcontainer. The bwrap cases run.
- Criterion 8: CI and the devcontainer report the same test count for a default run.
  Verification: Compare the test count of `uv run devops ci` on the stock CI runner and in the devcontainer. The counts are equal.
- Criterion 9: The coverage of sandbox/host.py in CI goes up from 69%.
  Verification: The pull request states the new coverage figure. It is above 69%.
- Criterion 10: The full CI gate passes and the Tests & Coverage job stays under 5 minutes.
  Verification: Run `uv run devops ci`. It passes. The Tests & Coverage job duration is under 5 minutes.

### Key questions
- **What is the seam that the test fills with the process fake?**: The call to subprocess.Popen in sandbox/host.py at line 297-303. HostSandbox starts bwrap through this call. A test replaces it with a fake that provides pipes for stdout and stderr and records kill and wait. [sources: src/devops_cli/sandbox/host.py:297-303]
- **What interface does the process fake expose for the I/O loop?**: The fake provides stdout and stderr as pipes the test writes to. It records the signals sent (kill) and the reap (wait). The test writes to the pipes to simulate the child's output, and the I/O loop reads from them. (proposed)
- **How do the bwrap-marked tests become opt-in so that CI and the devcontainer report the same count?**: A default pytest run, devops ci, and CI do not select bwrap-marked tests. A person runs them with -m bwrap in the devcontainer. The exclusion is set in the test configuration so both environments report the same count. (proposed)
- **Does the process fake extend the existing ProcessFake or is it a new class in tests/support/fakes/process.py?**: The existing ProcessFake returns CompletedProcess for run_subprocess. The sandbox I/O loop needs a Popen-like object with pipes. A new class in the same file is the likely approach, since the body names the file as the home of the double. (proposed) [sources: tests/support/fakes/process.py]
- **Which files hold the mock-detection code that must be deleted?**: src/devops_cli/sandbox/host.py at lines 96-124 holds _is_mock_subprocess and _communicate_mock. The body cites these as the only locations in src that detect a mock. [sources: src/devops_cli/sandbox/host.py:96-124]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Priority": "P2-Medium", "Status": "In Review", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "9f1b63e4e7b49a670c12cc89a690e9dbe3bd8e2fc04f22e8d1bc334993a41a1c", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "3f5542a3732e32d21be96410c4ae021b0e80aa9008e681104425fa8da4b6f1f1"} -->
