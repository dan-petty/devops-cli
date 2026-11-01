# Design

## Decisions

- **Use tuple[str, str] as the key type of CHART_CLAIMS, matching _CHART_TOKENS**: The pattern already exists in the same codebase. The token test design document records the decision to name the version so a chart bump fails until the entry is re-read.
- **Match by chart name only in the lookup, ignoring the version in the key**: The version is checked by the separate symmetric-difference test. The lookup only needs the chart name to find the right entry. The token test does the same.
- **Use symmetric difference with pinned_charts() for the version-match test**: Catches both a missing entry and a stale version. The token test uses this exact assertion.

## Rejected alternatives

- **Keep str key and add a separate version list**: Two structures to keep in sync. The token test already proved the tuple key is simpler and the symmetric-difference check is one line.
- **Match by full tuple including version in the lookup**: Would require chart_values() to yield the version, changing the shared helper. The token test does not do this.
- **Subset check only (pinned_charts() - CHART_CLAIMS.keys())**: Would miss a stale entry for a chart that is no longer installed. The symmetric difference is stricter and matches the existing pattern.
