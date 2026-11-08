# Change: Add Argo workflow to keep RAG index current (#1653)

## Why
The RAG index of managed repositories' default branches goes stale because no cluster job runs the ingestion pass on a schedule. Issue #1653 delivers an Argo WorkflowTemplate and CronWorkflow to run the ingestion pass from #1389 on a schedule matching the roadmap service poll interval, with single-run concurrency via mutex, zero-trust network perimeter scoping to Qdrant, bounded embedding concurrency, and a lag alert to detect staleness.

This change fits in one pull request.

## What Changes
- Adds Argo WorkflowTemplate `k8s/devops/workflowtemplate-rag-ingest.yaml` running `devops ai rag ingest` in the Service image under global mutex `rag-ingest`, with embedding concurrency set to 1 and Qdrant credentials mounted from dedicated Secret `qdrant-api-key`.
- Adds Argo CronWorkflow `k8s/devops/cronworkflow-rag-ingest.yaml` running on schedule `*/3 * * * *` matching `service.poll_interval_seconds` (151s) with `concurrencyPolicy: Forbid`.
- Adds NetworkPolicy `k8s/devops/networkpolicy-rag-ingest.yaml` allowing egress only from ingest pods to Qdrant on TCP port 6333 in namespace `llm`, and updates `k8s/llm/networkpolicy.yaml` with matching ingress rule admitting ingest pods on port 6333.
- Adds cluster secret definition for `devops/qdrant-api-key` in `src/devops_cli/k8s/cluster_secrets.py`.
- Updates `MANIFESTS_BY_STACK` and `POST_HELM_BY_STACK` in `src/devops_cli/commands/k8s/stack_lifecycle.py` to deploy the NetworkPolicy, WorkflowTemplate, and CronWorkflow under stack `devops`.
- Adds `RAG_INGEST_LAST_SUCCESS_TIMESTAMP` instrument in `src/devops_cli/telemetry/instruments.py` and emits freshness gauge on successful repository ingestion in `src/devops_cli/ai/rag/ingest.py`.
- Adds `RagIngestBehind` Prometheus alert in `k8s/monitoring/prometheus-values.yaml` alerting when freshness lag exceeds two schedule periods (360 seconds).
- Updates `k8s/devops/kustomization.yaml` and adds comprehensive offline unit and integration tests.

## Feasibility
Confirmed against the running system:
- Argo Workflows CRDs (`argoproj.io/v1alpha1`) support `WorkflowTemplate` with `synchronization.mutex` and `CronWorkflow` with `concurrencyPolicy: Forbid` (verified via `kubectl kustomize k8s/argo-workflows`).
- Ingestion command `devops ai rag ingest` exists and executes in the service image (#1389).
- `DEFAULT_SERVICE_POLL_INTERVAL_SECONDS` is 151 seconds (`src/devops_cli/config/defaults.py:976`), for which `*/3 * * * *` (180s) is the shortest whole-minute cron period that is not shorter than the setting.
- Zero-trust network policies with namespace and pod selectors restrict TCP port 6333 access between namespace `devops` and `llm`.

## Existing Tool Considered
Argo Workflows covers the workflow orchestration need (Apache-2.0, CNCF-graduated). The alternatives check of 2026-11-01 recorded `not-applicable` and named no tool. A CronWorkflow with `concurrencyPolicy: Forbid` and WorkflowTemplate with `synchronization.mutex` provide the schedule, single-run lock, and overlap prevention without custom scheduling code. Internal obsolete code deleted: none.
