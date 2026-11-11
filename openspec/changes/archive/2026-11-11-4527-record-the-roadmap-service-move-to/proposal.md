# Proposal: Record the roadmap Service move to jobs and Valkey

## Why

Closes #4527. ADR 0008 plans the move of the roadmap jobs onto Argo Workflows after a go verdict. The owner recorded "warm p95 11 s - go" on #1535 on 2026-11-11. On the same day the owner asked to move as much Service work as possible to jobs, workflows and event-driven tools, with a central Valkey store for the shared data. No record holds that direction. ADR 0003, ADR 0009 and ADR 0017 still describe a Service that runs lanes and a poll timer. ADR 0017 names the model lane for scoped intake, but the code uses the triage lane, and it gives a poll of 151 seconds, but the live poll is 300 seconds.

## What Changes

- New ADR 0021. It records the go verdict with its numbers, the Service as a webhook router only, one pod for each unit of work, the sweep and the due marks, the engine parts, the plain stage Job as the first step, `valkey-roadmap` and the nine rules of its state, one request budget for all pods, the model limits that the owner set, the cold start, the order of the steps of tracker #4517, the rejected options and the consequences.
- ADR 0003, ADR 0008, ADR 0009 and ADR 0017 each get a one-line note "Amended on 2026-11-11 by ADR 0021" at the top. The note of ADR 0017 corrects its lane and poll lines. The old text of each record stays.
- `CONTEXT.md` defines "Unit of work", "Sweep" and "Due mark".
- No spec delta (`skip_specs: true`): the change adds documents only and changes no behavior that a consumer sees. Each step of tracker #4517 adds its own spec delta.

## Capabilities

None.

## Impact

- No behavior change. This pull request applies nothing to the cluster, the ConfigMap or a Secret.
- The alternatives check reads the ADRs in force under a cap of 8,192 tokens. With ADR 0021 and the four notes, the ADRs in force use 7,000 tokens, so the check leaves no ADR out.
- The change fits one pull request.

## Feasibility

- The go verdict is the comment "warm p95 11 s - go" of 2026-11-11 on #1535, read through `devops gh api`. The measurement comment above it gives the numbers: warm p95 11 s, cold run 54 s, burst p95 24 s, no new 429 or 5xx answer, 0 of 40 submissions failed, 56 to 78 API-server requests for each Workflow.
- The lane premise was read in `src/devops_cli/roadmap/run.py`: `_SCOPED_INTAKE` uses `lane=CONST_SERVICE_LANE_TRIAGE`. The poll premise: `DEFAULT_SERVICE_POLL_INTERVAL_SECONDS` is 151 in `src/devops_cli/config/defaults.py`, and the live ConfigMap `devops-cli-config` sets `poll_interval_seconds: 300` (a read with `kubectl get configmap`).
- The managed namespace premise was read in the upstream page https://argo-workflows.readthedocs.io/en/latest/managed-namespace/: the controller takes `--namespaced` and `--managed-namespace <namespace>`.
- The `Strict` premise was read in https://argo-workflows.readthedocs.io/en/latest/workflow-restrictions/: under `Secure`, "If a running Workflow's underlying WorkflowTemplate changes, the Workflow will error out".
- The `schedules` premise was read in https://argo-workflows.readthedocs.io/en/latest/upgrading/: v4.0 removed "`schedule` in CronWorkflows".
- The owner decisions of 2026-11-11 on tracker #4517 give the model limits (one stage Job before the engine; then `agent` = 2 and `triage` = 2), the generated Valkey passwords and the removal of the Mattermost `/roadmap` command.

## Existing Tool Considered

The ADR form of `docs/adr/` and the glossary form of `CONTEXT.md`. No build. The decisions that the record makes each name their open tool: Argo Workflows, Kubernetes Jobs, Valkey with valkey-py, the `limits` library and the uv Docker layer pattern. This change deletes no code.
