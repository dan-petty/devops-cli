## Problem

Since #6537 (#6517, 2026-11-20), the runner image installs no dev group into `/app/.venv`. The bootstrap of the Job installs the dev group into `<checkout>/.venv`, and `checkout_environment` puts that venv first on the PATH of the checks.

The base replay of a behavior group does not use that venv. `replay_group_tests` (`src/devops_cli/roadmap/implement/implement_base_replay.py`) calls `replay_on_base` in the Job process, and `pytest_replay_argv` (`src/devops_cli/ci/fail_to_pass.py`) starts `sys.executable -m pytest`. In the Job, `sys.executable` is `/app/.venv/bin/python`, which has no pytest. So each behavior group stops at its first exit check, and the Job discards the work.

Stop reports of 2026-11-21 with `/app/.venv/bin/python: No module named pytest`:

| Item | Time | Failed check |
| --- | --- | --- |
| #6603 | 09:51Z | `pytest on base: tests/roadmap/project_review/test_review_readers.py` |
| #4147 | 14:18Z | `pytest on base: tests/security/test_secret_redaction.py` |
| #6522 | 15:50Z | `pytest on base: tests/github/test_ci_job_time.py` |
| #6627 | 19:29Z | `pytest on base: tests/roadmap/refine/test_roadmap_refine_sanitize.py, tests/roadmap/test_roadmap_body_hash.py` |

The #6627 run used 4,475,162 input tokens before it stopped.

`openspec/specs/roadmap-implement-runner/spec.md` already says that the exit checks of a step get the checkout venv first on PATH. The replay ignores PATH, because it names the interpreter.

## Expected

The base replay of an implement step runs the Python of `<checkout>/.venv`. `devops ci fail-to-pass` keeps `sys.executable`, because its process runs in the checkout venv.

This is a fix of a broken existing check, not a new gate, so the freeze of #6519 does not apply.

## Acceptance criteria

- A test shows that `replay_group_tests` starts pytest with `<checkout>/.venv/bin/python`.
- The spec of the runner says which interpreter the base replay uses.
- After the release, the next implement Job with a behavior group reports a base replay result and not `No module named pytest`.

## Dependencies

None. Related: #6517, #6519, #6627.


## Source

Source: https://github.com/dan-petty/devops-cli/issues/6627

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P0-Critical", "Status": "In Review", "Value": "High", "claim.replaced_status": "New"} -->
