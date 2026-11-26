# Tasks

## 1. Keep the issue entries of a private repository out of the shared tier

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/valkey/tiered.py`, `src/devops_cli/valkey/cache.py`, `src/devops_cli/k8s/cluster_secrets.py`. Changes: `src/devops_cli/roadmap/stores/visibility.py`, `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/roadmap/stores/test_brain_issues.py`, `tests/roadmap/stores/test_github_store_brain.py`, `tests/roadmap/stores/test_listing_shared.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/conftest.py`.
Adds: `visibility_of`, `held_visibility`, `for_user`, `configured_valkey_user`, `reset_visibility`, `issue_key`

- [x] 1.1 Add the failing cases to `tests/roadmap/stores/test_github_store_brain.py` (`test_a_private_repository_reads_github_each_time_and_writes_no_key`, `test_an_issue_that_the_service_opens_in_a_private_repository_writes_no_key`, `test_a_private_repository_is_shared_under_the_sweep_user`, `test_a_public_repository_keeps_the_shared_read_and_write`, `test_a_failed_visibility_read_reads_github_and_writes_no_key`) and to `tests/roadmap/stores/test_brain_issues.py` (`test_a_key_names_its_repository_and_number`, `test_an_entry_of_a_private_repository_reaches_the_shared_tier_only_under_the_sweep_user`, `test_a_caller_with_no_answer_and_no_read_uses_the_answer_that_the_process_holds`, `test_no_visibility_read_while_the_shared_tier_does_not_answer`), and give each other case of the two modules the visibility read of a public repository
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_brain_issues.py tests/roadmap/stores/test_github_store_brain.py` fails on the base
- [x] 1.2 Move the visibility check from `src/devops_cli/roadmap/stores/listing_shared.py` to `src/devops_cli/roadmap/stores/visibility.py`, with the read of GitHub as an argument of `visibility_of`; keep `repository_visibility` and `TieredSnapshotStore` on it, register `reset_visibility` in `tests/conftest.py`, and import the moved names from their module in `tests/roadmap/stores/test_listing_shared.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_shared.py` passes
- [x] 1.3 In `src/devops_cli/roadmap/stores/brain_issues.py`, build the prefix `valkey:roadmap:v1:issue:<owner>/<name>` under `CONST_VALKEY_ROADMAP_PREFIX`, give the key of an issue with `issue_key`, make the mapping the private `_issue_cache`, and make `cached_issue` and `remember_issue` send no command of an entry for a private or an unknown answer unless the process sends `SWEEP_USER`, with the `GET` of the key prefix before the visibility read; in `src/devops_cli/roadmap/stores/github_store.py`, read and write each entry through `_cached_issue` and `_remember_issue`, which pass `repository_is_private`; seed the public entry of `tests/roadmap/implement/test_roadmap_implement_submit.py` with `private=False`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_brain_issues.py tests/roadmap/stores/test_github_store_brain.py tests/roadmap/stores/test_listing_shared.py tests/roadmap/implement/test_roadmap_implement_submit.py` passes

## 2. Take the visibility of a delivery in the webhook route

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/roadmap/stores/brain_issues.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `tests/server/routes/test_webhooks_brain.py`.

- [x] 2.1 Add the failing cases `test_a_delivery_of_a_private_repository_writes_no_key`, `test_a_delivery_of_a_private_repository_is_shared_under_the_sweep_user` and `test_a_delivery_with_no_visibility_uses_the_answer_that_the_process_holds` to `tests/server/routes/test_webhooks_brain.py`, and give the payload of each other case `private: false`
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py` fails on the base
- [x] 2.2 Add the optional field `private` to `WebhookRepository` in `src/devops_cli/models/webhooks.py`, and pass `payload.repository.private` to `cached_issue` and `remember_issue` in `_remember_delivery_issue` and `_remember_own_delivery_issue` of `src/devops_cli/server/routes/webhooks.py`
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py` passes

## 3. Describe the rule of the issue cache in the documents

Kind: other. Reads: `docs/CLUSTER.md`, `k8s/README.md`, `docs/TELEMETRY.md`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`. Changes: `docs/CLUSTER.md`, `k8s/README.md`, `docs/TELEMETRY.md`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`.

- [x] 3.1 Name the store `issue` and the two causes of an unknown answer in the descriptions of `devops_cli_brain_reads_total` and `devops_cli_brain_writes_total` in `src/devops_cli/telemetry/instruments.py` and in the docstrings of `BrainRead` and `BrainWrite` in `src/devops_cli/config/constants.py`, and regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Edit `docs/CLUSTER.md` and `k8s/README.md` to give the key `valkey:roadmap:v1:issue:<owner>/<name>:<number>`, the cache Valkey `valkey-devops`, the rule for a private repository and the visibility of a delivery
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1 and group 2: Test first: a read and a webhook delivery of a private repository write no key to the `valkey_server` fake, and each read answers from GitHub, as before #6013. The test fails on the base.
- Group 1: A test: with `valkey.username` set to `sweep`, the record of a private repository reaches the shared tier.
- Group 1: A test: each key of the issue cache starts with `valkey:roadmap:v1:`.
- Group 1: A test: a public repository keeps the shared read and write of today.
- Pending a person: Live proof after the release: 25 hours after the deploy, a `SCAN` of `valkey-devops` finds no key with the prefix `roadmap:v1:brain-issue`, and no key of a private repository under the new prefix. A comment gives the counts. Only a person with access to the cluster runs the scan, and the old keys go with their TTL of 24 hours.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
