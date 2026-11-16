# Proposal: #5970

## Why

The owner rule of 2026-11-16 gives every job generous token limits while the jobs are not yet reliable. Implement runs used 23M to 26M of the 40M item budget before they stopped for other reasons, and #3464 stopped with `limit_reached` at 24.5M while the live budgets were halved. Closes #5970.

## What Changes

- `roadmap.implement.step_token_budget` 32,000,000 and `item_token_budget` 80,000,000 in `k8s/devops/configmap.example.yaml` (four times the defaults); the step ceiling stays two times the step budget.
- The template test and the requirement of the implement limits state the factor four for the two token budgets.

## Capabilities

- `roadmap-service-deployment`: the requirement on the implement limits changes.

## Impact

- A deploy-stack after the merge renders the budgets; the running image knows both keys. The time limits do not change.

## Feasibility

- Loki, 7 days to 2026-11-16: 3 `limit_reached` stops of implement; the token stop came during the halved budgets.

## Existing Tool Considered

The template and deploy-stack. The change edits two values.
