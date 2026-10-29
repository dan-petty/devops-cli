# Tasks

## 1. The runner image and its publication

- [x] Add failing tests that read `Dockerfile`, `release.yml` and `ci.yml`: the stage, its place, the pinned bases, the release job and the pull request job
  - Verification: `uv run devops ci test tests/invariants/test_runner_image.py`
- [x] Add the `runner` stage, the `runner-image` job of the release, and the `runner-image` job of CI
  - Verification: `uv run devops ci test tests/invariants/test_runner_image.py tests/test_workflow_contracts.py tests/invariants/test_service_image.py`

## 2. The Job template and the run-job option

- [x] Add failing tests: the Job builder with the runner template, the extra environment and labels, the name prefix, the `--template` option and its dry run
  - Verification: `uv run devops ci test tests/test_k8s_cluster_job.py`
- [x] Add `JobTemplate`, the `--template` option, and the messages and help
  - Verification: `uv run devops ci test tests/test_k8s_cluster_job.py`

## 3. The manifests

- [x] Add failing tests: CronJob `devops-cli-runner`, the ServiceAccount, the Role, the RoleBinding, the projected token, the egress policy, and the second image of ImageUpdater
  - Verification: `uv run devops ci test tests/test_k8s_devops_runtime.py tests/test_k8s_roadmap_service.py tests/test_k8s_runner.py`
- [x] Add the manifests to `k8s/devops/` and to the kustomization, and the second image to `k8s/argocd/image-updater-values.yaml`
  - Verification: `uv run devops ci test tests/test_k8s_devops_runtime.py tests/test_k8s_roadmap_service.py tests/test_k8s_runner.py tests/test_k8s_argocd_apps.py`

## 4. The token of one repository and the process of the job

- [x] Add failing tests: the request body with and without `service.github_app.token_repository`, a bad value, and a child that reads the environment of a non-dumpable parent
  - Verification: `uv run devops ci test tests/test_github_app_identity.py tests/test_process_hardening.py`
- [x] Add the setting, the `repositories` of the request, and `core/process_hardening.py` with its call in `apply_implement`
  - Verification: `uv run devops ci test tests/test_github_app_identity.py tests/test_process_hardening.py tests/test_roadmap_implement_job.py tests/test_config_declarations.py`

## 5. The Service row

- [ ] Add failing tests: the row in the table, one Job for a Staged item, no second Job while it runs, the report of a Job that succeeded, failed or is gone, the stop of an item whose Job left it eligible, and a missing CronJob
  - Verification: `uv run devops ci test tests/test_roadmap_implement_submit.py tests/test_roadmap_run.py`
- [ ] Add the record keys, `k8s/cluster_job_api.py`, `roadmap/implement_submit.py`, the row, and the label selector in the Kubernetes fake
  - Verification: `uv run devops ci test tests/test_roadmap_implement_submit.py tests/test_roadmap_run.py tests/k8s`

## 6. The documentation

- [ ] Describe the runner, the Job, the Role and the guarantees in `k8s/README.md` and `docs/ROUTINE_TASKS.md`, the publication in `RELEASE_CYCLE.md`, the term in `CONTEXT.md`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 7. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2667-implement-runner-job`

## Workflow follow-up

- Pending a person: make the GHCR package `runner` public, as the package `service` is, after the first release that publishes it.
- Pending a person: the runner Job takes the whole Secret `devops-cli`. A narrower Secret for the runner is the better end state, and a person makes secrets.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
