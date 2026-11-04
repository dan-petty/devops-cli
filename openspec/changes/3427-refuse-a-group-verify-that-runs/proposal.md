# Proposal

## Why

The stage check accepts a group whose `verify` command runs a test module that does not read the file the group changes (#3427). The command passes on the base, so the plan proves nothing about the change.

## What Changes

- `form_problems` in `src/devops_cli/roadmap/stage_form.py` refuses a `verify` command that runs a test module outside the group's `changes`, `creates` and `reads`, and does not judge a negative search that names a test module, because it searches and runs no test.
- A new `RoadmapMessages` entry in `src/devops_cli/lang/en/messages.py` names the group, the command and the unnamed test module, and gives the remedy: list the module in `reads`, or give the command of the group's own test.
- `tests/roadmap/test_roadmap_stage_form.py` covers an unnamed module, a module named in `reads`, `changes` and `creates`, and a command that runs no test module.
- The staging prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` states the rule, and `tests/roadmap/test_roadmap_stage_prompt_rules.py` asserts it, so the model writes the `reads` entry before the retry.
- The sample builder already names `tests/test_sample.py` in `changes` and `creates`. The `_plan` helper of `tests/roadmap/test_roadmap_stage_form.py` keeps that test as its default `verify` after a case changes another path, so the helper takes its `verify` from the case's own test module.
- The plan of the `good-2491-a-refused-jwt-exchange-of-the` case updates `tests/github/test_github_app_identity.py`, but its group names no such path in `changes` or `reads`. The change adds the path to `changes`, so the golden set replay keeps a good plan accepted.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A verify command runs a test that its group names, and the staging prompt states the rule

## Impact

- Code: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`

## Feasibility

- `search_code` for `_is_test_module` showed the helper in `src/devops_cli/roadmap/stage_form.py`, and the probe `_is_test_module` lists `src/devops_cli/roadmap/stage_form.py` as its one caller, so the rule has one definition to reuse.
- `read_file` of `src/devops_cli/roadmap/stage_form.py` showed `form_problems` calling `_verify_problems(number, group.verify)` and reading `group.creates` in the same loop, so the group's own paths are already at hand.
- The probe output says `The path `src/devops_cli/roadmap/stage_form.py` is a file of the staging commit.` and `The path `tests/roadmap/test_roadmap_stage_form.py` is a file of the staging commit.`, so both cited paths exist at this commit.
- The probe output says `The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit.`, so the message catalog that the issue cites exists.
- `read_file` of `tests/roadmap/test_roadmap_stage_task_verification.py` showed that the module builds a `StageGroup`, renders `tasks.md` and parses it, and loads no prompt, which confirms the evidence of the issue.
- A trial of the rule over the recorded plans and the form tests showed two faults that the rule exposes, and neither is a fault of the rule. `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` reports `good-2491-a-refused-jwt-exchange-of-the: a good plan is refused by the gate paths.` until the plan lists `tests/github/test_github_app_identity.py` in `changes`; the `test` task of that group already updates the module. `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails 11 cases, because the `_plan` helper keeps the sample's `tests/test_sample.py` as the `verify` after a case changes another path.
- `read_file` of `tests/support/builders.py` showed that the default sample names `tests/test_sample.py` in `changes` and `creates`, so the sample builder needs no change.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails before the change and passes after it, and `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` still passes, because the new rule judges only the `verify` command of a group.

## Existing Tool Considered

No open, maintained tool checks that the test a plan's command runs exercises the file that the plan changes. The rule extends `form_problems`, which already parses every `verify` command of a plan. Written cost: about 3,000 tokens to build, about 1,000 tokens per year to keep and fix, and about 2 hours elapsed.

## Dependencies

None.
