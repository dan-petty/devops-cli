# Tasks

## 1. Generate the user passwords and the aclfile of valkey-roadmap

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secret_source.py`, `tests/k8s/test_cluster_secrets_file.py`, `tests/invariants/test_k8s_manifests.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`.

- [x] 1.1 Add the case `test_valkey_roadmap_user_passwords_and_derived_aclfile` to `tests/k8s/test_cluster_secret_plan.py`, and add the 4 rows of `devops/valkey-roadmap-auth` to the expected rows of `test_table_holds_each_secret_entry_with_its_source_and_restarts`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py` fails on the base
- [x] 1.2 Add the 3 keyring names, `ROADMAP_STATE_VALKEY_ACL_TEMPLATE` and the row `devops/valkey-roadmap-auth` to `src/devops_cli/k8s/cluster_secrets.py`, and add the row to each fixed list of the push and deploy tests
  - Verification: `$ uv run devops ci test tests/k8s tests/invariants/test_k8s_manifests.py tests/commands/k8s` passes

## 2. Name the store in the settings and give one tier of it

Kind: behavior. Reads: `src/devops_cli/valkey/cache.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`. Changes: `src/devops_cli/valkey/cache.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `tests/valkey/test_roadmap_state_tier.py`, `tests/security/test_config_declarations.py`, `tests/commands/test_config_audit_keys.py`, `tests/conftest.py`.

- [x] 2.1 Add `tests/valkey/test_roadmap_state_tier.py` with 5 cases, and the case `test_the_roadmap_state_settings_are_declared_with_their_variables` with the 3 variables and the keyring entry in `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/valkey/test_roadmap_state_tier.py tests/security/test_config_declarations.py` fails on the base
- [x] 2.2 Add `RoadmapStateConfig` as `roadmap.state` and `get_roadmap_state_password` to `src/devops_cli/config/settings.py`, the credential `roadmap.state.password` to `src/devops_cli/config/env.py`, and `roadmap_state_tier` with `reset_roadmap_state_tier` to `src/devops_cli/valkey/cache.py`, where `_ProcessTier` holds the one tier of each kind
  - Verification: `$ uv run devops ci test tests/valkey tests/security/test_config_declarations.py tests/commands/test_config_audit_keys.py` passes

## 3. Build valkey-roadmap in the product base

Kind: manifest. Reads: `k8s/devops/kustomization.yaml`, `k8s/devops/networkpolicy.yaml`, `tests/gate/k8s_checks/devops_runtime.py`. Changes: `k8s/devops/valkey-roadmap/kustomization.yaml`, `k8s/devops/valkey-roadmap/valkey.conf`, `k8s/devops/kustomization.yaml`, `k8s/devops/networkpolicy.yaml`, `k8s/devops/configmap.example.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/gate/k8s_checks/devops_runtime.py`, `tests/gate/k8s_render.py`.

- [x] 3.1 Add the folder `k8s/devops/valkey-roadmap` with the base and its 3 components at v0.24.1, the suffix `-roadmap`, the settings and the patches, and list it in `k8s/devops/kustomization.yaml` and in `PRODUCT_MANIFESTS_BY_STACK`
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [x] 3.2 Add `valkey` to the two lists of `devops-default-perimeter-ingress` and `devops-default-perimeter-egress`, and add the two containers of the store to the container list of `tests/gate/k8s_checks/devops_runtime.py`
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter` passes
- [x] 3.3 Add `roadmap.state.url` to `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 4. Document the store

Kind: other. Changes: `k8s/README.md`, `docs/CLUSTER.md`, `docs/SERVICE_PATTERNS.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 4.1 Add the 4 Secret rows, the paragraph of the store and its tree entry to `k8s/README.md`, the section `valkey-roadmap` to `docs/CLUSTER.md` and the checks of rows ST2 and CL4 to `docs/SERVICE_PATTERNS.md`, and write the generated documents again with `devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The brain index, its first client pod, the label `valkey-client: "true"`, the egress rule and the two variables of that pod: #4676.
- The users `router` and `sweep`, the request windows, the GraphQL hold, the halt, the delivery ids and the sentinel: #4563.
- Pending a person: before the merge, run `uv run devops k8s push-secrets --only devops/valkey-roadmap-auth` from the branch, then `uv run devops k8s push-secrets --only devops/valkey-roadmap-auth --plan`. Merge only when each of the 4 keys reads `unchanged`.
- Pending a person: add TCP 9121 to the rule of namespace `devops` in `monitoring-default-perimeter-egress` of the environment repository, so that Alloy scrapes the exporter.
- Pending a person: after the merge, run `uv run devops k8s deploy-stack --stack devops` from a checkout of `main`, which writes `roadmap.state.url` to ConfigMap `devops-cli-config`.
- Pending a person: after the merge, give the live proof of the issue: the pod is ready, `ACL USERS` lists `agent`, `brain`, `default` and `metrics`, `ACL GETUSER default` shows `off`, `redis_up` is 1, a connection with no user is refused, `agent` gets `NOPERM` on a write of `roadmap:v1:brain-item:probe`, and a pod in another namespace cannot connect on TCP 6379.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
