# Proposal: #7292

## Why

The brain issue cache of #6013 breaks two rules of the shared cache tier (#7292). It writes the issue records of each repository to `valkey-devops`, and ADR 0023 section 8 keeps that tier to public repositories until each client sends a role user. Its key, `roadmap:v1:brain-issue:<owner>/<name>:<number>`, is outside each key pattern of the ACL users of #4704, so each command gets `NOPERM` when a client sends a role user.

## What Changes

- The issue cache uses the visibility check of the listing snapshot. The check moves from `listing_shared.py` to the module `src/devops_cli/roadmap/stores/visibility.py`, and the snapshot store and the issue cache both call it. No second copy of the check exists.
- A process sends no command for the entry of an issue of a private repository unless it sends the ACL user `sweep`, and none for a repository whose visibility is unknown, as the snapshot store does. A read gives no entry, so the store reads GitHub, as before #6013. A write does not occur. The cache keeps no copy in the process.
- The key of an entry is `valkey:roadmap:v1:issue:<owner>/<name>:<number>`, under `CONST_VALKEY_ROADMAP_PREFIX`, which `sweep` writes and `brain` reads.
- `GitHubRoadmapStore` gives the cache its own visibility read. The cache sends that read only when the process holds no answer, and only after Valkey answered one `GET` of the key prefix.
- The webhook route sends no visibility read. It takes `repository.private` of the signed delivery, which `WebhookRepository` now parses, else the answer that the process holds. With neither, it writes nothing.
- A read and a write that the cache refuses count `private` or `unknown` on `devops_cli_brain_reads_total` and `devops_cli_brain_writes_total` with the store `issue`.
- No migration and no delete: each record under the old prefix has a TTL of 24 hours (`DEFAULT_BRAIN_ISSUE_TTL_SECONDS`), and no code reads it after the release.
- `docs/CLUSTER.md`, `k8s/README.md` and `docs/TELEMETRY.md` describe the key, the rule and the counter results.

A consumer observes the keys of `valkey-devops`, the GitHub requests of a row and the counters, so the change carries spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-brain/shared-cache`: A private repository's issue entries are shared only under the sweep user, A refused issue entry counts its cause, The issue cache reads the visibility only after the shared tier answered, A caller with no visibility read gets the answer of the process, The cached issue key names its repository and number, The brain holds the issue that a row reads, A row reads the cached issue before GitHub, A Service write fills the cached issue, The cache counts a hit and a miss for each row, A quiet Service repository stays inside the request budget
- `roadmap-service-webhooks`: A delivery gives the visibility of its repository, The roadmap consumer writes the cached issue before it wakes the lane, Own-write issue deliveries refresh the cached issue without waking a lane

## Impact

- Code: `src/devops_cli/roadmap/stores/visibility.py` (new), `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/telemetry/instruments.py`
- Documents: `docs/CLUSTER.md`, `k8s/README.md`, `docs/TELEMETRY.md`
- Tests: `tests/roadmap/stores/test_brain_issues.py`, `tests/roadmap/stores/test_github_store_brain.py`, `tests/server/routes/test_webhooks_brain.py`, `tests/roadmap/stores/test_listing_shared.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/conftest.py`
- Deleted internal code: the visibility cache, `Visibility`, `SWEEP_USER` and `_configured_valkey_user` of `listing_shared.py`, which move to `visibility.py`. The key builder call `RepoRef.valkey_key("brain-issue")` of `brain_issues.py` goes.
- GitHub requests: a process with a Valkey that answers sends one visibility read for a repository in each 30 minutes, shared with the listing snapshot. A process with no Valkey sends none.
- Operation: for at most 24 hours after the release, `valkey-devops` holds the old keys, which no code reads. Each cached issue is read from GitHub one time after the release, because the key changed.

## Feasibility

- The defect is in the source at the base commit `9f4cc6efb`: `src/devops_cli/roadmap/stores/brain_issues.py:54` builds the mapping with `ref.valkey_key("brain-issue")` and no visibility read, and `src/devops_cli/github/repo_ref.py:203` gives that key the root `roadmap:v1`.
- The ACL patterns are in `DEVOPS_CACHE_VALKEY_ACL_TEMPLATE` (`src/devops_cli/k8s/cluster_secrets.py:58`): `sweep` holds `~valkey:roadmap:*` and `brain` holds `%R~valkey:roadmap:*`, so the new key is in the pattern of its writer and of its reader.
- The issue gives the measured state of 2026-11-26: a read-only `SCAN` of `valkey-devops` found 453 keys with the prefix `roadmap:v1:brain-issue`, and 32 of them hold issue records of the 2 private repositories of the Service.
- The new tests fail on the base: `uv run pytest -n 4 tests/roadmap/stores/test_brain_issues.py tests/roadmap/stores/test_github_store_brain.py tests/server/routes/test_webhooks_brain.py` gave 33 failed and 1 passed with the source of `9f4cc6efb`. `test_a_private_repository_reads_github_each_time_and_writes_no_key` and `test_a_delivery_of_a_private_repository_writes_no_key` fail there on their assertion, because the fake holds the key.
- A webhook delivery carries the visibility: the payload schema of GitHub lists `private` in the required properties of `repository` (`payload-schemas/api.github.com/common/repository.schema.json` of `octokit/webhooks`, read on 2026-11-26), with the description "Whether the repository is private or public." The route verifies the HMAC of the body before it reads the payload (`_authenticated_payload`, `src/devops_cli/server/routes/webhooks.py`).
- The route cannot send the visibility read itself: `_read_and_route` is `async` and calls the consumer on the event loop (`src/devops_cli/server/routes/webhooks.py:819`), and a `gh` read there stops each other request of the Service until it ends.
- A module that the GitHub store imports must load no cachetools: the probe "the help leaves the ETag store of the GitHub session (cachetools) unloaded" of `tests/gate/startup_imports.py` failed when `brain_issues.py` imported the visibility module at the top. So `brain_issues.py` imports `visibility`, `valkey.cache` and `valkey.tiered` in its functions, as it imports `TieredMapping` today.
- In a test with no `shared_valkey` fixture, `shared_cache_tier()` gives a tier of `valkey://localhost:6379/0` whose first command fails (probe run on 2026-11-26: `GET` gave None and the breaker was open). So the visibility read must come after a command that Valkey answered. Else each read of an issue in a process with no Valkey costs one GitHub request.
- The set that the claim covers is the call sites of `cached_issue` and `remember_issue` in `src/`: `git grep -n -e "cached_issue(" -e "remember_issue(" -- src/` gives 18 lines: the 2 definitions in `brain_issues.py`, the 2 calls with `is_private=` in the methods `_cached_issue` and `_remember_issue` of `github_store.py`, the 2 definitions and the 9 call sites of these methods, and the 3 calls with `private=` in `webhooks.py`. No call site sends a command of an entry with no visibility.

## Existing Tool Considered

The need is a rule of this project about which of its own keys a process may write. Valkey's ACL (`valkey-io/valkey`, BSD-3-Clause, in use since #4704) refuses a key that is outside the pattern of a user, and the change puts the key under the pattern of its role. An ACL cannot tell a public repository from a private one under one pattern, so the check stays in the client, where #6611 put it for the snapshot. The change builds no new mechanism: it reuses that check, `cachetools.TLRUCache` for its answers, and `TieredMapping` for the entries.
