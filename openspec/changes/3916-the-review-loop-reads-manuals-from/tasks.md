# Tasks

## 1. Read the review manuals from the research index

Kind: behavior. Reads: `src/devops_cli/ai/kb.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `src/devops_cli/review/analysis.py`, `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/review/report.py`, `tests/review/test_kb_manuals_metadata.py`, `tests/review/test_review_group_analysis.py`, `tests/review/test_review_prompt_adversaries.py`, `tests/ai/test_kb.py`, `ARCHITECTURE.md`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/review/test_report.py`. Changes: `src/devops_cli/ai/kb.py`, `tests/review/test_kb_manuals_metadata.py`, `tests/review/test_review_group_analysis.py`, `tests/review/test_review_prompt_adversaries.py`, `ARCHITECTURE.md`.
Adds: `ManualIndexRecord`, `read_manual_index_records`, `manual_reference_key`

- [ ] 1.1 `test_loader_returns_the_record_at_the_pinned_version` fails on the base, because `load_matched_kb_manuals` in `src/devops_cli/ai/kb.py` walks the front-matter articles. Rewrite `test_loader_matches_tools_lock_inventory_floor_and_kubernetes`, `test_loader_excludes_mismatched_and_undated_manuals`, `test_run_group_analysis_populates_kb_drift_and_injected` and `test_floor_only_environment_matches_and_drifts_manuals_and_filtering_keeps_some` in `tests/review/test_kb_manuals_metadata.py` to load records into the `qdrant` fixture, add `test_manual_key_names_url_date_and_hash`, `test_an_expired_record_is_listed_as_expired`, `test_a_record_refused_at_ingest_is_listed`, `test_an_unset_store_is_one_drift_entry` and `test_an_unreachable_store_is_one_drift_entry`, and pass `kb_manuals={}` at each `run_group_analysis` call site of `tests/review/test_review_group_analysis.py` and of `tests/review/test_review_prompt_adversaries.py`
  - Verification: `$ uv run devops ci test tests/review/test_kb_manuals_metadata.py` fails on the base
- [ ] 1.2 Add `ManualIndexRecord` to `src/devops_cli/ai/kb.py` with source_url, fetched_at, expires_at, content_hash, component, version_range, tools, topics, tags, text and refused_at_ingest. Add `read_manual_index_records`, which takes its client from `resolve_qdrant_client` of `src/devops_cli/ai/rag/indexer.py`, scrolls the research collection with a limit, keeps the records of kind manual and returns their payloads. Add `manual_reference_key`, which builds kb:<source_url>@<fetch_date>@<sha16> with the fetch date in ISO 8601 and the first `CONST_KB_SHA_DIGEST_LENGTH` characters of the content hash. Replace the article scan of `load_matched_kb_manuals` with these records and drop its `kb_dir` argument: keep a record whose version range contains the version of its component from the lock files at read time through `_version_matches_pattern`, list an expired record with reason expired, list a refused record with reason refused_at_ingest and list a mismatched record with reason version_drift. Catch `ConfigurationError` and `QdrantClientError` from the read and return no manual with one drift entry that names `qdrant.url`, or with reason index_unreachable. Build each `MatchedManual` with `path` and `key` from the record, `content` from the record text, and `tools`, `topics` and `tags` from the record, so `filter_kb_manuals_for_group` keeps its behavior. Rewrite the article-dependent cases of `tests/review/test_kb_manuals_metadata.py` so each loads records into the `qdrant` fixture and asserts a record, a reason and a key. Pass `kb_manuals={}` at each `run_group_analysis` call site of `tests/review/test_review_group_analysis.py` and `tests/review/test_review_prompt_adversaries.py`, so those cases never read the store
  - Verification: `$ uv run devops ci test tests/review/test_kb_manuals_metadata.py` passes
- [ ] 1.3 Edit `ARCHITECTURE.md` to state that a review reads its manuals from the research index and reports an expired, refused or unread record beside version drift
  - Verification: `$ uv run devops ci docs` passes

## 2. Show the drift reasons of the report

Kind: other. Reads: `src/devops_cli/review/report.py`, `tests/review/test_report.py`. Changes: `tests/review/test_report.py`.

- [ ] 2.1 Extend `test_the_report_lists_the_knowledge_base_drift_when_no_group_analysis_ran` in `tests/review/test_report.py` with a drift entry whose reason is expired and one whose reason is refused_at_ingest, and assert that the `## Reference coverage: drift` section of the rendered report holds both lines
  - Verification: `$ uv run devops ci test tests/review/test_report.py` passes

## 3. Delete the front-matter match that nothing calls

Kind: other. Reads: `src/devops_cli/ai/kb.py`, `tests/ai/test_kb.py`, `tests/review/test_kb_manuals_metadata.py`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/review/test_report.py`. Changes: `src/devops_cli/ai/kb.py`.

- [ ] 3.1 Delete `_process_manual_file`, `_evaluate_applies_to`, `_evaluate_single_spec`, `_match_python_spec`, `_match_tool_spec`, `_match_package_spec`, `_match_k8s_spec`, `_extract_candidate_versions` and `_extract_manual_tags` from `src/devops_cli/ai/kb.py`. Keep `parse_manual_front_matter`, `KbFrontMatter`, `_is_valid_spec_syntax`, `_version_matches_pattern`, `_lookup_uv_lock_version` and `_resolve_matching_context`, which the record match and the shipped articles still need
  - Verification: `$ ! git grep -n -I -F -w _evaluate_applies_to src/ tests/` passes

## 4. Score the review before and after on the same cases

Kind: other. Reads: `src/devops_cli/commands/review.py`, `tests/fixtures/review_labels/labels.json`, `docs/SELF_IMPROVEMENT.md`. Changes: `docs/SELF_IMPROVEMENT.md`.

- [ ] 4.1 Add the before-and-after protocol for a manual-source change to `docs/SELF_IMPROVEMENT.md`: the labelled inputs of `tests/fixtures/review_labels/labels.json`, the review at the base commit and at the branch head over the same inputs, the two `devops review score` commands, and the two score tables. Run the protocol and paste both score tables into the pull request comment, and run this check by hand: Add a worktree of the base commit with `git worktree add ../base origin/main`. In that worktree run `uv run devops review path <labelled input>` for each input of `tests/fixtures/review_labels/labels.json` and keep the session folders. Run the same review on the branch head over the same inputs. Score each set with `uv run devops review score <session> --labels tests/fixtures/review_labels/labels.json`, paste both score tables into the pull request comment and write them into the doc.
- [ ] 4.2 Edit `docs/SELF_IMPROVEMENT.md` to hold the before-and-after protocol and the two score tables of this change
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: a manual applies only to the pinned version of its tool; a record past its expiry is not returned and the report lists it as expired.
- Group 1: A test: the key in a report names URL, date and hash.
- Group 4: The review eval is run before and after on the same cases; the pull request comment gives the scores.
- Group 1: Tests use a recorded fake of Qdrant; no network.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
