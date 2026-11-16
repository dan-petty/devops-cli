# Tasks

## 1. Each job has a task of its own in the settings (behavior)

- [x] 1.1 Write the failing tests: a model set only for `refine` reaches `refine` and leaves `ai.model` to every other job task; `stage` takes nothing from `analysis`; a variable sets the model and the window of each job task; the old tasks still load.
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_job_tasks.py tests/config/test_ai_task_settings_paths.py`
- [x] 1.2 Add the job tasks to `AITasksConfig` with the variables of `stage`, and remove `_TASK_PARENTS` and the parent branch of `AIConfig.for_task`. Delete `tests/config/test_stage_task_setting.py`, whose tests the new file replaces.
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_job_tasks.py tests/config/test_ai_task_settings_paths.py`

## 2. Each job and each eval of a job reads its own task (behavior)

- [x] 2.1 Write the failing tests: the consolidation judge asks for `consolidate`, intake for `intake`, retitle for `retitle`, the review of refine for `refine_review`, the refine investigation and the alternatives check read the window of their own task, the stage command asks for `stage` and `stage_review`, `fix-plan` asks for `fix_plan` and reads the windows of `fix_plan` and `fix_plan_review`, and the window error of a run names the setting of its task.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_judge.py tests/roadmap/intake/test_roadmap_intake_model_reply.py tests/roadmap/test_roadmap_retitle.py tests/roadmap/refine/test_roadmap_refine_trust.py tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/stage/test_roadmap_stage_command.py tests/roadmap/steps/test_roadmap_fix_plan.py tests/roadmap/stage/test_roadmap_stage_toolbox.py`
- [x] 2.2 Change each reader to its own task: intake, retitle, refine, the alternatives check, the consolidation judge, the stage job, `fix-plan`, the group splitter of the implement job and the eval commands. Remove `analysis_window`. Pass the task to the `ToolboxClient` of a run and name it in the window errors.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_judge.py tests/roadmap/intake/test_roadmap_intake_model_reply.py tests/roadmap/test_roadmap_retitle.py tests/roadmap/refine/test_roadmap_refine_trust.py tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/stage/test_roadmap_stage_command.py tests/roadmap/steps/test_roadmap_fix_plan.py tests/roadmap/stage/test_roadmap_stage_toolbox.py`

## 3. The ConfigMap template names a model for each job (manifests)

- [x] 3.1 Give each job task of `k8s/devops/configmap.example.yaml` its own entry, and remove the entries `analysis`, `verification` and `triage`. Change the tests that read the template.
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/k8s/test_k8s_configmap.py tests/roadmap/stage/test_roadmap_stage_window.py tests/roadmap/test_roadmap_limit_classes.py tests/ai/spend/test_hosted_group_prices.py`

## 4. Documents

- [x] 4.1 Regenerate the generated documents, and change the pages that state the old shared tasks: `docs/roadmap/stage.md`, `docs/roadmap/refine.md`, `docs/roadmap/intake.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md`, `docs/SELF_IMPROVEMENT.md`, `SECURITY.md` and `config.example.yaml`.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: after the image rolls out, add the job tasks to the live ConfigMap `devops-cli-config`, as the proposal lists them under Impact.
