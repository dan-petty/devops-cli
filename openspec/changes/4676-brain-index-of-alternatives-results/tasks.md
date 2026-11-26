# Tasks

## 1. Read the brain entry of an issue

Kind: behavior. Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/inventory.py`, `src/devops_cli/roadmap/stores/store.py`. Changes: `src/devops_cli/roadmap/brain_entries.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_brain_entries.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 Add `tests/roadmap/test_brain_entries.py` with the cases of the two forms of the block, the references, the skip class, the canonical id, the used entries and the issues that give no entry
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_entries.py` fails on the base
- [x] 1.2 Add `BrainEntry`, `checked_entry` and `entry_of` to `src/devops_cli/roadmap/brain_entries.py`, and the 6 limits `CONST_ROADMAP_BRAIN_*` with their classes in `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_entries.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 2. Scan through the tier of the roadmap state

Kind: behavior. Reads: `src/devops_cli/valkey/client.py`. Changes: `src/devops_cli/valkey/cache.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/valkey/test_roadmap_state_tier.py`, `tests/support/fakes/valkey.py`.

- [x] 2.1 Add the case of `scan` to `tests/valkey/test_valkey_cache_tier.py` and the case of an installed tier to `tests/valkey/test_roadmap_state_tier.py`
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_cache_tier.py tests/valkey/test_roadmap_state_tier.py` fails on the base
- [x] 2.2 Add `ValkeyCacheTier.scan` and `install_roadmap_state_tier` to `src/devops_cli/valkey/cache.py`, and the fixture `roadmap_state_valkey` and the record of each MULTI/EXEC block to `tests/support/fakes/valkey.py`
  - Verification: `$ uv run devops ci test tests/valkey` passes

## 3. Write the index of one item in one transaction

Kind: behavior. Reads: `src/devops_cli/github/repo_ref.py`, `src/devops_cli/valkey/cache.py`. Changes: `src/devops_cli/roadmap/brain_index.py`, `tests/roadmap/test_brain_index.py`.

- [x] 3.1 Add `tests/roadmap/test_brain_index.py` with the cases of the item hash, the one transaction, the newer check, the TTL of each key, the scan of one repository, the watermark and a store that does not answer
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_index.py` fails on the base
- [x] 3.2 Add `BrainIndex` with `write`, `watermark`, `advance` and `item_keys` to `src/devops_cli/roadmap/brain_index.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_index.py` passes

## 4. Copy the checks of a round into the index

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/valkey/tiered.py`. Changes: `src/devops_cli/roadmap/brain_sync.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_brain_sync.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`.

- [x] 4.1 Add `tests/roadmap/test_brain_sync.py` with the cases of the three changed issues, the catch-up, the bound, the near items, the instruments, the store that is down, the first read and the round whose check is off, and the case of the row in `tests/roadmap/test_roadmap_alternatives_item_writes.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_sync.py tests/roadmap/test_roadmap_alternatives_item_writes.py` fails on the base
- [x] 4.2 Add `sync_brain_index` and `sync_alternatives_round` to `src/devops_cli/roadmap/brain_sync.py`, the three instruments to `INSTRUMENTS`, the store `brain_index` to `BrainStore`, and the call of the step to `_run_alternatives_adapter`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_sync.py tests/roadmap/test_roadmap_alternatives_item_writes.py tests/telemetry/test_telemetry_instruments.py` passes

## 5. Make the roadmap Service pod the client of the store

Kind: manifest. Reads: `k8s/devops/valkey-roadmap/kustomization.yaml`, `k8s/devops/networkpolicy.yaml`. Changes: `k8s/devops/roadmap-service/deployment.yaml`, `k8s/devops/roadmap-service/networkpolicy-egress.yaml`, `k8s/devops/configmap.example.yaml`, `tests/gate/k8s_checks/runner.py`.

- [x] 5.1 Add the label `valkey-client: "true"` and the variable `DEVOPS_CLI_ROADMAP_STATE_PASSWORD` to the pod template of Deployment `roadmap-service`, and `roadmap.state.username` to `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter` passes
- [x] 5.2 Add the egress rule to the pods of the store on TCP 6379 to `roadmap-service-egress`, and the rule to the egress list of `check_only_the_service_pod_may_reach_the_api_server`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 6. Document the index

Kind: other. Changes: `docs/roadmap/alternatives.md`, `docs/CLUSTER.md`, `k8s/README.md`, `docs/SERVICE_PATTERNS.md`, `docs/TELEMETRY.md`.

- [x] 6.1 Add the section "The brain index" to `docs/roadmap/alternatives.md`, the client, its label and its egress rule to the section `valkey-roadmap` of `docs/CLUSTER.md` and to `k8s/README.md`, the checks of rows ST2 and CL4 to `docs/SERVICE_PATTERNS.md`, and write the generated documents again with `devops docs generate`
  - Verification: `$ uv run devops ci --check --only docs` passes

## Workflow follow-up

- The digest that the check reads before its model call, the nearest items of the aggregate and the record key `alternatives.brain_used`: #4682.
- The record key `alternatives.refs` and the sections of the reference step: #4672.
- The repair of the index, with the items that left a tool or a reference: #4687.
- The users `router` and `sweep`, the coordination keys and the sentinel of `valkey-roadmap`: #4563.
- Pending a person: record a scenario of `XADD` with `MAXLEN` and of `SCAN` with `MATCH` for the contract suite of the Valkey fake from a real `valkey-server` (`tests/support/valkey_recording.py`). The devcontainer holds no `valkey-server`.
- Pending a person: after the merge, run `uv run devops k8s deploy-stack --stack devops` from a checkout of `main`, which writes `roadmap.state.url` and `roadmap.state.username` to ConfigMap `devops-cli-config`, and restart `deployment/roadmap-service` when its pod is older than the ConfigMap.
- Pending a person: after the merge and the release, give the live proof of the issue: the alternatives row checks 3 items as the App, and a comment gives the result line of each item, its entry from `HGETALL roadmap:v1:brain-item:<owner>/<name>:<n>`, and `devops_cli_brain_sync_lag_seconds{store="brain_index"}` against the interval of the row.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
