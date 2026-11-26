# Tasks

## 1. Behavior

Kind: behavior. Reads: `tests/gate/k8s_checks/job_admission_policy.py`, `tests/gate/k8s_checks/stage_job.py`, `tests/gate/k8s_checks/runner.py`, `k8s/devops/roadmap-service/admissionpolicy.yaml`. Changes: `tests/gate/k8s_checks/job_admission_policy.py`, `tests/gate/k8s_checks/stage_job.py`, `tests/gate/k8s_checks/runner.py`, `src/devops_cli/config/constants.py`, `k8s/devops/roadmap-service/admissionpolicy.yaml`, `k8s/devops/cronjob-stage.yaml`, `k8s/devops/cronjob-runner.yaml`.

- [x] 1.1 Change the gate checks to the approved key set: the stage container reads three keys, `prepare` and `publish` read the App key and the password of the cache, `agent` reads the key of the gateway only, and the policy refuses the password of the cache in `agent` and `DEVOPS_CLI_QDRANT_API_KEY` in a stage Job
  - Verification: `$ uv run devops ci --check --only k8s` fails on the base with 3 failed cases
- [x] 1.2 Add `DEVOPS_CLI_VALKEY_PASSWORD` to `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS`, to the key list and the message of the policy `roadmap-service-jobs`, to the container `stage` of CronJob `roadmap-stage` and to the containers `prepare` and `publish` of CronJob `devops-cli-runner`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. Documents

Kind: other. Changes: `docs/CLUSTER.md`.

- [x] 2.1 Name the keys of each container and the keys that the policy admits in `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci --check --only docs` passes

## 3. Live proof

- Pending person: after the release, `devops_cli_valkey_cache_errors_total{job="roadmap-stage",error="auth"}` stays at 0 for 24 hours and `devops_cli_brain_cache_total{job="roadmap-stage",result="hit"}` is above 0. Only a person or an agent with cluster access reads the live values, and a comment on #7293 gives them with the GitHub requests of the stage Jobs for the same hours.
