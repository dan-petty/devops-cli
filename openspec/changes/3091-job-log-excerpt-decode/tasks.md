# Tasks

## 1. Read a pod log as text (behavior)

Reads: `src/devops_cli/k8s/service.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/k8s/doctor.py`, `tests/support/fakes/kubernetes.py`. Changes: `src/devops_cli/k8s/service.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/k8s/doctor.py`, `tests/support/fakes/kubernetes.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/k8s/test_k8s_pod_log_text.py` (new), `tests/k8s/test_k8s_doctor.py`.

- [ ] 1.1 Let the pod log of `FakeCoreV1` be `bytes`, and answer as the real client does for a plain read and a raw read. Write failing tests: `log_tail` of a `bytes` log with a check mark gives the character and real line breaks, and of a `str` log gives it unchanged; the doctor snapshot of a `bytes` log holds one entry for each line, with the check mark and a masked token; the real client reads a loopback log as text
  - Verification: `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/k8s/test_k8s_pod_log_text.py tests/k8s/test_k8s_doctor.py` fails on the base for the `bytes` and doctor tests
- [ ] 1.2 Add `read_pod_log_text` to `k8s/service.py`, call it in `log_tail` and in the doctor, and delete `str(log)`
  - Verification: `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/k8s/test_k8s_pod_log_text.py tests/k8s/test_k8s_doctor.py` passes

## 2. Show the excerpt in a fenced block (behavior)

Reads: `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/fence.py` (new), `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_fence.py` (new).

- [ ] 2.1 Write failing tests: the report comment of a Job with a `bytes` log holds a fenced block, real line breaks, the check mark, no `b'` prefix and a masked token; a log with a run of three backticks gets a longer fence; `code_fence` gives three backticks, or one more than the longest run
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_fence.py` fails on the base
- [ ] 2.2 Add `code_fence`, use it in the report comment and in the stop comment, and change the message `implement_job_report` and `implement_job_report_no_log`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_fence.py tests/roadmap/test_roadmap_implement_job.py`

## 3. Documents and gates (no behavior)

Changes: `README.md`, generated documents, `openspec/changes/3091-job-log-excerpt-decode/`.

- [ ] 3.1 Regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme .` then `uv run devops ci docs`
- [ ] 3.2 Show that no `str(log)` conversion of a pod log is left in the source
  - Verification: `! git grep -n "return str(log)" src/devops_cli/k8s`
- [ ] 3.3 Run the fail-to-pass check and the full gate
  - Verification: `uv run devops ci fail-to-pass --base origin/main`, then `uv run devops ci`
- [ ] 3.4 Validate the change and archive it as the last commit
  - Verification: `uv run devops openspec check`

## Workflow follow-up
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
