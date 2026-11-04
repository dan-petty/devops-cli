# Proposal

## Why

The stage check accepts a group whose `verify` command runs a test module that does not read the file the group changes (#3427). The command passes on the base, so the plan proves nothing about the change.

## What Changes

- `form_problems` in `src/devops_cli/roadmap/stage_form.py` refuses a `verify` command that runs a test module outside the group's `changes`, `creates` and `reads`.
- A new `RoadmapMessages` entry in `src/devops_cli/lang/en/messages.py` names the group, the command and the unnamed test module.
- `tests/roadmap/test_roadmap_stage_form.py` covers an unnamed module, a module named in `reads`, `changes` and `creates`, and a command that runs no test module.
- The staged plans that the golden set and the sample builder give keep a `verify` command that names a module of their own group.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A verify command runs a test that its group names

## Impact

- Code: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_form.py`, `tests/support/builders.py`, `tests/roadmap/test_roadmap_stage_plan.py`

## Feasibility

- `search_code` for `_is_test_module` showed the helper in `src/devops_cli/roadmap/stage_form.py`, and the probe `_is_test_module` lists `src/devops_cli/roadmap/stage_form.py` as its one caller, so the rule has one definition to reuse.
- `read_file` of `src/devops_cli/roadmap/stage_form.py` showed `form_problems` calling `_verify_problems(number, group.verify)` and reading `group.creates` in the same loop, so the group's own paths are already at hand.
- The probe output says `The path `src/devops_cli/roadmap/stage_form.py` is a file of the staging commit.` and `The path `tests/roadmap/test_roadmap_stage_form.py` is a file of the staging commit.`, so both cited paths exist at this commit.
- The probe output says `The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit.`, so the message catalog that the issue cites exists.
- `read_file` of `tests/roadmap/test_roadmap_stage_task_verification.py` showed that the module builds a `StageGroup`, renders `tasks.md` and parses it, and loads no prompt, which confirms the evidence of the issue.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails before the change and passes after it, and `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` still passes, because the new rule judges only the `verify` command of a group.

## Existing Tool Considered

No open, maintained tool checks that the test a plan's command runs exercises the file that the plan changes. The rule extends `form_problems`, which already parses every `verify` command of a plan. Written cost: about 3,000 tokens to build, about 1,000 tokens per year to keep and fix, and about 2 hours elapsed.

## Dependencies

None.
