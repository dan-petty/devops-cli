# Proposal: #7293

## Why

The runner Jobs of the roadmap (stage, implement and fix-checks) send no credentials to the cache Valkey `valkey-devops`. Each command fails with an authentication error, the circuit breaker of the cache tier opens, and each read of the shared tier of the project brain goes to GitHub. Measured on 2026-11-26 in Prometheus, 24 hours: the stage Jobs counted 318 `auth` errors and 6,831 `open` errors in `devops_cli_valkey_cache_errors_total`, 3,507 reads of the issue store with the result `fallback`, 0 hits of the issue cache in 3,492 reads, and 11,756 GitHub requests. The Service pod had 3,650 hits of the row `refine` in the same hours.

#6518 removed each key of Secret `devops-cli` that a Job did not need, and the password of the cache was one of them, although the Job reads the cache. The spec `llm-valkey` already says that a runner Job reaches the cache with `DEVOPS_CLI_VALKEY_PASSWORD`.

## What Changes

- CronJob `roadmap-stage`: the container `stage` reads `DEVOPS_CLI_VALKEY_PASSWORD` from Secret `devops-cli`.
- CronJob `devops-cli-runner`: the containers `prepare` and `publish` read the same key. The container `agent` gets no new key.
- `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` holds the third key.
- The admission policy `roadmap-service-jobs` admits the third key. Its rule for the three containers stays: `agent` reads only the key of the gateway.
- The gate checks of the `k8s` row hold the new key set. The case that used the password of the cache as the refused key now uses `DEVOPS_CLI_QDRANT_API_KEY`.
- `docs/CLUSTER.md` names the keys of each container.

## Capabilities

- `roadmap-implement-runner`: the keys of the runner containers, and the keys that the policy admits.
- `roadmap-stage/job`: the keys of the stage template.

## Impact

- The key exists in Secret `devops/devops-cli` today, so no step of a person comes before the merge.
- Argo CD syncs the templates and the policy from one commit. A Job of an older Service image comes from the same templates, so no order of the release matters.
- The containers send the default user, as the Service does today. #6600 moves each client to a role user.
- This pull request merges after #7292, so that the cache holds public repositories only when the Jobs can read it.

## Feasibility

- `kubectl -n devops get secret devops-cli -o json` lists the key `DEVOPS_CLI_VALKEY_PASSWORD` (2026-11-26).
- `devops-default-perimeter-egress` admits TCP 6379 to namespace `llm`, and `valkey-devops-perimeter-ingress` admits namespace `devops`, so the network is not the cause.
- `src/devops_cli/roadmap/job_launcher.py` builds each Job from the CronJob of the cluster (`runner_job`), so a key of the template reaches the Job.
- The rule of the policy for the three containers reads `(c.name == "agent") == (key == "DEVOPS_CLI_AI_API_KEY")`. It refuses the password of the cache in `agent` and admits it in `prepare` and `publish` with no new expression.

## Existing Tool Considered

The `secretKeyRef` of Kubernetes and the ValidatingAdmissionPolicy that the project already uses. No new tool. Cost: about 60,000 tokens and 1 hour.

## Weakened checks

- check: `tests/gate/k8s_checks/job_admission_policy.py::check_each_container_of_a_runner_job_may_read_exactly_its_key_of_the_constant`
  reason: The check held that the policy refuses `DEVOPS_CLI_VALKEY_PASSWORD` in each container. The owner approved on 2026-11-26 (comment on #7293) that `prepare` and `publish` read it. The check now holds that the policy admits it there and refuses it in `agent`.
