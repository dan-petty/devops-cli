# Proposal: #4676

## Why

The alternatives check keeps each result in the block and in the job record of its issue (#4676). No reader joins these results: one tool is on many items, and each check searches again. ADR 0023 section 3 puts the join in a brain index in `valkey-roadmap`, with the block and the record as its durable copy. The store, its setting and its ACL users exist since #7294, and no process reads or writes it yet.

## What Changes

- The alternatives row of the Service runs the step `brain-sync` after its checks. The step copies the check of each issue that changed since its watermark into the brain index of the repository. It reads only the issues that the round holds, so it sends no GitHub request and makes no model call.
- The index holds one hash for the item of a check, one for its tool and one for each reference repository, each with a TTL of 45 days, the audit stream `brain-events` with about 10,000 entries, and the watermark key of the step. `RepoRef` builds each key, and each key starts with `roadmap:v1:brain-`.
- The keys of one item and its stream entry go in one MULTI/EXEC. The entry of the newer check stays when a copy of an older block comes late.
- A round whose store is down or not configured ends as before and counts one `fallback`.
- Three instruments: `devops_cli_brain_entries`, `devops_cli_brain_sync_lag_seconds` and `devops_cli_brain_first_reads_total`. The counters of the project brain get the store `brain_index`.
- `ValkeyCacheTier` gets `scan`, and the tier of the roadmap state gets an install seam for tests.
- The roadmap Service pod becomes the first client of `valkey-roadmap`: the label `valkey-client: "true"`, the password of the user `brain` from Secret `devops/valkey-roadmap-auth`, and one egress rule to the pods of the store on TCP 6379. `k8s/devops/configmap.example.yaml` names the user `brain`.
- The change fits one pull request.
- The change adds a step of a Service row, keys of a store, instruments and manifest objects, which a consumer observes, so it carries a spec delta.

## Capabilities

### New Capabilities

- `project-brain/index`: the brain index of the alternatives results, its keys, the step that writes it, its instruments and its first client pod.

### Modified Capabilities

None. The requirements of `roadmap-state/store` and `roadmap-state/client` stay as they are: the aclfile already holds the users `brain` and `agent` with the pattern `roadmap:v1:brain-*`.

## Impact

- Code: `src/devops_cli/roadmap/brain_entries.py`, `src/devops_cli/roadmap/brain_index.py` and `src/devops_cli/roadmap/brain_sync.py` are new. `src/devops_cli/roadmap/run.py`, `src/devops_cli/valkey/cache.py`, `src/devops_cli/telemetry/instruments.py` and `src/devops_cli/config/constants.py` change.
- Manifests: `k8s/devops/roadmap-service/deployment.yaml`, `k8s/devops/roadmap-service/networkpolicy-egress.yaml` and `k8s/devops/configmap.example.yaml`.
- Gate: `tests/gate/k8s_checks/runner.py` holds `roadmap-service-egress` to its two rules.
- Documents: `docs/roadmap/alternatives.md`, `docs/CLUSTER.md`, `k8s/README.md`, `docs/SERVICE_PATTERNS.md` and the generated `docs/TELEMETRY.md`.
- Each alternatives round of a public repository sends 1 `HSCAN`, 1 `HSET` and at least 1 `SCAN` to the store, and one WATCH transaction for each changed issue that holds a check. The first round of a repository copies each check, at most 500.
- The live ConfigMap `devops-cli-config` needs `roadmap.state.url` and `roadmap.state.username`, which `devops k8s deploy-stack --stack devops` writes from a checkout of `main`. Until then the row counts a `fallback` in each round.
- The record keys `alternatives.refs` (#4672) and `alternatives.brain_used` (#4682) are read when the record holds them. Until their issues declare them, an entry holds no reference and no used entry.

## Feasibility

- The store answers each command of the index for the user `brain`. The probe of #7294 on the rendered store (comment "Facts for #4676" on pull request #7302) records: `brain` writes `roadmap:v1:brain-item:*` and the stream `roadmap:v1:brain-events`, and gets `NOPERM` on a key of another kind. The aclfile gives `brain` the pattern `~roadmap:v1:brain-*` with `+@all -@dangerous` (`ROADMAP_STATE_VALKEY_ACL_TEMPLATE`, `src/devops_cli/k8s/cluster_secrets.py:78`). The probe sent `HSET` and `XADD`. It did not send `WATCH`, `MULTI`, `EXEC`, `EXPIRE`, `HSCAN` and `SCAN` as `brain`: the Valkey command reference puts none of them in the category `dangerous`, and the live proof of the issue shows them on the store.
- The existing transaction support fits. `ValkeyCacheTier.watch_and_write` (`src/devops_cli/valkey/cache.py:215`) watches one key, gives the bytes of one field to a callback and sends the commands of the callback in one MULTI/EXEC. The index watches the item key and reads `checked_at`.
- The in-memory Valkey of the tests answers `XADD` with `MAXLEN ~`, `SCAN` with `MATCH` and the WATCH transaction: `uv run pytest -n 4 tests/roadmap/test_brain_index.py` passes with 9 cases on fakeredis with valkey-py 6.2.0.
- The round holds the listing with no second read. `select_items` reads `store.items()`, which reads the listing through `IncrementalListing.read` (`src/devops_cli/roadmap/stores/github_store.py:1549`), and `_kept` (`src/devops_cli/roadmap/stores/github_store.py:1533`) keeps each issue that a write returns. So `store.issues()` after the checks sends no request.
- The live Secret holds the key. `kubectl -n devops get secret valkey-roadmap-auth` on 2026-11-26 lists the keys `agent`, `brain`, `metrics` and `users.acl`, and Deployment `valkey-roadmap` has 1 of 1 pods ready. The live ConfigMap holds no `roadmap.state` yet.
- Unverified: the contract suite of the Valkey fake (`tests/valkey/test_valkey_contract.py`) holds no scenario for `XADD` and `SCAN`. A new scenario needs a record from a real `valkey-server`, which the devcontainer does not hold. The live proof of the issue covers the real store.

## Existing Tool Considered

- Valkey core types through valkey-py, behind the existing `ValkeyClient` and `ValkeyCacheTier` with the breaker of pybreaker: hashes, `EXPIRE`, a stream with `MAXLEN`, `WATCH`/`MULTI`/`EXEC` and `SCAN`. The change adds no dependency, no Lua script, no server module and no vector store.
- `RepoRef.valkey_key` builds each key (ADR 0022 section 5), and `canonical_id` and `project_of` of `devops_cli.roadmap.inventory` give the id of a tool and the repository of a link.
- The alternatives check of 2026-11-26 in #4676 gives the verdict `in-use` for valkey-py and found no open tool that indexes check results across issues. The project code is the parse of the block and the record, the join across items, the watermark and the instruments: about 150,000 tokens and 4 hours to build.
- The change deletes no internal code.
