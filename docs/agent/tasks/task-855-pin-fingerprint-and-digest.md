# Task: Pin finding fingerprint and run-store digest to literal values (#855)

**Issue**: [#855](https://github.com/dan-petty/devops-cli/issues/855)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: type/test, priority/p2-medium, scope/security

## Description

Two digests are persisted outside the pull requests that compute them:
1. `NormalizedFinding.fingerprint` (`devops_cli.security.normalization:NormalizedFinding.fingerprint`): SHA-256 over tool, rule_id, path, and canonical message joined by `'␟'`, sliced to 32 hex characters (with symbol appended when present). Suppression policies store this and match only on exact equality, and SARIF emits it as partial fingerprints under `devopsCli/v1`.
2. `run_store.digest` (`devops_cli.ai.run_store:digest`): SHA-256 over canonical JSON data (`sort_keys=True, default=str, separators=(",", ":")`), sliced to 16 hex characters. It names stored benchmark baselines and Valkey index keys.

Previously, tests checked only relational properties (such as line-insensitivity or round-trips). Any refactor or inadvertent change that modified serialization options, part ordering, separators, or canonicalisation would pass tests while silently invalidating suppressions and orphaning baselines.

This change introduces regression pins asserting literal hash values across fixed finding and payload inputs, adds an invariant check for `CONST_SARIF_FINGERPRINT_KEY == "devopsCli/v1"`, and adds a golden OASIS SARIF 2.1.0 document asserted against SARIF emission and validated against the schema.

## Acceptance Criteria

- [x] **Fingerprint pins in `tests/test_security_sarif.py`**:
  - Pinned 4 fixed `NormalizedFinding` inputs (covering line-based, symbol-based, multi-tool, and canonical message variation) to literal 32-hex SHA-256 fingerprints (`test_finding_fingerprints_are_pinned_to_literal_values`).
  - Added assertion that `CONST_SARIF_FINGERPRINT_KEY == "devopsCli/v1"` with documentation that an algorithm change bumps the key, updates the pins, and adds a CHANGELOG line in the same commit (`test_sarif_fingerprint_key_pinned`).
  - Verified that swapping hashed parts, changing the separator, or altering message canonicalisation breaks the fingerprint pin (`test_swapping_parts_or_changing_separator_or_canonicalisation_alters_fingerprint`).
- [x] **Golden SARIF report**:
  - Added golden SARIF report `tests/golden/sarif_report.json`.
  - Asserted `to_sarif` output equals the golden report, and validated the golden document against `tests/fixtures/sarif-schema-2.1.0.json` (`test_golden_sarif_report_matches_and_validates_against_schema`).
- [x] **Run-store digest pins in `tests/test_run_store.py`**:
  - Pinned `run_store.digest` to literal 16-hex SHA-256 digests for 2 fixed dicts (`test_digest_pinned_to_literal_values`).
  - Verified that altering `json.dumps` serialization options changes the digest (`test_digest_fails_when_json_options_differ`).
- [x] **Performance & dependencies**:
  - The new tests execute in < 1 second with zero new dependencies added.
- [x] **Changelog**:
  - Added changelog fragment `changelog.d/855.md` under `### Security`.
- [x] `uv run devops ci` passes.
