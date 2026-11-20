# Proposal

## Why

The runner Job template loads the whole Secret `devops-cli` with `envFrom` (#6518). Each implement and fix-checks pod then holds the 10 keys of the Secret: the private key of the App, the gateway key, the cache password, the Qdrant key, 2 MCP tokens, the Mattermost command token, the Crawl4AI token, the Firecrawl key and the webhook secrets. The jobs of the pod read only 2 of them. The next experiment gives the agent of a Job a real shell, so each key in the pod environment is one command away from the agent. A Job must hold only the keys that it reads.

## What Changes

- CronJob `devops-cli-runner` takes 2 keys of Secret `devops-cli` through `secretKeyRef`, each in the variable of its name, and no `envFrom`: `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY`, the keys of a stage Job (`CONST_ROADMAP_STAGE_JOB_SECRET_KEYS`). No Secret and no key name is new, so nothing goes to the cluster before the merge.
- The admission policy `roadmap-service-jobs` admits the same 2 keys in `valueFrom` for a runner Job. Without this, the policy refuses every runner Job that the Service makes from the new template: a server dry run of such a Job as the Service on 2026-11-20 got `An env entry must not use valueFrom`.
- The gate checks of the k8s row read the new template: the runner check reads the 2 keys, and one check runs the policy against a runner Job with a third key, an MCP token and the `envFrom` of a Job made before this change.
- `docs/CLUSTER.md` and the comment of `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` name the keys of a runner Job.
- The change carries a spec delta in `roadmap-implement-runner`, because a manifest and the admission of a Job are observable.
- The change fits one pull request: about 100 changed lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-runner`: the runner Job takes 2 keys of the Secret, and the admission policy admits them.

## Impact

- Manifests: `k8s/devops/cronjob-runner.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`.
- Code: a comment in `src/devops_cli/config/constants.py`. Gate checks: `tests/gate/k8s_checks/runner.py`, `tests/gate/k8s_checks/job_admission_policy.py`. Test: `tests/roadmap/implement/test_roadmap_implement_submit.py` reads an env entry with no `value`.
- Documents: `docs/CLUSTER.md`.
- Live Jobs: a runner Job that the Service made before the sync keeps `envFrom`. The policy still admits `envFrom` of Secret `devops-cli` for a runner Job, so the Service can patch the deadline of that Job and resume a waiting fix-checks Job.
- Relation: #5498 adds a table of keys and token permissions for each roadmap Job and a template test. This change applies the row of the runner Job by hand and builds no table. #2695 and #5506 move the agent away from the keys.

## Feasibility

- `kubectl -n devops get secret devops-cli -o go-template` with the key names only listed 10 keys on 2026-11-20. No value was read.
- The job process reads `ai.api_key` (`get_ai_api_key`: the model client and the step broker, `implement_broker.py`) and the App key (`app_installation.py`). A grep of `src/devops_cli/roadmap/implement/`, `roadmap/steps/` and the fix-checks modules finds no other credential getter.
- A child process gets no key: `build_subprocess_env` drops each name that matches `*KEY*`, `*TOKEN*`, `*SECRET*` or `*PASSWORD*` (`core/process.py`). The shell of a step gets only `PATH`, `HOME`, `LANG`, `LC_*` and the values of `shell_environment` (pydantic-ai-harness `LocalWorkspace`).
- `roadmap.implement.mcp` is false by default and in the live ConfigMap, so `get_mcp_implement_token` is not called. No module under `src/devops_cli/roadmap/` uses Valkey, Qdrant, Firecrawl or Crawl4AI in the runner path, and no NetworkPolicy lets a Job pod reach Crawl4AI.
- `load_settings` with the live ConfigMap and only the 2 keys in a clean environment loads, and the getters of the other keys return no value.
- `build_job` replaces only the env names that the Service passes (`DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`, `PYTEST_XDIST_AUTO_NUM_WORKERS`, `OTEL_SERVICE_NAME`), so the 2 `secretKeyRef` entries stay in the implement and fix-checks Jobs.
- gitops-engine `pkg/sync/sync_tasks.go` sorts a CronJob before a kind it does not list, such as ValidatingAdmissionPolicy, in one sync wave.

## Existing Tool Considered

Kubernetes `secretKeyRef` and ValidatingAdmissionPolicy cover the need, and the stage template already uses them. The change builds nothing: about 150,000 agent tokens and 2 hours to plan, change and prove. It deletes the `envFrom` of the runner template.
