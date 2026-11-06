# Proposal

## Why

Issue #3575, split from #3053. The shell allowlist of the agent admits `git`, so an agent can commit. A step makes the only commit, so today the first exit check stops the step with the class `head_moved` when the head is not at the head of the keeper. The step then discards the work and gives no repair turn. The stop of #2636 read "The agent moved HEAD" after 7,166,584 input tokens, and all that work went. A wider refusal of git commands is not the answer: refused commands are already the largest stop class, and #2695 records the decision on the sandbox.

## What Changes

- `_exit_failure` in `src/devops_cli/roadmap/implement_step.py` puts a moved head back with `git reset --soft <expected head>`, where the expected head is `WipKeeper.expected_head`. The index and the checkout keep the work of the agent. The exit checks then judge that work, and a commit of the agent in an extra turn is reset the same way.
- The step stops with the class `head_moved` only when the reset exits with a status other than 0. The reason names the reset command, its exit status and the output of git.
- The step prints one muted line that names the moved head and the expected head.
- The reset goes to the expected head of the keeper, so the `wip:` commits of the step stay in the history until the step folds them into its commit.
- The class `head_moved` keeps its action `retry`. The change adds no class and no setting.
- The change carries spec deltas in `roadmap-implement-step` and `roadmap-implement-job`, because the stop reason, the Job log line and the cases of the class `head_moved` are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the requirement `A step makes the only commit` states the reset of a moved head.
- `roadmap-implement-job`: the requirement `A stop site passes a typed class of its cause` states the case of the class `head_moved`.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`.
- `docs/ROADMAP_WORKFLOW.md` (the row of `head_moved`).
- Tests in `tests/roadmap/` that stated the old stop.

## Feasibility

Checked on `origin/main` ad1e4b83, on 2026-11-06.

1. The defect is real. `_exit_failure` compared `_head(source)` with `keeper.expected_head` and returned a `head_moved` failure before any other check. The tests `test_a_commit_that_the_agent_makes_stops_the_step_and_the_checkout_returns_to_its_start` and `test_an_extra_turn_that_commits_stops_the_step_and_the_checkout_returns_to_its_start` held that stop.
2. The repair works on a real git repository. The new tests run real git in `tmp_path`, as the other step tests do. A step in which the agent commits during the turn ends done, its one commit has the start commit as parent, and it holds the work of the agent. A step in which the agent commits after a `wip:` commit also ends done, and the commit of the step folds the `wip:` commit. The cases in which a check fails after the reset end stopped with that failure, not with `head_moved`.
3. `git reset --soft <commit>` moves HEAD only; the manual of git (`git-reset`) says it touches neither the index file nor the working tree. This is the mode the keeper already uses in `fold` and `unfold`.
4. Not verified: a real run with a real model. A stub model script replays the agent, and one faked `git reset` stands for a reset that fails.

## Existing Tool Considered

git covers the reset with `git reset --soft`, which is open, maintained and installed in the runner. The project adds one call in the step (about 20 lines). Cost to build: about 20,000 tokens and about 1 hour. Cost to keep: about 1,000 tokens each quarter. Cost to fix one miss: about 5,000 tokens. The change deletes the stop of the first exit check and the two tests that held it.
