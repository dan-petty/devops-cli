# Proposal

## Why

Issue #3155: the owner set the live Service config on 2026-11-02 to plan with `deepseek-v4.1-flash-1017` (`ai.tasks.analysis.model`) and to review with `claude-sonnet-5-5` (`ai.tasks.verification.model`). The example in the repository still names `devops-background`, and no document says which model each stage uses or why.

## Feasibility

- The live ConfigMap `devops-cli-config` in namespace `devops` was patched with `kubectl patch`; its data equals the new config, and `deployment/roadmap-service` restarted and is ready. A call to each group from inside the Service pod answers (`deepseek-v4.1-flash-1017` costs 4.3e-06 USD, `claude-sonnet-5-5` 7.6e-05 USD for one word).
- `Settings.model_validate` accepts the new config: `ai.for_task("analysis")` gives `deepseek-v4.1-flash-1017` and `ai.for_task("verification")` gives `claude-sonnet-5-5`.
- `git grep -n 'for_task("verification")' -- src/devops_cli/roadmap` prints nothing: no roadmap code reads the slot yet (#3153).
- The evaluation behind the choice: `.data/agent/scratch/model-eval/` on the golden set of `tests/fixtures/roadmap_eval/stage`.

## Existing Tool Considered

The settings model already validates `ai.tasks.<task>.model`. No new tool.

## What Changes

- `k8s/devops/configmap.example.yaml`: `analysis` is `deepseek-v4.1-flash-1017` and `verification` is `claude-sonnet-5-5`.
- `k8s/README.md` (Roadmap service) gets item 19: the slot of each stage, the evaluation numbers, and how to change the ConfigMap.
- Tests: the example config test holds the two names, and a new gateway test holds every model of the example config against the groups of the gateway.
- The change has no spec delta: no `devops` command, option or message changes.

## Impact

- Documentation and tests only. The cluster already runs the config.
