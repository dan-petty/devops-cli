# Proposal: #5933

## Why

The alternatives check ran a trial on `local/qwen3.8:27b` from 2026-11-16. From 02:40Z to 03:40Z it passed 8 of 20 runs, and 11 runs ended with `UnexpectedModelBehavior`: the local model answered with text and no structured reply. On DeepSeek no run ended that way in the two days before. The template comment of the trial names this stop rule. Closes #5933.

## What Changes

- `ai.tasks.alternatives` in `k8s/devops/configmap.example.yaml` names `openrouter/deepseek/deepseek-v4.1-flash-1017` with `context_window` 256000.
- The template tests and the requirement on the job models list only `intake` and `retitle` on the local model.

## Capabilities

- `roadmap-service-deployment`: the requirement on the model of each job changes.

## Impact

- After the merge, `devops k8s deploy-stack --stack devops` renders the change; the running image knows the key, so no image change is needed.

## Feasibility

- Loki on 2026-11-16: 11 `reason=UnexpectedModelBehavior` results of the job `alternatives` in 24 h, and 0 in each of the two days before.

## Existing Tool Considered

The template and deploy-stack are the tools for the live config. The change edits one value.
