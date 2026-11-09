# Proposal: #3258

## Why

Two kinds of facts are not in the stage planner's context: the failure taxonomy and runner pod capabilities. A plan that changes retry, review, or stop behavior must state how failures are classed. A plan whose feature needs a tool or privilege that the runner pod lacks is not caught by the staging gates. This change adds failure taxonomy and runner capability facts to the staging context, instructs the planner to state needed capabilities in Feasibility, and refuses plans that add unsupported commands or verify programs. Closes #3258.

## What Changes

- Add failure taxonomy facts (`FailureClass`, `FailureAction`, and `ACTION_BY_CLASS` rules from `src/devops_cli/roadmap/failure.py`) to staging context when the plan cites retry, review, stop, tier, or failure words.
- Add runner capability facts (image tools from `Dockerfile` and `RUNNER_TOOLS`, `NOT_IN_RUNNER` entries from `runner_tools.py`, and pod security settings from `k8s/devops/cronjob-runner.yaml`) to staging context when the plan cites a command or tool name.
- Read all facts from repository files at the staged commit and fail when a source file is missing or moved.
- Update `src/devops_cli/ai/tasks/roadmap_stage_change.md` to instruct the planner to state each needed failure class and runner capability in `## Feasibility`.
- Add a staging gate check in `content_problems` that refuses a plan that adds `devops review` to the Job or has a task verify that runs a `NOT_IN_RUNNER` program without a Feasibility line that names its runner capability.
- Add replay case for PR #3183 to the golden set in `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/`.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: Adds failure taxonomy and runner capabilities to staging context, instructs planner on Feasibility, refuses unsupported Job commands and verify programs, and adds golden set replay case.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`.
- Fixtures: `tests/fixtures/roadmap_eval/stage/3183-the-implement-job-reviews-its-own/`.

## Feasibility

- `src/devops_cli/roadmap/failure.py` exists at the staging commit and defines `FailureClass`, `FailureAction`, and `ACTION_BY_CLASS`.
- `src/devops_cli/roadmap/runner_tools.py` exists at the staging commit and defines `RUNNER_TOOLS` and `NOT_IN_RUNNER`.
- `Dockerfile` exists at the root and specifies the runner image packages (`git`, `ca-certificates`, `curl`, `jq`).
- `k8s/devops/cronjob-runner.yaml` exists at the staging commit and defines the runner pod securityContext (`runAsNonRoot: true`, `seccompProfile: RuntimeDefault`) and container securityContext (`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities: drop ALL`).
- `content_problems` in `src/devops_cli/roadmap/stage/stage_change.py` is the gate evaluated by both the live planner and the golden set replay.

## Existing Tool Considered

No open tool covers this repository-specific staging context and gate logic. The change builds its own code at a cost of about 40k tokens and 2 days of elapsed time.
