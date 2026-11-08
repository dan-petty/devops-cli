# Design: Argo workflow for RAG index scheduling (#1653)

## Context
Managed repositories indexed in Qdrant need periodic re-indexing when commits land on default branches. In-cluster jobs run in namespace `devops`. The roadmap Service runs with 0 replicas, and in-process background threads were removed in favor of Argo Workflows (#1535).

## Decisions
- **Argo Workflows as engine**: A CronWorkflow schedules execution and a WorkflowTemplate defines the job.
  - *Chosen*: Argo Workflows CronWorkflow and WorkflowTemplate. ADR 0008 and #1535 established Argo Workflows as the standard cluster job execution engine.
  - *Rejected*: Kubernetes CronJob. CronJobs do not support cross-job mutexes, so manual submissions could race with scheduled runs.
  - *Rejected*: In-process Service thread. The Service runs at 0 replicas (#1562) and in-process workers are deleted.
- **Schedule interval**: `*/3 * * * *` (180 seconds).
  - *Chosen*: `*/3 * * * *`. The poll interval `service.poll_interval_seconds` is 151 seconds. 180 seconds is the shortest whole-minute period not shorter than 151s.
  - *Rejected*: `*/2 * * * *` (120 seconds). Runs faster than the poll interval, causing redundant checks.
  - *Rejected*: `*/1 * * * *` (60 seconds). Triples execution frequency for negligible latency improvement.
- **Concurrency model**: Global `rag-ingest` mutex in WorkflowTemplate, plus `concurrencyPolicy: Forbid` in CronWorkflow.
  - *Chosen*: Argo `synchronization.mutex` named `rag-ingest` combined with `concurrencyPolicy: Forbid`. Ensures exactly one ingest run executes cluster-wide across scheduled and manual triggers.
  - *Rejected*: `concurrencyPolicy: Forbid` alone. Does not guard against manual workflow submissions.
- **Credential scoping**: Dedicated Secret `qdrant-api-key` in namespace `devops` mounted only in ingest pods.
  - *Chosen*: Dedicated Secret `qdrant-api-key` adopted from `llm/qdrant-api-key`. Only the ingest pod mounts this Secret.
  - *Rejected*: Putting the key into `devops-cli` Secret. That would expose Qdrant credentials to every workload in namespace `devops`.
- **Network perimeter**: Dedicated NetworkPolicy selecting `app.kubernetes.io/name: rag-ingest` for egress to port 6333, with matching ingress rule on Qdrant in `llm`.
  - *Chosen*: Fine-grained pod-selector-based NetworkPolicy for port 6333.
  - *Rejected*: Allowing port 6333 in `devops-default-perimeter`. That would permit all devops workloads to reach Qdrant.
- **Embedding concurrency**: Set `ai.gateway_concurrency.embedding` to 1 via `DEVOPS_CLI_AI_GATEWAY_CONCURRENCY_EMBEDDING=1`.
  - *Chosen*: Limit concurrency to 1 to avoid starving gateway slots needed by roadmap jobs.
  - *Rejected*: Unrestricted default concurrency. Ingestion could monopolize embedding gateway slots.
- **Metrics and lag alert**: Emit freshness timestamp metric and alert `RagIngestBehind` when lag exceeds two schedule periods (360 seconds).
  - *Chosen*: Prometheus alert based on `devops_cli_rag_ingest_last_success_timestamp_seconds` with threshold `> 360`.
  - *Rejected*: Scraping short-lived pods directly. Pods finishing in seconds are missed by Prometheus scrape intervals.
