# Design

## Decisions

- **`watch` starts in mode `on`.** It replaces two live rows, so a start in mode `plan` stops their work: no plan draft becomes ready and no conflict comment is posted. Mode `off` stays the stop switch of `watch`.
- **The five new rows keep the start in mode `plan`.** `resolve`, `group` and `split` are new steward rows, and `fix-checks` and `fix-conflict` are new fix rows. No live work moves to them.
- **The fix due marks follow the mode of the fix row.** `watch` sets a fix due mark only when the fix row exists and is not `off`, so no due mark waits for a row that does not run. Until the fix row is in mode `on`, the verdict also gets the route of a pull request of a person. In mode `plan` the fix row writes nothing to GitHub, so without this route a bot pull request with a conflict gets no comment, but `pr_conflicts` comments on it today.

## Rejected alternatives

- **A mode for each route of `watch`.** It adds config keys for one row. One mode for each row is the rule, and the fix route depends only on the mode of the fix row.
- **Keep `stage_ready` and `pr_conflicts` until `watch` leaves mode `plan`.** #5024 deletes the two rows, and the project adds no shim before `1.0.0`.
