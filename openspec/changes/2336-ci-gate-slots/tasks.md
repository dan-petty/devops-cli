# Tasks

## 1. Measure the default number of slots

- [x] 1.1 On a 16-CPU host, time `uv run devops ci test` alone and then two of them side by side, and read the load average and the process ids of the container. Add a "Measurement" section to design.md with the times, and set the divisor of the default from it. Verify: `openspec validate 2336-ci-gate-slots --strict` passes and the section names the times and the divisor.

## 2. Gate slots

- [x] 2.1 Write the failing tests in `tests/test_ci_gate_slots.py`: a free slot is taken; a run waits while every slot is held and starts when one is freed (the test passes a `sleep` that frees the slot); the slot is free after a normal exit and after an exception; a slot held by a child process is free after SIGKILL; the wait message names the process number and the worktree of each holder; the default number of slots is 1 for 4 CPUs and for 16 CPUs, and 2 for 32 CPUs. Verify: `uv run devops ci test tests/test_ci_gate_slots.py` fails because the module does not exist.
- [x] 2.2 Add `filelock` as a direct dependency with `uv add filelock`. Add `src/devops_cli/ci/gate_slots.py`. The command imports it when it takes a slot, so `devops --help` does not import `filelock`. The module holds one context manager that takes a slot, waits with a `sleep` parameter, writes the holder text and releases the slot in a `finally` block. Verify: `uv run devops ci test tests/test_ci_gate_slots.py` passes and `uv run devops ci lockfile` passes.
- [x] 2.3 Add the wait message to `src/devops_cli/lang/en/messages.py` in ASD-STE100, with no hard wrap. Verify: `uv run devops ci test tests/test_ci_gate_slots.py` passes and the invariant tests on messages pass (`uv run devops ci test tests/test_architectural_invariants.py`).

## 3. The `ci.gate_slots` setting

- [x] 3.1 Add failing tests to `tests/test_ci_gate_slots.py`: the setting is read from the config file and from `DEVOPS_CLI_CI_GATE_SLOTS`; the value 0 is refused with an error that names `ci.gate_slots`; an unset setting gives the number from the CPU count. Verify: `uv run devops ci test tests/test_ci_gate_slots.py` fails on the new tests.
- [x] 3.2 Add `CIConfig` with the field `gate_slots` to `src/devops_cli/config/settings.py`, register the key in `src/devops_cli/config/options.py`, and describe it in `config.example.yaml`. Verify: `uv run devops ci test tests/test_ci_gate_slots.py tests/test_config_audit_keys.py tests/test_config_commands.py` passes.
- [x] 3.3 Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci docs` passes and `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` name `ci.gate_slots`.

## 4. Take a slot in `devops ci`

- [x] 4.1 Write the failing CLI tests in `tests/test_ci_gate_admission.py`, one for each scenario of the spec: a heavy run waits; the pre-push selection takes no slot; the full-suite `devops ci test` and `devops ci coverage` wait while a narrowed `devops ci test tests/test_x.py` starts at once; a dry run and a cached verdict take no slot; a stop signal ends the wait and holds no slot; the wait is not in the summary or the over-budget warning and is recorded as `ci.gate_slot_wait_seconds`. Verify: `uv run devops ci test tests/test_ci_gate_admission.py` fails.
- [x] 4.2 Add the `heavy` flag to `CheckSpec` and set it for `test`, `security` and `typecheck` in `get_check_specs`. Take the slot in `all_checks` after the cached verdict and before the clock starts, in `coverage` before pytest starts, and in `test` before pytest starts when `workers` is `None`. Record the wait as `ci.gate_slot_wait_seconds`. Verify: `uv run devops ci test tests/test_ci_gate_admission.py tests/test_ci.py tests/test_ci_dry_run.py` passes.
- [x] 4.3 In `CONTRIBUTING.md`, in the step that describes the full `uv run devops ci`, say that parallel gates take turns, show how `ci.gate_slots` changes the number, and say which runs never wait. Add the same rule to the help text of `devops ci` (`HELP.ci.app`). Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci docs` passes and `docs/CLI_REFERENCE.md` shows the rule.

## 5. Check on the real host

- [x] 5.1 Set `ci.gate_slots` to 1, start `uv run devops ci --only test` in two worktrees at the same time, and read the output of the second. Verify: it prints the wait message with the process number and the worktree of the first, and it starts its checks only after the first ends.
- [ ] 5.2 Run the full `uv run devops ci` in the worktree. Verify: every check passes.

## Workflow follow-up

- A command that creates a worktree and refuses an issue that another agent holds is #2337.
- Removal of worktrees whose commits are merged, without a manual run of `prune`, is #2338.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
