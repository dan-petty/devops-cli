# Design

## Placement

The split and renamed files go under `tests/security/`, and the known_hosts property under `tests/git/`, the package that owns `_ensure_known_host`. This follows the rule of #1307 Q17: a file goes to the package that owns most of what it tests. #1313 places the rest of the test tree.

## Rejected alternatives

- **A shared module for `_PINNED_FINDINGS`:** the fingerprint pins and the SARIF snapshot both used the same four findings. A test module cannot import another test module (docs/TESTING.md), and the data is specific to the fingerprint test. The snapshot test builds the same four findings with `make_normalized_finding` in about ten lines instead.
- **`write_policy` copied into three files:** the report pipeline and the CLI tests are one behaviour, the scan report, so they share one file. That file writes its two policy files in place, and only the suppression-policy file keeps the helper.
- **A snapshot of the SBOM:** the SBOM is Trivy's own output, passed through byte for byte (Feasibility).
- **Moving the remaining `run_subprocess`, settings and `ScannerRegistry` patches onto fakes:** #2543 and #2544 own them. This change keeps each patch where it was, also inside the dissolved tests.
