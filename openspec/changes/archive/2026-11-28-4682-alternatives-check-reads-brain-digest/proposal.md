# Proposal: #4682

## Why

Each alternatives check sees only its own item (#4682). Four open merge-conflict items got four different tools, and durable-run items got five tools, two of which ADR 0008 rejects. A decision on one item does not reach the check of the next item. ADR 0023 section 1 gives the check a digest of the project brain before its one model call. The brain index of #4676 exists in `valkey-roadmap`, and no check reads it yet.

## What Changes

- Before its one model call, the check of an item of no skip class reads the digest of the item from the brain index: the near items of the entry of the item, at most 5, each with the date of its check, its verdict, the canonical id and the name of its tool, and the ADRs in force that reject that tool. The JSON text of the digest holds at most 2,000 tokens, and the cut takes whole entries.
- The request of the model holds the digest as `brain` only when the digest has an entry. The check makes no other model call. The prompt says what `brain` holds.
- A written check records the ids of the brain entries that the digest used in `alternatives.brain_used`, at most 10, in the one write of its block and marks. The record key is declared, so the sync of #4676 copies it to the field `uses` of the entry.
- The new setting `roadmap.brain.digest`, `on` or `off`, `on` by default. `off` makes no read of the brain index.
- With no `roadmap.state.url`, while the store does not answer, and for an item with no entry or no near item, the digest is empty and the check runs as before.
- The digest holds no ring and no area verdict: the index holds neither. #7389 adds the ring and #4693 the area verdict.
- The change fits one pull request.
- The change adds a key to the request of the model, a key to the job record of an issue and a setting, which a consumer observes, so it carries a spec delta in the new nested capability `project-brain/digest`.

## Capabilities

### New Capabilities

- `project-brain/digest`: the brain digest that the alternatives check reads before its model call, its entries, its bound, its request key, its record and its setting.

### Modified Capabilities

None. `openspec/specs/roadmap-alternatives/spec.md` holds 80 requirements, the limit of a capability (`openspec/config.yaml`), and gets no requirement.

## Impact

- Code: `src/devops_cli/roadmap/brain_digest.py` is new. `src/devops_cli/roadmap/brain_index.py` gets the reads `items` and `tools`. `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/brain_entries.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py` and the prompt `src/devops_cli/ai/tasks/roadmap_alternatives.md` change.
- Store: the check of one item sends at most 11 `HSCAN` commands to `valkey-roadmap` as the user `brain`: the entry of the item, its near items and their tools. The user holds `+@all -@dangerous` on `roadmap:v1:brain-*`, and the index already reads its watermark with `HSCAN`. No ACL rule and no egress rule changes.
- Tokens: a digest of 5 entries holds about 360 tokens, and the request of each turn of the run holds it.
- Documents: `docs/roadmap/alternatives.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md`, `k8s/devops/configmap.example.yaml`, one dated line of ADR 0023, and the generated `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`.
- The live ConfigMap needs no change: the default is `on`, and the Service pod already names the store and the user `brain`.

## Feasibility

- The index gives the near items with no new write. `_Checks.related` (`src/devops_cli/roadmap/brain_sync.py:131`) writes at most 5 other items of the repository that name the same tool, the newest check first, to the field `near` of each item hash (`src/devops_cli/roadmap/brain_index.py`, `_commands`). The tool hash holds the canonical id and the name of the tool.
- The index holds no ring and no area check. The item hash holds `verdict`, `tool_id`, `refs`, `near`, `checked_at`, `body_hash`, `adr_hash`, `state`, `uses` and `schema`, and the keys are only `brain-item`, `brain-tool`, `brain-ref`, `brain-events` and `brain-sync` (the key table of `src/devops_cli/roadmap/brain_index.py`).
- The ADR reader gives the status of a tool with no new parse: `rejects(adr, *names)` (`src/devops_cli/roadmap/adr.py:424`) is the test that confirms the verdict `rejected` today. A fixture ADR that rejects Temporal and chooses Argo Workflows gives ADR 0008 for Temporal and no ADR for Argo Workflows in `tests/roadmap/test_brain_digest.py`.
- The token count exists: `count_tokens` (`src/devops_cli/ai/context_budget.py:90`) is the exact count of the ADR cut `fit_to_budget` (`src/devops_cli/roadmap/adr.py:246`).
- The store admits the read: the aclfile gives `brain` the pattern `~roadmap:v1:brain-*` with `+@all -@dangerous` (`src/devops_cli/k8s/cluster_secrets.py:83`), and `HSCAN` is no dangerous command.
- The record key was dropped before: `decode_job_record` keeps only the declared keys (`_JOB_RECORD_KEYS`, `src/devops_cli/roadmap/stores/store.py`), and `brain_entries` read `alternatives.brain_used` by its text.
- `uv run pytest -n 4 tests/roadmap/test_brain_digest.py tests/config/test_brain_digest_setting.py tests/security/test_config_declarations.py tests/roadmap/test_roadmap_limit_classes.py` on the base gave 5 failures and 1 collection error, and passes with the change.
- Unverified: a read of the live store. No command of this change reaches the cluster. The live proof is a task for a person after the release.

## Existing Tool Considered

- The alternatives checks of 2026-11-14 and 2026-11-26 in #4682 give the verdict `none`. Generic memory layers such as mem0 and retrieval frameworks such as llama-index keep a store of their own and call a model to extract memories, and none builds a dated digest of this project's brain index. ADR 0023 rejects a vector store for the entries.
- The change uses the existing `BrainIndex`, the client of `roadmap_state_tier()` with its breaker of pybreaker, valkey-py, the ADR reader and tiktoken through `count_tokens`. It adds no dependency, no store and no model call.
- The project code is the read of the entries, the digest, its cut and the record: about 100,000 tokens and 3 hours to build.
- The change deletes the constant `_USES_KEY` of `src/devops_cli/roadmap/brain_entries.py`, and the `HSCAN` loop of `BrainIndex.watermark` moves into the read of a whole hash.
