# Tasks

## 1. The template, the admission and the network of the stage Job

Kind: behavior.

- [x] 1.1 Add the gate checks of CronJob `roadmap-stage`, of the stage branch and the delete policy of the admission policy, of the Role and of the SearXNG reach, and the build tests of the stage Job
  - Verification: `$ uv run python -c "import sys; from tests.gate.k8s import main; sys.exit(main())"` fails on the base
- [x] 1.2 Add `k8s/devops/cronjob-stage.yaml`, the variable `stage` and the policy `roadmap-service-job-deletes` in `admissionpolicy.yaml`, the Role rows, `searxng-stage-clients` and the SearXNG ingress peer, `STAGE_TEMPLATE`, the stage builders, `ClusterJobs.delete_job` and `devops k8s run-job --template stage`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_cluster_job.py tests/k8s/test_k8s_cluster_job_api.py tests/commands/k8s/test_k8s_run_job.py`

## 2. The entry point of the stage Job

Kind: behavior.

- [x] 2.1 Add `tests/roadmap/stage/test_roadmap_stage_job_entry.py` (selection, budgets, ends, check-in, own orphan, command, structure) and the blobless clone test
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py tests/roadmap/test_roadmap_run_checkout.py` fails on the base
- [x] 2.2 Add `src/devops_cli/roadmap/stage/stage_job.py`, `--job-item`, the settings `roadmap.stage.time_budget_seconds`, `github_requests_per_hour`, `job` and `job_deadline`, the record keys of the check-out, the narrowed selection, the own-orphan rule and `ensure_checkout(blobless=True)`
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/test_roadmap_run_checkout.py tests/security/test_config_declarations.py`

## 3. Documents

Kind: documents.

- [x] 3.1 Add the section Stage Jobs to `docs/CLUSTER.md`, the stage Job to `docs/roadmap/stage.md`, the record keys to `docs/ROADMAP_WORKFLOW.md`, and regenerate the references with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Part 2, #4559: the Service submits stage Jobs, writes the check-out, recovers a lost Job, and removes the in-pod path.
- Pending a person: after the release, run one stage Job on a real Ready item with `devops k8s run-job --template stage --repo dan-petty/devops-cli --item <n> -- roadmap stage --repo dan-petty/devops-cli --job-item <n> --confirm`, restart the Service during it, and state the GitHub requests of the Job (`devops_cli_github_requests_total{job="roadmap-stage"}`) on #4559.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
