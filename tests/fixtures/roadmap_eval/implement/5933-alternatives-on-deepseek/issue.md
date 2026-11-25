## Problem

The alternatives check runs on `local/qwen3.8:27b` in a trial of the owner of 2026-11-16 (`k8s/devops/configmap.example.yaml`, `ai.tasks.alternatives`). The trial meets its stop rule, which the template comment states: "Name DeepSeek again when the check passes less than 85% of 20 runs, or a structured reply fails".

- From 2026-11-16 02:40Z to 03:40Z, after the GitHub budget let the rounds run again, the check passed 8 of 20 runs.
- 11 runs ended with `reason=UnexpectedModelBehavior`: the local model answered with text and no structured reply. One more ended with `AIClientError`.
- In the two days before the trial, on DeepSeek, no run ended with `UnexpectedModelBehavior`, and the check passed 97% over 48 h.

Refine left the same trial on 2026-11-16 for the same failure (#5909).

## Expected behavior

`ai.tasks.alternatives` names `openrouter/deepseek/deepseek-v4.1-flash-1017` with `context_window` 256000 in the template, and `devops k8s deploy-stack --stack devops` renders it into the live ConfigMap. Intake and retitle stay on the local model.

## Related

- #5909 (a model setting for each job), #5583.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
