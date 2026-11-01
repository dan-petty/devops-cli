# Tasks

## 1. The Status function derives Blocked, and the record keeps the digest

Reads: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/store.py`, `tests/roadmap/test_roadmap_status_sync.py`.

- [ ] 1.1 Write tests for `derive_status` with the new fact `stopped`, for `facts_of` on an item that holds `implement.stopped`, and for a sweep that turns a Ready item with a stop on record into Blocked and leaves a Blocked item alone. Verify that `uv run devops ci test tests/roadmap/test_roadmap_status_sync.py` fails on the base
- [ ] 1.2 Add the fact `stopped` to `StatusFacts`, the order In Progress, Blocked, Planned, Ready to `derive_status`, the fact to `facts_of`, and the record key `implement.job_digest` to `ImplementRecordKey`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_status_sync.py` passes
- [ ] 1.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. The Service records the digest of the runner image when it creates a Job

Reads: `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/implement_submit.py`. Changes: `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/lang/en/messages.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/roadmap/test_roadmap_implement_submit.py`.

- [ ] 2.1 Write tests for `ClusterJobs.template_digest` (an image with a digest, an image with none, a missing CronJob), for the record `implement.job_digest` that holds the digest when the API receives the create, for a template with no digest, and for the report comment that names the digest. Verify that `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/roadmap/test_roadmap_implement_submit.py` fails on the base
- [ ] 2.2 Add `ClusterJobs.template_digest`, record the digest in the same write as `implement.job`, and add the digest line to the report comment. Verify that `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/roadmap/test_roadmap_implement_submit.py` passes
- [ ] 2.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. A stop sets Blocked

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_submit.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_planned.py`, `tests/roadmap/test_roadmap_implement_submit.py`.

- [ ] 3.1 Change the tests of a stop of a step, of a stop of a Planned item and of a Job report to expect the Status Blocked. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_planned.py tests/roadmap/test_roadmap_implement_submit.py` fails on the base
- [ ] 3.2 Set the Status of both stop paths with `derive_status`, and change the stop comment, the report text and the help text to say Blocked. Verify that the same command passes
- [ ] 3.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Two clear rules take an item out of Blocked

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/implement_submit.py`. Changes: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

- [ ] 4.1 Write tests for the retry rule, the digest rule, the same digest over ten rounds (the count of Job creates stays 1), a second stop on the new digest, a stop with no digest, a stop of an item that a Job or an agent or a person holds, a comment of a stranger, and a failed clear that does not stop the others. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py` fails on the base
- [ ] 4.2 Add `stop_clear.py` with the two rules and call it in the round of the row `implement`, after the Status sweep and before the plan. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/test_roadmap_implement_submit.py` passes
- [ ] 4.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. The documents say what the code does

Reads: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`, `tests/invariants/test_roadmap_workflow_doc.py`.

- [ ] 5.1 Change the retry check of `tests/invariants/test_roadmap_workflow_doc.py` to read the clear rules (a retry row starts from `status/blocked` with `implement.stopped`), and verify that `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` fails on the base
- [ ] 5.2 Change `docs/ROADMAP_WORKFLOW.md` (the transitions, the Blocked row, `implement.job_digest`, the stop and retry path, the diagram, the planned list) and step 16 of the Roadmap service in `k8s/README.md`. Verify that `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 5.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
