# Proposal

## Why

A plan can order the removal of an old test, but the step guard refuses each lost test, so such a plan can never pass (#3490). #2519 stopped two times on a test that its plan orders the step to delete, with 4,516,206 input tokens. Each stop read `tests_lost` with the action `retry`, so a new runner image starts the same step again, and a retry cannot help.

## What Changes

- `read_change` reads the `## Weakened checks` section of `proposal.md` into `StageProposal.weakened_checks`. Each entry holds `check`, `stopped` and `safeguard`, the fields that the plan of #3320 names. The reader refuses an entry in another form with `PlanReadError`.
- This change owns the reader, the model and the form of an entry. #3320 keeps the reply key, the writer and the gate, and its plan changes to say so. The reply schema does not show the field until the writer of #3320 exists, because the stage job would lose a key that it cannot write.
- The step guard allows a lost test when the plan on the default branch names it as `path::name` in the `check` of an entry. It refuses any other lost test. The job reads the record from `origin/<default>`, never from the checkout, which the agent can edit.
- The class `tests_lost` takes the action `wait`, so the rule `digest` does not retry it. The change adds no new class.
- The step prompt and the reason of the stop say the same as the guard.
- The eval property `tests_kept` reads the same record: `load_case` adds the tests of the plan to `allow_lost_tests`, and the eval run gives that list to the step. A hunk shows no class, so `tests_kept` reads an entry `path::Class.test_x` as `test_x`.
- The plans of #2519, #2592, #2610 and #2636 get an entry for each test that they remove, rename or move. An entry names a test of a class as `path::Class.test_x`, the name that the guard reads. An invariant over the change folders fails an entry that names such a test with no class or with another class.
- A consumer observes the guard, the stop comment and the plan reader, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A step keeps each test that the merged plan does not record.
- `roadmap-implement-job`: The job gives the step the record of the plan on the default branch.
- `roadmap-failure-taxonomy`: The class `tests_lost` waits for a person.
- `roadmap-eval-implement`: `tests_kept` reads the record of the plan.
- `roadmap-plan-check`: The plan reader reads the weakened checks of a plan.

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_test_names.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/implement_eval.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/roadmap/implement_eval_properties.py`, `src/devops_cli/lang/en/messages.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`
- Plans: `openspec/changes/2519-the-claim-table-of-the-local/proposal.md`, `openspec/changes/2592-devops-ai-gateway-tune-recommends-weights/proposal.md`, `openspec/changes/2610-devops-k8s-image-pins-resolves-with/proposal.md`, `openspec/changes/2636-a-result-that-no-lookup-marked/proposal.md`, `openspec/changes/3320-a-plan-that-deletes-a-guard/proposal.md`, `openspec/changes/3320-a-plan-that-deletes-a-guard/tasks.md`, `openspec/changes/3320-a-plan-that-deletes-a-guard/design.md`, `openspec/changes/3328-the-stage-probe-checks-prompt-reply/proposal.md`, `openspec/changes/3328-the-stage-probe-checks-prompt-reply/design.md` (the plans of #3320 and #3328 quote the assertion on `StageProposal.model_fields`, which this change turns into the properties of the schema)

## Feasibility

Checked against `origin/main` at `05544abc`.

- `git grep -n "weakened_checks\|WeakenedCheck" origin/main -- src tests` prints nothing, so the list of #3320 is a plan and not code. `openspec/changes/3320-a-plan-that-deletes-a-guard/` holds that plan. It names the fields `check`, `stopped` and `safeguard`, and the section `## Weakened checks` between `## Impact` and `## Feasibility`. It gives no form for the line of an entry, so this change sets the form and the plan of #3320 uses it.
- #3320 stopped at group 1 on 2026-11-05 with the class `plan_defect`: no group of its plan reads the section back, and `read_change` builds `StageProposal` with no such field. So the reader must exist for #3320 to pass, and this change does not wait for #3320.
- A probe with pydantic 2.13.5 shows that `SkipJsonSchema[list[str]]` on a field leaves the field out of `model_json_schema()`, and that the model still accepts a value for the field. So `read_change` can fill the field and the reply schema does not change.
- `_tests_failure` in `src/devops_cli/roadmap/implement_step.py` reads `lost_since` and stops for each lost test, and `_unkeepable` calls it for each `wip:` commit.
- `_hooks_config` in `src/devops_cli/roadmap/implement_run.py` reads the hooks from `origin/<default>` because the agent can edit the file of the checkout (#3043). The record has the same risk: an agent that adds an entry to the `proposal.md` of the checkout must not waive a test. A later step starts from the `wip:` commits of the branch, so a read at the start of a step does not solve this.
- `stop_clear.py` clears a stop by digest only when `ACTION_BY_CLASS` gives the class the action `retry`, so the action `wait` stops that rule with no change to the rule.
- `lost_since` reports a moved test under its old path, and `git diff --no-renames` treats a move as a delete and an add, so an entry that names the old `path::name` covers a rename and a move.
- `git grep` finds a test by its bare name, but the guard compares the qualified name that `defined_tests` gives (`Class.test_x`). So each entry was checked with `recorded_tests` against `defined_tests` of its file at `origin/main`. The first version of the entries of #2592 named five tests of `class TestTune` with no class, which the probe found missing, and the entries now carry `TestTune.`. The probe also found two tests that tasks of the plans rename or move and that the entries did not name: `test_ai_gateway_weights_refuses_scalar_string_in_config_set` (task 4.2 of #2592) and `test_an_image_reference_splits_as_the_docker_sdk_splits_it` (task 1.1 of #2610). Both have an entry now. `tests/invariants/test_change_folders.py` keeps the probe: it fails an entry that names a test of a class with no class or with another class.

## Existing Tool Considered

No open tool reads the plan of this repository. The change reuses project code: `lost_since`, `read_change`, `change_root`, `files_at`, `tree_files`, and the standard library `re`. It adds no dependency. To build it costs about 60k tokens to write, about 5k tokens a month to keep and fix, and about 3 hours of elapsed time. The change deletes no internal code.
