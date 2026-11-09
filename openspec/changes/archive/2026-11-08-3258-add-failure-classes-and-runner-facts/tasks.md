# Tasks

## 1. Add failure taxonomy and runner capabilities to staging context

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/runner_tools.py`, `k8s/devops/cronjob-runner.yaml`, `Dockerfile`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_context.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_context.py`, assert that an item citing `retry` gets the failure class table and `ACTION_BY_CLASS` rules in context, an item citing a command gets the runner image tools, `NOT_IN_RUNNER` entries and pod security settings, and moving `failure.py`, `runner_tools.py`, or `k8s/devops/cronjob-runner.yaml` fails and names the moved source. Verify that `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_context.py` fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_context.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage.py`, add helpers to read the failure taxonomy and runner capabilities from repository files at the staged commit when keywords trigger them, fail when a source file is missing or moved, and append the sections to `StageRequest.context`. Verify that `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_context.py` passes
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_context.py` passes

## 2. Instruct the planner on Feasibility capabilities

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 2.1 In `src/devops_cli/ai/tasks/roadmap_stage_change.md`, instruct the planner to state needed failure classes and runner capabilities in `## Feasibility`. Assert the rule in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 3. Refuse unsupported Job commands and verify programs in the staging gate

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`.

- [x] 3.1 In `tests/roadmap/stage/test_roadmap_stage_content.py`, assert that a plan adding `devops review` to the Job without a Feasibility line naming a review tool from `NOT_IN_RUNNER` is refused, a task verify running `helm template` without Feasibility capability is refused, a medium-effort plan with a verify running `docker build` without Feasibility capability is refused, and valid Feasibility lines pass. Verify that `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` fails on the base
- [x] 3.2 In `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/lang/en/messages.py`, add runner capability checks to `content_problems`. Add self-acceptance test in `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`. Verify that `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_self_acceptance.py` passes
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_self_acceptance.py` passes

## 4. Add golden set replay case for PR #3183

Reads: `tests/fixtures/roadmap_eval/stage/`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/case.json`, `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/facts.json`, `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/issue.txt`, `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/plan.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [x] 4.1 Add fixture folder `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/` with `case.json`, `facts.json`, `issue.txt`, and `plan.json`. Add 3183 to `EVALUATED_PULLS` in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Verify that `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
