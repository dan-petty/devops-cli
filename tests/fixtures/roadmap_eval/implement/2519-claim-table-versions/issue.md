### Problem Description

`CHART_CLAIMS` in `tests/test_k8s_local_path_placement.py` (#1634) has one entry for each chart that an Argo CD Application installs. Each entry names the values that turn on a claim and the value path of the pod's affinity. The key is the chart name only. No check ties an entry to the chart version that the Application pins.

A chart release can move a value. Loki did this in 20.0.2 (#1632): it moved the pod field of the token from `serviceAccount.automountServiceAccountToken` to `defaults.automountServiceAccountToken`. If a release moves the claim switch or the affinity path, the test reads a value that the chart no longer uses. The test then passes, and the pod can bind its volume on the control-plane node.

The token test of #1652 has the same kind of table, `_CHART_TOKENS` in `tests/invariants/test_k8s_manifests.py`. Its key is the chart and the version, and a test fails when an Application pins another version. `pinned_charts()` in `tests/support/k8s_tree.py` reads the pinned versions.

### Reproduction Steps

1. Change `targetRevision` of the chart source in `k8s/argocd/apps/grafana.yaml` to a later grafana chart version. Change the deploy-stack release to the same version.
2. In that later version, suppose that the chart reads the claim switch from another value than `persistence.enabled`.
3. Run `uv run devops ci test tests/test_k8s_local_path_placement.py`.

### Expected vs Actual Behavior

Expected: the test fails when an Application pins a chart version that `CHART_CLAIMS` was not read from. The person who bumps the chart then reads the claim values of the new version again.

Actual: the test passes at each chart version, because the key of `CHART_CLAIMS` is the chart name only.

### Environment Diagnostics

Not applicable. The defect is in a test table of the repository. Found in the review of #1652.

### Logs, Traces, or Terminal Output

None.

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
The CHART_CLAIMS table in tests/test_k8s_local_path_placement.py is keyed by chart name only. When a chart release moves a value path, the test reads a stale path and passes silently. A pod can then bind its volume on the control-plane node. The fix adds the pinned chart version to each key and a test that fails when an Application pins a version the table was not read from. The pattern already exists in _CHART_TOKENS in tests/invariants/test_k8s_manifests.py.

### Acceptance criteria

### Requirement: version-keyed table
CHART_CLAIMS SHALL use a tuple of chart name and pinned version as its key type.

#### Scenario: key type check
- **WHEN** the test module is imported and CHART_CLAIMS is inspected
- **THEN** every key is a tuple of two strings, and the set of keys equals the set returned by pinned_charts()

### Requirement: version mismatch fails
A test SHALL fail when an Application pins a chart version that CHART_CLAIMS does not name.

#### Scenario: pinned version not in table
- **WHEN** pinned_charts() returns a (chart, version) pair that is not a key of CHART_CLAIMS
- **THEN** the test asserts a non-empty symmetric difference and fails

### Requirement: placement checks unchanged
The existing placement checks SHALL pass with the new key structure.

#### Scenario: all placement tests pass
- **WHEN** uv run devops ci test tests/test_k8s_local_path_placement.py is run
- **THEN** every test in the module passes

### Existing Tool Considered
No external tool covers this need. The fix is a repository-internal test change. It reuses pinned_charts() from tests/support/k8s_tree.py and copies the tuple key pattern from _CHART_TOKENS in tests/invariants/test_k8s_manifests.py. The written cost is the tokens to change the CHART_CLAIMS key type from str to tuple[str, str], update the _chart_sites lookup, add one test function, and update the existing coverage test. No new dependency is added.

### Key questions
- **What key structure does CHART_CLAIMS use after the fix?**: tuple[str, str], the same as _CHART_TOKENS. Each key is (chart_name, pinned_version). (best practice) [sources: tests/invariants/test_k8s_manifests.py, openspec/changes/archive/2026-10-28-1652-no-unused-service-account-token/design.md]
  - Chosen: tuple[str, str] matching _CHART_TOKENS. The pattern already exists in the same codebase. The token test's design document records the decision to name the version so a chart bump fails until the entry is re-read.
  - Rejected: keep str key and add a separate version list. Two structures to keep in sync. The token test already proved the tuple key is simpler and the symmetric-difference check is one line.
- **How does the test obtain the pinned chart versions?**: pinned_charts() in tests/support/k8s_tree.py already returns frozenset[tuple[str, str]] of (chart, targetRevision) for every Application source that has a chart. [sources: tests/support/k8s_tree.py]
- **How does _chart_sites look up a chart when the key is a tuple?**: Match by chart name only, ignoring the version in the key, exactly as _chart_sites in test_k8s_manifests.py does: (sites for (name, _), sites in CHART_CLAIMS.items() if name == chart). (best practice) [sources: tests/invariants/test_k8s_manifests.py]
  - Chosen: match by name only, like the token test. The version is checked by the separate symmetric-difference test. The lookup only needs the chart name to find the right entry.
  - Rejected: match by full tuple including version. Would require chart_values() to yield the version, changing the shared helper. The token test does not do this.
- **Which test asserts the version match?**: A new test in test_k8s_local_path_placement.py asserts sorted(pinned_charts() ^ CHART_CLAIMS.keys(), key=str) == [], mirroring test_the_chart_table_names_each_chart_at_the_version_that_an_application_pins in test_k8s_manifests.py. (best practice) [sources: tests/invariants/test_k8s_manifests.py]
  - Chosen: symmetric difference with pinned_charts(). Catches both a missing entry and a stale version. The token test uses this exact assertion.
  - Rejected: subset check only (pinned_charts() - CHART_CLAIMS.keys()). Would miss a stale entry for a chart that is no longer installed. The symmetric difference is stricter and matches the existing pattern.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->
