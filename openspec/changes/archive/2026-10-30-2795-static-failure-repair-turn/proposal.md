# Proposal

## Why

Issue #2795. The implement Job `devops-cli-runner-20261030-185232-83ce` ran #2745 with the 0.22.6 image. The agent fixed `_write_content` and wrote tests. The Job formatted the test file. Then `uv run ruff check` found an unused import in the test file (`pytest`), the step stopped at group 1, and the Job discarded all of the work.

A step gives the agent no turn after the exit checks. So one fault that the agent can fix in one edit costs the whole group. The tick turn (#2721) already fixes this for a forgotten tick. A fault of `ruff check` or `mypy --strict` has the same shape: the work is good, the fault is small, and the agent has not seen the text of the fault.

## What Changes

- After the agent ends its run, the verification commands pass, and `ruff check` or `mypy --strict` fails, the step runs one more model turn. The turn continues the same conversation under the same `UsageLimits`. Its message holds the text of the failure.
- The turn may change only the files that the step had changed before it, and the `tasks.md` of the change. Git checks this, as it does for the tick turn.
- After the turn every exit check runs again. When a check still fails, the step stops with the first check that fails, as it does today.
- A step gets at most one extra turn, whichever check asks for it. When a static check fails and a task is unticked, the one turn lists both. When a static check passes after the turn and a task is still unticked, the step stops. It does not run a tick turn after a repair turn. When the tick turn runs first and a static check fails after it, the step stops.
- The two turns share one helper in `implement_step.py`. The code of the tick turn moves into it. It does not get a copy.
- The instructions of the step say that a failed static check gets one turn.
- A consumer observes the exit order and the turns of a step, so the change carries a spec delta. It modifies two requirements of `roadmap-implement-step` and adds two.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the exit checks, the requirement for the tick turn, and two added requirements for the turn that fixes a failed static check and the files it may change.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `tests/test_roadmap_implement_step.py` and a new `tests/test_roadmap_implement_step_repair.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The failure is real. The stop comment of the Service on #2745 (18:57 UTC) reads "uv run ruff check -- src/devops_cli/config/settings.py src/devops_cli/config/write_history.py tests/config/test_config_file_mode.py exited with status 1. unused-import: `pytest` imported but unused". The diff in the comment shows ticked tasks and working code. The code path is `_exit_failure` in `implement_step.py`: it returns the failure of `_static_failure`, `_attempt` runs no turn for it, and `run_step` resets the checkout.
- The premise "the agent could not run `ruff check` itself" is not shown. The shell allowlist holds `ruff` and `mypy` (`IMPLEMENT_SHELL_PROGRAMS` in `config/commands.py`, with `uv`,). The Job log of that run (Loki, stream `devops/runner`) shows 11 `shell` calls: ten with the program `uv`, ok, and one with the program `other`, refused. A refused call names `other` only for a program that is not on the allowlist, so it was not `ruff`, `mypy` or `uv`. So the allowlist is no cause, and this change leaves it as it is. The text of the failure goes into the message of the turn, so the agent needs no shell call to read it.
- One more turn of the same conversation is possible. #2721 proved it on pydantic-ai 2.59.0: `run_sync(conversation=...)` keeps the messages and the usage, so one `UsageLimits` covers both turns. The tick turn is in production use with it.
- Git can say which files the turn changed. `git write-tree` after `git add -A` gives the tree before the turn. `git diff --cached --name-only -z <tree>` after the turn lists what differs. `_foreign_change` already does this for the tick turn. The repair turn passes it a set of paths that the turn may change.
- The failure text is bounded before it reaches the model. `_command_failure` keeps the last `CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES` lines of the output, and the message cuts the text to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters.
- The case of both a static failure and an unticked task: the exit order puts the ticks last, so a step with both reports the static failure first. One turn that lists both costs one conversation turn. Two turns would cost two. The turn is the same conversation, so the model has the context of both. The step runs one turn.

## Existing Tool Considered

pydantic-ai `Conversation` and `UsageLimits`, already in use, give the extra turn and the shared budget. `git write-tree` and `git diff --cached` give the check of the changed files. `ruff` and `mypy` give the failure text, and the step already runs them. The change builds only the decision of which failure gets the turn. Cost, estimated: about 120 lines of code and tests, about 80k tokens of agent work and two hours of elapsed time. The upkeep is small: the code follows the helper that the tick turn already uses.

The change deletes no code. It moves the body of `_tick_turn` into a helper that both turns use, and it widens `_foreign_change` to take the paths that a turn may change. A fix with `ruff check --fix` in the Job was considered and rejected (see the design).
