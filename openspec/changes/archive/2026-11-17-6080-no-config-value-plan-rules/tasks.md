# Tasks

## 1. A workflow change needs no test (behavior)

- [x] 1.1 Write the failing test `test_a_workflow_change_needs_no_test_because_actionlint_and_zizmor_check_it` in `tests/roadmap/stage/test_roadmap_stage_paths.py`, in place of the four tests of the contract rule
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py`
- [x] 1.2 Delete `workflow_contract_problems`, `WORKFLOW_CONTRACT_TEST` and `WORKFLOW_DIRECTORY` from `src/devops_cli/roadmap/stage/stage_paths.py` and the message `stage_problem_workflow_contract`, and drop the contract test from the helper `_changing` of `tests/roadmap/stage/test_roadmap_stage_plan.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py tests/roadmap/stage/test_roadmap_stage_plan.py`

## 2. A scenario of a changed manifest, workflow or config file names its proof command (behavior)

- [x] 2.1 Write the failing tests in `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`: a scenario of a changed manifest, workflow or root config file with no command is refused; a behavior test that names the manifest and a command that runs tests are no proof; a validator command or a live check proves it; a base scenario is exempt; a changed Markdown document keeps the rule of code
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`
- [x] 2.2 Add `_changed_config_paths`, `_runs_tests` and `_config_scenario_problem` to `src/devops_cli/roadmap/stage/stage_change.py`, call them from `_scenario_problems`, and add the message `stage_scenario_config_proof`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`

## 3. A new test module sits in the mirror of its source code (behavior)

- [x] 3.1 Write the failing tests in `tests/roadmap/stage/test_roadmap_stage_form.py`: a new test module in `tests/invariants/` is refused for a plan that changes source code and for one that changes none
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py`
- [x] 3.2 Drop the exemption of `tests/invariants/` from `form_problems` in `src/devops_cli/roadmap/stage/stage_form.py`, and add the message `stage_test_path_mirror` for a plan that changes no source file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py`

## 4. The plan rules name a command proof (behavior)

- [x] 4.1 Write the failing tests: the stage prompt, `openspec/config.yaml` and `docs/TESTING.md` keep the phrase "names a validator command or a live check as its proof" (`tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`), and the refine reply prompt keeps it too (`tests/roadmap/refine/test_roadmap_refine_proposal.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/refine/test_roadmap_refine_proposal.py`
- [x] 4.2 Write the proof form into `openspec/config.yaml`, `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_refine_reply.md`, and drop `tests/invariants/` as a place for a new test module from the stage prompt
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/refine/test_roadmap_refine_proposal.py tests/roadmap/stage/test_roadmap_stage_form.py`
- [x] 4.3 Name `uv run devops ci --check --only k8s` as the proof of the dashboard scenario of the golden case `good-2950-the-alert-case-is-a-manifest-group`, and replay the golden set: 6 of 6 good plans pass and 85 of 85 known defects are caught, before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/`

## 5. Documents

- [x] 5.1 State the proof form, the rule of `tests/invariants/`, and that the coverage floor, diff-cover and Fail-to-Pass ask for no test of a manifest or a config value in `docs/TESTING.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #6090: a `devops ci` row that runs the Renovate config validator, the proof of a change of the Renovate config.
- #6083: rewrite the scenarios of the living specs that read a manifest, in the proof form of this change.
- Pending a person: run the live score of the stage prompt, `uv run devops roadmap eval stage --limit <n>`, before and after this change. The worktree guard of the agent session refused the command, because its text holds the word `eval`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
