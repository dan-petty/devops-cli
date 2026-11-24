# Proposal: #5129

## Why
`devops infra drift` (#5127) and `devops infra plan` (#5124) run only on a workstation. No schedule runs drift in the cluster. An infra pull request shows no plan before review. ADR 0021 moves Service work to cluster Jobs and Argo Workflows. This change closes #5129 by running drift on a schedule and planning infra pull requests.

## What Changes
- Add `--all` to `devops infra drift` to run drift for each repo in `infra.repos` with access level `plan` or higher.
- Add WorkflowTemplate `infra-drift` and daily CronWorkflow `infra-drift` in namespace `devops`.
- Add `ansible-runner` to `RUNNER_TOOLS` with a `job:` reason.
- Add NetworkPolicy `infra-ssh-egress` admitting TCP 22 to node CIDR ranges for pods with component `infra`.
- Mount Secret `infra-ssh-key` read-only for SSH credentials in the runner pod.
- Update the webhook router to launch an `infra-plan` Job on `pull_request` `synchronize` for infra repos.
- Add step `infra-plan` to post and update a single marked plan comment on infra pull requests.
- This change fits in one pull request.

## Capabilities
- Run scheduled drift checks for all eligible infrastructure repositories in the cluster.
- Automatically generate and update execution plans on infrastructure pull requests.
- Enforce network egress boundaries for cluster infrastructure jobs.

## Impact
- Automated daily drift reporting for infrastructure repositories.
- Faster pull request reviews through automated check-mode plan comments.
- No breaking changes to existing workstation commands.

## Feasibility
- Argo Workflows CronWorkflow and WorkflowTemplate patterns exist in `k8s/devops/cronworkflow-rag-ingest.yaml`.
- The webhook router and `job_launcher` seam exist in `src/devops_cli/server/routes/webhooks.py` and `job_launcher.py`.
- NetworkPolicy patterns and invariants exist in `k8s/devops/networkpolicy.yaml` and tests.

## Existing Tool Considered
- Tool: `argoproj/argo-workflows` (https://github.com/argoproj/argo-workflows), Apache-2.0, in-use.
- Reason: Argo Workflows provides scheduling and pod templates, but lacks the repository access level loop, marked plan comment updates, and SSH egress policy glue.
- Cost to build: about 4M tokens and 6 hours.
