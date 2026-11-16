# Proposal: #5583

## Why

`devops k8s deploy-stack --stack devops` renders ConfigMap `devops-cli-config` from `k8s/devops/configmap.example.yaml`. A value that only the live ConfigMap holds is lost at the next deploy. The owner chose twice the default attempt limits of the stage, implement and fix-plan jobs on 2026-11-13, and an agent set them with `kubectl patch`. A deploy between 2026-11-14 02:00Z and 2026-11-15 23:00Z removed them, and the jobs ran on the defaults after it. The owner asked for the higher limits again on 2026-11-16. The two model changes of `ai.tasks.triage` (2026-11-15) and `ai.tasks.analysis` (2026-11-16) are also only in the live ConfigMap. Closes #5583.

## What Changes

- `k8s/devops/configmap.example.yaml` sets the doubled attempt limits of `roadmap.stage` (7 keys), `roadmap.implement` (19 keys) and `roadmap.fix_plan` (3 keys). The item time of implement stays at the 14400 s ceiling of the Job deadline.
- The template names `local/qwen3.8:27b` for `ai.tasks.triage` and `ai.tasks.analysis`, and keeps the prefixed names of the other slots.
- Tests read the limits and the slot models from the template. The planner tests read the task `stage`, not `analysis`.
- `docs/CLUSTER.md` and the comments of the template state the new slot models.

## Capabilities

- `roadmap-service-deployment`: the requirement on the chat slots changes, and one requirement on the attempt limits is added.

## Impact

- The next deploy-stack keeps the limits and the slot models that the live ConfigMap holds now.
- The `backlog_*` keys, `roadmap.stage.jobs` and `service.github_requests_per_hour` do not change.

## Feasibility

- The edited template validates as `Settings`: the limits load, `stage` keeps its own DeepSeek entry, and `triage` and `analysis` read `local/qwen3.8:27b`.
- Both Ollama backends of `qwen3.8:27b` run `OLLAMA_CONTEXT_LENGTH=262144`, above the `context_window` 256000 of `analysis`.

## Existing Tool Considered

The template and deploy-stack are the existing tools for the live config. The change edits values only.
