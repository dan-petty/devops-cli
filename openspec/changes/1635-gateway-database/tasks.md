# Tasks

## 1. The gateway database and its connection

Kind: manifests. Reads: `k8s/mattermost/database.yaml`, `k8s/mattermost/networkpolicy.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/gateway/networkpolicy.yaml`, `k8s/llm/networkpolicy.yaml`. Changes: `k8s/llm/gateway-db.yaml`, `k8s/llm/kustomization.yaml`, `k8s/llm/networkpolicy.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/gateway/networkpolicy.yaml`, `k8s/llm/gateway/config.yaml`, `tests/gate/k8s_checks/gateway_database.py`.

- [x] 1.1 Write the checks of the `k8s` row first in `tests/gate/k8s_checks/gateway_database.py`: the `Cluster` keeps its data and names no secret, `DATABASE_URL` comes from `llm-gateway-db-app`, the migration directory is an `emptyDir` under a read-only root, the `startupProbe` allows ten minutes, the gateway refuses a key when the database is down, and the three policies admit only what the spec lists. Verification: `uv run devops ci --only k8s --check` fails on the base in the checks of the Deployment and passes after 1.2
- [x] 1.2 Add `k8s/llm/gateway-db.yaml` (the policy, then the `Cluster`), list it in `k8s/llm/kustomization.yaml`, add the egress rule to the gateway policy, leave the database pods out of `llm-default-perimeter`, and give the gateway Deployment `DATABASE_URL`, `LITELLM_MIGRATION_DIR` with its `emptyDir` and a `startupProbe`. Verification: `uv run devops ci --only k8s --check` and `kubectl apply --dry-run=client -f k8s/llm/gateway-db.yaml`

## 2. The stack order and the secret guard

Kind: behavior. Reads: `src/devops_cli/commands/k8s/stack_lifecycle.py` (the release, repository and post-Helm tables), `tests/invariants/test_k8s_manifests.py` (the secret guard). Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/invariants/test_k8s_manifests.py`, `tests/gate/k8s_checks/gateway_database.py`, `tests/commands/k8s/test_k8s.py` (the post-Helm list of stack `llm`), `tests/ai/benchmark/test_k8s_llm_gateway.py` (the egress check admits the database peer on 5432 and nothing wider).

- [x] 2.1 Write the failing tests first: the check that `cloudnative-pg` is a release of `infra` only and that `llm/gateway-db.yaml` is a post-Helm path of `llm`, and the two tests of the secret guard (a `Cluster` without `initdb.secret` makes `<cluster>-app`, a `Cluster` with one does not). Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py` fails on the base with the Secret `llm/llm-gateway-db-app` unlisted
- [x] 2.2 Move the `cloudnative-pg` release and its repository from stack `chat` to stack `infra`, after `prometheus-operator-crds`, add the post-Helm path to stack `llm`, and make the guard remove the Secret that such a `Cluster` creates. Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/commands/k8s/test_k8s.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/commands/k8s/test_k8s_mattermost.py tests/invariants/test_k8s_argocd_apps.py` (one file at a time) and `uv run devops ci --only k8s --check`

## 3. Documents

Kind: documents. Changes: `k8s/README.md`.

- [x] 3.1 Describe the database, its Secret, the perimeter, the start-up, the rollout, the missing salt key and the missing backup under "LLM Gateway", the operator's new stack in the stack table and in "Mattermost", and the Secret without a row under "Cluster Secrets". Verification: `uv run devops ci docs`

## Workflow follow-up

- A scheduled backup of the database off its node, with a tested restore: #3741.
- The agent grant command (`devops agent env`): #1154.
- A virtual key for the cluster Jobs in place of the master key: the issues that follow #1154.
- Pending a person: after the sync, read `/health/readiness` of the gateway and see that it reports a connected database, and that `kubectl -n llm get cluster llm-gateway-db` reports a healthy cluster and `kubectl -n llm get pvc` shows its claim `Bound`.
- Pending a person: mint a test key of one hour with the master key from the keyring, call one model with it, delete it, and see that the next call answers 401.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
