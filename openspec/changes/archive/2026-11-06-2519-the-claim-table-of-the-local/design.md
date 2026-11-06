# Design

## Decisions

- **Key `CHART_CLAIMS` with `tuple[str, str]`, as `_CHART_TOKENS` does.** The pattern exists in `tests/invariants/test_k8s_manifests.py`. The design of the token test records the decision to name the version, so that a chart bump fails until a person reads the entry again. The risk is real: commit 33b582d0 bumped traefik from 41.6.0 to 42.1.3 and nothing made a person read the claim values of the new version.
- **Find the entry of a chart by name only.** `_chart_sites` unpacks exactly one entry with `(sites,) = (...)`, then calls it when it is a callable. The version is checked by the separate symmetric-difference test. A table with two versions of one chart fails the unpack, which is the wanted result.
- **Replace the old coverage test with the new one, in the same edit.** The old test compares chart names with the keys. With tuple keys it fails for every chart. The new test covers the same case (a chart with no entry) and the case of a changed version, so the old test goes in the group that replaces it.
- **Assert with a symmetric difference.** `sorted(pinned_charts() ^ CHART_CLAIMS.keys(), key=str) == []` catches a missing entry, a stale version and an entry for a chart that no Application installs. It is the assertion of the token test.
- **Check that the guard fails with numbered manual steps, not with a second test.** The test reads the real tree, so it cannot run on a made-up pin. A test that patched the Application files would test the test and add code.

## Rejected alternatives

- **Keep the key as the chart name and add a second list of versions.** Two structures must stay in sync. The token test shows that the tuple key is simpler and that the check is one line.
- **Find the entry by the full tuple, with the version.** `chart_values()` yields the chart name only. The lookup would need that helper to yield the version, and the helper is shared with other tests. The token test does not do this.
- **A subset check, `pinned_charts() - CHART_CLAIMS.keys()`.** It would miss an entry for a chart that no Application installs, and an entry at an old version beside the new one.
- **Keep the old coverage test next to the new one.** It fails with tuple keys, so the module could not pass. A version of it that strips the version from the keys would repeat the new test.
- **A spec delta for the new requirement.** The change edits a test table and a document, and no consumer sees a different behavior. The rules of this repository give such a change no delta.
