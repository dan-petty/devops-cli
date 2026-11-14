# Proposal

## Why

No test checks that the rendered `k8s/devops` set holds a scheduled RAG ingest with a valid cron expression that runs `ai rag ingest` through its template. The existing module reads the files directly and pins the schedule, but it does not fail when the scheduled resource is absent or the template runs another command (#4135).

## What Changes

- `tests/commands/k8s/test_k8s_rag_ingest_manifests.py` gains helpers that select the scheduled ingest, read its schedule, resolve its template and assert the container runs `ai rag ingest`.
- Tests cover a valid schedule, the template command, another command, no scheduled resource and an empty schedule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`

## Feasibility

- The CronWorkflow `rag-ingest` holds `spec.schedule` and a `workflowTemplateRef`.
- The WorkflowTemplate holds the `devops ai rag ingest` container.
- The test harness refuses a real `kubectl`, so the helper reads the resources that the kustomization lists.
- Verification commands: `uv run devops ci test tests/commands/k8s/test_k8s_rag_ingest_manifests.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The test module already parses YAML and reads the kustomization. The change adds helpers and assertions, and no dependency.
