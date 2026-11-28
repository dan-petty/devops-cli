# Tasks

## 1. Add the setting of the digest

Kind: behavior. Reads: `src/devops_cli/config/env.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/config/test_brain_digest_setting.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Add `tests/config/test_brain_digest_setting.py` with the default `on`, the variable and a refused value, and the variable `DEVOPS_CLI_ROADMAP_BRAIN_DIGEST` to `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/config/test_brain_digest_setting.py tests/security/test_config_declarations.py` fails on the base
- [x] 1.2 Add `RoadmapBrainConfig` with `digest` to `roadmap` in `src/devops_cli/config/settings.py`, and `BrainDigestMode` with `DEFAULT_ROADMAP_BRAIN_DIGEST` to `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run devops ci test tests/config/test_brain_digest_setting.py tests/security/test_config_declarations.py` passes

## 2. Read the digest of an item from the brain index

Kind: behavior. Reads: `src/devops_cli/roadmap/brain_sync.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/valkey/cache.py`. Changes: `src/devops_cli/roadmap/brain_index.py`, `src/devops_cli/roadmap/brain_digest.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_brain_digest.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 2.1 Add the cases of the five near items, the date, the cut at 2,000 tokens, the ADR status, the index with no area check, the near item with no entry and the empty digest to `tests/roadmap/test_brain_digest.py`, and the class of `CONST_ROADMAP_BRAIN_DIGEST_MAX_TOKENS` to `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py tests/roadmap/test_roadmap_limit_classes.py` fails on the base
- [x] 2.2 Add `items`, `tools`, `item_entry_id` and `tool_entry_id` to `src/devops_cli/roadmap/brain_index.py`, `read_digest` and `digest_index` to `src/devops_cli/roadmap/brain_digest.py`, and `CONST_ROADMAP_BRAIN_DIGEST_MAX_TOKENS` to `src/devops_cli/config/constants.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py tests/roadmap/test_brain_index.py tests/roadmap/test_brain_sync.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 3. Give the digest to the check and record the used entries

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/brain_entries.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_brain_digest.py`.

- [x] 3.1 Add the cases of the request with and with no `brain`, the count of model calls, the brain that is not available, the switch `off`, the eleven entries in one write and the cleared key to `tests/roadmap/test_brain_digest.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py` fails on the base
- [x] 3.2 Give the digest of `read_digest` to `alternatives_request` as `brain` in `_verdict_check`, add `brain_used` to `Check` and its mark to `AlternativesWriter.settle`, declare `AlternativesRecordKey.BRAIN_USED` and read it in `checked_entry`, and say what `brain` holds in the prompt
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py tests/roadmap/test_brain_entries.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_alternatives_one_write.py` passes

## 4. Document the setting

Kind: other. Changes: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `k8s/devops/configmap.example.yaml`.

- [x] 4.1 Write the generated documents again with `devops docs generate`, and add `roadmap.brain.digest` with its comment to `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci --check --only docs` passes

## 5. Document the digest

Kind: other. Changes: `docs/roadmap/alternatives.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md`, `docs/adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md`.

- [x] 5.1 Add the section "The brain digest" and the record of the used entries to `docs/roadmap/alternatives.md`, the keys `alternatives.refs` and `alternatives.brain_used` to the record table of `docs/ROADMAP_WORKFLOW.md`, the read of the digest to the section `valkey-roadmap` of `docs/CLUSTER.md`, and one dated line `Fact out of date` to ADR 0023
  - Verification: `$ uv run devops ci --check --only docs` passes
- [x] 5.2 Put the requirements of the digest in the nested capability `project-brain/digest`, and none in `roadmap-alternatives`
  - Verification: `$ uv run devops openspec check` passes, and `git grep -c '^### Requirement:' openspec/specs/roadmap-alternatives/spec.md` prints 80

## Workflow follow-up

- The ring of a tool in the digest, when the brain index holds one: #7389.
- The values `answered` and `partial` of `devops_cli_brain_first_reads_total`, which the live proof of the issue names: #7388.
- The area verdict of an area check, which the digest reads when the brain holds one: #4693.
- Pending a person: after the merge and the release, the alternatives row checks 3 items of the stage window as the App, and a comment gives the result line of each item, the brain entries of each digest (`alternatives.brain_used` of its record) and the lines of `devops_cli_ai_tokens_total{row="alternatives"}` over 7 days, with a rise of at most 1,500 prompt tokens for each check.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
