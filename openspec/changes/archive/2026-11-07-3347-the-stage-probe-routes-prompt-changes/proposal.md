# Proposal

## Why

The issue #3347 reports a plan that changed planner prompts and cited only the plan test, so no prompt-rule test read or verified the prompt. The plan check accepts such a plan, and a prompt edit can then break the agreement between the prompt text and the rules with no notice. The change refuses that plan and states the rule in the two planner prompts.

## What Changes

- Add `PROMPT_RULE_TEST` and `PROMPT_PREFIX` to `src/devops_cli/roadmap/stage/stage_change.py`, and add `_prompt_rule_problems` to the problems of `content_problems`.
- Refuse a group that changes a `src/devops_cli/ai/tasks/roadmap_stage_*.md` prompt and lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in neither `reads` nor `changes`.
- Refuse a group that changes such a prompt and gives no `verify` command that names `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, including a group that gives `process` in place of `verify`.
- Add the message `stage_problem_prompt_rule` to `src/devops_cli/lang/en/messages.py`.
- State the rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`, and pin the sentence in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- The change carries a spec delta because `devops roadmap stage` and its messages are observable to a consumer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A prompt change lists the prompt-rule test, A prompt change verifies the prompt-rule test, The stage prompts name the prompt-rule test

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds, and the paths of the issue moved: the probe reads "The path `roadmap_stage_change.md` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/tasks/roadmap_stage_change.md`. No commit in the history deleted or renamed it."
- The issue cites the prompt-rule test at a path that the staging commit does not hold: the probe reads "The path `tests/roadmap/test_roadmap_stage_prompt_rules.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`." The test exists at `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, and the check names that path. The same move holds for `tests/roadmap/stage/test_roadmap_stage_plan.py`.
- The cited check file also moved: `list_files src/devops_cli/roadmap/stage` shows `stage_change.py`, and `search_code "def content_problems"` finds `src/devops_cli/roadmap/stage/stage_change.py:def content_problems`, so the rule has its place in the staged commit.
- `read_file src/devops_cli/roadmap/stage/stage_change.py` shows `content_problems` calling `_message_file_problems` and `_self_acceptance_problems`, so one more call in that function adds the rule to the gate that the job and the replay both run.
- `read_file src/devops_cli/roadmap/stage/stage_change.py` shows `STAGE_EVAL_TRIGGER_PATHS` with `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/roadmap/stage/stage_change.py`, so group 1 also runs the replay with the score before and after.
- `read_file tests/roadmap/stage/test_roadmap_stage_content.py` shows `def _plan_that_adds_a_rule` and `SELF_ACCEPTANCE_TEST`, so the new tests of `content_problems` go in that module, beside the tests of the message-file rule.
- `read_file src/devops_cli/ai/tasks/roadmap_stage_change.md` shows no sentence that names `test_roadmap_stage_prompt_rules`, so the prompt states no prompt-rule rule and this plan adds it.
- A precondition of the check: `check_proposal` needs a checkout of the repository to read the tree of the staged commit (`StagedTree`), and `plan_recheck` needs a client of GitHub to read the plan on the default branch.
- A precondition of the first test: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` needs a checkout of the repository with its dependencies installed.
- A precondition of the prompt pin: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` needs a checkout of the repository, because it reads `AGENTS.md` and `docs/TESTING.md` from the tree.
- A precondition of the replay: `uv run devops roadmap eval stage --replay` needs a checkout of the repository and no network, because it reads the golden cases under `tests/fixtures/roadmap_eval/stage/`.
- The first checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then `uv run devops roadmap eval stage --replay`, then `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool or library covers this need, because the check reads the `groups` of this repository's own `StageProposal` inside `content_problems`. The change builds its own code: about 60k tokens to build, about 6k tokens to keep and fix at each later change, and about 3 hours of elapsed time. It deletes no internal code.

## Dependencies

- #3955 changes `src/devops_cli/lang/en/messages.py`, the file where this plan adds `stage_problem_prompt_rule`.
- #3957 changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/lang/en/messages.py`, the two paths where this plan adds the prompt sentence and the message.
- #3961 changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/lang/en/messages.py`, the two paths where this plan adds the prompt sentence and the message.
- #3981 changes `src/devops_cli/lang/en/messages.py`, the file where this plan adds `stage_problem_prompt_rule`.
