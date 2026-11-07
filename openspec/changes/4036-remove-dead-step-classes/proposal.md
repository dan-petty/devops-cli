# Proposal

## Why

The step class `StepClass` has four members, and only two have a reader: `EDIT` (a group of a change) and `REPAIR` (the fix of a failed check). `PLAN` and `REVIEW` have none. The setting `roadmap.implement.ladder` and the example ConfigMap still list them. A person can change the tier of a dead class and nothing happens. #4036, part of #3027.

## What Changes

- Remove `PLAN` and `REVIEW` from `StepClass`, and `plan` and `review` from `CONST_ROADMAP_IMPLEMENT_STEP_CLASSES`. The default ladder follows the constant, so it holds `edit` and `repair`.
- Change the description of the setting `roadmap.implement.ladder` to name the two classes.
- Remove the keys `plan` and `review` from the ladder in `k8s/devops/configmap.example.yaml`.
- Change the tests in `tests/config/test_settings.py` that use the keys `plan` and `review`. A new test file, `tests/roadmap/implement/test_roadmap_implement_step_classes.py`, checks that `StepClass` has exactly `EDIT` and `REPAIR`, that the constant, the default ladder and the example ConfigMap hold exactly `edit` and `repair`, and that a ladder with the key `plan` or `review` is refused with a message.
- Change the requirement "The implement job runs on a hosted gateway group" of `roadmap-service-deployment`: "the four step classes" becomes "the two step classes". Add the requirement "The ladder names only the step classes that a step reads" to `roadmap-implement-step`. The setting and its refusal message are observable, so the change carries a spec delta.
- Regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` with `uv run devops docs generate --sync-readme`. Check the text about the step classes in `docs/roadmap/implement.md` and `k8s/README.md`.
- Rollout rule. The validator `_check_ladder` refuses a ladder key that is not a step class. The live ConfigMap `devops-cli-config` fails to load if it names `plan` or `review`. A person removes both keys from the live ConfigMap in the same deploy, and shows the diff first. An agent does not change the live ConfigMap. This change adds no shim.
- The change fits one pull request.
- Out of scope: a cap, a timeout, or a guard for a missing `context_window`. #3049 (open) adds the class `review` back when it builds the review step.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: the template ConfigMap holds a ladder for the two step classes.
- `roadmap-implement-step`: the ladder names only the step classes that a step reads.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`.
- Manifest: `k8s/devops/configmap.example.yaml`.
- Documents: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md` (generated), `docs/roadmap/implement.md`, `k8s/README.md`.
- Tests: `tests/roadmap/implement/test_roadmap_implement_step_classes.py`, `tests/config/test_settings.py`.

## Feasibility

The premise was checked at origin/main in the worktree of this change.

- `grep -rnE 'StepClass\.(PLAN|REVIEW)' src tests` finds no reader. `StepClass` is used only as the default `EDIT` of `run_step`, as `REPAIR` of the fix step, and in `_ladder_tiers`.
- Real system. `RoadmapImplementConfig(ladder={"bogus": ["devops-coder"]})` fails today with "the ladder names no step class bogus; use plan, edit, repair, review". So the validator reads `CONST_ROADMAP_IMPLEMENT_STEP_CLASSES`, and removing the two names makes it refuse `plan` and `review` with no new code.
- No merged change or newer ADR did this work. #3049 (open, the review step) and #3569 (open, another change) do not conflict. #3060 (the ladder) is closed.
- The new tests fail on origin/main for the right reason: `StepClass` has four members, the constant has four names, and a ladder with the key `plan` is accepted.
- The live ConfigMap was not read. The rollout rule covers both cases.

## Existing Tool Considered

None needed. The change removes code. It deletes the members `PLAN` and `REVIEW`, the constant names `plan` and `review`, and the two ConfigMap lines.
