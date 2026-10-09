# Task: Fingerprint v2 and Deterministic Order-Independent Correlation (#1141)

**Issue**: [#1141](https://github.com/dan-petty/devops-cli/issues/1141)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p1-high
**Scope**: scope/security

## Description

Prior to this change, `devops scan` used Fingerprint v1 (MD5 over tool, rule ID, path, and canonical message), which excluded line numbers to tolerate code shifting above the finding, but collided on duplicate messages across different functions and omitted enclosing symbols and line-window contexts. Furthermore, findings deduplication and correlation relied on insertion order: `deduplicate` retained the first-seen item in arrival order, and `correlate` used single-linkage dictionary grouping, resulting in non-deterministic representative anchors and order-dependent cluster outputs across permutations.

To ensure immutable identities, stable suppressions, and order-independent correlation across scans and reviews:
1. Migrated `devops scan` and `NormalizedFinding` to Fingerprint v2 (`CONST_SARIF_FINGERPRINT_KEY = "devopsCli/v2"`):
   - Computes SHA-256 over tool, rule ID, repository-relative path, qualified enclosing symbol extracted via AST (e.g., `Class.method`, function name, or `<module>`), and a 100 non-whitespace character window hash starting from the flagged line.
   - Assigns a deterministic occurrence index only when base identities collide.
2. Sourced identity for region-less findings from SARIF `logicalLocations`: `kind/namespace/name[/container]` for Kubernetes resources, and `purl@version` for dependency advisories.
3. Kept scanner's own `partialFingerprints` as metadata properties without overriding `devops-cli` fingerprint identity.
4. Formulated `correlation_key` over `(path or logical location, overlapping region, CWE)`.
5. Enforced complete linkage clustering in `correlate`:
   - Pre-sorts findings using a total key (`parsed_path, start_line, end_line, rule_id, tool, fingerprint`).
   - Admits a finding into an existing cluster only if the correlation predicate holds against *every* existing member, ensuring bridging-first chains leave 2 distinct clusters in every permutation.
   - Disallows findings from the same tool from correlating with each other across tools, preserving distinct checks and multiple scanner hits.
6. Implemented deterministic representative and scalar selection:
   - Evaluates highest severity rank, then narrowest parsed region span, then total finding key, with sorted reference collections.
   - Orders clusters deterministically using severity rank, negative confirmations count, case-insensitive parsed path, numeric start and end lines (`a.py:9` before `a.py:10`), enclosing symbol, rule ID, tool, and fingerprint.
7. Validated order independence across 4 fixtures (`chained triple`, `bridging-first chain`, `#512 SQL injection pair`, and recorded `_watcher` session) over all `itertools.permutations`, verifying 1 distinct set and 1 distinct output sequence in every order while retaining `k8s/informer.py:44-112`.
8. Added stability tests verifying that non-identical and identical line insertions above do not alter fingerprints, distinct sites yield distinct fingerprints, inserting a 10th DaemonSet leaves the other 9 unchanged, and suppressions match after line shifts.

## Key Changes

- **Constants & Review Fingerprint (`src/devops_cli/config/constants.py`, `src/devops_cli/review/fingerprint.py`)**:
  - Bumped `CONST_SARIF_FINGERPRINT_KEY` to `"devopsCli/v2"`.
  - Added AST-based `extract_enclosing_symbol` to determine qualified enclosing symbols from Python source.
  - Updated `compute_fingerprint_v2` to automatically extract enclosing symbols when source code is provided.
- **Security SARIF Engine (`src/devops_cli/security/sarif.py`)**:
  - Emitted `endLine` in SARIF physical location regions when present.
  - Decomposed `_location_of` into `_physical_location_of` and `_logical_symbol_of` helpers, extracting `end_line` and preserving complexity $M \le 10$.
- **Finding Normalization & Correlation (`src/devops_cli/security/normalization.py`)**:
  - Added `end_line`, `cwe`, `file_content`, and `occurrence_index` attributes to `NormalizedFinding`.
  - Updated `fingerprint` property to compute Fingerprint v2, reading file content from disk when available.
  - Implemented `correlation_key` returning `(_finding_locator, _finding_region, _extract_cwe)`.
  - Implemented `_findings_correlate` enforcing cross-tool agreement, region overlap within tolerance 2, and CWE compatibility.
  - Implemented complete linkage in `correlate` with pre-sorting by `_total_finding_key`.
  - Implemented `_pick_representative` choosing highest severity, narrowest parsed region, and total key tie-breaks.
  - Added numeric location ordering in `rank_clusters` sorting `a.py:9` before `a.py:10`.
  - Implemented `assign_occurrence_indices` with on-disk fallback for colliding findings.
  - Decomposed `_extract_cwe` and `_iter_strings` generator helpers keeping nesting depth $\le 3$.
- **Test Suite (`tests/test_security_sarif.py`, `tests/test_security_kubelinter.py`)**:
  - Added golden Fingerprint v2 test pins in `test_a_finding_without_a_symbol_keeps_its_fingerprint`.
  - Updated fingerprint length assertion from 32 to 64 hex characters.
  - Added stability tests: `test_fingerprint_v2_stability_on_unrelated_insertions`, `test_fingerprint_v2_distinguishes_distinct_sites`, `test_fingerprint_v2_daemonset_stability`, and `test_fingerprint_suppression_matches_after_edit_above_line`.
  - Added property vs identity test `test_a_tools_own_partial_fingerprints_are_kept_as_a_property_not_identity`.
  - Added logical location test `test_a_finding_without_a_region_takes_identity_from_logical_locations_or_purl`.
  - Added 3-row BLE001 deduplication test `test_deduplicate_and_scan_keep_all_rows_of_ble001_fixture`.
  - Added full permutation tests over `itertools.permutations` across all 4 fixtures (`test_order_independence_across_permutations`).
  - Added complete linkage cluster count verification (`test_bridging_first_chain_leaves_two_clusters_in_every_order`).
  - Added representative preservation verification (`test_watcher_session_keeps_informer_range_in_every_order`).
  - Added numerical location sort verification (`test_cluster_ranking_sorts_parsed_location_numerically`).

## Acceptance Criteria

- [x] Fingerprint v2 for a result with a region = sha256 of tool, rule id, path, enclosing qualified symbol from AST, 100 non-whitespace character window hash, and occurrence index on collision (`test_a_finding_without_a_symbol_keeps_its_fingerprint`).
- [x] A result without a region takes identity from SARIF `logicalLocations`: `kind/namespace/name[/container]` for Kubernetes objects, and `purl@version` for advisories (`test_a_finding_without_a_region_takes_identity_from_logical_locations_or_purl`).
- [x] Stability tests pass: non-identical and identical lines inserted above leave fingerprints unchanged, distinct sites give distinct fingerprints, inserting a 10th DaemonSet leaves the other 9 unchanged, and suppressions match after line shifts (`test_fingerprint_v2_stability_on_unrelated_insertions`, `test_fingerprint_v2_distinguishes_distinct_sites`, `test_fingerprint_v2_daemonset_stability`, `test_fingerprint_suppression_matches_after_edit_above_line`).
- [x] `deduplicate` and `devops scan` keep all 3 rows of a fixture with 3 BLE001 hits in one file (`test_deduplicate_and_scan_keep_all_rows_of_ble001_fixture`).
- [x] A tool's own `partialFingerprints` are kept as a property, not as identity (`test_a_tools_own_partial_fingerprints_are_kept_as_a_property_not_identity`).
- [x] `correlation_key` uses (path or logical location, overlapping region, CWE).
- [x] A fingerprint suppression still matches after an edit above the line.
- [x] Fingerprint pins bumped to `"devopsCli/v2"`.
- [x] Order independence: `deduplicate` and `correlate` produce identical sets and output sequences over `itertools.permutations` across 4 fixtures: chained triple, bridging-first chain, #512 SQL injection pair, and recorded `_watcher` session (`test_order_independence_across_permutations`).
- [x] Complete linkage: input pre-sorted by total key; findings join cluster only when correlation predicate holds against every member; bridging-first chain leaves 2 clusters in every order (`test_bridging_first_chain_leaves_two_clusters_in_every_order`).
- [x] Deterministic picks: representative and scalars chosen by highest severity, narrowest parsed region, and total key; list fields sorted; `_watcher` keeps `k8s/informer.py:44-112` in every order; parsed locations sort `a.py:9` before `a.py:10` (`test_watcher_session_keeps_informer_range_in_every_order`, `test_cluster_ranking_sorts_parsed_location_numerically`).
- [x] Stdlib only (`itertools`, no networkx).
- [x] Tests run offline with fakes and recorded tool output: no network, no real scanner, no model; each test under 1 s.
- [x] `changelog.d/1141.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Pending a person: Offline replay: the finding lists reaching `deduplicate` and `correlate` in one #415 corpus run are captured, and the number of lists with more than one output across permutations is counted before and after, recorded in the task file.
- Pending a person: `devops scan` row counts over `src/` before and after, plus the number of identities that needed an occurrence index, recorded in the task file.
