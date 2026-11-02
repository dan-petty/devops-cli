# Tasks

## 1. Refuse a spec delta that the changed paths do not need

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 Add a test in `tests/roadmap/test_roadmap_stage_plan.py` that a proposal with `skip_specs: false` and every `changes` path under `tests/`, `.github/workflows/`, `docs/` or `openspec/` gets the problem text, and that a proposal with a `src/` path gets none, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 Add the four prefixes and a helper in `src/devops_cli/roadmap/stage_change.py` that says whether every `changes` path of the groups is a non-spec path. Append the new problem in `check_proposal` when `skip_specs` is false and the helper is true. Add the message `stage_problem_specs_not_needed` to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Refuse an added requirement that the base spec already has

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add a test in `tests/roadmap/test_roadmap_stage_plan.py` that an ADDED requirement whose name is in the base spec of the capability gets the problem text, and that a new name gets none, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Read the requirement names of each base spec under `openspec/specs/<capability>/spec.md` where the stage job already lists the capabilities in `src/devops_cli/roadmap/stage.py`, and pass them to `check_proposal` beside `known`. Refuse an ADDED requirement whose name is in that set, with the message `stage_problem_duplicate_requirement` in `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Give the model the purpose and the requirement names of each capability

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 3.1 Add a test in `tests/roadmap/test_roadmap_stage_plan.py` that the model input holds the purpose and the requirement names of each capability, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 3.2 Build the capability list in `src/devops_cli/roadmap/stage.py` with the purpose and the requirement names of each base spec, and render it into the stage prompt. Tell the model in `src/devops_cli/ai/tasks/roadmap_stage_change.md` to set `skip_specs` from the changed paths and to avoid a requirement name that the list holds, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 4. Refuse the replay of the plan of #2977

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 4.1 Add the plan of #2977 to the replay cases with the `paths` gate and the problem text that the new rule gives, so the replay refuses it. Keep the case of a good plan that the gate accepts, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
