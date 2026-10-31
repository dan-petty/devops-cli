# Design

## Decisions

- **Edit the two defaults at their source.** `DEFAULT_ROADMAP_STAGE_FILTER` and `DEFAULT_IMPLEMENT_FILTERS` are the single places. The example ConfigMap repeats the stage filter, and a test holds that it equals the default.
- **Keep `status=ready` in both filters.** The filter of the setting must not be empty (`min_length=1`), and the entry says the intent. The jobs also leave out a not-Ready item whatever the filter says.
- **Add no setting for the implement filter.** The issue asks for a changed default only. A setting would be a second place for the value and new surface that no one asked for. The Service calls the default.
- **Keep the order.** Priority first, lowest issue number second. A test holds P0 before P3 under the new default.
- **Do not widen the stage prompt or the change shape.** Nothing in them assumes a bug (see the proposal).

## Rejected alternatives

- **Add `roadmap.implement.filter` to the settings and the ConfigMap.** The issue does not ask for it. The default lives in code and the Service uses it. A setting is a new key to document, test and sync. File it if the owner wants per-repository control.
- **Leave out `type/epic` in the judge.** No open issue has the label today, and a filter has no negation. The `Dependencies` check already leaves out an item that depends on an open issue. A new rule for a case that does not occur adds code for nothing.
- **Remove `status=ready` from the filters.** The setting needs one entry, and the judge would still leave out the items that are not Ready.
