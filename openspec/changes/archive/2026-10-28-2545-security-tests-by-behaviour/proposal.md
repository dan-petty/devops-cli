# Proposal

## Why

Issue #2545, part 4 of #1332: the security and crypto test files have the wrong shape.

- `tests/test_security_sarif.py` (1,780 lines, 137 tests) and `tests/test_reference_extractor.py` (1,206 lines) each test several behaviours, and the second has four catch-all tests.
- `tests/test_tflint.py` and `tests/test_security_tflint.py` test one module.
- Two files are named after a consolidation refactor, not after what they test.
- The SARIF document is compared with a hand-kept file in `tests/golden/`.
- Two files build findings with a local factory, and eleven files invoke the CLI through a module-level `CliRunner()`.
- Redaction, suppression-policy evaluation and the known_hosts check take open-ended input, which docs/TESTING.md tests with Hypothesis properties.

## What Changes

- `tests/test_security_sarif.py` becomes seven files under `tests/security/`, one for each behaviour: finding normalization, fingerprints, correlation, SARIF emission, SARIF ingestion, the suppression policy and the scan report.
- `tests/test_reference_extractor.py` becomes six files under `tests/security/`: address classes, name classes, extraction, false positives, the literal parsers and the report order.
- Each catch-all in the named files becomes one test or one parametrized table for each behaviour. No assertion is lost; the moved tests keep their names, and the pull request lists each renamed test.
- The two tflint files become `tests/security/test_tflint.py`. Its one test that patched `subprocess.run` and `shutil.which` runs on `scanner_fake`, as the others do.
- The consolidation-named files become `tests/security/test_scanner_base_and_registry.py` and `tests/security/test_secret_redaction.py`.
- syrupy snapshots replace the hand comparisons: the SARIF document of four findings (`tests/golden/sarif_report.json` is deleted; the snapshot holds the same document) and the AIBOM document, with its random serial number and timestamp matched by type.
- Hypothesis properties cover redaction (`tests/security/test_redaction_properties.py`), suppression-policy evaluation (`tests/security/test_suppression_properties.py`) and the pinned known_hosts lines (`tests/git/test_known_hosts_properties.py`).
- `make_normalized_finding` joins `make_finding` in `tests/support/builders.py`. It replaces the SARIF file's local `make`, and `make_finding` replaces the gitleaks file's local `_leak`.
- The eleven module-level `CliRunner()`s give way to the `cli` fixture, which runs `devops <group> <command>`.
- The change alters tests only, so it has no spec delta (`skip_specs: true`).
- This change fits one pull request.

## Impact

- Tests under `tests/security/`, `tests/git/` and `tests/support/builders.py`, and the named files under `tests/`.
- `tests/golden/sarif_report.json` is deleted.

## Feasibility

Measured on origin/main 0702d133 (2026-10-28), after #2551 merged.

- syrupy 6.1.1 and Hypothesis 6.168.3 are dev dependencies in `pyproject.toml`, and five test files already store syrupy snapshots.
- The SARIF snapshot was compared with `tests/golden/sarif_report.json` before the file was deleted: `to_sarif` of the four findings equals the golden document.
- **SBOM:** `devops scan sbom` passes Trivy's output through byte for byte. #1439 deleted the hand-written SBOM builders, so devops-cli makes no SBOM document of its own. The tests already assert that the written file equals Trivy's output, and a snapshot would store a copy of each test's own literal. So the SBOM gets no snapshot.
- **known_hosts:** no known_hosts parser exists in `src`; `crypto/known_hosts.py`, which the issue names, does not exist. The code that reads known_hosts is `git/operations.py:_ensure_known_host`, which appends GitHub's pinned host keys that the file lacks. The property covers it.
- **Redaction:** before the new properties were written, each was explored with 3,000 Hypothesis examples. Masking twice equals masking once, and a GitHub token leaves no part of its body. The URI property first failed on a user name equal to its password, which is a fault of the property, not of `mask_uri_credentials`. The property now asserts the whole masked URI.
- **Mutations:** each new property fails when the behaviour it states is broken in the code: an expiry that never lapses, a fingerprint compare that always matches, an exact match in place of the glob, `apply` that drops a finding, a mask that appends a character, redaction without the GitHub token patterns, a URI left unmasked, and `_ensure_known_host` appending every pinned line or no line break.
- **Catch-alls:** `test_vault_broker_error_branches`, which #1332 names, does not exist on main any more.
- **Tests:** the named files gave 902 test IDs before the change and give 1,053 after. 849 test names stay, 455 of them in a new file. 52 test functions were renamed or dissolved into the 203 new IDs, which also count the new property and snapshot tests. The pull request lists each one.

## Existing Tool Considered

syrupy (snapshots), Hypothesis (properties), pytest parametrization, the `cli` fixture (#1310), the builders (#1312) and `scanner_fake` (#772). Nothing new is built. The change deletes `tests/golden/sarif_report.json`, the two local finding factories, the eleven module-level `CliRunner()`s, the catch-all tests and the duplicate tflint file.
