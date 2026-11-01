# Proposal

## Why

#2519: CHART_CLAIMS is keyed by chart name only. When a chart release moves a value path, the test reads a stale path and passes silently. A pod can then bind its volume on the control-plane node. The token test (#1652) already solved this with a tuple key and a symmetric-difference check.

## What Changes

- Change CHART_CLAIMS key type from str to tuple[str, str] in tests/core/test_k8s_local_path_placement.py
- Update the chart lookup to match by name only, ignoring the version in the key
- Add a test that asserts pinned_charts() ^ CHART_CLAIMS.keys() is empty
- Add a spec delta to the local-path-volume-placement capability for the version-keyed table requirement
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: version-keyed claim table, version mismatch fails

## Impact

- Tests: `tests/core/test_k8s_local_path_placement.py`

## Feasibility

- The issue premise is confirmed: CHART_CLAIMS in tests/core/test_k8s_local_path_placement.py is keyed by chart name only (identifier match at line 90 shows the dict annotation). The pattern to copy exists in tests/invariants/test_k8s_manifests.py: _CHART_TOKENS uses tuple[str, str] keys and test_the_chart_table_names_each_chart_at_the_version_that_an_application_pins asserts the symmetric difference with pinned_charts().
- pinned_charts() in tests/support/k8s_tree.py returns frozenset[tuple[str, str]] of (chart, targetRevision) for every Application source that has a chart. This is the source of the versions.
- First check: run `uv run devops ci test tests/core/test_k8s_local_path_placement.py` to confirm the module passes before the change. Second check: after the change, run the same command to confirm all tests pass with the new key structure.

## Existing Tool Considered

No external tool covers this need. The fix is a repository-internal test change. It reuses pinned_charts() from tests/support/k8s_tree.py and copies the tuple key pattern from _CHART_TOKENS in tests/invariants/test_k8s_manifests.py. The written cost is the tokens to change the CHART_CLAIMS key type from str to tuple[str, str], update the lookup, and add one test function. No new dependency is added.
