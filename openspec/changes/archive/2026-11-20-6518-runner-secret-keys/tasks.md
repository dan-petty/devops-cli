# Tasks

## 1. Manifests

- [x] 1.1 CronJob `devops-cli-runner` takes `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` of Secret `devops-cli` through `secretKeyRef` and no `envFrom`; the gate check of the runner container reads the 2 keys
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 The admission policy `roadmap-service-jobs` admits the 2 keys in `valueFrom` for a runner Job and refuses them in a planner run Job, and admits `envFrom` of the Secret only in the `UPDATE` of a runner Job; gate checks run the policy against a runner Job with a third key or an MCP token, the `CREATE` and the `UPDATE` of a runner Job with the `envFrom` of the Secret, and a planner run Job with each key
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Documents

- [x] 2.1 `docs/CLUSTER.md` and the comment of `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` name the keys of a runner Job
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #5498: a table of keys and token permissions for each roadmap Job, a template test, and a policy that refuses `envFrom` in each request when no runner Job made before #6518 runs.
- #5506 and #2695: the agent container of a Job holds no credential, and the shell of a step runs in a real sandbox.
- Pending a person: after the merge and the Argo CD sync, an implement Job and a fix-checks Job run green, and their result lines go on #6518.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
