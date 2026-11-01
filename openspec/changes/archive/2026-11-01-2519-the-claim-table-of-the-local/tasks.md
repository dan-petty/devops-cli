# Tasks

## 1. Key CHART_CLAIMS by chart version and add the mismatch test

Reads: none. Changes: `tests/core/test_k8s_local_path_placement.py`.

- [x] 1.1 Write test_the_claim_table_names_each_chart_at_the_version_that_an_application_pins. It asserts sorted(pinned_charts() ^ CHART_CLAIMS.keys(), key=str) == []. This test fails before the implementation because CHART_CLAIMS keys are strings, not tuples, and verify that `uv run devops ci test tests/core/test_k8s_local_path_placement.py` fails on the base
- [x] 1.2 Change CHART_CLAIMS type annotation from dict[str, ...] to dict[tuple[str, str], ...]. Update every key from the chart name string to a (chart_name, version) tuple, using the version from the Argo CD Application file. Update the lookup that finds a chart entry to match by name only: (entry for (name, _), entry in CHART_CLAIMS.items() if name == chart). This mirrors _chart_sites in tests/invariants/test_k8s_manifests.py, and verify that `uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes
- [x] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
