# Proposal

## Why

Issue #2721. The first live run of the implement job stopped at group 1 although the agent wrote the fix. The agent did the work and forgot to tick a task in `tasks.md`. The step then stopped with "A task of the group is not ticked", reset the checkout, and kept nothing. The pull request had only its plan commit, and a person could not see what the agent wrote.

Two things in the design made one forgotten tick cost the whole step:

1. The job needs the model to tick each task. The tick is a bookkeeping act. The job can check that the work is done (verification and static checks), but it asked the model for the tick only once, in the first run.
2. A stopped step keeps nothing. The diff of the discarded work is gone, so a person cannot judge the work or decide to retry.

## What Changes

- The instructions of the step and its user message name the exact path of the `tasks.md` of the change and the exact form of a tick (`- [ ]` to `- [x]`). They say that the step is not done until every task of the group is ticked.
- The exit checks run in a new order. The group may change only in its checkboxes and no other group may change. Then each verification command and the static checks run. The check that every task is ticked runs last.
- A step whose only fault is missing ticks gets one more model turn. The verification and the static checks have passed by then. The turn asks only for the ticks and lists the unticked tasks. It is the same conversation and the same `UsageLimits` as the first turn. The turn may change only `tasks.md`. The job checks this with git, and any other change stops the step. After the turn every exit check runs again.
- A stopped step keeps the diff of its work. The step reads the diff of the discarded work, masks secrets in it (`devops_cli.security.sanitizer.mask_secrets`) and cuts it to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters. `StepOutcome` carries it. The job posts it in the stop comment in a fenced block. The fence is longer than any run of backticks in the diff, so no text of the diff can end the block.
- A consumer observes the stop comment, the exit order and the `StepOutcome`, so the change carries spec deltas. It modifies three requirements of `roadmap-implement-step` and one of `roadmap-implement-job`, and adds three requirements to `roadmap-implement-step`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the exit checks and their order, the inputs of a step and the limits of a run change. Three requirements are added: the tick turn, the files that the turn may change, and the diff of a stopped step.
- `roadmap-implement-job`: the stop comment holds the diff of the discarded work.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_roadmap_implement_step.py`, `tests/test_roadmap_implement_job.py` and the snapshot of the inputs of a step.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The failure is real. The comment of the Service on #2656 reads "Stopped at group 1. Reason: A task of the group is not ticked: [ ] 1.1 Write a test in tests/test_round_trip.py ...". Its "Last message of the agent" says that the agent changed `src/devops_cli/config/round_trip.py`, ran its tests and says nothing of a tick. The code path is `_tasks_failure` in `implement_step.py`: it returns `implement_stop_unticked` before any verification command runs, and `run_step` resets the checkout.
- One more turn of the same conversation is possible with the installed pydantic-ai 2.59.0. Read in `pydantic_ai/conversation.py` and `pydantic_ai/run.py`: `AgentRunResult.conversation` returns a `Conversation` with the messages, the running `usage` and the `conversation_id`, and `run_sync(conversation=...)` continues it. The docstring says that `message_history=` alone drops the usage, "without which every turn's `UsageLimits` budget starts over from zero".
- Probed with a `FunctionModel` and `UsageLimits(request_limit=2)`: the first turn used 1 request, the second turn started with the usage 1 and ended with 2, and a third turn raised `UsageLimitExceeded` ("The next request would exceed the request_limit of 2"). The same third turn with `message_history=` alone ran with the usage reset to 1. So `conversation=` keeps one budget for both turns, and `message_history=` does not.
- `capture_run_messages` captures only the first run in a context ("`messages` will represent the messages exchanged during the first call only"). The second turn opens its own context. In it the list holds the messages of the history and then the new ones, so the job counts the new replies after the replies of the history.
- Git can say which files the turn changed. `git write-tree` after `git add -A` gives a tree of the work before the turn, and `git diff --cached --name-only -z <tree>` after `git add -A` lists the paths that differ from it. The job needs no file parser.
- A fenced block that text cannot end is a rule of CommonMark (section 4.5): a closing fence needs at least as many backticks as the opening fence. A fence longer than the longest backtick run of the text is safe. A test parses the comment with `markdown-it-py`, which the project already uses, and asserts one fenced block that holds the whole diff.

## Existing Tool Considered

pydantic-ai `Conversation` and `UsageLimits`, already in use, give the extra turn and the shared budget. `git write-tree` and `git diff --cached --name-only` give the check of the changed files. `devops_cli.security.sanitizer.mask_secrets` masks secrets. `markdown-it-py` parses the comment in the test. The change builds only the two decisions that no tool makes: when the extra turn runs, and how long the fence is (one `max` over the backtick runs). Cost of what it builds, estimated: about 250 lines of code and tests, about 120k tokens of agent work and half a day of elapsed time. The upkeep is small: the code follows `Conversation` and git.

The change deletes no code. It replaces the early unticked check in `_exit_failure` with the check at the end of the sequence.
