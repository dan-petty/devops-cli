# Proposal

## Why

Issue #2494: `k8s/devops/roadmap-service/deployment.yaml` held the Service at `replicas: 0`, and its comment said to keep it there until a separate item moved the roadmap state to labels and milestones. #2399 delivered that item. The App `devops-cli-service` is installed, and its key is in Secret `devops/devops-cli`. Argo CD self-heals the deployment, so only a change in git can start the Service.

The ConfigMap template `k8s/devops/configmap.example.yaml` sends each generation call of the Service and of the cluster Jobs to `devops-background`, which serves one request at a time, and each embedding call to `qwen3-embedding:0.6b`, but sets no retry count. With the default `ai.max_retries` of 4, a call can be sent 5 times. `k8s/README.md` (LLM Gateway) tells background work to retry once.

## What Changes

- `deployment/roadmap-service` sets `replicas: 1`. Its comment names the identity the Service acts as (GitHub App `devops-cli-service`, ADR 0015) and points to the stop switch in `k8s/README.md`.
- The ConfigMap template sets `ai.max_retries: 1`. The render that deploy-stack does replaces only the `service` section, so the value gets to the cluster when deploy-stack runs. Argo CD does not apply the ConfigMap.
- `k8s/README.md`, "Roadmap service", replaces the note that held the Service at `replicas: 0` with a go-live check (a deploy-stack run, a read of the live retry count and a restart of the pod, then the pod, the scrape, a test delivery, the first hour inside the request budget) and a stop switch (suspend the installation, turn off automated sync from `bootstrap` down to `devops`, scale to 0, delete the running Jobs, turn off the hooks). "LLM Gateway" says that the template sets the retry count for the in-cluster services, and that deploy-stack applies it. The install check of "Argo Workflows" no longer says that `roadmap-service` is at 0 replicas.
- A manifest is observable, so the change has a spec delta: the new capability `roadmap-service-deployment`.
- The change fits one pull request.

## Feasibility

- `git show origin/main:k8s/devops/roadmap-service/deployment.yaml` at 0c2cba63 holds `replicas: 0` and the comment that waits on the labels item. The change of #2399 is archived (`openspec/changes/archive/2026-10-28-2399-roadmap-labels`), and ADR 0016 records it.
- `render_devops_configmap_content` (`src/devops_cli/k8s/configmap.py`) replaces only `service` and validates the whole config with `Settings`. `AISettings.max_retries` (`src/devops_cli/config/settings.py`) is an integer, 0 or more, with the default `DEFAULT_AI_MAX_RETRIES` = 4. The client sends `max(1, retries + 1)` attempts (`src/devops_cli/ai/client/unified.py`), so 1 gives 2 attempts.
- `kubectl kustomize k8s/devops` renders no ConfigMap: `k8s/devops/kustomization.yaml` does not list `configmap.example.yaml`, so Argo CD does not apply `devops-cli-config`. On a cluster that Argo CD manages, deploy-stack applies the ConfigMap and returns before it restarts `roadmap-service` (`_handle_argo_managed_deployment` in `src/devops_cli/commands/k8s/stack_lifecycle.py`). Only the deploy to a cluster without Argo CD restarts it (`_post_deploy_credentials`).
- `k8s/argocd/apps/devops.yaml` sets `selfHeal: true`, and `cluster` and `bootstrap` are its parents (`k8s/README.md`, Pausing an Application). The repository pauses an Application with a merge patch of `spec.syncPolicy.automated.enabled: false` (`_pause_args` in `src/devops_cli/k8s/volume_move.py`).
- The scrape of the pod and the OTLP export both give the Service's series `job="roadmap-service"`, and the rule group `roadmap-service` (#2472) selects each series with that job (`k8s/README.md`, Alerts). The go-live check uses the same filter, so the series of a workstation (`job="devops-cli"`) do not count.
- The Service answers a signed ping with HTTP 200 and `{"status": "pong"}`, and counts it with `event="ping"` and `outcome="ignored"` (`_route` and `_Delivery.conclude` in `src/devops_cli/server/routes/webhooks.py`). The budget is `service.github_requests_per_hour`, 500 by default (`DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR`).
- The halt, the hourly budget and the failure ledger are in memory (`RequestBudget` in `src/devops_cli/server/service.py`; `FailureLedger` in `src/devops_cli/roadmap/run.py`), so a restart clears them.

## Existing Tool Considered

Argo CD's GitOps sync applies the replica count and the ConfigMap. Nothing is built, and no internal code is deleted.
