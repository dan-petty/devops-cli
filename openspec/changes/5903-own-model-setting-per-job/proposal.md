# Proposal: #5903

## Why
The roadmap jobs read shared task slots of `ai.tasks` (#5903). The slot `analysis` serves refine, the alternatives check, the consolidation judge and the group splitter of the implement job. The slot `verification` serves the review of refine, the review of the stage job and the review of `fix-plan`. The slot `triage` serves intake and retitle. The repair of `fix-plan` reads the slot `stage`, and `_TASK_PARENTS` gives the task `stage` each field that it does not set from `analysis`. So a model trial of one job also moves other jobs. On 2026-11-16 the owner asked for a trial of refine and alternatives on `local/qwen3.8:27b`, and the only setting moved the consolidation judge too. The owner direction of 2026-11-16 is that each job has a model setting of its own, so that a trial moves exactly one job.

## What Changes
- `AITasksConfig` gets one task for each model role of a roadmap job: `intake`, `retitle`, `refine`, `refine_review`, `alternatives`, `consolidate`, `stage_review`, `fix_plan`, `fix_plan_review` and `implement_split`. The tasks `stage` and `implement` stay. A job and each eval command of a job read only their own task.
- A field that a task does not set takes the value of `ai`. `_TASK_PARENTS` goes, so `stage` takes nothing from `analysis`.
- The tasks `analysis`, `verification` and `triage` stay for the commands that are not roadmap jobs, such as `devops review`, so an existing config file stays valid. No roadmap job reads them.
- Each new task has the variables `DEVOPS_CLI_AI_TASK_<TASK>_PROVIDER`, `_MODEL`, `_REASONING_EFFORT`, `_OLLAMA_URLS`, `_CONTEXT_WINDOW` and `_MAX_TOKENS`, as `stage` has.
- The error of a run whose window ends its tools too soon names the setting of the task of that run.
- `k8s/devops/configmap.example.yaml` names a model for each job task: DeepSeek with `context_window` 256000, and `local/qwen3.8:27b` for `intake` and `retitle` (owner decision of 2026-11-15). It sets no `analysis`, `verification` or `triage` entry, because no job of the Service reads them.
- The settings, the messages and the ConfigMap template are observable, so the change carries spec deltas.

## Capabilities
- `ai-task-models`: each roadmap job reads a task of its own, with no parent task.
- `roadmap-intake-jev`, `roadmap-intake-duplicates`: intake and its evals read `intake`.
- `roadmap-refine/review`, `roadmap-refine/investigation`, `roadmap-refine/context`: refine reads `refine` and `refine_review`.
- `roadmap-alternatives`: the check reads `alternatives`.
- `roadmap-consolidate-plan`: the judge reads `consolidate`.
- `roadmap-stage/verification`, `roadmap-stage/run-limits`, `roadmap-stage-eval`: the stage review reads `stage_review`, and the planner reads only `stage`.
- `roadmap-service-deployment`, `roadmap-job-limits`: the template names a model for each job.

## Impact
- The image that reads the new tasks must roll out before the live ConfigMap holds them, because `AITasksConfig` refuses an unknown key. Until a person adds the new keys to the live ConfigMap, each job uses `ai.model` and `ai.context_window`.
- The live keys that keep the current models: `refine`, `alternatives`, `consolidate` and `implement_split` with `local/qwen3.8:27b` and `context_window` 256000 (the live `analysis`), `intake` and `retitle` with `local/qwen3.8:27b` (the live `triage`), and `fix_plan` with `openrouter/deepseek/deepseek-v4.1-flash-1017` and `context_window` 256000 (the live `stage`). The reviews had no live `verification` entry, so they need no key.
- The change fits one pull request.

## Feasibility
`git grep -n -E 'for_task\(|get_task_model\(|get_llm_client\(task=|task_window\('` on origin/main at 0.159.0 lists each reader. `AIConfig.for_task` applies `ai.tasks.<task>` over `ai`, and `getattr(self.tasks, task, AITaskOverride())` already gives `ai` to a task with no field. `AITasksConfig` is `extra="forbid"`. The variables come from `Variable(fields=...)` in `config/env.py`, as for `stage`.

## Existing Tool Considered
The settings are pydantic models, and the variables come from the existing `Variable` metadata, so the change adds fields and no tool. The change deletes `_TASK_PARENTS`, the parent branch of `AIConfig.for_task`, and `analysis_window` of `refine_investigation.py`.
